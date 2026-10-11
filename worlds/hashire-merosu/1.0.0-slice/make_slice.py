"""从完整版的编写源生成切片版的编写源（S-077，dev-plan「完整世界模型 + 一份切片配置」）。

    python -I worlds/hashire-merosu/1.0.0-slice/make_slice.py

读 `1.0.0-draft/world.src.json`，写 `1.0.0-slice/world.src.json`；之后 build_world 照常校验、展开引文，
出 `1.0.0-slice/world.json`（`.github/scripts/check_world.sh` 一起跑）。切片和完整版的差别全在这个文件里，
每一处改动都注明 S-077 的哪一条。城门、工房、收幕的固定演出和可调查物（S-080 ④、S-087）W-2 起写在完整版里，
切片照抄。生成出来的 `world.src.json` 不要手改：改完整版的编写源或这个脚本，再重跑。
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DRAFT = HERE.parent / "1.0.0-draft" / "world.src.json"
OUT = HERE / "world.src.json"
SOURCE = HERE.parent / "sources" / "melos_plain.txt"

ROLE = "role.traveler"
T_JUMP = 5370  # 三日目 17:30（S-077 ⑤）
GROUND = "place.execution-ground"

# 跳转时的人物去向（S-077 ⑦）：老爺到刑场，フィロストラトス去进城的路（结局不上场）
OLD_MAN_TO_GROUND = {"op": "relocate", "character": "char.old-man", "place": GROUND}
PHILOSTRATUS_TO_ROAD = {"op": "relocate", "character": "char.philostratus", "place": "place.road-to-city"}
# 幕末页算玩家知道约定（S-077 ⑫，PM 10-10）：三条落地都写。约定没成立（beat.05 没发生）时事实不成立，knows() 照样算不知道
PLAYER_KNOWS_PROMISE = {"op": "learn", "character": "player", "fact": "fact.promise"}
# S-088：切片里立约前的两拍是锚点（见 make_slice 里的注释）
SLICE_ANCHORS = ("beat.03", "beat.04")

# 第一幕的两个去处（S-077 ④⑤；副题的后半：UX 文案表；落点和落地句：前端 #22 的位置点，UX `ux/slice/jump-transition.md`「落地」）
SLICE_EXITS: list[dict[str, Any]] = [
    {
        "id": "exit.1.city",
        "label": "市に残り、メロスの帰りを待つ",
        "sub": "西の門が見える所で",
        "toAct": "act.4",
        "place": GROUND,
        "t": T_JUMP,
        "spot": "ground-west",
        "effects": [{**OLD_MAN_TO_GROUND, "spot": "stake-front"}, PHILOSTRATUS_TO_ROAD, PLAYER_KNOWS_PROMISE],
        "arrival": {"line": "刑場の西のはずれ。ここからなら、西の門をくぐる者が、だれより先に見える。"},
    },
    {
        "id": "exit.1.old-man",
        "label": "老爺の家に身を寄せる",
        "sub": "老爺があなたを覚えている",
        "toAct": "act.4",
        "place": GROUND,
        "t": T_JUMP,
        "requires": [{"var": "var.player.walkedOldManHome", "op": "==", "value": True}],
        "spot": "stake-front",
        "effects": [{**OLD_MAN_TO_GROUND, "spot": "stake-front-side"}, PHILOSTRATUS_TO_ROAD, PLAYER_KNOWS_PROMISE],
        "arrival": {
            "line": "三日のあいだ、老爺はあなたを家に置いてくれた。いまは二人で、刑場の前に立っている。",
            "opener": "char.old-man",
        },
    },
]

# 「ほかの考えがある」成行时的落点（契约 1.7 的 Act.plan，C-19，后端 10-10 定）：同样到三日目 17:30 的刑场。玩家站起点
# stake-front（UX「刑場（数据默认）」），老爺在西头 ground-west；打算自己的效果（例：群众 learn 约定）由叙事者提取后加上
SLICE_PLAN: dict[str, Any] = {
    "toAct": "act.4",
    "place": GROUND,
    "t": T_JUMP,
    "spot": "stake-front",
    "effects": [{**OLD_MAN_TO_GROUND, "spot": "ground-west"}, PHILOSTRATUS_TO_ROAD, PLAYER_KNOWS_PROMISE],
    "arrival": {"line": "三日目の夕方。あなたは、刑場の近くに来ていた。"},
}


def by_id(xs: list[dict[str, Any]], id_: str) -> dict[str, Any]:
    return next(x for x in xs if x["id"] == id_)


def make_slice(src: dict[str, Any]) -> dict[str, Any]:
    w = copy.deepcopy(src)
    w["worldModelVersion"] = w["worldModelVersion"].replace("-draft.", "-slice.")  # 跟着完整版的修订号
    w["_authoring"] = (
        "切片版。由 1.0.0-slice/make_slice.py 从 1.0.0-draft/world.src.json 生成，不要手改。" + w["_authoring"]
    )

    # ① 只开旅人；王城的三条 conditionalAccess 不开
    traveler = by_id(w["roles"], ROLE)
    traveler.pop("conditionalAccess", None)
    traveler["note"] = "誰も知らない。切片では広場・石工房・刑場だけ（S-077 ①）。"
    w["roles"] = [traveler]
    for c in w["characters"]:  # 别的身份的开局互助只是普通互助
        for aid in c.get("mutualAid", []):
            if aid.get("opening") not in (None, ROLE):
                del aid["opening"]

    # ① 旅人去不了的地点上的情境动作去掉（王城的「保証する」、归途和村子的都在这里）；只给别的身份的也去掉
    access = set(traveler["access"])
    affs = []
    for a in w["affordances"]:
        if a["place"] not in access or ("roles" in a and ROLE not in a["roles"]):
            continue
        if "roles" in a:
            a["roles"] = [ROLE]
        affs.append(a)
    w["affordances"] = affs

    # ① 第一幕不开王城；第四幕只在广场（归途 M3 才做）
    acts = {a["id"]: a for a in w["acts"]}
    acts["act.1"]["scenes"] = ["scene.syracuse-square"]
    acts["act.4"]["scenes"] = ["scene.syracuse-square"]
    for a in acts.values():  # 归途的停靠点（S-081）切片用不上；幕末第一行和预告是完整版的（切片用前端的文案，copy-ja 6）
        for k in ("stops", "endLines", "closingLine"):
            a.pop(k, None)
    # 第二、三幕在切片里只在后台结算，去处不会出现；落在归途和王城（第四幕只有广场）的去掉，其余照旧
    acts["act.3"]["exits"] = [e for e in acts["act.3"]["exits"] if e["id"] not in ("exit.3.road", "exit.3.vigil")]

    # ② 玩家不会被抓：叙事者提交 arrested 会被第 3 步按取值拒掉（bad-value）。hostage 留着：全局规则和
    #    「あなたが身代わりになった」要它，切片里进不了王城，按地点就做不到
    custody = by_id(w["stateVars"], "var.player.custody")
    custody["values"].remove("arrested")
    del custody["valueLabels"]["arrested"]

    # S-088（PM 10-11）：切片围着约定做，约定一定要立成，收幕时 5 类结局才一定有一类成立（B-9 数据评审第 4 题）。
    # 锚点不能阻止、推迟。设的是 beat.03、04，不是 04、05：
    # - beat.04 的前提「梅洛斯知道王的暴虐」只有 beat.03 给；
    # - beat.05（立约）的前提「梅洛斯被抓」由锚点 beat.04 写下，叙事者推翻不了（R1），beat.05 又在玩家去不了的王城，所以一定立成；
    # - beat.05 设成锚点会锁住它写的 var.hostage.who，B-4「我来当人质」就被 R1 拒掉，切片里走不到 player-substituted
    beats = {b["id"]: b for b in w["beats"]}
    for bid in SLICE_ANCHORS:
        beats[bid]["kind"] = "anchor"
    anchored = {*w["anchors"], *SLICE_ANCHORS}
    w["anchors"] = sorted((a for a in anchored if a in beats), key=lambda a: beats[a]["order"]) + [
        a for a in w["anchors"] if a not in beats
    ]

    # ④⑤ 幕末只列市里去得了的两个去处，都跳到三日目 17:30 的刑场；「ほかの考えがある」是前端的固定选项，成行时落在 plan
    acts["act.1"]["exits"] = copy.deepcopy(SLICE_EXITS)
    acts["act.1"]["plan"] = copy.deepcopy(SLICE_PLAN)

    # S-050：切片里只和老爺、梅洛斯说话；别的人物只有走动版，没有对话版（S-078 ①）
    for c in w["characters"]:
        if c["talkable"] and c["id"] not in ("char.melos", "char.old-man"):
            c["talkable"] = False

    # ⑩ 石工房开着，但第一幕见不到セリヌンティウス和フィロストラトス（在屋里干活、不出来）
    for cid in ("char.selinuntius", "char.philostratus"):
        by_id(w["characters"], cid)["initialActivity"] = "absent"

    # 旅人去不了的地点上的可调查物（归途的川）和只在它们上面演的固定演出也去掉
    w["objects"] = [o for o in w.get("objects", []) if o["place"] in access]
    gone = {o["id"] for o in src.get("objects", [])} - {o["id"] for o in w["objects"]}
    w["setPieces"] = [p for p in w.get("setPieces", []) if p["on"].get("target") not in gone]

    # 上面去掉身份和情境动作以后没人拿得到的物品（别的身份开局带的）也去掉
    rest = json.dumps({k: v for k, v in w.items() if k != "items"}, ensure_ascii=False)
    w["items"] = [x for x in w["items"] if f'"{x["id"]}"' in rest]

    # 1.10：注音词表只留原文里有、或者切片里还出现的词（别的身份的名字、他们开局带的东西去掉，build_world 查词都出现过）
    if "ruby" in w:
        seen = SOURCE.read_text(encoding="utf-8") + json.dumps({k: v for k, v in w.items() if k != "ruby"}, ensure_ascii=False)
        w["ruby"] = [x for x in w["ruby"] if x["word"] in seen]

    return w


def main() -> int:
    src = json.loads(DRAFT.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps(make_slice(src), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parents[2])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
