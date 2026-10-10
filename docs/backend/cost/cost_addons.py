#!/usr/bin/env python3
"""What D-012〜D-015 add to the per-run cost, on top of data's model (data/cost/cost_model.py).

  python3 -I backend/cost/cost_addons.py      → Markdown tables for backend-design §8

Same prices, exchange rate and conventions as data's model (it is imported, not copied). Every number is an
estimate; spike S-5 replaces them with measured runs.
"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "data_cost_model", Path(__file__).resolve().parents[2] / "data" / "cost" / "cost_model.py")
dm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dm)

PRICE, JPY, text_call = dm.PRICE, dm.JPY, dm.text_call

ADD = dict(
    acts=4, key_moments=4, turns_per_midact_tick=8,        # world ticks: act changes + key moments + every 8 settled turns
    tick_in=6000, tick_out=500, tick_think=800,            # plans + director in one flash call (MEDIUM)
    tick_event_share=0.6, tick_check_in=5000, tick_check_out=300, tick_check_think=700,  # one batched check
    improv_extra_out=60, improv_share=0.25, improv_in=1500, improv_out=80,               # extraction field + lite check
    ending_extra_in=12000, ending_extra_out=3000, verify_extra_in=6000, verify_extra_out=1000,  # 3 layers, 7 characters
    safety_in=500, safety_out=30,                          # self-harm check on every player line (flash-lite)
    suggest_share=0.6, suggest_in=2000, suggest_out=150,   # chips after a character speaks (flash-lite)
    actplan_calls=1.5, actplan_in=5000, actplan_out=300, actplan_think=500,  # free-form plan at act end
    approach_turns=3, confirm_turns=2,                     # extra Live turns the server starts
)

LEVERS = dict(
    triage_in=1500, triage_out=20, triage_pass=0.6,        # flash-lite decides whether a turn needs full extraction
    card_from_3d=True,                                     # ux 11.3: card picture = a frame of the 3D ending, no image model
)


def addons(p: dict, a: dict = ADD) -> dict:
    f, n = p["flash"], p["turns"]
    live_per_turn = dm.live_cost(p) / n
    ticks = (a["acts"] - 1) + a["key_moments"] + n / a["turns_per_midact_tick"]
    r = {}
    r["世界推进（角色打算 + 导演）"] = ticks * (
        text_call(f, a["tick_in"], a["tick_out"] + a["tick_think"], p["cached_share"])
        + a["tick_event_share"] * text_call(f, a["tick_check_in"], a["tick_check_out"] + a["tick_check_think"], p["cached_share"]))
    r["即兴设定"] = n * (text_call(f, 0, a["improv_extra_out"])
                       + a["improv_share"] * text_call("flash_lite", a["improv_in"], a["improv_out"]))
    r["三层结局（多出的部分）"] = text_call(f, a["ending_extra_in"], a["ending_extra_out"]) + text_call(f, a["verify_extra_in"], a["verify_extra_out"])
    r["自伤筛查"] = n * text_call("flash_lite", a["safety_in"], a["safety_out"])
    r["候选话语"] = n * a["suggest_share"] * text_call("flash_lite", a["suggest_in"], a["suggest_out"])
    r["幕末自由说"] = a["actplan_calls"] * text_call(f, a["actplan_in"], a["actplan_out"] + a["actplan_think"], p["cached_share"])
    r["角色主动开口、确认"] = (a["approach_turns"] + a["confirm_turns"]) * live_per_turn
    return r


def levers(p: dict, lv: dict = LEVERS) -> dict:
    f, n = p["flash"], p["turns"]
    full_extract = n * text_call(f, p["extract_in"], p["extract_out"] + p["extract_think"], p["cached_share"])
    r = {"闲聊轮先分流": n * text_call("flash_lite", lv["triage_in"], lv["triage_out"]) - (1 - lv["triage_pass"]) * full_extract}
    if lv["card_from_3d"]:
        r["结局卡用 3D 定格"] = -p["images"] * PRICE["image"][p["image_kind"]]
    return r


def main() -> None:
    scen = {"基准（20 分钟 40 轮）": {}, "玩得久（30 分钟 60 轮）": dict(minutes=30, turns=60),
            "压力（60 轮、每轮都检查）": dict(minutes=30, turns=60, turns_per_conv=10, check_share=1.0, check_attempts=2.0)}
    rows = {}
    for name, over in scen.items():
        p = {**dm.BASE, **over}
        base = dm.session_cost(p)["合计"]
        add = addons(p)
        lev = levers(p)
        rows[name] = {"数据工程的基准（v1.0 口径）": base, **add, "小计（加上新增）": base + sum(add.values()),
                      **lev, "合计（用了杠杆）": base + sum(add.values()) + sum(lev.values())}
    keys = list(next(iter(rows.values())).keys())
    print("| 项目 | " + " | ".join(rows) + " |")
    print("|---|" + "---:|" * len(rows))
    for k in keys:
        bold = k.startswith(("小计", "合计"))
        cells = [(f"**${v:.2f}（{v * JPY:.0f} 円）**" if bold else f"${v:+.3f}" if k not in ("数据工程的基准（v1.0 口径）",) else f"${v:.2f}（{v * JPY:.0f} 円）")
                 for v in (rows[n][k] for n in rows)]
        print(f"| {k} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
