"""Claude's real client (B-8 acceptance groups 2, 3, 4): the transport layer is swapped for a fake, with no network and
no real key.

The tests that need the SDK (how SDK errors are converted, the key not leaking) catch the SDK's requests with
`httpx.MockTransport`; CI jobs without the optional dependency real skip them. Model IDs are fake (`test-sonnet-5-5`:
enough for the tier name and version to be recognized), and the key is a fake marker; the tests check that they do not
appear in the ledger, replays, logs, Spans or exception messages. All lines are written for tests.

Claude の実クライアント（B-8 受け入れ確認 第 2、3、4 グループ）：トランスポート層を偽物に差し替え、ネットワークにも
本物のキーにも頼らない。

SDK が必要なテスト（SDK のエラーの変換、キーが漏れないこと）は `httpx.MockTransport` で SDK が送るリクエストを受け取る。
オプション依存 real を入れていない CI のジョブではスキップする。モデル ID は偽物（`test-sonnet-5-5`：ティア名と
バージョンを判別できれば十分）、キーは偽の目印で、それらが台帳、リプレイ、ログ、Span、例外メッセージに現れないことを
確認する。セリフはすべてテスト用に書いたもの。
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

KEY = "sk-ant-test-marker-0000"  # fake; checks whether it leaks / 偽物。漏れていないか確認する
IDS = {"haiku": "test-haiku-5-5-idmark", "sonnet": "test-sonnet-5-5-idmark"}  # fake model IDs / 偽のモデル ID
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
    """A fake transport layer: records what was sent and returns the given replies in order (or raises the given
    exceptions).

    偽のトランスポート層：送られたものを記録し、与えられた返答を順に返す（または与えられた例外を投げる）。
    """

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


# —— Group 2: the shape of the request / 第 2 グループ：リクエストの形 ——


def test_request_shape(tmp_path: Path) -> None:
    fake = Fake(ok({"candidates": []}))
    got = asyncio.run(client(fake, tmp_path).call("extract", REQ | {"state": {"t": 1080}}))
    assert got.output == {"candidates": []} and got.model == "sonnet-5.5"
    assert got.prompt_version == PROMPTS["extract"].version
    (p,) = fake.sent
    assert p["model"] == IDS["sonnet"] and p["max_tokens"] == config.TEXT["extract"].max_output
    world, instructions = p["system"]
    # The prefix carries no sources / プレフィックスに出典は含まない
    assert world["text"].startswith("<world>\n") and "aozora:" not in world["text"]
    # The cache breakpoint is on the world model prefix / キャッシュポイントは世界モデルのプレフィックスに打つ
    assert world["cache_control"] == {"type": "ephemeral"}
    assert instructions == {"type": "text", "text": PROMPTS["extract"].text, "cache_control": {"type": "ephemeral"}}
    (msg,) = p["messages"]
    assert msg["role"] == "user" and msg["content"] == render_body("extract", REQ | {"state": {"t": 1080}})
    assert "<world>" not in msg["content"] and msg["content"].index("<state>") < msg["content"].index("<turn>")
    # Angle brackets become full-width / 山括弧は全角に置き換える
    assert '<utterance speaker="player">＜b＞宿＜/b＞はどこ？</utterance>' in msg["content"]
    assert p["output_config"] == {"format": {"type": "json_schema", "schema": api_schema("extract")}, "effort": "low"}
    # The API has no temperature parameter / API に temperature パラメータはない
    assert p["thinking"] == {"type": "between_tools"} and "temperature" not in p

    fake = Fake(ok({"route": "chat"}))
    asyncio.run(client(fake, tmp_path).call("triage", {"turn": REQ["turn"]}))
    (p,) = fake.sent
    assert p["model"] == IDS["haiku"] and p["thinking"] == {"type": "disabled"} and "temperature" not in p
    assert "effort" not in p["output_config"]
    # No world model version: no prefix block / 世界モデルのバージョンなし：プレフィックスのブロックもない
    assert [b["text"] for b in p["system"]] == [PROMPTS["triage"].text]

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


# —— Group 2: the Schema sent to the API / 第 2 グループ：API に送る Schema ——


def test_api_schemas_pass_the_local_check() -> None:
    for kind in PROMPTS:
        assert schema_problems(api_schema(kind)) == [], kind
    assert schema_problems({"type": "object", "properties": {"a": {"type": "string", "maxLength": 3}}}) == [
        "$: object without additionalProperties: false / オブジェクトに additionalProperties: false がない",
        "$.a: has maxLength / maxLength がある",
    ]
    many = {f"p{i}": {"type": "string"} for i in range(25)}
    assert schema_problems({"type": "object", "properties": many, "additionalProperties": False}) == [
        "25 optional parameters, over 24 / 省略可能なパラメータが 25 個で 24 を超える"
    ]


def unions(node: Json) -> int:
    if isinstance(node, list):
        return sum(unions(x) for x in node)
    if not isinstance(node, dict):
        return 0
    subs = [*node.get("properties", {}).values(), *(node[k] for k in ("items", "anyOf") if k in node)]
    return ("anyOf" in node) + sum(unions(x) for x in subs)


def test_api_schemas_stay_as_small_as_what_passed() -> None:
    """B-8 small test (10-11): extraction with 4 unions and rewrite with 5 both passed; the end-of-act plan originally
    had 10, and the very first call returned 400.

    B-8 の小テスト（10-11）：抽出のユニオン型 4 個、書き換えの 5 個はどちらも通った。幕末のプランは元は 10 個で、最初の
    呼び出しで 400 が返った。
    """
    assert {k: unions(api_schema(k)) for k in ("extract", "rewrite", "plan")} == {"extract": 4, "rewrite": 5, "plan": 4}
    assert all(unions(api_schema(k)) <= 5 for k in PROMPTS)
    plan = api_schema("plan")["properties"]
    ops = {v["properties"]["op"]["const"] for v in plan["effects"]["items"]["anyOf"]}
    assert ops == {"inc", "beat", "learn", "relocate", "improv"}  # no set, hold, promise / set、hold、promise は不要
    alt = plan["alternative"]["anyOf"]
    assert alt[1] == {"type": "null"} and set(alt[0]["properties"]) == {"exit", "label", "with", "effects"}
    for out in ({"exit": "exit.1.city"}, {"label": "広場で待つ", "with": [], "effects": []}, None):
        doc = {"accepted": False, "label": None, "with": [], "effects": [], "narration": ["x"], "alternative": out}
        jsonschema.validate(doc, api_schema("plan"))
        # Locally still the three forms
        # ローカルは従来どおり 3 種類で検証
        jsonschema.validate(doc, PROMPTS["plan"].schema)


def test_the_full_schema_is_still_checked_locally(tmp_path: Path) -> None:
    four = {"candidates": [CANDIDATE] * 4}
    # The API copy has no maxItems: the model may give 4 / API 用には maxItems がない：モデルは 4 個返しうる
    jsonschema.validate(four, api_schema("extract"))
    with pytest.raises(BadOutput):
        # The full local Schema catches it / ローカルの完全な Schema が止める
        asyncio.run(client(Fake(ok(four)), tmp_path).call("extract", REQ))
    got = asyncio.run(client(Fake(ok({"candidates": [CANDIDATE]})), tmp_path).call("extract", REQ))
    assert got.output["candidates"] == [CANDIDATE]


def test_fixture_outputs_fit_both_schemas() -> None:
    """The outputs written in the fake model's rules (what the model's answers would look like) can also be written
    under the Schema sent to the API.

    偽モデルのルールに書いた出力（モデルがどう答えるかの見本）は、API に送る Schema でも書ける。
    """
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


# —— Group 2: replies, ledger / 第 2 グループ：返答、台帳 ——


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
    assert "idmark" not in json.dumps(line)  # model IDs stay out of the ledger / モデル ID は台帳に入れない


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
    """No response (unreachable, 5xx, 429): one error line, cost 0, re-raised as usual (B-5).

    応答なし（接続できない、5xx、429）：error の行を 1 つ記録し、費用 0、例外はそのまま投げる（B-5）。
    """
    for err in (ModelCallFailed("Claude HTTP 500"), RateLimited("Claude returned 429")):
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
    with pytest.raises(BudgetStop, match="Claude ledger"):
        # The total cap counts only the Claude ledger / 総上限は Claude の台帳だけを数える
        asyncio.run(client(fake, tmp_path, max_total=1.0).call("extract", REQ))
    with pytest.raises(BudgetStop, match="per-item cap"):
        asyncio.run(client(fake, tmp_path, max_total=100.0, max_item=5.5, item="e0-x").call("extract", REQ))
    assert fake.sent == []
    # Google's 5 dollars do not count toward Claude's total cap / Google の 5 ドルは Claude の総上限に数えない
    asyncio.run(client(fake, tmp_path, max_total=100.0).call("extract", REQ))
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
    # Recorded up to the cancellation: the slow answer takes 1 second and the time limit is 50 ms. `ms` starts timing
    # only after the quota check, later than `wait_for` starts, and the gap grows under high load, so there is no lower
    # bound
    # 取り消しまでを記録する：遅い返答は 1 秒、時間制限は 50 ミリ秒。`ms` は利用枠の確認の後から計時するので
    # `wait_for` より開始が遅く、負荷が高いと差が広がるため、下限は設けない
    assert all(x["status"] == "timeout" and 0 < x["ms"] < 1000 for x in billed)
    assert billed[2]["costUsd"] == pytest.approx(rt.cancelled_cost("extract", extract_request()))
    # This turn's cost (playthrough_metrics) matches the ledger
    # このターンの費用（playthrough_metrics）は台帳と一致する
    assert spend.usd == pytest.approx(by_kind(billed))


def extract_request() -> Json:
    """The extraction request the pipeline sends for TURN (the same situation gives the same request).

    パイプラインが TURN に対して送る抽出のリクエスト（同じ局面なら同じリクエスト）。
    """
    fake = FakeText()
    asyncio.run(Pipeline(fake, SCHEMAS, IdGen(), Tracer()).extract(BOOK, at(), TURN, Spend()))
    return next(r for k, r in fake.calls if k == "extract")


# —— Group 2: 429, 529 and other errors (needs the SDK) / 第 2 グループ：429、529 とその他のエラー（SDK が必要） ——


def sdk_client(handler: Callable[[Any], Any]) -> Any:
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")  # the httpx fork the SDK uses / SDK が使う httpx のフォーク
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
        # The SDK read it from the environment itself
        # SDK 自身が環境変数から読んだ
        assert r.headers["x-api-key"] == KEY
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
    for _ in range(2):  # runs stop at the first 429, 529, no resend / 実行は最初の 429、529 で止まり、再送しない
        with pytest.raises(RateLimited) as e:
            asyncio.run(p.extract(BOOK, at(), TURN, Spend()))
        errors.append(e.value)
    for _ in range(2):
        with pytest.raises(ModelCallFailed) as e2:
            asyncio.run(rt.call("extract", REQ))
        errors.append(e2.value)
    assert len(seen) == 6  # the SDK does not retry on its own / SDK は自分では再試行しない
    assert [str(e) for e in errors] == [
        "Claude returned 429 (rate limited or overloaded); stopping / "
        "Claude が 429 を返した（レート制限または過負荷）。停止する",
        "Claude returned 529 (rate limited or overloaded); stopping / "
        "Claude が 529 を返した（レート制限または過負荷）。停止する",
        "Claude HTTP 500 api_error (message not logged / メッセージは記録しない)",
        "Claude HTTP 400 invalid_request_error (message not logged / メッセージは記録しない)",
    ]
    # The original exception is not printed along / 元の例外は一緒に出力されない
    assert all(e.__cause__ is None and e.__suppress_context__ for e in errors)
    spans = json.dumps([s.attrs for s in tracer.spans], ensure_ascii=False)
    outputs = [
        caplog.text,
        spans,
        *(repr(e) for e in errors),
        (tmp_path / "ledger.jsonl").read_text(encoding="utf-8"),
        *(f.read_text(encoding="utf-8") for f in (tmp_path / "rec").glob("*.jsonl")),
    ]
    for text in outputs:
        assert KEY not in text and "idmark" not in text  # neither key nor model ID leaks / キーもモデル ID も外に出ない
    recs = [r for f in sorted((tmp_path / "rec").glob("*.jsonl")) for r in lines(f)]
    assert [(r["kind"], r["provider"], r["model"]) for r in recs] == [
        ("extract", "claude", "sonnet-5.5"),
        ("triage", "claude", "haiku-5.5"),
    ]
    # Thinking tokens are for information only and included in outputTokens
    # 思考トークンは参考用で、outputTokens に含まれる
    assert recs[0]["usage"] == USAGE | {"thinkingTokens": 120}
    assert recs[0]["costUsd"] == pytest.approx(claude_prices().cost("sonnet-5.5", USAGE))


# —— Group 3: configuration / 第 3 グループ：設定 ——


def settings(tmp: Path, **kw: Any) -> Settings:
    base = Settings(database_url="postgresql+psycopg://x", model="real", ledger=tmp / "l.jsonl", max_claude_usd=1.0)
    return replace(base, **kw)


@pytest.mark.parametrize(
    ("env", "said"),
    [
        ({k: v for k, v in ENV.items() if k != "ANTHROPIC_API_KEY"}, "ANTHROPIC_API_KEY is not set"),
        ({k: v for k, v in ENV.items() if k != "ZJ_CLAUDE_SONNET"}, "ZJ_CLAUDE_SONNET is not set"),
        (ENV | {"ZJ_CLAUDE_SONNET": "test-sonnet-5-6-idmark"}, "ZJ_CLAUDE_SONNET is recognized as sonnet-5.6"),
        (ENV | {"ZJ_CLAUDE_HAIKU": "mystery-model-idmark"}, "ZJ_CLAUDE_HAIKU: cannot recognize the tier name"),
        (ENV | {"ZJ_CLAUDE_HAIKU": IDS["sonnet"]}, "ZJ_CLAUDE_HAIKU is recognized as sonnet-5.5"),
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
    # Can be built without Vertex's environment variables / Vertex の環境変数がなくても作れる
    routed = real_text_model(settings(tmp_path))
    assert asyncio.run(routed.call("extract", REQ)).model == "sonnet-5.5" and len(fake.sent) == 1
    with pytest.raises(ConfigError, match="ZJ_VERTEX_PROJECT"):
        # Checked only for the kind that calls Google
        # Google を呼ぶ種類のときだけ確認
        asyncio.run(routed.call("reply", REQ))
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        # Claude's is missing: exits at the start
        # Claude の分が欠けている：最初に終了
        real_text_model(settings(tmp_path))


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
    assert problems == [
        "two versions configured for the same tier / 同じティアに 2 つのバージョンが設定されている: "
        "haiku-5.5, haiku-5.6"
    ]


# —— Group 4: replays are separated by provider / 第 4 グループ：リプレイはプロバイダごとに分ける ——


def test_a_google_replay_does_not_answer_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The model is written the same way, only the provider differs / モデルの書き方は同じで、プロバイダだけが違う
    google = TextSpec("google", "sonnet-5.5", 15.0, 4096, thinking="LOW")
    monkeypatch.setitem(config.TEXT, "extract", google)
    asyncio.run(Recording(FakeText(), tmp_path).call("extract", REQ))
    assert asyncio.run(ReplayText(tmp_path).call("extract", REQ)).output == DEFAULTS["extract"](REQ)
    monkeypatch.setitem(config.TEXT, "extract", replace(google, provider="claude"))
    with pytest.raises(ReplayMissing, match="claude sonnet-5.5"):
        asyncio.run(ReplayText(tmp_path).call("extract", REQ))


# —— 429, 529 while serving players: treated as a failure of this call (B-8 item 4)
# プレイヤーに提供中の 429、529：この呼び出しの失敗として扱う（B-8 第 4 項） ——


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
    # Still failing after one resend: this turn only advances the clock / 1 回再送してもだめ：このターンは時計だけ進む
    assert ex.timed_out and ex.candidates == []
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
    """The repo contains only tier names plus versions: real model IDs live only in environment variables on the Mac.

    リポジトリにはティア名とバージョンだけを書く：本物のモデル ID は Mac の環境変数にだけある。
    """
    for path in (Path(claude.__file__), Path(config.__file__)):
        assert "claude-" not in path.read_text(encoding="utf-8").replace("claude-prices", "")
