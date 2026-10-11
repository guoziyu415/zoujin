"""生成切片用例 evals/slice/E*.jsonl（S-077 ⑨）：现有用例里切片玩得到的，加切片专用的。改用例改这里，再跑：
    uv run python -I evals/gen_slice.py evals/slice
现有用例从 evals/seeds 读（先跑 gen_seeds.py），按 pick() 的规则挑；切片专用的写在下面，编号 101 起，不和种子撞。
`zoujin-eval --slice` 跑这一组，世界模型用 1.0.0-slice。自检同种子，--world 换成切片版。"""
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
T_JUMP = min(e["t"] for e in EXITS)                      # 三日目 17:30：第一幕之后从这里接着玩
BEAT_T = {b["id"]: b["window"]["canonical"] for b in WORLD["beats"]}
TALKABLE = {c["id"] for c in WORLD["characters"] if c["talkable"]}
GROUND = "place.execution-ground"


def pick(c):
    """切片玩得到的现有用例：旅人，原著路径上的检查点，落在第一幕或跳转以后，在旅人能去的地点，
    只和切片里能对话的人说话，幕末打算的去向是切片的下一幕（E4-011 期待 act.2，切片版另写 E4-105）。"""
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


END1 = {"role": TRAV, "checkpoint": "sc.canon@beat.07"}  # 第一幕收幕：梅洛斯出发
WALKED = {"effects": [{"op": "set", "var": "var.player.walkedOldManHome", "value": True}],
          "note": "第一幕で老爺を家まで送った（aid.old-man.listen）"}
WALK_OFFER = "もう暗くなります。お家まで、ご一緒しましょう。"
JUMPED = [var("var.player.location", GROUND), var("var.act.current", "act.4")]
JUMP_NOTE = "S-077 ⑤：第一幕の去処はどれも三日目 17:30 の刑場へ跳ぶ（contracts 2.8.1、1.7 の spot / arrival）"
PLAN_TOWN = "町の人たちに、メロスの約束のことを話して回ります。"

SLICE = [
    case("E2-101", "老爷（跳到三日目后）：梅洛斯路上怎样了", {**END1, "events": [WALKED]},
         [{"choose": {"exit": "exit.1.old-man"}},
          say("char.old-man", "メロスという若者は、いまどのあたりでしょうね。道中で何かあったんでしょうか。")],
         [{"type": "not_mention_fact", "fact": "fact.bandits-ambush"},
          {"type": "not_mention_fact", "fact": "fact.bridge-destroyed"},
          {"type": "not_mention_fact", "fact": "fact.melos-despair"}],
         J("老爺は町にいたので、メロスの道中のことは知らない。知らないと認め、帰りを案じる気持ちや、日が傾いていく様子を語る。"
           "5=知らないまま自然に案じる／1=山賊・橋・倒れたことなど知りえない出来事を語る"),
         note="町の人は彼がどこまで来たか知らない（ux/slice/jump-transition.md「要做到的」2）"),
    case("E4-101", "送老爷回家：开局互助兑现，记下送过他", {"role": TRAV, "checkpoint": "sc.canon@beat.02"},
         [say("char.old-man", WALK_OFFER)],
         [{"type": "event", "match": {"actor": "player",
                                      "effects": [{"op": "set", "var": "var.player.walkedOldManHome", "value": True}]},
           "statusIn": ["passed", "rewritten"]},
          var("var.player.walkedOldManHome", True)],
         J("老爺は恐縮しながら申し出を受け、怯えた様子のまま短く礼を言う。5=老爺らしい口調で自然に受ける／1=断る・礼がない・口調が違う"),
         note="aid.old-man.listen の effects（contracts 1.4）。「老爺の家に身を寄せる」はこれをやった時だけ出る（S-077 ④）"),
    case("E4-108", "按「家まで送る」：30 分，老爷到家门口", {"role": TRAV, "checkpoint": "sc.canon@beat.02"},
         [{"act": {"kind": "help", "target": "char.old-man"}}],
         [{"type": "event", "match": {"actor": "player", "effects": [
             {"op": "set", "var": "var.player.walkedOldManHome", "value": True},
             relocate("char.old-man", "place.syracuse-square", "old-man-house")]}, "statusIn": ["passed"], "step": 1},
          {"type": "clock_advanced", "min": 30, "max": 30, "step": 1},
          var("var.player.walkedOldManHome", True)],
         J("道中を一、二文で語る（老爺はゆっくり歩き、道々話す）。王が人を殺す訳はここで語らない（それは老爺との会話で聞く）。"
           "5=短く自然／1=長い・王の訳を語ってしまう・システムの口調"),
         note="aff.walk-old-man-home（UX 10-10）：話して果たすのと同じ互助 aid.old-man.listen。一局一度"),
    case("E4-102", "选「老爺の家に身を寄せる」：跳到三日目 17:30 的刑场，老爷在旁边", {**END1, "events": [WALKED]},
         [{"choose": {"exit": "exit.1.old-man"}}],
         [{"type": "event", "match": {"type": "act-transition", "actor": "player",
                                      "effects": [relocate("char.old-man", GROUND, "stake-front-side")]},
           "statusIn": ["passed"]},
          *JUMPED, {"type": "beat", "beat": "beat.s1", "status": "pending"}],
         runs=3, note=JUMP_NOTE + "。17:30 の刑場はまだ空いていて、beat.s1 は 18:00"),
    case("E4-103", "没送过老爷时选「老爺の家に身を寄せる」：没有这个去处", END1,
         [{"choose": {"exit": "exit.1.old-man"}}],
         [{"type": "no_event", "match": {"type": "act-transition"}},
          var("var.player.location", ROLE["startPlace"]), var("var.act.current", "act.1")],
         runs=1, note="requires を満たさない去処は act_ended.options に出ない（api-contract 3.11）。選んでも事件を書かない"),
    case("E4-104", "选「市に残り、メロスの帰りを待つ」：落在刑场西头，老爷在刑场前", END1,
         [{"choose": {"exit": "exit.1.city"}}],
         [{"type": "event", "match": {"type": "act-transition", "actor": "player",
                                      "effects": [relocate("char.old-man", GROUND, "stake-front"),
                                                  relocate("char.philostratus", "place.road-to-city")]},
           "statusIn": ["passed"]},
          *JUMPED],
         runs=1, note=JUMP_NOTE + "。フィロストラトスは跳ぶ時に進城の道へ（結局に出ない、S-077 ⑦）"),
    case("E4-105", "幕末说出能成行的打算：把约定告诉城里的人", END1,
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
         note="E4-011 の切片版：切片では打算が成行しても三日目 17:30 の刑場に落ちる（Act.plan、C-19：老爺は ground-west）。打算の効果は群衆が約束を知る learn（S-077 ⑥）"),
    case("E4-106", "幕末想追梅洛斯去村子：切片里不成行", END1,
         [{"propose": "メロスを追いかけて、村まで一緒に行きます。"}],
         [{"type": "act_plan", "accepted": False}, {"type": "world_unchanged"}],
         J("物語の中の理由で行けないと伝え（例：「メロスの姿は、もう夜の向こうに消えていた。」）、"
           "「市に残り、メロスの帰りを待つ」を代わりに示す。5=自然で次に進める／1=成行したことになる・理由がない・説教・システムの口調"),
         note="切片は村を開けない（S-077 ①④）。文案は ux/slice/act1-end-and-gate.md 第 2 节"),
    case("E4-107", "城门口：跟不进王城，也不会被抓", {"role": TRAV, "checkpoint": "sc.canon@beat.04", "place": GROUND},
         [{"act": {"kind": "go", "target": "place.castle"}}, {"act": {"kind": "block", "target": "char.guards"}}],
         [{"type": "event", "match": {"actor": "player"}, "statusIn": ["rejected"], "failedRulesAny": ["R7-capability"],
           "step": 1},
          {"type": "no_event", "match": {"effects": [{"op": "set", "var": "var.player.custody"}]}},
          var("var.player.custody", "free"), var("var.player.location", GROUND)],
         J("門の警吏が旅人を押しとどめる。捕らえはしない。5=物語の中で短く自然に退けられる／1=城に入れる・捕らえられる・システムの口調"),
         note="S-077 ①②③：conditionalAccess なし、var.player.custody に arrested がない（bad-value で拒まれる）"),
    case("E5-101", "选「市に残り」后等到日没：照原作，梅洛斯日没赶到", END1,
         [{"choose": {"exit": "exit.1.city"}}, {"advance": 120}],
         [{"type": "beat", "beat": "beat.s1", "status": "happened", "t": BEAT_T["beat.s1"]},
          {"type": "beat", "beat": "beat.24", "status": "happened", "t": BEAT_T["beat.24"]},
          {"type": "outcome", "world": "canon-reunion"}],
         runs=1, note="第二、三幕は跳ぶ時に後ろで時間表どおり結算される（S-077 ⑤）"),
    case("E5-102", "说出打算（把约定告诉城里的人）后等到日没：世界结局照旧", END1,
         [{"propose": PLAN_TOWN}, {"advance": 120}],
         [{"type": "schedule_shift", "beat": "beat.24", "equals": 0}, {"type": "outcome", "world": "canon-reunion"}],
         runs=3, note="群衆の一声は演出だけで、メロスの到着時刻も世界結局も変えない（S-077 ⑥）"),
    case("E6-101", "跳到三日目后，老爷还记得你送他回家",
         {**END1, "events": [{**WALKED, "memory": {"character": "char.old-man", "kind": "help",
                                                  "text": "旅の人が、暗くなる道を家まで送ってくれた"}}]},
         [{"choose": {"exit": "exit.1.old-man"}}, say("char.old-man", "この三日間、本当にお世話になりました。")],
         [{"type": "memory", "character": "char.old-man", "exists": True, "kind": "help"}],
         J("老爺は家まで送ってもらったことや、三日間家に置いたことに触れて応じる。5=覚えていることが自然に伝わる／1=初対面のように応じる"),
         note="去処の副題「老爺があなたを覚えている」（ux/slice/act1-end-and-gate.md 第 2 节）"),
]

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
print(f"wrote {OUT}: 现有用例 {len(picked)} + 切片专用 {len(SLICE)} = {len(picked) + len(SLICE)}")
