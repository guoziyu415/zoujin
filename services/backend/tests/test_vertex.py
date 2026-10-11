"""真文本模型的客户端（B-2 验收第 8 组）：传输层换成 httpx.MockTransport，不联网、不用凭证。

项目 ID 用一个假的记号，查它不出现在账本、回放、日志和异常消息里。B-8 以后分流和提取走 Claude（`test_claude.py`），
Google 的客户端对哪种提示都一样：这里把分流和提取临时换回 B-2 时的 Google 设定来测它。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from zoujin_backend import config
from zoujin_backend.config import PRICES, ConfigError, Settings, TextSpec
from zoujin_backend.ids import IdGen
from zoujin_backend.models import vertex
from zoujin_backend.models.ledger import Ledger, cost_usd
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import (
    BadOutput,
    BudgetStop,
    ModelCallFailed,
    RateLimited,
    Recording,
    ReplayText,
    replay_key,
)
from zoujin_backend.narrator.pipeline import Pipeline, Spend, TurnInput
from zoujin_backend.trace import Tracer

from .conftest import SCHEMAS
from .test_rules import BOOK, OLD, at

Json = Any

PROJECT = "proj-marker-0000"  # 假的；查它有没有漏出去
REQ = {"worldModelVersion": BOOK.version, "turn": {"character": OLD, "mode": "text", "player": "<b>宿</b>はどこ？"}}
USAGE = {
    "promptTokenCount": 12000,
    "cachedContentTokenCount": 10000,
    "candidatesTokenCount": 300,
    "thoughtsTokenCount": 200,
}


@pytest.fixture(autouse=True)
def google_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    flash, lite = "gemini-3.8-flash", "gemini-3.5-flash-lite"
    monkeypatch.setitem(config.TEXT, "triage", TextSpec("google", lite, 5.0, 256, temperature=0.0))
    monkeypatch.setitem(config.TEXT, "extract", TextSpec("google", flash, 15.0, 4096, thinking="LOW", temperature=0.2))


class Auth:
    def token(self) -> str:
        return "token-for-test"


def reply_body(output: Json, usage: Json = USAGE) -> Json:
    parts = [{"text": "考え中", "thought": True}, {"text": json.dumps(output, ensure_ascii=False)}]
    return {"candidates": [{"content": {"parts": parts}}], "usageMetadata": usage}


def client(
    handler: Callable[[httpx.Request], httpx.Response],
    tmp: Path,
    *,
    location: str = "global",
    max_total: float = 1.0,
    max_item: float | None = None,
    item: str | None = None,
) -> vertex.RealText:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return vertex.RealText(
        transport=vertex.RestTransport(PROJECT, location, Auth(), http),
        ledger=Ledger(tmp / "ledger.jsonl", max_total, max_item, item),
        worlds=lambda v: BOOK.world,
        regional=location != "global",
    )


def ok(output: Json, seen: list[httpx.Request] | None = None) -> Callable[[httpx.Request], httpx.Response]:
    def handler(r: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(r)
        return httpx.Response(200, json=reply_body(output))

    return handler


def lines(path: Path) -> list[Json]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def by_kind(billed: list[Json]) -> dict[str, float]:
    out: dict[str, float] = {}
    for x in billed:
        out[x["kind"]] = out.get(x["kind"], 0.0) + x["costUsd"]
    return out


def test_request_shape(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    rt = client(ok({"candidates": []}, seen), tmp_path, item="s2d-01")
    got = asyncio.run(rt.call("extract", REQ | {"state": {"t": 1080}}))
    assert got.output == {"candidates": []} and got.prompt_version == PROMPTS["extract"].version
    (r,) = seen
    assert r.url.host == "aiplatform.googleapis.com"
    assert r.url.path.endswith("/locations/global/publishers/google/models/gemini-3.8-flash:generateContent")
    assert r.headers["authorization"] == "Bearer token-for-test"
    body = json.loads(r.content)
    assert body["systemInstruction"]["parts"][0]["text"] == PROMPTS["extract"].text
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and cfg["responseJsonSchema"] == PROMPTS["extract"].schema
    assert cfg["thinkingConfig"] == {"thinkingLevel": "LOW"} and cfg["temperature"] == 0.2
    user = body["contents"][0]["parts"][0]["text"]
    assert user.startswith("<world>\n") and "aozora:" not in user  # 前缀在最前，不带出处
    assert user.index("<world>") < user.index("<state>") < user.index("<turn>")
    assert '<utterance speaker="player">＜b＞宿＜/b＞はどこ？</utterance>' in user  # 尖括号换成全角
    regional = client(ok({"route": "chat"}, seen), tmp_path, location="asia-northeast1")
    asyncio.run(regional.call("triage", {"turn": REQ["turn"]}))
    assert seen[-1].url.host == "asia-northeast1-aiplatform.googleapis.com"
    assert "thinkingConfig" not in json.loads(seen[-1].content)["generationConfig"]  # flash-lite 不设思考档


def test_cost_by_price_list_and_ledger_line(tmp_path: Path) -> None:
    rt = client(ok({"candidates": []}), tmp_path, item="s2d-01")
    got = asyncio.run(rt.call("extract", REQ))
    p = PRICES["gemini-3.8-flash"]
    want = (2000 * p["input"] + 10000 * p["cachedInput"] + 500 * p["output"]) / 1_000_000
    assert got.cost_usd == pytest.approx(want)
    assert got.usage == {"inputTokens": 12000, "cachedTokens": 10000, "outputTokens": 300, "thoughtTokens": 200}
    (line,) = lines(tmp_path / "ledger.jsonl")
    assert line["provider"] == "google" and line["kind"] == "extract" and line["model"] == "gemini-3.8-flash"
    assert line["costUsd"] == pytest.approx(want) and line["item"] == "s2d-01" and line["at"].endswith("Z")
    regional = client(ok({"candidates": []}), tmp_path / "r", location="us-central1")
    assert asyncio.run(regional.call("extract", REQ)).cost_usd == pytest.approx(want * 1.10)
    assert cost_usd("gemini-3.8-flash", {}, regional=False) == 0.0


def test_rate_limit_and_errors(tmp_path: Path) -> None:
    calls: list[int] = []

    def limited(r: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": f"quota for projects/{PROJECT}"}})

    with pytest.raises(RateLimited) as e:
        asyncio.run(client(limited, tmp_path).call("extract", REQ))
    assert PROJECT not in str(e.value) and len(calls) == 1

    def broken(r: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": f"projects/{PROJECT} broke"}})

    with pytest.raises(ModelCallFailed) as e2:
        asyncio.run(client(broken, tmp_path).call("extract", REQ))
    assert PROJECT not in str(e2.value)

    def garbage(r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}], "usageMetadata": USAGE}
        )

    with pytest.raises(BadOutput) as e3:
        asyncio.run(client(garbage, tmp_path).call("extract", REQ))
    limit, fail, line = lines(tmp_path / "ledger.jsonl")
    assert [(x["status"], x["costUsd"]) for x in (limit, fail)] == [("error", 0), ("error", 0)]  # 没有回应：花费 0
    assert PROJECT not in json.dumps([limit, fail])
    assert line["status"] == "bad-output" and line["ms"] >= 0  # 不合 Schema 的那次也花了钱，记账
    assert line["costUsd"] > 0 and e3.value.cost_usd == pytest.approx(line["costUsd"])  # 叙事者拿它加进这一轮的花费


def test_budget_caps_are_cumulative(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    guess = vertex.estimate_usd("gemini-3.8-flash", "extract", 50_000, regional=False)
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps({"provider": "google", "kind": "extract", "costUsd": 0.95, "item": "e0-x"}) + "\n"
        + json.dumps({"provider": "claude", "kind": "judge", "costUsd": 5.0}) + "\n"
        + json.dumps({"provider": "claude", "kind": "judge", "costUsd": 0.04, "item": "e0-x"}) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    books = Ledger(tmp_path / "ledger.jsonl", 1.0)
    assert books.spent() == pytest.approx(0.95)  # 总上限只算 Google 那本账
    assert books.spent("e0-x") == pytest.approx(0.99)  # 单项上限两本账合起来（数据 #49）
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=1.0)
    with pytest.raises(BudgetStop):
        asyncio.run(rt.call("extract", REQ))  # 账本里已经花了 0.95（E-0 记的），加这一次的预计超过 1.0
    assert seen == [] and guess > 0.05
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=100.0, max_item=0.01, item="s2d-01")
    with pytest.raises(BudgetStop):
        asyncio.run(rt.call("extract", REQ))  # 单项上限
    assert seen == []
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=100.0)
    asyncio.run(rt.call("extract", REQ))
    assert len(seen) == 1 and Ledger(tmp_path / "ledger.jsonl", 1.0).spent() > 0.95  # Claude 那本账不算
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=100.0, max_item=1.0, item="e0-x")
    with pytest.raises(BudgetStop):
        asyncio.run(rt.call("extract", REQ))  # Google 0.95 + Claude 0.04 + 这次的预计 > 1.0：Claude 那行也算进单项
    assert len(seen) == 1


def test_cancelled_call_is_billed_at_the_estimate(tmp_path: Path) -> None:
    async def slow(r: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json=reply_body({"candidates": []}))

    http = httpx.AsyncClient(transport=httpx.MockTransport(slow))
    rt = replace(client(ok({}), tmp_path), transport=vertex.RestTransport(PROJECT, "global", Auth(), http))
    p = Pipeline(rt, SCHEMAS, IdGen(), Tracer(), {"triage": 0.05, "extract": 0.05, "check": 0.05, "rewrite": 0.05})
    spend = Spend()
    ex = asyncio.run(p.extract(BOOK, at(), TurnInput(character=OLD, player="宿は？"), spend))
    assert ex.timed_out  # 分流两次超时当「可能」，提取两次超时 → 只走时钟
    billed = lines(tmp_path / "ledger.jsonl")
    assert [x["kind"] for x in billed] == ["triage", "triage", "extract", "extract"]
    assert all(x["costUsd"] > 0 and x["usage"] == {} for x in billed)
    assert spend.usd == pytest.approx(by_kind(billed))  # 这一轮的花费（playthrough_metrics）和账本对得上


def test_invalid_output_is_in_the_turn_spend(tmp_path: Path) -> None:
    def garbage(r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}], "usageMetadata": USAGE}
        )

    p = Pipeline(client(garbage, tmp_path), SCHEMAS, IdGen(), Tracer())
    spend = Spend()
    ex = asyncio.run(p.extract(BOOK, at(), TurnInput(character=OLD, player="宿は？"), spend))
    assert ex.timed_out  # 两次都不合格：分流当「可能」，提取 → 只走时钟
    billed = lines(tmp_path / "ledger.jsonl")
    assert [x["kind"] for x in billed] == ["triage", "triage", "extract", "extract"]
    assert spend.usd == pytest.approx(by_kind(billed)) and all(v > 0 for v in spend.usd.values())


def test_recorded_replays_have_the_b0_format(tmp_path: Path) -> None:
    rt = Recording(client(ok({"candidates": []}), tmp_path), tmp_path / "rec")
    asyncio.run(rt.call("extract", REQ))
    (rec,) = lines(tmp_path / "rec" / "extract.jsonl")
    assert set(rec) == {
        "key",
        "kind",
        "provider",
        "model",
        "promptVersion",
        "request",
        "response",
        "usage",
        "costUsd",
        "recordedAt",
    }
    assert rec["key"] == replay_key("google", "gemini-3.8-flash", PROMPTS["extract"].version, REQ)
    replayed = asyncio.run(ReplayText(tmp_path / "rec").call("extract", REQ))
    assert replayed.output == {"candidates": []} and replayed.cost_usd == rec["costUsd"]


def test_project_id_only_from_explicit_env(tmp_path: Path) -> None:
    settings = replace(
        Settings(database_url="postgresql+psycopg://x"), model="real", ledger=tmp_path / "l.jsonl", max_google_usd=1.0
    )
    for env in ({}, {vertex.PROJECT_ENV: PROJECT}, {vertex.LOCATION_ENV: "global"}):
        with pytest.raises(ConfigError):
            vertex.real_text(settings, env=env, transport=object())  # type: ignore[arg-type]
    no_cap = replace(settings, max_google_usd=None)
    with pytest.raises(ConfigError):
        vertex.real_text(no_cap, env={vertex.PROJECT_ENV: PROJECT, vertex.LOCATION_ENV: "global"})


def test_project_id_never_leaves(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    rt = Recording(client(ok({"candidates": []}), tmp_path, item="s2d-01"), tmp_path / "rec")
    asyncio.run(rt.call("extract", REQ))
    for p in (tmp_path / "ledger.jsonl", tmp_path / "rec" / "extract.jsonl"):
        assert PROJECT not in p.read_text(encoding="utf-8")
    assert PROJECT not in caplog.text
