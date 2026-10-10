"""一口气推演（Sim）：和参考实现生成的黄金文件逐字段相等，情景的预期都符合，同一输入结果相同，续跑和一口气相同。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from zoujin_worldsim import OCCURRED, Sim

REPO = Path(__file__).resolve().parents[3]
WORLD_DIR = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
SCENARIOS: list[dict[str, Any]] = [
    {"id": "sc.canon", "note": "原著どおり（プレイヤーは何もしない）", "expect": "canon-reunion"}
] + json.loads((WORLD_DIR / "scenarios.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
SIM = Sim(WORLD)
ITEMS = {it["id"] for it in WORLD["items"]}
WATCH = WORLD["clock"]["deadline"]["watchBeat"]


def effects_of(action: str) -> list[dict[str, Any]]:
    for af in WORLD["affordances"]:
        if af["id"] == action:
            return list(af["effects"])
    for act in WORLD["acts"]:
        for ex in act.get("exits", []):
            for i, x in enumerate((ex.get("enRoute") or {}).get("choices", [])):
                if action == f"{ex['id']}.enRoute[{i}]":
                    return list(x["effects"])
    raise KeyError(action)


def test_golden_covers_24_simulations(golden: dict[str, Any]) -> None:
    assert list(golden["runs"]) == [sc["id"] for sc in SCENARIOS]
    assert len(golden["runs"]) == 24


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_run_matches_golden(sc: dict[str, Any], golden: dict[str, Any]) -> None:
    want = golden["runs"][sc["id"]]
    r = SIM.run(sc, role=ROLE)
    sig = WORLD["endings"]["signature"]
    got = {
        "outcome": r["outcome"],
        "signature": {
            "vars": {v: r["state"].get(v) for v in sig["vars"]},
            "beats": {b: r["status"].get(b) == "happened" for b in sig["beats"]},
        },
        "status": r["status"],
        "times": r["times"],
        "variant": r["variant"],
        "vars": {v["id"]: r["state"].get(v["id"]) for v in WORLD["stateVars"]},
        "holdings": {k: v for k, v in r["state"].items() if k in ITEMS},
        "where": r["where"],
        "arrival": r["times"].get(WATCH),
        "shift": r["shift"],
        "late": sorted(r["late"]),
        "auto": sorted(r["auto"]),
        "violations": [[t, x] for t, x in r["violations"]],
    }
    for key in want:
        assert got[key] == want[key], f"{sc['id']} 的 {key} 和黄金文件不同"


def test_canon_beats_match_golden(golden: dict[str, Any]) -> None:
    for bid, want in golden["canon_beats"].items():
        r = SIM.run({}, until=("beat", bid), role=ROLE)
        assert {"t": r["t"], "status": r["status"].get(bid), "where": r["where"]} == want, bid


def test_arrival_delta_matches_golden(golden: dict[str, Any]) -> None:
    for g in golden["arrival"]:
        got = SIM.arrival_delta({}, effects_of(g["action"]), g["t"], role=ROLE)
        assert got == {"minutes": g["minutes"], "inTime": g["inTime"]}, g


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_scenario_expectations(sc: dict[str, Any]) -> None:
    r = SIM.run(sc, role=ROLE)
    if not sc.get("gap"):
        assert r["outcome"] == sc["expect"]
    for var, val in sc.get("expectVars", {}).items():
        assert r["state"].get(var) == val, var
    for bid, want in sc.get("expectBeats", {}).items():
        st = r["status"].get(bid)
        assert (st if st in OCCURRED else "not-happened") == want, bid
    for bid, want in sc.get("expectTimes", {}).items():
        assert r["times"].get(bid) == want, bid
    for bid, want in sc.get("expectVariant", {}).items():
        assert r["variant"].get(bid) == want, bid


def _comparable(r: dict[str, Any]) -> str:
    keys = ("outcome", "status", "times", "state", "where", "variant", "shift", "violations")
    return json.dumps({k: r[k] for k in keys}, sort_keys=True, ensure_ascii=False)


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_same_input_same_result(sc: dict[str, Any]) -> None:
    assert _comparable(SIM.run(sc, role=ROLE)) == _comparable(Sim(WORLD).run(sc, role=ROLE))


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_resume_from_any_beat_equals_full_run(sc: dict[str, Any]) -> None:
    full = _comparable(SIM.run(sc, role=ROLE))
    for b in WORLD["beats"]:
        part = SIM.run(sc, until=("beat", b["id"]), role=ROLE)
        assert _comparable(SIM.resume(part, sc)) == full, f"{sc['id']} 从 {b['id']} 续跑"


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda sc: sc["id"])
def test_beats_happen_between_schedule_and_latest(sc: dict[str, Any]) -> None:
    # 到点发生，或者在等前提、之后再查时发生：不早于本局排定时间，不晚于 window.latest
    r = SIM.run(sc, role=ROLE)
    for b, t in r["times"].items():
        x = SIM.beats[b]
        assert x["window"]["canonical"] + r["shift"].get(b, 0) <= t <= x["window"]["latest"], b
