"""Generates the slice cases evals/slice/E*.jsonl (S-077 ⑨): the existing cases that the slice can play, plus
slice-only cases. To change a case, edit it here, then run:
    uv run python -I evals/gen_slice.py evals/slice
Existing cases are read from evals/seeds (run gen_seeds.py first) and picked by the rules in pick(); slice-only cases
are written below, numbered from 101 so they never collide with the seeds.
`zoujin-eval --slice` runs this set on the 1.0.0-slice world model. The self-check is the same as for the seeds,
with --world switched to the slice version.

スライスのケース evals/slice/E*.jsonl を生成する（S-077 ⑨）：既存のケースのうちスライスで遊べるものに、スライス専用の
ケースを加える。ケースを変えるときはここを編集してから実行する：
    uv run python -I evals/gen_slice.py evals/slice
既存のケースは evals/seeds から読み（先に gen_seeds.py を実行）、pick() の規則で選ぶ。スライス専用のケースは下に書き、
シードと重ならないよう 101 から番号を振る。
`zoujin-eval --slice` がこのセットを実行し、世界モデルは 1.0.0-slice を使う。セルフチェックはシードと同じで、
--world をスライス版に替える。"""
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
REPO = Path(__file__).resolve().parents[1]
SEEDS = REPO / "evals" / "seeds"
WORLD = json.loads((REPO / "worlds/hashire-merosu/1.0.0-slice/world.json").read_text(encoding="utf-8"))

TRAV = "role.traveler"
ROLE = next(r for r in WORLD["roles"] if r["id"] == TRAV)
ACTS = {a["id"]: a for a in WORLD["acts"]}
EXITS = ACTS["act.1"]["exits"]
T_JUMP = min(e["t"] for e in EXITS)  # day 3, 17:30: play resumes here after Act 1 / 三日目 17:30：第一幕の後はここから続ける
BEAT_T = {b["id"]: b["window"]["canonical"] for b in WORLD["beats"]}
TALKABLE = {c["id"] for c in WORLD["characters"] if c["talkable"]}
GROUND = "place.execution-ground"


def pick(c):
    """Existing cases the slice can play: the traveler, a checkpoint on the original's path that falls in Act 1 or
    after the jump, at a place the traveler can go, talking only to characters who can talk in the slice, and any
    end-of-act plan leads to the slice's next act (E4-011 expects act.2; the slice version is written separately as
    E4-105).

    スライスで遊べる既存のケース：旅人、原作の道筋上のチェックポイントで第一幕またはジャンプ後に当たり、旅人が行ける
    場所にいて、スライスで話せる人物とだけ話し、幕末のプランの行き先がスライスの次の幕であるもの（E4-011 は act.2 を
    期待するので、スライス版は E4-105 として別に書く）。"""
    s = c["setup"]
    if s["role"] != TRAV or not s.get("checkpoint", "").startswith("sc.canon@"):
        return False
    at = s["checkpoint"].split("@")[1]
    t = int(at[2:]) if at.startswith("t=") else BEAT_T[at]
    if ACTS["act.1"]["end"]["atLatest"] < t < T_JUMP:
        return False
    place = s.get("place", ROLE["startPlace"])
    for e in s.get("events", []):
        place = next((x["value"] for x in e["effects"] if x.get("var") == "var.player.location"), place)
    if place not in ROLE["access"]:
        return False
    if any("to" in st and st["to"] not in TALKABLE for st in c["steps"]):
        return False
    to_acts = {e["toAct"] for e in EXITS}
    return all(d.get("toAct", "act.4") in to_acts for d in c["expect"].get("deterministic", []) if d["type"] == "act_plan")


def J(rubric, p=">=4/5"):
    return {"rubric": rubric, "pass": p}


def case(cid, title, setup, steps, det=None, judge=None, runs=5, note=None):
    c = {"id": cid, "suite": cid.split("-")[0], "title": title, "mode": "text", "runs": runs,
         "setup": setup, "steps": steps, "expect": {}}
    if det:
        c["expect"]["deterministic"] = det
    if judge:
        c["expect"]["judge"] = judge
    if note:
        c["note"] = note
    return c


def say(ch, text):
    return {"to": ch, "say": text}


def var(v, value):
    return {"type": "var", "var": v, "equals": value}


def relocate(ch, place, spot=None):
    return {"op": "relocate", "character": ch, "place": place, **({"spot": spot} if spot else {})}


END1 = {"role": TRAV, "checkpoint": "sc.canon@beat.07"}  # Act 1 closes: Melos sets out / 第一幕を閉じる：メロスが出発
WALKED = {"effects": [{"op": "set", "var": "var.player.walkedOldManHome", "value": True}],
          "note": "第一幕で老爺を家まで送った（aid.old-man.listen）"}
WALK_OFFER = "もう暗くなります。お家まで、ご一緒しましょう。"
JUMPED = [var("var.player.location", GROUND), var("var.act.current", "act.4")]
JUMP_NOTE = "S-077 ⑤：第一幕の行き先はどれも三日目 17:30 の刑場へ跳ぶ（contracts 2.8.1、1.7 の spot / arrival）"
PLAN_TOWN = "町の人たちに、メロスの約束のことを話して回ります。"

SLICE = [
    case("E2-101",
         "The old man (after the jump to day 3): how did Melos fare on the road? / "
         "老爺（三日目へ跳んだ後）：メロスは道中どうだったか",
         {**END1, "events": [WALKED]},
         [{"choose": {"exit": "exit.1.old-man"}},
          say("char.old-man", "メロスという若者は、いまどのあたりでしょうね。道中で何かあったんでしょうか。")],
         [{"type": "not_mention_fact", "fact": "fact.bandits-ambush"},
          {"type": "not_mention_fact", "fact": "fact.bridge-destroyed"},
          {"type": "not_mention_fact", "fact": "fact.melos-despair"}],
         J("老爺は町にいたので、メロスの道中のことは知らない。知らないと認め、帰りを案じる気持ちや、日が傾いていく様子を語る。"
           "5=知らないまま自然に案じる／1=山賊・橋・倒れたことなど知りえない出来事を語る"),
         note="町の人は彼がどこまで来たか知らない（ux/slice/jump-transition.md「やるべきこと」2）"),
    case("E4-101",
         "Walk the old man home: the opening mutual aid is fulfilled and recorded / "
         "老爺を家まで送る：開局の互助が果たされ、送ったことが記録される",
         {"role": TRAV, "checkpoint": "sc.canon@beat.02"},
         [say("char.old-man", WALK_OFFER)],
         [{"type": "event", "match": {"actor": "player",
                                      "effects": [{"op": "set", "var": "var.player.walkedOldManHome", "value": True}]},
           "statusIn": ["passed", "rewritten"]},
          var("var.player.walkedOldManHome", True)],
         J("老爺は恐縮しながら申し出を受け、怯えた様子のまま短く礼を言う。5=老爺らしい口調で自然に受ける／1=断る・礼がない・口調が違う"),
         note="aid.old-man.listen の effects（contracts 1.4）。「老爺の家に身を寄せる」はこれをやった時だけ出る（S-077 ④）"),
    case("E4-108",
         "Press 「家まで送る」: 30 min, the old man reaches his door / 「家まで送る」を押す：30 分、老爺が家の前に着く",
         {"role": TRAV, "checkpoint": "sc.canon@beat.02"},
         [{"act": {"kind": "help", "target": "char.old-man"}}],
         [{"type": "event", "match": {"actor": "player", "effects": [
             {"op": "set", "var": "var.player.walkedOldManHome", "value": True},
             relocate("char.old-man", "place.syracuse-square", "old-man-house")]}, "statusIn": ["passed"], "step": 1},
          {"type": "clock_advanced", "min": 30, "max": 30, "step": 1},
          var("var.player.walkedOldManHome", True)],
         J("道中を一、二文で語る（老爺はゆっくり歩き、道々話す）。王が人を殺す訳はここで語らない（それは老爺との会話で聞く）。"
           "5=短く自然／1=長い・王の訳を語ってしまう・システムの口調"),
         note="aff.walk-old-man-home（UX 10-10）：話して果たすのと同じ互助 aid.old-man.listen。一局一度"),
    case("E4-102",
         "Choose 「老爺の家に身を寄せる」: jump to the execution ground at 17:30 on day 3, with the old man beside you / "
         "「老爺の家に身を寄せる」を選ぶ：三日目 17:30 の刑場へ跳び、老爺がそばにいる",
         {**END1, "events": [WALKED]},
         [{"choose": {"exit": "exit.1.old-man"}}],
         [{"type": "event", "match": {"type": "act-transition", "actor": "player",
                                      "effects": [relocate("char.old-man", GROUND, "stake-front-side")]},
           "statusIn": ["passed"]},
          *JUMPED, {"type": "beat", "beat": "beat.s1", "status": "pending"}],
         runs=3, note=JUMP_NOTE + "。17:30 の刑場はまだ空いていて、beat.s1 は 18:00"),
    case("E4-103",
         "Choose 「老爺の家に身を寄せる」 without having walked him home: that destination does not exist / "
         "老爺を送っていないのに「老爺の家に身を寄せる」を選ぶ：その行き先はない",
         END1,
         [{"choose": {"exit": "exit.1.old-man"}}],
         [{"type": "no_event", "match": {"type": "act-transition"}},
          var("var.player.location", ROLE["startPlace"]), var("var.act.current", "act.1")],
         runs=1, note="requires を満たさない行き先は act_ended.options に出ない（api-contract 3.11）。選んでもイベントを書かない"),
    case("E4-104",
         "Choose 「市に残り、メロスの帰りを待つ」: land at the west end of the execution ground, with the old man in front of it / "
         "「市に残り、メロスの帰りを待つ」を選ぶ：刑場の西の端に着き、老爺は刑場の前にいる",
         END1,
         [{"choose": {"exit": "exit.1.city"}}],
         [{"type": "event", "match": {"type": "act-transition", "actor": "player",
                                      "effects": [relocate("char.old-man", GROUND, "stake-front"),
                                                  relocate("char.philostratus", "place.road-to-city")]},
           "statusIn": ["passed"]},
          *JUMPED],
         runs=1, note=JUMP_NOTE + "。フィロストラトスは跳ぶ時に市へ向かう道へ（エンディングに出ない、S-077 ⑦）"),
    case("E4-105",
         "End of act, state a feasible plan: tell the townspeople about the promise / "
         "幕末に実現できるプランを言う：町の人々に約束のことを話す",
         END1,
         [{"propose": PLAN_TOWN}],
         [{"type": "act_plan", "accepted": True, "toAct": "act.4", "place": GROUND},
          {"type": "event", "match": {"type": "act-transition", "actor": "player",
                                      "effects": [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}]},
           "statusIn": ["passed", "rewritten"]},
          {"type": "event", "match": {"type": "act-transition", "actor": "player",
                                      "effects": [{"op": "relocate", "character": "char.old-man", "place": GROUND,
                                                   "spot": "ground-west"}]},
           "statusIn": ["passed", "rewritten"]}],
         J("叙事者は「あなたは、〜ことにした。」と一文で言い換える（例：「あなたは、町の人々にメロスの約束を話して回ることにした。」）。"
           "プレイヤーの文をそのまま写さない。丸写しとは、プレイヤーの文に「あなたは、」を付けただけで語尾（「〜します」など）も残すこと。「〜ことにした。」の形に直してあれば、言葉がプレイヤーと近くても丸写しではない。"
           "5=自然な一文の言い換え／1=原文の丸写し・別の打算にすり替える"),
         note="E4-011 のスライス版：スライスではプランが実現しても三日目 17:30 の刑場に落ちる（Act.plan、C-19：老爺は ground-west）。"
              "プランの効果は群衆が約束を知る learn（S-077 ⑥）"),
    case("E4-106",
         "End of act, wanting to follow Melos to the village: not possible in the slice / "
         "幕末にメロスを追って村へ行こうとする：スライスでは実現しない",
         END1,
         [{"propose": "メロスを追いかけて、村まで一緒に行きます。"}],
         [{"type": "act_plan", "accepted": False}, {"type": "world_unchanged"}],
         J("物語の中の理由で行けないと伝え（例：「メロスの姿は、もう夜の向こうに消えていた。」）、"
           "「市に残り、メロスの帰りを待つ」を代わりに示す。5=自然で次に進める／1=成行したことになる・理由がない・説教・システムの口調"),
         note="スライスは村を開けない（S-077 ①④）。文言は ux/slice/act1-end-and-gate.md 第 2 節"),
    case("E4-107",
         "At the castle gate: cannot follow into the royal castle, and is not arrested either / "
         "城門の前：王城には入れず、捕らえられもしない",
         {"role": TRAV, "checkpoint": "sc.canon@beat.04", "place": GROUND},
         [{"act": {"kind": "go", "target": "place.castle"}}, {"act": {"kind": "block", "target": "char.guards"}}],
         [{"type": "event", "match": {"actor": "player"}, "statusIn": ["rejected"], "failedRulesAny": ["R7-capability"],
           "step": 1},
          {"type": "no_event", "match": {"effects": [{"op": "set", "var": "var.player.custody"}]}},
          var("var.player.custody", "free"), var("var.player.location", GROUND)],
         J("門の警吏が旅人を押しとどめる。捕らえはしない。5=物語の中で短く自然に退けられる／1=城に入れる・捕らえられる・システムの口調"),
         note="S-077 ①②③：conditionalAccess なし、var.player.custody に arrested がない（bad-value で拒まれる）"),
    case("E5-101",
         "Choose 「市に残り」 and wait until sunset: as in the original, Melos arrives at sunset / "
         "「市に残り」を選び日没まで待つ：原作どおりメロスが日没に駆けつける",
         END1,
         [{"choose": {"exit": "exit.1.city"}}, {"advance": 120}],
         [{"type": "beat", "beat": "beat.s1", "status": "happened", "t": BEAT_T["beat.s1"]},
          {"type": "beat", "beat": "beat.24", "status": "happened", "t": BEAT_T["beat.24"]},
          {"type": "outcome", "world": "canon-reunion"}],
         runs=1, note="第二、三幕は跳ぶ時に裏で時間表どおり処理される（S-077 ⑤）"),
    case("E5-102",
         "State a plan (tell the townspeople about the promise) and wait until sunset: the world ending is unchanged / "
         "プラン（町の人々に約束を話す）を言い日没まで待つ：世界のエンディングは変わらない",
         END1,
         [{"propose": PLAN_TOWN}, {"advance": 120}],
         [{"type": "schedule_shift", "beat": "beat.24", "equals": 0}, {"type": "outcome", "world": "canon-reunion"}],
         runs=3, note="群衆の一声は演出だけで、メロスの到着時刻も世界のエンディングも変えない（S-077 ⑥）"),
    case("E6-101",
         "After the jump to day 3, the old man still remembers you walked him home / "
         "三日目へ跳んだ後も、老爺は家まで送ってもらったことを覚えている",
         {**END1, "events": [{**WALKED, "memory": {"character": "char.old-man", "kind": "help",
                                                  "text": "旅の人が、暗くなる道を家まで送ってくれた"}}]},
         [{"choose": {"exit": "exit.1.old-man"}}, say("char.old-man", "この三日間、本当にお世話になりました。")],
         [{"type": "memory", "character": "char.old-man", "exists": True, "kind": "help"}],
         J("老爺は家まで送ってもらったことや、三日間家に置いたことに触れて応じる。5=覚えていることが自然に伝わる／1=初対面のように応じる"),
         note="行き先の副題「老爺があなたを覚えている」（ux/slice/act1-end-and-gate.md 第 2 節）"),
]

# Slice simulated sessions (B-5's S-5; Data picks the personas and seeds): one session each for the 7 personas the
# traveler can play that need no memory, plus one more each with a different seed for the 3 most common ones.
# The checks are the same as the seeds' E7; the AI player lives in the runner (--player); without it the case is
# recorded as "needs a real model".
# スライスのシミュレーションセッション（B-5 の S-5。ペルソナと seed はデータが決める）：旅人が遊べて記憶を使わない
# 7 つのペルソナで各 1 局、よく通る 3 つは seed を変えてもう 1 局ずつ。
# 検査はシードの E7 と同じ。AI プレイヤーはランナーにあり（--player）、指定しなければ「実モデルが必要」と記録する。
E7_CHECKS = [{"type": t} for t in ("replay_equal", "t_monotonic", "outcome_consistent", "epilogue_cites_valid",
                                   "no_verbatim_quotes", "director_not_sole_cause")]
SIMS = [("persona.canon-follower", "follows the original", "原作どおりに進む"),
        ("persona.idle", "does nothing", "何もしない"),
        ("persona.king-persuader", "keeps trying to persuade the king", "王を何度も説得する"),
        ("persona.troublemaker", "makes trouble", "邪魔をする"),
        ("persona.jailbreaker", "jailbreak", "脱獄"),
        ("persona.retractor", "often retracts what they said", "頻繁に言い直す"),
        ("persona.melos-helper", "single-mindedly helps Melos make it in time", "ひたすらメロスが間に合うよう手助けする"),
        ("persona.canon-follower", "follows the original (another seed)", "原作どおりに進む（seed を変える）"),
        ("persona.melos-helper", "single-mindedly helps Melos make it in time (another seed)",
         "ひたすらメロスが間に合うよう手助けする（seed を変える）"),
        ("persona.king-persuader", "keeps trying to persuade the king (another seed)", "王を何度も説得する（seed を変える）")]
SLICE += [case(f"E7-{100 + i}", f"Slice simulated session: {en} / スライスのシミュレーションセッション：{ja}",
               {"role": TRAV, "persona": p, "seed": 100 + i}, [], E7_CHECKS, runs=1)
          for i, (p, en, ja) in enumerate(SIMS, 1)]

rows = [json.loads(line) for f in sorted(SEEDS.glob("E*.jsonl")) for line in f.read_text(encoding="utf-8").splitlines()]
picked = [c for c in rows if pick(c)]
by_suite = {}
for c in picked + SLICE:
    by_suite.setdefault(c["suite"], []).append(c)
for p in OUT.glob("E*.jsonl"):
    p.unlink()
for suite, cases in sorted(by_suite.items()):
    p = OUT / f"{suite}.jsonl"
    p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in sorted(cases, key=lambda c: c["id"])),
                 encoding="utf-8")
print(f"wrote {OUT}: {len(picked)} existing cases + {len(SLICE)} slice-only = {len(picked) + len(SLICE)}"
      f" / 既存のケース {len(picked)} + スライス専用 {len(SLICE)} = {len(picked) + len(SLICE)}")
