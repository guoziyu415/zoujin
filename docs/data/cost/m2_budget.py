#!/usr/bin/env python3
"""Estimate of M2's two development ledgers: the tables in m2-model-budget.md come from here. Everything is an
estimate, to be replaced with actual ledger numbers once M2's first batch has run. Standard library only.

The cost of one call and of one playthrough comes from cost_model.py (the post-D-028 basis, B-8's tokens per step).
One full slice eval pass is counted case by case from evals/slice/*.jsonl: which model steps each kind of step calls
(EVAL_MIX), times runs; scoring is cases with a judge × runs.

Usage: python3 -I m2_budget.py  → the two ledgers' tables (Markdown) and the unit prices to write into
evals/config/live-cost.json

M2 開発期の 2 つの台帳の見積もり：m2-model-budget.md の表はここから出す。すべて推算で、M2 の最初のバッチを
実行したら台帳の実数に置き換える。標準ライブラリのみ。

1 回の呼び出しと 1 プレイの費用は cost_model.py を使う（D-028 以降の算定基準、B-8 のステップごとのトークン数）。
スライス評価 1 回分は evals/slice/*.jsonl をケースごとに数える：ステップの種類ごとにどのモデルステップを呼ぶか
（EVAL_MIX）に runs を掛ける。採点は judge 付きのケース × runs。

使い方：python3 -I m2_budget.py  → 2 つの台帳の表（Markdown）と、evals/config/live-cost.json に書く単価"""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("data_cost_model", HERE / "cost_model.py")
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

SLICE = cm.REPO / "evals" / "slice"
SEEDS = cm.REPO / "evals" / "seeds"

# Which model steps each step of an eval calls (average calls per step). Higher than in a whole playthrough: eval
# utterances mostly target the narrator and rarely stop at triage.
# 評価の各ステップがどのモデルステップを呼ぶか（ステップあたりの平均回数）。通しのプレイより比率が高い：評価の発話は
# ほとんどナレーターを狙っており、振り分けで止まることは少ない。
# Called throughout a full pass, so the cache stays warm / 1 回分の間ずっと呼ぶので、キャッシュは温まったまま
FREQUENT = ("extract", "check", "rewrite")
EVAL_MIX = {
    "say": {"triage": 1, "safety": 1, "extract": 0.8, "check": 0.8 * 1.3, "rewrite": 0.2, "memory": 0.5,
            "suggest": 0.6, "reply": 1},
    "silence": {"reply": 1, "suggest": 0.6},
    "act": {"extract": 1, "check": 1.3, "rewrite": 0.2, "narrate": 1},
    "choose": {"world_tick": 1, "narrate": 1},
    "propose": {"safety": 1, "plan": 1, "world_tick": 1},
    "advance": {"world_tick": 1},
    "deleteMemory": {"delete_memory": 1},
    "newPlaythrough": {},
    "deletePlaythrough": {},
}
# One text-mode character reply (Gemini 3.8 Flash, kept at Google by B-8): converted from two S-068 measurements,
# with scoring taken out
# テキストモードの人物応答 1 回（Gemini 3.8 Flash、B-8 で Google に残す）：S-068 の 2 回の実測から換算し、採点分を除く
REPLY_USD = 0.015
# One scoring call, Opus 5.5, effort low; thinking can't be turned off and counts in out. Calibration measurements
# (10-11, 150 calls): in 951–1,234, average 1,035; out average 102, max 220. Slice transcripts are longer than the
# calibration samples, so assume 1,500 in and 150 out
# 採点 1 回、Opus 5.5、effort low。思考はオフにできず out に含まれる。キャリブレーションの実測（10-11、150 回）：
# 入力 951〜1,234、平均 1,035。出力平均 102、最大 220。スライスの対話記録はキャリブレーションのサンプルより長いので、
# 入力 1,500、出力 150 で計算
JUDGE = dict(fresh=1500, out=150)
# Calibration, 50 items × 3, already spent (Mac ledger) / キャリブレーション 50 件 × 3 回は支出済み（Mac の台帳）
CALIBRATED_USD = 0.93
# One AI player turn, Sonnet 5.5: persona and world description cached, not via Batch
# AI プレイヤーの 1 ターン、Sonnet 5.5：ペルソナと世界の説明はキャッシュ経由、Batch は使わない
PLAYER = dict(cached=8000, fresh=1000, out=200)

# First pass, one Haiku comparison pass, 5 prompt-tuning rounds of half a pass each, two gate passes
# 最初の 1 回、Haiku の比較 1 回、プロンプト調整 5 回（各半回分）、合格判定 2 回
PASSES = dict(first=1, haiku_compare=1, tuning=5 * 0.5, gate=2)
# Slice-length simulated playthrough: about 15 turns of act one + ending settlement
# スライスの長さの模擬プレイ：第一幕約 15 ターン + エンディングの確定
SLICE_SIM = dict(minutes=8, turns=15, acts=1, ticks_fixed=3, deletes=0)
SONNET_PLAN = "Sonnet (per B-8) / Sonnet（B-8 どおり）"
COMPARE_PLAN = "Extraction and check on Haiku / 抽出・チェックを Haiku に"
PLANS = {
    SONNET_PLAN: {},
    "Extraction on Haiku / 抽出を Haiku に": {"extract": "haiku"},
    COMPARE_PLAN: {"extract": "haiku", "check": "haiku"},
}
# B-8: S-2 and the first eval pass each run once more on Haiku
# B-8：S-2 と最初の評価をそれぞれ Haiku でもう 1 回ずつ実行する
COMPARE = PLANS[COMPARE_PLAN]
# Reruns, retries triggered by time limits, resuming after the Mac disconnects
# 再実行、時間制限による再試行、Mac の切断後の再開
SPARE = 0.3

DATA, BACKEND = "Data / データ", "Backend / バックエンド"


def step_kind(step):
    keys = set(step) - {"to"}
    if len(keys) != 1 or (kind := next(iter(keys))) not in EVAL_MIX:
        raise SystemExit(f"m2_budget.py does not know this kind of step: {sorted(step)}; add it to EVAL_MIX first"
                         f" / m2_budget.py はこの種類のステップを知らない：{sorted(step)}。"
                         "先に EVAL_MIX に追加すること")
    return kind


def slice_pass(plan, prices, folder=SLICE):
    """One full eval pass (the slice by default): Claude (narrator), Google (character replies), scoring calls, case
    count. Simulated-playthrough cases (E7 personas) are counted separately.

    評価 1 回分（既定はスライス）：Claude（ナレーター）、Google（人物の応答）、採点回数、ケース数。模擬プレイの
    ケース（E7 のペルソナ）は別に計算する。"""
    cases = [json.loads(x) for f in sorted(folder.glob("*.jsonl"))
             for x in f.read_text("utf-8").splitlines() if x.strip()]
    cases = [c for c in cases if "persona" not in c["setup"]]
    claude = google = 0.0
    judged = 0
    frequent = set()
    for case in cases:
        runs = case.get("runs", 5)
        rare = set()
        for step in case["steps"]:
            for name, n in EVAL_MIX[step_kind(step)].items():
                if name == "reply":
                    google += runs * n * REPLY_USD
                    continue
                tier = plan.get(name, cm.STEPS[name]["tier"])
                claude += runs * n * cm.claude_call(name, tier, prices)
                if cm.STEPS[name]["cached"]:
                    (frequent if name in FREQUENT else rare).add(name)
        # The runs of one case go back to back: infrequent prompts write the cache once per case, frequent ones once
        # per full pass
        # 同じケースの複数回は続けて実行する：あまり呼ばないプロンプトはケースごとに 1 回、よく呼ぶものは 1 回分につき
        # 1 回キャッシュを書く
        claude += sum(cm.cache_write(n, plan.get(n, cm.STEPS[n]["tier"]), prices) for n in rare)
        judged += runs if "judge" in case["expect"] else 0
    claude += sum(cm.cache_write(n, plan.get(n, cm.STEPS[n]["tier"]), prices) for n in frequent)
    return claude, google, judged, len(cases)


def judge_call(prices, batch):
    tiers, _, discount = prices
    pr = tiers["opus"]
    usd = JUDGE["fresh"] * pr["in"] + JUDGE["out"] * pr["out"]
    return usd * discount if batch else usd


def player_turn(prices):
    pr = prices[0]["sonnet"]
    return PLAYER["cached"] * pr["cached"] + PLAYER["fresh"] * pr["in"] + PLAYER["out"] * pr["out"]


def sim(p, plan, prices):
    """One simulated playthrough (text mode, no Live): Claude = narrator + AI player; Google = character replies.
    Playthroughs run back to back: frequently called prompts keep a warm cache, and the end-of-act plan and ending
    prompts write it once per playthrough.

    模擬プレイ 1 回（テキストモード、Live は使わない）：Claude = ナレーター + AI プレイヤー、Google = 人物の応答。
    1 プレイずつ続けて実行する：よく呼ぶプロンプトのキャッシュは温まったまま、幕末のプランとエンディングの
    プロンプトはプレイごとに 1 回書く。"""
    r = cm.claude_session({**cm.CLAUDE_BASE, **p}, plan, prices, warm=(*FREQUENT, "narrate", "world_tick"))
    return r[cm.CLAUDE_SUBTOTAL] + p.get("turns", 40) * player_turn(prices), p.get("turns", 40) * REPLY_USD


def checks(n, plan_tier, prices):
    """n model checks (S-2 and check-prompt tuning: one call per candidate), cache written once.

    モデルチェック n 回（S-2 とチェックプロンプトの調整：候補 1 件につき 1 回）、キャッシュは 1 回書く。"""
    return n * cm.claude_call("check", plan_tier, prices) + cm.cache_write("check", plan_tier, prices)


def budget(plan, prices):
    """Line items of M2's two ledgers: [(ledger, who, item, volume, USD)]. plan is the tier used once the tier is
    chosen: the prompt-tuning and gate eval passes, and the two kinds of simulated playthrough. Before the choice,
    follow B-8: tune the check prompt with Sonnet; run S-2 and the first eval pass once each on Sonnet and Haiku.

    M2 の 2 つの台帳の明細：[(台帳, 担当, 項目, 量, ドル)]。plan はティア決定後に使うティア：プロンプト調整と
    合格判定の評価、2 種類の模擬プレイ。決定前は B-8 どおり：チェックプロンプトの調整は Sonnet、S-2 と最初の評価は
    Sonnet と Haiku で 1 回ずつ。"""
    first = slice_pass({}, prices)
    compare = slice_pass(COMPARE, prices)
    chosen = slice_pass(plan, prices)
    judged, n_cases = first[2], first[3]
    n_passes = sum(PASSES.values())
    later = PASSES["tuning"] + PASSES["gate"]
    persona, persona_g = sim(SLICE_SIM, plan, prices)
    s5, s5_g = sim({}, plan, prices)
    rows = [
        ("claude", DATA, "Judge calibration / 審査員のキャリブレーション",
         "50 items × 3 already spent; after the J23 and J24 rubric change, retest 2 items × 3"
         " / 50 件 × 3 回は支出済み。J23・J24 の細則変更後に 2 件 × 3 回を再テスト",
         CALIBRATED_USD + 6 * judge_call(prices, False)),
        ("claude", DATA,
         "S-2 holdout set (Sonnet, then one Haiku pass) / S-2 ホールドアウトセット（Sonnet、続けて Haiku で 1 回）",
         "50 items × 3, one pass per tier / 50 件 × 3 回、両ティアで 1 回ずつ",
         checks(150, "sonnet", prices) + checks(150, "haiku", prices)),
        ("claude", DATA, "Slice eval: narrator / スライス評価：ナレーター",
         f"{n_cases} cases; one full Sonnet pass, one Haiku comparison pass, {later:g} passes for prompt tuning and"
         f" gating / {n_cases} ケース。Sonnet で 1 回分、比較用に Haiku で 1 回分、"
         f"プロンプト調整と合格判定で {later:g} 回分",
         first[0] + compare[0] + later * chosen[0]),
        ("claude", DATA, "Slice eval: scoring / スライス評価：採点",
         f"{judged} per pass × {n_passes:g} passes, via Batch / 1 回分 {judged} 回 × {n_passes:g} 回分、Batch 経由",
         judged * n_passes * judge_call(prices, True)),
        ("claude", DATA, "Persona simulated playthroughs / ペルソナ模擬プレイ",
         "11 personas × 2 playthroughs, about 15 turns each, including the AI player"
         " / 11 ペルソナ × 2 プレイ、1 プレイ約 15 ターン、AI プレイヤー込み", 22 * persona),
        ("claude", DATA, "E1 jailbreak sample expansion / E1 脱獄サンプルの拡充", "Very small / ごく少量", 1.0),
        ("claude", BACKEND, "B-8 mini test / B-8 小テスト",
         "7 prompts × 20 calls (B-8) / 7 種のプロンプト × 20 回（B-8）", 1.0),
        ("claude", BACKEND,
         "Check prompt tuning (before the tier is chosen, on Sonnet)"
         " / チェックプロンプトの調整（ティア決定前、Sonnet で）",
         "10 public items × 3 × 5 rounds / 公開の 10 件 × 3 回 × 5 ラウンド", checks(150, "sonnet", prices)),
        ("claude", BACKEND, "S-5 simulated playthroughs / S-5 模擬プレイ",
         "10 playthroughs × 40 turns, including the AI player / 10 プレイ × 40 ターン、AI プレイヤー込み", 10 * s5),
        ("google", BACKEND, "B-6 pre-recorded lines / B-6 事前収録セリフ", "D-027", 0.2),
        ("google", DATA, "Slice eval: character replies / スライス評価：人物の応答",
         f"{first[1] / REPLY_USD:.0f} per pass × {n_passes:g} passes"
         f" / 1 回分 {first[1] / REPLY_USD:.0f} 回 × {n_passes:g} 回分",
         first[1] * n_passes),
        ("google", DATA, "Persona simulated playthroughs: character replies / ペルソナ模擬プレイ：人物の応答",
         "22 playthroughs × 15 turns / 22 プレイ × 15 ターン", 22 * persona_g),
        ("google", BACKEND, "S-5 simulated playthroughs: character replies / S-5 模擬プレイ：人物の応答",
         "10 playthroughs × 40 turns / 10 プレイ × 40 ターン", 10 * s5_g),
        ("google", BACKEND,
         "Live self-test (a few internal playthroughs once the gateway is connected)"
         " / Live の自己テスト（ゲートウェイ接続後、内部で数プレイ）",
         "10 playthroughs × 20 minutes / 10 プレイ × 20 分", 10 * cm.live_cost(cm.BASE)),
        # Model Armor (S-085 ②) is free for the first 2 million tokens a month, then $0.10 per million (pricing page
        # 2026-10-11). Development uses a few hundred thousand tokens a month
        # Model Armor（S-085 ②）は毎月最初の 200 万トークンが無料、その後は 100 万あたり $0.10（料金ページ
        # 2026-10-11）。開発期は月に数十万トークン程度
        ("google", BACKEND, "Model Armor (once connected, second layer) / Model Armor（接続後、第 2 層）",
         "Free up to 2 million tokens a month / 月 200 万トークンまで無料", 0.0),
    ]
    return rows


def m3_rows(plan, prices):
    """M3: seeds run twice (first pass and gate; E7's personas are replaced by the 200 playthroughs), plus 200
    playthroughs for diversity (full length, 40 turns).

    M3：シードを 2 回実行（最初の 1 回と合格判定。E7 のペルソナは 200 プレイで代替）、多様性確認の 200 プレイ
    （フルの長さ、40 ターン）。"""
    seeds = slice_pass(plan, prices, SEEDS)
    s5, s5_g = sim({}, plan, prices)
    return [
        ("Seeds: narrator and scoring / シード：ナレーターと採点",
         f"{seeds[3]} cases (E7 personas counted separately) × 2 passes, {seeds[2]} scoring calls per pass"
         f" / {seeds[3]} ケース（E7 のペルソナは別計算）× 2 回分、採点は 1 回分 {seeds[2]} 回", "Claude",
         2 * (seeds[0] + seeds[2] * judge_call(prices, True))),
        ("Seeds: character replies / シード：人物の応答", "Same as above / 同上", "Google", 2 * seeds[1]),
        ("200-playthrough diversity: narrator and AI player / 200 プレイの多様性：ナレーターと AI プレイヤー",
         "200 playthroughs × 40 turns / 200 プレイ × 40 ターン", "Claude", 200 * s5),
        ("200-playthrough diversity: character replies / 200 プレイの多様性：人物の応答",
         "200 playthroughs × 40 turns / 200 プレイ × 40 ターン", "Google", 200 * s5_g),
    ]


def main():
    prices = cm.claude_prices()
    budgets = {name: budget(plan, prices) for name, plan in PLANS.items()}
    base = budgets[next(iter(PLANS))]
    for book, title in (("claude", "Claude ledger / Claude 台帳"), ("google", "Google ledger / Google 台帳")):
        # The Google ledger does not change with the narrator's tier, so it gets one column
        # Google の台帳はナレーターのティアで変わらないので、1 列だけ出す
        cols = list(PLANS) if book == "claude" else [next(iter(PLANS))]
        print(f"### {title}")
        print()
        print("| Who / 担当 | Item / 項目 | Volume / 量 | "
              + (" | ".join(cols) if book == "claude" else "Cost / 費用") + " |")
        print("|---|---|---|" + "---:|" * len(cols))
        for i, (b, who, item, qty, _) in enumerate(base):
            if b == book:
                print(f"| {who} | {item} | {qty} | " + " | ".join(f"${budgets[n][i][4]:.1f}" for n in cols) + " |")
        subs = {n: sum(r[4] for r in budgets[n] if r[0] == book) for n in cols}
        print("| | Subtotal / 小計 | | " + " | ".join(f"**${subs[n]:.0f}**" for n in cols) + " |")
        print(f"| | Plus {SPARE:.0%} / {SPARE:.0%} 上乗せ | | "
              + " | ".join(f"**about ${subs[n] * (1 + SPARE):.0f} / 約 ${subs[n] * (1 + SPARE):.0f}**" for n in cols)
              + " |")
        print()
    print("### M3 extrapolation (outside M2's two caps) / M3 の外挿（M2 の 2 つの上限には含めない）")
    print()
    print("| Item / 項目 | Volume / 量 | Ledger / 台帳 | " + " | ".join(PLANS) + " |")
    print("|---|---|---|" + "---:|" * len(PLANS))
    m3 = {n: m3_rows(plan, prices) for n, plan in PLANS.items()}
    for i, (item, qty, book, _) in enumerate(m3[next(iter(PLANS))]):
        print(f"| {item} | {qty} | {book} | " + " | ".join(f"${m3[n][i][3]:.0f}" for n in PLANS) + " |")
    print()
    first = slice_pass({}, prices)
    # The evals live-mode estimate multiplies "steps that call a model" (MODEL_STEPS in live.py) by a per-step unit
    # price, so average over those kinds of steps here too
    # evals の live の見積もりは「モデルを呼ぶステップ」（live.py の MODEL_STEPS）に 1 ステップの単価を掛けるので、
    # ここでもその種類のステップ数で平均する
    model_steps = {"say", "act", "propose", "silence", "choose"}
    steps = sum(c.get("runs", 5) * sum(step_kind(s) in model_steps for s in c["steps"])
                for f in sorted(SLICE.glob("*.jsonl"))
                for c in (json.loads(x) for x in f.read_text("utf-8").splitlines() if x.strip()))
    persona, persona_g = sim(SLICE_SIM, {}, prices)
    print("To write into evals/config/live-cost.json (on Sonnet) / evals/config/live-cost.json に書く値（Sonnet）:")
    print(f"- turn: claude ${first[0] / steps:.3f}, google ${first[1] / steps:.3f}"
          f" (average over the {steps} model-calling steps of one full slice pass"
          f" / スライス 1 回分のモデルを呼ぶ {steps} ステップの平均)")
    print(f"- judge: claude ${judge_call(prices, True):.3f} (via Batch / Batch 経由)")
    print(f"- simulatedPlaythrough: claude ${persona:.2f}, google ${persona_g:.2f}"
          " (one slice-length playthrough / スライスの長さの 1 プレイ)")


if __name__ == "__main__":
    main()
