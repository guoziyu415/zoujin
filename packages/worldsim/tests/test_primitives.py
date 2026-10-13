"""knows() (R4), spoilers() (R4, output-side monitoring), travel_minutes() (R3 distances) and activity() (R7,
snapshots): the narrator's deterministic rules and eval S-2 use the same ones.

knows()（R4）、spoilers()（R4、出力側の監視）、travel_minutes()（R3 の道のり）、activity()（R7、スナップショット）：
ナレーターの決定的ルールと評価 S-2 が同じものを使う。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from zoujin_worldsim import (
    SimState,
    activity,
    apply,
    check_effects,
    initial_state,
    knows,
    settle,
    spoilers,
    travel_minutes,
)

WORLD_DIR = Path(__file__).resolve().parents[3] / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
GROUND = "place.execution-ground"
RF = "rf_01J00000000000000000000000"


def at(t: int, effects: list[dict[str, Any]] | None = None) -> SimState:
    s = initial_state(WORLD, ROLE)
    if effects:
        s = apply(WORLD, s, {"t": 0, "dt": 0, "origin": "turn", "effects": effects})
    return settle(WORLD, s, t)[1]


def test_since_learn_and_own_improv() -> None:
    s = at(0)
    assert knows(WORLD, s, "char.selinuntius", "fact.friendship")  # since pre
    assert not knows(WORLD, s, "char.selinuntius", "fact.promise")  # since beat.06, not happened yet / まだ起きていない
    s = at(1411)
    assert knows(WORLD, s, "char.selinuntius", "fact.promise")
    assert not knows(WORLD, s, "char.crowd", "fact.promise")
    s = apply(WORLD, s, {"t": s["t"], "dt": 0, "origin": "turn", "effects": [
        {"op": "learn", "character": "char.crowd", "fact": "fact.promise"},
        {"op": "improv", "factId": RF, "character": "char.old-man", "statement": "…"},
    ]})  # fmt: skip
    assert knows(WORLD, s, "char.crowd", "fact.promise")
    assert knows(WORLD, s, "char.old-man", RF)  # Their own improvised fact / 自分の即興設定
    assert not knows(WORLD, s, "char.melos", RF)  # Someone else's, not learned / 他人のもので、知っていない
    s = apply(WORLD, s, {"t": s["t"], "dt": 0, "origin": "turn",
                         "effects": [{"op": "learn", "character": "char.melos", "fact": RF}]})  # fmt: skip
    assert knows(WORLD, s, "char.melos", RF)
    assert not knows(WORLD, s, "char.nobody", "fact.promise")
    assert not knows(WORLD, s, "char.melos", "fact.nothing")


def test_a_fact_that_is_not_true_this_run_is_known_by_nobody() -> None:
    """Contract 2.3 (1.4): if the trueFrom beat has not happened, neither anyone's knows nor what they learned counts
    (S-064).

    契約 2.3（1.4）：trueFrom のビートが起きていなければ、誰の knows も、知ったことも数えない（S-064）。
    """
    # Set up by hand; R4 would reject it
    # 手で配置したもの。R4 なら拒否する
    early = at(0, [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}])
    assert not knows(WORLD, early, "char.crowd", "fact.promise")
    # Counts only after beat.05 happens
    # beat.05 が起きてから数える
    assert knows(WORLD, settle(WORLD, early, 1411)[1], "char.crowd", "fact.promise")
    s = at(1411)
    # Melos's since is beat.25
    # Melos の since は beat.25
    late = {**copy.deepcopy(s), "beats": {**s["beats"], "beat.25": "happened"}}
    # trueFrom is beat.s2
    # trueFrom は beat.s2
    for s2, known in [(None, False), ("prevented", False), ("happened", True)]:
        beats = late["beats"] if s2 is None else {**late["beats"], "beat.s2": s2}
        assert knows(WORLD, {**late, "beats": beats}, "char.melos", "fact.selinuntius-doubted-once") is known


def test_spoilers_are_terms_of_facts_the_speaker_does_not_know() -> None:
    """B-12: a spoiler term of a fact the character does not know right now counts when it appears in what they say;
    facts they know, or that became true in this run and were then learned, do not.

    B-12：登場人物の発話に、その人が今知らない事実のネタバレ語があれば数える。知っている事実や、このプレイで成立
    してから知った事実は数えない。
    """
    start, later = at(0), at(1500)  # 1500: beat.01〜07 have happened / beat.01〜07 は発生済み
    # The old man: since pre
    # 老爺は since pre
    assert spoilers(WORLD, start, "char.old-man", "今日は六人殺された") == {}
    assert spoilers(WORLD, start, "char.melos", "今日は六人殺された") == {"fact.six-killed-today": ["六人"]}
    assert spoilers(WORLD, later, "char.melos", "今日は六人殺された") == {}  # Melos: since beat.03 / メロス
    # The promise only becomes true at beat.05: before that it counts for anyone; after that it does not count for
    # those who know it (セリヌンティウス since beat.06) but still counts for those who do not (the old man)
    # 約束は beat.05 で初めて成立する：それより前は誰が言っても数える。その後は知っている人（セリヌンティウス
    # since beat.06）は数えず、知らない人（老爺）はそのまま数える
    line = "わたしが身代わりになろう。三日目の日没までに帰る"
    hit = {"fact.promise": ["身代わり", "三日目の日没", "日没までに帰"]}
    assert spoilers(WORLD, start, "char.selinuntius", line) == hit
    assert spoilers(WORLD, later, "char.selinuntius", line) == {}
    assert spoilers(WORLD, later, "char.old-man", line) == hit
    assert spoilers(WORLD, start, "char.melos", "いい天気だ") == {}


def test_spoilers_skip_what_the_player_just_said() -> None:
    """A term the player said themselves this turn does not count when the character repeats it (the rule for E2
    cases: the player's question must not contain spoiler terms); terms the player did not say still count.

    プレイヤーがこのターンで自分から口にした語は、登場人物が続けて言っても数えない（E2 の出題規則：プレイヤーの
    質問にネタバレ語を入れてはいけない）。言っていない語はそのまま数える。
    """
    s = at(0)
    assert spoilers(WORLD, s, "char.old-man", "山賊？ 待ち伏せなど聞いたことがない", said="山賊がいるらしい") == {
        "fact.bandits-ambush": ["待ち伏せ"]
    }
    assert spoilers(WORLD, s, "char.old-man", "山賊？", said="山賊がいるらしい") == {}
    # The player is judged by knows too
    # プレイヤーも knows で判定
    assert spoilers(WORLD, s, "player", "大雨になる") == {"fact.storm": ["大雨"]}


def test_the_player_knows_what_the_role_knows_and_what_they_learn() -> None:
    """Player = the role's initialKnowledge + what was learned in this run (contract 2.1, 1.7).

    プレイヤー = ロールの initialKnowledge + このプレイで知ったこと（契約 2.1、1.7）。
    """
    s = at(0)
    assert knows(WORLD, s, "player", "fact.city-silent")
    assert not knows(WORLD, s, "player", "fact.king-killings")
    assert check_effects(WORLD, s, [{"op": "learn", "character": "player", "fact": "fact.king-killings"}], "turn") == []
    bad = check_effects(WORLD, s, [{"op": "learn", "character": "char.nobody", "fact": "fact.king-killings"}], "turn")
    assert [p["code"] for p in bad] == ["unknown-id"]
    # What the old man told the player
    # 老爺がプレイヤーに話したこと
    told = [{"op": "learn", "character": "player", "fact": "fact.king-killings"}]
    s = apply(WORLD, s, {"t": 0, "dt": 0, "origin": "turn", "effects": told})
    assert knows(WORLD, s, "player", "fact.king-killings")
    assert not knows(WORLD, s, "char.melos", "fact.king-killings")  # Melos: since beat.03 / メロスは beat.03 から
    boy = settle(WORLD, initial_state(WORLD, "role.shepherd-boy"), 1980)[1]
    assert knows(WORLD, boy, "player", "fact.sister-engaged")
    assert not knows(WORLD, boy, "player", "fact.city-silent")


def test_the_player_learns_public_facts_of_beats_they_see() -> None:
    """When a beat happens with the player at the beat's place, settle writes learn into that system event, public
    facts only (contract 2.1, 2.3, 1.7).

    ビートが起きたときプレイヤーがビートの場所にいれば、settle はそのシステムイベントに learn を書く。public な
    ものだけ（契約 2.1、2.3、1.7）。
    """
    drafts, s = settle(WORLD, at(0, [{"op": "set", "var": "var.player.location", "value": GROUND}]), 1201)
    # The arrest is in the castle forecourt
    # 捕縛は王城の前庭
    arrest = next(d["event"] for d in drafts if d["beat"] == "beat.04")
    assert {"op": "learn", "character": "player", "fact": "fact.melos-dagger"} in arrest["effects"]
    assert knows(WORLD, s, "player", "fact.melos-dagger")
    # The promise (beat.05) and hostage (beat.06) are inside the castle; the player is not there
    # 約束（beat.05）と人質（beat.06）は王城内で、プレイヤーはいない
    drafts, s = settle(WORLD, s, 1411)
    assert not any(e.get("character") == "player" for d in drafts for e in d["event"]["effects"])
    assert not knows(WORLD, s, "player", "fact.promise")
    away = at(1411)  # Stayed in the square all along / ずっと広場にいる
    assert not knows(WORLD, away, "player", "fact.melos-dagger")
    assert not any(e["op"] == "learn" for d in settle(WORLD, at(0), 1201)[0] for e in d["event"]["effects"])


def test_the_player_is_away_while_an_act_change_settles() -> None:
    """Step 3 of an act switch (contract 2.8.1): the player's place has not changed yet, but for this stretch they
    count as absent and no learn is written; everything else is unchanged.

    幕切り替えの第 3 段階（契約 2.8.1）：プレイヤーの場所はまだ変わっていないが、この区間は不在とみなし、learn を
    書かない。ほかはそのまま。
    """
    there = at(0, [{"op": "set", "var": "var.player.location", "value": GROUND}])
    seen, s_seen = settle(WORLD, there, 1201)
    away, s_away = settle(WORLD, there, 1201, player_present=False)
    assert not any(e.get("character") == "player" for d in away for e in d["event"]["effects"])
    assert not knows(WORLD, s_away, "player", "fact.melos-dagger")
    assert knows(WORLD, s_seen, "player", "fact.melos-dagger")

    def unlearned(e: dict[str, Any]) -> dict[str, Any]:
        return {**e, "effects": [x for x in e["effects"] if x.get("character") != "player"]}

    assert [unlearned(d["event"]) for d in seen] == [d["event"] for d in away]
    assert s_away["beats"] == s_seen["beats"]


def test_walking_minutes_take_the_shortest_way() -> None:
    def m(a: str, b: str) -> int | None:
        return travel_minutes(WORLD, f"place.{a}", f"place.{b}")

    assert m("syracuse-square", "syracuse-square") == 0
    # Walking within one scene takes 0 minutes (S-038, api-contract 3.8): square, workshop, execution ground
    # 同じシーン内の移動は 0 分（S-038、api-contract 3.8）：広場、工房、刑場
    assert m("syracuse-square", "execution-ground") == m("stonemason-workshop", "execution-ground") == 0
    assert m("village", "groom-house") == m("melos-home", "groom-house") == 0
    # Across scenes, use adjacent and take the shortest: square → castle directly is 10 minutes; via the execution
    # ground, 0 + 5 minutes is shorter
    # シーンをまたぐときは adjacent で最短を取る：広場 → 王城は直接だと 10 分、刑場経由なら 0 + 5 分で短い
    assert m("syracuse-square", "castle") == m("stonemason-workshop", "castle") == m("execution-ground", "castle") == 5
    assert m("castle", "syracuse-square") == 5
    # The neighbouring village has no scene (sceneRef null)
    # 隣村にはシーンがない
    assert m("village", "neighbor-village") == 120
    assert m("neighbor-village", "river") == 180
    assert m("road-to-city", "syracuse-square") == 60
    # Each stop on the return journey is its own scene (S-081 ②: 「ひとりで先へ行く」 costs time on the road), so
    # use adjacent's walking minutes
    # 帰路の立ち寄り地点はそれぞれ 1 つのシーン（S-081 ②：「ひとりで先へ行く」は道中の時間を使う）なので、
    # adjacent の徒歩分数を使う
    assert m("river", "mountain-pass") == 100
    assert m("river", "road-to-city") == 100 + 45 + 120
    assert m("melos-home", "syracuse-square") == 120 + 180 + 100 + 45 + 120 + 60
    assert m("syracuse-square", "nowhere") is None


def test_unreachable_and_no_pacing() -> None:
    w = copy.deepcopy(WORLD)
    w["places"].append({**w["places"][0], "id": "place.island", "adjacent": [], "sceneRef": None})
    assert travel_minutes(w, "place.syracuse-square", "place.island") is None
    assert travel_minutes(w, "place.island", "place.island") == 0
    w["pacing"] = {**w["pacing"], "sceneWalkMinutes": 3}
    assert travel_minutes(w, "place.syracuse-square", "place.execution-ground") == 3
    del w["pacing"]
    assert travel_minutes(w, "place.syracuse-square", "place.execution-ground") == 0


def test_activity_follows_the_beats_until_someone_is_moved() -> None:
    """Contract 2.4 (1.1): at the opening it is initialActivity; an activity given by a beat lasts until the next beat
    that gives them one, or a move.

    契約 2.4（1.1）：オープニングでは initialActivity。ビートが与えた activity は、その人に次に activity を与える
    ビートか移動まで続く。
    """
    assert activity(WORLD, at(0), "char.sister") == "work"  # initialActivity, at initialPlace / initialPlace にいる
    assert activity(WORLD, at(0), "char.melos") == "idle"  # Omitted = idle / 省略 = idle
    assert activity(WORLD, at(2040), "char.sister") == "talk"  # Given by beat.08 / beat.08 が与えた
    assert activity(WORLD, at(1180), "char.melos") == "talk"  # beat.03
    # beat.04 moves him into the castle with no activity
    # activity なしで王城へ移す
    assert activity(WORLD, at(1200), "char.melos") == "idle"
    assert activity(WORLD, at(1230), "char.melos") == "talk"  # beat.05
    assert activity(WORLD, at(2070), "char.melos") == "sleep"  # beat.09
    assert activity(WORLD, at(3150), "char.melos") == "talk"  # beat.10, at the groom's house / 花婿の家
    # beat.11 takes participants home with no activity
    # activity なしで家へ
    assert activity(WORLD, at(3600), "char.melos") == "idle"
    # Home all along; beat.08 still counts
    # ずっと家にいて beat.08 が有効
    assert activity(WORLD, at(3600), "char.sister") == "talk"
    assert activity(WORLD, at(0), "player") == "idle"
    assert activity(WORLD, at(0), "char.nobody") == "idle"


def test_absent_lasts_only_while_nobody_moves_them() -> None:
    """S-077 ⑩: an absent character becomes present once a beat takes them away (participants move to the beat's
    place, contract 3.1).

    S-077 ⑩：absent の登場人物は、ビートに連れ出された（参加人物はビートの場所に移る、契約 3.1）後は在場になる。
    """
    assert activity(WORLD, at(5390), "char.crowd") == "absent"  # absent at the opening, still in the square / まだ広場
    # beat.s1: the crowd is a participant, moved to the execution ground; the beat gives it no activity
    # beat.s1：群衆は参加人物で刑場へ移り、ビートは activity を与えない
    s = at(5400)
    assert s["locations"]["char.crowd"] == GROUND
    assert activity(WORLD, s, "char.crowd") == "idle"
    # Not a participant; moved there by the outcomes' relocate
    # outcomes の relocate で移動
    assert activity(WORLD, s, "char.maiden") == "idle"
    assert activity(WORLD, s, "char.selinuntius") == "idle"  # Given by beat.s1 / beat.s1 が与えた


def test_activity_ends_when_an_event_moves_someone() -> None:
    """An event by the narrator or a character moved someone (not a beat): SimState has no history, so it judges by
    "right now they are not where the beats put them" and falls back to idle.

    ナレーターや登場人物のイベントが人を動かした（ビートではない）：SimState には履歴がないので、「今ビートが
    置いた場所にいない」ことで判定し、idle に戻る。
    """
    s = at(2070)
    assert activity(WORLD, s, "char.melos") == "sleep"
    moved = {"op": "relocate", "character": "char.melos", "place": "place.village"}
    s = apply(WORLD, s, {"t": s["t"], "dt": 0, "origin": "turn", "effects": [moved]})
    assert activity(WORLD, s, "char.melos") == "idle"


def test_activity_uses_the_outcomes_this_run_used() -> None:
    """A beat changed by the player in advance (altered): where he should be is computed from this run's actual
    outcomes, not the original story's relocate.

    プレイヤーが事前に変えたビート（altered）：その人がいるべき場所は、原作の relocate ではなく、このプレイの実際の
    結果から計算する。
    """
    canon = at(4590)  # beat.14: the original story moves Melos to the village / 原作ではメロスを村へ移す
    assert canon["locations"]["char.melos"] == "place.village"
    assert activity(WORLD, canon, "char.melos") == "run"
    # Changed so it does not move him
    # 彼を動かさないように変更
    s = at(4590, [{"op": "beat", "beat": "beat.14", "to": "altered", "outcomes": []}])
    assert s["beats"]["beat.14"] == "altered"
    assert s["locations"]["char.melos"] == "place.melos-home"
    assert activity(WORLD, s, "char.melos") == "run"
