"""评测运行器（E-0）：读 E1〜E8 的用例，经后端的 zoujin_backend.eval_api 跑完每一步，做确定性检查，出报告。

- api：运行器怎么调后端（形状、两种异常）；
- checks：28 种确定性检查；
- runner：跑用例、跳过和超时的处理、判分的接口；
- report：report.json 和 report.md，和 data-design 7.3 的门槛比；
- live：live 模式的开关、上限和预计花费（真模型的客户端 M2 再接）；
- cli：uv run zoujin-eval。
"""

from .api import EvalApi, EvalSession, StepResult
from .checks import CHECKS, RunContext, WorldIndex
from .results import CaseResult, CheckResult, RunResult
from .runner import Options, run_case, run_cases

__all__ = [
    "CHECKS",
    "CaseResult",
    "CheckResult",
    "EvalApi",
    "EvalSession",
    "Options",
    "RunContext",
    "RunResult",
    "StepResult",
    "WorldIndex",
    "run_case",
    "run_cases",
]
