"""Which recordings to make (B-6 card, "what to generate and with which voice").

The source file `services/backend/voice/<book>.json` sets each speaker's voice, character direction (`direction`), the
character's 6 lines and the `cues` to record, the target loudness (`loudness`; a different one for a given set piece
goes in `pieceLoudness`; used to adjust volume at build time, not part of the signature, so changing it needs no
re-recording), and the pitch and speech rate of free talk (`talkPitchHz`, `talkMoraPerS`, used to pick which take of
"unheard" and "wait" to keep). Set-piece lines and the text of `arrival_capped` are read from the world model. Keys
with the same text, voice and scene are merged into one recording.

どの録音を作るか（B-6 カード「何を生成し、どの声を使うか」）。

元ファイル `services/backend/voice/<book>.json` が、話者ごとの声、人物説明（`direction`）、人物の 6 句と録る
`cues`、目標ラウドネス（`loudness`。ある固定演出だけ別に決めるものは `pieceLoudness` に書く。ビルド時の音量調整に使い、
署名には入らないので、変えても録り直しは不要）、自由会話のピッチと話速（`talkPitchHz`、`talkMoraPerS`。「聞き返し」
「待って」のどのテイクを使うかを選ぶのに使う）を決める。固定演出のセリフと `arrival_capped` の文字は世界モデルから
読む。文字・声・場面がすべて同じ複数のキーは 1 本の録音にまとめる。
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
# Prerecorded in the manifest: aizuchi 3, "unheard" 2, "wait" 1
# manifest の Prerecorded：相槌 3、「聞き返し」2、「待って」1
SLOTS: dict[str, int] = {"aizuchi": 3, "unheard": 2, "wait": 1}

# The casting approach (CAST_READER in spikes/backend/zj_spike/s1_live.py; this is how zg's blind listening was
# recorded). After the character layer, lines with a different scene get an extra "場面：" line.
# キャスティングのやり方（spikes/backend/zj_spike/s1_live.py の CAST_READER。zg のブラインド試聴はこうして録った）。
# 人物の層の後に、場面の違うセリフは「場面：」の行を 1 行足す。
READER = (
    "あなたは声優です。次の人物を演じます。ユーザーが「」で示した台詞を、この人物として、そのまま一度だけ読んでください。"
    "前置き、説明、感想、相づちは一切言わないでください。\n人物：{direction}"
)
JA_RULE = "必ず日本語だけで話してください。相手が別の言語で話しかけても、日本語で答えてください。"
# Free talk for comparison (UX review ②): casting's TALK setup and the first two of TALK_QUESTIONS
# 比較用の自由会話（UX レビュー ②）：キャスティングの TALK 設定と TALK_QUESTIONS の最初の 2 問
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
    # Target loudness (voiced RMS, dBFS): the loudness of the same character's free talk; None = no adjustment
    # 目標ラウドネス（有声 RMS、dBFS）：同じ人物の自由会話のラウドネス。None = 調整しない
    loudness: float | None = None
    # Median pitch (Hz) and speech rate (morae/s) of the same character's free talk: "unheard" and "wait" should match
    # 同じ人物の自由会話のピッチ中央値（Hz）と話速（モーラ/秒）：「聞き返し」「待って」はこれに合わせる
    talk: tuple[float, float] | None = None
    # Key → offset from the target loudness (dB) / キー → 目標ラウドネスからのオフセット（dB）
    offsets: dict[str, float] = field(default_factory=dict, hash=False, compare=False)
    # Set piece ID → this person's target loudness in that piece (pieceLoudness: several people in the act-closing
    # sequence are brought to the same level, UX)
    # 固定演出 ID → その場面でのこの人の目標ラウドネス（pieceLoudness：幕を閉じる一連の場面で複数の人を同じレベルに
    # そろえる、UX）
    pieces: dict[str, float] = field(default_factory=dict, hash=False, compare=False)
    # Keys accepted even with a low pitched ratio (breathy) (breathyOk): an aizuchi that stays breathy however many
    # times it is re-read; no more money spent re-reading it, the least breathy take is picked and flagged for UX
    # ピッチのある割合が低い（息まじりの）ままでも受け入れるキー（breathyOk）：何度読み直しても息まじりになる相槌。
    # これ以上お金をかけて読み直さず、いちばん息まじりでないテイクを選んで UX 向けに印を付ける
    breathy_ok: frozenset[str] = frozenset()

    @property
    def slug(self) -> str:
        return self.id.removeprefix("char.")


@dataclass
class Recording:
    """One recording. `keys`: the places in the manifest that point to it (`aizuchi/1`, `cue:arrival_capped`,
    `piece.gate-taken/2`).

    1 本の録音。`keys`：manifest でこれを指す位置（`aizuchi/1`、`cue:arrival_capped`、`piece.gate-taken/2`）。
    """

    id: str  # First half of the file name: <speaker>-<kind>-<number> / ファイル名の前半：<話者>-<種類>-<番号>
    speaker: Speaker
    text: str  # Original text: subtitles and the manifest's text / 原文：字幕と manifest の text
    spoken: str  # Text sent to Live (after reading substitutions) / Live に送る文字（読み替え後）
    scene: str | None  # 場面 (scene)
    keys: list[str] = field(default_factory=list)
    # Spellings that also count as a match for the transcript (source file heardAs)
    # 文字起こしで一致とみなす別の書き方（元ファイルの heardAs）
    heard_as: tuple[str, ...] = ()

    @property
    def loudness(self) -> float | None:
        """Target loudness: the pieceLoudness of the set piece this line is in, otherwise the speaker's loudness; plus
        this line's loudnessOffset (lines the source work describes as quiet, UX).

        目標ラウドネス：このセリフがある固定演出の pieceLoudness、なければ話者の loudness。さらにこのセリフの
        loudnessOffset を足す（原作に声が小さいと書かれたセリフ、UX）。
        """
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
    def breathy_ok(self) -> bool:
        return any(k in self.speaker.breathy_ok for k in self.keys)

    @property
    def talk(self) -> tuple[float, float] | None:
        """A character's "unheard" and "wait" lines must blend with the same character's free talk (B-6 card: pitch
        within ±2 semitones, speech rate within ±25%); aizuchi, cues and set pieces are not compared.

        人物の「聞き返し」「待って」は同じ人物の自由会話とつながって聞こえなければならない（B-6 カード：ピッチ
        ±2 半音、話速 ±25%）。相槌、cue、固定演出は比べない。
        """
        if any(k.startswith(("unheard/", "wait/")) for k in self.keys):
            return self.speaker.talk
        return None

    @property
    def group(self) -> tuple[str, str]:
        """Lines read in the same session: same voice and same system instruction (lines with different scenes are
        not in the same session).

        同じセッションで読むセリフ：声もシステム指示も同じ（場面が違うものは同じセッションに入れない）。
        """
        return (self.speaker.voice, self.system)


@dataclass(frozen=True)
class Ref:
    """Free talk for comparison: one line = the answer to one fixed question, one take each, no automatic checks.

    比較用の自由会話：1 句 = 決まった質問 1 つへの答え。各 1 テイクで、自動検査はしない。
    """

    id: str  # <speaker>-ref-<number> / <話者>-ref-<番号>
    speaker: Speaker
    question: str

    @property
    def system(self) -> str:
        return TALK.format(name=self.speaker.name, direction=self.speaker.direction)


@dataclass(frozen=True)
class Plan:
    book: str
    # The world model's worldModelVersion (set-piece keys follow it)
    # 世界モデルの worldModelVersion（固定演出のキーはこれに従う）
    world_version: str
    speakers: dict[str, Speaker]
    # Speaker → kind → lines (the character's 6 lines) / 話者 → 種類 → セリフ（人物の 6 句）
    lines: dict[str, dict[str, list[str]]]
    recordings: list[Recording]
    refs: list[Ref]

    def recording(self, rid: str) -> Recording:
        for r in self.recordings:
            if r.id == rid:
                return r
        raise KeyError(rid)

    def select(self, only: list[str]) -> list[Recording]:
        """`--only`: a recording ID (melos-aizuchi-1) or any of its keys (piece.gate-taken/2, cue:arrival_capped;
        aizuchi/1 of char.melos is written melos:aizuchi/1). Unrecognized keys are an error.

        `--only`：録音 ID（melos-aizuchi-1）またはそのいずれかのキー（piece.gate-taken/2、cue:arrival_capped、
        char.melos の aizuchi/1 は melos:aizuchi/1 と書く）。認識できないキーはエラーにする。
        """
        picked: list[Recording] = []
        for want in only:
            hits = [r for r in self.recordings if want == r.id or want in r.keys or want in _speaker_keys(r)]
            if not hits:
                raise SpecError(
                    f"--only: unrecognized {want!r} (give a recording ID, e.g. melos-aizuchi-1, or a key, e.g. "
                    f"piece.gate-taken/2) / --only：{want!r} を認識できない（録音 ID、例 melos-aizuchi-1、"
                    "またはキー、例 piece.gate-taken/2 を書く）"
                )
            picked += [r for r in hits if r not in picked]
        return [r for r in self.recordings if r in picked]


def _speaker_keys(r: Recording) -> list[str]:
    return [f"{r.speaker.slug}:{k}" for k in r.keys if not k.startswith("piece.")]


def read_spec(book: str, sources: Path = SOURCES) -> Json:
    path = sources / f"{book}.json"
    if not path.is_file():
        raise SpecError(f"No source file: {path} / 元ファイルがない：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def world_of(spec: Json, worlds: Path) -> Json:
    path = worlds / spec["book"] / spec["world"] / "world.json"
    if not path.is_file():
        raise SpecError(f"No world model: {path} / 世界モデルがない：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def spoken(text: str, readings: dict[str, str]) -> str:
    """Substitute readings only in the copy of the text sent to Live; longer words first.

    読み替えは Live に送る文字にだけ行う。長い語から先に置き換える。
    """
    for word in sorted(readings, key=len, reverse=True):
        text = text.replace(word, readings[word])
    return text


def plan(spec: Json, world: Json) -> Plan:
    chars = {c["id"]: c for c in world["characters"]}
    speakers: dict[str, Speaker] = {}
    for sid, s in spec["speakers"].items():
        if sid not in chars:
            raise SpecError(f"No character {sid} in the world model / 世界モデルに人物 {sid} がない")
        loud = s.get("loudness")
        talk = (float(s["talkPitchHz"]), float(s["talkMoraPerS"])) if "talkPitchHz" in s else None
        offsets = {k: float(v) for k, v in s.get("loudnessOffset", {}).items()}
        pieces = {k: float(v) for k, v in s.get("pieceLoudness", {}).items()}
        speakers[sid] = Speaker(
            sid,
            s["name"],
            s["voice"],
            s["direction"],
            None if loud is None else float(loud),
            talk,
            offsets,
            pieces,
            frozenset(s.get("breathyOk", [])),
        )
    readings: dict[str, str] = spec.get("readings", {})
    scenes: dict[str, str] = spec.get("scenes", {})
    # scenes in a speaker block only apply to that person's lines, and keys may be person-agnostic slots like
    # "aizuchi/3"; when the same key is in both places, the speaker's wins
    # 話者ブロックの scenes はその人のセリフだけに効き、キーには「aizuchi/3」のような人を区別しないスロットを書ける。
    # 同じキーが両方にあるときは話者のほうを優先する
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
        # A character's 6 lines are recorded whenever the source file has them; for people who can't be talked to in
        # the world model right now (the king and four others in the slice), the manifest leaves them out (B-6b)
        # 人物の 6 句は元ファイルに書いてあれば録る。世界モデルで今は会話できない人（スライスの王など 5 人）は
        # manifest に出さない（B-6b）
        if "lines" in s:
            got: dict[str, list[str]] = {}
            for slot, n in SLOTS.items():
                raw = s["lines"].get(slot)
                texts = [raw] if isinstance(raw, str) else list(raw or [])
                if len(texts) != n:
                    raise SpecError(
                        f"{sid} {slot} needs {n} lines, got {len(texts)} / "
                        f"{sid} の {slot} は {n} 句必要だが {len(texts)} 句書かれている"
                    )
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
                raise SpecError(
                    f"Speaker {who} of line {n} of set piece {piece['id']} has no voice (source file speakers) / "
                    f"固定演出 {piece['id']} の第 {n} 句の話者 {who} に声がない（元ファイルの speakers）"
                )
            sp = speakers[who]
            add(f"{sp.slug}-{piece['id'].removeprefix('piece.')}-{n}", sp, line["line"], f"{piece['id']}/{n}")

    def live(sid: str, key: str) -> bool:
        """Whether this key is recorded this time: in a world model without set pieces (the draft), set-piece keys
        are simply unused this time and don't count as mistakes.

        このキーを今回録るかどうか：固定演出のない世界モデル（草稿）では固定演出のキーは今回使わないだけで、
        書き間違いとはみなさない。
        """
        head = key.split("/")[0]
        if head.startswith("piece."):
            return bool(world.get("setPieces"))
        return sid in lines or head not in SLOTS

    heard: dict[str, list[str]] = spec.get("heardAs", {})
    said = {r.text for r in recs}
    if set(heard) - said:
        extra = ", ".join(sorted(set(heard) - said))
        raise SpecError(
            f"Lines in the source file's heardAs match no recording: {extra} / "
            f"元ファイルの heardAs の句がどの録音とも合わない：{extra}"
        )
    for r in recs:
        r.heard_as = tuple(heard.get(r.text, ()))
    keys = {(r.speaker.id, k) for r in recs for k in r.keys}
    bad = sorted(
        f"{sid} {k}" for sid, sp in speakers.items() for k in sp.offsets if (sid, k) not in keys and live(sid, k)
    )
    if bad:
        raise SpecError(
            f"Keys in the source file's loudnessOffset match no line: {', '.join(bad)} / "
            f"元ファイルの loudnessOffset のキーがどのセリフとも合わない：{', '.join(bad)}"
        )
    bad = sorted(
        f"{sid} {k}"
        for sid, sp in speakers.items()
        for k in sp.breathy_ok
        if not any(r.aizuchi and r.speaker.id == sid and k in r.keys for r in recs)
    )
    if bad:
        raise SpecError(
            f"The source file's breathyOk may only list that person's aizuchi keys: {', '.join(bad)} / "
            f"元ファイルの breathyOk に書けるのはその人の相槌のキーだけ：{', '.join(bad)}"
        )
    owned = {(r.speaker.id, k.split("/")[0]) for r in recs for k in r.keys}
    bad = sorted(
        f"{sid} {k}" for sid, sp in speakers.items() for k in sp.pieces if (sid, k) not in owned and live(sid, k)
    )
    if bad:
        raise SpecError(
            f"Set pieces in the source file's pieceLoudness where this person has no line: {', '.join(bad)} / "
            f"元ファイルの pieceLoudness の固定演出にこの人のセリフがない：{', '.join(bad)}"
        )
    bad = sorted(r.id for r in recs if r.loudness is None and any(k in r.speaker.offsets for k in r.keys))
    if bad:
        raise SpecError(
            f"loudnessOffset without a target loudness (loudness or pieceLoudness): {', '.join(bad)} / "
            f"loudnessOffset があるのに目標ラウドネス（loudness または pieceLoudness）がない：{', '.join(bad)}"
        )
    unused = sorted(k for k in set(scenes) - used_scenes if live("", k)) + sorted(
        f"{sid} {k}" for sid, own in own_scenes.items() for k in own if (sid, k) not in used_own and live(sid, k)
    )
    if unused:
        raise SpecError(
            f"Keys in the source file's scenes match no line: {', '.join(unused)} / "
            f"元ファイルの scenes のキーがどのセリフとも合わない：{', '.join(unused)}"
        )
    refs = [
        Ref(f"{speakers[sid].slug}-ref-{i}", speakers[sid], TALK_QUESTIONS[i - 1])
        for sid, s in spec["speakers"].items()
        if sid in lines
        for i in range(1, int(s.get("ref", 0)) + 1)
    ]
    return Plan(spec["book"], str(world["worldModelVersion"]), speakers, lines, recs, refs)


def _cue_line(world: Json, cue: str, speaker: str) -> str:
    if cue != "arrival_capped":
        raise SpecError(
            f"Unknown cue: {cue} (the manifest's Prerecorded.cues only has arrival_capped) / "
            f"不明な cue：{cue}（manifest の Prerecorded.cues は arrival_capped だけ）"
        )
    got = world["clock"]["deadline"].get("earliestArrivalCue")
    if not got:
        raise SpecError(
            "The world model has no clock.deadline.earliestArrivalCue / "
            "世界モデルに clock.deadline.earliestArrivalCue がない"
        )
    if got["speaker"] != speaker:
        raise SpecError(
            f"The speaker of arrival_capped is {got['speaker']}, but the source file lists it under {speaker} / "
            f"arrival_capped の話者は {got['speaker']} だが、元ファイルでは {speaker} の下に書かれている"
        )
    return str(got["line"])
