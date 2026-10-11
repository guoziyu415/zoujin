#!/usr/bin/env python3
"""M2 开发期两本账的估算：m2-model-budget.md 里的表从这里出。全部是推算，M2 第一批跑完后用账本的实数替换。只用标准库。

一次调用的花费、一局的花费用 cost_model.py（D-028 以后的口径，B-8 每一步的 token）。切片评测一整遍按 evals/slice/*.jsonl
逐例数：每种步骤调哪几步模型（EVAL_MIX），乘上 runs；判分按带 judge 的用例 × runs。

用法：python3 -I m2_budget.py  → 两本账的表（Markdown）、写进 evals/config/live-cost.json 的几个单价"""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("data_cost_model", HERE / "cost_model.py")
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

SLICE = cm.REPO / "evals" / "slice"
SEEDS = cm.REPO / "evals" / "seeds"

# 评测里每一步调哪几步模型（每步平均几次）。比整局的比例高：评测的话大多是冲着叙事者去的，很少在分流就停。
FREQUENT = ("提取", "模型检查", "改写或降级")  # 一整遍里一直在调，缓存一直热着
EVAL_MIX = {
    "say": {"分流": 1, "安全分类": 1, "提取": 0.8, "模型检查": 0.8 * 1.3, "改写或降级": 0.2, "记忆一句": 0.5, "候选话语": 0.6,
            "reply": 1},
    "silence": {"reply": 1, "候选话语": 0.6},
    "act": {"提取": 1, "模型检查": 1.3, "改写或降级": 0.2, "地の文": 1},
    "choose": {"世界推进": 1, "地の文": 1},
    "propose": {"安全分类": 1, "幕末打算": 1, "世界推进": 1},
    "advance": {"世界推进": 1},
    "deleteMemory": {"删除那一句": 1},
    "newPlaythrough": {},
    "deletePlaythrough": {},
}
REPLY_USD = 0.015  # 文字模式的人物回答（Gemini 3.8 Flash，B-8 留在 Google）一次：S-068 两次实测折算，扣掉判分
# 判分一次，Opus 5.5，effort low；思考关不掉，算在 out 里。校准实测（10-11，150 次）：进 951〜1,234、平均 1,035，
# 出平均 102、最多 220。切片的对话记录比校准样本长，进按 1,500、出按 150 算
JUDGE = dict(fresh=1500, out=150)
CALIBRATED_USD = 0.93  # 校准 50 条 × 3 次已经实花（Mac 账本）
PLAYER = dict(cached=8000, fresh=1000, out=200)  # AI 玩家一轮，Sonnet 5.5：画像和世界说明走缓存，不走 Batch

PASSES = dict(first=1, haiku_compare=1, tuning=5 * 0.5, gate=2)  # 第一遍、Haiku 对照一遍、调提示 5 次各半遍、过关两遍
SLICE_SIM = dict(minutes=8, turns=15, acts=1, ticks_fixed=3, deletes=0)  # 切片长度的模拟局：第一幕约 15 轮 + 结局结算
PLANS = {
    "Sonnet（按 B-8）": {},
    "提取换 Haiku": {"提取": "haiku"},
    "提取、检查换 Haiku": {"提取": "haiku", "模型检查": "haiku"},
}
COMPARE = PLANS["提取、检查换 Haiku"]  # B-8：S-2 和第一遍评测各多跑一遍 Haiku
SPARE = 0.3  # 重跑、时限触发的重试、Mac 断线后续跑


def step_kind(step):
    keys = set(step) - {"to"}
    if len(keys) != 1 or (kind := next(iter(keys))) not in EVAL_MIX:
        raise SystemExit(f"m2_budget.py 不认识这种步骤：{sorted(step)}，先在 EVAL_MIX 里加上")
    return kind


def slice_pass(plan, prices, folder=SLICE):
    """评测跑一整遍（默认切片）：Claude（叙事者）、Google（人物回答）、判分次数、用例数。模拟局的用例（E7 画像）另算。"""
    cases = [json.loads(x) for f in sorted(folder.glob("*.jsonl")) for x in f.read_text("utf-8").splitlines() if x.strip()]
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
        # 同一例的几次连着跑：不常调的提示每例写一次缓存，常调的一整遍写一次
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
    """一局模拟局（文字模式，不走 Live）：Claude = 叙事者 + AI 玩家；Google = 人物回答。
    一局接一局地跑：常调的提示缓存一直热着，幕末打算和结局那几种每局写一次。"""
    r = cm.claude_session({**cm.CLAUDE_BASE, **p}, plan, prices, warm=(*FREQUENT, "地の文", "世界推进"))
    return r["Claude 小计"] + p.get("turns", 40) * player_turn(prices), p.get("turns", 40) * REPLY_USD


def checks(n, plan_tier, prices):
    """n 次模型检查（S-2 和调检查提示：一条候选一次），缓存写一次。"""
    return n * cm.claude_call("模型检查", plan_tier, prices) + cm.cache_write("模型检查", plan_tier, prices)


def budget(plan, prices):
    """M2 两本账的明细：[(账, 谁, 项, 量, 美元)]。plan 是定了型号以后用的那一档：调提示和过关那几遍评测、两种模拟局。
    定型号以前的照 B-8：调检查提示用 Sonnet，S-2 和第一遍评测 Sonnet、Haiku 各一遍。"""
    first = slice_pass({}, prices)
    compare = slice_pass(COMPARE, prices)
    chosen = slice_pass(plan, prices)
    judged, n_cases = first[2], first[3]
    n_passes = sum(PASSES.values())
    later = PASSES["tuning"] + PASSES["gate"]
    persona, persona_g = sim(SLICE_SIM, plan, prices)
    s5, s5_g = sim({}, plan, prices)
    rows = [
        ("claude", "数据", "评审员校准", "50 条 × 3 次已实花；J23、J24 改细则后复测 2 条 × 3 次",
         CALIBRATED_USD + 6 * judge_call(prices, False)),
        ("claude", "数据", "S-2 留出集（Sonnet，再 Haiku 一遍）", "50 条 × 3 次，两档各一遍",
         checks(150, "sonnet", prices) + checks(150, "haiku", prices)),
        ("claude", "数据", "切片评测：叙事者", f"{n_cases} 例，一整遍 Sonnet、一遍 Haiku 对照，调提示和过关 {later:g} 遍",
         first[0] + compare[0] + later * chosen[0]),
        ("claude", "数据", "切片评测：判分", f"每遍 {judged} 次 × {n_passes:g} 遍，走 Batch", judged * n_passes * judge_call(prices, True)),
        ("claude", "数据", "画像模拟局", "11 个画像 × 2 局，每局约 15 轮，含 AI 玩家", 22 * persona),
        ("claude", "数据", "E1 越狱样本扩写", "量很小", 1.0),
        ("claude", "后端", "B-8 小测", "7 种提示 × 20 次（B-8）", 1.0),
        ("claude", "后端", "调检查提示（在定型号以前，用 Sonnet）", "公开的 10 条 × 3 次 × 5 轮", checks(150, "sonnet", prices)),
        ("claude", "后端", "S-5 模拟局", "10 局 × 40 轮，含 AI 玩家", 10 * s5),
        ("google", "后端", "B-6 预录句", "D-027", 0.2),
        ("google", "数据", "切片评测：人物回答", f"每遍 {first[1] / REPLY_USD:.0f} 次 × {n_passes:g} 遍",
         first[1] * n_passes),
        ("google", "数据", "画像模拟局：人物回答", "22 局 × 15 轮", 22 * persona_g),
        ("google", "后端", "S-5 模拟局：人物回答", "10 局 × 40 轮", 10 * s5_g),
        ("google", "后端", "Live 自测（网关接上以后，内部玩几局）", "10 局 × 20 分钟", 10 * cm.live_cost(cm.BASE)),
        # Model Armor（S-085 ②）每月头 200 万 token 不收钱，之后每百万 $0.10（价目页 2026-10-11）。开发期每月约几十万 token
        ("google", "后端", "Model Armor（接上以后，第二层）", "每月 200 万 token 以内不收钱", 0.0),
    ]
    return rows


def m3_rows(plan, prices):
    """M3：种子跑两遍（第一遍、过关；E7 的画像由 200 局代替），200 局多样性（全长 40 轮）。"""
    seeds = slice_pass(plan, prices, SEEDS)
    s5, s5_g = sim({}, plan, prices)
    return [
        ("种子：叙事者和判分", f"{seeds[3]} 例（E7 画像另算）× 2 遍，判分每遍 {seeds[2]} 次", "Claude",
         2 * (seeds[0] + seeds[2] * judge_call(prices, True))),
        ("种子：人物回答", "同上", "Google", 2 * seeds[1]),
        ("200 局多样性：叙事者和 AI 玩家", "200 局 × 40 轮", "Claude", 200 * s5),
        ("200 局多样性：人物回答", "200 局 × 40 轮", "Google", 200 * s5_g),
    ]


def main():
    prices = cm.claude_prices()
    budgets = {name: budget(plan, prices) for name, plan in PLANS.items()}
    base = budgets[next(iter(PLANS))]
    for book, title in (("claude", "Claude 账"), ("google", "Google 账")):
        # Google 那本不随叙事者的型号变，只出一列
        cols = list(PLANS) if book == "claude" else [next(iter(PLANS))]
        print(f"### {title}")
        print()
        print("| 谁 | 项 | 量 | " + (" | ".join(cols) if book == "claude" else "花费") + " |")
        print("|---|---|---|" + "---:|" * len(cols))
        for i, (b, who, item, qty, _) in enumerate(base):
            if b == book:
                print(f"| {who} | {item} | {qty} | " + " | ".join(f"${budgets[n][i][4]:.1f}" for n in cols) + " |")
        subs = {n: sum(r[4] for r in budgets[n] if r[0] == book) for n in cols}
        print("| | 小计 | | " + " | ".join(f"**${subs[n]:.0f}**" for n in cols) + " |")
        print(f"| | 加 {SPARE:.0%} | | " + " | ".join(f"**约 ${subs[n] * (1 + SPARE):.0f}**" for n in cols) + " |")
        print()
    print("### M3 外推（不在 M2 的两个上限里）")
    print()
    print("| 项 | 量 | 账 | " + " | ".join(PLANS) + " |")
    print("|---|---|---|" + "---:|" * len(PLANS))
    m3 = {n: m3_rows(plan, prices) for n, plan in PLANS.items()}
    for i, (item, qty, book, _) in enumerate(m3[next(iter(PLANS))]):
        print(f"| {item} | {qty} | {book} | " + " | ".join(f"${m3[n][i][3]:.0f}" for n in PLANS) + " |")
    print()
    first = slice_pass({}, prices)
    # evals 的 live 估价按「要调模型的步」（live.py 的 MODEL_STEPS）乘一步的单价，所以这里也按这几种步数平均
    model_steps = {"say", "act", "propose", "silence", "choose"}
    steps = sum(c.get("runs", 5) * sum(step_kind(s) in model_steps for s in c["steps"]) for f in sorted(SLICE.glob("*.jsonl"))
                for c in (json.loads(x) for x in f.read_text("utf-8").splitlines() if x.strip()))
    persona, persona_g = sim(SLICE_SIM, {}, prices)
    print("写进 evals/config/live-cost.json（按 Sonnet）：")
    print(f"- turn：claude ${first[0] / steps:.3f}、google ${first[1] / steps:.3f}（切片一整遍 {steps} 个要调模型的步平均）")
    print(f"- judge：claude ${judge_call(prices, True):.3f}（走 Batch）")
    print(f"- simulatedPlaythrough：claude ${persona:.2f}、google ${persona_g:.2f}（切片长度一局）")


if __name__ == "__main__":
    main()
