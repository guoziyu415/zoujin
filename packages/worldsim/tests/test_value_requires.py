"""契约 1.6（C-16）StateVar.valueRequires 的黄金测试，测参考实现 reference/worldsim.py 的 value_requires()。

用例按 contracts.md 第 7 节 C-16 定的：39 被拒、40 能过；同一事件里顺序两种；系统事件不受限；桥不在时设 bridge 被拒；
值没变不判；设好以后条件不再成立不追究。W-1 把参考实现整理成包以后，包也要过这些用例。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
WORLD = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
SCENARIOS = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "scenarios.json"


def _load_reference() -> ModuleType:
    path = REPO / "packages" / "worldsim" / "reference" / "worldsim.py"
    spec = importlib.util.spec_from_file_location("worldsim_reference", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ref = _load_reference()
world: dict[str, Any] = json.loads(WORLD.read_text(encoding="utf-8"))
sim = ref.Sim(world)


def state(**overrides: Any) -> dict[str, Any]:
    """世界模型的初值，再按 trust=…、disposition=… 这样的简写改几项。"""
    names = {
        "trust": "var.king.trust",
        "disposition": "var.king.disposition",
        "bridge": "var.bridge",
        "crossing": "var.river.crossing",
    }
    s = {v["id"]: v["default"] for v in world["stateVars"]}
    for k, v in overrides.items():
        s[names[k]] = v
    return s


def set_(var: str, value: Any) -> dict[str, Any]:
    return {"op": "set", "var": var, "value": value}


def inc(var: str, by: int) -> dict[str, Any]:
    return {"op": "inc", "var": var, "by": by}


WAVERING = set_("var.king.disposition", "wavering")
REFORMED = set_("var.king.disposition", "reformed")
BRIDGE = set_("var.river.crossing", "bridge")


def test_world_has_the_three_rules() -> None:
    got = {(v["id"], r["value"]): r["when"] for v in world["stateVars"] for r in v.get("valueRequires", [])}
    assert got == {
        ("var.king.disposition", "wavering"): [{"var": "var.king.trust", "op": ">=", "value": 40}],
        ("var.king.disposition", "reformed"): [{"var": "var.king.trust", "op": ">=", "value": 70}],
        ("var.river.crossing", "bridge"): [{"var": "var.bridge", "op": "==", "value": "intact"}],
    }


@pytest.mark.parametrize(
    ("effect", "trust", "ok"),
    [(WAVERING, 39, False), (WAVERING, 40, True), (REFORMED, 69, False), (REFORMED, 70, True)],
)
def test_threshold(effect: dict[str, Any], trust: int, ok: bool) -> None:
    got = sim.value_requires([effect], state(trust=trust))
    assert (got == []) is ok
    if not ok:
        assert got[0]["var"] == "var.king.disposition" and got[0]["value"] == effect["value"]
        assert got[0]["note"]


def test_order_within_one_event() -> None:
    # ③ 按每个 effect 之前的状态判：先升信任再设 wavering 能过，反过来不过
    assert sim.value_requires([inc("var.king.trust", 35), WAVERING], state(trust=5)) == []
    assert len(sim.value_requires([WAVERING, inc("var.king.trust", 35)], state(trust=5))) == 1


def test_system_events_are_not_checked() -> None:
    # ① 到点的节拍和期限（origin = schedule）不判：刑场的 beat.26 让王改心靠的是节拍前提
    assert sim.value_requires([REFORMED], state(trust=5), system=True) == []


def test_bridge() -> None:
    assert sim.value_requires([BRIDGE], state(bridge="intact")) == []
    got = sim.value_requires([BRIDGE], state(bridge="destroyed"))
    assert [(x["var"], x["value"]) for x in got] == [("var.river.crossing", "bridge")]
    # 同一事件里先冲掉桥，再说过了桥：按前一个 effect 之后的状态判
    destroy = set_("var.bridge", "destroyed")
    assert len(sim.value_requires([destroy, BRIDGE], state(bridge="intact"))) == 1


def test_unchanged_value_is_not_checked() -> None:
    # ② 设成现在的值不判（信任掉到 40 以下以后，再写一次 wavering 不算违规）
    assert sim.value_requires([WAVERING], state(trust=10, disposition="wavering")) == []


def test_later_drop_is_not_a_violation() -> None:
    # ⑤ 设好以后条件不再成立，不自动改回、不算违规
    s = state(trust=40)
    assert sim.value_requires([WAVERING, inc("var.king.trust", -20)], s) == []
    assert s["var.king.trust"] == 40, "value_requires 不改传进来的状态"


def test_simulation_records_violations() -> None:
    # 推演照样应用事件，违反的记进 violations；build_world 拿它查情景
    bad = {"events": [{"t": 3000, "effects": [REFORMED]}], "beats": {"beat.18": {"to": "delayed", "minutes": 240}}}
    res = sim.run(bad)
    assert [(t, x["value"]) for t, x in res["violations"]] == [(3000, "reformed")]
    for sc in json.loads(SCENARIOS.read_text(encoding="utf-8")):
        assert sim.run(sc)["violations"] == [], sc["id"]
