"""worldsim 测试共用的数据：『走れメロス』的世界模型、24 次推演的情景、参考实现生成的黄金文件。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from zoujin_worldsim import SimState, apply, initial_state, role_of, settle

REPO = Path(__file__).resolve().parents[3]
WORLD_DIR = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft"
GOLDEN = Path(__file__).resolve().parent / "golden"
ROLE = "role.traveler"  # 24 次推演都用旅人（W-1 卡「逐事件 = 一口气」）


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


WORLD: dict[str, Any] = load(WORLD_DIR / "world.json")
SCENARIOS: list[dict[str, Any]] = [
    {"id": "sc.canon", "note": "原著どおり（プレイヤーは何もしない）", "expect": "canon-reunion"}
] + load(WORLD_DIR / "scenarios.json")
SCENARIO_IDS = [sc["id"] for sc in SCENARIOS]


@pytest.fixture(scope="session")
def world() -> dict[str, Any]:
    return WORLD


@pytest.fixture(scope="session")
def golden() -> dict[str, Any]:
    return {name: load(GOLDEN / f"{name}.json")[name] for name in ("runs", "canon_beats", "arrival")}


def scenario(sc_id: str) -> dict[str, Any]:
    return next(sc for sc in SCENARIOS if sc["id"] == sc_id)


type Log = list[dict[str, Any]]


def play(world: dict[str, Any], sc: dict[str, Any], role: str = ROLE) -> tuple[SimState, Log]:
    """按 W-1 卡的做法逐事件推演一个情景：initial_state → 情景的节拍改动在时钟 0 作为一个事件应用 →
    settle 到身份的 startT → 情景的事件按 t 逐个先 settle 到它的 t 再 apply → 最后 settle 到底。
    返回最后的状态和事件日志（情景的事件和 settle 写出的系统事件，按先后）。"""
    s = initial_state(world, role)
    log: Log = []

    def step(event: dict[str, Any]) -> None:
        nonlocal s
        s = apply(world, s, event)
        log.append(event)

    def settle_to(t2: int | None) -> None:
        nonlocal s
        drafts, after = settle(world, s, t2)
        for d in drafts:
            step(d["event"])
        assert s == after, "settle 返回的状态 = 把草稿依次 apply 到结算前的状态"

    if sc.get("beats"):
        step(
            {
                "t": 0,
                "dt": 0,
                "origin": "action",
                "effects": [{"op": "beat", "beat": b, **o} for b, o in sc["beats"].items()],
            }
        )
    settle_to(role_of(world, role)["startT"])
    for ev in sorted(sc.get("events", []), key=lambda e: e["t"]):
        settle_to(ev["t"])
        step({"t": ev["t"], "dt": 0, "origin": "action", "effects": ev["effects"]})
    settle_to(None)
    return s, log


@pytest.fixture(scope="session")
def played(world: dict[str, Any]) -> Callable[[str], tuple[SimState, Log]]:
    cache: dict[str, tuple[SimState, Log]] = {}

    def get(sc_id: str) -> tuple[SimState, Log]:
        if sc_id not in cache:
            cache[sc_id] = play(world, scenario(sc_id))
        return cache[sc_id]

    return get


@pytest.fixture(scope="session")
def play_scenario() -> Callable[..., tuple[SimState, Log]]:
    """自己造的情景用：play(world, sc, role=ROLE)。"""
    return play
