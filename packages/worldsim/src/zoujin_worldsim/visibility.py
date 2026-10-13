"""Whether the player can see an event (contract 1.12, section 3 "which changes the player can see", 2.1 ②, 2.11).

The rule is written only here and all three places use it: settle writing learn for the player (_occur_draft), whether
the backend pushes the event (projection.is_visible), and whether the player counts as present at a set piece on a
beat. If the three each wrote their own, you would get rain pushed without telling the player, or the player told
without the rain being pushed.

Checked in order: ① the player did the event ② the player is at the event's place ③ the event is a beat with no
participants (weather, natural disasters: in 『走れメロス』 beat.12 大雨, beat.15 雨が上がる, beat.17 濁流) that falls
in the same scene as the player: both places have a sceneRef that is non-empty and the same.
In step 3 of an act switch (settle with player_present=False) the player always counts as absent; callers do not ask
here.

プレイヤーがあるイベントを見られるか（契約 1.12、第 3 節「プレイヤーに見える変化」、2.1 ②、2.11）。

ルールはここに 1 つだけ書き、3 か所すべてがこれを使う：settle がプレイヤーに learn を書く（_occur_draft）、
バックエンドがそのイベントをプッシュするか（projection.is_visible）、ビート上の固定演出でプレイヤーが在場と
みなされるか。3 か所がそれぞれ別に書くと、雨をプッシュしたのにプレイヤーに知らせない、あるいはプレイヤーに
知らせたのに雨をプッシュしない、ということが起きる。

順に見る：① イベントはプレイヤーが起こした ② プレイヤーがイベントの場所にいる ③ イベントが参加人物のない
ビート（天候、天災。『走れメロス』の beat.12 大雨、beat.15 雨が上がる、beat.17 濁流）で、プレイヤーと同じ
シーンに落ちる：2 つの場所の sceneRef がどちらも空でなく、かつ同じ。
幕切り替えの第 3 段階（settle の player_present=False）ではプレイヤーは常に不在とみなし、呼び出し側はここに
問い合わせない。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .sim import World


def same_scene(world: World, a: str, b: str) -> bool:
    """Two places are in the same scene: both sceneRefs are non-empty and equal (a place with no scene is not in the
    same scene as anything, not even itself).

    2 つの場所が同じシーンにある：両方の sceneRef が空でなく、かつ同じ（シーンのない場所はどこと同じシーンにも
    ならず、自分自身とも同じにならない）。
    """
    scenes = {p["id"]: p.get("sceneRef") for p in world["places"]}
    sa, sb = scenes.get(a), scenes.get(b)
    return sa is not None and sa == sb


def open_air(world: World, beat: str) -> bool:
    """A beat with no participants (weather, natural disasters): everyone in the same scene can see it.

    参加人物のないビート（天候、天災）：同じシーンにいる人には皆見える。
    """
    return any(b["id"] == beat and not b["participants"] for b in world["beats"])


def sees(world: World, player_place: str | None, event: Mapping[str, Any]) -> bool:
    """Whether the player at player_place (var.player.location before the event) can see event (needs actor, place,
    effects).

    プレイヤーが player_place（イベント前の var.player.location）にいるとき、event（actor、place、effects が必要）を
    見られるか。
    """
    if event.get("actor") == "player":
        return True
    place = event.get("place")
    if place is None or player_place is None:
        return False
    if place == player_place:
        return True
    return same_scene(world, place, player_place) and any(
        e.get("op") == "beat" and open_air(world, e.get("beat", "")) for e in event.get("effects", ())
    )
