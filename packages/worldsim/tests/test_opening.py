"""开局到起点（opening）：和逐事件推演一致、检查点停在对的地方、写出的事件 B-0 能直接补字段写库。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from zoujin_worldsim import SimState, apply, initial_state, opening, parse_checkpoint, settle

WORLD_DIR = Path(__file__).resolve().parents[3] / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
SCENARIOS: list[dict[str, Any]] = [{"id": "sc.canon", "expect": "canon-reunion"}] + json.loads(
    (WORLD_DIR / "scenarios.json").read_text(encoding="utf-8")
)
ROLE = "role.traveler"

type Played = Callable[[str], tuple[SimState, list[dict[str, Any]]]]


def scenario(sc_id: str) -> dict[str, Any]:
    return next(sc for sc in SCENARIOS if sc["id"] == sc_id)


def finish(s: SimState) -> SimState:
    return settle(WORLD, s, None)[1]


def test_parse_checkpoint() -> None:
    assert parse_checkpoint("sc.canon@beat.05") == ("sc.canon", ("beat", "beat.05"))
    assert parse_checkpoint("sc.king-hardened@t=1200") == ("sc.king-hardened", ("t", 1200))
    for bad in ("sc.canon", "sc.canon@", "@beat.05"):
        with pytest.raises(ValueError, match="检查点"):
            parse_checkpoint(bad)


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_scenario_equals_playing_it(sc: dict[str, Any], played: Played) -> None:
    """推演到底 = conftest 里按 W-1 卡逐事件推演的结果，事件一条不差。"""
    out, s = opening(WORLD, ROLE, sc)
    want_s, want_log = played(sc["id"])
    assert s == want_s
    assert [(d["event"]["t"], d["event"]["effects"]) for d in out] == [(e["t"], e["effects"]) for e in want_log]
    assert [d["event"]["seq"] for d in out] == list(range(1, len(out) + 1))
    assert s["deadline"]


def test_events_replay_to_the_same_state() -> None:
    out, s = opening(WORLD, ROLE, scenario("sc.detour"), place="place.syracuse-square")
    r = initial_state(WORLD, ROLE)
    for d in out:
        r = apply(WORLD, r, d["event"])
    assert r == s


def test_what_each_event_is() -> None:
    out, _ = opening(WORLD, ROLE, scenario("sc.king-hardened"), ("beat", "beat.07"), place="place.execution-ground")
    assert out[0]["source"] == "place" and out[0]["note"] == "開始地点"
    assert out[0]["event"]["effects"] == [
        {"op": "set", "var": "var.player.location", "value": "place.execution-ground"}
    ]
    hardened = next(d for d in out if d["source"] == "scenario")
    assert hardened["event"]["t"] == 1235 and hardened["event"]["origin"] == "action"
    assert hardened["event"]["place"] == "place.execution-ground"  # 玩家所在地
    beats = [d for d in out if d["source"] == "schedule"]
    assert all(d["event"]["origin"] == "schedule" and "note" not in d for d in beats)
    assert beats[-1]["beat"] == "beat.07"


@pytest.mark.parametrize("beat", ["beat.03", "beat.05", "beat.07", "beat.24"])
def test_checkpoint_stops_right_after_the_beat(beat: str) -> None:
    out, s = opening(WORLD, ROLE, None, ("beat", beat))
    assert out[-1]["beat"] == beat and s["beats"][beat] == "happened"
    assert s["t"] == s["times"][beat]
    assert finish(s) == opening(WORLD, ROLE, None)[1], "从检查点接着结算 = 一口气推演到底"


def test_checkpoint_at_a_minute_moves_the_clock() -> None:
    out, s = opening(WORLD, ROLE, None, ("t", 1210))  # beat.04 在 1200，beat.05 在 1230
    assert s["t"] == 1210 and s["beats"] == {
        "beat.01": "happened",
        "beat.02": "happened",
        "beat.03": "happened",
        "beat.04": "happened",
    }
    assert out[-1]["source"] == "clock" and out[-1]["event"]["effects"] == []
    _, at_beat = opening(WORLD, ROLE, None, ("t", 1200))
    assert at_beat["t"] == 1200 and at_beat["beats"]["beat.04"] == "happened", "那一刻到点的节拍也算"
    full = opening(WORLD, ROLE, None)[1]
    assert finish(s) == {**full, "seq": full["seq"] + 1}, "多了一个推时钟的事件，别的一样"


def test_checkpoint_at_the_deadline_includes_the_deadline_rule() -> None:
    dl = WORLD["clock"]["deadline"]["t"]
    _, s = opening(WORLD, ROLE, scenario("sc.river-delay"), ("t", dl))
    assert s["t"] == dl and s["deadline"]
    assert s["vars"]["var.hostage.fate"] == "executed"


def test_checkpoint_before_a_scenario_event_leaves_it_out() -> None:
    sc = scenario("sc.king-hardened")
    _, s = opening(WORLD, ROLE, sc, ("t", 1230))
    assert s["vars"]["var.king.trust"] == initial_state(WORLD, ROLE)["vars"]["var.king.trust"]
    _, s = opening(WORLD, ROLE, sc, ("t", 1240))
    assert s["vars"]["var.king.trust"] < initial_state(WORLD, ROLE)["vars"]["var.king.trust"]


def test_checkpoint_errors() -> None:
    with pytest.raises(ValueError, match="不存在"):
        opening(WORLD, ROLE, None, ("beat", "beat.99"))
    prevented = next(sc for sc in SCENARIOS if any(o.get("to") == "prevented" for o in sc.get("beats", {}).values()))
    beat = next(b for b, o in prevented["beats"].items() if o["to"] == "prevented")
    with pytest.raises(ValueError, match="没到检查点"):
        opening(WORLD, ROLE, prevented, ("beat", beat))


def test_does_not_change_its_input() -> None:
    sc = scenario("sc.detour")
    before = repr(sc)
    opening(WORLD, ROLE, sc, ("beat", "beat.18"))
    assert repr(sc) == before
