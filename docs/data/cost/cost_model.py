#!/usr/bin/env python3
"""单次体验（一局）成本模型。价格见 pricing-2026-10-06.md（官方页面，2026-10-06 查得）。
所有数字是估算：时长、轮数、token 量是假设，等后端 spike S-5（模拟局）实测后替换。只用标准库。
口径和 backend-design.md 第 8 节对齐：叙事者走 global 端点（不加区域价）、结局用 3.8 Flash 高思考、思考 token 按输出计费、
汇率 1 美元 = 150 日元。
用法：python3 -I cost_model.py  → 打印各场景的表格（Markdown）。"""

M = 1_000_000
JPY = 150
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


def main():
    rows = {name: session_cost({**BASE, **over}) for name, over in SCENARIOS.items()}
    keys = list(next(iter(rows.values())).keys())
    print("| 项目 | " + " | ".join(rows) + " |")
    print("|---|" + "---:|" * len(rows))
    for k in keys:
        cells = [f"${rows[n][k]:.3f}" for n in rows]
        if k == "合计":
            cells = [f"**${rows[n][k]:.2f}（{rows[n][k] * JPY:.0f} 円）**" for n in rows]
        print(f"| {k} | " + " | ".join(cells) + " |")
    one = live_cost(BASE, single_session=True)
    split = live_cost(BASE)
    print()
    print(f"对照：同样 {BASE['turns']} 轮，整局只开一个 Live 会话（不压缩）语音约 ${one:.2f}；"
          f"每 {BASE['turns_per_conv']} 轮重开一条会话约 ${split:.2f}（约 {one / split:.1f} 倍）。")
    base = rows[list(rows)[0]]["合计"]
    print(f"基准 1,000 局约 ${base * 1000:,.0f}（约 {base * 1000 * JPY / 10000:,.1f} 万円）。")


if __name__ == "__main__":
    main()
