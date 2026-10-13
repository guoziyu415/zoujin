"""A few primitives the narrator's deterministic rules need that the simulation did not have (B-2 card: proposed by
backend, added by data, reviewed by backend; spoilers was added during the B-12 review).

- knows(): R4 (contract 2.1 anti-spoiler rule). What character C knows right now = the entries in `C.knows` whose
  `since` has happened (or is `pre`) + what was learned via `learn` in this run (including other characters' improvised
  facts) + C's own improvised facts; (1.7) for the player = the role's `initialKnowledge` + what was learned in this run
  (told by characters, plus public facts that settle wrote into system events when the player was present at a beat).
  If a world fact's `trueFrom` has not happened in this run, nobody counts as knowing it (contract 2.3, 1.4). Matches
  the eval's evals/s2_check.py (the judgement used for S-2 labelling).
- travel_minutes(): R3 distances (contract 2.2 `adjacent`, api-contract 3.7, 3.8). Shortest path over the walking
  minutes of `places.adjacent`; between two places in the same scene, `pacing.sceneWalkMinutes` (S-038: walking inside
  a scene takes 0 minutes). Measures only the player's moves and `relocate`s outside the schedule; characters moving
  on schedule follow the schedule (backend-design 2.4).
- spoilers(): whether a character's utterance contains a fact they should not know right now (a `Fact.spoilerTerms`
  term appears in the utterance and they do not `knows` that fact). Shared by the narrator's R4 check of improvised
  facts, the gateway's output-side monitoring (B-12, backend-design 2.11) and the eval entry point's
  `monitor.spoilers`; the same standard as eval E2's `not_mention_fact` (E2 looks only at the one fact named when the
  case is written, and the self-check guarantees the character does not know it at the checkpoint).
- lived() (1.12 addendum): which happened beat a character lived through, used for the "most recent beat" the narrator
  gives a character (S-092). The same scene rule as sees() (1.12), but a character counts only beats they took part in
  and beats with no participants that fall in the same scene (weather, natural disasters), not "being at the beat's
  place": what a character knows follows `Character.knows` (presence in the original story is already written there)
  and `learn`, not automatic learning by presence (contract 2.1 ②); give them a beat they were present at but did not
  take part in, and they will say things they do not know. Where they were at the moment of the beat uses place_at():
  the same replay as activity(), i.e. "where they should be according to the beats".
- activity(): what a character is doing right now (contract 2.4 Activity, 1.1). Used by R7 (a character who is not
  present or is `absent` cannot be talked to) and the snapshot's `characters[].activity` (api-contract 2.3). Computes
  only the part the world model gives; the narrator infers the rest from the conversation (backend-design 2.7).

Not here: `crossing` (minutes to cross the river; done together with M3 and the stops on the return journey). The four
places of the return journey (川, 峠, 泉, 野の道) are each a scene of their own (S-081: between stops is a running
stretch, and "ひとりで先へ行く" costs time on the road), so they use the walking minutes of `adjacent`, not the 0
minutes inside a scene. The slice has no return journey.

ナレーターの決定的ルールに必要で、シミュレーションにはもともとなかったいくつかのプリミティブ（B-2 カード：
バックエンドが提案、データが追加、バックエンドがレビュー。spoilers は B-12 のレビュー時に追加）。

- knows()：R4（契約 2.1 ネタバレ防止ルール）。登場人物 C が今知っていること = `C.knows` のうち `since` が起きた
  （または `pre`）もの + このプレイで `learn` によって知ったこと（他人の即興設定を含む）+ C 自身の即興設定。
  （1.7）プレイヤー = ロールの `initialKnowledge` + このプレイで知ったこと（登場人物から聞いたこと、およびビート
  発生時にプレイヤーが在場し、settle がシステムイベントに書き込んだ public な事実）。世界の事実の `trueFrom` が
  このプレイで起きていなければ、誰も知っていることにはならない（契約 2.3、1.4）。評価の evals/s2_check.py
  （S-2 のラベル付けに使う判定）と一致する。
- travel_minutes()：R3 の道のり（契約 2.2 `adjacent`、api-contract 3.7、3.8）。`places.adjacent` の徒歩分数で
  最短経路を取る。同じシーン内の 2 地点間は `pacing.sceneWalkMinutes`（S-038：シーン内の移動は 0 分）。測るのは
  プレイヤーの移動とスケジュール外の `relocate` だけ。スケジュールどおりに動く登場人物はスケジュールを見る
  （backend-design 2.4）。
- spoilers()：登場人物の発話に、今その人が知っているはずのない事実が含まれていないか（`Fact.spoilerTerms` が
  発話に現れ、その人がその事実を `knows` していない）。ナレーターの R4 による即興設定のチェック、ゲートウェイの
  出力側監視（B-12、backend-design 2.11）、評価エントリーポイントの `monitor.spoilers` がこれ 1 つを共有する。
  評価 E2 の `not_mention_fact` と同じ基準（E2 は出題時に指定した 1 件だけを見て、セルフチェックで登場人物が
  チェックポイントでそれを知らないことを保証する）。
- lived()（1.12 補足）：登場人物が起きたビートのどれを体験したか。ナレーターが登場人物に渡す「直近のビート」に
  使う（S-092）。sees()（1.12）と同じシーンのルールだが、登場人物が数えるのは参加したビートと、参加人物がなく
  同じシーンに落ちるビート（天候、天災）だけで、「ビートの場所にいた」ことは数えない。登場人物が何を知るかは
  `Character.knows`（原作での在場はすでに書いてある）と `learn` に従い、在場による自動的な学習には従わない
  （契約 2.1 ②）。在場しただけで参加していないビートを渡すと、知らないことを話してしまう。ビートのその瞬間に
  どこにいたかは place_at() を使う。activity() と同じリプレイで、「ビートに従えばどこにいるべきか」である。
- activity()：登場人物が今何をしているか（契約 2.4 の Activity、1.1）。R7（相手が不在、または `absent` の
  登場人物とは会話できない）とスナップショットの `characters[].activity` に使う（api-contract 2.3）。計算するのは
  世界モデルが与える部分だけで、残りはナレーターが会話から推測する（backend-design 2.7）。

ここにないもの：`crossing`（川を渡る分数。M3 と帰路の立ち寄り地点と一緒に実装する）。帰路の 4 地点（川、峠、泉、
野の道）はそれぞれ 1 つのシーン（S-081：立ち寄り地点の間は走る区間で、「ひとりで先へ行く」は道中の時間を使う）
なので、シーン内の 0 分ではなく `adjacent` の徒歩分数で計算する。スライスに帰路はない。
"""

from __future__ import annotations

import heapq
from typing import Any

from .incremental import SimState
from .sim import OCCURRED, World, role_of
from .visibility import same_scene


def knows(world: World, state: SimState, who: str, fact: str) -> bool:
    """Whether who (a character ID or "player") knows fact (a fact ID, or the rf_ ID of an improvised fact) right now.

    who（登場人物 ID または "player"）が今 fact（事実 ID、または即興設定の rf_ ID）を知っているか。
    """
    beats = state["beats"]
    f = next((x for x in world["facts"] if x["id"] == fact), None)
    if f is not None and f["trueFrom"] != "pre" and beats.get(f["trueFrom"]) not in OCCURRED:
        return False
    if fact in state["knowledge"].get(who, []):
        return True
    if who == "player":
        return fact in role_of(world, state["role"]).get("initialKnowledge", [])
    rf = state["runFacts"].get(fact)
    if rf is not None and rf.get("character") == who:
        return True
    c = next((x for x in world["characters"] if x["id"] == who), None)
    return c is not None and any(
        k["fact"] == fact and (k["since"] == "pre" or beats.get(k["since"]) in OCCURRED) for k in c.get("knows", [])
    )


def spoilers(world: World, state: SimState, who: str, text: str, said: str = "") -> dict[str, list[str]]:
    """Spoiler terms in text said by who, for facts they do not know right now: {fact ID: terms that appear}, in the
    order of facts in the world model; empty if none.

    "Do not know" is `not knows()`, which already includes "this fact has not become true in this run yet" (contract
    2.3, 1.4). Matching is on raw substrings, with no kana or full-width normalization, the same as `s2_check.py` for E2
    and S-2. said = what the player said in the same turn: a term the player said themselves does not count when the
    character repeats it (E2 cases follow the same rule: the player's question must not contain spoiler terms).

    who が話した text のうち、その人が今知らない事実のネタバレ語：{事実 ID: 現れた語}。世界モデル内の事実の順で、
    なければ空。

    「知らない」とは `not knows()` のことで、「この事実はこのプレイでまだ成立していない」も含む（契約 2.3、1.4）。
    照合は生の部分文字列で、仮名や全角の正規化はしない。E2、S-2 の `s2_check.py` と同じ。said = 同じターンの
    プレイヤーの発話：プレイヤー自身が口にした語は、登場人物が続けて言ってもカウントしない（E2 の出題も同じ規則：
    プレイヤーの質問にネタバレ語を入れてはいけない）。
    """
    hits: dict[str, list[str]] = {}
    for f in world["facts"]:
        terms = [t for t in f.get("spoilerTerms") or () if t in text and t not in said]
        if terms and not knows(world, state, who, f["id"]):
            hits[f["id"]] = terms
    return hits


def travel_minutes(world: World, src: str, dst: str) -> int | None:
    """The minimum minutes to walk from src to dst. 0 for the same place; None if unreachable (or a place does not
    exist).

    src から dst まで最短で何分歩くか。同じ場所なら 0、たどり着けない（または場所が存在しない）なら None。
    """
    places = {p["id"]: p for p in world["places"]}
    if src not in places or dst not in places:
        return None
    in_scene = world.get("pacing", {}).get("sceneWalkMinutes", 0)
    best, q = {src: 0}, [(0, src)]
    while q:
        d, p = heapq.heappop(q)
        if p == dst:
            return d
        if d > best[p]:
            continue
        scene = places[p]["sceneRef"]
        for e in places[p]["adjacent"]:
            n = e["place"]
            nd = d + (in_scene if scene is not None and places[n]["sceneRef"] == scene else e["travelMinutes"])
            if nd < best.get(n, nd + 1):
                best[n] = nd
                heapq.heappush(q, (nd, n))
    return None


def activity(world: World, state: SimState, who: str) -> str:
    """What who (a character ID) is doing right now. Returns idle for anything that is not a character (including
    "player").

    Contract 2.4 (1.1): at the opening it is `initialActivity` (omitted = idle); after a beat happens it is what that
    beat's `activities` gives them, "until their next beat with an activity, or a move". Moved, and the new place gives
    nothing = idle (S-077 ⑩: someone working indoors is no longer absent once a beat takes them away). SimState does not
    keep the event history, so the happened beats are replayed in order of occurrence to get the place they "should
    be" at according to the beats; if the current `locations` differs from it = something other than a beat (a
    character's event, the narrator) moved them = idle.

    who（登場人物 ID）が今何をしているか。登場人物でないもの（"player" を含む）には idle を返す。

    契約 2.4（1.1）：オープニングでは `initialActivity`（省略 = idle）。ビートが起きた後は、そのビートの
    `activities` がその人に与えたもので、「その人の次の activity 付きビート、または移動まで」続く。移動して、
    新しい場所で何も与えられていなければ idle（S-077 ⑩：屋内で働いていた人は、ビートに連れ出された後はもう absent
    ではない）。SimState はイベントの履歴を持たないので、起きたビートを発生時刻順にリプレイし、ビートに従えば
    「いるべき」場所を求める。今の `locations` がそれと違えば、ビート以外（登場人物のイベント、ナレーター）が
    その人を動かしたということで idle。
    """
    r = _replay(world, state, who)
    if r is None:
        return "idle"
    place, act = r
    return act if state["locations"].get(who) == place else "idle"


def place_at(world: World, state: SimState, who: str, beat: str) -> str | None:
    """The place who (a character ID) should be at, according to the beats, at the moment beat happens: replays the
    beats that happened before beat in order of occurrence (the same replay as activity()).

    SimState does not keep the event history, so the times something other than a beat (a character's event, the
    narrator's relocate) moved them cannot be computed; this is therefore "where they should be according to the
    beats", not where they really were. None for anything that is not a character (including "player"), or if beat
    does not exist or did not happen in this run.

    beat が起きた瞬間に who（登場人物 ID）がビートに従えばいるべき場所：beat より前に起きたビートを発生時刻順に
    リプレイする（activity() と同じ方式）。

    SimState はイベントの履歴を持たないので、ビート以外（登場人物のイベント、ナレーターの relocate）がその人を
    動かした分は計算できない。したがってこれは「ビートに従えばどこにいるべきか」であり、実際にどこにいたかでは
    ない。登場人物でないもの（"player" を含む）、beat が存在しない、またはこのプレイで起きていなければ None。
    """
    beats = {b["id"]: b for b in world["beats"]}
    if beat not in beats or state["beats"].get(beat) not in OCCURRED:
        return None
    r = _replay(world, state, who, (state["times"].get(beat, 0), beats[beat]["order"]))
    return None if r is None else r[0]


def lived(world: World, state: SimState, who: str, beat: str) -> bool:
    """Character who lived through beat: it happened in this run (happened / altered), and they are a participant, or
    beat has no participants and falls in the same scene as where they were at the time (place_at). False if it did
    not happen, or for anything that is not a character (including "player").

    登場人物 who が beat を体験した：このプレイで起きた（happened / altered）うえで、その人が参加人物であるか、
    beat に参加人物がなく、その時点（place_at）でその人がいた場所と同じシーンに落ちる。起きていないもの、
    登場人物でないもの（"player" を含む）はすべて False。
    """
    b = next((x for x in world["beats"] if x["id"] == beat), None)
    if b is None or state["beats"].get(beat) not in OCCURRED:
        return False
    if who in b["participants"]:
        return True
    if b["participants"]:
        return False
    where = place_at(world, state, who, beat)
    return where is not None and same_scene(world, b["place"], where)


def _replay(world: World, state: SimState, who: str, before: tuple[int, int] | None = None) -> tuple[str, str] | None:
    """Replays the happened beats in order of occurrence (`order` within the same time) and returns the (place,
    activity) who should have according to the beats.

    If before is given, only beats ordered before it ((time, order)) are replayed. None for anything that is not a
    character.

    起きたビートを発生時刻順（同時刻なら `order` 順）にリプレイし、who がビートに従えば持つべき（場所, activity）を
    返す。

    before が与えられれば、それより前に並ぶビート（(時刻, order)）だけをリプレイする。登場人物でなければ None。
    """
    c = next((x for x in world["characters"] if x["id"] == who), None)
    if c is None:
        return None
    act: str = c.get("initialActivity", "idle")
    place: str = c["initialPlace"]
    beats = {b["id"]: b for b in world["beats"]}
    done = sorted(
        (b for b, st in state["beats"].items() if st in OCCURRED and b in beats),
        key=lambda b: (state["times"].get(b, 0), beats[b]["order"]),
    )
    for b in done:
        x = beats[b]
        if before is not None and (state["times"].get(b, 0), x["order"]) >= before:
            break
        # Participants first move to the beat's place (contract 3.1)
        # 参加人物はまずビートの場所へ移る（契約 3.1）
        after = x["place"] if who in x["participants"] else place
        for e in _outcomes(x, state):
            if e.get("op") == "relocate" and e.get("character") == who:
                after = e["place"]
        given = next((a["activity"] for a in x.get("activities", []) if a["character"] == who), None)
        if given is not None:
            act = given
        elif after != place:
            act = "idle"
        place = after
    return place, act


def _outcomes(beat: dict[str, Any], state: SimState) -> list[dict[str, Any]]:
    """The outcomes this beat actually uses in this run: a variant's, the one the player changed in advance (altered),
    or the original story's.

    このプレイでこのビートが実際に使う結果：バリアントのもの、プレイヤーが事前に変えたもの（altered）、または
    原作のもの。
    """
    vid = state["variants"].get(beat["id"])
    if vid is not None:
        v = next((v for v in beat.get("variants", []) if v["id"] == vid), None)
        if v is not None:
            return list(v["outcomes"])
    o = state["overrides"].get(beat["id"], {})
    if state["beats"].get(beat["id"]) == "altered" and o.get("to") == "altered":
        return list(o.get("outcomes", []))
    return list(beat["outcomes"])
