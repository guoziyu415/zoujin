"""Claude 的真客户端（B-8 验收第 2、3、4 组）：传输层换成假的，不联网、不用真 Key。

要 SDK 的几条（SDK 的错误怎么换、Key 不漏）用 `httpx.MockTransport` 接住 SDK 发的请求；CI 里没装可选依赖 real 的
任务跳过它们。模型 ID 用假的（`test-sonnet-5-5`：认得出档名和版本就行），Key 用一个假的记号，查它们不出现在账本、
回放、日志、Span 和异常消息里。台词都是为测试写的。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from zoujin_backend import config
from zoujin_backend.config import REPO, ConfigError, Settings, TextSpec, text_spec
from zoujin_backend.ids import IdGen
from zoujin_backend.models import claude
from zoujin_backend.models.claude import (
    API_EFFECT,
    EFFECT_DROPPED,
    EFFECT_VARIANTS,
    ClaudeText,
    api_schema,
    claude_ids,
    claude_text,
    schema_problems,
)
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.render import render_body
from zoujin_backend.models.text import (
    DEFAULTS,
    BadOutput,
    BudgetStop,
    FakeText,
    ModelCallFailed,
    RateLimited,
    Recording,
    ReplayMissing,
    ReplayText,
    key_of,
    real_text_model,
)
from zoujin_backend.narrator.pipeline import Pipeline, Spend, TurnInput
from zoujin_backend.trace import Tracer
from zoujin_llm import Ledger, Reply, claude_prices

from .conftest import SCHEMAS
from .test_rules import BOOK, OLD, at

Json = Any

KEY = "sk-ant-test-marker-0000"  # 假的；查它有没有漏出去
IDS = {"haiku": "test-haiku-5-5-idmark", "sonnet": "test-sonnet-5-5-idmark"}  # 假的模型 ID
ENV = {"ANTHROPIC_API_KEY": KEY, "ZJ_CLAUDE_HAIKU": IDS["haiku"], "ZJ_CLAUDE_SONNET": IDS["sonnet"]}
REQ = {"worldModelVersion": BOOK.version, "turn": {"character": OLD, "mode": "text", "player": "<b>宿</b>はどこ？"}}
USAGE = {"inputTokens": 1500, "cacheReadTokens": 17000, "cacheWriteTokens": 0, "outputTokens": 300}
TURN = TurnInput(character=OLD, player="宿は？")
CANDIDATE = {
    "actor": OLD,
    "type": "say",
    "origin": "turn",
    "summary": "老爺は、若いころ羊を追っていたと話した",
    "causes": [],
    "effects": [{"op": "improv", "character": OLD, "statement": "老爺は若いころ羊飼いだった"}],
    "needsConfirm": False,
}


class Fake:
    """假的传输层：记下发了什么，按顺序回给定的回答（或抛给定的异常）。"""

    def __init__(self, *replies: Reply | BaseException | Callable[[], Any]) -> None:
        self.replies = list(replies)
        self.sent: list[Json] = []

    async def create(self, params: Json) -> Reply:
        self.sent.append(params)
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(r, BaseException):
            raise r
        if callable(r):
            return await r()  # type: ignore[no-any-return]
        return r


def ok(output: Json, stop: str = "end_turn") -> Reply:
    return Reply(json.dumps(output, ensure_ascii=False), stop, dict(USAGE))


def client(
    transport: Any, tmp: Path, *, max_total: float = 1.0, max_item: float | None = None, item: str | None = None
) -> ClaudeText:
    return ClaudeText(
        transport=transport,
        ledger=Ledger(tmp / "ledger.jsonl", "claude", max_total, max_item, item),
        worlds=lambda v: BOOK.world,
        ids=IDS,
    )


def lines(path: Path) -> list[Json]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def by_kind(billed: list[Json]) -> dict[str, float]:
    out: dict[str, float] = {}
    for x in billed:
        out[x["kind"]] = out.get(x["kind"], 0.0) + x["costUsd"]
    return out


# —— 第 2 组：请求的形状 ——


def test_request_shape(tmp_path: Path) -> None:
    fake = Fake(ok({"candidates": []}))
    got = asyncio.run(client(fake, tmp_path).call("extract", REQ | {"state": {"t": 1080}}))
    assert got.output == {"candidates": []} and got.model == "sonnet-5.5"
    assert got.prompt_version == PROMPTS["extract"].version
    (p,) = fake.sent
    assert p["model"] == IDS["sonnet"] and p["max_tokens"] == config.TEXT["extract"].max_output
    world, instructions = p["system"]
    assert world["text"].startswith("<world>\n") and "aozora:" not in world["text"]  # 前缀不带出处
    assert world["cache_control"] == {"type": "ephemeral"}  # 缓存点打在世界模型前缀上
    assert instructions == {"type": "text", "text": PROMPTS["extract"].text, "cache_control": {"type": "ephemeral"}}
    (msg,) = p["messages"]
    assert msg["role"] == "user" and msg["content"] == render_body("extract", REQ | {"state": {"t": 1080}})
    assert "<world>" not in msg["content"] and msg["content"].index("<state>") < msg["content"].index("<turn>")
    assert '<utterance speaker="player">＜b＞宿＜/b＞はどこ？</utterance>' in msg["content"]  # 尖括号换成全角
    assert p["output_config"] == {"format": {"type": "json_schema", "schema": api_schema("extract")}, "effort": "low"}
    assert p["thinking"] == {"type": "between_tools"} and "temperature" not in p  # API 没有温度这个参数

    fake = Fake(ok({"route": "chat"}))
    asyncio.run(client(fake, tmp_path).call("triage", {"turn": REQ["turn"]}))
    (p,) = fake.sent
    assert p["model"] == IDS["haiku"] and p["thinking"] == {"type": "disabled"} and "temperature" not in p
    assert "effort" not in p["output_config"]
    assert [b["text"] for b in p["system"]] == [PROMPTS["triage"].text]  # 没有世界模型版本：没有前缀那一段

    fake = Fake(ok({"results": []}))
    asyncio.run(client(fake, tmp_path).call("check", REQ | {"candidates": []}))
    (p,) = fake.sent
    assert p["thinking"] == {"type": "adaptive"} and p["output_config"]["effort"] == "medium"
    assert "temperature" not in p


def test_the_prefix_is_built_once_per_version(tmp_path: Path) -> None:
    built: list[str] = []

    def worlds(v: str) -> Json:
        built.append(v)
        return BOOK.world

    rt = replace(client(Fake(ok({"candidates": []})), tmp_path), worlds=worlds)
    for _ in range(3):
        asyncio.run(rt.call("extract", REQ))
    assert built == [BOOK.version]


# —— 第 2 组：发给 API 的 Schema ——


def test_api_schemas_pass_the_local_check() -> None:
    for kind in PROMPTS:
        assert schema_problems(api_schema(kind)) == [], kind
    assert schema_problems({"type": "object", "properties": {"a": {"type": "string", "maxLength": 3}}}) == [
        "$：对象没有 additionalProperties: false",
        "$.a：有 maxLength",
    ]
    many = {f"p{i}": {"type": "string"} for i in range(25)}
    assert schema_problems({"type": "object", "properties": many, "additionalProperties": False}) == [
        "可选参数 25 个，超过 24"
    ]


def unions(node: Json) -> int:
    if isinstance(node, list):
        return sum(unions(x) for x in node)
    if not isinstance(node, dict):
        return 0
    subs = [*node.get("properties", {}).values(), *(node[k] for k in ("items", "anyOf") if k in node)]
    return ("anyOf" in node) + sum(unions(x) for x in subs)


def test_api_schemas_stay_as_small_as_what_passed() -> None:
    """B-8 小测（10-11）：提取 4 个联合类型、改写 5 个都过了，幕末打算原来 10 个，第一次调用就回 400。"""
    assert {k: unions(api_schema(k)) for k in ("extract", "rewrite", "plan")} == {"extract": 4, "rewrite": 5, "plan": 4}
    assert all(unions(api_schema(k)) <= 5 for k in PROMPTS)
    plan = api_schema("plan")["properties"]
    ops = {v["properties"]["op"]["const"] for v in plan["effects"]["items"]["anyOf"]}
    assert ops == {"inc", "beat", "learn", "relocate", "improv"}  # 不要 set、hold、promise
    alt = plan["alternative"]["anyOf"]
    assert alt[1] == {"type": "null"} and set(alt[0]["properties"]) == {"exit", "label", "with", "effects"}
    for out in ({"exit": "exit.1.city"}, {"label": "広場で待つ", "with": [], "effects": []}, None):
        doc = {"accepted": False, "label": None, "with": [], "effects": [], "narration": ["x"], "alternative": out}
        jsonschema.validate(doc, api_schema("plan"))
        jsonschema.validate(doc, PROMPTS["plan"].schema)  # 本地照旧按三种验


def test_the_full_schema_is_still_checked_locally(tmp_path: Path) -> None:
    four = {"candidates": [CANDIDATE] * 4}
    jsonschema.validate(four, api_schema("extract"))  # API 那份没有 maxItems：模型可能给 4 个
    with pytest.raises(BadOutput):
        asyncio.run(client(Fake(ok(four)), tmp_path).call("extract", REQ))  # 本地的完整 Schema 拦住
    got = asyncio.run(client(Fake(ok({"candidates": [CANDIDATE]})), tmp_path).call("extract", REQ))
    assert got.output["candidates"] == [CANDIDATE]


def test_fixture_outputs_fit_both_schemas() -> None:
    """假模型的规则里写的输出（模型会怎么答的样子）在发给 API 的 Schema 下也写得出来。"""
    seen = 0
    for path in sorted((REPO / "fixtures" / "fake-text").glob("*.json")):
        for r in json.loads(path.read_text(encoding="utf-8"))["rules"]:
            if "output" in r:
                jsonschema.validate(r["output"], PROMPTS[r["kind"]].schema)
                jsonschema.validate(r["output"], api_schema(r["kind"]))
                seen += 1
    assert seen >= 5


def test_effect_variants_follow_the_contract() -> None:
    schema = json.loads((REPO / "packages/contracts/schemas/data/event.schema.json").read_text(encoding="utf-8"))
    contract = {v["properties"]["op"]["const"]: v for v in schema["$defs"]["Effect"]["oneOf"]}
    assert set(contract) == set(EFFECT_VARIANTS)
    for op, v in contract.items():
        dropped = EFFECT_DROPPED.get(op, set())
        ours = EFFECT_VARIANTS[op]
        assert set(v["properties"]) - dropped == set(ours["properties"]), op
        assert set(v["required"]) - dropped == set(ours["required"]), op
    assert len(API_EFFECT["anyOf"]) == 8


# —— 第 2 组：回答、账本 ——


def test_ledger_line(tmp_path: Path) -> None:
    got = asyncio.run(client(Fake(ok({"candidates": []})), tmp_path, item="s2d-01").call("extract", REQ))
    want = claude_prices().cost("sonnet-5.5", USAGE)
    assert got.cost_usd == pytest.approx(want) and got.usage == USAGE
    (line,) = lines(tmp_path / "ledger.jsonl")
    assert (line["provider"], line["use"], line["kind"], line["model"], line["item"]) == (
        "claude",
        "product",
        "extract",
        "sonnet-5.5",
        "s2d-01",
    )
    assert line["costUsd"] == pytest.approx(want) and line["usage"] == USAGE
    assert line["status"] == "ok" and isinstance(line["ms"], int) and line["ms"] >= 0  # B-5
    assert "idmark" not in json.dumps(line)  # 模型 ID 不进账本


@pytest.mark.parametrize(
    "reply",
    [
        Reply(None, "refusal", dict(USAGE)),
        Reply('{"candidates": [', "max_tokens", dict(USAGE)),
        Reply("not json", "end_turn", dict(USAGE)),
        Reply('{"candidates": "none"}', "end_turn", dict(USAGE)),
    ],
)
def test_failed_answers_are_billed(reply: Reply, tmp_path: Path) -> None:
    with pytest.raises(BadOutput) as e:
        asyncio.run(client(Fake(reply), tmp_path).call("extract", REQ))
    (line,) = lines(tmp_path / "ledger.jsonl")
    assert line["costUsd"] > 0 and e.value.cost_usd == pytest.approx(line["costUsd"])
    assert line["status"] == "bad-output"


def test_no_answer_is_a_free_error_line(tmp_path: Path) -> None:
    """没有回应（连不上、5xx、429）：记一行 error，花费 0，照旧抛出（B-5）。"""
    for err in (ModelCallFailed("Claude HTTP 500"), RateLimited("Claude 回 429")):
        with pytest.raises(type(err)):
            asyncio.run(client(Fake(err), tmp_path).call("extract", REQ))
    rows = lines(tmp_path / "ledger.jsonl")
    assert [(x["status"], x["costUsd"], x["usage"]) for x in rows] == [("error", 0, {}), ("error", 0, {})]
    assert all(x["ms"] >= 0 and "playthroughId" not in x for x in rows)


def test_budget_stops_before_sending(tmp_path: Path) -> None:
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps({"provider": "claude", "kind": "judge", "costUsd": 0.99, "item": "e0-x"}) + "\n"
        + json.dumps({"provider": "google", "kind": "reply", "costUsd": 5.0, "item": "e0-x"}) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    fake = Fake(ok({"candidates": []}))
    with pytest.raises(BudgetStop, match="Claude 账本"):
        asyncio.run(client(fake, tmp_path, max_total=1.0).call("extract", REQ))  # 总上限只算 Claude 那本
    with pytest.raises(BudgetStop, match="单项上限"):
        asyncio.run(client(fake, tmp_path, max_total=100.0, max_item=5.5, item="e0-x").call("extract", REQ))
    assert fake.sent == []
    asyncio.run(client(fake, tmp_path, max_total=100.0).call("extract", REQ))  # Google 的 5 美元不算进 Claude 的总上限
    assert len(fake.sent) == 1


def test_cancelled_call_is_billed_at_the_estimate(tmp_path: Path) -> None:
    async def slow() -> Reply:
        await asyncio.sleep(1)
        return ok({"route": "chat"})

    rt = client(Fake(slow), tmp_path)
    p = Pipeline(rt, SCHEMAS, IdGen(), Tracer(), {"triage": 0.05, "extract": 0.05, "check": 0.05, "rewrite": 0.05})
    spend = Spend()
    ex = asyncio.run(p.extract(BOOK, at(), TURN, spend))
    assert ex.timed_out
    billed = lines(tmp_path / "ledger.jsonl")
    assert [x["kind"] for x in billed] == ["triage", "triage", "extract", "extract"]
    assert all(x["costUsd"] > 0 and x["usage"] == {} and x["provider"] == "claude" for x in billed)
    # 记到取消为止：慢回答要 1 秒，时限 50 毫秒。`ms` 从额度检查之后才计时，比 `wait_for` 起算得晚，
    # 负载高时差得更多，所以不卡下限
    assert all(x["status"] == "timeout" and 0 < x["ms"] < 1000 for x in billed)
    assert billed[2]["costUsd"] == pytest.approx(rt.cancelled_cost("extract", extract_request()))
    assert spend.usd == pytest.approx(by_kind(billed))  # 这一轮的花费（playthrough_metrics）和账本对得上


def extract_request() -> Json:
    """流水线给 TURN 发的提取请求（同样的局面请求一样）。"""
    fake = FakeText()
    asyncio.run(Pipeline(fake, SCHEMAS, IdGen(), Tracer()).extract(BOOK, at(), TURN, Spend()))
    return next(r for k, r in fake.calls if k == "extract")


# —— 第 2 组：429、529 和别的错误（要 SDK） ——


def sdk_client(handler: Callable[[Any], Any]) -> Any:
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")  # SDK 用的 httpx 分支
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return anthropic.AsyncAnthropic(max_retries=0, http_client=http)


def message(output: Json) -> Json:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": IDS["sonnet"],
        "content": [
            {"type": "thinking", "thinking": "考え中", "signature": "sig"},
            {"type": "text", "text": json.dumps(output, ensure_ascii=False)},
        ],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 1500,
            "output_tokens": 300,
            "cache_read_input_tokens": 17000,
            "cache_creation_input_tokens": 0,
            "output_tokens_details": {"thinking_tokens": 120},
        },
    }


def test_sdk_errors_and_the_key_never_leave(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    httpx = pytest.importorskip("httpx2")
    from zoujin_llm.claude import AsyncTransport

    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    caplog.set_level(logging.DEBUG)
    statuses = iter([200, 200, 429, 529, 500, 400])
    seen: list[Any] = []

    def handler(r: Any) -> Any:
        seen.append(r)
        assert r.headers["x-api-key"] == KEY  # SDK 自己从环境变量读的
        code = next(statuses)
        if code == 200:
            out: Json = {"route": "maybe"} if json.loads(r.content)["model"] == IDS["haiku"] else {"candidates": []}
            return httpx.Response(200, json=message(out))
        kind = {429: "rate_limit_error", 529: "overloaded_error", 500: "api_error"}.get(code, "invalid_request_error")
        return httpx.Response(code, json={"type": "error", "error": {"type": kind, "message": f"bad key {KEY}"}})

    tracer = Tracer()
    rt = Recording(client(AsyncTransport(sdk_client(handler)), tmp_path), tmp_path / "rec")
    p = Pipeline(rt, SCHEMAS, IdGen(), tracer)
    ex = asyncio.run(p.extract(BOOK, at(), TURN, Spend()))
    assert not ex.timed_out and ex.candidates == []
    sent = json.loads(seen[1].content)
    assert sent["model"] == IDS["sonnet"] and sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["messages"][0]["content"] == render_body("extract", extract_request())
    errors: list[BaseException] = []
    for _ in range(2):  # 跑：第一个 429、529 就停，不重发
        with pytest.raises(RateLimited) as e:
            asyncio.run(p.extract(BOOK, at(), TURN, Spend()))
        errors.append(e.value)
    for _ in range(2):
        with pytest.raises(ModelCallFailed) as e2:
            asyncio.run(rt.call("extract", REQ))
        errors.append(e2.value)
    assert len(seen) == 6  # SDK 不自己重试
    assert [str(e) for e in errors] == [
        "Claude 回 429（限流或过载），停下",
        "Claude 回 529（限流或过载），停下",
        "Claude HTTP 500 api_error（消息不记）",
        "Claude HTTP 400 invalid_request_error（消息不记）",
    ]
    assert all(e.__cause__ is None and e.__suppress_context__ for e in errors)  # 原异常不跟着打印
    spans = json.dumps([s.attrs for s in tracer.spans], ensure_ascii=False)
    outputs = [
        caplog.text,
        spans,
        *(repr(e) for e in errors),
        (tmp_path / "ledger.jsonl").read_text(encoding="utf-8"),
        *(f.read_text(encoding="utf-8") for f in (tmp_path / "rec").glob("*.jsonl")),
    ]
    for text in outputs:
        assert KEY not in text and "idmark" not in text  # Key、模型 ID 都不出去
    recs = [r for f in sorted((tmp_path / "rec").glob("*.jsonl")) for r in lines(f)]
    assert [(r["kind"], r["provider"], r["model"]) for r in recs] == [
        ("extract", "claude", "sonnet-5.5"),
        ("triage", "claude", "haiku-5.5"),
    ]
    assert recs[0]["usage"] == USAGE | {"thinkingTokens": 120}  # 思考的 token 只用来看，含在 outputTokens 里
    assert recs[0]["costUsd"] == pytest.approx(claude_prices().cost("sonnet-5.5", USAGE))


# —— 第 3 组：配置 ——


def settings(tmp: Path, **kw: Any) -> Settings:
    base = Settings(database_url="postgresql+psycopg://x", model="real", ledger=tmp / "l.jsonl", max_claude_usd=1.0)
    return replace(base, **kw)


@pytest.mark.parametrize(
    ("env", "said"),
    [
        ({k: v for k, v in ENV.items() if k != "ANTHROPIC_API_KEY"}, "没设 ANTHROPIC_API_KEY"),
        ({k: v for k, v in ENV.items() if k != "ZJ_CLAUDE_SONNET"}, "没设 ZJ_CLAUDE_SONNET"),
        (ENV | {"ZJ_CLAUDE_SONNET": "test-sonnet-5-6-idmark"}, "ZJ_CLAUDE_SONNET 认出来是 sonnet-5.6"),
        (ENV | {"ZJ_CLAUDE_HAIKU": "mystery-model-idmark"}, "ZJ_CLAUDE_HAIKU 认不出档名和版本"),
        (ENV | {"ZJ_CLAUDE_HAIKU": IDS["sonnet"]}, "ZJ_CLAUDE_HAIKU 认出来是 sonnet-5.5"),
    ],
)
def test_claude_needs_key_ids_and_cap(env: dict[str, str], said: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as e:
        claude_text(settings(tmp_path), env=env, transport=Fake(ok({})))
    assert said in str(e.value) and "idmark" not in str(e.value) and KEY not in str(e.value)


def test_claude_needs_a_ledger_and_its_own_cap(tmp_path: Path) -> None:
    for s in (settings(tmp_path, max_claude_usd=None, max_google_usd=50.0), settings(tmp_path, ledger=None)):
        with pytest.raises(ConfigError, match="ZJ_MAX_CLAUDE_USD"):
            claude_text(s, env=ENV, transport=Fake(ok({})))
    rt = claude_text(settings(tmp_path, max_item_usd=2.0, ledger_item="b8-probe"), env=ENV, transport=Fake(ok({})))
    assert rt.ids == IDS and rt.ledger.provider == "claude" and rt.ledger.max_total_usd == 1.0
    assert (rt.ledger.item, rt.ledger.max_item_usd, rt.ledger.use) == ("b8-probe", 2.0, "product")


def test_claude_only_runs_do_not_need_vertex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake(ok({"candidates": []}))
    monkeypatch.setattr("zoujin_llm.claude.AsyncTransport", lambda: fake)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    for k in ("ZJ_VERTEX_PROJECT", "ZJ_VERTEX_LOCATION"):
        monkeypatch.delenv(k, raising=False)
    routed = real_text_model(settings(tmp_path))  # 没设 Vertex 的环境变量也建得起来
    assert asyncio.run(routed.call("extract", REQ)).model == "sonnet-5.5" and len(fake.sent) == 1
    with pytest.raises(ConfigError, match="ZJ_VERTEX_PROJECT"):
        asyncio.run(routed.call("reply", REQ))  # 真要调 Google 的那一种才查
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        real_text_model(settings(tmp_path))  # Claude 的少了：一开始就退出


def test_tier_override() -> None:
    env = {"ZJ_TEXT_MODELS": " check=haiku-5.5 , extract=haiku-5.5"}
    check = text_spec("check", env)
    assert check.model == "haiku-5.5" and check.thinking == "adaptive" and check.effort == "medium"
    assert text_spec("rewrite", env) == config.TEXT["rewrite"]
    for bad in ("reply=haiku-5.5", "check=gemini-3.8-flash", "check=haiku"):
        with pytest.raises(ConfigError):
            text_spec(bad.split("=")[0], {"ZJ_TEXT_MODELS": bad})


def test_tier_override_moves_keys_and_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    before = key_of("check", REQ)
    monkeypatch.setenv("ZJ_TEXT_MODELS", "check=haiku-5.5")
    assert key_of("check", REQ) != before and key_of("check", REQ).startswith("claude|haiku-5.5|")
    ids, problems = claude_ids(ENV)
    assert problems == [] and ids == IDS
    monkeypatch.setenv("ZJ_TEXT_MODELS", "check=haiku-5.6")
    _, problems = claude_ids(ENV)
    assert problems == ["同一档配了两个版本：haiku-5.5、haiku-5.6"]


# —— 第 4 组：回放按供应商分开 ——


def test_a_google_replay_does_not_answer_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    google = TextSpec("google", "sonnet-5.5", 15.0, 4096, thinking="LOW")  # 型号的写法一样，只差供应商
    monkeypatch.setitem(config.TEXT, "extract", google)
    asyncio.run(Recording(FakeText(), tmp_path).call("extract", REQ))
    assert asyncio.run(ReplayText(tmp_path).call("extract", REQ)).output == DEFAULTS["extract"](REQ)
    monkeypatch.setitem(config.TEXT, "extract", replace(google, provider="claude"))
    with pytest.raises(ReplayMissing, match="claude sonnet-5.5"):
        asyncio.run(ReplayText(tmp_path).call("extract", REQ))


# —— 服务玩家时的 429、529：当作这一次失败（B-8 第 4 条） ——


@pytest.mark.parametrize("mode", ["stop", "degrade"])
def test_rate_limit_stops_runs_and_degrades_serving(mode: str) -> None:
    fake = FakeText(rules=[{"kind": "extract", "error": "rate-limit"}])
    tracer = Tracer()
    p = Pipeline(fake, SCHEMAS, IdGen(), tracer, on_rate_limit=mode)
    run = p.extract(BOOK, at(), TURN, Spend())
    if mode == "stop":
        with pytest.raises(RateLimited):
            asyncio.run(run)
        assert [k for k, _ in fake.calls] == ["triage", "extract"]
        return
    ex = asyncio.run(run)
    assert ex.timed_out and ex.candidates == []  # 重发一次还不行：这一轮只走时钟
    assert [k for k, _ in fake.calls] == ["triage", "extract", "extract"]
    assert [s["status"] for s in tracer.named("narrator.extract")] == [
        "rate_limited",
        "rate_limited",
    ]


def test_spans_say_which_provider() -> None:
    tracer = Tracer()
    p = Pipeline(FakeText(), SCHEMAS, IdGen(), tracer)
    asyncio.run(p.extract(BOOK, at(), TURN, Spend()))
    calls: list[Mapping[str, Any]] = [*tracer.named("narrator.triage"), *tracer.named("narrator.extract")]
    assert [(s["provider"], s["model"]) for s in calls] == [("claude", "haiku-5.5"), ("claude", "sonnet-5.5")]


def test_module_has_no_model_ids() -> None:
    """仓库里只写档名加版本：真的模型 ID 只在 Mac 的环境变量里。"""
    for path in (Path(claude.__file__), Path(config.__file__)):
        assert "claude-" not in path.read_text(encoding="utf-8").replace("claude-prices", "")
