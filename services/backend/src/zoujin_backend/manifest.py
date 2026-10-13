"""The manifest (api-contract 2.1, B-7): generated entirely from what is in the repo, never hand-written; the
production gateway and the mock use the same generator.

- World model: book, roles, scenes and places (place names), characters, acts, clock, ruby word list;
- B-6 voice manifest (`<voice dir>/<bookId>/voices.json`, optional): characters' pre-recorded lines and set-piece
  pre-recorded lines, each checked line by line against the world model;
- Frontend scene packs (`ZJ_SCENE_PACKS`): each scene directory's entry file (`index.json`, otherwise `scene.json`);
  the version is the hash of every file in the directories the entry reaches.

Only what can really be loaded goes in: scenes without a pack, roles whose start scene has no pack, and recordings that
don't match the world model or whose file is missing are all left out; the startup log records only IDs, key names,
version numbers and counts (no line text). The result passes the `ManifestResponse` Schema; if it can't be generated,
`ManifestError` is raised and the gateway doesn't start. Generated once at process start: changing the world model,
voices or scene packs needs a restart.

manifest（api-contract 2.1、B-7）：すべてリポジトリの中身から生成し、手書きしない。本番のゲートウェイと mock は同じ
生成器を使う。

- 世界モデル：本、ロール、シーンと場所（地名）、人物、幕、時計、ルビの語リスト。
- B-6 の音声マニフェスト（`<音声ディレクトリ>/<bookId>/voices.json`。なくてもよい）：人物の事前収録セリフ、固定演出の
  事前収録セリフ。1 句ずつ世界モデルと照合する。
- フロントエンドのシーンパック（`ZJ_SCENE_PACKS`）：各シーンディレクトリの入口ファイル（`index.json`、なければ
  `scene.json`）。バージョンは入口からたどれるディレクトリ内の全ファイルの hash。

本当に読み込めるものだけを入れる：パックのないシーン、開始シーンにパックのないロール、世界モデルと合わない録音や
ファイルのない録音はすべて出さない。起動ログには ID、キー名、バージョン番号と個数だけを記録する（セリフは記録しない）。
結果は `ManifestResponse` の Schema を通す。生成できなければ `ManifestError` を投げ、ゲートウェイは起動しない。
プロセス起動時に 1 回生成する：世界モデル、音声、シーンパックを替えたら再起動が必要。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Book

log = logging.getLogger("zoujin.manifest")

Json = Any

SCHEMA = "api/rest/manifest.schema.json"
# Scene directory entry: F-10's index first, otherwise the combined file (the square)
# シーンディレクトリの入口：F-10 のインデックスを優先し、なければまとめた 1 ファイル（広場）
ENTRIES = ("index.json", "scene.json")
# Private book content stays out of the browser cache; ETag is kept for explicit conditional requests
# 非公開の本の内容はブラウザのキャッシュに残さない。明示的な条件付きリクエストのために ETag は残す
CACHE = "private, no-store"
# Recording file names carry a hash / 録音のファイル名には hash が付く
FILE_CACHE = "public, max-age=31536000, immutable"
ARRIVAL = "arrival_capped"


class ManifestError(ValueError):
    """Couldn't generate: the error says which input (world model, voice manifest, scene packs) and which file or
    field.

    生成できなかった：どの入力（世界モデル、音声マニフェスト、シーンパック）のどのファイル・フィールドかをエラーに書く。
    """


@dataclass(frozen=True)
class Pack:
    url: str  # /scenes/<assetVersion>/<dir>/<entry file> / /scenes/<assetVersion>/<ディレクトリ>/<入口ファイル>
    # First 8 hex digits of the sha256 of every file in the directories the entry reaches
    # 入口からたどれるディレクトリ内の全ファイルの sha256 の先頭 8 桁
    version: str
    # Directories the entry reaches (deployed together under /scenes/<assetVersion>/)
    # 入口からたどれるディレクトリ（デプロイ時は /scenes/<assetVersion>/ の下にまとめて置く）
    dirs: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    doc: Json
    # Recording file name → local file; only those referenced in doc / 録音のファイル名 → ローカルのファイル。doc が参照するものだけ
    files: dict[str, Path]
    # Scene packs: (assetVersion, dir) → local dir. When deployed the gateway serves `/scenes/<assetVersion>/<dir>/…`
    # itself (B-23), only what is listed here
    # シーンパック：（assetVersion, ディレクトリ）→ ローカルのディレクトリ。デプロイ時はゲートウェイ自身が
    # `/scenes/<assetVersion>/<ディレクトリ>/…` を配信し（B-23）、ここにあるものだけを配信する
    scenes: dict[tuple[str, str], Path] = field(default_factory=dict)

    @property
    def book_id(self) -> str:
        book_id: str = self.doc["book"]["id"]
        return book_id

    @property
    def etag(self) -> str:
        return f'"{self.doc["manifestVersion"]}"'

    def fresh(self, if_none_match: str | None) -> bool:
        """The request's If-None-Match matches (several comma-separated, weak W/, and `*` are all accepted): answer 304.

        リクエストの If-None-Match が一致した（カンマ区切りの複数、弱い比較の W/、`*` もすべて認める）：304 を返す。
        """
        if not if_none_match:
            return False
        tags = {t.strip().removeprefix("W/") for t in if_none_match.split(",")}
        return "*" in tags or self.etag in tags

    def has_role(self, role_id: str) -> bool:
        """Open roles: starting a game only accepts those in the manifest (the mock too).

        開放されているロール：開始時は manifest にあるものだけを認める（mock も同じ）。
        """
        return any(r["roleId"] == role_id for r in self.doc["roles"])

    def voice_file(self, book_id: str, name: str) -> Path | None:
        """A recording listed in the manifest; anything unlisted, the list itself, or another book gives None.

        manifest に載っている録音。載っていないもの、リスト自体、別の本はすべて None。
        """
        return self.files.get(name) if book_id == self.book_id else None

    def scene_file(self, version: str, folder: str, rel: str) -> Path | None:
        """A file in a scene pack referenced by the manifest; a version mismatch, outside the directory, or escaping it
        (`..`, symlinks) gives None.

        manifest が参照するシーンパック内の 1 ファイル。バージョンが合わない、ディレクトリ外、ディレクトリから出る
        （`..`、シンボリックリンク）はすべて None。
        """
        base = self.scenes.get((version, folder))
        if base is None or not rel:
            return None
        top = base.resolve()
        path = (top / rel).resolve()
        return path if top in path.parents and path.is_file() else None


def media_type(path: Path) -> str:
    # The tests' fake encoder outputs wav / テストの偽エンコーダーは wav を出す
    return "audio/mp4" if path.suffix == ".m4a" else "audio/wav"


def scene_packs(root: Path, scene_ids: Iterable[str]) -> dict[str, Pack]:
    """Scenes with a pack: for `scene.x` look at the entry file in `<root>/x/`. The directories the entry reaches (the
    directories of `index.json`'s `packs[].manifest` and `sharedPacks`) must all exist one level below `<root>`,
    otherwise the scene is left out.

    パックのあるシーン：`scene.x` は `<root>/x/` の入口ファイルを見る。入口からたどれるディレクトリ（`index.json` の
    `packs[].manifest` があるディレクトリと `sharedPacks`）がすべて `<root>` の 1 階層下に存在しなければ、そのシーンは
    出さない。
    """
    out = {}
    for sid in scene_ids:
        folder = root / sid.removeprefix("scene.")
        entry = next((folder / n for n in ENTRIES if (folder / n).is_file()), None)
        if entry is None:
            continue
        dirs = _reach(root, folder, entry)
        if dirs is None:
            continue
        version = _version(root, dirs)
        out[sid] = Pack(url=f"/scenes/{version}/{folder.name}/{entry.name}", version=version, dirs=dirs)
    return out


def _reach(root: Path, folder: Path, entry: Path) -> tuple[str, ...] | None:
    """Names of the directories the entry reaches (its own first, the rest by name); escaping `<root>`, a missing
    directory, or an unreadable `index.json` gives None (logged).

    入口からたどれるディレクトリ名（自分を先頭に、残りは名前順）。`<root>` から出る、ディレクトリがない、`index.json`
    が読めない：None（ログに記録）。
    """
    names = {folder.name}
    if entry.name == "index.json":
        try:
            index = json.loads(entry.read_text(encoding="utf-8"))
            refs = [(folder / p["manifest"]).parent for p in index.get("packs", [])]
            refs += [root / name for name in index.get("sharedPacks", [])]
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            log.info(
                "manifest: can't read index.json of scene directory %s; left out / "
                "manifest：シーンディレクトリ %s の index.json が読めないので出さない",
                folder.name,
                folder.name,
            )
            return None
        top = Path(os.path.normpath(root))
        for ref in refs:
            # `..` is resolved only literally; scene directories may be symlinks
            # `..` は字面どおりにだけたどる。シーンディレクトリはシンボリックリンクでもよい
            d = Path(os.path.normpath(ref))
            if d.is_dir() and (d == folder or folder in d.parents):
                continue  # Inside its own directory, already counted / 自分のディレクトリ内なので、もう数に入っている
            if d.parent != top or not d.is_dir():
                log.info(
                    "manifest: scene directory %s references a pack not one level below the scene pack directory; "
                    "left out / manifest：シーンディレクトリ %s が参照するパックがシーンパックディレクトリの "
                    "1 階層下にないので出さない",
                    folder.name,
                    folder.name,
                )
                return None
            names.add(d.name)
    return (folder.name, *sorted(names - {folder.name}))


def _version(root: Path, dirs: Iterable[str]) -> str:
    """First 8 hex digits of the sha256 over every file (relative path and content) in these directories: the version
    changes when any file in the pack changes.

    これらのディレクトリ内の全ファイル（相対パスと内容）をまとめた sha256 の先頭 8 桁：パック内のどのファイルが
    変わってもバージョンが変わる。
    """
    h = hashlib.sha256()
    for name in sorted(dirs):
        base = root / name
        for f in sorted(p for p in base.rglob("*") if p.is_file()):
            with f.open("rb") as fh:
                digest = hashlib.file_digest(fh, "sha256").digest()
            h.update(f"{name}/{f.relative_to(base).as_posix()}".encode() + b"\0" + digest)
    return h.hexdigest()[:8]


def read_voices(voice_dir: Path, book_id: str) -> tuple[Json | None, Path]:
    path = voice_dir / book_id / "voices.json"
    if not path.is_file():
        return None, path
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except json.JSONDecodeError as e:
        raise ManifestError(
            f"Voice manifest {path} is not JSON (line {e.lineno}) / 音声マニフェスト {path} が JSON ではない（{e.lineno} 行目）"
        ) from None


def generate(book: Book, schemas: SchemaBook, *, packs: Path, voices: Path, release: int = 1) -> Manifest:
    """The manifest of one book (the version used for new games). `packs` is the scene pack directory, `voices` the
    voice directory (split by book below it).

    1 冊の本（新しく始めるときに使うバージョン）の manifest。`packs` はシーンパックのディレクトリ、`voices` は音声の
    ディレクトリ（その下は本ごとに分かれる）。
    """
    w = book.world
    where = f"{book.path or book.version}"
    found = scene_packs(packs, [s["id"] for s in w["scenes"]])
    for s in w["scenes"]:
        if s["id"] not in found:
            log.info(
                "manifest: scene %s has no scene pack; left out / manifest：シーン %s にシーンパックがないので出さない",
                s["id"],
                s["id"],
            )
    places = {p["id"]: p for p in w["places"]}

    roles = []
    for r in w["roles"]:
        if r["release"] > release:
            continue
        start = places[r["startPlace"]].get("sceneRef")
        if start not in found:
            log.info(
                "manifest: start scene %s of role %s has no scene pack; left out / "
                "manifest：ロール %s の開始シーン %s にシーンパックがないので出さない",
                start,
                r["id"],
                r["id"],
                start,
            )
            continue
        roles.append(
            {
                "roleId": r["id"],
                "name": r["name"],
                "summary": _need(r, "summary", f"{where} roles[{r['id']}]"),
                "startSceneId": start,
                "startActId": r["startAct"],
            }
        )
    scenes = [
        {
            "sceneId": s["id"],
            "places": [p["id"] for p in w["places"] if p.get("sceneRef") == s["id"]],
            "assetUrl": found[s["id"]].url,
            "assetVersion": found[s["id"]].version,
        }
        for s in w["scenes"]
        if s["id"] in found
    ]
    # All place names are given (the map and details show them); places whose scene is left out (no pack) get a null
    # sceneId, consistent with scenes
    # 地名はすべて出す（地図と詳細に表示する）。シーンを出さない（パックがない）場所の sceneId は null で、scenes と
    # 一致する
    place_names = [
        {"placeId": p["id"], "name": p["name"], "sceneId": p.get("sceneRef") if p.get("sceneRef") in found else None}
        for p in w["places"]
    ]
    acts = []
    for a in w["acts"]:
        ids = [x for x in a["scenes"] if x in found]
        # The Schema requires at least one scene per act; none of this act's scenes has a pack, so the frontend
        # handles it as having no pack
        # Schema は 1 幕に最低 1 シーンを要求する。この幕のシーンにはどれもパックがないので、フロントエンドはパック
        # なしとして扱う
        if not ids:
            log.info(
                "manifest: none of act %s's scenes has a scene pack; left out / "
                "manifest：幕 %s のシーンにシーンパックが 1 つもないので出さない",
                a["id"],
                a["id"],
            )
            continue
        acts.append({"actId": a["id"], "title": a["title"], "sceneIds": ids})

    doc_voices, voices_path = read_voices(voices, book.book_id)
    prerecorded, pieces = _checked_voices(book, schemas, doc_voices, voices_path)
    characters = []
    for c in w["characters"]:
        out = {
            "id": c["id"],
            "name": c["name"],
            "reading": _need(c, "reading", f"{where} characters[{c['id']}]"),
            "talkable": bool(c["talkable"]),
        }
        if c["id"] in prerecorded:
            out["prerecorded"] = prerecorded[c["id"]]
        characters.append(out)

    clock = w["clock"]
    body: Json = {
        "book": {k: w["book"][k] for k in ("id", "title", "author")},
        "roles": roles,
        "scenes": scenes,
        "places": place_names,
        "characters": characters,
        "acts": acts,
        "clock": {
            "deadlineT": clock["deadline"]["t"],
            "sunsetMinuteOfDay": clock["sunsetMinuteOfDay"],
            "days": list(clock["labels"]["days"]),
        },
        "ruby": [{"word": x["word"], "reading": x["reading"]} for x in w.get("ruby", [])],
    }
    if pieces:
        body["setPieceVoices"] = pieces
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    doc = {"manifestVersion": f"{book.version}+{digest[:8]}", **body}
    problems = schemas.spots(SCHEMA, "#/$defs/ManifestResponse", doc)
    if problems:
        raise ManifestError(
            f"The manifest generated from world model {where} doesn't match the Schema / "
            f"世界モデル {where} から生成した manifest が Schema に合わない: " + "; ".join(problems[:5])
        )
    files = {name: voices / book.book_id / name for name in _clip_names(doc, book.book_id)}
    counts = (len(roles), len(scenes), len(acts), len(characters), len(prerecorded), len(pieces), len(body["ruby"]))
    log.info(
        "manifest %s: roles %d, scenes %d, acts %d, characters %d (%d with pre-recorded lines), set-piece "
        "pre-recorded lines %d, ruby %d / ロール %d、シーン %d、幕 %d、人物 %d（事前収録セリフ付き %d）、"
        "固定演出の事前収録セリフ %d、ルビ %d",
        doc["manifestVersion"],
        *counts,
        *counts,
    )
    dirs = {(p.version, d): packs / d for p in found.values() for d in p.dirs}
    return Manifest(doc=doc, files=files, scenes=dirs)


def _need(d: Json, key: str, where: str) -> Any:
    value = d.get(key)
    if value is None or value == "":
        raise ManifestError(f"World model {where} is missing {key} / 世界モデル {where} に {key} がない")
    return value


def _checked_voices(
    book: Book, schemas: SchemaBook, voices: Json | None, path: Path
) -> tuple[dict[str, Json], dict[str, Json]]:
    """What in the voice manifest matches the world model and has its recording file: character → `Prerecorded`,
    set-piece key → recording.

    音声マニフェストのうち世界モデルと合い、録音ファイルもあるもの：人物 → `Prerecorded`、固定演出のキー → 録音。
    """
    if voices is None:
        log.info(
            "manifest: no voice manifest (%s); no character gets pre-recorded lines / "
            "manifest：音声マニフェストがない（%s）ので、どの人物にも事前収録セリフを付けない",
            book.book_id,
            book.book_id,
        )
        return {}, {}
    problems = []
    for sid, block in voices.get("characters", {}).items():
        problems += [f"characters/{sid}{e}" for e in _spots(schemas, "#/$defs/Prerecorded", block)]
    for key, clip in voices.get("setPieceVoices", {}).items():
        problems += [f"setPieceVoices/{key}{e}" for e in _spots(schemas, "#/$defs/SetPieceVoiceKey", key)]
        problems += [f"setPieceVoices/{key}{e}" for e in _spots(schemas, "#/$defs/VoiceClip", clip)]
    if problems:
        raise ManifestError(
            f"Voice manifest {path} doesn't match the manifest Schema / "
            f"音声マニフェスト {path} が manifest の Schema に合わない: " + "; ".join(problems[:5])
        )
    if voices.get("worldModelVersion") != book.version:
        log.info(
            "manifest: the voice manifest is for %s and the book is %s; used after checking line by line / "
            "manifest：音声マニフェストは %s のもので本は %s。1 句ずつ照合してから使う",
            voices.get("worldModelVersion"),
            book.version,
            voices.get("worldModelVersion"),
            book.version,
        )

    folder = path.parent
    prefix = f"/assets/voice/{book.book_id}/"

    def there(clip: Json) -> bool:
        name = clip["url"].removeprefix(prefix)
        ok = clip["url"].startswith(prefix) and "/" not in name and name != path.name and (folder / name).is_file()
        return bool(ok)

    w = book.world
    talkable = {c["id"] for c in w["characters"] if c["talkable"]}
    cue = w["clock"]["deadline"].get("earliestArrivalCue")
    prerecorded = {}
    for sid, block in voices.get("characters", {}).items():
        # Characters who can't be talked to have none (Schema), and those not in the world model are left out too
        # 会話できない人物には付けない（Schema）。世界モデルにいない人物も出さない
        if sid not in talkable:
            log.info(
                "manifest: %s can't be talked to; its 6 lines in the voice manifest are left out / "
                "manifest：%s とは会話できないので、音声マニフェストの 6 句は出さない",
                sid,
                sid,
            )
            continue
        if not all(there(x) for x in [*block["aizuchi"], *block["unheard"], block["wait"]]):
            log.info(
                "manifest: a recording file of %s's 6 lines is missing; this character gets no pre-recorded lines / "
                "manifest：%s の 6 句に録音ファイルのないものがあるので、この人物には事前収録セリフを付けない",
                sid,
                sid,
            )
            continue
        cues = {}
        for kind, clip in block["cues"].items():
            if cue is None or kind != ARRIVAL or sid != cue["speaker"]:
                log.info(
                    "manifest: %s %s is not this character's line in the world model; left out / "
                    "manifest：%s の %s は世界モデルでこの人物のセリフではないので出さない",
                    sid,
                    kind,
                    sid,
                    kind,
                )
            elif clip["text"] != cue["line"]:
                log.info(
                    "manifest: %s %s doesn't match the world model's text; left out / "
                    "manifest：%s の %s が世界モデルの文字と合わないので出さない",
                    sid,
                    kind,
                    sid,
                    kind,
                )
            elif not there(clip):
                log.info(
                    "manifest: the recording file of %s %s is missing; left out / "
                    "manifest：%s の %s の録音ファイルがないので出さない",
                    sid,
                    kind,
                    sid,
                    kind,
                )
            else:
                cues[kind] = clip
        prerecorded[sid] = {k: block[k] for k in ("aizuchi", "unheard", "wait")} | {"cues": cues}

    lines = {p["id"]: p["lines"] for p in w.get("setPieces", [])}
    pieces = {}
    for key, clip in sorted(voices.get("setPieceVoices", {}).items()):
        piece, _, n = key.rpartition("/")
        got = lines.get(piece, [])
        line = got[int(n) - 1] if int(n) <= len(got) else None
        if line is None or "speaker" not in line:
            log.info(
                "manifest: set-piece key %s is not a character's line in the world model; left out / "
                "manifest：固定演出のキー %s は世界モデルで人物のセリフではないので出さない",
                key,
                key,
            )
        elif clip["text"] != line["line"]:
            log.info(
                "manifest: set-piece key %s doesn't match the world model's text; left out / "
                "manifest：固定演出のキー %s が世界モデルの文字と合わないので出さない",
                key,
                key,
            )
        elif not there(clip):
            log.info(
                "manifest: the recording file of set-piece key %s is missing; left out / "
                "manifest：固定演出のキー %s の録音ファイルがないので出さない",
                key,
                key,
            )
        else:
            pieces[key] = clip
    return prerecorded, pieces


def _spots(schemas: SchemaBook, ref: str, doc: Json) -> list[str]:
    return schemas.spots(SCHEMA, ref, doc)


def _clip_names(doc: Json, book_id: str) -> list[str]:
    clips = [x for c in doc["characters"] if "prerecorded" in c for x in _clips(c["prerecorded"])]
    clips += list(doc.get("setPieceVoices", {}).values())
    return sorted({x["url"].removeprefix(f"/assets/voice/{book_id}/") for x in clips})


def _clips(block: Json) -> list[Json]:
    """Every recording in one character's `Prerecorded`.

    1 人の人物の `Prerecorded` にあるすべての録音。
    """
    return [*block["aizuchi"], *block["unheard"], block["wait"], *block["cues"].values()]
