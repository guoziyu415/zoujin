"""世界状态的共享规则库（W-1）。叙事者、评测运行器和数据的工具都只用它，世界状态只有这一套规则在算。

- 一口气推演：Sim（run / resume / arrival_delta / classify），从参考实现 ../../reference/worldsim.py 原样移植；
- 逐事件推演：initial_state / apply / settle / world_state / check_effects，加上 classify / predict / arrival_delta；
- 开局到起点：opening / parse_checkpoint（eval_api 的 setup 里 checkpoint、scenario、place 三种起点）；
- 叙事者规则的原语：knows（R4，谁此刻知道一件事）、travel_minutes（R3，两地之间最少走几分钟）；
- （1.7）固定演出选哪一条：pick_set_piece（契约 2.11）。

规则要改先改参考实现，再重跑 tests/golden/gen_golden.py。
"""

from .incremental import (
    Draft,
    Problem,
    SimState,
    apply,
    arrival_delta,
    check_effects,
    classify,
    flat,
    initial_state,
    predict,
    settle,
    world_state,
)
from .opening import Opened, Until, opening, parse_checkpoint
from .pieces import pick_set_piece
from .primitives import knows, travel_minutes
from .sim import OCCURRED, Sim, role_of

__all__ = [
    "OCCURRED",
    "Draft",
    "Opened",
    "Problem",
    "Sim",
    "SimState",
    "Until",
    "apply",
    "arrival_delta",
    "check_effects",
    "classify",
    "flat",
    "initial_state",
    "knows",
    "opening",
    "parse_checkpoint",
    "pick_set_piece",
    "predict",
    "role_of",
    "settle",
    "travel_minutes",
    "world_state",
]
