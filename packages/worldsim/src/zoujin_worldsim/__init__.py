"""世界状态的共享规则库（W-1）。叙事者、评测运行器和数据的工具都只用它，世界状态只有这一套规则在算。

- 一口气推演：Sim（run / resume / arrival_delta / classify），从参考实现 ../../reference/worldsim.py 原样移植；
- 逐事件推演：initial_state / apply / settle / world_state / check_effects，加上 classify / predict / arrival_delta；
- 开局到起点：opening / parse_checkpoint（eval_api 的 setup 里 checkpoint、scenario、place 三种起点）；
- 叙事者规则的原语：knows（R4，谁此刻知道一件事）、travel_minutes（R3，两地之间最少走几分钟）、
  activity（R7 和快照，人物此刻在做什么，absent 的不能对话）、spoilers（R4 和输出侧监控，话里有没有此刻不该知道的事）；
- （1.7）固定演出选哪一条：pick_set_piece（契约 2.11）；
- （1.12）玩家看不看得到一个事件：sees（契约第 3 节，写 learn、推事件、固定演出的在场都用它）。

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
from .primitives import activity, knows, spoilers, travel_minutes
from .sim import OCCURRED, Sim, role_of
from .visibility import same_scene, sees

__all__ = [
    "OCCURRED",
    "Draft",
    "Opened",
    "Problem",
    "Sim",
    "SimState",
    "Until",
    "activity",
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
    "same_scene",
    "sees",
    "settle",
    "spoilers",
    "travel_minutes",
    "world_state",
]
