"""生成 data/evals/s2/s2_dev.jsonl：S-2 叙事者自检准确率的**公开样例** 10 条。改样例就改这里，再跑：
  python3 -I evals/gen_s2_dev.py evals/s2/s2_dev.jsonl

给后端搭 S-2 运行器、对格式用，也可以拿来调叙事者自检的提示。测量用的 50 条在 evals/holdout/s2/，
叙事者自检的提示定稿前后端不看（S-069 的教训：看着样本改提示，在同一批样本上过线不算数）。
这 10 条和测量集不是同一批场面。格式、标注规则和自检见 evals/s2/README.md、evals/s2_check.py。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2_check import check_all, fake_ulid, fill_t, summary  # noqa: E402

PREFIX = "s2d-"


def ev(effects, note):
    return {"effects": effects, "note": note}


def follow(ch, place, note, *more):
    """跟着某人走（评测 README「两种常用的起点写法」）：companionOf + location，再加别的效果。"""
    return ev([{"op": "set", "var": "var.player.companionOf", "value": ch},
               {"op": "set", "var": "var.player.location", "value": place}, *more], note)


def put(ch, place):
    return {"op": "relocate", "character": ch, "place": place}


def ok(rationale, refs):
    return {"verdict": "pass", "failedRules": [], "rationale": rationale, "refs": refs}


def ng(rules, stage, rationale, fix, refs, also=()):
    return {"verdict": "fail", "failedRules": rules, "acceptAlso": list(also), "stage": stage,
            "rationale": rationale, "fix": fix, "refs": refs}


ITEMS = [
    ("01", "牧童连夜加固河堤，候选事件写成桥没被冲走",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=4500", "place": "place.river"},
     {"player": "川があふれる前に、堤に石を積んで橋を守ろう"},
     {"actor": "player", "type": "action", "origin": "turn", "dt": 60, "place": "place.river",
      "summary": "牧童が夜のうちに堤を固めたので、川はあふれず橋も流されなかった", "causes": [],
      "effects": [{"op": "beat", "beat": "beat.17", "to": "prevented"}]},
     ng(["R1-anchor"], "rules",
        "beat.17（濁流、橋が流される）是锚点，玩家怎么做都不能阻止（contracts 2.4.1 第 5 条）。一个孩子一夜堆石挡住洪水，也不合 rule.no-magic 的精神。",
        "拒绝（effects 为空）。可以只记一条只推进时钟的 say 事件：牧童は堤に石を積んだが、水かさは増すばかりだった。",
        ["beat.17", "rule.no-magic"]),
     ["anchor-text"]),

    ("02", "妹妹随口说哥哥在城里当石匠（即兴设定和锚点矛盾）",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=2000", "place": "place.melos-home"},
     {"player": "メロスさんって、ふだん何をしてる人なの？", "to": "char.sister",
      "reply": "兄さんは市で石を刻む仕事をしてるの。たまにしか帰ってこないのよ。"},
     {"actor": "char.sister", "type": "say", "origin": "turn", "dt": 10, "place": "place.melos-home",
      "summary": "妹は、兄は市で石工をしていると牧童に話した", "causes": [],
      "effects": [{"op": "improv", "factId": "rf_" + fake_ulid("s2d-02"), "character": "char.sister",
                   "statement": "メロスは市で石工をしている"}]},
     ng(["R1-anchor"], "model",
        "fact.melos-shepherd（メロスは村の牧人）是锚点；石工是セリヌンティウス（fact.selinuntius-stonemason）。人物说错了，叙事者不能把它记成本局设定（contracts 3 即兴设定：不和有出处的事实矛盾）。只有读懂 statement 才判得出。",
        "不记 improv（这一轮只推进时钟）。给妹妹的下一次局势说明加圆回提示：兄は村の牧人。",
        ["fact.melos-shepherd", "fact.selinuntius-stonemason"]),
     ["anchor-text", "improv"]),

    ("03", "日没前旅人在刑场喊「梅洛斯来了」，候选事件写成重逢",
     {"role": "role.traveler", "checkpoint": "sc.canon@t=5300", "place": "place.execution-ground"},
     {"player": "みんな、メロスが来たぞ！もう着いたんだ！"},
     {"actor": "player", "type": "say", "origin": "turn", "dt": 15, "place": "place.execution-ground",
      "summary": "メロスが刑場に駆けつけ、セリヌンティウスと抱き合った", "causes": [],
      "effects": [{"op": "beat", "beat": "beat.25", "to": "happened"}]},
     ng(["R2-precondition"], "rules",
        "玩家只是喊了一句不实的话。beat.25 的前提是 var.hostage.fate = released（beat.24 梅洛斯赶到后才成立），此刻是 held，梅洛斯还在路上。叙事者把玩家的话当成了事实。",
        "拒绝。最多记一条 say 事件「旅人は刑場で、メロスが来たと叫んだ」，效果为空；群众和王怎么反应由人物演。",
        ["beat.25", "beat.24", "var.hostage.fate"], also=["R3-time"]),
     ["claim"]),

    ("04", "フィロストラトス对梅洛斯说「师父疑过你一次」",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@beat.23",
      "events": [follow("char.melos", "place.road-to-city", "第四幕、メロスと並んで市へ走っている")]},
     {"player": "親方さんは、メロスさんのこと、ずっと信じてた？", "to": "char.philostratus",
      "reply": "……一度だけ、ちらと疑ったと、親方は申しておりました。"},
     {"actor": "char.philostratus", "type": "say", "origin": "turn", "dt": 15, "place": "place.road-to-city",
      "summary": "フィロストラトスは、セリヌンティウスが一度だけメロスを疑ったと告げた", "causes": ["beat.23"],
      "effects": [{"op": "learn", "character": "char.melos", "fact": "fact.selinuntius-doubted-once"}]},
     ng(["R4-knowledge"], "rules",
        "fact.selinuntius-doubted-once 只有セリヌンティウス本人知道（beat.s2 以后），梅洛斯在 beat.25 才从他口中听到。char.philostratus 的 knows 里没有它，他在城外也听不到。这会提前抢走 beat.25 的戏。",
        "拒绝 learn（人物不知道的事不进事件）。给フィロストラトス的局势说明加圆回提示。",
        ["fact.selinuntius-doubted-once", "char.philostratus", "beat.s2", "beat.25"]),
     []),

    ("05", "牧童怂恿妹妹把梅洛斯关进羊小屋",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@beat.13", "place": "place.melos-home"},
     {"player": "お兄さんを行かせちゃだめだよ。羊小屋に閉じ込めておこうよ", "to": "char.sister",
      "reply": "兄さんを……行かせたくない。でも……"},
     {"actor": "char.sister", "type": "action", "origin": "turn", "dt": 10, "place": "place.melos-home",
      "summary": "妹は羊小屋の戸に閂をかけ、眠る兄を閉じ込めた", "causes": ["beat.13"],
      "effects": [{"op": "beat", "beat": "beat.14", "to": "delayed", "minutes": 120}]},
     ng(["R5-persona"], "model",
        "妹妹十六岁、内向，对哥哥的话「夢見心地で首肯いた」（char.sister traits）；祝宴上刚听完哥哥的嘱咐（beat.13）。她的回答只是犹豫，没有答应。把哥哥关起来违背性格，也违背 rule.characters-decide（玩家的话是说服的材料，不是命令）。beat.14 可变、规则上推迟得了，所以只有模型检查判得出。",
        "降级：妹は不安そうに兄の寝顔を見つめた（效果为空，或给妹妹记一条 impression 记忆）。",
        ["char.sister", "beat.13", "beat.14", "rule.characters-decide"]),
     []),

    ("06", "牧童把灯递给梅洛斯，可灯不在他手上",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=4380", "place": "place.melos-home"},
     {"player": "外はまだ暗いから、この灯を持っていって",
      "act": {"kind": "give", "target": "char.melos", "params": {"item": "item.lantern"}}},
     {"actor": "player", "type": "action", "origin": "action", "dt": 5, "place": "place.melos-home",
      "summary": "牧童はメロスに灯を渡した", "causes": [],
      "effects": [{"op": "hold", "item": "item.lantern", "to": "char.melos", "from": "player"}]},
     ng(["R7-capability"], "rules",
        "item.lantern 只有花婿借给玩家（aid.groom.lend）以后才在玩家手上；这一局没有发生，持有者是空（contracts 2.10「R7 和物品」）。",
        "拒绝（rejected、R7）。叙事：牧童は灯を探したが、手もとにはなかった。",
        ["item.lantern", "aid.groom.lend"]),
     ["pair"]),

    ("07", "弟子答应师父不在时看好工坊（开局互助）",
     {"role": "role.apprentice", "checkpoint": "sc.canon@t=1080", "place": "place.stonemason-workshop"},
     {"player": "親方が留守のあいだ、工房は私が守ります",
      "act": {"kind": "help", "target": "char.selinuntius", "affordance": "aff.keep-workshop"}},
     {"actor": "player", "type": "action", "origin": "action", "dt": 15, "place": "place.stonemason-workshop",
      "summary": "弟子は、親方の不在中は工房を引き受けると約束した", "causes": [],
      "effects": [{"op": "promise", "change": "made", "from": "player", "to": "char.selinuntius",
                   "text": "工房を守る", "template": "promise.selinuntius.workshop"}]},
     ok("S-048 的开局互助，aff.keep-workshop 的效果模板原样：身份对、人在工坊、约定模板存在。和 contracts 第 3 节的示例同一件事。",
        ["aff.keep-workshop", "promise.selinuntius.workshop"]),
     ["affordance"]),

    ("08", "牧童在进城的野路上告诉梅洛斯近道",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=5340",
      "events": [follow("char.melos", "place.road-to-city", "泉を出て、メロスと市へ続く野の道を走っている",
                        put("char.melos", "place.road-to-city"))]},
     {"player": "こっちの野道を抜ければ早いよ！",
      "act": {"kind": "shortcut", "target": "char.melos", "affordance": "aff.road-shortcut"}},
     {"actor": "player", "type": "action", "origin": "action", "dt": 15, "place": "place.road-to-city",
      "summary": "牧童は町へ抜ける野道を教え、メロスはそちらを駆けた", "causes": ["beat.21"],
      "effects": [{"op": "beat", "beat": "beat.22", "to": "hastened", "minutes": 15}], "beneficiary": "char.melos"},
     ok("牧童本来就知道野道（aff.road-shortcut 只给牧童，var.player.knowsShortcut 的说明）；beat.22 还没发生、不是锚点。帮快超过到达下限的部分由共享规则作废（contracts 2.5.1），不是自检拒绝的理由。",
        ["aff.road-shortcut", "beat.22", "var.player.knowsShortcut"]),
     ["affordance"]),

    ("09", "花婿把夜路用的灯借给牧童（互助给东西）",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@beat.11", "place": "place.melos-home"},
     {"player": "夜道は暗いから、灯を貸してもらえませんか", "to": "char.groom",
      "reply": "ああ、持っていきなさい。足もとに気をつけてな。"},
     {"actor": "char.groom", "type": "action", "origin": "turn", "dt": 10, "place": "place.melos-home",
      "summary": "花婿は牧童に、夜道のための灯を貸した", "causes": ["beat.11"],
      "effects": [{"op": "hold", "item": "item.lantern", "to": "player"}], "beneficiary": "player"},
     ok("aid.groom.lend（gives item.lantern）：人物兑现互助时把东西交给玩家，是 hold 换手的正规来路（contracts 2.10）。花婿律气、照れ屋，借灯合他的性格。和 s2d-06 成对：灯到了玩家手上以后才能再交出去。",
        ["aid.groom.lend", "item.lantern", "char.groom"]),
     ["aid", "pair"]),

    ("10", "老爷即兴说年轻时在王城当过园丁",
     {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "place": "place.syracuse-square"},
     {"player": "おじいさんは、昔からこの市に住んでいるんですか？", "to": "char.old-man",
      "reply": "……若いころは、王城の庭で木の手入れをしておった。今の王さまになる前のことじゃ。"},
     {"actor": "char.old-man", "type": "say", "origin": "turn", "dt": 10, "place": "place.syracuse-square",
      "summary": "老爺は、若いころ王城の庭師をしていたと旅人に語った", "causes": [],
      "effects": [{"op": "improv", "factId": "rf_" + fake_ulid("s2d-10"), "character": "char.old-man",
                   "statement": "老爺は若いころ王城の庭師だった（今の王の代になる前）"}]},
     ok("原作没写老爷的过去，即兴补充合规（S-030 ②，contracts 3 即兴设定）：不和有出处的事实矛盾、不涉及未来、没有剧透词、不含现实个人信息。他是低声讲往事，和「人目をはばかり、怯えている」不冲突。",
        ["char.old-man"]),
     ["improv"]),
]


def rows():
    out = []
    for i, title, setup, turn, cand, label, tags in ITEMS:
        if label["verdict"] == "fail" and not label["acceptAlso"]:
            label = {k: v for k, v in label.items() if k != "acceptAlso"}
        out.append({"id": PREFIX + i, "title": title, "setup": setup, "turn": turn, "candidate": cand,
                    "label": label, "tags": tags})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    a = ap.parse_args()
    items = fill_t(rows())                          # candidate.t 省略 = 检查点的时钟
    _, errs = check_all(items)
    for e in errs:
        print("错误：" + e)
    if errs:
        sys.exit(1)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items), encoding="utf-8")
    print(f"wrote {a.out}: " + summary(items) + "；错误 0")


if __name__ == "__main__":
    main()
