"""Eval runner (E-0): reads the E1〜E8 cases, runs every step through the backend's zoujin_backend.eval_api, does the
deterministic checks, and writes the report.

- api: how the runner calls the backend (shapes, two exceptions);
- checks: the 28 kinds of deterministic checks;
- runner: running cases, handling skips and timeouts, the judging interface;
- report: report.json and report.md, compared with the bars of data-design 7.3;
- live: the live mode's switch, caps and estimated cost (the real-model client is wired in at M2);
- cli: uv run zoujin-eval.

評価ランナー（E-0）：E1〜E8 のケースを読み、バックエンドの zoujin_backend.eval_api で各ステップを実行し、決定的チェックを
行い、レポートを出す。

- api：ランナーがバックエンドをどう呼ぶか（形、2 種類の例外）。
- checks：28 種類の決定的チェック。
- runner：ケースの実行、スキップとタイムアウトの扱い、採点のインターフェース。
- report：report.json と report.md。data-design 7.3 の基準と比べる。
- live：live モードのスイッチ、上限、見積もり費用（実モデルのクライアントは M2 でつなぐ）。
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
