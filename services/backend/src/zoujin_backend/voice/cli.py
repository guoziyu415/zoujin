"""`zoujin-voice`: generating the pre-recorded lines (B-6 card "generation script").

`zoujin-voice`：事前収録セリフの生成（B-6 カード「生成スクリプト」）。

    # Fake models: synthesized audio, to see the flow and output (CI, project threads)
    # 偽モデル：合成した音声で流れと出力を見る（CI、プロジェクトスレッド）
    uv run zoujin-voice
    # Real models: only on zg's Mac. First run without --confirm to see the counts, takes and estimated cost; then
    # run with --confirm within the approved budget
    # 本物のモデル：zg の Mac のみ。まず --confirm なしで一度実行し、本数・テイク数・見積もり費用を見る。承認済みの
    # 範囲内で --confirm を付けて実行する
    ZJ_MODEL=real ZJ_LEDGER=<ledger> ZJ_VERTEX_PROJECT=… ZJ_VERTEX_LOCATION=… \\
        uv run --all-packages --extra real zoujin-voice --max-google-usd <Google total cap> [--max-usd 1] --confirm
    # If everything is already read there are no calls: re-pick and re-emit the release
    # すべて読み済みなら呼び出さず、選び直して release を出し直す
    uv run zoujin-voice --resume out/b6/<time> [--only <key> …]

- Each line is read 3 times, aizuchi 6 times (one session per take, never reading in a row within one session); within
  a take, lines with the same voice and system instruction share a session, one line per turn. Each line is
  transcribed right after it is read. Serial; stops at the first 429, and stops when the ledger reaches a cap (the
  total cap, or this run's cap `--max-usd`, default $1).
- Output goes to `out/b6/<time>/`: `takes/` (each take's raw WAV and the numbers used by the checks, kept on the Mac),
  `ref/` (free talk for comparison), `release/` (the chosen `.m4a`, `voices.json`, `audit.md`, `ref/`) and a zip of
  `release`, finally printing the zip's sha256. Lines in the release are brought to the speaker's target loudness (the
  source file's `loudness`) with the true peak held below −1 dBTP; volume is not part of the signature, so changing it
  only means re-emitting.
- `--resume <dir>` continues a run, without paying again for what was read; lines whose source changed (voice,
  direction, text) are re-read automatically. `--only` re-reads only the given lines (recording ID or key; the old takes
  move into `takes/discarded/`), and the manifest is still re-emitted for all lines.
- Every character with 6 lines in the source file is recorded (B-6b: seven people); those who can't be talked to in
  the world model right now are left out of the manifest. `--world` switches the world model (e.g. `1.0.0-draft`): what
  was read isn't read again; with a world model without set pieces, the manifest has no set pieces either.
- Logs and the ledger never contain line text, only keys, counts, lengths and costs; `audit.md` has the transcripts of
  the chosen takes and the refs (our own script and answers to fixed questions, not the player's words).
- Exit codes: 0 done; 2 bad configuration; 3 stopped at a cap or on 429 (continue with `--resume`); 130 Ctrl-C.

- 各句は 3 回、相槌は 6 回読む（1 テイクに 1 セッションで、同じセッションで続けて読まない）。同じテイクの中では、声と
  システム指示が同じ句を同じセッションで 1 句 1 ターンで読む。1 句読むごとにすぐ文字起こしする。直列で実行し、最初の
  429 で止まる。台帳が上限（総上限、またはこの実行の上限 `--max-usd`、デフォルト $1）に達したら止まる。
- 出力は `out/b6/<時刻>/`：`takes/`（各テイクの元の WAV と検査用の数値。Mac に残す）、`ref/`（比較用の自由会話）、
  `release/`（選んだ `.m4a`、`voices.json`、`audit.md`、`ref/`）と `release` の zip。最後に zip の sha256 を表示する。
  release の句は話者の目標ラウドネス（元ファイルの `loudness`）に合わせ、真のピークを −1 dBTP 未満に抑える。音量は
  署名に入らないので、変えたら出し直すだけでよい。
- `--resume <ディレクトリ>` で続きを実行し、読み済みのものに再びお金はかけない。元ファイルが変わった句（声・説明・文字が
  変わったもの）は自動で読み直す。`--only` は指定した句（録音 ID またはキー。古いテイクは `takes/discarded/` に移す）
  だけを読み直し、リストはそれでも全句について出し直す。
- 元ファイルに 6 句が書いてある人物はすべて録る（B-6b：7 人）。世界モデルで今は会話できない人は manifest に出さない。
  `--world` で世界モデルを切り替える（例 `1.0.0-draft`）：読み済みのものは読まない。固定演出のない世界モデルでは、リスト
  にも固定演出はない。
- ログと台帳にはセリフの文字を書かず、キー・本数・長さ・費用だけを書く。`audit.md` には選んだテイクと ref の文字起こしが
  ある（自分たちの台本と決まった質問への答えで、プレイヤーの言葉ではない）。
- 終了コード：0 完了。2 設定の誤り。3 上限または 429 で停止（`--resume` で続ける）。130 Ctrl-C。
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
# Aizuchi are short and few pass (in the second real run on the Mac all 15 takes failed): read 6 takes at once, at
# only $0.0013 a take
# 相槌は短く合格が少ない（Mac での 2 回目の本番実行では 15 テイクすべて不合格）：一度に 6 テイク読む。1 テイクわずか
# $0.0013
AIZUCHI_TAKES = 6


def takes_of(r: Recording) -> int:
    return AIZUCHI_TAKES if r.aizuchi else TAKES


EXIT_CONFIG, EXIT_STOP = 2, 3
KIND_READ, KIND_TRANSCRIBE = "prerecorded", "prerecorded-transcribe"
MANIFEST = "api/rest/manifest.schema.json"


def parse(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="zoujin-voice",
        description="B-6: generate the pre-recorded lines (three read-aloud takes, automatic checks, voice manifest) / "
        "B-6：事前収録セリフの生成（3 テイクの読み上げ、自動検査、音声マニフェスト）",
    )
    p.add_argument("--book", default="hashire-merosu")
    p.add_argument(
        "--world",
        help="World model version directory (worlds/<book>/<this>); defaults to the source file's world / "
        "世界モデルのバージョンディレクトリ（worlds/<book>/<これ>）。デフォルトは元ファイルの world",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("out") / "b6",
        help="Parent directory of a new run (default out/b6) / 新しい実行の親ディレクトリ（デフォルト out/b6）",
    )
    p.add_argument(
        "--resume",
        type=Path,
        help="Directory of the run to continue (out/b6/<time>) / 続きを実行するディレクトリ（out/b6/<時刻>）",
    )
    p.add_argument(
        "--only",
        nargs="+",
        default=[],
        help="Re-read only these lines: recording ID (melos-aizuchi-1) or key (piece.gate-taken/2) / "
        "これらの句だけ読み直す：録音 ID（melos-aizuchi-1）またはキー（piece.gate-taken/2）",
    )
    p.add_argument(
        "--max-usd",
        type=float,
        default=1.0,
        help="Cap for this run (including continuations with --resume), default $1 / "
        "この実行（--resume での続きを含む）の上限。デフォルト $1",
    )
    p.add_argument(
        "--max-google-usd",
        type=float,
        help="Real models: total cap on the Google ledger (including what it already holds) / "
        "本物のモデル：Google 台帳の総上限（台帳に既にある分を含む）",
    )
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Real models: you've seen the estimated cost and confirm the calls / "
        "本物のモデル：見積もり費用を見たうえで呼び出しを承認する",
    )
    return p.parse_args(argv)


# —— A run's directory / 1 回の実行のディレクトリ ——


def sig(voice: str, system: str, spoken: str) -> str:
    """Content signature of a recording: voice, system instruction, and the text sent to Live. When the source file
    changes, the signature changes and the old takes are void.

    録音の内容の署名：声、システム指示、Live に送る文字。元ファイルが変わると署名が変わり、古いテイクは無効になる。
    """
    return hashlib.sha256(json.dumps([voice, system, spoken], ensure_ascii=False).encode()).hexdigest()[:16]


@dataclass
class Run:
    root: Path
    plan: Plan
    # The ledger item it is recorded under (this run's cap is computed from it)
    # 台帳のどの項目に記録するか（この実行の上限はこれで計算する）
    item: str

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
        """This take has been read and transcribed (or the turn's error was recorded), from the current source file.

        このテイクは読み済みで文字起こしも済み（またはこのターンのエラーを記録済み）で、しかも今の元ファイルどおりに
        読んだもの。
        """
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
        """--only: move the old takes to takes/discarded/<time>/ without deleting them (kept on the Mac to compare).

        --only：古いテイクを takes/discarded/<時刻>/ に移し、削除しない（Mac に残して比べる）。
        """
        dest = self.takes / "discarded" / time.strftime("%Y%m%d-%H%M%S")
        for p in sorted(self.takes.glob(f"{r.id}.*")):
            dest.mkdir(parents=True, exist_ok=True)
            p.replace(dest / p.name)


def open_run(args: argparse.Namespace, p: Plan) -> Run:
    if args.resume is not None:
        root = args.resume
        meta_path = root / "run.json"
        if not meta_path.is_file():
            raise ConfigError(
                f"{root} is not a zoujin-voice output directory (no run.json) / "
                f"{root} は zoujin-voice の出力ディレクトリではない（run.json がない）"
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["book"] != p.book:
            raise ConfigError(
                f"{root} belongs to {meta['book']}, not {p.book} / {root} は {p.book} ではなく {meta['book']} のもの"
            )
        return Run(root, p, meta["item"])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = args.out / stamp
    root.mkdir(parents=True, exist_ok=False)
    item = f"b6/{p.book}/{stamp}"
    meta = {"book": p.book, "worldModelVersion": p.world_version, "item": item, "createdAt": now_z()}
    (root / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return Run(root, p, item)


# —— Work to do and estimated cost / やることと見積もり費用 ——


@dataclass
class Work:
    # (take, recording): to be read aloud / （テイク番号、録音）：読み上げるもの
    reads: list[tuple[int, Recording]]
    # Read but not yet transcribed / 読み済みでまだ文字起こししていないもの
    transcribe_only: list[tuple[int, Recording]]
    refs: list[Ref]

    @property
    def empty(self) -> bool:
        return not (self.reads or self.transcribe_only or self.refs)


def pending(run: Run, recs: Sequence[Recording], with_refs: bool, redo: frozenset[str] = frozenset()) -> Work:
    """redo: the --only recording IDs, re-read entirely even if already read.

    redo：--only の録音 ID。読み済みでもすべて読み直す。
    """
    reads: list[tuple[int, Recording]] = []
    only: list[tuple[int, Recording]] = []
    for n in range(1, AIZUCHI_TAKES + 1):
        for r in recs:
            if n > takes_of(r):
                continue
            again = r.id in redo
            if not again and run.done(r, n):
                continue
            (only if not again and run.needs_transcript(r, n) else reads).append((n, r))
    refs = [x for x in run.plan.refs if with_refs and not (run.refs / f"{x.id}.json").is_file()]
    return Work(reads, only, refs)


def sessions(reads: Sequence[tuple[int, Recording]]) -> list[tuple[int, tuple[str, str], list[Recording]]]:
    """Split into sessions by (take, voice and system instruction), keeping the list order.

    （テイク番号、声とシステム指示）でセッションに分け、リストの順序は保つ。
    """
    out: dict[tuple[int, tuple[str, str]], list[Recording]] = {}
    for n, r in reads:
        out.setdefault((n, r.group), []).append(r)
    return [(n, g, rs) for (n, g), rs in out.items()]


# Add a 30% margin to the estimated cost (same as the data/cost estimate sheet)
# 見積もり費用にさらに 30% の余裕を足す（data/cost の見積もり表と同じ）
MARGIN = 1.3


def estimate(work: Work, *, regional: bool) -> float:
    """The estimated cost printed for people: the sum of the per-turn estimates (erring high) times the margin. The cap
    check before each call uses the per-turn estimate without the margin.

    人に見せる見積もり費用：ターンごとの見積もり（高め）の合計に余裕を掛けたもの。呼び出し前の上限判定はターンごとの
    見積もりを使い、余裕は掛けない。
    """
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
    for x in work.refs:  # Free talk: 15 seconds per line / 自由会話は 1 句 15 秒で見積もる
        usd += live_turn_estimate(x.system, x.question, 15.0, 200) + transcribe_estimate(15.0, regional=regional)
    return usd


def describe(run: Run, recs: Sequence[Recording], work: Work, usd: float) -> str:
    keys = sum(len(r.keys) for r in recs)
    book, wv = run.plan.book, run.plan.world_version
    reads, transcribe, refs = len(work.reads), len(work.reads) + len(work.transcribe_only), len(work.refs)
    return (
        f"{book} ({wv}): {len(recs)} recordings ({keys} keys), {TAKES} takes each ({AIZUCHI_TAKES} for aizuchi); "
        f"this run reads aloud {reads} turns, transcribes {transcribe} times, and {refs} free-talk lines for "
        f"comparison. Estimated cost (Google, errs high, incl. 30% margin) ≈ ${usd:.2f} / "
        f"{book}（{wv}）：録音 {len(recs)} 本（キー {keys} 個）、各 {TAKES} テイク（相槌は {AIZUCHI_TAKES} テイク）。"
        f"今回は読み上げ {reads} ターン、文字起こし {transcribe} 回、比較用の自由会話 {refs} 句。"
        f"見積もり費用（Google、高め、30% の余裕込み）≈ ${usd:.2f}"
    )


# —— Running / 実行 ——


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
                    # It may already have been billed: record the estimated cost (better too much). The session's
                    # state is unclear now, so close it and open a new one for the next line
                    # すでに課金されたかもしれない：見積もり費用で記録する（多めに記録するほうがよい）。このセッションの
                    # 状態はもう分からないので閉じ、次の句から新しいセッションを開く
                    spend.add(KIND_READ, LIVE_MODEL, {}, est)
                    run.write_meta(meta_path, base | {"error": str(e), "complete": True})
                    print(f"  {r.id} take {n} not read / テイク {n} 読めず: {e}")
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
                print(f"  {r.id} take {n} / テイク {n}: {len(got.pcm) / 2 / audio.RATE:.2f}s")
        finally:
            await session.close()
    by_speaker: dict[str, list[Ref]] = {}
    for x in work.refs:
        by_speaker.setdefault(x.speaker.id, []).append(x)
    # One session per character, asking the two questions in turn (free talk)
    # 人物ごとに 1 セッションで、2 つの質問を順に聞く（自由会話）
    for refs in by_speaker.values():
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
                    print(f"  {x.id} not read (retry with --resume) / 読めず（--resume で再試行）: {e}")
                    break
                spend.add(KIND_READ, LIVE_MODEL, got.usage, got.cost)
                history_s += len(got.pcm) / 2 / audio.RATE
                run.refs.mkdir(parents=True, exist_ok=True)
                (run.refs / f"{x.id}.wav").write_bytes(audio.wav(got.pcm))
                spend.before(transcribe_estimate(len(got.pcm) / 2 / audio.RATE, regional=regional))
                heard = await t.transcribe(got.pcm)
                spend.add(KIND_TRANSCRIBE, TRANSCRIBE_MODEL, heard.usage, heard.cost)
                run.write_meta(run.refs / f"{x.id}.json", {"question": x.question, "transcript": heard.text})
                print(f"  {x.id}: {len(got.pcm) / 2 / audio.RATE:.2f}s")
        finally:
            await session.close()


# —— Checks, selection, manifest output / 検査・選択・リストの出力 ——


@dataclass
class Chosen:
    rec: Recording
    verdict: checks.Verdict
    file: str | None = None  # File name in release/ / release/ 内のファイル名
    duration_ms: int | None = None
    mix: Mix | None = None


@dataclass(frozen=True)
class Mix:
    """Volume at build time: how loud the trimmed clip was, the target, how much it was adjusted, how loud the output
    is, and its true peak.

    ビルド時の音量：トリムしたクリップの元のラウドネス、目標、調整量、出力のラウドネス、真のピーク。
    """

    before_dbfs: float
    target_dbfs: float | None
    gain_db: float
    after_dbfs: float
    true_peak_dbtp: float


# Within ±1.5 dB of the same character's free talk (UX measurement) / 同じ人物の自由会話との差が ±1.5 dB 以内（UX 計測）
LOUDNESS_TOL_DB = 1.5


def judge_all(run: Run) -> list[Chosen]:
    out = []
    for r in run.plan.recordings:
        takes: dict[int, tuple[audio.Shape, str | None] | str] = {}
        for n in range(1, takes_of(r) + 1):
            m = run.take_meta(r.id, n)
            if m is None or not m.get("complete"):
                continue
            if "error" in m:
                takes[n] = f"Not read / 読めなかった: {m['error']}"
                continue
            pcm = audio.read_wav(run.takes / f"{r.id}.{n}.wav")
            takes[n] = (audio.shape(pcm, pitch=r.aizuchi or r.talk is not None), m.get("transcript"))
        verdict = checks.judge(
            r.text,
            takes,
            aizuchi=r.aizuchi,
            spoken=r.spoken,
            talk=r.talk,
            heard_as=r.heard_as,
            breathy_ok=r.breathy_ok,
        )
        out.append(Chosen(r, verdict))
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
        s = audio.shape(raw)
        pcm = audio.trim(raw, s, audio.aizuchi_pads(s) if c.rec.aizuchi else (audio.PAD_S, audio.PAD_S))
        before = audio.level(pcm).loudness_dbfs
        target = c.rec.loudness
        gain = 0.0 if target is None else round(target - before, 2)
        enc = encoder.encode(pcm, gain)
        c.file = f"{c.rec.id}.{hashlib.sha256(enc.data).hexdigest()[:8]}{encoder.suffix}"
        c.duration_ms = enc.duration_ms
        c.mix = Mix(before, target, gain, enc.loudness_dbfs, enc.true_peak_dbtp)
        if target is not None and abs(enc.loudness_dbfs - target) > LOUDNESS_TOL_DB:
            c.verdict.flags.append(
                f"After adjustment {enc.loudness_dbfs:.1f} dBFS, more than {LOUDNESS_TOL_DB} dB from the target "
                f"{target:.1f} (held down by the limiter?) / 調整後 {enc.loudness_dbfs:.1f} dBFS で、目標 {target:.1f} "
                f"から {LOUDNESS_TOL_DB} dB 以上離れている（リミッターで抑えられた？）"
            )
        (rel / c.file).write_bytes(enc.data)
    voices = voices_doc(run.plan, chosen)
    problems = voices_errors(schemas, voices)
    if problems:
        raise ConfigError(
            "voices.json doesn't match the manifest Schema / voices.json が manifest の Schema に合わない: "
            + "; ".join(problems)
        )
    (rel / "voices.json").write_text(json.dumps(voices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    refs = []
    for x in run.plan.refs:
        meta = run.refs / f"{x.id}.json"
        if not meta.is_file():
            continue
        raw = audio.read_wav(run.refs / f"{x.id}.wav")
        # Comparison clips: no volume adjustment, only the true peak is held down
        # 比較用は音量を調整せず、真のピークだけ抑える
        enc = encoder.encode(audio.trim(raw, audio.shape(raw)))
        name = f"{x.id}{encoder.suffix}"
        (rel / "ref").mkdir(exist_ok=True)
        (rel / "ref" / name).write_bytes(enc.data)
        refs.append((x, name, json.loads(meta.read_text(encoding="utf-8"))["transcript"]))
    (rel / "audit.md").write_text(audit_md(run, chosen, voices, refs), encoding="utf-8")
    return voices


def voices_doc(p: Plan, chosen: list[Chosen]) -> Json:
    """The manifest's two blocks: characters' 6 lines (missing one drops that character's whole block) and set-piece
    keys (missing one drops only that key).

    manifest の 2 ブロック：人物の 6 句（1 句でも欠ければその人物のブロックごと入れない）と固定演出のキー（1 句欠けても
    そのキーだけが抜ける）。
    """
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
    target = "no adjustment / 調整なし" if m.target_dbfs is None else f"{m.target_dbfs:.1f}"
    return (
        f"{m.before_dbfs:.1f} → {m.after_dbfs:.1f} dBFS ({target}) | {m.gain_db:+.1f} dB | {m.true_peak_dbtp:.1f} dBTP"
    )


def audit_md(run: Run, chosen: list[Chosen], voices: Json, refs: list[tuple[Ref, str, str]]) -> str:
    p = run.plan
    passed = [c for c in chosen if c.verdict.chosen is not None]
    chars = ", ".join(voices["characters"])
    n_pieces = len(voices["setPieceVoices"])
    cer, ai_max, ai_file = f"{checks.MAX_CER:.0%}", checks.AIZUCHI_MAX_S, checks.AIZUCHI_FILE_MAX_S
    ai_pitched, st, rate = (
        f"{checks.AIZUCHI_MIN_PITCHED:.0%}",
        f"{checks.TALK_MAX_ST:.0f}",
        f"{checks.TALK_MAX_RATE:.0%}",
    )
    lines = [
        f"# Pre-recorded lines audit sheet: {p.book} ({p.world_version}) / "
        f"事前収録セリフの監査シート：{p.book}（{p.world_version}）",
        "",
        f"- Run directory: `{run.root.name}`; {TAKES} takes per line ({AIZUCHI_TAKES} for aizuchi); "
        f"{len(passed)}/{len(chosen)} passed.",
        f"  実行ディレクトリ：`{run.root.name}`。1 句 {TAKES} テイク（相槌は {AIZUCHI_TAKES} テイク）。"
        f"合格 {len(passed)}/{len(chosen)} 本。",
        f"- Characters in the voice manifest: {chars or 'none'}; {n_pieces} set-piece keys.",
        f"  音声マニフェストに入る人物：{chars or 'なし'}。固定演出のキー {n_pieces} 個。",
        "- Checks (backend-design 3.6): voiced length against the median of the takes (more than double or under half "
        "is rejected) and against the mora-based range; still voiced in the last 0.1 seconds counts as truncated; a "
        f"transcript CER over {cer} or the original appearing twice is rejected. Aizuchi also need voiced ≤ {ai_max} "
        f"seconds, trimmed ≤ {ai_file} seconds and at least {ai_pitched} pitched windows; aizuchi failing only on CER, "
        "or whose raw take is voiced from the very start, are not discarded, only flagged.",
        "  検査（backend-design 3.6）：有声の長さを各テイクの中央値と比べ（2 倍以上・半分未満は不採用）、モーラ数による"
        "範囲とも比べる。最後の 0.1 秒にまだ音があれば途切れとする。文字起こしの文字誤り率が "
        f"{cer} を超えるもの、原文が 2 回出てくるものは不採用。相槌はさらに有声 {ai_max} 秒以下、トリム後 {ai_file} 秒"
        f"以下、ピッチのある窓 {ai_pitched} 以上が必要。文字誤り率だけで不合格の相槌や、元のテイクが冒頭から有声の"
        "相槌は捨てずに印だけ付ける。",
        f'- A character\'s "unheard" and "wait" lines against the same character\'s free talk: takes within '
        f"±{st} semitones of median pitch and ±{rate} speech rate are preferred; if none is, the closest take is "
        "picked and flagged. Speech rate = morae (estimated) ÷ voiced time excluding pauses.",
        f"  人物の「聞き返し」「待って」は同じ人物の自由会話と比べる：ピッチ中央値の差 ±{st} 半音、話速の差 ±{rate} "
        "以内を優先し、どれも範囲外なら最も近いテイクを選んで印を付ける。話速 = モーラ数（推定）÷ 間を除いた有声時間。",
        "- Volume: speakers with a target loudness (the loudness of the same character's free talk) have the whole "
        f"line brought to the target, others are left alone; the true peak is always held below {audio.PEAK_DBFS} "
        "dBTP. Loudness is the RMS of the voiced windows (the UX measurement method).",
        "  音量：目標ラウドネス（同じ人物の自由会話のラウドネス）のある話者はセリフ全体を目標に合わせ、ない話者は"
        f"そのままにする。真のピークはすべて {audio.PEAK_DBFS} dBTP 未満に抑える。ラウドネスは有声の窓の RMS"
        "（UX の計測方法）。",
        "- The transcript is written by a text model listening to the audio and often mishears archaic or rare words "
        "(S-071); for takes with a high CER, please listen to the raw take before deciding.",
        "  文字起こしはテキストモデルが音声を聞いて書いたもので、古語や珍しい語をよく聞き誤る（S-071）。文字誤り率の"
        "高いテイクは、元のテイクを聞いてから判断してほしい。",
        "",
        "## For UX to check / UX が確認するもの",
        "",
    ]
    todo = [c for c in chosen if c.verdict.chosen is None or c.verdict.flags]
    if not todo:
        lines.append(
            "None: every line has a passing take and nothing is flagged. / "
            "なし：すべての句に合格したテイクがあり、印の付いたものもない。"
        )
    for c in todo:
        if c.verdict.chosen is not None:
            why = "; ".join(c.verdict.flags)
        else:
            why = "No take passed; left out of the manifest / どのテイクも不合格、リストに入れない"
        lines.append(f"- `{c.rec.id}` ({', '.join(c.rec.keys)}) 「{c.rec.text}」: {why}")
    missing = [sid for sid in p.lines if sid not in voices["characters"]]
    for sid in missing:
        name = p.speakers[sid].name
        lines.append(
            f"- {name} ({sid}): some of the 6 lines failed, so this character has no `prerecorded` this time (the "
            f"frontend treats it as having no pre-recorded lines) / {name}（{sid}）の 6 句に不合格のものがあり、"
            "この人物には今回 `prerecorded` がない（フロントエンドは事前収録なしとして扱う）"
        )
    lines += [
        "",
        "## Line by line / 句ごと",
        "",
        "| Recording / 録音 | Keys / キー | Voice / 声 | Original / 原文 | Mora-based range / モーラ数による範囲 "
        "| Voiced length per take / 各テイクの有声の長さ | Chosen / 選択 | File / ファイル | Length / 長さ "
        "| Loudness: raw → output (target) / ラウドネス：元 → 出力（目標） | Gain / ゲイン | True peak / 真のピーク "
        "| Chosen take vs free talk / 選んだテイクと自由会話の比較 "
        "| Chosen take's transcript / 選んだテイクの文字起こし | Why rejected / 不合格の理由 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in chosen:
        v = c.verdict
        lens = " / ".join("—" if t.speech is None else f"{t.speech:.2f}" for t in v.takes)
        pick = next((t for t in v.takes if t.take == v.chosen), None)
        why = "<br>".join(f"take {t.take} / テイク {t.take}: {'; '.join(t.problems)}" for t in v.takes if t.problems)
        lines.append(
            f"| `{c.rec.id}` | {'<br>'.join(c.rec.keys)} | {c.rec.speaker.voice} | {_cell(c.rec.text)} "
            f"| {v.expected[0]:.2f}〜{v.expected[1]:.2f}s | {lens} | {v.chosen or '—'} | {c.file or '—'} "
            f"| {'—' if c.duration_ms is None else f'{c.duration_ms} ms'} | {_mix_cells(c.mix)} "
            f"| {_cell(pick.talk if pick else None)} | {_cell(pick.transcript if pick else None)} "
            f"| {why or '—'} |"
        )
    lines += [
        "",
        "## Free talk for comparison (`ref/`, not in the voice manifest or the repo) / "
        "比較用の自由会話（`ref/`。音声マニフェストにもリポジトリにも入れない）",
        "",
    ]
    if not refs:
        lines.append("None this time. / 今回はなし。")
    for x, name, heard in refs:
        lines.append(
            f"- `ref/{name}` ({x.speaker.name}, {x.speaker.voice}) asked / 質問「{x.question}」 → "
            f"transcript / 文字起こし「{_cell(heard)}」"
        )
    lines += ["", "## System instructions / システム指示", ""]
    for voice, system in dict.fromkeys(r.group for r in p.recordings):
        lines += [f"- {voice}:", "", "  ```", *[f"  {s}" for s in system.splitlines()], "  ```"]
    return "\n".join(lines) + "\n"


def zip_release(run: Run) -> tuple[Path, str]:
    """Zip release/ (files sorted by name, fixed timestamps) and return the path and sha256.

    release/ を zip にまとめ（ファイルは名前順、時刻は固定）、パスと sha256 を返す。
    """
    path = run.root / f"b6-release-{run.root.name}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(run.release.rglob("*")):
            if f.is_file():
                info = zipfile.ZipInfo(f"release/{f.relative_to(run.release).as_posix()}", (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes())
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


# —— Entry point / エントリーポイント ——


def gate(args: argparse.Namespace, env: Mapping[str, str], argv: Sequence[str]) -> list[str]:
    """What real models need; if anything is missing, only print and don't call.

    本物のモデルに必要なもの。1 つでも欠けていれば表示だけして呼び出さない。
    """
    missing = []
    if not env.get("ZJ_LEDGER"):
        missing.append("ZJ_LEDGER not set (the Google ledger) / ZJ_LEDGER が未設定（Google の台帳）")
    if args.max_google_usd is None:
        missing.append("--max-google-usd missing / --max-google-usd がない")
    if not env.get("ZJ_VERTEX_PROJECT") or not env.get("ZJ_VERTEX_LOCATION"):
        missing.append(
            "ZJ_VERTEX_PROJECT or ZJ_VERTEX_LOCATION not set / ZJ_VERTEX_PROJECT または ZJ_VERTEX_LOCATION が未設定"
        )
    if not args.confirm:
        missing.append("--confirm not given / --confirm が付いていない")
    cmd = [x for x in argv if x != "--confirm"]
    names = " ".join(f"{k}=…" for k in ("ZJ_MODEL", "ZJ_LEDGER", "ZJ_VERTEX_PROJECT", "ZJ_VERTEX_LOCATION"))
    print(f"Command / コマンド: {names} uv run --all-packages --extra real zoujin-voice {shlex.join(cmd)} --confirm")
    return missing


@dataclass
class Deps:
    """Tests swap in fakes; None = build according to ZJ_MODEL.

    テストでは偽物に差し替える。None = ZJ_MODEL に従って作る。
    """

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
        if args.world:
            spec["world"] = args.world
        p = plan(spec, world_of(spec, deps.repo / "worlds"))
        recs = p.select(args.only) if args.only else p.recordings
        if args.resume is None and not args.out.is_absolute():
            args.out = Path.cwd() / args.out
        run = open_run(args, p)
        redo = frozenset(r.id for r in recs) if args.only else frozenset()
        work = pending(run, recs, with_refs=not args.only, redo=redo)
        regional = env.get("ZJ_VERTEX_LOCATION", "global") != "global"
        print(describe(run, recs, work, estimate(work, regional=regional)))
        cap = f"${args.max_usd:.2f}"
        print(
            f"Cap for this run {cap} (recorded under {run.item} in the ledger; --resume continuations count too) / "
            f"この実行の上限 {cap}（台帳では {run.item} の下に記録。--resume での続きも含む）"
        )
        print(f"Directory / ディレクトリ: {run.root}")
        reader, transcriber, ledger = deps.reader, deps.transcriber, deps.ledger
        if real and reader is None:
            missing = gate(args, env, argv)
            if missing:
                print("Print only, no calls / 表示のみで呼び出さない: " + "; ".join(missing))
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
                print(
                    "Fake models: synthesized audio, no model is called / "
                    "偽モデル：合成した音声で、モデルは一切呼び出さない"
                )
            else:
                # --resume of a directory where everything is read: only re-pick by the current checks and re-emit
                # the release, all from existing takes
                # すべて読み済みのディレクトリを --resume：今の検査で選び直して release を出し直すだけで、すべて
                # 録音済みのものを使う
                print(
                    "All takes already read: no model calls, re-picking and re-emitting the release from existing "
                    "takes / すべて読み済み：モデルは呼び出さず、録音済みのものだけで選び直して release を出し直す"
                )
        encoder = deps.encoder or audio.FfmpegEncoder()
        schemas = SchemaBook(deps.repo / "packages" / "contracts" / "schemas")
        # A run that only prints the estimate leaves the old takes alone: they move only on a real run
        # 見積もりを表示するだけの実行では古いテイクを動かさない：本当に実行するときだけ移す
        for r in recs if args.only else []:
            run.discard(r)
    except (ConfigError, SpecError, RuntimeError) as e:
        print(f"zoujin-voice: {e}", file=sys.stderr)
        return EXIT_CONFIG
    spend = Spend(ledger)
    try:
        asyncio.run(generate(run, work, reader, transcriber, spend, regional))
    except (BudgetStop, RateLimited, ModelCallFailed) as e:
        print(f"Stopped / 停止 ({type(e).__name__}): {e}", file=sys.stderr)
        resume = f"uv run zoujin-voice --resume {run.root}"
        print(
            f"Spent ${spend.usd:.4f} this time. To continue: {resume} / 今回の費用 ${spend.usd:.4f}。続きは：{resume}",
            file=sys.stderr,
        )
        return EXIT_STOP
    except KeyboardInterrupt:
        resume = f"uv run zoujin-voice --resume {run.root}"
        print(f"Interrupted. To continue: {resume} / 中断。続きは：{resume}", file=sys.stderr)
        return 130
    left = pending(run, p.recordings, with_refs=False)
    if left.reads or left.transcribe_only:
        n = len(left.reads)
        print(
            f"{n} takes still unread (this run only did the --only lines): finish with --resume {run.root} before "
            f"the manifest is emitted / まだ読んでいないテイクが {n} 本（今回は --only の句だけ実行）："
            f"--resume {run.root} で最後まで実行してからリストを出す"
        )
        return 0
    try:
        chosen = judge_all(run)
        voices = build_release(run, chosen, encoder, schemas)
    except ConfigError as e:
        print(f"zoujin-voice: {e}", file=sys.stderr)
        return EXIT_CONFIG
    path, sha = zip_release(run)
    ok = sum(1 for c in chosen if c.verdict.chosen is not None)
    calls_en = ", ".join(f"{k} ×{v}" for k, v in spend.calls.items()) or "no calls"
    calls_ja = "、".join(f"{k} {v} 回" for k, v in spend.calls.items()) or "呼び出しなし"
    print(f"Spent ${spend.usd:.4f} this time ({calls_en}) / 今回の費用 ${spend.usd:.4f}（{calls_ja}）")
    n_chars, n_keys = len(voices["characters"]), len(voices["setPieceVoices"])
    print(
        f"Passed {ok}/{len(chosen)}; {n_chars} characters and {n_keys} set-piece keys in the manifest / "
        f"合格 {ok}/{len(chosen)} 本。リストに入る人物 {n_chars} 人、固定演出のキー {n_keys} 個"
    )
    print(f"Audit sheet / 監査シート: {run.release / 'audit.md'}")
    print(f"zip: {path}  sha256 {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
