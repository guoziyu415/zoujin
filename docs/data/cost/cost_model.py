#!/usr/bin/env python3
"""单次体验（一局）成本模型。所有数字是估算：时长、轮数、token 量是假设，等后端 spike S-5（模拟局）实测后替换。只用标准库。

D-028（2026-10-11）以后：Live 的语音留在 Google，叙事者用模型的几步都走 Claude，型号、思考、每步的 token 和次数照 B-8 卡
（docs/tasks/m2/B-8.md「单局成本」那张表）。Google 的单价见 pricing-2026-10-06.md；Claude 的单价读仓库里唯一那份
claude-prices.json（B-8 搬进 packages/llm 以前在 evals/config），这里不另抄一份。汇率 1 美元 = 150 日元。

D-028 以前全用 Gemini 的那一版（PRICE、BASE、session_cost、SCENARIOS）原样留着：后端的 backend/cost/cost_addons.py 引用它，
backend-design 第 8 节按 B-8 改完以后再删。

用法：
  python3 -I cost_model.py           → D-028 以后的一局（Markdown）：各场景、换 Haiku 的几种
  python3 -I cost_model.py --gemini  → D-028 以前全用 Gemini 的旧表"""

import json
import sys
from pathlib import Path

M = 1_000_000
JPY = 150
REPO = Path(__file__).resolve().parents[3]
# ---- 单价（USD）。intro = 2026-12-31 前的优惠价；list = 2027-01-01 起的标价 ----
PRICE = {
    "live": {"in_text": 0.75 / M, "in_audio": 3.00 / M, "out_text": 4.50 / M, "out_audio": 12.00 / M},
    "flash_intro": {"in": 0.75 / M, "cached": 0.075 / M, "out": 3.75 / M},
    "flash_list": {"in": 1.50 / M, "cached": 0.15 / M, "out": 7.50 / M},
    "flash_lite": {"in": 0.30 / M, "cached": 0.03 / M, "out": 2.50 / M},
    "image": {"nb2_1k": 0.067, "nb2_lite_1k": 0.034},
    "veo_per_s": {"none": 0.0, "lite_720p_audio": 0.05, "fast_720p_audio": 0.10},
    "run_instance_hour": 0.0684,  # 1 vCPU + 0.5 GiB，实例计费（有 WebSocket 时按实例计费）
}
AUDIO_TOK_PER_S = 25  # Live API

BASE = dict(
    minutes=20, turns=40, turns_per_conv=7,   # PM：20 分钟 40 轮；后端：平均每条角色会话 7 轮
    player_s=9, char_s=9,                     # 后端：玩家、角色各说约 6 分钟 → 每轮约 9 秒
    live_setup_text=2500,                     # 每条会话的系统指令：规则 + 人设 + 局势 + 记忆（文字 token）
    transcript_tok_per_s=6,                   # 日语转写约每秒 6 token（输入、输出都开转写）
    flash="flash_list",
    extract_in=3000, extract_out=300, extract_think=200, cached_share=0.6,   # 每轮一次提取（LOW 思考）
    check_share=0.5, check_attempts=1.3,      # 一半的轮次有候选事件要模型检查；平均 1.3 次尝试
    check_in=4000, check_out=200, check_think=600,                          # MEDIUM 思考
    memory_share=0.5, memory_in=800, memory_out=80,                         # 3.5 Flash-Lite 写记忆
    brief_share=0.5, brief_in=2500, brief_out=400,                          # 3.5 Flash-Lite 写局势说明
    ending_in=20000, ending_out=5000, verify_in=6000, verify_out=500,       # 3.8 Flash 高思考 + 一次校验
    images=1, image_kind="nb2_1k", video_s=0, video_kind="none",
    sessions_per_instance=20,
)


def live_cost(p, single_session=False):
    """Live 每一轮都按整段会话上下文重新计费：之前各轮的音频都算进输入。"""
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
    """D-028 以前：叙事者全用 Gemini。"""
    n, f = p["turns"], p["flash"]
    r = {}
    r["语音对话（Live）"] = live_cost(p, single_session)
    r["叙事者提取"] = n * text_call(f, p["extract_in"], p["extract_out"] + p["extract_think"], p["cached_share"])
    r["模型检查"] = n * p["check_share"] * p["check_attempts"] * text_call(f, p["check_in"], p["check_out"] + p["check_think"], p["cached_share"])
    r["记忆与局势说明"] = n * (p["memory_share"] * text_call("flash_lite", p["memory_in"], p["memory_out"])
                         + p["brief_share"] * text_call("flash_lite", p["brief_in"], p["brief_out"]))
    r["结局结算"] = text_call(f, p["ending_in"], p["ending_out"]) + text_call(f, p["verify_in"], p["verify_out"])
    r["结局插画"] = p["images"] * PRICE["image"][p["image_kind"]]
    r["结局短片"] = p["video_s"] * PRICE["veo_per_s"][p["video_kind"]]
    r["Cloud Run 分摊"] = PRICE["run_instance_hour"] * p["minutes"] / 60 / p["sessions_per_instance"]
    r["合计"] = sum(r.values())
    return r


SCENARIOS = {
    "基准（20 分钟 40 轮）": {},
    "基准 · 2026 年内优惠价": dict(flash="flash_intro"),
    "玩得久（30 分钟 60 轮）": dict(minutes=30, turns=60),
    "压力（30 分钟 60 轮、每轮都检查、2 次尝试、会话 10 轮）": dict(minutes=30, turns=60, turns_per_conv=10, check_share=1.0, check_attempts=2.0),
    "基准 + 8 秒短片（Veo 3.1 Lite）": dict(video_s=8, video_kind="lite_720p_audio"),
}


# ---- D-028 以后：文字模型走 Claude（B-8） ----

HAIKU_TOKENS = 1.3  # Haiku 5.5 的分词器，同样的文字多算约 30% 的 token（B-8）


def claude_prices():
    """读 claude-prices.json：B-8 以后在 packages/llm 里，之前在 evals/config。仓库里只有一份。"""
    found = sorted(REPO.glob("packages/llm/**/claude-prices.json")) + [REPO / "evals" / "config" / "claude-prices.json"]
    path = next(x for x in found if x.exists())
    d = json.loads(path.read_text(encoding="utf-8"))
    tiers = {k: {"in": v["input"] / M, "cached": v["cacheRead"] / M, "out": v["output"] / M} for k, v in d["perMTok"].items()}
    return tiers, d["cacheWriteMultiplier"], d["batchDiscount"]


# B-8「单局成本」那张表，一行一步。tok：表里的 token 是按哪一档的分词数的（Haiku 那几行 B-8 已经乘过 1.3）。
# cached = 世界模型前缀加这种提示的说明，走缓存；fresh = 状态、这一轮、请求字段；out 含思考。calls(p)：一局几次。
STEPS = {
    "分流":       dict(tier="haiku",  tok="haiku",  cached=0,     fresh=1200,  out=30,   calls=lambda p: p["turns"]),
    "提取":       dict(tier="sonnet", tok="sonnet", cached=17000, fresh=1500,  out=300,  calls=lambda p: p["turns"] * (p["extract_share"] + p["action_share"])),
    "模型检查":   dict(tier="sonnet", tok="sonnet", cached=17000, fresh=2000,  out=1200, calls=lambda p: p["turns"] * p["check_share"] * p["check_attempts"]),
    "改写或降级": dict(tier="sonnet", tok="sonnet", cached=17000, fresh=2000,  out=400,  calls=lambda p: p["turns"] * p["rewrite_share"]),
    "地の文":     dict(tier="sonnet", tok="sonnet", cached=17000, fresh=1200,  out=120,  calls=lambda p: p["turns"] * p["action_share"]),
    "幕末打算":   dict(tier="sonnet", tok="sonnet", cached=17000, fresh=2000,  out=600,  calls=lambda p: p["acts"]),
    "安全分类":   dict(tier="haiku",  tok="haiku",  cached=0,     fresh=1600,  out=30,   calls=lambda p: p["turns"] * p["safety_per_turn"]),
    "记忆一句":   dict(tier="haiku",  tok="haiku",  cached=0,     fresh=1000,  out=100,  calls=lambda p: p["turns"] * p["memory_share"]),
    "候选话语":   dict(tier="haiku",  tok="haiku",  cached=0,     fresh=2000,  out=200,  calls=lambda p: p["turns"] * p["suggest_share"]),
    "删除那一句": dict(tier="haiku",  tok="haiku",  cached=0,     fresh=800,   out=80,   calls=lambda p: p["deletes"]),
    "世界推进":   dict(tier="sonnet", tok="sonnet", cached=17000, fresh=3000,  out=1500, calls=lambda p: p["ticks_fixed"] + p["turns"] * p["ticks_per_turn"]),
    "结局生成":   dict(tier="sonnet", tok="sonnet", cached=17000, fresh=20000, out=3000, calls=lambda p: 1),
    "结局检查":   dict(tier="sonnet", tok="sonnet", cached=17000, fresh=6000,  out=800,  calls=lambda p: 1),
}

CLAUDE_BASE = dict(
    BASE,
    extract_share=0.6,    # 约四成闲聊在分流就停
    action_share=0.2,     # 动作约 8 次（40 轮）：每次提取一次、写一句地の文
    check_share=0.6, check_attempts=1.3,
    rewrite_share=0.15,   # 改写或降级约 6 次
    acts=3,               # 幕末打算：切片三幕
    safety_per_turn=1.1,  # 玩家说的每句话，加上打字的
    memory_share=0.5, suggest_share=0.6, deletes=1,
    ticks_fixed=8, ticks_per_turn=0.1,  # 世界推进：换幕和关键时刻 8 次，加上每 10 轮一次
    images=0,             # 结局卡的画面用 3D 结局的一帧，不调图像模型（ux-design 11.3）
)

CLAUDE_SCENARIOS = {
    "20 分钟 40 轮": {},
    "30 分钟 60 轮": dict(minutes=30, turns=60),
    "压力（60 轮，每轮都检查、2 次尝试）": dict(minutes=30, turns=60, extract_share=0.8, check_share=1.0, check_attempts=2.0,
                                          rewrite_share=1.0),
}

SONNET_STEPS = [k for k, v in STEPS.items() if v["tier"] == "sonnet"]
TIER_PLANS = {
    "按 B-8（提取、检查用 Sonnet）": {},
    "提取换 Haiku": {"提取": "haiku"},
    "提取、检查都换 Haiku": {"提取": "haiku", "模型检查": "haiku"},
    "叙事者全用 Haiku": {k: "haiku" for k in SONNET_STEPS},
}


def tokens(step, tier):
    """表里的 token 换成 tier 那一档的分词数。"""
    f = (HAIKU_TOKENS if tier == "haiku" else 1.0) / (HAIKU_TOKENS if step["tok"] == "haiku" else 1.0)
    return step["cached"] * f, step["fresh"] * f, step["out"] * f


def claude_call(name, tier=None, prices=None, batch=False):
    """一次调用（缓存已经写好）的花费。"""
    tiers, _, discount = prices or claude_prices()
    step = STEPS[name]
    pr = tiers[tier or step["tier"]]
    cached, fresh, out = tokens(step, tier or step["tier"])
    usd = cached * pr["cached"] + fresh * pr["in"] + out * pr["out"]
    return usd * discount if batch else usd


def cache_write(name, tier=None, prices=None):
    """写一次缓存比读多出的钱：前缀按 5 分钟写入的 1.25 倍计，减去这次本来要付的读取。"""
    tiers, write_mult, _ = prices or claude_prices()
    step = STEPS[name]
    pr = tiers[tier or step["tier"]]
    cached = tokens(step, tier or step["tier"])[0]
    return cached * (pr["in"] * write_mult - pr["cached"])


def claude_session(p, plan=None, prices=None, warm=()):
    """一局。前缀每种提示每局写一次缓存（B-8 的假设：同时玩的人多时局和局之间共用，更便宜）；
    warm 里的几种不写（模拟局一局接一局地跑，常调的提示缓存一直热着）。"""
    prices = prices or claude_prices()
    plan = plan or {}
    r = {}
    for name, step in STEPS.items():
        tier = plan.get(name, step["tier"])
        n = step["calls"](p)
        write = step["cached"] and n and name not in warm
        r[name] = n * claude_call(name, tier, prices) + (cache_write(name, tier, prices) if write else 0.0)
    r["Claude 小计"] = sum(r.values())
    r["语音对话（Live，Google）"] = live_cost(p)
    r["Cloud Run 分摊"] = PRICE["run_instance_hour"] * p["minutes"] / 60 / p["sessions_per_instance"]
    r["合计"] = r["Claude 小计"] + r["语音对话（Live，Google）"] + r["Cloud Run 分摊"]
    return r


def table(rows, money_rows=("合计",)):
    keys = list(next(iter(rows.values())).keys())
    out = ["| 项目 | " + " | ".join(rows) + " |", "|---|" + "---:|" * len(rows)]
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
    print("换 Haiku（合计，含 Live）：")
    print()
    print("| 叙事者的型号 | " + " | ".join(CLAUDE_SCENARIOS) + " |")
    print("|---|" + "---:|" * len(CLAUDE_SCENARIOS))
    for name, plan in TIER_PLANS.items():
        cells = [claude_session({**CLAUDE_BASE, **over}, plan, prices)["合计"] for over in CLAUDE_SCENARIOS.values()]
        print(f"| {name} | " + " | ".join(f"${x:.2f}（{x * JPY:.0f} 円）" for x in cells) + " |")


def main_gemini():
    rows = {name: session_cost({**BASE, **over}) for name, over in SCENARIOS.items()}
    print(table(rows))
    one = live_cost(BASE, single_session=True)
    split = live_cost(BASE)
    print()
    print(f"对照：同样 {BASE['turns']} 轮，整局只开一个 Live 会话（不压缩）语音约 ${one:.2f}；"
          f"每 {BASE['turns_per_conv']} 轮重开一条会话约 ${split:.2f}（约 {one / split:.1f} 倍）。")
    base = rows[list(rows)[0]]["合计"]
    print(f"基准 1,000 局约 ${base * 1000:,.0f}（约 {base * 1000 * JPY / 10000:,.1f} 万円）。")


if __name__ == "__main__":
    main_gemini() if "--gemini" in sys.argv[1:] else main_claude()
