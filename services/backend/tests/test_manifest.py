"""B-7：manifest 的生成器（`manifest.py`）、正式网关的路由、mock 用同一个生成器（卡的验收第 1〜6 条）。

不联网：世界模型和广场的 `scene.json` 用仓库里的，场景包目录和声音清单在测试的临时目录里造。
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
    """场景包目录：广场照仓库的，`extra` 的场景各放一份 scene.json（内容就是场景名）。"""
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


# —— 声音清单：B-6 的格式，录音文件是几个字节 ——


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
    """切片里固定演出的人物台词：键「{固定演出 ID}/{序号}」→ 文字。"""
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


# —— 1. 生成规则 ——


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
    assert doc["places"] == [  # v1.0.14：全部地点的地名；场景没出的 sceneId 为 null
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
    for internal in ('"note"', '"cite"', '"inferred"', "var."):  # 世界模型的内部字段和变量不出
        assert internal not in text


def test_draft_release_1_only_roles_whose_start_scene_has_a_pack(tmp_path: Path) -> None:
    w = world()
    doc = make(w, tmp_path)
    assert [r["roleId"] for r in doc["roles"]] == ["role.traveler", "role.apprentice"]  # 牧童的村没有包、release 2 不出
    assert [s["sceneId"] for s in doc["scenes"]] == ["scene.syracuse-square"]
    assert all(a["sceneIds"] == ["scene.syracuse-square"] for a in doc["acts"])
    assert make(w, tmp_path / "2", release=2)["roles"] == doc["roles"]  # 王城没有包：侍女、警吏照样不出


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
    """#103 的形状：`index.json` 只列兄弟包的相对地址和共用包，不带 sha（前端 2 #114 评审）。"""
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
    # 版本在最前：`../road-river-calm/` 落在同一个版本下面，不出界
    assert river.url == f"/scenes/{river.version}/road-river/index.json"
    assert river.dirs == ("road-river", "road-common", "road-river-calm", "road-river-flood")
    assert found["scene.syracuse-square"].dirs == ("syracuse-square",)
    # index.json 不变，兄弟包或共用包里任何一个文件变了，版本就变
    calm = root / "road-river-calm" / "scene.json"
    calm.write_text('{"files": {"a.glb": "3"}}', encoding="utf-8")
    after = scene_packs(root, ["scene.road-river"])["scene.road-river"].version
    assert after != river.version
    (root / "road-common" / "tex" / "grass.ktx2").write_bytes(b"grass2")
    assert scene_packs(root, ["scene.road-river"])["scene.road-river"].version not in (river.version, after)
    # 别的场景的包变了，这个场景的版本不变
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


# —— 2. 预录句 ——


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
    assert "prerecorded" not in chars["char.philostratus"]  # 切片里不能对话
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
        pieces[keys[1] + "0"] = clip(root, "too-far", "遠い。")  # 序号超出这条固定演出
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
    assert melos["cues"] == {} and melos["aizuchi"] == v["characters"]["char.melos"]["aizuchi"]  # 只少这个 cue
    assert chars["char.old-man"]["prerecorded"]["cues"] == {}  # 不是说这句的人物


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
    """仓库里的录音（assets/voice）对切片世界模型一句也不少：世界模型改了台词，这里先红，提醒重读。"""
    w = world(SLICE)
    v = json.loads((REPO / "assets" / "voice" / BOOK / "voices.json").read_text(encoding="utf-8"))
    doc = make(w, tmp_path, voices=REPO / "assets" / "voice")
    valid(doc)
    chars = {c["id"]: c.get("prerecorded") for c in doc["characters"]}
    assert {k: chars[k] for k in v["characters"]} == v["characters"]
    assert doc["setPieceVoices"] == v["setPieceVoices"]
    assert set(v["setPieceVoices"]) == set(speaker_lines(w))  # 切片里人物说的固定演出句都有录音


# —— 3. 版本 ——


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


# —— 4. 出错和日志 ——


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


# —— 5. mock 用同一个生成器 ——


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


# —— 4. 正式网关的路由（真 PostgreSQL） ——


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
        f = c.get(url)  # 录音文件不要登录
        assert f.status_code == 200 and f.headers["cache-control"] == FILE_CACHE
        assert (
            f.headers["content-type"] == "audio/mp4"
            and f.content == (root / BOOK / url.rsplit("/", 1)[-1]).read_bytes()
        )
        for other in (
            f"/assets/voice/{BOOK}/unlisted.m4a",
            f"/assets/voice/{BOOK}/voices.json",
            "/assets/voice/other-book/" + url.rsplit("/", 1)[-1],  # 清单里的文件名、别的书
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
    """网关叫叙事者：同一个事件循环里直接做（开局要叙事者写开局）。"""

    def __init__(self, narrator: Narrator) -> None:
        self.narrator = narrator

    async def run(self, pid: str) -> int:
        return len(await self.narrator.run(pid))


@pytest.mark.db
def test_gateway_only_opens_roles_in_the_manifest(env: Env, tmp_path: Path) -> None:
    """草稿世界模型里牧童是第一版的身份，但开局的村没有场景包，manifest 里没有它，开局也不收。"""
    settings = replace(env.settings, dev=True, voices=tmp_path)
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
