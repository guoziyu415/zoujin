"""`zoujin-voice`：预录句的生成（B-6 卡「生成脚本」）。

    uv run zoujin-voice                       # 假模型：合成的声音，看流程和输出（CI、项目线程）
    # 真模型：只在 zg 的 Mac 上。先不带 --confirm 跑一次，看条数、遍数和预计花费；在已批的范围内再带 --confirm
    ZJ_MODEL=real ZJ_LEDGER=<账本> ZJ_VERTEX_PROJECT=… ZJ_VERTEX_LOCATION=… \\
        uv run --all-packages --extra real zoujin-voice --max-google-usd <Google 那本账的总上限> [--max-usd 1] --confirm
    uv run zoujin-voice --resume out/b6/<时间> [--only <键> …]  # 都读过了就不调用，重挑、重出 release

- 每句读 3 遍（3 条会话，不在同一条会话里连读）；同一遍里，声音和系统指令相同的句子在同一条会话里一句一轮。每读完一句
  马上补转写。串行，遇到第一个 429 就停；账本到上限（总上限，或这一次跑的上限 `--max-usd`，默认 $1）就停。
- 输出在 `out/b6/<时间>/`：`takes/`（每遍的原始 WAV 和检查用的数字，留在 Mac）、`ref/`（对照用的自由对话）、
  `release/`（选中的 `.m4a`、`voices.json`、`audit.md`、`ref/`）和 `release` 的 zip，最后打印 zip 的 sha256。
  release 里的句子调到说话人的目标响度（源文件的 `loudness`），真峰值压到 −1 dBTP 以下；音量不进签名，改了只重出。
- `--resume <目录>` 接着跑，读过的不再花钱；源文件改了的句子（声音、说明、文字变了）自动重读。`--only` 只重读给定的
  句子（录音 ID 或键，旧的三遍挪进 `takes/discarded/`），清单照样按全部句子重出。
- 日志和账里不写台词的文字，只写键、条数、长度和花费；`audit.md` 里有选中那遍和 ref 的补转写（我们自己的台词稿和对
  固定问题的回答，不是玩家的话）。
- 退出码：0 跑完；2 配置不对；3 到上限或 429 停下（`--resume` 接着跑）；130 Ctrl-C。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shlex
import shutil
import sys
import time
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zoujin_backend.config import REPO, ConfigError, model_mode
from zoujin_backend.models.ledger import Ledger
from zoujin_backend.models.text import BudgetStop, ModelCallFailed, RateLimited, now_z
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.voice import audio, checks
from zoujin_backend.voice.models import (
    LIVE_MODEL,
    TRANSCRIBE_MODEL,
    FakeReader,
    FakeTranscriber,
    Reader,
    ReadFailed,
    Transcriber,
    live_turn_estimate,
    transcribe_estimate,
)
from zoujin_backend.voice.spec import SLOTS, Plan, Recording, Ref, SpecError, plan, read_spec, world_of

Json = Any

TAKES = 3
EXIT_CONFIG, EXIT_STOP = 2, 3
KIND_READ, KIND_TRANSCRIBE = "prerecorded", "prerecorded-transcribe"
MANIFEST = "api/rest/manifest.schema.json"


def parse(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="zoujin-voice", description="B-6：预录句的生成（照读三遍、自动检查、声音清单）")
    p.add_argument("--book", default="hashire-merosu")
    p.add_argument("--out", type=Path, default=Path("out") / "b6", help="新跑的上一级目录（默认 out/b6）")
    p.add_argument("--resume", type=Path, help="接着跑的目录（out/b6/<时间>）")
    p.add_argument(
        "--only", nargs="+", default=[], help="只重读这几句：录音 ID（melos-aizuchi-1）或键（piece.gate-taken/2）"
    )
    p.add_argument("--max-usd", type=float, default=1.0, help="这一次跑（含 --resume 接着跑的）的上限，默认 $1")
    p.add_argument("--max-google-usd", type=float, help="真模型：Google 那本账的总上限（含账本里已有的）")
    p.add_argument("--confirm", action="store_true", help="真模型：看过预计花费，确认要调用")
    return p.parse_args(argv)


# —— 一次跑的目录 ——


def sig(voice: str, system: str, spoken: str) -> str:
    """一句录音的内容签名：声音、系统指令、送给 Live 的文字。源文件改了，签名就变，旧的几遍作废。"""
    return hashlib.sha256(json.dumps([voice, system, spoken], ensure_ascii=False).encode()).hexdigest()[:16]


@dataclass
class Run:
    root: Path
    plan: Plan
    item: str  # 账本里记在哪一项下（这一次跑的上限按它算）

    @property
    def takes(self) -> Path:
        return self.root / "takes"

    @property
    def refs(self) -> Path:
        return self.root / "ref"

    @property
    def release(self) -> Path:
        return self.root / "release"

    def take_meta(self, rid: str, n: int) -> Json | None:
        path = self.takes / f"{rid}.{n}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def write_meta(self, path: Path, doc: Json) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def done(self, r: Recording, n: int) -> bool:
        """这一遍读过、补转写过（或这一轮出错记下了），而且是照现在的源文件读的。"""
        m = self.take_meta(r.id, n)
        return m is not None and m.get("sig") == sig(r.speaker.voice, r.system, r.spoken) and m.get("complete") is True

    def needs_transcript(self, r: Recording, n: int) -> bool:
        m = self.take_meta(r.id, n)
        return (
            m is not None
            and m.get("sig") == sig(r.speaker.voice, r.system, r.spoken)
            and not m.get("complete")
            and (self.takes / f"{r.id}.{n}.wav").is_file()
        )

    def discard(self, r: Recording) -> None:
        """--only：旧的几遍挪到 takes/discarded/<时间>/，不删（留在 Mac 上对照）。"""
        dest = self.takes / "discarded" / time.strftime("%Y%m%d-%H%M%S")
        for p in sorted(self.takes.glob(f"{r.id}.*")):
            dest.mkdir(parents=True, exist_ok=True)
            p.replace(dest / p.name)


def open_run(args: argparse.Namespace, p: Plan) -> Run:
    if args.resume is not None:
        root = args.resume
        meta_path = root / "run.json"
        if not meta_path.is_file():
            raise ConfigError(f"{root} 不是 zoujin-voice 的输出目录（没有 run.json）")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["book"] != p.book:
            raise ConfigError(f"{root} 是 {meta['book']} 的，不是 {p.book}")
        return Run(root, p, meta["item"])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = args.out / stamp
    root.mkdir(parents=True, exist_ok=False)
    item = f"b6/{p.book}/{stamp}"
    meta = {"book": p.book, "worldModelVersion": p.world_version, "item": item, "createdAt": now_z()}
    (root / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return Run(root, p, item)


# —— 要做的事和预计花费 ——


@dataclass
class Work:
    reads: list[tuple[int, Recording]]  # (第几遍, 录音)：要照读的
    transcribe_only: list[tuple[int, Recording]]  # 读过了、还没补转写的
    refs: list[Ref]

    @property
    def empty(self) -> bool:
        return not (self.reads or self.transcribe_only or self.refs)


def pending(run: Run, recs: Sequence[Recording], with_refs: bool) -> Work:
    reads: list[tuple[int, Recording]] = []
    only: list[tuple[int, Recording]] = []
    for n in range(1, TAKES + 1):
        for r in recs:
            if run.done(r, n):
                continue
            (only if run.needs_transcript(r, n) else reads).append((n, r))
    refs = [x for x in run.plan.refs if with_refs and not (run.refs / f"{x.id}.json").is_file()]
    return Work(reads, only, refs)


def sessions(reads: Sequence[tuple[int, Recording]]) -> list[tuple[int, tuple[str, str], list[Recording]]]:
    """按（第几遍, 声音和系统指令）分会话，保持清单的先后。"""
    out: dict[tuple[int, tuple[str, str]], list[Recording]] = {}
    for n, r in reads:
        out.setdefault((n, r.group), []).append(r)
    return [(n, g, rs) for (n, g), rs in out.items()]


MARGIN = 1.3  # 预计花费再加 30% 余量（同 data/cost 的估算表）


def estimate(work: Work, *, regional: bool) -> float:
    """打印给人看的预计花费：逐轮估（偏高）的合计再乘余量。调用前判上限用的是逐轮的估计，不乘。"""
    return MARGIN * _estimate(work, regional=regional)


def _estimate(work: Work, *, regional: bool) -> float:
    usd = 0.0
    for _, (_, system), rs in sessions(work.reads):
        history_s, history_chars = 0.0, 0
        for r in rs:
            usd += live_turn_estimate(system, r.spoken, history_s, history_chars)
            out_s = checks.mora(r.spoken) * 0.25 + 1.0
            usd += transcribe_estimate(out_s, regional=regional)
            history_s += out_s
            history_chars += len(r.spoken) * 2
    for _, r in work.transcribe_only:
        usd += transcribe_estimate(checks.mora(r.spoken) * 0.25 + 1.0, regional=regional)
    for x in work.refs:  # 自由对话一句按 15 秒估
        usd += live_turn_estimate(x.system, x.question, 15.0, 200) + transcribe_estimate(15.0, regional=regional)
    return usd


def describe(run: Run, recs: Sequence[Recording], work: Work, usd: float) -> str:
    keys = sum(len(r.keys) for r in recs)
    return (
        f"{run.plan.book}（{run.plan.world_version}）：{len(recs)} 条录音（{keys} 个键），每条 {TAKES} 遍；"
        f"这次要照读 {len(work.reads)} 轮、补转写 {len(work.reads) + len(work.transcribe_only)} 次，"
        f"对照的自由对话 {len(work.refs)} 句。预计花费（Google，偏高，含 30% 余量）≈ ${usd:.2f}"
    )


# —— 跑 ——


@dataclass
class Spend:
    ledger: Ledger | None
    usd: float = 0.0
    calls: dict[str, int] = field(default_factory=dict)

    def before(self, est: float) -> None:
        if self.ledger is not None:
            self.ledger.before(est)

    def add(self, kind: str, model: str, usage: Mapping[str, int], cost: float) -> None:
        self.usd += cost
        self.calls[kind] = self.calls.get(kind, 0) + 1
        if self.ledger is not None:
            self.ledger.add(kind=kind, model=model, usage=usage, cost=cost)


async def transcribe_take(run: Run, r: Recording, n: int, t: Transcriber, spend: Spend, regional: bool) -> None:
    m = run.take_meta(r.id, n) or {}
    pcm = audio.read_wav(run.takes / f"{r.id}.{n}.wav")
    spend.before(transcribe_estimate(len(pcm) / 2 / audio.RATE, regional=regional))
    heard = await t.transcribe(pcm)
    spend.add(KIND_TRANSCRIBE, TRANSCRIBE_MODEL, heard.usage, heard.cost)
    m.update(transcript=heard.text, complete=True)
    run.write_meta(run.takes / f"{r.id}.{n}.json", m)


async def generate(run: Run, work: Work, reader: Reader, t: Transcriber, spend: Spend, regional: bool) -> None:
    for n, r in work.transcribe_only:
        await transcribe_take(run, r, n, t, spend, regional)
    for n, (voice, system), rs in sessions(work.reads):
        session = await reader.open(voice, system)
        history_s, history_chars = 0.0, 0
        try:
            for r in rs:
                est = live_turn_estimate(system, r.spoken, history_s, history_chars)
                spend.before(est)
                base = {"take": n, "sig": sig(voice, system, r.spoken), "voice": voice, "readAt": now_z()}
                meta_path = run.takes / f"{r.id}.{n}.json"
                try:
                    got = await session.read(f"「{r.spoken}」")
                except ReadFailed as e:
                    # 可能已经计费了：按预计花费记（宁多记）。这条会话的状态说不清了，关掉、下一句开新的
                    spend.add(KIND_READ, LIVE_MODEL, {}, est)
                    run.write_meta(meta_path, base | {"error": str(e), "complete": True})
                    print(f"  {r.id} 第 {n} 遍没读成：{e}")
                    await session.close()
                    session = await reader.open(voice, system)
                    history_s, history_chars = 0.0, 0
                    continue
                spend.add(KIND_READ, LIVE_MODEL, got.usage, got.cost)
                run.takes.mkdir(parents=True, exist_ok=True)
                (run.takes / f"{r.id}.{n}.wav").write_bytes(audio.wav(got.pcm))
                run.write_meta(meta_path, base | {"liveText": got.live_text, "complete": False})
                history_s += len(got.pcm) / 2 / audio.RATE
                history_chars += len(r.spoken) + len(got.live_text)
                await transcribe_take(run, r, n, t, spend, regional)
                print(f"  {r.id} 第 {n} 遍：{len(got.pcm) / 2 / audio.RATE:.2f}s")
        finally:
            await session.close()
    by_speaker: dict[str, list[Ref]] = {}
    for x in work.refs:
        by_speaker.setdefault(x.speaker.id, []).append(x)
    for refs in by_speaker.values():  # 一个人物一条会话，两问依次问（自由对话）
        session = await reader.open(refs[0].speaker.voice, refs[0].system)
        history_s = 0.0
        try:
            for x in refs:
                est = live_turn_estimate(x.system, x.question, history_s + 15.0, 200)
                spend.before(est)
                try:
                    got = await session.read(x.question)
                except ReadFailed as e:
                    spend.add(KIND_READ, LIVE_MODEL, {}, est)
                    print(f"  {x.id} 没读成：{e}（--resume 再试）")
                    break
                spend.add(KIND_READ, LIVE_MODEL, got.usage, got.cost)
                history_s += len(got.pcm) / 2 / audio.RATE
                run.refs.mkdir(parents=True, exist_ok=True)
                (run.refs / f"{x.id}.wav").write_bytes(audio.wav(got.pcm))
                spend.before(transcribe_estimate(len(got.pcm) / 2 / audio.RATE, regional=regional))
                heard = await t.transcribe(got.pcm)
                spend.add(KIND_TRANSCRIBE, TRANSCRIBE_MODEL, heard.usage, heard.cost)
                run.write_meta(run.refs / f"{x.id}.json", {"question": x.question, "transcript": heard.text})
                print(f"  {x.id}：{len(got.pcm) / 2 / audio.RATE:.2f}s")
        finally:
            await session.close()


# —— 检查、挑选、出清单 ——


@dataclass
class Chosen:
    rec: Recording
    verdict: checks.Verdict
    file: str | None = None  # release/ 里的文件名
    duration_ms: int | None = None
    mix: Mix | None = None


@dataclass(frozen=True)
class Mix:
    """构建时的音量：裁好的那段原来多响、目标、调了多少，成品多响、真峰值。"""

    before_dbfs: float
    target_dbfs: float | None
    gain_db: float
    after_dbfs: float
    true_peak_dbtp: float


LOUDNESS_TOL_DB = 1.5  # 和同一人物自由对话差在 ±1.5 dB 以内（UX 量测）


def judge_all(run: Run) -> list[Chosen]:
    out = []
    for r in run.plan.recordings:
        takes: dict[int, tuple[audio.Shape, str | None] | str] = {}
        for n in range(1, TAKES + 1):
            m = run.take_meta(r.id, n)
            if m is None or not m.get("complete"):
                continue
            if "error" in m:
                takes[n] = f"没读成：{m['error']}"
                continue
            pcm = audio.read_wav(run.takes / f"{r.id}.{n}.wav")
            takes[n] = (audio.shape(pcm, pitch=r.aizuchi), m.get("transcript"))
        out.append(Chosen(r, checks.judge(r.text, takes, aizuchi=r.aizuchi, spoken=r.spoken)))
    return out


def url_of(book: str, name: str) -> str:
    return f"/assets/voice/{book}/{name}"


def build_release(run: Run, chosen: list[Chosen], encoder: audio.Encoder, schemas: SchemaBook) -> Json:
    rel = run.release
    if rel.exists():
        shutil.rmtree(rel)
    rel.mkdir(parents=True)
    for c in chosen:
        if c.verdict.chosen is None:
            continue
        raw = audio.read_wav(run.takes / f"{c.rec.id}.{c.verdict.chosen}.wav")
        pcm = audio.trim(raw, audio.shape(raw))
        before = audio.level(pcm).loudness_dbfs
        target = c.rec.speaker.loudness
        gain = 0.0 if target is None else round(target - before, 2)
        enc = encoder.encode(pcm, gain)
        c.file = f"{c.rec.id}.{hashlib.sha256(enc.data).hexdigest()[:8]}{encoder.suffix}"
        c.duration_ms = enc.duration_ms
        c.mix = Mix(before, target, gain, enc.loudness_dbfs, enc.true_peak_dbtp)
        if target is not None and abs(enc.loudness_dbfs - target) > LOUDNESS_TOL_DB:
            c.verdict.flags.append(
                f"调完 {enc.loudness_dbfs:.1f} dBFS，离目标 {target:.1f} 超过 {LOUDNESS_TOL_DB} dB（限幅压下去了？）"
            )
        (rel / c.file).write_bytes(enc.data)
    voices = voices_doc(run.plan, chosen)
    problems = voices_errors(schemas, voices)
    if problems:
        raise ConfigError("voices.json 不合 manifest 的 Schema：" + "；".join(problems))
    (rel / "voices.json").write_text(json.dumps(voices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    refs = []
    for x in run.plan.refs:
        meta = run.refs / f"{x.id}.json"
        if not meta.is_file():
            continue
        raw = audio.read_wav(run.refs / f"{x.id}.wav")
        enc = encoder.encode(audio.trim(raw, audio.shape(raw)))  # 对照用的不调音量，只压真峰值
        name = f"{x.id}{encoder.suffix}"
        (rel / "ref").mkdir(exist_ok=True)
        (rel / "ref" / name).write_bytes(enc.data)
        refs.append((x, name, json.loads(meta.read_text(encoding="utf-8"))["transcript"]))
    (rel / "audit.md").write_text(audit_md(run, chosen, voices, refs), encoding="utf-8")
    return voices


def voices_doc(p: Plan, chosen: list[Chosen]) -> Json:
    """manifest 的两块：人物的 6 句（缺一句这个人物整块不进）和固定演出的键（缺一句只少那个键）。"""
    clips: dict[tuple[str, str], Json] = {}
    for c in chosen:
        if c.file is None or c.duration_ms is None:
            continue
        clip = {"url": url_of(p.book, c.file), "text": c.rec.text, "durationMs": c.duration_ms}
        for k in c.rec.keys:
            clips[(c.rec.speaker.id, k)] = clip
    characters: Json = {}
    for sid in p.lines:
        block: Json = {}
        complete = True
        for slot, n in SLOTS.items():
            got = [clips.get((sid, f"{slot}/{i}")) for i in range(1, n + 1)]
            if any(x is None for x in got):
                complete = False
                break
            block[slot] = got[0] if slot == "wait" else got
        if not complete:
            continue
        block["cues"] = {k.removeprefix("cue:"): v for (s, k), v in clips.items() if s == sid and k.startswith("cue:")}
        characters[sid] = block
    pieces = {k: v for (_, k), v in clips.items() if k.startswith("piece.")}
    return {
        "worldModelVersion": p.world_version,
        "characters": characters,
        "setPieceVoices": dict(sorted(pieces.items())),
    }


def voices_errors(schemas: SchemaBook, doc: Json) -> list[str]:
    out = []
    for sid, block in doc["characters"].items():
        out += [f"{sid}{e}" for e in schemas.errors(MANIFEST, "#/$defs/Prerecorded", block)]
    for key, clip in doc["setPieceVoices"].items():
        out += [f"{key}{e}" for e in schemas.errors(MANIFEST, "#/$defs/SetPieceVoiceKey", key)]
        out += [f"{key}{e}" for e in schemas.errors(MANIFEST, "#/$defs/VoiceClip", clip)]
    return out


def _cell(text: str | None) -> str:
    return (text or "—").replace("|", "｜").replace("\n", " ")


def _mix_cells(m: Mix | None) -> str:
    if m is None:
        return "— | — | —"
    target = "不调" if m.target_dbfs is None else f"{m.target_dbfs:.1f}"
    return (
        f"{m.before_dbfs:.1f} → {m.after_dbfs:.1f} dBFS（{target}） | {m.gain_db:+.1f} dB | {m.true_peak_dbtp:.1f} dBTP"
    )


def audit_md(run: Run, chosen: list[Chosen], voices: Json, refs: list[tuple[Ref, str, str]]) -> str:
    p = run.plan
    passed = [c for c in chosen if c.verdict.chosen is not None]
    lines = [
        f"# 预录句审查单：{p.book}（{p.world_version}）",
        "",
        f"- 跑的目录：`{run.root.name}`；每句 {TAKES} 遍；过了的 {len(passed)}/{len(chosen)} 条。",
        f"- 进声音清单的人物：{', '.join(voices['characters']) or '无'}；"
        f"固定演出的键 {len(voices['setPieceVoices'])} 个。",
        "- 检查（backend-design 3.6）：有声长度和三遍的中位数比（一倍以上、一半以下不要），和拍数估的范围比；"
        f"最后 0.1 秒还有声音算截断；补转写字错率超过 {checks.MAX_CER:.0%} 或原文出现两遍不要。"
        f"相槌另要有声不超过 {checks.AIZUCHI_MAX_S} 秒、裁好不超过 {checks.AIZUCHI_FILE_MAX_S} 秒、有音高的窗至少 "
        f"{checks.AIZUCHI_MIN_PITCHED:.0%}；只在字错率上不过、或原始那遍一开头就有声的相槌不扔，只标出来。",
        "- 音量：有目标响度的说话人（同一人物自由对话的响度）整句调到目标，没有的不动；真峰值都压到 "
        f"{audio.PEAK_DBFS} dBTP 以下。响度是有声的窗的 RMS（UX 量测的做法）。",
        "- 补转写是文本模型听音频写的，古语和生僻词常听错（S-071），字错率高的那几遍请听一下原始的那遍再判。",
        "",
        "## 要 UX 看的",
        "",
    ]
    todo = [c for c in chosen if c.verdict.chosen is None or c.verdict.flags]
    if not todo:
        lines.append("没有：每句都有过了的一遍，也没有标出来的。")
    for c in todo:
        why = "；".join(c.verdict.flags) if c.verdict.chosen is not None else "三遍都不过，不进清单"
        lines.append(f"- `{c.rec.id}`（{'、'.join(c.rec.keys)}）「{c.rec.text}」：{why}")
    missing = [sid for sid in p.lines if sid not in voices["characters"]]
    for sid in missing:
        lines.append(
            f"- {p.speakers[sid].name}（{sid}）的 6 句有没过的，这个人物这次没有 `prerecorded`（前端照没有预录处理）"
        )
    lines += [
        "",
        "## 逐句",
        "",
        "| 录音 | 键 | 声音 | 原文 | 拍数估的范围 | 三遍的有声长度 | 选中 | 文件 | 长度 "
        "| 响度：原 → 成品（目标） | 增益 | 真峰值 | 选中那遍的补转写 | 不过的原因 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in chosen:
        v = c.verdict
        lens = " / ".join("—" if t.speech is None else f"{t.speech:.2f}" for t in v.takes)
        pick = next((t for t in v.takes if t.take == v.chosen), None)
        why = "<br>".join(f"第 {t.take} 遍：{'；'.join(t.problems)}" for t in v.takes if t.problems)
        lines.append(
            f"| `{c.rec.id}` | {'<br>'.join(c.rec.keys)} | {c.rec.speaker.voice} | {_cell(c.rec.text)} "
            f"| {v.expected[0]:.2f}〜{v.expected[1]:.2f}s | {lens} | {v.chosen or '—'} | {c.file or '—'} "
            f"| {'—' if c.duration_ms is None else f'{c.duration_ms} ms'} | {_mix_cells(c.mix)} "
            f"| {_cell(pick.transcript if pick else None)} "
            f"| {why or '—'} |"
        )
    lines += ["", "## 对照用的自由对话（`ref/`，不进声音清单、不进仓库）", ""]
    if not refs:
        lines.append("这次没有。")
    for x, name, heard in refs:
        lines.append(
            f"- `ref/{name}`（{x.speaker.name}，{x.speaker.voice}）问「{x.question}」→ 补转写「{_cell(heard)}」"
        )
    lines += ["", "## 系统指令", ""]
    for voice, system in dict.fromkeys(r.group for r in p.recordings):
        lines += [f"- {voice}：", "", "  ```", *[f"  {s}" for s in system.splitlines()], "  ```"]
    return "\n".join(lines) + "\n"


def zip_release(run: Run) -> tuple[Path, str]:
    """release/ 打成 zip（文件按名字排、时间固定），返回路径和 sha256。"""
    path = run.root / f"b6-release-{run.root.name}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(run.release.rglob("*")):
            if f.is_file():
                info = zipfile.ZipInfo(f"release/{f.relative_to(run.release).as_posix()}", (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes())
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


# —— 入口 ——


def gate(args: argparse.Namespace, env: Mapping[str, str], argv: Sequence[str]) -> list[str]:
    """真模型要齐的东西；少一样就只打印不调用。"""
    missing = []
    if not env.get("ZJ_LEDGER"):
        missing.append("没设 ZJ_LEDGER（Google 那本账）")
    if args.max_google_usd is None:
        missing.append("少 --max-google-usd")
    if not env.get("ZJ_VERTEX_PROJECT") or not env.get("ZJ_VERTEX_LOCATION"):
        missing.append("没设 ZJ_VERTEX_PROJECT / ZJ_VERTEX_LOCATION")
    if not args.confirm:
        missing.append("没带 --confirm")
    cmd = [x for x in argv if x != "--confirm"]
    names = " ".join(f"{k}=…" for k in ("ZJ_MODEL", "ZJ_LEDGER", "ZJ_VERTEX_PROJECT", "ZJ_VERTEX_LOCATION"))
    print(f"命令：{names} uv run --all-packages --extra real zoujin-voice {shlex.join(cmd)} --confirm")
    return missing


@dataclass
class Deps:
    """测试换成假的；None = 按 ZJ_MODEL 建。"""

    reader: Reader | None = None
    transcriber: Transcriber | None = None
    encoder: audio.Encoder | None = None
    ledger: Ledger | None = None
    repo: Path = REPO


def main(argv: Sequence[str] | None = None, deps: Deps | None = None, env: Mapping[str, str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse(argv)
    deps = deps or Deps()
    env = os.environ if env is None else env
    try:
        real = model_mode(env) == "real"
        spec = read_spec(args.book, deps.repo / "services" / "backend" / "voice")
        p = plan(spec, world_of(spec, deps.repo / "worlds"))
        recs = p.select(args.only) if args.only else p.recordings
        if args.resume is None and not args.out.is_absolute():
            args.out = Path.cwd() / args.out
        run = open_run(args, p)
        if args.only:
            for r in recs:
                run.discard(r)
        work = pending(run, recs, with_refs=not args.only)
        regional = env.get("ZJ_VERTEX_LOCATION", "global") != "global"
        print(describe(run, recs, work, estimate(work, regional=regional)))
        print(f"这一次跑的上限 ${args.max_usd:.2f}（账本里记在 {run.item} 下，--resume 接着跑的也算进去）")
        print(f"目录：{run.root}")
        reader, transcriber, ledger = deps.reader, deps.transcriber, deps.ledger
        if real and reader is None:
            missing = gate(args, env, argv)
            if missing:
                print("只打印，不调用：" + "；".join(missing))
                return 0
            from zoujin_backend.voice.models import real_models

            reader, transcriber = real_models(env)
        if ledger is None and real and env.get("ZJ_LEDGER"):
            ledger = Ledger(Path(env["ZJ_LEDGER"]), args.max_google_usd or 0.0, args.max_usd, run.item)
        elif ledger is not None:
            ledger.item, ledger.max_item_usd = run.item, args.max_usd
        if reader is None or transcriber is None:
            fake = FakeReader()
            reader, transcriber = fake, FakeTranscriber(fake)
            if work.reads or work.transcribe_only:
                print("假模型：合成的声音，不调用任何模型")
            else:  # --resume 一个都读完了的目录：只按现在的检查重挑、重出 release，用的全是已录的
                print("都读过了：不调用模型，只用已录的重挑、重出 release")
        encoder = deps.encoder or audio.FfmpegEncoder()
        schemas = SchemaBook(deps.repo / "packages" / "contracts" / "schemas")
    except (ConfigError, SpecError, RuntimeError) as e:
        print(f"zoujin-voice：{e}", file=sys.stderr)
        return EXIT_CONFIG
    spend = Spend(ledger)
    try:
        asyncio.run(generate(run, work, reader, transcriber, spend, regional))
    except (BudgetStop, RateLimited, ModelCallFailed) as e:
        print(f"停下（{type(e).__name__}）：{e}", file=sys.stderr)
        print(f"这次花了 ${spend.usd:.4f}。接着跑：uv run zoujin-voice --resume {run.root}", file=sys.stderr)
        return EXIT_STOP
    except KeyboardInterrupt:
        print(f"中断。接着跑：uv run zoujin-voice --resume {run.root}", file=sys.stderr)
        return 130
    left = pending(run, p.recordings, with_refs=False)
    if left.reads or left.transcribe_only:
        print(f"还有 {len(left.reads)} 遍没读（这次只跑了 --only 的那几句）：先 --resume {run.root} 跑完再出清单")
        return 0
    try:
        chosen = judge_all(run)
        voices = build_release(run, chosen, encoder, schemas)
    except ConfigError as e:
        print(f"zoujin-voice：{e}", file=sys.stderr)
        return EXIT_CONFIG
    path, sha = zip_release(run)
    ok = sum(1 for c in chosen if c.verdict.chosen is not None)
    print(f"这次花了 ${spend.usd:.4f}（{', '.join(f'{k} {v} 次' for k, v in spend.calls.items()) or '没有调用'}）")
    print(f"过了 {ok}/{len(chosen)} 条；进清单的人物 {len(voices['characters'])} 个，", end="")
    print(f"固定演出的键 {len(voices['setPieceVoices'])} 个")
    print(f"审查单：{run.release / 'audit.md'}")
    print(f"zip：{path}  sha256 {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
