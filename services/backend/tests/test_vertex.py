"""The real text model's client (B-2 acceptance group 8): the transport layer is swapped for httpx.MockTransport, with
no network and no credentials.

The project ID is a fake marker, and the tests check that it does not appear in the ledger, replays, logs or exception
messages. Since B-8 triage and extraction go through Claude (`test_claude.py`), but the Google client behaves the same
for every prompt kind: here triage and extraction are temporarily switched back to their B-2 Google settings to test it.

実テキストモデルのクライアント（B-2 受け入れ確認 第 8 グループ）：トランスポート層を httpx.MockTransport に差し替え、
ネットワークにも認証情報にも頼らない。

プロジェクト ID は偽の目印で、それが台帳、リプレイ、ログ、例外メッセージに現れないことを確認する。B-8 以降、振り分けと
抽出は Claude を通る（`test_claude.py`）が、Google のクライアントはどのプロンプト種別でも同じに動く：ここでは振り分けと
抽出を一時的に B-2 のときの Google の設定に戻してテストする。
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

PROJECT = "proj-marker-0000"  # fake; checks whether it leaks / 偽物。漏れていないか確認する
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
    # The prefix comes first and carries no sources / プレフィックスは先頭にあり、出典は含まない
    assert user.startswith("<world>\n") and "aozora:" not in user
    assert user.index("<world>") < user.index("<state>") < user.index("<turn>")
    # Angle brackets become full-width / 山括弧は全角に置き換える
    assert '<utterance speaker="player">＜b＞宿＜/b＞はどこ？</utterance>' in user
    regional = client(ok({"route": "chat"}, seen), tmp_path, location="asia-northeast1")
    asyncio.run(regional.call("triage", {"turn": REQ["turn"]}))
    assert seen[-1].url.host == "asia-northeast1-aiplatform.googleapis.com"
    # flash-lite sets no thinking level / flash-lite は思考レベルを設定しない
    assert "thinkingConfig" not in json.loads(seen[-1].content)["generationConfig"]


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
    # No response: cost 0 / 応答なし：費用 0
    assert [(x["status"], x["costUsd"]) for x in (limit, fail)] == [("error", 0), ("error", 0)]
    assert PROJECT not in json.dumps([limit, fail])
    # The call that failed the Schema also cost money and is recorded / Schema に合わなかった回も費用がかかり、記録する
    assert line["status"] == "bad-output" and line["ms"] >= 0
    # The narrator adds it to this turn's cost / ナレーターはこれをこのターンの費用に加える
    assert line["costUsd"] > 0 and e3.value.cost_usd == pytest.approx(line["costUsd"])


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
    # The total cap counts only the Google ledger
    # 総上限は Google の台帳のみ
    assert books.spent() == pytest.approx(0.95)
    # The per-item cap combines both ledgers (data #49) / 項目ごとの上限は 2 つの台帳の合計（データ #49）
    assert books.spent("e0-x") == pytest.approx(0.99)
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=1.0)
    with pytest.raises(BudgetStop):
        # The ledger has already spent 0.95 (recorded by E-0); with this call's estimate it exceeds 1.0
        # 台帳ではすでに 0.95 使っており（E-0 が記録）、今回の見積もりを足すと 1.0 を超える
        asyncio.run(rt.call("extract", REQ))
    assert seen == [] and guess > 0.05
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=100.0, max_item=0.01, item="s2d-01")
    with pytest.raises(BudgetStop):
        asyncio.run(rt.call("extract", REQ))  # per-item cap / 項目ごとの上限
    assert seen == []
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=100.0)
    asyncio.run(rt.call("extract", REQ))
    # The Claude ledger does not count / Claude の台帳は数えない
    assert len(seen) == 1 and Ledger(tmp_path / "ledger.jsonl", 1.0).spent() > 0.95
    rt = client(ok({"candidates": []}, seen), tmp_path, max_total=100.0, max_item=1.0, item="e0-x")
    with pytest.raises(BudgetStop):
        # Google 0.95 + Claude 0.04 + this call's estimate > 1.0: the Claude line also counts toward the item
        # Google 0.95 + Claude 0.04 + 今回の見積もり > 1.0：Claude の行も項目ごとの上限に数える
        asyncio.run(rt.call("extract", REQ))
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
    # Triage timing out twice counts as "possible"; extraction timing out twice → only the clock moves
    # 振り分けが 2 回タイムアウトしたら「可能性あり」、抽出が 2 回タイムアウトしたら → 時計だけ進む
    assert ex.timed_out
    billed = lines(tmp_path / "ledger.jsonl")
    assert [x["kind"] for x in billed] == ["triage", "triage", "extract", "extract"]
    assert all(x["costUsd"] > 0 and x["usage"] == {} for x in billed)
    # This turn's cost (playthrough_metrics) matches the ledger
    # このターンの費用（playthrough_metrics）は台帳と一致する
    assert spend.usd == pytest.approx(by_kind(billed))


def test_invalid_output_is_in_the_turn_spend(tmp_path: Path) -> None:
    def garbage(r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}], "usageMetadata": USAGE}
        )

    p = Pipeline(client(garbage, tmp_path), SCHEMAS, IdGen(), Tracer())
    spend = Spend()
    ex = asyncio.run(p.extract(BOOK, at(), TurnInput(character=OLD, player="宿は？"), spend))
    # Both attempts invalid: triage counts as "possible", extraction → only the clock moves
    # 2 回とも不合格：振り分けは「可能性あり」、抽出 → 時計だけ進む
    assert ex.timed_out
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
