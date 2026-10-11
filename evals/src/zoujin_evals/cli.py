"""命令行：uv run zoujin-eval --mode fake --deterministic-only（CI 用的就是这个）。

- fake：后端的假文本模型（CI 默认）；replay：后端的回放（ZJ_MODEL=replay）；
  live：真模型，只在 zg 的 Mac 上（见 live.py）。
- 模拟局（persona + seed）的 AI 玩家（player.py）：--player scripted 不调模型（fake、replay 用）；--player claude
  在 live 里调 Claude、在 replay 里只读 AI 玩家的回放（--player-replays）。不给 --player：fake、replay 里模拟局照旧记
  「要真模型」，live 里用 claude。
- 报告写到 --out 下的 report.json 和 report.md。检查不过不改退出码：CI 拿 report.json 和快照比。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from . import live, report
from .api import BACKEND_MODULE, load_backend
from .cases import load_cases
from .checks import WorldIndex
from .player import ClaudePlayer, Player, PlayerReplays, ScriptedPlayer
from .runner import Options, run_cases

WORLD = Path("worlds/hashire-merosu/1.0.0-draft/world.json")
CASES = Path("evals/seeds")
SLICE_WORLD = Path("worlds/hashire-merosu/1.0.0-slice/world.json")
SLICE_CASES = Path("evals/slice")
PRICES = Path("evals/config/live-cost.json")


def parse(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="zoujin-eval", description="评测运行器（E-0）")
    ap.add_argument("--mode", choices=("fake", "replay", "live"), default="fake")
    ap.add_argument("--deterministic-only", action="store_true", help="只跑确定性检查，不跑判分")
    ap.add_argument("--suite", action="append", default=[], help="只跑这个套件（可以给多次）")
    ap.add_argument("--case", action="append", default=[], help="只跑这个用例（可以给多次）")
    ap.add_argument("--slice", action="store_true", help=f"跑切片用例 {SLICE_CASES}，世界模型用切片版（S-077 ⑨）")
    ap.add_argument("--cases", type=Path, help=f"用例目录（默认 {CASES}）")
    ap.add_argument("--world", type=Path, help=f"世界模型 world.json（默认 {WORLD}）")
    ap.add_argument("--out", type=Path, default=Path("evals/out"), help="报告写到哪里")
    ap.add_argument("--timeout", type=float, help="每次运行的时限（秒）；不给 = 文字 600、语音和模拟局 1800；0 = 不限")
    ap.add_argument("--quiet", action="store_true", help="不打印每次运行的进度")
    g = ap.add_argument_group("live（只在 zg 的 Mac 上）")
    g.add_argument("--max-item-usd", type=float, help="单项上限（美元，两本账合起来），live 必填")
    g.add_argument("--max-google-usd", type=float, help="Google 账的总上限（美元，人物的文字回答、Live），live 必填")
    g.add_argument("--max-claude-usd", type=float, help="Claude 账的总上限（美元，叙事者、评审员、AI 玩家），live 必填")
    g.add_argument("--confirm", action="store_true", help="zg 看过预计花费、同意了")
    g.add_argument("--prices", type=Path, default=PRICES, help="每步估价")
    g.add_argument("--item", help="账本里记在哪一项下（如 s5），单项上限按它算，live 必填")
    p = ap.add_argument_group("模拟局的 AI 玩家")
    p.add_argument(
        "--player", choices=("scripted", "claude"), help="不给：live 用 claude，别的模式里模拟局记「要真模型」"
    )
    p.add_argument(
        "--player-model", default=os.environ.get("ZJ_PLAYER_MODEL"), help="AI 玩家的模型 ID（或 ZJ_PLAYER_MODEL）"
    )
    p.add_argument("--player-replays", type=Path, help="AI 玩家的回放目录（默认 --out 下的 player-replays）")
    a = ap.parse_args(argv)
    a.cases = a.cases or (SLICE_CASES if a.slice else CASES)
    a.world = a.world or (SLICE_WORLD if a.slice else WORLD)
    return a


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parse(argv)
    cases = load_cases(a.cases, suites=a.suite, ids=a.case)

    if a.mode == "live":
        prices = live.Prices.from_json(json.loads(a.prices.read_text(encoding="utf-8")))
        caps = {"google": a.max_google_usd, "claude": a.max_claude_usd}
        code, msg = live.gate(
            os.environ,
            max_item_usd=a.max_item_usd,
            caps=caps,
            confirm=a.confirm,
            cases=cases,
            prices=prices,
            deterministic_only=a.deterministic_only,
            argv=argv,
            item=a.item,
            player_model=a.player_model,
        )
        print(msg, file=sys.stderr if code else sys.stdout)
        if code is not None:
            return code
        assert a.item is not None and a.max_item_usd is not None
        os.environ.update(
            live.backend_env(item=a.item, max_item_usd=a.max_item_usd, caps={k: float(v or 0) for k, v in caps.items()})
        )
    else:
        os.environ["ZJ_MODEL"] = a.mode  # B-0 按它选假模型或回放
    os.environ["ZJ_WORLD"] = str(a.world.resolve())  # B-0 按它读世界模型（--slice 时是切片版），绝对路径
    api = load_backend()
    world = WorldIndex(json.loads(a.world.read_text(encoding="utf-8")))
    opts = Options(
        deterministic_only=a.deterministic_only,
        timeout_s=a.timeout,
        progress=(lambda _: None) if a.quiet else (lambda s: print(s, file=sys.stderr)),
        player=players(a),
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
    if opts.player is not None:
        meta["player"] = a.player or "claude"
    rep = report.build(results, meta)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "report.md").write_text(report.markdown(rep), encoding="utf-8")
    print(f"报告：{a.out / 'report.md'}，{a.out / 'report.json'}")
    return 0


def players(a: argparse.Namespace) -> Callable[[Mapping[str, Any]], Player] | None:
    """按用例造 AI 玩家。ScriptedPlayer 每局一个（随机数按 seed）；ClaudePlayer 每局一个，共用回放和账本。"""
    kind = a.player or ("claude" if a.mode == "live" else None)
    if kind is None:
        return None
    if kind == "scripted":
        return lambda case: ScriptedPlayer(seed=int(case["setup"].get("seed", 0)))
    if not a.player_model:
        raise SystemExit("--player claude 要模型 ID：--player-model 或 ZJ_PLAYER_MODEL（仓库里不写）")
    from zoujin_llm import claude_prices

    replays = PlayerReplays(a.player_replays or a.out / "player-replays")
    prices = claude_prices()
    if a.mode != "live":  # 只读回放：查不到这一局记「回放缺失或过期」
        return lambda case: ClaudePlayer(a.player_model, replays, prices)
    from .judge import AnthropicTransport, ClaudeLedger

    ledger = ClaudeLedger(Path(os.environ["ZJ_LEDGER"]), a.max_claude_usd, a.max_item_usd, a.item, use="eval")
    transport = AnthropicTransport()
    return lambda case: ClaudePlayer(a.player_model, replays, prices, ledger, transport)


if __name__ == "__main__":
    sys.exit(main())
