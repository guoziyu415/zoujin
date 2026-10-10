"""快照里的位置点怎么分（前端 assets/pipeline/plaza/README.md 的规则）：人物按布局顺序站第一个空着的，
`way.*` 和 `auto: false` 的除外；玩家站的算占着。"""

from __future__ import annotations

import json
from pathlib import Path

from zoujin_backend.world import Scene

GROUND = "place.execution-ground"
SQUARE = "place.syracuse-square"


def scene(tmp_path: Path) -> Scene:
    doc = {
        "sceneId": "scene.test",
        "defaultPlace": SQUARE,
        "places": [{"id": SQUARE}, {"id": GROUND}],
        "spots": {
            "way.castle": {"place": GROUND},
            "stake": {"place": GROUND, "auto": False},
            "stake-front": {"place": GROUND},
            "ground-west": {"place": GROUND},
            "king-west": {"place": GROUND, "auto": False},
            "fountain": {"place": SQUARE},
        },
        "exits": [{"place": "place.castle", "spot": "way.castle"}],
        "startSpots": {SQUARE: "fountain"},
    }
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return Scene.read(path)


def test_automatic_placement_skips_way_and_manual_spots(tmp_path: Path) -> None:
    s = scene(tmp_path)
    assert s.manual == {"stake", "king-west"}
    assert s.auto_spots(GROUND) == ["stake-front", "ground-west"]
    assert s.player_spot(GROUND) == "stake-front"  # 没有 startSpots 时：第一个能自动用的
    people = [("char.old-man", GROUND), ("char.melos", GROUND), ("char.king", GROUND)]
    assert s.character_spots(people, {"stake-front"}) == {
        "char.old-man": "ground-west",
        "char.melos": "ground-west",  # 不够了和别的人物重叠，不站到 stake、king-west、玩家身上
        "char.king": "ground-west",
    }


def test_fallbacks(tmp_path: Path) -> None:
    s = scene(tmp_path)
    # 这个地点只有玩家站的那一个点：只能重叠
    assert s.character_spots([("char.old-man", SQUARE)], {"fountain"}) == {"char.old-man": "fountain"}
    # 布局里没有这个地点：用地点 ID 的最后一段
    assert s.character_spots([("char.melos", "place.castle")]) == {"char.melos": "castle"}
    assert s.player_spot("place.castle") == "castle"
