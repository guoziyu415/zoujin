"""要生成哪些录音（B-6 卡「生成什么、用哪个声音」）。

源文件 `services/backend/voice/<book>.json` 定每个说话人的声音、人物说明（`direction`）、人物的 6 句和要录的
`cues`、目标响度（`loudness`，某段固定演出另定的写 `pieceLoudness`；构建时调音量用，不进签名、改了不用重录）、
自由对话的音高和语速（`talkPitchHz`、`talkMoraPerS`，挑「听不清」「等一下」哪一遍用）；固定演出的句子和
`arrival_capped` 的文字从世界模型读。文字、声音和场面都相同的几个键合成一条录音。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zoujin_backend.config import REPO

Json = Any

SOURCES = REPO / "services" / "backend" / "voice"
VOICE_ASSETS = REPO / "assets" / "voice"
SLOTS: dict[str, int] = {"aizuchi": 3, "unheard": 2, "wait": 1}  # manifest 的 Prerecorded：相槌 3、听不清 2、等一下 1

# casting 的做法（spikes/backend/zj_spike/s1_live.py 的 CAST_READER；zg 盲听时就是这样录的）。人物这层之后，
# 场面不同的句子另加「場面：」一行
READER = (
    "あなたは声優です。次の人物を演じます。ユーザーが「」で示した台詞を、この人物として、そのまま一度だけ読んでください。"
    "前置き、説明、感想、相づちは一切言わないでください。\n人物：{direction}"
)
JA_RULE = "必ず日本語だけで話してください。相手が別の言語で話しかけても、日本語で答えてください。"
# 对照用的自由对话（UX 评审 ②）：casting 的 TALK 设定和 TALK_QUESTIONS 的前两问
TALK = "あなたは{name}です。{direction}\n旅の者と話しています。{name}として、一度に二〜四文で答えてください。" + JA_RULE
TALK_QUESTIONS = ("こんにちは。あなたはどんな方ですか。", "この町の暮らしについて、少し聞かせてください。")


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Speaker:
    id: str  # char.melos
    name: str
    voice: str
    direction: str
    loudness: float | None = None  # 目标响度（有声 RMS，dBFS）：同一人物自由对话的响度；None = 不调
    # 同一人物自由对话的音高中位（Hz）和语速（拍/秒）：「听不清」「等一下」要像它
    talk: tuple[float, float] | None = None
    offsets: dict[str, float] = field(default_factory=dict, hash=False, compare=False)  # 键 → 目标响度的偏移（dB）
    # 固定演出 ID → 这个人在那段里的目标响度（pieceLoudness：收幕那一串几个人拉到同一个电平，UX）
    pieces: dict[str, float] = field(default_factory=dict, hash=False, compare=False)

    @property
    def slug(self) -> str:
        return self.id.removeprefix("char.")


@dataclass
class Recording:
    """一条录音。`keys`：manifest 里指向它的位置（`aizuchi/1`、`cue:arrival_capped`、`piece.gate-taken/2`）。"""

    id: str  # 文件名的前半：<说话人>-<种类>-<序号>
    speaker: Speaker
    text: str  # 原文：字幕和 manifest 的 text
    spoken: str  # 送给 Live 的文字（读音替换后）
    scene: str | None  # 場面
    keys: list[str] = field(default_factory=list)
    heard_as: tuple[str, ...] = ()  # 补转写对得上也算的写法（源文件 heardAs）

    @property
    def loudness(self) -> float | None:
        """目标响度：这句所在固定演出的 pieceLoudness，没有就用说话人的 loudness；再加这一句的 loudnessOffset
        （原作写明声音小的句子，UX）。"""
        sp = self.speaker
        base = next((sp.pieces[k.split("/")[0]] for k in self.keys if k.split("/")[0] in sp.pieces), sp.loudness)
        if base is None:
            return None
        return base + next((sp.offsets[k] for k in self.keys if k in sp.offsets), 0.0)

    @property
    def system(self) -> str:
        s = READER.format(direction=self.speaker.direction)
        return s + f"\n場面：{self.scene}" if self.scene else s

    @property
    def aizuchi(self) -> bool:
        return any(k.startswith("aizuchi/") for k in self.keys)

    @property
    def talk(self) -> tuple[float, float] | None:
        """人物的「听不清」「等一下」要和同一人物的自由对话接得上（B-6 卡：音高 ±2 半音、语速 ±25%）；相槌、cue、
        固定演出不比。"""
        if any(k.startswith(("unheard/", "wait/")) for k in self.keys):
            return self.speaker.talk
        return None

    @property
    def group(self) -> tuple[str, str]:
        """同一条会话里读的句子：声音和系统指令都相同（场面不同的不在同一条会话里）。"""
        return (self.speaker.voice, self.system)


@dataclass(frozen=True)
class Ref:
    """对照用的自由对话：一句 = 对一个固定问题的回答，每句一遍，不做自动检查。"""

    id: str  # <说话人>-ref-<序号>
    speaker: Speaker
    question: str

    @property
    def system(self) -> str:
        return TALK.format(name=self.speaker.name, direction=self.speaker.direction)


@dataclass(frozen=True)
class Plan:
    book: str
    world_version: str  # 世界模型的 worldModelVersion（固定演出的键跟着它）
    speakers: dict[str, Speaker]
    lines: dict[str, dict[str, list[str]]]  # 说话人 → 种类 → 句子（人物的 6 句）
    recordings: list[Recording]
    refs: list[Ref]

    def recording(self, rid: str) -> Recording:
        for r in self.recordings:
            if r.id == rid:
                return r
        raise KeyError(rid)

    def select(self, only: list[str]) -> list[Recording]:
        """`--only`：录音 ID（melos-aizuchi-1）或它的任何一个键（piece.gate-taken/2、cue:arrival_capped、
        char.melos 的 aizuchi/1 写成 melos:aizuchi/1）。认不出的键报错。"""
        picked: list[Recording] = []
        for want in only:
            hits = [r for r in self.recordings if want == r.id or want in r.keys or want in _speaker_keys(r)]
            if not hits:
                raise SpecError(f"--only 认不出 {want!r}（写录音 ID，例 melos-aizuchi-1，或键，例 piece.gate-taken/2）")
            picked += [r for r in hits if r not in picked]
        return [r for r in self.recordings if r in picked]


def _speaker_keys(r: Recording) -> list[str]:
    return [f"{r.speaker.slug}:{k}" for k in r.keys if not k.startswith("piece.")]


def read_spec(book: str, sources: Path = SOURCES) -> Json:
    path = sources / f"{book}.json"
    if not path.is_file():
        raise SpecError(f"没有源文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def world_of(spec: Json, worlds: Path) -> Json:
    path = worlds / spec["book"] / spec["world"] / "world.json"
    if not path.is_file():
        raise SpecError(f"没有世界模型：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def spoken(text: str, readings: dict[str, str]) -> str:
    """只在送给 Live 的那份文字里替换读音；长的词先换。"""
    for word in sorted(readings, key=len, reverse=True):
        text = text.replace(word, readings[word])
    return text


def plan(spec: Json, world: Json) -> Plan:
    chars = {c["id"]: c for c in world["characters"]}
    speakers: dict[str, Speaker] = {}
    for sid, s in spec["speakers"].items():
        if sid not in chars:
            raise SpecError(f"世界模型里没有人物 {sid}")
        loud = s.get("loudness")
        talk = (float(s["talkPitchHz"]), float(s["talkMoraPerS"])) if "talkPitchHz" in s else None
        offsets = {k: float(v) for k, v in s.get("loudnessOffset", {}).items()}
        pieces = {k: float(v) for k, v in s.get("pieceLoudness", {}).items()}
        speakers[sid] = Speaker(
            sid, s["name"], s["voice"], s["direction"], None if loud is None else float(loud), talk, offsets, pieces
        )
    readings: dict[str, str] = spec.get("readings", {})
    scenes: dict[str, str] = spec.get("scenes", {})
    # 说话人块里的 scenes 只管这个人的句子，键可以写「aizuchi/3」这种不分人的槽位；同一个键两处都有时说话人的优先
    own_scenes: dict[str, dict[str, str]] = {sid: s.get("scenes", {}) for sid, s in spec["speakers"].items()}
    used_scenes: set[str] = set()
    used_own: set[tuple[str, str]] = set()
    recs: list[Recording] = []
    by_content: dict[tuple[str, str, str | None], Recording] = {}

    def add(rid: str, sp: Speaker, text: str, key: str) -> None:
        scene = own_scenes[sp.id].get(key)
        if scene is not None:
            used_own.add((sp.id, key))
        else:
            scene = scenes.get(key)
            if scene is not None:
                used_scenes.add(key)
        same = by_content.get((sp.id, text, scene))
        if same is not None:
            same.keys.append(key)
            return
        r = Recording(rid, sp, text, spoken(text, readings), scene, [key])
        by_content[(sp.id, text, scene)] = r
        recs.append(r)

    lines: dict[str, dict[str, list[str]]] = {}
    for sid, s in spec["speakers"].items():
        sp = speakers[sid]
        # 人物的 6 句源文件写了就录：世界模型里这个人此刻不能对话的（切片里的王等五人），manifest 不给（B-6b）
        if "lines" in s:
            got: dict[str, list[str]] = {}
            for slot, n in SLOTS.items():
                raw = s["lines"].get(slot)
                texts = [raw] if isinstance(raw, str) else list(raw or [])
                if len(texts) != n:
                    raise SpecError(f"{sid} 的 {slot} 要 {n} 句，写了 {len(texts)} 句")
                got[slot] = texts
                for i, text in enumerate(texts, 1):
                    add(f"{sp.slug}-{slot}-{i}", sp, text, f"{slot}/{i}")
            lines[sid] = got
        for cue in s.get("cues", []):
            text = _cue_line(world, cue, sid)
            add(f"{sp.slug}-{cue}-1", sp, text, f"cue:{cue}")

    for piece in world.get("setPieces", []):
        for n, line in enumerate(piece.get("lines", []), 1):
            who = line.get("speaker")
            if who is None:
                continue
            if who not in speakers:
                raise SpecError(f"固定演出 {piece['id']} 第 {n} 句的说话人 {who} 没有配声音（源文件 speakers）")
            sp = speakers[who]
            add(f"{sp.slug}-{piece['id'].removeprefix('piece.')}-{n}", sp, line["line"], f"{piece['id']}/{n}")

    def live(sid: str, key: str) -> bool:
        """这个键这次录不录：没有固定演出的世界模型（草稿）里固定演出的键这次用不上，不算写错。"""
        head = key.split("/")[0]
        if head.startswith("piece."):
            return bool(world.get("setPieces"))
        return sid in lines or head not in SLOTS

    heard: dict[str, list[str]] = spec.get("heardAs", {})
    said = {r.text for r in recs}
    if set(heard) - said:
        raise SpecError(f"源文件 heardAs 里的句子对不上任何一条录音：{', '.join(sorted(set(heard) - said))}")
    for r in recs:
        r.heard_as = tuple(heard.get(r.text, ()))
    keys = {(r.speaker.id, k) for r in recs for k in r.keys}
    bad = sorted(
        f"{sid} 的 {k}" for sid, sp in speakers.items() for k in sp.offsets if (sid, k) not in keys and live(sid, k)
    )
    if bad:
        raise SpecError(f"源文件 loudnessOffset 里的键对不上任何一句：{', '.join(bad)}")
    owned = {(r.speaker.id, k.split("/")[0]) for r in recs for k in r.keys}
    bad = sorted(
        f"{sid} 的 {k}" for sid, sp in speakers.items() for k in sp.pieces if (sid, k) not in owned and live(sid, k)
    )
    if bad:
        raise SpecError(f"源文件 pieceLoudness 里的固定演出这个人没有句子：{', '.join(bad)}")
    bad = sorted(r.id for r in recs if r.loudness is None and any(k in r.speaker.offsets for k in r.keys))
    if bad:
        raise SpecError(f"有 loudnessOffset 但没有目标响度（loudness 或 pieceLoudness）：{', '.join(bad)}")
    unused = sorted(k for k in set(scenes) - used_scenes if live("", k)) + sorted(
        f"{sid} 的 {k}" for sid, own in own_scenes.items() for k in own if (sid, k) not in used_own and live(sid, k)
    )
    if unused:
        raise SpecError(f"源文件 scenes 里的键对不上任何一句：{', '.join(unused)}")
    refs = [
        Ref(f"{speakers[sid].slug}-ref-{i}", speakers[sid], TALK_QUESTIONS[i - 1])
        for sid, s in spec["speakers"].items()
        if sid in lines
        for i in range(1, int(s.get("ref", 0)) + 1)
    ]
    return Plan(spec["book"], str(world["worldModelVersion"]), speakers, lines, recs, refs)


def _cue_line(world: Json, cue: str, speaker: str) -> str:
    if cue != "arrival_capped":
        raise SpecError(f"不认识的 cue：{cue}（manifest 的 Prerecorded.cues 只有 arrival_capped）")
    got = world["clock"]["deadline"].get("earliestArrivalCue")
    if not got:
        raise SpecError("世界模型没有 clock.deadline.earliestArrivalCue")
    if got["speaker"] != speaker:
        raise SpecError(f"arrival_capped 的说话人是 {got['speaker']}，源文件写在 {speaker} 下")
    return str(got["line"])
