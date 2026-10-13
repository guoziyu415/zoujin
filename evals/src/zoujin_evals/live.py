"""live mode (E-0 card item 3; real runs since B-5): only on zg's Mac.

1. Without the Mac switch (environment variable ZJ_EVAL_LIVE=1, set only on zg's Mac) it exits and prints why.
2. Caps must be passed explicitly; there are no defaults: --max-item-usd (per item) and one total cap for each of the
   two ledgers, --max-google-usd and --max-claude-usd. Missing any one of them exits. The two ledgers (since D-028):
   Live, pre-recorded lines and the characters' replies in text mode go to google; the narrator, the judge and the AI
   player go to claude. It also needs --item (the ledger item to record under, e.g. s5) and the ledger file
   ZJ_LEDGER; when the cases include simulated games it needs the AI player's model ID (--player-model or
   ZJ_PLAYER_MODEL, not written in the repo).
3. Judging is not wired into live yet (the judge currently goes through zoujin-calibrate), so live needs
   --deterministic-only.
4. Without --confirm: print the estimated cost and the full command, then exit (D-030: within the per-item cap it just
   runs, no need to ask again).
5. With --confirm: check item 3 and the other things in item 2, and run for real once they are all there. The backend
   uses ZJ_MODEL=real; the runner puts the caps and the ledger into the environment (read by config.Settings); the AI
   player uses Claude.
   The ledger reaching a cap, or the first 429 / 529, stops the whole run (zoujin_llm.Stop).

live モード（E-0 カード第 3 条。B-5 から実際に実行）：zg の Mac でのみ。

1. Mac のスイッチ（環境変数 ZJ_EVAL_LIVE=1、zg の Mac でのみ設定）がなければ、理由を表示して終了する。
2. 上限は明示的に渡す必要があり、デフォルト値はない：--max-item-usd（項目ごと）と、2 つの台帳それぞれの総上限
   --max-google-usd、--max-claude-usd。1 つでも欠ければ終了する。2 つの台帳（D-028 以降）：Live、事前収録セリフ、
   テキストモードの人物の返答は google に、ナレーター、審査員、AI プレイヤーは claude に記録する。さらに --item
   （台帳のどの項目に記録するか、例 s5）と台帳ファイル ZJ_LEDGER が必要。ケースにシミュレーション局があるときは
   AI プレイヤーのモデル ID（--player-model または ZJ_PLAYER_MODEL。リポジトリには書かない）も必要。
3. live ではまだ採点をつないでいない（審査員は現在 zoujin-calibrate を使う）ので、live には --deterministic-only が
   必要。
4. --confirm なし：見積もり費用と完全なコマンドを表示して終了する（D-030：項目ごとの上限以内なら、改めて確認せずに
   実行する）。
5. --confirm あり：第 3 条と第 2 条の残りを確認し、すべて揃えば実際に実行する。バックエンドは ZJ_MODEL=real を使い、
   上限と台帳はランナーが環境に設定する（config.Settings が読む）。AI プレイヤーは Claude を使う。
   台帳が上限に達するか、最初の 429 / 529 で実行全体を止める（zoujin_llm.Stop）。
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .checks import step_kind

LIVE_SWITCH = "ZJ_EVAL_LIVE"
# steps that call a model; deletion and advance touch only the database and the rules
# モデルを呼ぶステップ。削除と advance はデータベースと規則にしか触れない
MODEL_STEPS = {"to", "act", "propose", "silence", "choose"}
PROVIDERS = ("google", "claude")  # the two ledgers / 2 つの台帳
CAP_FLAGS = {"google": "--max-google-usd", "claude": "--max-claude-usd"}
NAMES = {"google": "Google", "claude": "Claude"}

type Cost = dict[str, float]  # provider → US dollars / プロバイダー → 米ドル


def _cost(d: Mapping[str, Any]) -> Cost:
    unknown = sorted(set(d) - set(PROVIDERS))
    if unknown:
        raise ValueError(f"Unknown providers in live-cost.json / live-cost.json に不明なプロバイダー: {unknown}")
    return {p: float(d.get(p, 0)) for p in PROVIDERS}


@dataclass(frozen=True)
class Prices:
    # one step: the character's reply (google) + the narrator's steps (claude)
    # 1 ステップ：人物の返答（google）+ ナレーターの各ステップ（claude）
    turn: Cost
    judge: Cost  # one judging (the judge) / 採点 1 回（審査員）
    # one simulated game: the characters' replies (google) + narrator, ending, AI player (claude)
    # シミュレーション局 1 局：人物の返答（google）+ ナレーター、結末、AI プレイヤー（claude）
    simulated_playthrough: Cost

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> Prices:
        return cls(_cost(d["turn"]), _cost(d["judge"]), _cost(d["simulatedPlaythrough"]))


def case_cost(case: Mapping[str, Any], prices: Prices, *, deterministic_only: bool) -> Cost:
    """Estimated cost of one case, by provider = runs × (steps that call a model × one step + one judging); a
    simulated game counts as one game.

    1 ケースの見積もり費用（プロバイダー別）= runs ×（モデルを呼ぶステップ数 × 1 ステップ + 採点 1 回）。
    シミュレーション局は 1 局として数える。
    """
    runs = case.get("runs", 5)
    if "persona" in case["setup"]:
        per_run = dict(prices.simulated_playthrough)
    else:
        n = sum(step_kind(s) in MODEL_STEPS for s in case.get("steps", []))
        per_run = {p: n * prices.turn[p] for p in PROVIDERS}
    if "judge" in case.get("expect", {}) and not deterministic_only:
        per_run = {p: per_run[p] + prices.judge[p] for p in PROVIDERS}
    return {p: float(runs * per_run[p]) for p in PROVIDERS}


def gate(
    env: Mapping[str, str],
    *,
    max_item_usd: float | None,
    caps: Mapping[str, float | None],
    confirm: bool,
    cases: Sequence[Mapping[str, Any]],
    prices: Prices,
    deterministic_only: bool,
    argv: Sequence[str],
    item: str | None = None,
    player_model: str | None = None,
) -> tuple[int | None, str]:
    """Return (exit code, what to print): 0 = printed the estimated cost, exit; 2 = cannot run; None = --confirm given
    and everything in place, go on to run for real. caps: provider → total cap.

    （終了コード、表示する内容）を返す：0 = 見積もり費用を表示して終了。2 = 実行できない。None = --confirm があり条件が
    すべて揃っているので、続けて実際に実行する。caps：プロバイダー → 総上限。
    """
    if env.get(LIVE_SWITCH) != "1":
        return 2, (
            f"live calls real models and runs only on zg's Mac: {LIVE_SWITCH}=1 is not set, exiting."
            f" / live は実モデルを呼ぶので zg の Mac でのみ実行する：{LIVE_SWITCH}=1 が設定されていないため終了する。"
        )
    given = {"--max-item-usd": max_item_usd, **{CAP_FLAGS[p]: caps.get(p) for p in PROVIDERS}}
    missing = [n for n, v in given.items() if v is None]
    if missing:
        flags = " ".join(missing)
        return 2, (
            "live needs an explicit per-item cap and total caps for both ledgers; there are no defaults (zg has not set"
            f" the development model-spend caps yet). Missing {flags}, exiting."
            " / live では項目ごとの上限と 2 つの台帳の総上限を明示する必要がある。デフォルト値はない"
            f"（開発期のモデル費用の上限を zg がまだ決めていない）。{flags} が足りないため終了する。"
        )
    assert max_item_usd is not None
    total_caps = {p: float(caps[p] or 0) for p in PROVIDERS}
    if not confirm:
        return 0, estimate_text(cases, prices, deterministic_only, max_item_usd, total_caps, argv)
    if not deterministic_only:
        return 2, (
            "Judging is not wired into live yet (the judge goes through zoujin-calibrate): pass --deterministic-only,"
            " exiting. / live ではまだ採点をつないでいない（審査員は zoujin-calibrate を使う）：--deterministic-only を"
            "付けること。終了する。"
        )
    if not item:
        return 2, (
            "live needs --item (the ledger item to record under, e.g. s5); the per-item cap is computed by it, exiting."
            " / live には --item（台帳のどの項目に記録するか、例 s5）が必要。項目ごとの上限はそれで計算する。終了する。"
        )
    if not env.get("ZJ_LEDGER"):
        return 2, (
            "live needs a ledger: set ZJ_LEDGER (the same JSONL file as the backend), exiting."
            " / live には台帳が必要：ZJ_LEDGER を設定する（バックエンドと同じ JSONL ファイル）。終了する。"
        )
    if any("persona" in c["setup"] for c in cases) and not player_model:
        return 2, (
            "There are simulated games: the AI player's model ID is needed (--player-model or ZJ_PLAYER_MODEL; not"
            " written in the repo), exiting. / シミュレーション局がある：AI プレイヤーのモデル ID が必要"
            "（--player-model または ZJ_PLAYER_MODEL。リポジトリには書かない）。終了する。"
        )
    return (
        None,
        f'live: {len(cases)} cases, recorded under "{item}". / live：{len(cases)} 例、「{item}」の下に記録する。',
    )


def backend_env(*, item: str, max_item_usd: float, caps: Mapping[str, float]) -> dict[str, str]:
    """The environment set for the backend in a real run (read by config.Settings.from_env): real model, caps, the
    item to record under. The ledger ZJ_LEDGER is already in the environment.

    実際の実行でバックエンドに設定する環境（config.Settings.from_env が読む）：実モデル、上限、記録する項目。台帳
    ZJ_LEDGER はすでに環境にある。
    """
    return {
        "ZJ_MODEL": "real",
        "ZJ_LEDGER_ITEM": item,
        "ZJ_MAX_ITEM_USD": str(max_item_usd),
        "ZJ_MAX_GOOGLE_USD": str(caps["google"]),
        "ZJ_MAX_CLAUDE_USD": str(caps["claude"]),
    }


def estimate_text(
    cases: Sequence[Mapping[str, Any]],
    prices: Prices,
    deterministic_only: bool,
    max_item_usd: float,
    caps: Mapping[str, float],
    argv: Sequence[str],
) -> str:
    costs = [(c, case_cost(c, prices, deterministic_only=deterministic_only)) for c in cases]
    total = {p: sum(x[p] for _, x in costs) for p in PROVIDERS}
    lines = [
        "Estimated cost (extrapolated; unit prices in evals/config/live-cost.json)"
        " / 見積もり費用（推算。単価は evals/config/live-cost.json）:",
        "",
        "| Suite / スイート | Cases / ケース | Runs / 回数 | " + " | ".join(NAMES[p] for p in PROVIDERS) + " |",
        "|---|---:|---:|" + "---:|" * len(PROVIDERS),
    ]
    for suite in sorted({c["suite"] for c, _ in costs}):
        xs = [(c, x) for c, x in costs if c["suite"] == suite]
        runs = sum(c.get("runs", 5) for c, _ in xs)
        money = " | ".join(f"${sum(x[p] for _, x in xs):.2f}" for p in PROVIDERS)
        lines.append(f"| {suite} | {len(xs)} | {runs} | {money} |")
    sums_en = ", ".join(f"{NAMES[p]} about ${total[p]:.2f} (cap ${caps[p]:.2f})" for p in PROVIDERS)
    sums_ja = "、".join(f"{NAMES[p]} 約 ${total[p]:.2f}（上限 ${caps[p]:.2f}）" for p in PROVIDERS)
    lines += [
        "",
        f"Total: {sums_en}; per-item cap ${max_item_usd:.2f} (both ledgers combined)."
        f" / 合計：{sums_ja}。項目ごとの上限 ${max_item_usd:.2f}（2 つの台帳の合算）。",
    ]
    over = [c["id"] for c, x in costs if sum(x.values()) > max_item_usd]
    if over:
        lines.append(
            f"Cases over the per-item cap that will stop midway: {', '.join(over)}."
            f" / 項目ごとの上限を超え、途中で止まるケース：{'、'.join(over)}。"
        )
    for p in PROVIDERS:
        if total[p] > caps[p]:
            lines.append(
                f"{NAMES[p]} total is over its cap: this ledger stops at the cap and later cases do not run."
                f" / {NAMES[p]} の合計が上限を超える：この台帳は上限で止まり、後のケースは実行しない。"
            )
    cmd = ["uv", "run", "zoujin-eval", *argv]
    if "--confirm" not in cmd:
        cmd.append("--confirm")
    lines += [
        "",
        "Once zg agrees, run on the Mac: / zg の同意後、Mac で実行する：",
        "",
        f"    {LIVE_SWITCH}=1 {shlex.join(cmd)}",
    ]
    return "\n".join(lines)
