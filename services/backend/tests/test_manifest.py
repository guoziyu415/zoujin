"""B-7: the manifest generator (`manifest.py`), the production gateway's route, and the mock using the same
generator (the card's acceptance checks 1–6).

Offline: the world model and the square's `scene.json` come from the repo; the scene pack directory and the voice
manifest are built in the test's temporary directory.

B-7：manifest の生成器（`manifest.py`）、本番のゲートウェイのルート、mock が同じ生成器を使うこと（カードの受け入れ確認
第 1〜6 項）。

ネットワークなし：世界モデルと広場の `scene.json` はリポジトリのものを使い、シーンパックのディレクトリと音声マニフェスト
はテストの一時ディレクトリに作る。
"""

from __future__ import annotations

import copy
import json
import logging
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from zoujin_backend.config import DEFAULT_WORLD, REPO, ConfigError, Settings
from zoujin_backend.gateway import app as gateway_app
from zoujin_backend.manifest import CACHE, FILE_CACHE, ManifestError, generate, scene_packs
from zoujin_backend.mock.app import create_app as mock_app
from zoujin_backend.mock.core import Config
from zoujin_backend.narrator import app as narrator_app
from zoujin_backend.narrator.core import Narrator
from zoujin_backend.world import Book

from .conftest import SCHEMAS, Env
from .test_gateway import invite

Json = Any

SLICE = REPO / "worlds" / "hashire-merosu" / "1.0.0-slice" / "world.json"
SQUARE = REPO / "assets" / "scenes" / "syracuse-square" / "scene.json"
BOOK = "hashire-merosu"


def world(path: Path = DEFAULT_WORLD) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def book(w: Json, path: Path | None = None) -> Book:
    return Book(book_id=w["book"]["id"], world=w, path=path)


def packs(tmp: Path, *extra: str, index: bool = False) -> Path:
    """Scene pack directory: the square as in the repo, plus a scene.json for each `extra` scene (its content is just
    the scene name).

    シーンパックのディレクトリ：広場はリポジトリのとおり。`extra` のシーンにはそれぞれ scene.json を 1 つ置く（中身は
    シーン名だけ）。
    """
    root = tmp / "packs"
    (root / "syracuse-square").mkdir(parents=True)
    shutil.copy(SQUARE, root / "syracuse-square" / "scene.json")
    if index:
        (root / "syracuse-square" / "index.json").write_text('{"files": []}', encoding="utf-8")
    for name in extra:
        (root / name).mkdir()
        (root / name / "scene.json").write_text(json.dumps({"sceneId": f"scene.{name}"}), encoding="utf-8")
    return root


def make(w: Json, tmp: Path, *, packs_dir: Path | None = None, voices: Path | None = None, release: int = 1) -> Json:
    m = generate(book(w), SCHEMAS, packs=packs_dir or packs(tmp), voices=voices or tmp / "no-voice", release=release)
    return m.doc


def valid(doc: Json) -> None:
    assert SCHEMAS.errors("api/rest/manifest.schema.json", "#/$defs/ManifestResponse", doc) == []


# —— Voice manifest: B-6's format, the recording files are a few bytes ——
# —— 音声マニフェスト：B-6 の形式、録音ファイルは数バイト ——


def clip(root: Path, name: str, text: str) -> Json:
    (root / BOOK).mkdir(parents=True, exist_ok=True)
    (root / BOOK / f"{name}.m4a").write_bytes(name.encode())
    return {"url": f"/assets/voice/{BOOK}/{name}.m4a", "text": text, "durationMs": 800}


def six(root: Path, who: str) -> Json:
    return {
        "aizuchi": [clip(root, f"{who}-a{i}", "うむ。") for i in (1, 2, 3)],
        "unheard": [clip(root, f"{who}-u{i}", "……もう一度。") for i in (1, 2)],
        "wait": clip(root, f"{who}-w", "待ってくれ。"),
        "cues": {},
    }


def speaker_lines(w: Json) -> dict[str, str]:
    """Characters' set-piece lines in the slice: key "{set piece ID}/{number}" → text.

    スライスの固定演出での人物のセリフ：キー「{固定演出 ID}/{番号}」→ 文字。
    """
    return {f"{p['id']}/{i}": x["line"] for p in w["setPieces"] for i, x in enumerate(p["lines"], 1) if "speaker" in x}


def voices(tmp: Path, w: Json, edit: Any = None) -> Path:
    root = tmp / "voice"
    cue = w["clock"]["deadline"]["earliestArrivalCue"]
    doc: Json = {
        "worldModelVersion": w["worldModelVersion"],
        "characters": {
            "char.melos": six(root, "melos"),
            "char.old-man": six(root, "old-man"),
            "char.philostratus": six(root, "philostratus"),
        },
        "setPieceVoices": {k: clip(root, k.replace("/", "-"), v) for k, v in speaker_lines(w).items()},
    }
    doc["characters"]["char.melos"]["cues"]["arrival_capped"] = clip(root, "melos-arrival", cue["line"])
    if edit is not None:
        edit(doc, root)
    (root / BOOK / "voices.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return root


def written(root: Path) -> Json:
    return json.loads((root / BOOK / "voices.json").read_text(encoding="utf-8"))


# —— 1. Generation rules / 生成の規則 ——


@pytest.mark.parametrize("path", [DEFAULT_WORLD, SLICE], ids=["draft", "slice"])
def test_both_world_models_give_a_valid_manifest_by_the_2_1_rules(tmp_path: Path, path: Path) -> None:
    w = world(path)
    doc = make(w, tmp_path)
    valid(doc)
    places = {p["id"]: p for p in w["places"]}
    for s in doc["scenes"]:
        assert s["places"] == [p["id"] for p in w["places"] if p.get("sceneRef") == s["sceneId"]]
    for r in doc["roles"]:
        role = next(x for x in w["roles"] if x["id"] == r["roleId"])
        assert r["startSceneId"] == places[role["startPlace"]]["sceneRef"]
        assert r["startActId"] == role["startAct"] and r["summary"] == role["summary"]
    shown = {s["sceneId"] for s in doc["scenes"]}
    # v1.0.14: names of all places; sceneId is null when the scene is left out
    # v1.0.14：すべての場所の地名。シーンを出さないものは sceneId が null
    assert doc["places"] == [
        {"placeId": p["id"], "name": p["name"], "sceneId": p["sceneRef"] if p.get("sceneRef") in shown else None}
        for p in w["places"]
    ]
    for a in doc["acts"]:
        act = next(x for x in w["acts"] if x["id"] == a["actId"])
        assert a["sceneIds"] == [x for x in act["scenes"] if x in shown]
    assert [c["id"] for c in doc["characters"]] == [c["id"] for c in w["characters"]]
    assert doc["book"] == {k: w["book"][k] for k in ("id", "title", "author")}
    assert doc["clock"] == {
        "deadlineT": w["clock"]["deadline"]["t"],
        "sunsetMinuteOfDay": w["clock"]["sunsetMinuteOfDay"],
        "days": w["clock"]["labels"]["days"],
    }
    assert doc["ruby"] == w["ruby"]
    assert doc["manifestVersion"].startswith(w["worldModelVersion"] + "+")
    text = json.dumps(doc, ensure_ascii=False)
    # The world model's internal fields and variables are not exposed / 世界モデルの内部フィールドと変数は出さない
    for internal in ('"note"', '"cite"', '"inferred"', "var."):
        assert internal not in text


def test_draft_release_1_only_roles_whose_start_scene_has_a_pack(tmp_path: Path) -> None:
    w = world()
    doc = make(w, tmp_path)
    # The shepherd boy's village has no pack, and release 2 is left out / 牧童の村にはパックがなく、release 2 は出さない
    assert [r["roleId"] for r in doc["roles"]] == ["role.traveler", "role.apprentice"]
    assert [s["sceneId"] for s in doc["scenes"]] == ["scene.syracuse-square"]
    assert all(a["sceneIds"] == ["scene.syracuse-square"] for a in doc["acts"])
    # The castle has no pack: the maid and the guard are still left out
    # 王城にはパックがない：侍女と警吏はやはり出さない
    assert make(w, tmp_path / "2", release=2)["roles"] == doc["roles"]


def test_a_castle_pack_brings_in_the_castle_scene_and_its_roles(tmp_path: Path) -> None:
    w = world()
    doc = make(w, tmp_path, packs_dir=packs(tmp_path, "castle-throne"), release=2)
    valid(doc)
    castle = next(s for s in doc["scenes"] if s["sceneId"] == "scene.castle-throne")
    assert castle["places"] == ["place.castle"]
    assert {
        "placeId": "place.castle",
        "name": next(p["name"] for p in w["places"] if p["id"] == "place.castle"),
        "sceneId": "scene.castle-throne",
    } in doc["places"]
    version = castle["assetVersion"]
    assert len(version) == 8 and castle["assetUrl"] == f"/scenes/{version}/castle-throne/scene.json"
    assert next(a for a in doc["acts"] if a["actId"] == "act.1")["sceneIds"] == [
        "scene.syracuse-square",
        "scene.castle-throne",
    ]
    assert [r["roleId"] for r in doc["roles"]] == ["role.traveler", "role.apprentice", "role.castle-maid", "role.guard"]
    one = make(w, tmp_path / "1", packs_dir=packs(tmp_path / "1", "castle-throne"))  # ZJ_RELEASE=1
    assert [r["roleId"] for r in one["roles"]] == ["role.traveler", "role.apprentice"]


def test_index_json_wins_over_scene_json(tmp_path: Path) -> None:
    square = make(world(), tmp_path, packs_dir=packs(tmp_path, index=True))["scenes"][0]
    assert square["assetUrl"] == f"/scenes/{square['assetVersion']}/syracuse-square/index.json"


def road(root: Path, shared: list[str] | None = None, manifest: str = "../road-river-calm/scene.json") -> None:
    """The shape from #103: `index.json` lists only sibling packs' relative paths and shared packs, without sha
    (frontend 2 #114 review).

    #103 の形：`index.json` は兄弟パックの相対パスと共有パックだけを並べ、sha は持たない（フロントエンド 2 #114 の
    レビュー）。
    """
    for name in ("road-river", "road-river-calm", "road-river-flood", "road-common"):
        (root / name).mkdir(exist_ok=True)
    (root / "road-river-calm" / "scene.json").write_text('{"files": {"a.glb": "1"}}', encoding="utf-8")
    (root / "road-river-flood" / "scene.json").write_text('{"files": {"b.glb": "2"}}', encoding="utf-8")
    (root / "road-common" / "pack.json").write_text('{"textures": {}}', encoding="utf-8")
    (root / "road-common" / "tex").mkdir(exist_ok=True)
    (root / "road-common" / "tex" / "grass.ktx2").write_bytes(b"grass")
    index = {
        "packs": [
            {"pack": "road-river-calm", "act": "act.2", "manifest": manifest},
            {"pack": "road-river-flood", "act": "act.4", "manifest": "../road-river-flood/scene.json"},
        ],
        "sharedPacks": ["road-common"] if shared is None else shared,
    }
    (root / "road-river" / "index.json").write_text(json.dumps(index), encoding="utf-8")


def test_an_index_json_pack_versions_everything_it_reaches(tmp_path: Path) -> None:
    root = packs(tmp_path)
    road(root)
    found = scene_packs(root, ["scene.syracuse-square", "scene.road-river"])
    river = found["scene.road-river"]
    # The version comes first: `../road-river-calm/` lands under the same version, not out of bounds
    # バージョンが先頭にある：`../road-river-calm/` は同じバージョンの下に収まり、範囲外に出ない
    assert river.url == f"/scenes/{river.version}/road-river/index.json"
    assert river.dirs == ("road-river", "road-common", "road-river-calm", "road-river-flood")
    assert found["scene.syracuse-square"].dirs == ("syracuse-square",)
    # With index.json unchanged, any changed file in a sibling or shared pack changes the version
    # index.json が同じでも、兄弟パックや共有パックのどのファイルが変わってもバージョンが変わる
    calm = root / "road-river-calm" / "scene.json"
    calm.write_text('{"files": {"a.glb": "3"}}', encoding="utf-8")
    after = scene_packs(root, ["scene.road-river"])["scene.road-river"].version
    assert after != river.version
    (root / "road-common" / "tex" / "grass.ktx2").write_bytes(b"grass2")
    assert scene_packs(root, ["scene.road-river"])["scene.road-river"].version not in (river.version, after)
    # Another scene's pack changing doesn't change this scene's version
    # 別のシーンのパックが変わっても、このシーンのバージョンは変わらない
    square = found["scene.syracuse-square"].version
    assert scene_packs(root, ["scene.syracuse-square"])["scene.syracuse-square"].version == square


@pytest.mark.parametrize(
    ("shared", "manifest"),
    [(["road-gone"], "../road-river-calm/scene.json"), ([], "../../elsewhere/scene.json"), ([], "../x/scene.json")],
    ids=["missing-shared", "outside", "missing-pack"],
)
def test_an_index_json_reaching_outside_the_packs_is_not_shipped(
    tmp_path: Path, shared: list[str], manifest: str
) -> None:
    root = packs(tmp_path)
    road(root, shared, manifest)
    assert "scene.road-river" not in scene_packs(root, ["scene.road-river"])


def test_characters_are_all_of_the_world_model_with_its_talkable(tmp_path: Path) -> None:
    doc = make(world(SLICE), tmp_path)
    assert [c["id"] for c in doc["characters"] if c["talkable"]] == ["char.melos", "char.old-man"]
    assert len(doc["characters"]) == len(world(SLICE)["characters"])
    assert all(c["reading"] for c in doc["characters"])


# —— 2. Pre-recorded lines / 事前収録セリフ ——


def test_no_voices_json_means_no_prerecorded_lines(tmp_path: Path) -> None:
    doc = make(world(SLICE), tmp_path)
    assert not [c for c in doc["characters"] if "prerecorded" in c]
    assert "setPieceVoices" not in doc


def test_voices_json_goes_in_for_talkable_characters_and_matching_lines(tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w)
    doc = make(w, tmp_path, voices=root)
    valid(doc)
    v = written(root)
    chars = {c["id"]: c for c in doc["characters"]}
    assert chars["char.melos"]["prerecorded"] == v["characters"]["char.melos"]
    assert "arrival_capped" in chars["char.melos"]["prerecorded"]["cues"]
    assert chars["char.old-man"]["prerecorded"] == v["characters"]["char.old-man"]
    # Can't be talked to in the slice / スライスでは会話できない
    assert "prerecorded" not in chars["char.philostratus"]
    assert doc["setPieceVoices"] == v["setPieceVoices"] and len(doc["setPieceVoices"]) >= 2


def test_lines_that_do_not_match_the_world_model_are_left_out_one_by_one(tmp_path: Path) -> None:
    w = world(SLICE)
    keys = sorted(speaker_lines(w))
    changed, kept = keys[0], keys[1:]
    narration = next(
        f"{p['id']}/{i}" for p in w["setPieces"] for i, x in enumerate(p["lines"], 1) if "speaker" not in x
    )

    def edit(doc: Json, root: Path) -> None:
        pieces = doc["setPieceVoices"]
        pieces[changed] = {**pieces[changed], "text": pieces[changed]["text"] + "！"}
        pieces["piece.no-such-piece/1"] = clip(root, "nothing", "ない。")
        pieces[narration] = clip(root, "narration", "地の文。")
        # The number is beyond this set piece / 番号がこの固定演出の範囲を超える
        pieces[keys[1] + "0"] = clip(root, "too-far", "遠い。")
        melos = doc["characters"]["char.melos"]
        melos["cues"]["arrival_capped"] = {**melos["cues"]["arrival_capped"], "text": "間に合う。"}
        doc["characters"]["char.old-man"]["cues"]["arrival_capped"] = clip(
            root, "old-arrival", "……これなら、間に合う。"
        )

    root = voices(tmp_path, w, edit)
    doc = make(w, tmp_path, voices=root)
    valid(doc)
    v = written(root)
    assert sorted(doc["setPieceVoices"]) == kept
    chars = {c["id"]: c for c in doc["characters"]}
    melos = chars["char.melos"]["prerecorded"]
    # Only this cue is missing / この cue だけが欠ける
    assert melos["cues"] == {} and melos["aizuchi"] == v["characters"]["char.melos"]["aizuchi"]
    # Not the character who says this line / このセリフを言う人物ではない
    assert chars["char.old-man"]["prerecorded"]["cues"] == {}


def test_a_missing_voice_file_drops_only_what_uses_it(tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w)
    v = written(root)
    first = sorted(v["setPieceVoices"])[0]
    for url in (v["setPieceVoices"][first]["url"], v["characters"]["char.old-man"]["wait"]["url"]):
        (root / BOOK / url.rsplit("/", 1)[-1]).unlink()
    doc = make(w, tmp_path, voices=root)
    assert first not in doc["setPieceVoices"] and len(doc["setPieceVoices"]) == len(v["setPieceVoices"]) - 1
    chars = {c["id"]: c for c in doc["characters"]}
    assert "prerecorded" not in chars["char.old-man"] and "prerecorded" in chars["char.melos"]


def test_voices_json_of_another_world_version_is_still_checked_line_by_line(tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w, lambda doc, _: doc.update(worldModelVersion="hashire-merosu@0.9.0"))
    assert make(w, tmp_path, voices=root)["setPieceVoices"] == written(root)["setPieceVoices"]


def test_the_repo_recordings_all_match_the_slice_world_model(tmp_path: Path) -> None:
    """The repo's recordings (assets/voice) cover the slice world model without missing a line: if the world model's
    lines change, this goes red first as a reminder to re-read.

    リポジトリの録音（assets/voice）はスライスの世界モデルに対して 1 句も欠けない：世界モデルのセリフが変わったら
    ここが先に失敗し、読み直しを促す。
    """
    w = world(SLICE)
    v = json.loads((REPO / "assets" / "voice" / BOOK / "voices.json").read_text(encoding="utf-8"))
    doc = make(w, tmp_path, voices=REPO / "assets" / "voice")
    valid(doc)
    chars = {c["id"]: c.get("prerecorded") for c in doc["characters"] if c["talkable"]}
    # Every character who can be talked to is there, same as the recordings / 会話できる人物はすべてあり、録音と同じ
    assert {k: v["characters"][k] for k in chars} == chars
    # Characters who can't be talked to in the slice (the king and four others recorded ahead in B-6b) are not in the
    # manifest, but they must still be characters of the world model
    # スライスで会話できない人物（B-6b で先に録った王など 5 人）は manifest に出さないが、世界モデルの人物では
    # なければならない
    assert set(v["characters"]) - set(chars) <= {c["id"] for c in w["characters"]}
    assert doc["setPieceVoices"] == v["setPieceVoices"]
    # Every set-piece line spoken by a character in the slice has a recording
    # スライスで人物が話す固定演出のセリフにはすべて録音がある
    assert set(v["setPieceVoices"]) == set(speaker_lines(w))


# —— 3. Versions / バージョン ——


def test_manifest_version_is_stable_and_follows_every_input(tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w)
    pk = packs(tmp_path)
    base = make(w, tmp_path, packs_dir=pk, voices=root)
    assert make(w, tmp_path, packs_dir=pk, voices=root) == base

    w2 = copy.deepcopy(w)
    w2["roles"][0]["summary"] += "。"
    assert make(w2, tmp_path, packs_dir=pk, voices=root)["manifestVersion"] != base["manifestVersion"]

    v = written(root)
    v["characters"]["char.melos"]["wait"]["durationMs"] += 1
    (root / BOOK / "voices.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    assert make(w, tmp_path, packs_dir=pk, voices=root)["manifestVersion"] != base["manifestVersion"]

    entry = pk / "syracuse-square" / "scene.json"
    entry.write_bytes(entry.read_bytes() + b"\n")
    after = make(w, tmp_path, packs_dir=pk, voices=root)
    assert after["scenes"][0]["assetVersion"] != base["scenes"][0]["assetVersion"]
    assert after["manifestVersion"] != base["manifestVersion"]


# —— 4. Errors and logs / エラーとログ ——


def test_a_missing_role_summary_stops_the_gateway_naming_the_field(tmp_path: Path) -> None:
    w = world()
    del w["roles"][0]["summary"]
    path = tmp_path / "world.json"
    path.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ManifestError, match=r"role\.traveler.*summary") as e:
        gateway_app.build(Settings(database_url="postgresql+psycopg://x", world=path))
    assert str(path) in str(e.value)


def test_a_broken_voices_json_stops_startup_naming_the_file(tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w, lambda doc, _: doc["characters"]["char.melos"].pop("wait"))
    with pytest.raises(ManifestError, match="voices.json"):
        make(w, tmp_path, voices=root)


def test_startup_logs_only_ids_keys_versions_and_counts(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    w = world(SLICE)
    keys = sorted(speaker_lines(w))

    def edit(doc: Json, _: Path) -> None:
        doc["setPieceVoices"][keys[0]]["text"] = "違うせりふ。"
        doc["worldModelVersion"] = "hashire-merosu@0.9.0"

    root = voices(tmp_path, w, edit)
    with caplog.at_level(logging.INFO, logger="zoujin.manifest"):
        make(w, tmp_path, voices=root)
    text = caplog.text
    assert keys[0] in text and "char.philostratus" in text and "scene.village" in text
    lines = [*speaker_lines(w).values(), "違うせりふ。", w["clock"]["deadline"]["earliestArrivalCue"]["line"]]
    lines += [r["summary"] for r in w["roles"]] + ["うむ。", "待ってくれ。"]
    assert not [x for x in lines if x in text]


# —— 5. The mock uses the same generator / mock は同じ生成器を使う ——


def test_mock_gives_the_same_manifest_as_the_generator(tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w)
    pk = packs(tmp_path, "castle-throne")
    with TestClient(mock_app(Config(speed=0, strict=True, voices=root, scene_packs=pk))) as c:
        c.post("/v1/auth/login", json={"inviteCode": "mock"}, headers={"Origin": str(c.base_url)})
        r = c.get(f"/v1/books/{BOOK}/manifest")
        assert r.status_code == 200
        assert r.json() == make(w, tmp_path, packs_dir=pk, voices=root)
        assert r.headers["etag"] == f'"{r.json()["manifestVersion"]}"' and r.headers["cache-control"] == CACHE
        again = c.get(f"/v1/books/{BOOK}/manifest", headers={"If-None-Match": r.headers["etag"]})
        assert again.status_code == 304 and again.content == b""


# —— 4. The production gateway's route (real PostgreSQL) / 本番のゲートウェイのルート（実際の PostgreSQL） ——


@pytest.mark.db
def test_gateway_manifest_route_and_voice_files(env: Env, tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w)
    (root / BOOK / "unlisted.m4a").write_bytes(b"x")
    pk = packs(tmp_path)
    settings = replace(env.settings, dev=True, world=SLICE, voices=root, scene_packs=pk)
    with TestClient(gateway_app.create_app(settings)) as c:
        origin = {"Origin": str(c.base_url)}
        path = f"/v1/books/{BOOK}/manifest"
        r = c.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"

        v = written(root)
        url = v["setPieceVoices"][sorted(v["setPieceVoices"])[0]]["url"]
        f = c.get(url)  # Recording files need no login / 録音ファイルにログインは不要
        assert f.status_code == 200 and f.headers["cache-control"] == FILE_CACHE
        assert (
            f.headers["content-type"] == "audio/mp4"
            and f.content == (root / BOOK / url.rsplit("/", 1)[-1]).read_bytes()
        )
        for other in (
            f"/assets/voice/{BOOK}/unlisted.m4a",
            f"/assets/voice/{BOOK}/voices.json",
            # A file name from the list, but another book / リストにあるファイル名だが別の本
            "/assets/voice/other-book/" + url.rsplit("/", 1)[-1],
        ):
            assert c.get(other).status_code == 404, other

        assert c.post("/v1/auth/login", json={"inviteCode": invite(env)}, headers=origin).status_code == 200
        r = c.get(path)
        assert r.status_code == 200
        doc = r.json()
        valid(doc)
        assert doc == make(w, tmp_path, packs_dir=pk, voices=root)
        assert r.headers["etag"] == f'"{doc["manifestVersion"]}"' and r.headers["cache-control"] == CACHE
        same = c.get(path, headers={"If-None-Match": r.headers["etag"]})
        assert same.status_code == 304 and same.content == b"" and same.headers["etag"] == r.headers["etag"]
        assert c.get(path, headers={"If-None-Match": '"old"'}).status_code == 200
        r = c.get("/v1/books/other-book/manifest")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


@pytest.mark.db
def test_gateway_and_mock_answer_the_same(env: Env, tmp_path: Path) -> None:
    w = world(SLICE)
    root = voices(tmp_path, w)
    pk = packs(tmp_path)
    settings = replace(env.settings, dev=True, world=SLICE, voices=root, scene_packs=pk)
    with (
        TestClient(gateway_app.create_app(settings)) as g,
        TestClient(mock_app(Config(speed=0, strict=True, voices=root, scene_packs=pk))) as m,
    ):
        g.post("/v1/auth/login", json={"inviteCode": invite(env)}, headers={"Origin": str(g.base_url)})
        m.post("/v1/auth/login", json={"inviteCode": "mock"}, headers={"Origin": str(m.base_url)})
        a, b = g.get(f"/v1/books/{BOOK}/manifest"), m.get(f"/v1/books/{BOOK}/manifest")
        assert a.json() == b.json() and a.headers["etag"] == b.headers["etag"]
        assert a.headers["cache-control"] == b.headers["cache-control"]


class Direct:
    """The gateway calls the narrator: done directly in the same event loop (starting a game needs the narrator to write
    the opening).

    ゲートウェイがナレーターを呼ぶ：同じイベントループの中で直接行う（開始時にはナレーターが冒頭を書く必要がある）。
    """

    def __init__(self, narrator: Narrator) -> None:
        self.narrator = narrator

    async def run(self, pid: str) -> int:
        return len(await self.narrator.run(pid))


@pytest.mark.db
def test_gateway_only_opens_roles_in_the_manifest(env: Env, tmp_path: Path) -> None:
    """In the draft world model the shepherd boy is a first-release role, but when the starting village has no scene
    pack it isn't in the manifest and starting a game with it is refused (since F-11 the repo has the village's packs,
    so they are removed here before generating).

    草稿の世界モデルでは牧童は第 1 版のロールだが、開始する村にシーンパックがないときは manifest になく、開始も
    受け付けない（F-11 以降リポジトリには村のパックがあるので、ここではそれを除いてから生成する）。
    """
    packs = tmp_path / "scenes"
    for d in (REPO / "assets" / "scenes").iterdir():
        if not d.name.startswith("village"):
            shutil.copytree(d, packs / d.name)
    settings = replace(env.settings, dev=True, voices=tmp_path, scene_packs=packs)
    narrator = narrator_app.build(settings)
    with TestClient(gateway_app.create_app(settings, gateway_app.build(settings, Direct(narrator)))) as c:
        origin = {"Origin": str(c.base_url)}
        c.post("/v1/auth/login", json={"inviteCode": invite(env)}, headers=origin)
        for role, status in (("role.shepherd-boy", 400), ("role.apprentice", 201)):
            r = c.post(
                "/v1/playthroughs",
                json={"bookId": BOOK, "roleId": role},
                headers={**origin, "Idempotency-Key": f"k-{role}"},
            )
            assert r.status_code == status, (role, r.text)
        c.portal.call(narrator.engine.dispose)  # type: ignore[union-attr]


def test_config_reads_release_and_scene_packs(tmp_path: Path) -> None:
    s = Settings.from_env({"DATABASE_URL": "postgresql://x", "ZJ_RELEASE": "2", "ZJ_SCENE_PACKS": str(tmp_path)})
    assert s.release == 2 and s.packs == tmp_path
    assert Settings.from_env({"DATABASE_URL": "postgresql://x"}).packs == REPO / "assets" / "scenes"
    for bad in (
        {"ZJ_RELEASE": "0"},
        {"ZJ_RELEASE": "x"},
        {"ZJ_SCENE_PACKS": "rel"},
        {"ZJ_SCENE_PACKS": str(tmp_path / "no")},
    ):
        with pytest.raises(ConfigError):
            Settings.from_env({"DATABASE_URL": "postgresql://x", **bad})
