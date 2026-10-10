"""从完整版的编写源生成切片版的编写源（S-077，dev-plan「完整世界模型 + 一份切片配置」）。

    python -I worlds/hashire-merosu/1.0.0-slice/make_slice.py

读 `1.0.0-draft/world.src.json`，写 `1.0.0-slice/world.src.json`；之后 build_world 照常校验、展开引文，
出 `1.0.0-slice/world.json`（`.github/scripts/check_world.sh` 一起跑）。切片和完整版的差别全在这个文件里，
每一处改动都注明 S-077 的哪一条。生成出来的 `world.src.json` 不要手改：改完整版的编写源或这个脚本，再重跑。
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

ROLE = "role.traveler"
T_JUMP = 5370  # 三日目 17:30（S-077 ⑤）
GROUND = "place.execution-ground"

# 跳转时的人物去向（S-077 ⑦）：老爺到刑场，フィロストラトス去进城的路（结局不上场）
OLD_MAN_TO_GROUND = {"op": "relocate", "character": "char.old-man", "place": GROUND}
PHILOSTRATUS_TO_ROAD = {"op": "relocate", "character": "char.philostratus", "place": "place.road-to-city"}

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
        "effects": [{**OLD_MAN_TO_GROUND, "spot": "stake-front"}, PHILOSTRATUS_TO_ROAD],
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
        "effects": [{**OLD_MAN_TO_GROUND, "spot": "stake-front-side"}, PHILOSTRATUS_TO_ROAD],
        "arrival": {
            "line": "三日のあいだ、老爺はあなたを家に置いてくれた。いまは二人で、刑場の前に立っている。",
            "opener": "char.old-man",
        },
    },
]


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
    # 第二、三幕在切片里只在后台结算，去处不会出现；落在归途的那个去掉，其余照旧
    acts["act.3"]["exits"] = [e for e in acts["act.3"]["exits"] if e["id"] != "exit.3.road"]

    # ② 玩家不会被抓：叙事者提交 arrested 会被 R2 按取值拒掉（hostage 留着：全局规则和「あなたが身代わりになった」要它，
    #    切片里进不了王城，按地点就做不到）
    custody = by_id(w["stateVars"], "var.player.custody")
    custody["values"].remove("arrested")
    del custody["valueLabels"]["arrested"]

    # ④⑤ 幕末只列市里去得了的两个去处，都跳到三日目 17:30 的刑场；「ほかの考えがある」是前端的固定选项
    acts["act.1"]["exits"] = copy.deepcopy(SLICE_EXITS)

    # S-050：切片里只和老爺、梅洛斯说话；别的人物只有走动版，没有对话版（S-078 ①）
    for c in w["characters"]:
        if c["talkable"] and c["id"] not in ("char.melos", "char.old-man"):
            c["talkable"] = False

    # ⑩ 石工房开着，但第一幕见不到セリヌンティウス和フィロストラトス（在屋里干活、不出来）
    for cid in ("char.selinuntius", "char.philostratus"):
        by_id(w["characters"], cid)["initialActivity"] = "absent"

    # 上面去掉身份和情境动作以后没人拿得到的物品（别的身份开局带的）也去掉
    rest = json.dumps({k: v for k, v in w.items() if k != "items"}, ensure_ascii=False)
    w["items"] = [x for x in w["items"] if f'"{x["id"]}"' in rest]

    return w


def main() -> int:
    src = json.loads(DRAFT.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps(make_slice(src), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parents[2])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
