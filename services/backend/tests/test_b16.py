"""B-16（四幕的世界推进和导演）的验收：完整草稿走通四幕；幕切换时世界推进和节拍按时刻合并；每幕中段的推进和在玩家
面前的导演事件；迁移 0011。走评测入口（和网关同一条路），假模型的 `world` 按规则给候选。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_backend import eval_api
from zoujin_backend.config import async_url
from zoujin_backend.models.text import FakeText

from . import test_b3
from .conftest import alembic_config, truncate
from .test_b3 import CITY, DRAFT, Game

pytestmark = pytest.mark.db

game = test_b3.game  # 和 B-3 同一个 fixture：评测入口的一局

Json = Any


def rule(g: Game, output: Json, **when: Any) -> None:
    """给这一局的假模型加一条 `world` 的输出。"""
    text = g.s.text
    assert isinstance(text, FakeText)
    text.rules.append(FakeText._rule({"kind": "world", "when": when, "output": output, "times": 1}, "<test>"))


def calls(g: Game, kind: str) -> list[Json]:
    text = g.s.text
    assert isinstance(text, FakeText)
    return [r for k, r in text.calls if k == kind]


def close_act(g: Game) -> Json:
    """快进到这一幕收幕，返回幕末。"""
    for _ in range(80):
        end = g.row()["act_end"]
        if end is not None:
            return end
        g.s.advance(60)
    raise AssertionError("这一幕没有收")


def test_four_acts_on_the_full_draft(game: Callable[..., Game]) -> None:
    """完整草稿：第一幕 → 第二幕 → 第三幕 → 第四幕 → 结局。每次换幕调一次世界推进，节拍时间表照走。"""
    g = game("sc.canon@beat.07", world=DRAFT)
    seen = []
    for exit_id, to_act, t in (("exit.1.city", "act.2", 1440), ("exit.2.city", "act.3", 2040)):
        assert exit_id in [o["optionId"] for o in close_act(g)["options"]]
        step = g.s.choose(exit_id)
        st = eval_api._run(g.s._state())
        seen.append((step["toAct"], st["t"], st["vars"]["var.act.current"]))
        assert (step["toAct"], st["t"]) == (to_act, t)
    end = close_act(g)
    assert "exit.3.city" in [o["optionId"] for o in end["options"]]
    g.s.choose("exit.3.city")
    st = eval_api._run(g.s._state())
    assert (st["vars"]["var.act.current"], st["t"]) == ("act.4", 4590)
    for _ in range(20):
        if g.row()["status"] != "active":
            break
        g.s.advance(60)
    st = eval_api._run(g.s._state())
    assert st["beats"]["beat.24"] == "happened" and g.row()["status"] == "ended"
    reasons = [r["reason"] for r in calls(g, "world")]
    assert reasons.count("act") == 3
    act_calls = [r for r in calls(g, "world") if r["reason"] == "act"]
    assert [(r["window"]["from"] <= r["window"]["to"]) for r in act_calls] == [True, True, True]


def test_world_events_are_written_with_the_beats_at_act_change(game: Callable[..., Game]) -> None:
    """切片选 city：花婿照打算去村子（不在场，写在 beat.08 之后），导演候选没有原因（D5）、超出时间段的丢掉；
    「その頃」不列玩家没见过的人物的打算；指标记 1 件打算。"""
    g = game("sc.canon@beat.07")
    t0 = int(eval_api._run(g.s._state())["t"])
    beat08 = 2040
    move = [{"op": "relocate", "character": "char.groom", "place": "place.village"}]
    rule(
        g,
        {
            "events": [
                {
                    "t": beat08 + 60,
                    "actor": "char.groom",
                    "origin": "plan",
                    "type": "move",
                    "place": "place.village",
                    "summary": "花婿は婚礼の仕度のため、村へ出向いた",
                    "causes": [],
                    "effects": move,
                },
                {
                    "t": t0 + 30,
                    "actor": "char.travelers",
                    "origin": "director",
                    "type": "action",
                    "place": "place.road-to-city",
                    "summary": "旅の者たちが、街道で足を止めた",
                    "causes": [],
                    "effects": [{"op": "relocate", "character": "char.travelers", "place": "place.road-to-city"}],
                },
                {
                    "t": 6000,
                    "actor": "char.groom",
                    "origin": "plan",
                    "type": "move",
                    "place": "place.groom-house",
                    "summary": "花婿は家へ戻った",
                    "causes": [],
                    "effects": [{"op": "relocate", "character": "char.groom", "place": "place.groom-house"}],
                },
            ]
        },
        reason="act",
    )
    step = g.s.choose(CITY)
    (req,) = calls(g, "world")
    assert req["window"]["from"] == t0 and req["window"]["to"] == 5370 and req["director"]["present"] is False
    assert "char.groom" in [c["id"] for c in req["characters"]]
    evs = step["events"]
    mine = [e for e in evs if e.get("origin") in ("plan", "director")]
    assert [(e["actor"], e["t"], e["origin"], e["check"]["status"]) for e in mine] == [
        ("char.groom", beat08 + 60, "plan", "passed")
    ]
    i = evs.index(mine[0])
    assert any(x.get("beat") == "beat.08" for e in evs[:i] for x in e["effects"])
    assert evs[-1]["type"] == "act-transition" and evs[-1]["t"] == 5370
    (transition,) = g.push(step)
    assert mine[0]["eventId"] not in [x["eventId"] for x in transition["recap"]]
    m = g.metrics()
    assert (m["world_events"], m["director_events"]) == (1, 0)


def test_mid_act_advance_after_eight_talks_and_a_director_event_in_sight(game: Callable[..., Game]) -> None:
    """这一幕判完 8 轮对话排一个 `mid` 的世界推进：广场上的环境变化（导演，在玩家面前，原因是玩家的一轮）写进去、
    推给前端；同一幕第二件在玩家面前的被 D3 / D4 挡掉（名额用完）。"""
    g = game("sc.canon@beat.02")
    for i in range(6):
        g.s.say("char.old-man", f"そうなのですか、{i}")
    seventh = g.s.say("char.old-man", "なるほど")
    assert calls(g, "world") == []
    cause = next(e["eventId"] for e in reversed(seventh["events"]) if e["actor"] == "player")
    t8 = int(eval_api._run(g.s._state())["t"]) + 10  # 第 8 轮以后的此刻（第一幕一轮 10 分）
    learn = [{"op": "learn", "character": "char.young-man", "fact": "fact.six-killed-today"}]
    bell = {
        "t": t8,
        "actor": "system",
        "origin": "director",
        "type": "action",
        "place": "place.syracuse-square",
        "summary": "城の方から鐘が鳴り、若い衆が王の噂に耳をそばだてた",
        "causes": [cause],
        "effects": learn,
    }
    rule(g, {"events": [bell, {**bell, "summary": "もう一度、鐘が鳴った"}]}, reason="mid")
    seq = g.seq
    g.s.say("char.old-man", "そうでしたか")  # 第 8 轮：提交的事务里排 `mid`，这一步的叙事者接着做掉
    (req,) = calls(g, "world")
    assert req["reason"] == "mid" and req["director"] == {"present": True, "absent": 3}
    assert req["window"] == {**req["window"], "from": t8, "to": t8}
    written = [e for e in g.s.events() if e["seq"] > seq and e.get("origin") == "director"]
    assert [(e["actor"], e["causes"], e["effects"]) for e in written] == [("system", [cause], learn)]
    (commit,) = [m for m in g.commits(seq) if m["seq"] == written[0]["seq"]]
    assert commit["narration"] == ["城の方から鐘が鳴り、若い衆が王の噂に耳をそばだてた。"]
    assert g.metrics()["director_events"] == 1


def test_world_advance_can_be_switched_off(game: Callable[..., Game], monkeypatch: pytest.MonkeyPatch) -> None:
    g = game("sc.canon@beat.07")
    real = g.s._narrator

    def off(engine: Any) -> Any:
        n = real(engine)
        n.world_advance = False
        return n

    monkeypatch.setattr(g.s, "_narrator", off)
    step = g.s.choose(CITY)
    assert calls(g, "world") == [] and step["toAct"] == "act.4"


def test_migration_0011_goes_down_and_up(migrated: str) -> None:
    truncate(migrated)
    cfg = alembic_config(migrated)
    engine = create_async_engine(async_url(migrated), poolclass=NullPool)

    async def columns() -> set[str]:
        async with engine.connect() as c:
            return set(await c.run_sync(lambda sc: {x["name"] for x in inspect(sc).get_columns("playthrough_metrics")}))

    new = {"cost_world_usd", "world_events", "director_events"}
    try:
        command.downgrade(cfg, "0010")
        assert not new & eval_api._run(columns())
        command.upgrade(cfg, "head")
        assert new <= eval_api._run(columns())
    finally:
        command.upgrade(cfg, "head")
        eval_api._run(engine.dispose())
