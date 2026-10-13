"""pick_set_piece() (contract 1.7, 2.11): tested by attaching to the full draft a set of set pieces written the same
way as the slice's. For knows(), see test_primitives.

pick_set_piece()（契約 1.7、2.11）：完全版のドラフトに、スライスと同じ書き方の固定演出一式を付けてテストする。
knows() は test_primitives を参照。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zoujin_worldsim import SimState, apply, initial_state, pick_set_piece, settle

REPO = Path(__file__).resolve().parents[3]
WORLD = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
ROLE = "role.traveler"
GROUND = "place.execution-ground"
GATE = {"act": "go", "target": "place.castle", "refused": True}
NARRATE = [{"narration": "…"}]


def piece(id_: str, on: dict[str, Any], **kw: Any) -> dict[str, Any]:
    return {"id": id_, "on": on, **kw, "lines": NARRATE, "inferred": True}


PIECES = [
    piece("piece.gate-taken-again", {"beat": "beat.04"}, played=["piece.gate-turned-away"], once=True),
    piece("piece.gate-taken", {"beat": "beat.04"}, once=True),
    piece(
        "piece.gate-again",
        GATE,
        played=["piece.gate-taken", "piece.gate-turned-away"],
        notPlayed=["piece.gate-taken-again"],
        once=True,
    ),
    piece("piece.gate-turned-away", GATE, before=["beat.04"], once=True),
    piece("piece.crowd", {"beat": "beat.24"}, knows=[{"character": "char.crowd", "fact": "fact.promise"}]),
    piece("piece.any-help", {"act": "help"}, when=[{"var": "var.player.custody", "op": "==", "value": "free"}]),
    piece("piece.rain", {"beat": "beat.12"}),
]
W: dict[str, Any] = {**json.loads(WORLD.read_text(encoding="utf-8")), "setPieces": PIECES}


def at(place: str, t: int) -> SimState:
    """The traveler walks from the opening to place, settled to t.

    旅人がオープニングから place へ歩き、t まで精算する。
    """
    s = initial_state(W, ROLE)
    s = apply(W, s, {"t": 0, "dt": 0, "origin": "turn",
                     "effects": [{"op": "set", "var": "var.player.location", "value": place}]})  # fmt: skip
    _, s = settle(W, s, t)
    return s


def pick(s: SimState, hook: dict[str, Any], played: set[str]) -> str | None:
    p = pick_set_piece(W, s, hook, played)
    return None if p is None else p["id"]


def test_beat_pieces_play_only_when_the_player_is_at_the_beat() -> None:
    s = at(GROUND, 1201)
    assert s["beats"]["beat.04"] == "happened"
    assert pick(s, {"beat": "beat.04"}, set()) == "piece.gate-taken"
    assert pick(s, {"beat": "beat.04"}, {"piece.gate-taken"}) is None  # once
    assert pick(at("place.syracuse-square", 1201), {"beat": "beat.04"}, set()) is None


def test_open_air_beat_pieces_play_in_the_same_scene() -> None:
    """Contract 1.12: the downpour of beat.12 has no participants and falls on place.village. It also plays at the
    wedding (place.melos-home, the same scene), but not in another scene (シラクスの市). The same rule (sees) as
    settle writing learn and the backend pushing events.

    契約 1.12：beat.12 の大雨には参加人物がなく、place.village に落ちる。婚礼の場（place.melos-home、同じシーン）
    でも上演し、別のシーン（シラクスの市）では上演しない。settle の learn 書き込み、バックエンドのイベントの
    プッシュと同じルール（sees）。
    """
    assert pick(at("place.village", 0), {"beat": "beat.12"}, set()) == "piece.rain"
    assert pick(at("place.melos-home", 0), {"beat": "beat.12"}, set()) == "piece.rain"
    assert pick(at("place.syracuse-square", 0), {"beat": "beat.12"}, set()) is None


def test_the_gate_in_both_orders() -> None:
    """Arrested first, then walking up: 下がれ (the arrest scene) → 二度は言わぬ → narrator.
    Walking up first, then the arrest: 下がれ → 二度は言わぬ (the arrest scene) → narrator (UX 10-10).

    先に捕まってから近づく：下がれ（捕縛の場面）→ 二度は言わぬ → ナレーター。
    先に近づいてから捕まる：下がれ → 二度は言わぬ（捕縛の場面）→ ナレーター（UX 10-10）。
    """
    before, after = at(GROUND, 600), at(GROUND, 1201)
    played: set[str] = set()
    for s, hook, want in [
        (after, {"beat": "beat.04"}, "piece.gate-taken"),
        (after, GATE, "piece.gate-again"),
        (after, GATE, None),
    ]:
        got = pick(s, hook, played)
        assert got == want
        played |= {got} if got else set()
    played = set()
    for s, hook, want in [
        (before, GATE, "piece.gate-turned-away"),
        (after, {"beat": "beat.04"}, "piece.gate-taken-again"),
        (after, GATE, None),
    ]:
        got = pick(s, hook, played)
        assert got == want
        played |= {got} if got else set()
    assert pick(before, {**GATE, "refused": False}, set()) is None  # Only when refused / 拒否されたときだけ
    assert pick(before, {**GATE, "target": "place.road-to-city"}, set()) is None


def test_knows_and_when_conditions() -> None:
    s = at(GROUND, 5461)
    assert s["beats"]["beat.24"] == "happened"
    assert pick(s, {"beat": "beat.24"}, set()) is None  # The crowd did not know the promise / 群衆は約束を知らない
    s = apply(W, s, {"t": s["t"], "dt": 0, "origin": "turn",
                     "effects": [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}]})  # fmt: skip
    assert pick(s, {"beat": "beat.24"}, set()) == "piece.crowd"
    # No target written = the target is not checked / target なし = 対象を見ない
    assert pick(s, {"act": "help", "target": "char.old-man"}, set()) == "piece.any-help"
    assert pick(s, {"act": "help", "refused": True}, set()) is None
