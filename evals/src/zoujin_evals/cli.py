"""命令行：uv run zoujin-eval --mode fake --deterministic-only（CI 用的就是这个）。

- fake：后端的假文本模型（CI 默认）；replay：后端的回放（ZJ_MODEL=replay）；live：只有开关和退出（见 live.py）。
- 报告写到 --out 下的 report.json 和 report.md。检查不过不改退出码：CI 拿 report.json 和快照比。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import live, report
from .api import BACKEND_MODULE, load_backend
from .cases import load_cases
from .checks import WorldIndex
from .runner import Options, run_cases

WORLD = Path("worlds/hashire-merosu/1.0.0-draft/world.json")
CASES = Path("evals/seeds")
PRICES = Path("evals/config/live-cost.json")


def parse(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="zoujin-eval", description="评测运行器（E-0）")
    ap.add_argument("--mode", choices=("fake", "replay", "live"), default="fake")
    ap.add_argument("--deterministic-only", action="store_true", help="只跑确定性检查，不跑判分")
    ap.add_argument("--suite", action="append", default=[], help="只跑这个套件（可以给多次）")
    ap.add_argument("--case", action="append", default=[], help="只跑这个用例（可以给多次）")
    ap.add_argument("--cases", type=Path, default=CASES, help="用例目录")
    ap.add_argument("--world", type=Path, default=WORLD, help="世界模型 world.json")
    ap.add_argument("--out", type=Path, default=Path("evals/out"), help="报告写到哪里")
    ap.add_argument("--timeout", type=float, help="每次运行的时限（秒）；不给 = 文字 600、语音和模拟局 1800；0 = 不限")
    ap.add_argument("--quiet", action="store_true", help="不打印每次运行的进度")
    g = ap.add_argument_group("live（只在 zg 的 Mac 上）")
    g.add_argument("--max-item-usd", type=float, help="单项上限（美元），live 必填")
    g.add_argument("--max-total-usd", type=float, help="总上限（美元），live 必填")
    g.add_argument("--confirm", action="store_true", help="zg 看过预计花费、同意了")
    g.add_argument("--prices", type=Path, default=PRICES, help="每步估价")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parse(argv)
    cases = load_cases(a.cases, suites=a.suite, ids=a.case)

    if a.mode == "live":
        prices = live.Prices.from_json(json.loads(a.prices.read_text(encoding="utf-8")))
        code, msg = live.gate(
            os.environ,
            max_item_usd=a.max_item_usd,
            max_total_usd=a.max_total_usd,
            confirm=a.confirm,
            cases=cases,
            prices=prices,
            deterministic_only=a.deterministic_only,
            argv=argv,
        )
        print(msg, file=sys.stderr if code else sys.stdout)
        return code

    os.environ["ZJ_MODEL"] = a.mode  # B-0 按它选假模型或回放
    api = load_backend()
    world = WorldIndex(json.loads(a.world.read_text(encoding="utf-8")))
    opts = Options(
        deterministic_only=a.deterministic_only,
        timeout_s=a.timeout,
        progress=(lambda _: None) if a.quiet else (lambda s: print(s, file=sys.stderr)),
    )
    results = run_cases(api, cases, world, opts)
    meta = {
        "runner": "zoujin_evals",
        "mode": a.mode,
        "deterministicOnly": a.deterministic_only,
        "worldModelVersion": world.raw["worldModelVersion"],
        "backend": BACKEND_MODULE if api is not None else None,
        "cases": len(cases),
        "filter": {"suite": a.suite, "case": a.case},
    }
    rep = report.build(results, meta)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "report.md").write_text(report.markdown(rep), encoding="utf-8")
    print(f"报告：{a.out / 'report.md'}，{a.out / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
