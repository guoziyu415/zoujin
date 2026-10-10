"""世界状态的共享规则库（W-1）。叙事者、评测运行器和数据的工具都只用它，世界状态只有这一套规则在算。

- 一口气推演：Sim（run / resume / arrival_delta / classify），从参考实现 ../../reference/worldsim.py 原样移植；
- 逐事件推演：initial_state / apply / settle / world_state / check_effects，加上 classify / predict / arrival_delta。

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
from .sim import OCCURRED, Sim, role_of

__all__ = [
    "OCCURRED",
    "Draft",
    "Problem",
    "Sim",
    "SimState",
    "apply",
    "arrival_delta",
    "check_effects",
    "classify",
    "flat",
    "initial_state",
    "predict",
    "role_of",
    "settle",
    "world_state",
]
