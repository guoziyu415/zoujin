"""Command line: uv run zoujin-eval --mode fake --deterministic-only (this is exactly what CI uses).

- fake: the backend's fake text model (CI default); replay: the backend's replay (ZJ_MODEL=replay);
  live: real models, only on zg's Mac (see live.py).
- The AI player of simulated games (persona + seed) (player.py): --player scripted calls no model (for fake and
  replay); --player claude calls Claude in live and only reads the AI player's replays in replay (--player-replays).
  Without --player: in fake and replay, simulated games still record "needs a real model"; live uses claude.
- The report is written to report.json and report.md under --out. Failing checks do not change the exit code: CI
  compares report.json with the snapshot.

コマンドライン：uv run zoujin-eval --mode fake --deterministic-only（CI が使うのはまさにこれ）。

- fake：バックエンドの偽テキストモデル（CI のデフォルト）。replay：バックエンドのリプレイ（ZJ_MODEL=replay）。
  live：実モデル、zg の Mac でのみ（live.py を参照）。
- シミュレーション局（persona + seed）の AI プレイヤー（player.py）：--player scripted はモデルを呼ばない（fake、
  replay 用）。--player claude は live では Claude を呼び、replay では AI プレイヤーのリプレイ（--player-replays）だけを
  読む。--player なし：fake と replay ではシミュレーション局は従来どおり「実モデルが必要」と記録し、live では claude を
  使う。
- レポートは --out 下の report.json と report.md に書く。チェックが不合格でも終了コードは変えない：CI は report.json を
  スナップショットと比べる。
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
    ap = argparse.ArgumentParser(prog="zoujin-eval", description="Eval runner (E-0) / 評価ランナー（E-0）")
    ap.add_argument("--mode", choices=("fake", "replay", "live"), default="fake")
    ap.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Run deterministic checks only, no judging / 決定的チェックだけを実行し、採点しない",
    )
    ap.add_argument(
        "--suite",
        action="append",
        default=[],
        help="Run only this suite (can be given several times) / このスイートだけを実行（複数回指定可）",
    )
    ap.add_argument(
        "--case",
        action="append",
        default=[],
        help="Run only this case (can be given several times) / このケースだけを実行（複数回指定可）",
    )
    ap.add_argument(
        "--slice",
        action="store_true",
        help=f"Run the slice cases {SLICE_CASES} on the slice world model (S-077 ⑨)"
        f" / スライスのケース {SLICE_CASES} を実行し、世界モデルはスライス版を使う（S-077 ⑨）",
    )
    ap.add_argument(
        "--cases", type=Path, help=f"Case directory (default {CASES}) / ケースのディレクトリ（デフォルト {CASES}）"
    )
    ap.add_argument(
        "--world",
        type=Path,
        help=f"World model world.json (default {WORLD}) / 世界モデル world.json（デフォルト {WORLD}）",
    )
    ap.add_argument(
        "--out", type=Path, default=Path("evals/out"), help="Where to write the report / レポートの書き出し先"
    )
    ap.add_argument(
        "--timeout",
        type=float,
        help="Time limit per run (seconds); omitted = 600 for text, 1800 for voice and simulated games; 0 = no limit"
        " / 各回の時間制限（秒）。省略時はテキスト 600、音声とシミュレーション局 1800。0 = 無制限",
    )
    ap.add_argument(
        "--quiet", action="store_true", help="Do not print the progress of each run / 各回の進捗を表示しない"
    )
    g = ap.add_argument_group("live (only on zg's Mac) / live（zg の Mac でのみ）")
    g.add_argument(
        "--max-item-usd",
        type=float,
        help="Per-item cap (US dollars, both ledgers combined); required for live"
        " / 項目ごとの上限（米ドル、2 つの台帳の合算）。live では必須",
    )
    g.add_argument(
        "--max-google-usd",
        type=float,
        help="Total cap of the Google ledger (US dollars; characters' text replies, Live); required for live"
        " / Google 台帳の総上限（米ドル。人物のテキスト返答、Live）。live では必須",
    )
    g.add_argument(
        "--max-claude-usd",
        type=float,
        help="Total cap of the Claude ledger (US dollars; narrator, judge, AI player); required for live"
        " / Claude 台帳の総上限（米ドル。ナレーター、審査員、AI プレイヤー）。live では必須",
    )
    g.add_argument(
        "--confirm",
        action="store_true",
        help="zg has seen the estimated cost and agreed / zg が見積もり費用を確認し、同意した",
    )
    g.add_argument("--prices", type=Path, default=PRICES, help="Estimated price per step / ステップごとの見積もり単価")
    g.add_argument(
        "--item",
        help="The ledger item to record under (e.g. s5); the per-item cap is computed by it; required for live"
        " / 台帳のどの項目に記録するか（例 s5）。項目ごとの上限はそれで計算する。live では必須",
    )
    p = ap.add_argument_group("AI player of simulated games / シミュレーション局の AI プレイヤー")
    p.add_argument(
        "--player",
        choices=("scripted", "claude"),
        help='Omitted: live uses claude; in other modes simulated games record "needs a real model"'
        " / 省略時：live は claude を使い、他のモードではシミュレーション局を「実モデルが必要」と記録する",
    )
    p.add_argument(
        "--player-model",
        default=os.environ.get("ZJ_PLAYER_MODEL"),
        help="The AI player's model ID (or ZJ_PLAYER_MODEL) / AI プレイヤーのモデル ID（または ZJ_PLAYER_MODEL）",
    )
    p.add_argument(
        "--player-replays",
        type=Path,
        help="Directory of the AI player's replays (default player-replays under --out)"
        " / AI プレイヤーのリプレイのディレクトリ（デフォルトは --out 下の player-replays）",
    )
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
            if code == 0:
                print(
                    "Estimate only; no model has been called and no run results have been produced."
                    " / 見積もりのみ。モデルはまだ呼んでおらず、実行結果もまだ生成していない。"
                )
            return code
        assert a.item is not None and a.max_item_usd is not None
        os.environ.update(
            live.backend_env(item=a.item, max_item_usd=a.max_item_usd, caps={k: float(v or 0) for k, v in caps.items()})
        )
    else:
        # B-0 picks the fake model or replay by it / B-0 はこれで偽モデルかリプレイを選ぶ
        os.environ["ZJ_MODEL"] = a.mode
    # B-0 reads the world model by it (the slice version with --slice); an absolute path
    # B-0 はこれで世界モデルを読む（--slice のときはスライス版）。絶対パス
    os.environ["ZJ_WORLD"] = str(a.world.resolve())
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
    meta["expectedJudgeRuns"] = {c["id"]: c.get("runs", 5) if "judge" in c.get("expect", {}) else 0 for c in cases}
    if opts.player is not None:
        meta["player"] = a.player or "claude"
    rep = report.build(results, meta)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "report.md").write_text(report.markdown(rep), encoding="utf-8")
    print(f"Report / レポート: {a.out / 'report.md'}, {a.out / 'report.json'}")
    if a.mode == "live":
        return int(any(c.get("skip") or any(r["status"] != "pass" for r in c.get("results", [])) for c in results))
    return 0


def players(a: argparse.Namespace) -> Callable[[Mapping[str, Any]], Player] | None:
    """Make the AI player per case. One ScriptedPlayer per game (random numbers by seed); one ClaudePlayer per game,
    sharing the replays and the ledger.

    ケースごとに AI プレイヤーを作る。ScriptedPlayer は 1 局に 1 つ（乱数は seed による）。ClaudePlayer も 1 局に 1 つ
    で、リプレイと台帳を共有する。
    """
    kind = a.player or ("claude" if a.mode == "live" else None)
    if kind is None:
        return None
    if kind == "scripted":
        return lambda case: ScriptedPlayer(seed=int(case["setup"].get("seed", 0)))
    if not a.player_model:
        raise SystemExit(
            "--player claude needs a model ID: --player-model or ZJ_PLAYER_MODEL (not written in the repo)"
            " / --player claude にはモデル ID が必要：--player-model または ZJ_PLAYER_MODEL（リポジトリには書かない）"
        )
    from zoujin_llm import claude_prices

    replays = PlayerReplays(a.player_replays or a.out / "player-replays")
    prices = claude_prices()
    # read replays only: if this game is not found it records "replay missing or stale"
    # リプレイだけを読む：この局が見つからなければ「リプレイが無いか期限切れ」と記録する
    if a.mode != "live":
        return lambda case: ClaudePlayer(a.player_model, replays, prices)
    from .judge import AnthropicTransport, ClaudeLedger

    ledger = ClaudeLedger(Path(os.environ["ZJ_LEDGER"]), a.max_claude_usd, a.max_item_usd, a.item, use="eval")
    transport = AnthropicTransport()
    return lambda case: ClaudePlayer(a.player_model, replays, prices, ledger, transport)


if __name__ == "__main__":
    sys.exit(main())
