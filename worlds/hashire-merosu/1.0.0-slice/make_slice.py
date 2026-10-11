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

# 固定演出（契约 1.7 的 setPieces，2.11；S-080 ④，PM 10-10 定放进切片世界模型）。
# 文字和谁说：UX `ux/slice/act1-end-and-gate.md` 第 1、2、4 节；预录句的声音（警吏 Charon、群众里的女人 Despina、
# セリヌンティウス Iapetus）在 UX 的文案表，不写在这里。
# 同一个时机按列表顺序取第一条条件满足的，所以有条件的写在前面。UX 10-10 的规则：警吏的两句各说一次；
# 抓梅洛斯那场是导演好的，不因为「一次」被跳过，玩家之前已经被「下がれ…」挡过，那场里就改说「二度は言わぬ」；
# 两句都说过以后，再走上去交给叙事者。立约（beat.05）以后第一次走到门口，不管之前挡过几次，警吏赶人时说出约定，
# 玩家就知道了（S-077 ⑪，PM 10-10；台词 UX 第 1 节「约定以后」），之后「二度は言わぬ」没说过就说。叫法统一成「警吏」（UX 10-10）。
# 23:30 以后的「灯は消えていた」只出一次（走进院子和敲门共用）
GATE = "place.castle"  # 王城门口的场景出口通往的地点（布局 exits[].place）；出口给 enabled，由判定拒掉（后端 10-10）
WORKSHOP = "place.stonemason-workshop"
WORKSHOP_DOOR = "obj.workshop-door"
SPEAR = {"narration": "警吏が、あなたの前に槍を下ろした。"}
STAND_BACK = {"speaker": "char.guards", "line": "下がれ、旅の者。ここから先は、通さぬ。"}
NOT_TWICE = {"speaker": "char.guards", "line": "二度は言わぬ。下がれ。"}
PROMISE_MADE = {"speaker": "char.guards", "line": "下がれ。メロスとかいう羊飼いなら、王と約束をした。"}
PROMISE_TERMS = {"speaker": "char.guards", "line": "三日目の日没までに戻らねば、身代わりの石工セリヌンティウスが磔だ。"}
TAKEN_IN = {"narration": "メロスは、王城の奥へ引かれていった。"}
LIGHT_OUT = {"narration": "工房の灯は、いつのまにか消えていた。"}
SLICE_SET_PIECES: list[dict[str, Any]] = [
    {
        "id": "piece.gate-taken-again",
        "on": {"beat": "beat.04"},
        "played": ["piece.gate-turned-away"],
        "once": True,
        "lines": [SPEAR, NOT_TWICE, TAKEN_IN],
        "inferred": True,
        "note": "第 1 节：抓梅洛斯那场，玩家之前已经被挡过一次，第 3 步的警吏改说第二句（UX 10-10）",
    },
    {
        "id": "piece.gate-taken",
        "on": {"beat": "beat.04"},
        "once": True,
        "lines": [SPEAR, STAND_BACK, TAKEN_IN],
        "inferred": True,
        "note": "第 1 节：跟着梅洛斯走到王城门口。梅洛斯回头看一眼、不说话是演出，不是台词",
    },
    {
        "id": "piece.gate-promise",
        "on": {"act": "go", "target": GATE, "refused": True},
        "after": ["beat.05"],
        "once": True,
        "lines": [SPEAR, PROMISE_MADE, PROMISE_TERMS],
        "learns": [{"character": "player", "fact": "fact.promise"}],
        "inferred": True,
        "note": "第 1 节「约定以后」：只说约定本身（日限、晚了人质死、人质是谁），不提深夜召人质、出发、王的耳语（S-077 ⑪）",
    },
    {
        "id": "piece.gate-again",
        "on": {"act": "go", "target": GATE, "refused": True},
        "played": ["piece.gate-taken", "piece.gate-turned-away", "piece.gate-promise"],
        "notPlayed": ["piece.gate-taken-again"],
        "once": True,
        "lines": [NOT_TWICE],
        "inferred": True,
        "note": "第 1 节第 6 步：已经被挡过一次，再走上去",
    },
    {
        "id": "piece.gate-turned-away",
        "on": {"act": "go", "target": GATE, "refused": True},
        "before": ["beat.04"],
        "once": True,
        "lines": [SPEAR, STAND_BACK],
        "inferred": True,
        "note": "梅洛斯被抓之前自己走到王城门口：同一个警吏、同两句（UX 10-10 确认）",
    },
    {
        "id": "piece.workshop-door-closed",
        "on": {"act": "move", "target": WORKSHOP},
        "before": ["beat.06"],
        "once": True,
        "lines": [{"narration": "戸は閉ざされている。中から、石を刻む音が聞こえる。戸の隙間から、灯がもれている。"}],
        "inferred": True,
        "note": "第 4 节：23:30（beat.06，セリヌンティウス被召进王城）以前走进工房的院子",
    },
    {
        "id": "piece.workshop-dark",
        "on": {"act": "move", "target": WORKSHOP},
        "after": ["beat.06"],
        "notPlayed": ["piece.workshop-knock-dark"],
        "once": True,
        "lines": [LIGHT_OUT],
        "inferred": True,
        "note": "第 4 节：23:30 以后",
    },
    {
        "id": "piece.workshop-knock",
        "on": {"act": "examine", "target": WORKSHOP_DOOR},
        "before": ["beat.06"],
        "once": True,
        "lines": [
            {"speaker": "char.selinuntius", "line": "もう遅い。用があるなら、明日にしてくれ。"},
            {"narration": "それきり、戸の向こうからは、石を刻む音しか聞こえなかった。"},
        ],
        "inferred": True,
        "note": "第 4 节：敲门、喊人、想进去。只有声音，人不出来（S-077 ⑩）",
    },
    {
        "id": "piece.workshop-knock-dark",
        "on": {"act": "examine", "target": WORKSHOP_DOOR},
        "after": ["beat.06"],
        "notPlayed": ["piece.workshop-dark"],
        "once": True,
        "lines": [LIGHT_OUT],
        "inferred": True,
        "note": "第 4 节：23:30 以后敲门（UX 10-10 确认）",
    },
    {
        "id": "piece.crowd-makes-way",
        "on": {"beat": "beat.24"},
        "knows": [{"character": "char.crowd", "fact": "fact.promise"}],
        "once": True,
        "lines": [
            {"speaker": "char.crowd", "line": "メロスだ！　メロスが帰って来た！"},
            {"narration": "人々が振り返り、道をあけた。"},
        ],
        "inferred": True,
        "note": "第 2 节：玩家把约定告诉了城里的人（learn 群众 fact.promise），梅洛斯赶到时群众里一个女人认出他",
    },
]
# 可调查物（契约 1.7 的 objects，2.12）：工房关着的屋门。按钮上的字 UX 10-10 定；位置点等前端在布局里加
SLICE_OBJECTS: list[dict[str, Any]] = [
    {
        "id": WORKSHOP_DOOR,
        "place": WORKSHOP,
        "spot": "workshop-door",
        "label": "戸を叩く",
        "inferred": True,
        "note": "第 4 节：院子里关着的屋门，里面传出凿石头的声音",
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

    # S-080 ④：城门、工房、群众让路的固定演出，和工房的屋门
    w["setPieces"] = copy.deepcopy(SLICE_SET_PIECES)
    w["objects"] = copy.deepcopy(SLICE_OBJECTS)

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
