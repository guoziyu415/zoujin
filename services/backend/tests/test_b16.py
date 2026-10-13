"""Acceptance checks for B-16 (world advancement and the director across four acts): the full draft runs through
four acts; at act transitions world advancement and beats are merged by time; mid-act advancement and director events
in front of the player; migration 0011. Goes through the eval entry point (the same path as the gateway), with the fake
model's `world` giving candidates by rule.

B-16（4 幕にわたる世界の進行とディレクター）の受け入れ確認：完全版の草稿で 4 幕を通す。幕切り替えでは世界の進行と
ビートを時刻順に合わせる。各幕の中盤の進行と、プレイヤーの目の前でのディレクターのイベント。マイグレーション 0011。
評価の入口（ゲートウェイと同じ経路）を通り、偽モデルの `world` が規則に従って候補を出す。
"""

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

# The same fixture as B-3: one game via the eval entry point / B-3 と同じ fixture：評価の入口の 1 ゲーム
game = test_b3.game

Json = Any


def rule(g: Game, output: Json, **when: Any) -> None:
    """Add one `world` output to this game's fake model.

    このゲームの偽モデルに `world` の出力を 1 つ加える。
    """
    text = g.s.text
    assert isinstance(text, FakeText)
    text.rules.append(FakeText._rule({"kind": "world", "when": when, "output": output, "times": 1}, "<test>"))


def calls(g: Game, kind: str) -> list[Json]:
    text = g.s.text
    assert isinstance(text, FakeText)
    return [r for k, r in text.calls if k == kind]


def close_act(g: Game) -> Json:
    """Fast-forward until this act closes and return the end of act.

    この幕が閉じるまで早送りし、幕末を返す。
    """
    for _ in range(80):
        end = g.row()["act_end"]
        if end is not None:
            return end
        g.s.advance(60)
    raise AssertionError("The act didn't close / 幕が閉じなかった")


def test_four_acts_on_the_full_draft(game: Callable[..., Game]) -> None:
    """Full draft: act 1 → act 2 → act 3 → act 4 → ending. Each act change calls world advancement once, and the beat
    schedule runs as usual.

    完全版の草稿：第一幕 → 第二幕 → 第三幕 → 第四幕 → エンディング。幕を移るたびに世界の進行を 1 回呼び、ビートの
    予定表は通常どおり進む。
    """
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
    """Slice, choosing city: the groom goes to the village as planned (not present, written after beat.08); the director
    candidate without a cause (D5) and the one outside the window are dropped; 「その頃」 doesn't list plans of
    characters the player hasn't met; the metrics record 1 plan.

    スライスで city を選ぶ：花婿はプランどおり村へ行く（その場にいない、beat.08 のあとに書く）。原因のないディレクター
    の候補（D5）と時間帯の外のものは捨てる。「その頃」はプレイヤーが会っていない登場人物のプランを載せない。指標には
    プランを 1 件記録する。
    """
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
    """After 8 judged dialogue turns in this act, a `mid` world advancement is queued: an environmental change in the
    square (director, in front of the player, caused by a player turn) is written and pushed to the frontend; a second
    one in front of the player in the same act is blocked by D3 / D4 (quota used up).

    この幕で対話 8 ターンの判定が済むと `mid` の世界の進行を 1 つ積む：広場の環境の変化（ディレクター、プレイヤーの
    目の前、原因はプレイヤーのターン）を書き、フロントエンドにプッシュする。同じ幕でプレイヤーの目の前の 2 件目は
    D3 / D4 で止まる（枠を使い切った）。
    """
    g = game("sc.canon@beat.02")
    for i in range(6):
        g.s.say("char.old-man", f"そうなのですか、{i}")
    seventh = g.s.say("char.old-man", "なるほど")
    assert calls(g, "world") == []
    cause = next(e["eventId"] for e in reversed(seventh["events"]) if e["actor"] == "player")
    # The time after the 8th turn (10 minutes per turn in act 1) / 8 ターン目のあとの時刻（第一幕は 1 ターン 10 分）
    t8 = int(eval_api._run(g.s._state())["t"]) + 10
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
    # 8th turn: `mid` is queued in the commit transaction, and this step's narrator run handles it next.
    # 8 ターン目：コミットのトランザクションで `mid` を積み、このステップのナレーターが続けて処理する。
    g.s.say("char.old-man", "そうでしたか")
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
