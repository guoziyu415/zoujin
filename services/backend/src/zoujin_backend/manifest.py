"""manifest（api-contract 2.1，B-7）：全部从仓库里的东西生成，不手写；正式网关和 mock 用同一个生成器。

- 世界模型：书、身份、场景和地点（地名）、人物、幕、时钟、注音词表；
- B-6 的声音清单（`<声音目录>/<bookId>/voices.json`，可以没有）：人物的预录句、固定演出的预录句，逐句和世界模型核对；
- 前端的场景包（`ZJ_SCENE_PACKS`）：每个场景目录的入口文件（`index.json`，没有就 `scene.json`）和它的内容 hash。

只有真能加载的东西才进：没有包的场景、开局场景没有包的身份、和世界模型对不上或文件不在的录音都不出，启动日志只记 ID、
键名、版本号和个数（不记台词）。结果过 `ManifestResponse` 的 Schema；生成不出来就抛 `ManifestError`，网关起不来。
进程启动时生成一次：换世界模型、声音或场景包都要重启。
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Book

log = logging.getLogger("zoujin.manifest")

Json = Any

SCHEMA = "api/rest/manifest.schema.json"
ENTRIES = ("index.json", "scene.json")  # 场景目录的入口：F-10 的索引优先，没有就是合起来的那份（广场）
CACHE = "private, no-cache"  # manifest 不长缓存，靠 ETag 问（2.1）
FILE_CACHE = "public, max-age=31536000, immutable"  # 录音文件名带 hash
ARRIVAL = "arrival_capped"


class ManifestError(ValueError):
    """生成不出来：错误里写清是哪一样（世界模型、声音清单、场景包）、哪个文件或字段。"""


@dataclass(frozen=True)
class Pack:
    url: str  # /scenes/<目录>/<assetVersion>/<入口文件>
    version: str  # 入口文件的 sha256 前 8 位


@dataclass(frozen=True)
class Manifest:
    doc: Json
    files: dict[str, Path]  # 录音的文件名 → 本机文件；只有 doc 里引用了的

    @property
    def book_id(self) -> str:
        book_id: str = self.doc["book"]["id"]
        return book_id

    @property
    def etag(self) -> str:
        return f'"{self.doc["manifestVersion"]}"'

    def fresh(self, if_none_match: str | None) -> bool:
        """请求带的 If-None-Match 对上了（逗号分开的几个、弱校验 W/、`*` 都认）：回 304。"""
        if not if_none_match:
            return False
        tags = {t.strip().removeprefix("W/") for t in if_none_match.split(",")}
        return "*" in tags or self.etag in tags

    def has_role(self, role_id: str) -> bool:
        """开放的身份：开局时只认 manifest 里有的（mock 也这样）。"""
        return any(r["roleId"] == role_id for r in self.doc["roles"])

    def voice_file(self, book_id: str, name: str) -> Path | None:
        """manifest 里列着的录音；清单外的、清单本身、别的书都是 None。"""
        return self.files.get(name) if book_id == self.book_id else None


def media_type(path: Path) -> str:
    return "audio/mp4" if path.suffix == ".m4a" else "audio/wav"  # 测试的假编码器出 wav


def scene_packs(root: Path, scene_ids: Iterable[str]) -> dict[str, Pack]:
    """有包的场景：`scene.x` 看 `<root>/x/` 里的入口文件。"""
    out = {}
    for sid in scene_ids:
        folder = root / sid.removeprefix("scene.")
        entry = next((folder / n for n in ENTRIES if (folder / n).is_file()), None)
        if entry is None:
            continue
        version = hashlib.sha256(entry.read_bytes()).hexdigest()[:8]
        out[sid] = Pack(url=f"/scenes/{folder.name}/{version}/{entry.name}", version=version)
    return out


def read_voices(voice_dir: Path, book_id: str) -> tuple[Json | None, Path]:
    path = voice_dir / book_id / "voices.json"
    if not path.is_file():
        return None, path
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except json.JSONDecodeError as e:
        raise ManifestError(f"声音清单 {path} 不是 JSON（第 {e.lineno} 行）") from None


def generate(book: Book, schemas: SchemaBook, *, packs: Path, voices: Path, release: int = 1) -> Manifest:
    """一本书（开新局用的那个版本）的 manifest。`packs` 是场景包目录，`voices` 是声音目录（下面按书分）。"""
    w = book.world
    where = f"世界模型 {book.path or book.version}"
    found = scene_packs(packs, [s["id"] for s in w["scenes"]])
    for s in w["scenes"]:
        if s["id"] not in found:
            log.info("manifest：场景 %s 没有场景包，不出", s["id"])
    places = {p["id"]: p for p in w["places"]}

    roles = []
    for r in w["roles"]:
        if r["release"] > release:
            continue
        start = places[r["startPlace"]].get("sceneRef")
        if start not in found:
            log.info("manifest：身份 %s 的开局场景 %s 没有场景包，不出", r["id"], start)
            continue
        roles.append(
            {
                "roleId": r["id"],
                "name": r["name"],
                "summary": _need(r, "summary", f"{where} 的 roles[{r['id']}]"),
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
    # 地名全给（地图、详情要显示）；场景没出（没有包）的地点 sceneId 为 null，和 scenes 对得上
    place_names = [
        {"placeId": p["id"], "name": p["name"], "sceneId": p.get("sceneRef") if p.get("sceneRef") in found else None}
        for p in w["places"]
    ]
    acts = []
    for a in w["acts"]:
        ids = [x for x in a["scenes"] if x in found]
        if not ids:  # Schema 要求每一幕至少一个场景；这一幕的场景都没有包，前端照没有包处理
            log.info("manifest：幕 %s 的场景都没有场景包，不出", a["id"])
            continue
        acts.append({"actId": a["id"], "title": a["title"], "sceneIds": ids})

    doc_voices, voices_path = read_voices(voices, book.book_id)
    prerecorded, pieces = _checked_voices(book, schemas, doc_voices, voices_path)
    characters = []
    for c in w["characters"]:
        out = {
            "id": c["id"],
            "name": c["name"],
            "reading": _need(c, "reading", f"{where} 的 characters[{c['id']}]"),
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
        raise ManifestError(f"由{where}生成的 manifest 不合 Schema：" + "；".join(problems[:5]))
    files = {name: voices / book.book_id / name for name in _clip_names(doc, book.book_id)}
    log.info(
        "manifest %s：身份 %d、场景 %d、幕 %d、人物 %d（带预录句的 %d）、固定演出的预录句 %d、注音 %d",
        doc["manifestVersion"],
        len(roles),
        len(scenes),
        len(acts),
        len(characters),
        len(prerecorded),
        len(pieces),
        len(body["ruby"]),
    )
    return Manifest(doc=doc, files=files)


def _need(d: Json, key: str, where: str) -> Any:
    value = d.get(key)
    if value is None or value == "":
        raise ManifestError(f"{where} 缺 {key}")
    return value


def _checked_voices(
    book: Book, schemas: SchemaBook, voices: Json | None, path: Path
) -> tuple[dict[str, Json], dict[str, Json]]:
    """声音清单里和世界模型对得上、录音文件也在的：人物 → `Prerecorded`，固定演出的键 → 录音。"""
    if voices is None:
        log.info("manifest：没有声音清单（%s），人物都不带预录句", book.book_id)
        return {}, {}
    problems = []
    for sid, block in voices.get("characters", {}).items():
        problems += [f"characters/{sid}{e}" for e in _spots(schemas, "#/$defs/Prerecorded", block)]
    for key, clip in voices.get("setPieceVoices", {}).items():
        problems += [f"setPieceVoices/{key}{e}" for e in _spots(schemas, "#/$defs/SetPieceVoiceKey", key)]
        problems += [f"setPieceVoices/{key}{e}" for e in _spots(schemas, "#/$defs/VoiceClip", clip)]
    if problems:
        raise ManifestError(f"声音清单 {path} 不合 manifest 的 Schema：" + "；".join(problems[:5]))
    if voices.get("worldModelVersion") != book.version:
        log.info("manifest：声音清单是 %s 的，书是 %s，逐句核对后照用", voices.get("worldModelVersion"), book.version)

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
        if sid not in talkable:  # 不能对话的人物没有（Schema），世界模型里没有的也不出
            log.info("manifest：%s 不能对话，声音清单里的 6 句不出", sid)
            continue
        if not all(there(x) for x in [*block["aizuchi"], *block["unheard"], block["wait"]]):
            log.info("manifest：%s 的 6 句有录音文件不在，这个人物不带预录句", sid)
            continue
        cues = {}
        for kind, clip in block["cues"].items():
            if cue is None or kind != ARRIVAL or sid != cue["speaker"]:
                log.info("manifest：%s 的 %s 不是世界模型里这个人物的话，不出", sid, kind)
            elif clip["text"] != cue["line"]:
                log.info("manifest：%s 的 %s 和世界模型的文字对不上，不出", sid, kind)
            elif not there(clip):
                log.info("manifest：%s 的 %s 录音文件不在，不出", sid, kind)
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
            log.info("manifest：固定演出的键 %s 在世界模型里不是人物说的一句，不出", key)
        elif clip["text"] != line["line"]:
            log.info("manifest：固定演出的键 %s 和世界模型的文字对不上，不出", key)
        elif not there(clip):
            log.info("manifest：固定演出的键 %s 的录音文件不在，不出", key)
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
    """一个人物 `Prerecorded` 里的全部录音。"""
    return [*block["aizuchi"], *block["unheard"], block["wait"], *block["cues"].values()]
