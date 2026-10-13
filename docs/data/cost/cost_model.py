#!/usr/bin/env python3
"""Cost model for a single experience (one playthrough). Every number is an estimate: duration, turn count and token
amounts are assumptions, to be replaced once backend spike S-5 (simulated playthroughs) has measured them. Standard
library only.

Since D-028 (2026-10-11): Live voice stays on Google, and every model step of the narrator goes to Claude; tiers,
thinking, tokens per step and call counts follow the B-8 card (the "per-playthrough cost" table in
docs/tasks/m2/B-8.md).
Google unit prices are in pricing-2026-10-06.md; Claude unit prices are read from the repo's single claude-prices.json
(in evals/config until B-8 moves it into packages/llm), not copied here. Exchange rate: 1 USD = 150 JPY.

The pre-D-028 all-Gemini version (PRICE, BASE, session_cost, SCENARIOS) is kept as is: the backend's
backend/cost/cost_addons.py uses it. Delete it once backend-design section 8 has been updated for B-8.

Usage:
  python3 -I cost_model.py           → one playthrough after D-028 (Markdown): each scenario, and the Haiku variants
  python3 -I cost_model.py --gemini  → the old pre-D-028 all-Gemini table

1 プレイ（一回の体験）のコストモデル。数字はすべて見積もり：時間、ターン数、トークン量は仮定で、バックエンドの
spike S-5（模擬プレイ）で実測したら置き換える。標準ライブラリのみ。

D-028（2026-10-11）以降：Live の音声は Google に残し、ナレーターがモデルを使うステップはすべて Claude にする。
ティア、思考、ステップごとのトークン数と回数は B-8 カード（docs/tasks/m2/B-8.md の「1 プレイのコスト」の表）に従う。
Google の単価は pricing-2026-10-06.md を参照。Claude の単価はリポジトリに 1 部だけある claude-prices.json を読み
（B-8 で packages/llm に移すまでは evals/config）、ここには写さない。為替レート：1 ドル = 150 円。

D-028 以前のすべて Gemini の版（PRICE、BASE、session_cost、SCENARIOS）はそのまま残す：バックエンドの
backend/cost/cost_addons.py が参照している。backend-design 第 8 節を B-8 に合わせて直したら一緒に削除する。

使い方：
  python3 -I cost_model.py           → D-028 以降の 1 プレイ（Markdown）：各シナリオと Haiku に替えた場合
  python3 -I cost_model.py --gemini  → D-028 以前のすべて Gemini の旧表"""

import json
import sys
from pathlib import Path

M = 1_000_000
JPY = 150
REPO = Path(__file__).resolve().parents[3]
# ---- Unit prices (USD). intro = discounted price before 2026-12-31; list = list price from 2027-01-01 ----
# ---- 単価（USD）。intro = 2026-12-31 までの優待価格、list = 2027-01-01 からの定価 ----
PRICE = {
    "live": {"in_text": 0.75 / M, "in_audio": 3.00 / M, "out_text": 4.50 / M, "out_audio": 12.00 / M},
    "flash_intro": {"in": 0.75 / M, "cached": 0.075 / M, "out": 3.75 / M},
    "flash_list": {"in": 1.50 / M, "cached": 0.15 / M, "out": 7.50 / M},
    "flash_lite": {"in": 0.30 / M, "cached": 0.03 / M, "out": 2.50 / M},
    "image": {"nb2_1k": 0.067, "nb2_lite_1k": 0.034},
    "veo_per_s": {"none": 0.0, "lite_720p_audio": 0.05, "fast_720p_audio": 0.10},
    # 1 vCPU + 0.5 GiB, instance billing (instance-based billing while WebSockets are open)
    # 1 vCPU + 0.5 GiB、インスタンス課金（WebSocket があるときはインスタンス単位の課金）
    "run_instance_hour": 0.0684,
}
AUDIO_TOK_PER_S = 25  # Live API

BASE = dict(
    # PM: 20 minutes, 40 turns; backend: on average 7 turns per character conversation
    # PM：20 分 40 ターン。バックエンド：登場人物との会話 1 本あたり平均 7 ターン
    minutes=20, turns=40, turns_per_conv=7,
    # Backend: player and character each speak about 6 minutes → about 9 seconds per turn
    # バックエンド：プレイヤーと登場人物がそれぞれ約 6 分話す → 1 ターン約 9 秒
    player_s=9, char_s=9,
    # System instruction per conversation: rules + persona + situation + memories (text tokens)
    # 会話ごとのシステム指示：ルール + 人物設定 + 状況 + 記憶（テキストトークン）
    live_setup_text=2500,
    # Japanese transcription is about 6 tokens per second (transcription on for both input and output)
    # 日本語の書き起こしは毎秒約 6 トークン（入力・出力とも書き起こしを有効にする）
    transcript_tok_per_s=6,
    flash="flash_list",
    # One extraction per turn (LOW thinking) / 毎ターン 1 回の抽出（LOW 思考）
    extract_in=3000, extract_out=300, extract_think=200, cached_share=0.6,
    # Half the turns have candidate events for the model to check; 1.3 attempts on average
    # 半分のターンでモデルがチェックする候補イベントがある。平均 1.3 回試行
    check_share=0.5, check_attempts=1.3,
    check_in=4000, check_out=200, check_think=600,  # MEDIUM thinking / MEDIUM 思考
    # 3.5 Flash-Lite writes memories / 3.5 Flash-Lite が記憶を書く
    memory_share=0.5, memory_in=800, memory_out=80,
    # 3.5 Flash-Lite writes situation briefs / 3.5 Flash-Lite が状況説明を書く
    brief_share=0.5, brief_in=2500, brief_out=400,
    # 3.8 Flash with high thinking + one verification / 3.8 Flash の高思考 + 検証 1 回
    ending_in=20000, ending_out=5000, verify_in=6000, verify_out=500,
    images=1, image_kind="nb2_1k", video_s=0, video_kind="none",
    sessions_per_instance=20,
)

TOTAL = "Total / 合計"
CLOUD_RUN = "Cloud Run share / Cloud Run の按分"


def live_cost(p, single_session=False):
    """Live re-bills the whole conversation context on every turn: all earlier turns' audio counts as input.

    Live は毎ターン、会話全体のコンテキストで課金し直す：それまでの各ターンの音声がすべて入力に入る。"""
    pr = PRICE["live"]
    a_in, a_out = p["player_s"] * AUDIO_TOK_PER_S, p["char_s"] * AUDIO_TOK_PER_S
    per_turn_out = a_out * pr["out_audio"] + (p["player_s"] + p["char_s"]) * p["transcript_tok_per_s"] * pr["out_text"]

    def conversation(n):
        return sum(p["live_setup_text"] * pr["in_text"] + (k * (a_in + a_out) + a_in) * pr["in_audio"] + per_turn_out
                   for k in range(n))
    if single_session:
        return conversation(p["turns"])
    full, rest = divmod(p["turns"], p["turns_per_conv"])
    return full * conversation(p["turns_per_conv"]) + conversation(rest)


def text_call(model, tin, tout, cached_share=0.0):
    pr = PRICE[model]
    return tin * (1 - cached_share) * pr["in"] + tin * cached_share * pr["cached"] + tout * pr["out"]


def session_cost(p, single_session=False):
    """Before D-028: the whole narrator on Gemini.

    D-028 以前：ナレーターはすべて Gemini。"""
    n, f = p["turns"], p["flash"]
    r = {}
    r["Voice conversation (Live) / 音声会話（Live）"] = live_cost(p, single_session)
    r["Narrator extraction / ナレーターの抽出"] = n * text_call(
        f, p["extract_in"], p["extract_out"] + p["extract_think"], p["cached_share"])
    r["Model check / モデルチェック"] = n * p["check_share"] * p["check_attempts"] * text_call(
        f, p["check_in"], p["check_out"] + p["check_think"], p["cached_share"])
    r["Memory and situation brief / 記憶と状況説明"] = n * (
        p["memory_share"] * text_call("flash_lite", p["memory_in"], p["memory_out"])
        + p["brief_share"] * text_call("flash_lite", p["brief_in"], p["brief_out"]))
    r["Ending settlement / エンディングの確定"] = (text_call(f, p["ending_in"], p["ending_out"])
                                                 + text_call(f, p["verify_in"], p["verify_out"]))
    r["Ending illustration / エンディングの挿絵"] = p["images"] * PRICE["image"][p["image_kind"]]
    r["Ending video / エンディングの短編動画"] = p["video_s"] * PRICE["veo_per_s"][p["video_kind"]]
    r[CLOUD_RUN] = PRICE["run_instance_hour"] * p["minutes"] / 60 / p["sessions_per_instance"]
    r[TOTAL] = sum(r.values())
    return r


SCENARIOS = {
    "Baseline (20 min, 40 turns) / 基準（20 分 40 ターン）": {},
    "Baseline · 2026 intro price / 基準・2026 年内の優待価格": dict(flash="flash_intro"),
    "Long play (30 min, 60 turns) / 長めのプレイ（30 分 60 ターン）": dict(minutes=30, turns=60),
    "Stress (30 min, 60 turns, check every turn, 2 attempts, 10-turn sessions)"
    " / 負荷（30 分 60 ターン、毎ターンチェック、2 回試行、会話 10 ターン）":
        dict(minutes=30, turns=60, turns_per_conv=10, check_share=1.0, check_attempts=2.0),
    "Baseline + 8 s video (Veo 3.1 Lite) / 基準 + 8 秒の短編動画（Veo 3.1 Lite）":
        dict(video_s=8, video_kind="lite_720p_audio"),
}


# ---- After D-028: text models go to Claude (B-8) ----
# ---- D-028 以降：テキストモデルは Claude（B-8） ----

# Haiku 5.5's tokenizer counts about 30% more tokens for the same text (B-8)
# Haiku 5.5 のトークナイザーは同じ文章を約 30% 多くトークンとして数える（B-8）
HAIKU_TOKENS = 1.3


def claude_prices():
    """Read claude-prices.json: in packages/llm after B-8, in evals/config before. The repo holds only one copy.

    claude-prices.json を読む：B-8 以降は packages/llm、それ以前は evals/config。リポジトリに 1 部だけ。"""
    found = sorted(REPO.glob("packages/llm/**/claude-prices.json")) + [REPO / "evals" / "config" / "claude-prices.json"]
    path = next(x for x in found if x.exists())
    d = json.loads(path.read_text(encoding="utf-8"))
    tiers = {k: {"in": v["input"] / M, "cached": v["cacheRead"] / M, "out": v["output"] / M}
             for k, v in d["perMTok"].items()}
    return tiers, d["cacheWriteMultiplier"], d["batchDiscount"]


# B-8's "per-playthrough cost" table, one row per step. tok: which tier's tokenizer the table's token counts use
# (B-8 already multiplied the Haiku rows by 1.3).
# cached = world-model prefix plus this prompt's instructions, served from cache; fresh = state, this turn, request
# fields; out includes thinking. calls(p): calls per playthrough. The keys match the backend's prompt names where
# there is one; LABELS gives the row names printed in the tables.
# B-8 の「1 プレイのコスト」の表、1 行 1 ステップ。tok：表のトークン数がどのティアのトークナイザーで数えたものか
# （Haiku の行は B-8 で 1.3 倍済み）。
# cached = 世界モデルのプレフィックスとこのプロンプトの説明、キャッシュ経由。fresh = 状態、このターン、リクエストの
# フィールド。out は思考を含む。calls(p)：1 プレイの回数。キーはバックエンドのプロンプト名があればそれに合わせ、
# 表に出す行名は LABELS にある。
STEPS = {
    "triage":        dict(tier="haiku",  tok="haiku",  cached=0,     fresh=1200,  out=30,
                          calls=lambda p: p["turns"]),
    "extract":       dict(tier="sonnet", tok="sonnet", cached=17000, fresh=1500,  out=300,
                          calls=lambda p: p["turns"] * (p["extract_share"] + p["action_share"])),
    "check":         dict(tier="sonnet", tok="sonnet", cached=17000, fresh=2000,  out=1200,
                          calls=lambda p: p["turns"] * p["check_share"] * p["check_attempts"]),
    "rewrite":       dict(tier="sonnet", tok="sonnet", cached=17000, fresh=2000,  out=400,
                          calls=lambda p: p["turns"] * p["rewrite_share"]),
    "narrate":       dict(tier="sonnet", tok="sonnet", cached=17000, fresh=1200,  out=120,
                          calls=lambda p: p["turns"] * p["action_share"]),
    "plan":          dict(tier="sonnet", tok="sonnet", cached=17000, fresh=2000,  out=600,
                          calls=lambda p: p["acts"]),
    "safety":        dict(tier="haiku",  tok="haiku",  cached=0,     fresh=1600,  out=30,
                          calls=lambda p: p["turns"] * p["safety_per_turn"]),
    "memory":        dict(tier="haiku",  tok="haiku",  cached=0,     fresh=1000,  out=100,
                          calls=lambda p: p["turns"] * p["memory_share"]),
    "suggest":       dict(tier="haiku",  tok="haiku",  cached=0,     fresh=2000,  out=200,
                          calls=lambda p: p["turns"] * p["suggest_share"]),
    "delete_memory": dict(tier="haiku",  tok="haiku",  cached=0,     fresh=800,   out=80,
                          calls=lambda p: p["deletes"]),
    "world_tick":    dict(tier="sonnet", tok="sonnet", cached=17000, fresh=3000,  out=1500,
                          calls=lambda p: p["ticks_fixed"] + p["turns"] * p["ticks_per_turn"]),
    "ending":        dict(tier="sonnet", tok="sonnet", cached=17000, fresh=20000, out=3000,
                          calls=lambda p: 1),
    "ending_check":  dict(tier="sonnet", tok="sonnet", cached=17000, fresh=6000,  out=800,
                          calls=lambda p: 1),
}
LABELS = {
    "triage": "Triage / 振り分け",
    "extract": "Extraction / 抽出",
    "check": "Model check / モデルチェック",
    "rewrite": "Rewrite or downgrade / 書き換えまたは格下げ",
    "narrate": "Narration line (地の文) / 地の文",
    "plan": "End-of-act plan / 幕末のプラン",
    "safety": "Safety classification / 安全分類",
    "memory": "One-line memory / 記憶の一文",
    "suggest": "Suggested lines / 発話の候補",
    "delete_memory": "Delete that line / その一文の削除",
    "world_tick": "World tick / 世界の進行",
    "ending": "Ending generation / エンディング生成",
    "ending_check": "Ending check / エンディングのチェック",
}
CLAUDE_SUBTOTAL = "Claude subtotal / Claude 小計"
LIVE_GOOGLE = "Voice conversation (Live, Google) / 音声会話（Live、Google）"

CLAUDE_BASE = dict(
    BASE,
    extract_share=0.6,    # about 40% small talk stops at triage / 約 4 割の雑談は振り分けで止まる
    # About 8 actions (in 40 turns): one extraction and one 地の文 line each
    # アクションは約 8 回（40 ターン）：毎回抽出 1 回と地の文 1 文
    action_share=0.2,
    check_share=0.6, check_attempts=1.3,
    rewrite_share=0.15,   # about 6 rewrites or downgrades / 書き換えまたは格下げ約 6 回
    acts=3,               # end-of-act plan: three acts in the slice / 幕末のプラン：スライスは 3 幕
    # Every line the player says, plus typed ones / プレイヤーが話す毎文と、入力した文
    safety_per_turn=1.1,
    memory_share=0.5, suggest_share=0.6, deletes=1,
    # World tick: 8 for act changes and key moments, plus one every 10 turns
    # 世界の進行：幕の切り替えとキーモーメントで 8 回、加えて 10 ターンごとに 1 回
    ticks_fixed=8, ticks_per_turn=0.1,
    # The ending card's picture is a frame of the 3D ending; no image model is called (ux-design 11.3)
    # エンディングカードの画像は 3D エンディングの 1 フレームで、画像モデルは呼ばない（ux-design 11.3）
    images=0,
)

CLAUDE_SCENARIOS = {
    "20 min, 40 turns / 20 分 40 ターン": {},
    "30 min, 60 turns / 30 分 60 ターン": dict(minutes=30, turns=60),
    "Stress (60 turns, check every turn, 2 attempts) / 負荷（60 ターン、毎ターンチェック、2 回試行）":
        dict(minutes=30, turns=60, extract_share=0.8, check_share=1.0, check_attempts=2.0, rewrite_share=1.0),
}

SONNET_STEPS = [k for k, v in STEPS.items() if v["tier"] == "sonnet"]
TIER_PLANS = {
    "Per B-8 (Sonnet for extraction and check) / B-8 どおり（抽出・チェックは Sonnet）": {},
    "Extraction on Haiku / 抽出を Haiku に": {"extract": "haiku"},
    "Extraction and check both on Haiku / 抽出・チェックとも Haiku に": {"extract": "haiku", "check": "haiku"},
    "Whole narrator on Haiku / ナレーターをすべて Haiku に": {k: "haiku" for k in SONNET_STEPS},
}


def tokens(step, tier):
    """Convert the table's tokens to the token count of the given tier's tokenizer.

    表のトークン数を tier のトークナイザーでの数に換算する。"""
    f = (HAIKU_TOKENS if tier == "haiku" else 1.0) / (HAIKU_TOKENS if step["tok"] == "haiku" else 1.0)
    return step["cached"] * f, step["fresh"] * f, step["out"] * f


def claude_call(name, tier=None, prices=None, batch=False):
    """Cost of one call (with the cache already written).

    1 回の呼び出し（キャッシュは書き込み済み）の費用。"""
    tiers, _, discount = prices or claude_prices()
    step = STEPS[name]
    pr = tiers[tier or step["tier"]]
    cached, fresh, out = tokens(step, tier or step["tier"])
    usd = cached * pr["cached"] + fresh * pr["in"] + out * pr["out"]
    return usd * discount if batch else usd


def cache_write(name, tier=None, prices=None):
    """Extra cost of writing the cache once over reading it: the prefix at 1.25x for a 5-minute write, minus the read
    this call would have paid anyway.

    キャッシュを 1 回書くときに読み取りより余分にかかる費用：プレフィックスを 5 分書き込みの 1.25 倍で計算し、
    この呼び出しで本来払う読み取り分を差し引く。"""
    tiers, write_mult, _ = prices or claude_prices()
    step = STEPS[name]
    pr = tiers[tier or step["tier"]]
    cached = tokens(step, tier or step["tier"])[0]
    return cached * (pr["in"] * write_mult - pr["cached"])


def claude_session(p, plan=None, prices=None, warm=()):
    """One playthrough. The prefix cache is written once per prompt per playthrough (B-8's assumption: with many
    concurrent players it is shared across playthroughs, which is cheaper); prompts in warm are not written
    (simulated playthroughs run back to back, so frequently called prompts keep a warm cache).

    1 プレイ。プレフィックスのキャッシュはプロンプトごとに 1 プレイ 1 回書く（B-8 の仮定：同時に遊ぶ人が多いと
    プレイ間で共有され、もっと安くなる）。warm に入っているものは書かない（模擬プレイは 1 プレイずつ続けて実行するので、
    よく呼ぶプロンプトのキャッシュは温まったまま）。"""
    prices = prices or claude_prices()
    plan = plan or {}
    r = {}
    for name, step in STEPS.items():
        tier = plan.get(name, step["tier"])
        n = step["calls"](p)
        write = step["cached"] and n and name not in warm
        r[LABELS[name]] = n * claude_call(name, tier, prices) + (cache_write(name, tier, prices) if write else 0.0)
    r[CLAUDE_SUBTOTAL] = sum(r.values())
    r[LIVE_GOOGLE] = live_cost(p)
    r[CLOUD_RUN] = PRICE["run_instance_hour"] * p["minutes"] / 60 / p["sessions_per_instance"]
    r[TOTAL] = r[CLAUDE_SUBTOTAL] + r[LIVE_GOOGLE] + r[CLOUD_RUN]
    return r


def table(rows, money_rows=(TOTAL,)):
    keys = list(next(iter(rows.values())).keys())
    out = ["| Item / 項目 | " + " | ".join(rows) + " |", "|---|" + "---:|" * len(rows)]
    for k in keys:
        cells = [f"${rows[n][k]:.3f}" for n in rows]
        if k in money_rows:
            cells = [f"**${rows[n][k]:.2f}（{rows[n][k] * JPY:.0f} 円）**" for n in rows]
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def main_claude():
    prices = claude_prices()
    rows = {name: claude_session({**CLAUDE_BASE, **over}, prices=prices) for name, over in CLAUDE_SCENARIOS.items()}
    print(table(rows))
    print()
    print("Switching to Haiku (total, including Live) / Haiku に替えた場合（合計、Live 込み）:")
    print()
    print("| Narrator tier / ナレーターのティア | " + " | ".join(CLAUDE_SCENARIOS) + " |")
    print("|---|" + "---:|" * len(CLAUDE_SCENARIOS))
    for name, plan in TIER_PLANS.items():
        cells = [claude_session({**CLAUDE_BASE, **over}, plan, prices)[TOTAL] for over in CLAUDE_SCENARIOS.values()]
        print(f"| {name} | " + " | ".join(f"${x:.2f}（{x * JPY:.0f} 円）" for x in cells) + " |")


def main_gemini():
    rows = {name: session_cost({**BASE, **over}) for name, over in SCENARIOS.items()}
    print(table(rows))
    one = live_cost(BASE, single_session=True)
    split = live_cost(BASE)
    print()
    print(f"For comparison: over the same {BASE['turns']} turns, one Live session for the whole playthrough"
          f" (no compression) costs about ${one:.2f} in voice; reopening a session every {BASE['turns_per_conv']}"
          f" turns costs about ${split:.2f} (about {one / split:.1f}x)."
          f" / 比較：同じ {BASE['turns']} ターンで、1 プレイ全体を Live の会話 1 本で通す（圧縮なし）と"
          f"音声は約 ${one:.2f}、"
          f"{BASE['turns_per_conv']} ターンごとに会話を開き直すと約 ${split:.2f}（約 {one / split:.1f} 倍）。")
    base = rows[list(rows)[0]][TOTAL]
    print(f"Baseline: 1,000 playthroughs cost about ${base * 1000:,.0f}"
          f" (about {base * 1000 * JPY / 10000:,.1f} 万円)."
          f" / 基準で 1,000 プレイ約 ${base * 1000:,.0f}（約 {base * 1000 * JPY / 10000:,.1f} 万円）。")


if __name__ == "__main__":
    main_gemini() if "--gemini" in sys.argv[1:] else main_claude()
