"""sees() (contract 1.12): whether the player can see an event. Used by settle writing learn for the player, by the
backend pushing events, and for whether the player counts as present at a set piece on a beat.

sees()（契約 1.12）：プレイヤーがあるイベントを見られるか。settle がプレイヤーに learn を書くとき、バックエンドが
イベントをプッシュするとき、ビート上の固定演出で在場とみなすかどうかのすべてで使う。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from zoujin_worldsim import SimState, apply, initial_state, knows, lived, place_at, same_scene, sees, settle

WORLD_DIR = Path(__file__).resolve().parents[3] / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
WEDDING = "place.melos-home"  # The wedding (beat.11, 13), scene.village / 婚礼（beat.11、13）
GROOM = "place.groom-house"  # scene.village
# Downpour: no participants; since W-2 it falls on place.melos-home (scene.village)
# 大雨：参加人物なし、W-2 以降は place.melos-home に落ちる
RAIN = "beat.12"


def at(place: str) -> SimState:
    s = initial_state(WORLD, ROLE)
    return apply(
        WORLD,
        s,
        {"t": 0, "dt": 0, "origin": "turn", "effects": [{"op": "set", "var": "var.player.location", "value": place}]},
    )


def beat_event(drafts: list[Any], beat: str) -> dict[str, Any]:
    return next(d["event"] for d in drafts if d["beat"] == beat)


def test_the_rain_reaches_the_wedding() -> None:
    """Contract 1.12: the downpour of beat.12 (since W-2 it falls on the wedding's place.melos-home) counts as seen
    by a player at the groom's house (place.groom-house) in the same scene: settle writes learn for the player in the
    downpour's system event, and the backend pushes it to the player by the same rule.

    契約 1.12：beat.12 の大雨（W-2 以降は婚礼の place.melos-home に落ちる）は、同じシーンの花婿の家
    （place.groom-house）にいるプレイヤーにも見えたことになる：settle は大雨のシステムイベントでプレイヤーに
    learn を書き、バックエンドは同じルールでそれをプレイヤーにプッシュする。
    """
    drafts, s = settle(WORLD, at(GROOM), 3660)
    rain = beat_event(drafts, RAIN)
    assert rain["place"] == WEDDING and rain["place"] != GROOM
    assert sees(WORLD, GROOM, rain)
    assert {"op": "learn", "character": "player", "fact": "fact.storm"} in rain["effects"]
    assert knows(WORLD, s, "player", "fact.storm")


def test_a_beat_with_people_is_seen_only_at_its_own_place() -> None:
    """A beat with participants still looks only at the place: the wedding is at place.melos-home, so a player at
    the groom's house in the same scene does not count as present.

    参加人物のいるビートは従来どおり場所だけを見る：婚礼は place.melos-home なので、同じシーンの花婿の家にいる
    プレイヤーは在場とみなさない。
    """
    drafts, _ = settle(WORLD, at(GROOM), 3660)
    wedding = beat_event(drafts, "beat.11")
    assert same_scene(WORLD, GROOM, wedding["place"])
    assert not sees(WORLD, GROOM, wedding)
    assert sees(WORLD, WEDDING, wedding)
    # The rain is visible at the groom's house too
    # 雨は花婿の家からも見える
    assert sees(WORLD, GROOM, beat_event(drafts, RAIN))


def test_places_without_a_scene_are_never_the_same_scene() -> None:
    """Both sceneRefs must be non-empty: place.neighbor-village has no scene, so it is not in the same scene even as
    itself (the same place is covered separately by rule ②).

    両方の sceneRef が空でない必要がある：place.neighbor-village にはシーンがないので、自分自身とも同じシーンに
    ならない（同じ場所は別に第 ② 条で扱う）。
    """
    assert not same_scene(WORLD, "place.neighbor-village", "place.neighbor-village")
    w = copy.deepcopy(WORLD)
    for p in w["places"]:
        if p["id"] in ("place.river", "place.mountain-pass"):
            p["sceneRef"] = None
    flood = {
        "actor": "system",
        "place": "place.river",
        "effects": [{"op": "beat", "beat": "beat.17", "to": "happened"}],
    }
    assert not sees(w, "place.mountain-pass", flood)
    assert sees(w, "place.river", flood)


def test_the_player_sees_what_they_do_and_nothing_without_a_place() -> None:
    mine = {"actor": "player", "place": "place.castle", "effects": []}
    assert sees(WORLD, "place.village", mine)
    assert not sees(WORLD, None, {"actor": "system", "place": "place.village", "effects": []})


def test_an_act_change_still_counts_the_player_away() -> None:
    """Step 3 of an act switch (player_present=False): no learn is written even for rain in the same scene (contract
    2.8.1, unchanged by 1.12).

    幕切り替えの第 3 段階（player_present=False）：同じシーンの雨でも learn を書かない（契約 2.8.1、1.12 でも
    変わらない）。
    """
    drafts, s = settle(WORLD, at(WEDDING), 3660, player_present=False)
    assert not any(e.get("character") == "player" for d in drafts for e in d["event"]["effects"])
    assert not knows(WORLD, s, "player", "fact.storm")


def test_lived_counts_the_rain_for_the_wedding_guests() -> None:
    """lived() from the contract 1.12 addendum: the sister and the groom at the wedding did not take part in beat.12,
    but the downpour has no participants and falls in the same scene (scene.village), so it counts as lived through;
    beats they took part in count as usual. The king in the city and the guards at the execution ground do not.

    契約 1.12 補足の lived()：婚礼にいる妹と花婿は beat.12 に参加していないが、大雨には参加人物がなく同じシーン
    （scene.village）に落ちるので、体験したとみなす。参加したビートは従来どおり数える。都の王や刑場の警吏は数えない。
    """
    _, s = settle(WORLD, at(WEDDING), 3660)
    # beat.11 brings him to the wedding
    # beat.11 が彼を婚礼へ連れていく
    assert place_at(WORLD, s, "char.groom", RAIN) == WEDDING
    # The place before the beat, not including this beat
    # このビートを含まない、ビート前の場所
    assert place_at(WORLD, s, "char.groom", "beat.10") == GROOM
    for who in ("char.sister", "char.groom", "char.melos"):
        assert lived(WORLD, s, who, RAIN)
    assert lived(WORLD, s, "char.sister", "beat.11")
    assert not lived(WORLD, s, "char.king", RAIN)
    assert not lived(WORLD, s, "char.guards", RAIN)


def test_lived_is_not_presence() -> None:
    """lived() does not count "being at the beat's place": what a character knows follows knows and learn, and a beat
    they were present at but did not take part in is not given to them (contract 2.1 ②).
    Beats that did not happen, and the player, are both False.

    lived() は「ビートの場所にいた」ことを数えない：登場人物が何を知るかは knows と learn に従い、在場しただけで
    参加していないビートは渡さない（契約 2.1 ②）。
    起きていないビートもプレイヤーもどちらも False。
    """
    _, s = settle(WORLD, at(WEDDING), 3660)
    # beat.09 is at her house; only Melos takes part
    # beat.09 は彼女の家で、参加はメロスだけ
    assert place_at(WORLD, s, "char.sister", "beat.09") == WEDDING
    assert not lived(WORLD, s, "char.sister", "beat.09")
    assert not lived(WORLD, s, "char.sister", "beat.13")  # Not yet happened at 3660 / 3660 の時点ではまだ起きていない
    assert place_at(WORLD, s, "char.sister", "beat.13") is None
    assert not lived(WORLD, s, "player", RAIN)
    assert place_at(WORLD, s, "player", RAIN) is None
