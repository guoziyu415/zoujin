"""B-5 模拟局（验收第 1、2、3、5、6、8 组）：persona 照正式开局、AI 玩家看的 view() 和 manifest()、每一步的耗时、
评测的一局里记的账带 playthroughId。走到结局的三条路等 B-9 的结局（后端 2）合了再加。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from zoujin_backend import eval_api
from zoujin_backend.config import DEFAULT_WORLD, REPO, Settings
from zoujin_backend.db import store
from zoujin_backend.gateway import app as gateway_app
from zoujin_backend.models.text import FakeText, TextResult
from zoujin_backend.narrator import app as narrator_app
from zoujin_llm import Ledger, playthrough

from .conftest import OLD, PLAYER_LINE, SCHEMAS, Env
from .test_gateway import invite
from .test_manifest import Direct

pytestmark = pytest.mark.db

Json = Any

BOOK = "hashire-merosu"
SLICE = REPO / "worlds" / BOOK / "1.0.0-slice" / "world.json"
PERSONA = {"role": "role.traveler", "persona": "persona.canon-follower", "seed": 3}
HIDDEN = ("vars", "beats", "schedule", "beatResults", "facts")  # AI 玩家不能看的（WorldState 里的）


def shape(ev: Json) -> tuple[Any, ...]:
    check = ev["check"]["status"]
    return (ev["t"], ev["dt"], ev["actor"], ev["type"], ev["place"], ev["summary"], ev["effects"], check)


def keys(doc: Json) -> set[str]:
    if isinstance(doc, dict):
        return set(doc) | {k for v in doc.values() for k in keys(v)}
    if isinstance(doc, list):
        return {k for v in doc for k in keys(v)}
    return set()


def log_of(env: Env, pid: str, version: str) -> list[Json]:
    async def main() -> list[Json]:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                return await store.event_log(c, pid, version)
        finally:
            await engine.dispose()

    return asyncio.run(main())


@pytest.fixture
def db(env: Env, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_WORLD", raising=False)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    yield env


# —— 第 1 组：开局 ——


def test_persona_opens_like_the_gateway(db: Env) -> None:
    """同一个世界模型：网关 POST /v1/playthroughs 开的局和 persona 开的局，事件和快照一样（ID 除外）。"""
    settings = replace(db.settings, world=DEFAULT_WORLD)
    narrator = narrator_app.build(settings)
    with TestClient(gateway_app.create_app(settings, gateway_app.build(settings, Direct(narrator)))) as c:
        origin = {"Origin": str(c.base_url)}
        c.post("/v1/auth/login", json={"inviteCode": invite(db)}, headers=origin)
        r = c.post(
            "/v1/playthroughs",
            json={"bookId": BOOK, "roleId": "role.traveler"},
            headers={**origin, "Idempotency-Key": "k-b5"},
        )
        assert r.status_code == 201, r.text
        pid = r.json()["playthroughId"]
        via_gateway = c.get(f"/v1/playthroughs/{pid}/snapshot").json()
        c.portal.call(narrator.engine.dispose)  # type: ignore[union-attr]
    s = eval_api.setup(PERSONA, mode="text")
    opened = log_of(db, pid, s.book.version)
    assert opened and [shape(e) for e in s.events()] == [shape(e) for e in opened]
    mine = s.view()["snapshot"]
    assert {**mine, "playthroughId": pid} == via_gateway


def test_persona_setup_rules(db: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    mixes: list[Json] = [{"checkpoint": "sc.canon@beat.03"}, {"scenario": "sc.canon"}, {"events": []}]
    for mixed in mixes:
        with pytest.raises(ValueError, match="persona 不和"):
            eval_api.setup({**PERSONA, **mixed}, mode="text")
    monkeypatch.setenv("ZJ_WORLD", str(SLICE))
    with pytest.raises(ValueError, match="没有这个身份"):  # 切片只开了旅人
        eval_api.setup({**PERSONA, "role": "role.apprentice", "persona": "persona.vigil"}, mode="text")
    s = eval_api.setup(PERSONA, mode="text")
    assert s.book.path == SLICE
    (span,) = s.tracer.named("eval.setup")
    assert span["eval.persona"] == "persona.canon-follower" and span["eval.seed"] == 3
    assert span["playthrough_id"] == s.pid
    assert set(span) == {"playthrough_id", "mode", "eval.persona", "eval.seed", "duration_ms"}  # 只有 ID 和数
    assert isinstance(s.text, FakeText) and s.text.seed == 3  # 种子给假模型
    assert s.view()["snapshot"]["clock"]["t"] == s.book.roles["role.traveler"]["startT"]  # 起点是正式开局


def test_planted_memory_still_raises(db: Env) -> None:
    planted = {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "events": [{"effects": [], "memory": {}}]}
    with pytest.raises(eval_api.EvalNotImplemented, match="memory"):
        eval_api.setup(planted, mode="text")


# —— 第 2、3 组：AI 玩家看什么 ——


def test_view_is_what_the_gateway_shows(db: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZJ_WORLD", str(SLICE))
    s = eval_api.setup(PERSONA, mode="text")
    first = s.view()
    s.say(OLD, PLAYER_LINE)
    s.act("wait", None, {})
    seen = first["snapshot"]["lastSeq"]
    later = s.view(seen)
    gw = gateway_app.build(replace(db.settings, world=SLICE), Direct(None))  # type: ignore[arg-type]

    async def main() -> tuple[Json, list[Json], list[Json]]:
        try:
            return (
                await gw.snapshot(s.pid),
                await gw.visible_events(s.pid, 0, 10_000),
                await gw.visible_events(s.pid, seen, 10_000),
            )
        finally:
            await gw.engine.dispose()

    snap, every, after = asyncio.run(main())
    assert later["snapshot"] == snap and later["events"] == after
    assert s.view()["events"] == every and every  # 走了一轮、等了一会儿：有玩家看得见的事件
    assert all(e["seq"] > seen for e in later["events"])
    SCHEMAS.response("snapshot", 200, later["snapshot"])
    SCHEMAS.response("events", 200, {"events": every, "lastSeq": snap["lastSeq"]})
    assert not keys(later) & set(HIDDEN)
    hidden_seqs = {e["seq"] for e in s.events()} - {e["seq"] for e in every}
    assert hidden_seqs  # 只改时间的、不在场的占 seq，但 view() 里没有


def test_manifest_is_the_gateways(db: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZJ_WORLD", str(SLICE))
    s = eval_api.setup(PERSONA, mode="text")
    gw = gateway_app.build(replace(db.settings, world=SLICE), Direct(None))  # type: ignore[arg-type]
    asyncio.run(gw.engine.dispose())
    assert gw.manifest is not None and s.manifest() == gw.manifest.doc
    s.manifest()["roles"].clear()  # 给出去的是一份拷贝
    assert s.manifest() == gw.manifest.doc


# —— 第 5 组：每一步的耗时 ——


def test_every_step_says_how_long_it_took(db: Env) -> None:
    s = eval_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@t=1080"}, mode="text")
    steps = [
        s.say(OLD, PLAYER_LINE),
        s.say(OLD, "宿はどこですか。", hold=True),
        s.retract(2),
        s.advance(5),
        s.act("wait", None, {}),
        s.confirm("yes"),  # 没有草稿：error，也带耗时
        s.propose("城へ行く"),  # 收幕以前：invalid_request
        s.choose("nowhere"),
    ]
    for out in steps:
        assert isinstance(out["elapsedMs"], int) and out["elapsedMs"] >= 0, out


# —— 第 6、8 组：账本带这一局的 playthroughId ——


class Billed:
    """假模型外面包一层，每次调用像真客户端那样记一行账（CI 不调真模型）。"""

    def __init__(self, inner: FakeText, ledger: Ledger) -> None:
        self.inner, self.ledger, self.mode = inner, ledger, "fake"

    async def call(self, kind: str, request: Json) -> TextResult:
        got = await self.inner.call(kind, request)
        self.ledger.record(kind=kind, model="sonnet-5.5", usage={}, cost=0.0, ms=1.5, status="ok")
        return got

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return 0.0


def test_calls_in_an_eval_playthrough_carry_its_id(db: Env, tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    s = eval_api.setup(PERSONA, mode="text")
    s.text = Billed(FakeText(Settings.from_env().fake_text), Ledger(path, "claude", 1.0, item="s5"))  # type: ignore[assignment]
    s.say(OLD, PLAYER_LINE)
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert rows and {r["playthroughId"] for r in rows} == {s.pid}
    assert all((r["ms"], r["status"], r["item"]) == (2, "ok", "s5") for r in rows)
    with playthrough(None):
        Ledger(path, "claude", 1.0).record(kind="judge", model="opus-5.5", usage={}, cost=0.0)
    assert "playthroughId" not in json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    text = path.read_text(encoding="utf-8")
    assert PLAYER_LINE not in text and "宿" not in text  # 不写原话
