"""How spots are assigned in the snapshot (the rule in the frontend's assets/pipeline/plaza/README.md): characters
take the first free spot in layout order, except `way.*` and `auto: false` ones; the player's spot counts as taken.
Which world model new games use. In delivered event sentences the player is written as 「あなた」.

スナップショットでの立ち位置の割り当て（フロントエンドの assets/pipeline/plaza/README.md の規則）：登場人物は
レイアウト順に最初の空いた立ち位置に立ち、`way.*` と `auto: false` のものは除く。プレイヤーの立ち位置は埋まっている
とみなす。新しいゲームでどの世界モデルを使うか。送るイベント文ではプレイヤーを「あなた」と書く。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from zoujin_backend.config import DEFAULT_WORLD, REPO, ConfigError, released_worlds, world_path
from zoujin_backend.narrator.writer import SCHEMA_VERSION
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
    # Without startSpots: the first auto-assignable one / startSpots がないとき：自動で使える最初のもの
    assert s.player_spot(GROUND) == "stake-front"
    people = [("char.old-man", GROUND), ("char.melos", GROUND), ("char.king", GROUND)]
    assert s.character_spots(people, {"stake-front"}) == {
        "char.old-man": "ground-west",
        # Out of spots: overlap with other characters, never on stake, king-west or the player.
        # 足りなければほかの登場人物と重なり、stake、king-west、プレイヤーの上には立たない。
        "char.melos": "ground-west",
        "char.king": "ground-west",
    }


def test_fallbacks(tmp_path: Path) -> None:
    s = scene(tmp_path)
    # This place only has the player's spot: overlapping is the only option.
    # この場所にはプレイヤーの立ち位置しかない：重なるしかない。
    assert s.character_spots([("char.old-man", SQUARE)], {"fountain"}) == {"char.old-man": "fountain"}
    # The place isn't in the layout: use the last segment of the place ID.
    # レイアウトにこの場所がない：場所 ID の最後の部分を使う。
    assert s.character_spots([("char.melos", "place.castle")]) == {"char.melos": "castle"}
    assert s.player_spot("place.castle") == "castle"


# —— Which world model new games use (data review #26: by configuration, not directory order) ——
# —— 新しいゲームでどの世界モデルを使うか（データレビュー #26：ディレクトリの並び順ではなく設定で決める） ——


def later_world(tmp_path: Path) -> Path:
    """A world model whose directory name sorts after the draft (like a later 1.0.0-slice).

    ディレクトリ名が草稿より後に並ぶ世界モデル（将来の 1.0.0-slice のようなもの）。
    """
    w = json.loads(DEFAULT_WORLD.read_text(encoding="utf-8"))
    w["worldModelVersion"] = "hashire-merosu@9.9.9-test"
    path = tmp_path / "worlds" / "hashire-merosu" / "9.9.9-test" / "world.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    return path


def test_new_playthroughs_use_the_configured_world_not_the_last_directory(tmp_path: Path) -> None:
    later = later_world(tmp_path)
    for p in sorted((REPO / "worlds").glob("*/*/world.json")):  # the repo's are there too / リポジトリのものもある
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
    # Existing games can still look it up / 既存のゲームは従来どおり引ける
    assert lib.version("hashire-merosu@9.9.9-test").version == "hashire-merosu@9.9.9-test"

    # A file outside the repo works too / リポジトリの外のファイルでもよい
    lib = Library(REPO / "worlds", scenes, world_path({"ZJ_WORLD": str(later)}))
    assert lib.current.version == "hashire-merosu@9.9.9-test"
    assert lib.version(draft).version == draft


def test_zj_world_must_be_an_absolute_path_to_a_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="absolute path"):
        world_path({"ZJ_WORLD": "worlds/hashire-merosu/1.0.0-draft/world.json"})
    with pytest.raises(ConfigError, match="does not exist"):
        world_path({"ZJ_WORLD": str(tmp_path / "nope.json")})


def test_extra_books_are_explicit_and_do_not_replace_pinned_versions(tmp_path: Path) -> None:
    w = json.loads(DEFAULT_WORLD.read_text())
    w["book"]["id"] = "test-book"
    w["worldModelVersion"] = "test-book@1.0.0"
    p = tmp_path / "world.json"
    p.write_text(json.dumps(w))
    release = released_worlds({"ZJ_WORLDS": json.dumps([str(p)])})
    lib = Library(REPO / "worlds", REPO / "assets/scenes", DEFAULT_WORLD, release)
    assert set(lib.available) == {"hashire-merosu", "test-book"}
    assert lib.book("test-book") is lib.version("test-book@1.0.0")
    assert lib.book("hashire-merosu") is lib.current
    with pytest.raises(ValueError, match="Duplicate open book"):
        Library(REPO / "worlds", REPO / "assets/scenes", DEFAULT_WORLD, (DEFAULT_WORLD,))
    for invalid in ("{}", '"no"', "[1]", '["relative.json"]', "not json"):
        with pytest.raises(ConfigError):
            released_worlds({"ZJ_WORLDS": invalid})
    w["worldModelVersion"] = lib.current.version
    p.write_text(json.dumps(w))
    with pytest.raises(ValueError, match="reused by different books"):
        Library(REPO / "worlds", REPO / "assets/scenes", DEFAULT_WORLD, (p,))


def test_workshop_has_separate_positions_for_every_individual_and_player() -> None:
    lib = Library(REPO / "worlds", REPO / "assets/scenes", DEFAULT_WORLD)
    book = lib.current
    scene = lib.layouts["scene.syracuse-square"]
    place = "place.stonemason-workshop"
    people = [(cid, place) for cid, c in book.characters.items() if not c.get("group")]
    player = scene.player_spot(place)
    placed = scene.character_spots(people, {player})
    assert len(set(placed.values())) == len(people)
    assert player not in placed.values() and "workshop-door" not in placed.values()
    # Don't just compare IDs: the real generated coordinates must also be apart, leaving at least 1.2 m for the
    # characters' bodies and small movements.
    # ID を比べるだけでなく、実際に生成した座標も互いに離れていること。
    # 登場人物の体と小さな動きのために少なくとも 1.2m 空ける。
    doc = json.loads((REPO / "assets/scenes/syracuse-square/scene.json").read_text())
    spots = [doc["spots"][s] for s in [player, *placed.values()]]
    from math import hypot

    for i, left in enumerate(spots):
        assert left["place"] == place
        for right in spots[i + 1 :]:
            assert hypot(left["pos"][0] - right["pos"][0], left["pos"][2] - right["pos"][2]) >= 1.2


def test_delivered_lines_call_the_player_anata() -> None:
    """In delivered event sentences the player is 「あなた」 (UX 10-10); characters whose names contain the role name
    are left alone; period only adds 「。」 when there is no sentence-final punctuation.

    送るイベント文ではプレイヤーは「あなた」（UX 10-10）。名前に役柄名を含む登場人物は置き換えない。period は
    文末に句読点がないときだけ「。」を補う。
    """
    from zoujin_backend.projection import as_you

    from .conftest import BOOK

    assert as_you(BOOK, "role.traveler", "旅人は、老爺を家まで送った") == "あなたは、老爺を家まで送った"
    assert as_you(BOOK, "role.traveler", "メロスが走り出した。", period=True) == "メロスが走り出した。"
    assert as_you(BOOK, "role.traveler", "旅人は刑場へ移った", period=True) == "あなたは刑場へ移った。"
    assert as_you(BOOK, "role.traveler", "", period=True) == ""


def test_characters_whose_name_holds_the_role_name_are_kept() -> None:
    """Since contract 1.8, character names in world models no longer contain role names (the data self-check), so this
    checks the fallback with a hand-built book.

    契約 1.8 以降、世界モデルの登場人物名に役柄名は含まれない（データのセルフチェック）ので、ここでは自前で組んだ本で
    保険を確かめる。
    """
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
    """「その頃」: line uses summary, with the player written as 「あなた」 and 「。」 added at the end.

    「その頃」：line は summary を使い、プレイヤーは「あなた」と書き、文末に「。」を補う。
    """
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


def test_events_are_written_with_the_newest_contract_version() -> None:
    """The `SCHEMA_VERSION` used to write events follows the contract: it is the newest in `SchemaVersion`, and also
    the version the repo's world model is written in. When the data side bumps the contract this goes red, reminding
    the backend to bump along.

    イベントを書くときの `SCHEMA_VERSION` は契約に従う：`SchemaVersion` の最新のもので、リポジトリの世界モデルが
    書かれたバージョンでもある。データ側が契約を上げるとこれが赤くなり、バックエンドも一緒に上げるよう知らせる。
    """
    common = json.loads((REPO / "packages/contracts/schemas/data/common.schema.json").read_text(encoding="utf-8"))
    assert SCHEMA_VERSION == common["$defs"]["SchemaVersion"]["enum"][-1]
    world = json.loads(DEFAULT_WORLD.read_text(encoding="utf-8"))
    assert SCHEMA_VERSION == world["schemaVersion"]


def test_weather_beats_are_seen_from_anywhere_in_the_same_scene() -> None:
    """Data contract 1.12: a beat without participating characters (beat.12, the heavy rain at place.village) is
    pushed anywhere in the same scene (scene.village); not in other scenes or at places without a scene; beats with
    participants still require being at their place; what the player does is still pushed; rejected ones aren't.

    データ契約 1.12：参加する登場人物のいないビート（beat.12 の大雨、place.village）は同じ場面（scene.village）なら
    どこでもプッシュする。別の場面や場面のない場所ではしない。参加者のいるビートは従来どおりその場所にいる必要がある。
    プレイヤーがしたことは従来どおりプッシュする。却下されたものはしない。
    """
    from zoujin_backend.projection import is_visible

    draft = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
    book = Library(REPO / "worlds", REPO / "assets" / "scenes", draft).current

    def beat(b: str, place: str, status: str = "passed") -> dict[str, Any]:
        return {
            "actor": "system",
            "place": place,
            "effects": [{"op": "beat", "beat": b, "to": "happened"}],
            "check": {"status": status},
        }

    rain = beat("beat.12", "place.village")
    assert is_visible(book, rain, "place.village")
    assert is_visible(book, rain, "place.melos-home")  # same scene / 同じ場面
    assert not is_visible(book, rain, "place.river")  # another scene / 別の場面
    # The beat's place has no scene / ビートの場所に場面がない
    assert not is_visible(book, beat("beat.15", "place.neighbor-village"), "place.village")
    # Has participants: must be at its place / 参加者がいる：その場所にいる必要がある
    wedding = beat("beat.13", "place.melos-home")
    assert book.beats["beat.13"]["participants"]
    assert is_visible(book, wedding, "place.melos-home")
    assert not is_visible(book, wedding, "place.village")
    assert is_visible(book, {**wedding, "actor": "player"}, "place.river")
    assert not is_visible(book, beat("beat.12", "place.village", "rejected"), "place.village")
