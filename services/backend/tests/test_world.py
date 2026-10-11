"""快照里的位置点怎么分（前端 assets/pipeline/plaza/README.md 的规则）：人物按布局顺序站第一个空着的，
`way.*` 和 `auto: false` 的除外；玩家站的算占着。开新局用哪个世界模型。下发的事件句里玩家写成「あなた」。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from zoujin_backend.config import DEFAULT_WORLD, REPO, ConfigError, world_path
from zoujin_backend.world import Library, Scene

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


# —— 开新局用哪个世界模型（数据评审 #26：不按目录排序，按配置）——


def later_world(tmp_path: Path) -> Path:
    """一份目录名排在草稿后面的世界模型（像以后的 1.0.0-slice）。"""
    w = json.loads(DEFAULT_WORLD.read_text(encoding="utf-8"))
    w["worldModelVersion"] = "hashire-merosu@9.9.9-test"
    path = tmp_path / "worlds" / "hashire-merosu" / "9.9.9-test" / "world.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    return path


def test_new_playthroughs_use_the_configured_world_not_the_last_directory(tmp_path: Path) -> None:
    later = later_world(tmp_path)
    for p in sorted((REPO / "worlds").glob("*/*/world.json")):  # 仓库里的也在
        dst = tmp_path / "worlds" / p.relative_to(REPO / "worlds")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(p.read_bytes())
    scenes = REPO / "assets" / "scenes"
    lib = Library(tmp_path / "worlds", scenes, world_path({}))
    draft = json.loads(DEFAULT_WORLD.read_text(encoding="utf-8"))["worldModelVersion"]
    assert lib.current.version == draft
    book = lib.book("hashire-merosu")
    assert book is not None and book.version == draft
    assert lib.book("no-such-book") is None
    assert lib.version("hashire-merosu@9.9.9-test").version == "hashire-merosu@9.9.9-test"  # 已有的局照样查得到

    lib = Library(REPO / "worlds", scenes, world_path({"ZJ_WORLD": str(later)}))  # 仓库外的文件也行
    assert lib.current.version == "hashire-merosu@9.9.9-test"
    assert lib.version(draft).version == draft


def test_zj_world_must_be_an_absolute_path_to_a_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="绝对路径"):
        world_path({"ZJ_WORLD": "worlds/hashire-merosu/1.0.0-draft/world.json"})
    with pytest.raises(ConfigError, match="不存在"):
        world_path({"ZJ_WORLD": str(tmp_path / "nope.json")})


def test_delivered_lines_call_the_player_anata() -> None:
    """下发的事件句里玩家是「あなた」（UX 10-10）；名字里含身份名的人物不换；period 只在没有句末标点时补「。」。"""
    from zoujin_backend.projection import as_you

    from .conftest import BOOK

    assert as_you(BOOK, "role.traveler", "旅人は、老爺を家まで送ることにした") == "あなたは、老爺を家まで送ることにした"
    assert as_you(BOOK, "role.traveler", "メロスが走り出した。", period=True) == "メロスが走り出した。"
    assert as_you(BOOK, "role.traveler", "旅人は刑場へ移った", period=True) == "あなたは刑場へ移った。"
    assert as_you(BOOK, "role.traveler", "", period=True) == ""


def test_characters_whose_name_holds_the_role_name_are_kept() -> None:
    """契约 1.8 起世界模型里的人物名不再含身份名（数据的自检），这里用自己搭的一本书查兜底。"""
    from types import SimpleNamespace

    from zoujin_backend.projection import as_you
    from zoujin_backend.world import Book

    book = cast(
        Book,
        SimpleNamespace(
            roles={"role.guard": {"name": "警吏"}},
            characters={"char.guards": {"name": "警吏（巡邏・刑吏）"}, "char.chief": {"name": "警吏長"}},
        ),
    )
    out = as_you(book, "role.guard", "警吏は警吏長と警吏（巡邏・刑吏）に話した", period=True)
    assert out == "あなたは警吏長と警吏（巡邏・刑吏）に話した。"


def test_commit_events_call_the_player_anata_without_a_period() -> None:
    from zoujin_backend.projection import visible_event

    from .conftest import BOOK

    ev = {
        "eventId": "evt_test",
        "seq": 3,
        "t": 0,
        "dt": 0,
        "type": "action",
        "actor": "player",
        "place": GROUND,
        "summary": "旅人は警吏に名を告げた",
        "causes": [],
        "effects": [],
        "keyMoment": False,
    }
    out = visible_event(BOOK, ev, "role.traveler")
    assert out["summary"] == "あなたは警吏に名を告げた" and ev["summary"] == "旅人は警吏に名を告げた"


def test_recap_lines_call_the_player_anata_with_a_period() -> None:
    """「その頃」：line 用 summary，玩家写成「あなた」、句末补「。」。"""
    from zoujin_backend.narrator.acts import recap

    from .conftest import BOOK

    passed = {"status": "passed"}
    skipped: list[dict[str, Any]] = [
        {
            "eventId": "evt_a",
            "type": "beat",
            "actor": "char.melos",
            "summary": "メロスが走り出した。",
            "check": passed,
            "keyMoment": True,
            "effects": [],
        },
        {
            "eventId": "evt_b",
            "type": "action",
            "actor": "char.old-man",
            "origin": "plan",
            "check": passed,
            "summary": "市の老爺が旅人のことを町の人に話した",
            "effects": [],
        },
    ]
    lines = [r["line"] for r in recap(BOOK, "role.traveler", skipped, {"char.old-man"}, set())]
    assert lines == ["メロスが走り出した。", "市の老爺があなたのことを町の人に話した。"]
