"""Golden tests for contract 1.6 (C-16) StateVar.valueRequires: both the reference implementation
reference/worldsim.py and the package's Sim are tested.

Cases as set by C-16 in contracts.md section 7: 39 is rejected, 40 passes; both orders within one event; only due beats
and the deadline (origin = schedule) are unrestricted, director events are still checked; setting bridge when the
bridge is gone is rejected; an unchanged value is not checked; a condition that stops holding after it is set is not
pursued. check_effects() of the event-by-event simulation is tested in test_incremental.py.

契約 1.6（C-16）StateVar.valueRequires のゴールデンテスト：参照実装 reference/worldsim.py とパッケージの Sim の
両方をテストする。

ケースは contracts.md 第 7 節の C-16 で決めたとおり：39 は拒否、40 は通る。同じイベント内の 2 通りの順序。
期限に達したビートと期限（origin = schedule）だけは制限されず、ディレクターイベントは判定する。橋がないときに
bridge を設定すると拒否。値が変わらなければ判定しない。設定後に条件が成り立たなくなっても追及しない。
イベントごとのシミュレーションの check_effects() は test_incremental.py でテストする。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from zoujin_worldsim import Sim

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
SIMS = {"reference": ref.Sim(world), "package": Sim(world)}


@pytest.fixture(params=list(SIMS))
def sim(request: pytest.FixtureRequest) -> Any:
    return SIMS[request.param]


def run(sim: Any, sc: dict[str, Any]) -> dict[str, Any]:
    """The reference implementation hard-codes the opening to the square; the package reads it from the role, so use
    the traveler (who also starts in the square).

    参照実装はオープニングを広場に固定している。パッケージはロールから読むので、旅人を使う（開始地点も広場）。
    """
    result: dict[str, Any] = sim.run(sc, role="role.traveler") if isinstance(sim, Sim) else sim.run(sc)
    return result


def state(**overrides: Any) -> dict[str, Any]:
    """The world model's initial values, with a few overridden via shorthands like trust=…, disposition=….

    世界モデルの初期値に、trust=…、disposition=… のような略記でいくつかの項目を上書きしたもの。
    """
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
def test_threshold(sim: Any, effect: dict[str, Any], trust: int, ok: bool) -> None:
    got = sim.value_requires([effect], state(trust=trust))
    assert (got == []) is ok
    if not ok:
        assert got[0]["var"] == "var.king.disposition" and got[0]["value"] == effect["value"]
        assert got[0]["note"]


def test_order_within_one_event(sim: Any) -> None:
    # ③ Judged on the state before each effect: raising trust first and then setting wavering passes; the reverse
    # does not
    # ③ 各 effect の前の状態で判定：先に信頼を上げてから wavering にすれば通り、逆は通らない
    assert sim.value_requires([inc("var.king.trust", 35), WAVERING], state(trust=5)) == []
    assert len(sim.value_requires([WAVERING, inc("var.king.trust", 35)], state(trust=5))) == 1


def test_scheduled_events_are_not_checked(sim: Any) -> None:
    # ① Due beats and the deadline (origin = schedule) are not checked: what makes the king change his heart in
    # beat.26 at the execution ground is the beat's preconditions
    # ① 期限に達したビートと期限（origin = schedule）は判定しない：刑場の beat.26 で王が改心するのはビートの
    # 前提条件による
    assert sim.value_requires([REFORMED], state(trust=5), origin="schedule") == []


def test_director_events_are_checked(sim: Any) -> None:
    # ① Director events also have actor system, but origin is director, so they are still checked: do not skip by actor
    # ① ディレクターイベントの actor も system だが origin は director なので判定する：actor でスキップしてはいけない
    event = {"actor": "system", "origin": "director", "effects": [REFORMED]}
    got = sim.value_requires(event["effects"], state(trust=5), origin=event["origin"])
    assert [(x["var"], x["value"]) for x in got] == [("var.king.disposition", "reformed")]


def test_bridge(sim: Any) -> None:
    assert sim.value_requires([BRIDGE], state(bridge="intact")) == []
    got = sim.value_requires([BRIDGE], state(bridge="destroyed"))
    assert [(x["var"], x["value"]) for x in got] == [("var.river.crossing", "bridge")]
    # In one event, wash the bridge away first, then say they crossed the bridge: judged on the state after the
    # previous effect
    # 同じイベント内で先に橋を流し、それから橋を渡ったとする：前の effect の後の状態で判定
    destroy = set_("var.bridge", "destroyed")
    assert len(sim.value_requires([destroy, BRIDGE], state(bridge="intact"))) == 1


def test_unchanged_value_is_not_checked(sim: Any) -> None:
    # ② Setting the current value is not checked (once trust drops below 40, writing wavering again is not a violation)
    # ② 今の値に設定するのは判定しない（信頼が 40 未満に下がった後、もう一度 wavering を書いても違反ではない）
    assert sim.value_requires([WAVERING], state(trust=10, disposition="wavering")) == []


def test_later_drop_is_not_a_violation(sim: Any) -> None:
    # ⑤ If the condition stops holding after it is set, it is not reverted automatically and is not a violation
    # ⑤ 設定後に条件が成り立たなくなっても、自動で戻さず、違反ともしない
    s = state(trust=40)
    assert sim.value_requires([WAVERING, inc("var.king.trust", -20)], s) == []
    assert s["var.king.trust"] == 40, (
        "value_requires does not change the state passed in / value_requires は渡された状態を変えない"
    )


def test_simulation_records_violations(sim: Any) -> None:
    # The simulation still applies events and records violations in violations; build_world uses it to check scenarios
    # シミュレーションはそれでもイベントを適用し、違反は violations に記録する。build_world はこれでシナリオを確認する
    bad = {"events": [{"t": 3000, "effects": [REFORMED]}], "beats": {"beat.18": {"to": "delayed", "minutes": 240}}}
    res = run(sim, bad)
    assert [(t, x["value"]) for t, x in res["violations"]] == [(3000, "reformed")]
    for sc in json.loads(SCENARIOS.read_text(encoding="utf-8")):
        assert run(sim, sc)["violations"] == [], sc["id"]
