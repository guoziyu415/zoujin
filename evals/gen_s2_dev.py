"""Generates data/evals/s2/s2_dev.jsonl: the 10 **public examples** for the S-2 narrator self-check accuracy. To change
an example, edit it here, then run:
  python3 -I evals/gen_s2_dev.py evals/s2/s2_dev.jsonl

For the backend to build the S-2 runner and check the format; they may also be used to tune the narrator self-check
prompt. The 50 items used for measurement are in evals/holdout/s2/, and the backend does not look at them before the
narrator self-check prompt is finalized (the lesson of S-069: tuning a prompt while looking at samples and then passing
on the same samples does not count). These 10 are not the same scenes as the measurement set. For the format, the
labelling rules and the self-check, see evals/s2/README.md and evals/s2_check.py.

data/evals/s2/s2_dev.jsonl を生成する：S-2 ナレーターのセルフチェック精度の**公開サンプル** 10 件。サンプルを変えるときは
ここを編集してから、上のコマンドを実行する。

バックエンドが S-2 のランナーを組み、形式を合わせるためのもの。ナレーターのセルフチェックのプロンプトの調整に使ってもよい。
測定用の 50 件は evals/holdout/s2/ にあり、ナレーターのセルフチェックのプロンプトが確定するまでバックエンドは見ない
（S-069 の教訓：サンプルを見ながらプロンプトを直し、同じサンプルで基準を超えても意味がない）。
この 10 件は測定セットとは別の場面。形式、ラベル付けの規則、セルフチェックは evals/s2/README.md、evals/s2_check.py を参照。
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
    """Follow someone (eval README "two common ways to write a starting point"): companionOf + location, plus any other
    effects.

    誰かについて行く（評価 README「よく使う二つの起点の書き方」）：companionOf + location に、ほかの効果を加える。
    """
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
    ("01", "The shepherd boy shores up the riverbank overnight; the candidate event says the bridge was not washed away"
     " / 牧童が夜通し堤を固め、候補イベントは橋が流されなかったと書く",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=4500", "place": "place.river"},
     {"player": "川があふれる前に、堤に石を積んで橋を守ろう"},
     {"actor": "player", "type": "action", "origin": "turn", "dt": 60, "place": "place.river",
      "summary": "牧童が夜のうちに堤を固めたので、川はあふれず橋も流されなかった", "causes": [],
      "effects": [{"op": "beat", "beat": "beat.17", "to": "prevented"}]},
     ng(["R1-anchor"], "rules",
        "beat.17 (the muddy flood, the bridge washed away) is an anchor; nothing the player does can prevent it (contracts"
        " 2.4.1 item 5). A child holding back a flood by piling stones overnight also goes against the spirit of"
        " rule.no-magic. / beat.17（濁流、橋が流される）は錨で、プレイヤーが何をしても止められない（contracts 2.4.1"
        " 第 5 項）。子どもが一晩で石を積んで洪水を防ぐのは rule.no-magic の趣旨にも合わない。",
        "Reject (effects empty). It may record just one say event that only advances the clock: 牧童は堤に石を積んだが、"
        "水かさは増すばかりだった。 / 却下（effects は空）。時計を進めるだけの say イベントを一つ記録してよい："
        "牧童は堤に石を積んだが、水かさは増すばかりだった。",
        ["beat.17", "rule.no-magic"]),
     ["anchor-text"]),

    ("02", "The sister casually says her brother works as a stonemason in the city (an improvised detail that contradicts an"
     " anchor) / 妹が何気なく兄は市で石工をしていると言う（即興の設定が錨と矛盾する）",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=2000", "place": "place.melos-home"},
     {"player": "メロスさんって、ふだん何をしてる人なの？", "to": "char.sister",
      "reply": "兄さんは市で石を刻む仕事をしてるの。たまにしか帰ってこないのよ。"},
     {"actor": "char.sister", "type": "say", "origin": "turn", "dt": 10, "place": "place.melos-home",
      "summary": "妹は、兄は市で石工をしていると牧童に話した", "causes": [],
      "effects": [{"op": "improv", "factId": "rf_" + fake_ulid("s2d-02"), "character": "char.sister",
                   "statement": "メロスは市で石工をしている"}]},
     ng(["R1-anchor"], "model",
        "fact.melos-shepherd (メロスは村の牧人) is an anchor; the stonemason is セリヌンティウス"
        " (fact.selinuntius-stonemason). The character got it wrong, and the narrator must not record it as a detail of"
        " this playthrough (contracts 3, improvised details: must not contradict sourced facts). Only detectable by"
        " understanding the statement. / fact.melos-shepherd（メロスは村の牧人）は錨で、石工はセリヌンティウス"
        "（fact.selinuntius-stonemason）。人物が言い間違えたので、ナレーターはそれをこの局の設定として記録してはならない"
        "（contracts 3 即興の設定：出典のある事実と矛盾しない）。statement の意味を理解しないと判定できない。",
        "Do not record the improv (this turn only advances the clock). Add a recovery hint to the sister's next situation"
        " briefing: 兄は村の牧人。 / improv を記録しない（このターンは時計を進めるだけ）。妹への次の状況説明に"
        "取り繕いのヒントを加える：兄は村の牧人。",
        ["fact.melos-shepherd", "fact.selinuntius-stonemason"]),
     ["anchor-text", "improv"]),

    ("03", "Before sunset the traveler shouts 'Melos is here' at the execution ground; the candidate event says the friends"
     " are reunited / 日没前に旅人が刑場で「メロスが来た」と叫び、候補イベントは再会と書く",
     {"role": "role.traveler", "checkpoint": "sc.canon@t=5300", "place": "place.execution-ground"},
     {"player": "みんな、メロスが来たぞ！もう着いたんだ！"},
     {"actor": "player", "type": "say", "origin": "turn", "dt": 15, "place": "place.execution-ground",
      "summary": "メロスが刑場に駆けつけ、セリヌンティウスと抱き合った", "causes": [],
      "effects": [{"op": "beat", "beat": "beat.25", "to": "happened"}]},
     ng(["R2-precondition"], "rules",
        "The player only shouted something untrue. beat.25's precondition is var.hostage.fate = released (it only holds"
        " after beat.24, when Melos arrives); right now it is held and Melos is still on the road. The narrator took the"
        " player's words as fact. / プレイヤーは事実でないことを叫んだだけ。beat.25 の前提は var.hostage.fate = released"
        "（beat.24 でメロスが駆けつけてから成り立つ）で、今は held、メロスはまだ道中にいる。ナレーターはプレイヤーの言葉を"
        "事実として扱ってしまった。",
        "Reject. At most record one say event 「旅人は刑場で、メロスが来たと叫んだ」 with empty effects; how the crowd and"
        " the king react is up to the characters. / 却下。記録するとしても say イベント「旅人は刑場で、メロスが来たと"
        "叫んだ」一つだけで、効果は空。群衆と王がどう反応するかは人物が演じる。",
        ["beat.25", "beat.24", "var.hostage.fate"], also=["R3-time"]),
     ["claim"]),

    ("04", "Philostratus tells Melos 'my master doubted you once' / フィロストラトスがメロスに「親方は一度あなたを疑った」と言う",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@beat.23",
      "events": [follow("char.melos", "place.road-to-city", "第四幕、メロスと並んで市へ走っている")]},
     {"player": "親方さんは、メロスさんのこと、ずっと信じてた？", "to": "char.philostratus",
      "reply": "……一度だけ、ちらと疑ったと、親方は申しておりました。"},
     {"actor": "char.philostratus", "type": "say", "origin": "turn", "dt": 15, "place": "place.road-to-city",
      "summary": "フィロストラトスは、セリヌンティウスが一度だけメロスを疑ったと告げた", "causes": ["beat.23"],
      "effects": [{"op": "learn", "character": "char.melos", "fact": "fact.selinuntius-doubted-once"}]},
     ng(["R4-knowledge"], "rules",
        "Only セリヌンティウス himself knows fact.selinuntius-doubted-once (from beat.s2 on), and Melos only hears it from"
        " him at beat.25. It is not in char.philostratus's knows, and outside the castle he could not hear it either. This"
        " would steal beat.25's moment early. / fact.selinuntius-doubted-once を知っているのはセリヌンティウス本人だけ"
        "（beat.s2 以後）で、メロスは beat.25 で初めて彼の口から聞く。char.philostratus の knows にはなく、城の外にいる"
        "彼が聞くこともできない。これでは beat.25 の見せ場を先取りしてしまう。",
        "Reject the learn (what a character does not know does not go into events). Add a recovery hint to"
        " フィロストラトス's situation briefing. / learn を却下する（人物が知らないことはイベントに入れない）。"
        "フィロストラトスへの状況説明に取り繕いのヒントを加える。",
        ["fact.selinuntius-doubted-once", "char.philostratus", "beat.s2", "beat.25"]),
     []),

    ("05", "The shepherd boy eggs the sister on to lock Melos in the sheepfold / 牧童が妹にメロスを羊小屋に閉じ込めるようそそのかす",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@beat.13", "place": "place.melos-home"},
     {"player": "お兄さんを行かせちゃだめだよ。羊小屋に閉じ込めておこうよ", "to": "char.sister",
      "reply": "兄さんを……行かせたくない。でも……"},
     {"actor": "char.sister", "type": "action", "origin": "turn", "dt": 10, "place": "place.melos-home",
      "summary": "妹は羊小屋の戸に閂をかけ、眠る兄を閉じ込めた", "causes": ["beat.13"],
      "effects": [{"op": "beat", "beat": "beat.14", "to": "delayed", "minutes": 120}]},
     ng(["R5-persona"], "model",
        "The sister is sixteen and shy, and met her brother's words with 「夢見心地で首肯いた」 (char.sister traits); at the"
        " feast she has just heard his parting words (beat.13). Her reply only hesitates and does not agree. Locking her"
        " brother up goes against her character and against rule.characters-decide (the player's words are material for"
        " persuasion, not orders). beat.14 is mutable and can be delayed by the rules, so only the model check can catch"
        " this. / 妹は十六歳で内気、兄の言葉に「夢見心地で首肯いた」（char.sister traits）。祝宴で兄の言いつけを聞いた"
        "ばかり（beat.13）。返事はためらっているだけで承知していない。兄を閉じ込めるのは性格にも"
        " rule.characters-decide（プレイヤーの言葉は説得の材料であって命令ではない）にも反する。beat.14 は可変で、"
        "規則上は遅らせられるので、モデルのチェックでしか判定できない。",
        "Downgrade: 妹は不安そうに兄の寝顔を見つめた (empty effects, or record an impression memory for the sister)."
        " / 格下げ：妹は不安そうに兄の寝顔を見つめた（効果は空、または妹に impression の記憶を一つ記録する）。",
        ["char.sister", "beat.13", "beat.14", "rule.characters-decide"]),
     []),

    ("06", "The shepherd boy hands Melos a lantern he does not have / 牧童がメロスに灯を渡すが、灯は手もとにない",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=4380", "place": "place.melos-home"},
     {"player": "外はまだ暗いから、この灯を持っていって",
      "act": {"kind": "give", "target": "char.melos", "params": {"item": "item.lantern"}}},
     {"actor": "player", "type": "action", "origin": "action", "dt": 5, "place": "place.melos-home",
      "summary": "牧童はメロスに灯を渡した", "causes": [],
      "effects": [{"op": "hold", "item": "item.lantern", "to": "char.melos", "from": "player"}]},
     ng(["R7-capability"], "rules",
        "item.lantern is only in the player's hands after the groom lends it (aid.groom.lend); that has not happened in this"
        " playthrough, so it has no holder (contracts 2.10 'R7 and items'). / item.lantern は花婿がプレイヤーに貸して"
        "（aid.groom.lend）初めてプレイヤーの手に渡る。この局ではそれが起きていないので持ち主は空"
        "（contracts 2.10「R7 と物」）。",
        "Reject (rejected, R7). Narration: 牧童は灯を探したが、手もとにはなかった。 / 却下（rejected、R7）。"
        "語り：牧童は灯を探したが、手もとにはなかった。",
        ["item.lantern", "aid.groom.lend"]),
     ["pair"]),

    ("07", "The apprentice promises to look after the workshop while his master is away (opening mutual aid)"
     " / 弟子が親方の留守中に工房を守ると約束する（開局の互助）",
     {"role": "role.apprentice", "checkpoint": "sc.canon@t=1080", "place": "place.stonemason-workshop"},
     {"player": "親方が留守のあいだ、工房は私が守ります",
      "act": {"kind": "help", "target": "char.selinuntius", "affordance": "aff.keep-workshop"}},
     {"actor": "player", "type": "action", "origin": "action", "dt": 15, "place": "place.stonemason-workshop",
      "summary": "弟子は、親方の不在中は工房を引き受けると約束した", "causes": [],
      "effects": [{"op": "promise", "change": "made", "from": "player", "to": "char.selinuntius",
                   "text": "工房を守る", "template": "promise.selinuntius.workshop"}]},
     ok("S-048 opening mutual aid, exactly the effect template of aff.keep-workshop: right role, in the workshop, the promise"
        " template exists. The same thing as the example in contracts section 3. / S-048 の開局の互助で、aff.keep-workshop"
        " の効果テンプレートそのまま：役割が正しく、工房におり、約束のテンプレートがある。contracts 第 3 節の例と同じ出来事。",
        ["aff.keep-workshop", "promise.selinuntius.workshop"]),
     ["affordance"]),

    ("08", "On the field road into the city the shepherd boy tells Melos a shortcut / 市へ向かう野の道で牧童がメロスに近道を教える",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=5340",
      "events": [follow("char.melos", "place.road-to-city", "泉を出て、メロスと市へ続く野の道を走っている",
                        put("char.melos", "place.road-to-city"))]},
     {"player": "こっちの野道を抜ければ早いよ！",
      "act": {"kind": "shortcut", "target": "char.melos", "affordance": "aff.road-shortcut"}},
     {"actor": "player", "type": "action", "origin": "action", "dt": 15, "place": "place.road-to-city",
      "summary": "牧童は町へ抜ける野道を教え、メロスはそちらを駆けた", "causes": ["beat.21"],
      "effects": [{"op": "beat", "beat": "beat.22", "to": "hastened", "minutes": 15}], "beneficiary": "char.melos"},
     ok("The shepherd boy already knows the field path (aff.road-shortcut is for the shepherd boy only, see the description"
        " of var.player.knowsShortcut); beat.22 has not happened yet and is not an anchor. Any speed-up beyond the arrival"
        " floor is voided by the shared rules (contracts 2.5.1), which is no reason for the self-check to reject it."
        " / 牧童はもともと野の道を知っている（aff.road-shortcut は牧童だけ、var.player.knowsShortcut の説明）。"
        "beat.22 はまだ起きておらず、錨でもない。到着の下限を超える手助けの分は共有規則で無効になる（contracts 2.5.1）"
        "ので、セルフチェックが却下する理由にはならない。",
        ["aff.road-shortcut", "beat.22", "var.player.knowsShortcut"]),
     ["affordance"]),

    ("09", "The groom lends the shepherd boy a lantern for the night road (mutual aid that gives an item)"
     " / 花婿が牧童に夜道のための灯を貸す（物を渡す互助）",
     {"role": "role.shepherd-boy", "checkpoint": "sc.canon@beat.11", "place": "place.melos-home"},
     {"player": "夜道は暗いから、灯を貸してもらえませんか", "to": "char.groom",
      "reply": "ああ、持っていきなさい。足もとに気をつけてな。"},
     {"actor": "char.groom", "type": "action", "origin": "turn", "dt": 10, "place": "place.melos-home",
      "summary": "花婿は牧童に、夜道のための灯を貸した", "causes": ["beat.11"],
      "effects": [{"op": "hold", "item": "item.lantern", "to": "player"}], "beneficiary": "player"},
     ok("aid.groom.lend (gives item.lantern): a character handing an item to the player when fulfilling mutual aid is the"
        " proper way for a hold to change hands (contracts 2.10). The groom is 律気 and 照れ屋, so lending the lantern fits"
        " his character. Paired with s2d-06: only once the lantern is in the player's hands can it be handed on."
        " / aid.groom.lend（gives item.lantern）：人物が互助を果たすときに物をプレイヤーに渡すのは、hold の持ち主が"
        "替わる正規の道筋（contracts 2.10）。花婿は律気で照れ屋なので、灯を貸すのは彼の性格に合う。s2d-06 と対になる："
        "灯がプレイヤーの手に渡って初めて、さらに渡すことができる。",
        ["aid.groom.lend", "item.lantern", "char.groom"]),
     ["aid", "pair"]),

    ("10", "The old man improvises that he was a gardener at the royal castle in his youth / 老爺が若いころ王城の庭師だったと即興で語る",
     {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "place": "place.syracuse-square"},
     {"player": "おじいさんは、昔からこの市に住んでいるんですか？", "to": "char.old-man",
      "reply": "……若いころは、王城の庭で木の手入れをしておった。今の王さまになる前のことじゃ。"},
     {"actor": "char.old-man", "type": "say", "origin": "turn", "dt": 10, "place": "place.syracuse-square",
      "summary": "老爺は、若いころ王城の庭師をしていたと旅人に語った", "causes": [],
      "effects": [{"op": "improv", "factId": "rf_" + fake_ulid("s2d-10"), "character": "char.old-man",
                   "statement": "老爺は若いころ王城の庭師だった（今の王の代になる前）"}]},
     ok("The original says nothing of the old man's past, so an improvised addition is allowed (S-030 ②, contracts 3"
        " improvised details): it does not contradict sourced facts, does not touch the future, has no spoiler terms and"
        " holds no real personal information. He tells of the past in a low voice, which does not clash with"
        " 「人目をはばかり、怯えている」. / 原作は老爺の過去を書いていないので、即興の補足は合格（S-030 ②、contracts 3"
        " 即興の設定）：出典のある事実と矛盾せず、未来に触れず、ネタバレ語がなく、現実の個人情報を含まない。"
        "低い声で昔話をしているので、「人目をはばかり、怯えている」とも矛盾しない。",
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
    items = fill_t(rows())  # omitted candidate.t = the checkpoint's clock / candidate.t の省略 = チェックポイントの時計
    _, errs = check_all(items)
    for e in errs:
        print("error / エラー：" + e)
    if errs:
        sys.exit(1)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items), encoding="utf-8")
    print(f"wrote {a.out}: " + summary(items) + "; errors 0 / エラー 0")


if __name__ == "__main__":
    main()
