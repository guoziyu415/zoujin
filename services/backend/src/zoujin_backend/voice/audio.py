"""照读出来的 PCM（16 位、24 kHz、单声道，Live 的下行格式）：分析、裁静音、调音量、编码成 AAC。

- 有声的范围按 10 毫秒一帧的 RMS 判：高于 `SILENCE_DBFS` 算有声。截断和裁头尾用它。
- 截断：原始那一遍最后 0.1 秒还有声音（没落到静音）。
- 裁头尾：先查截断再裁，有声范围前后各留 80 毫秒；原始那遍头尾不够 80 毫秒的补静音。
- 响度和相槌的长度照 UX 量测的做法（`level`）：40 毫秒的窗、10 毫秒一跳，比最响的窗低 30 dB 以内（且高于 −55 dBFS）
  的算有声；响度 = 这些窗的 RMS。音高（`pitched`）：YIN 找得到周期的窗占几成，耳语找不到。
- 音量：有目标响度的说话人（源文件的 `loudness`，同一人物自由对话的响度）整句调到目标；没有的不动。真峰值都压到
  −1 dBTP 以下（ux-design 16.2 第 3 样，UX 量测）。
- 编码：AAC-LC、单声道、24 kHz、48 kbps 的 `.m4a`（Mac 上用 ffmpeg）；`durationMs` 按转好的文件算（ffprobe）。
"""

from __future__ import annotations

import io
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

RATE = 24_000
FRAME = RATE // 100  # 10 ms
SILENCE_DBFS = -45.0
TAIL_S = 0.1
PAD_S = 0.08
PEAK_DBFS = -1.0  # 真峰值的上限（dBTP）
WIN = 4  # level 的窗：4 帧 = 40 毫秒
REL_GATE_DB = 30.0
FLOOR_DBFS = -55.0
PITCH_RATE = 8_000  # 音高降到 8 kHz 算（纯 Python，快三倍）
PITCH_GATE_DB = 20.0
YIN_THRESH = 0.15
F0_RANGE = (60.0, 400.0)


def samples(pcm: bytes) -> array[int]:
    a = array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def to_bytes(a: array[int]) -> bytes:
    if sys.byteorder == "big":
        a = array("h", a)
        a.byteswap()
    return a.tobytes()


def dbfs(rms: float) -> float:
    return -120.0 if rms <= 0 else 20 * math.log10(rms / 32768)


def _rms(a: array[int], start: int, end: int) -> float:
    n = end - start
    if n <= 0:
        return 0.0
    return math.sqrt(sum(a[i] * a[i] for i in range(start, end)) / n)


@dataclass(frozen=True)
class Shape:
    seconds: float  # 整段
    voiced_start: float  # 第一帧有声的开始（秒）；整段无声时 = seconds
    voiced_end: float  # 最后一帧有声的结束
    tail_voiced: bool  # 最后 0.1 秒还有声音：截断
    peak_dbfs: float
    span: float | None = None  # level 量的有声范围（UX 的做法）；None = 没量，按 speech
    loudness_dbfs: float | None = None
    pitched: float | None = None  # 有音高的窗占几成；None = 没量（只给相槌量，慢）

    @property
    def speech(self) -> float:
        """有声范围的长度（中间的停顿也算）。长度检查都用它，不用整段（头尾的静音每遍不一样）。"""
        return max(0.0, self.voiced_end - self.voiced_start)


def shape(pcm: bytes, *, pitch: bool = False) -> Shape:
    a = samples(pcm)
    n = len(a)
    voiced = [dbfs(_rms(a, i, min(n, i + FRAME))) > SILENCE_DBFS for i in range(0, n, FRAME)]
    first = next((i for i, v in enumerate(voiced) if v), None)
    last = next((i for i in range(len(voiced) - 1, -1, -1) if voiced[i]), None)
    tail = max(0, n - int(RATE * TAIL_S))
    peak = max((abs(x) for x in a), default=0)
    lv = level(pcm)
    return Shape(
        seconds=n / RATE,
        voiced_start=(first * FRAME / RATE) if first is not None else n / RATE,
        voiced_end=min(n, (last + 1) * FRAME) / RATE if last is not None else n / RATE,
        tail_voiced=n > 0 and dbfs(_rms(a, tail, n)) > SILENCE_DBFS,
        peak_dbfs=dbfs(peak),
        span=lv.span,
        loudness_dbfs=lv.loudness_dbfs,
        pitched=pitched(pcm) if pitch else None,
    )


def trim(pcm: bytes, s: Shape) -> bytes:
    """有声范围前后各留 80 毫秒。原始那遍一开头就有声（UX 量到メロス「ああ。」头 10 毫秒 −29 dB）或结尾不够 80 毫秒的，
    补静音补够。"""
    n = len(pcm) // 2
    pad = round(PAD_S * RATE)
    start = round(s.voiced_start * RATE) - pad
    end = round(s.voiced_end * RATE) + pad
    body = pcm[max(0, start) * 2 : min(n, end) * 2]
    return bytes(2 * max(0, -start)) + body + bytes(2 * max(0, end - n))


AAC_FRAME = 1024


def released_seconds(s: Shape) -> float:
    """裁好、补够静音以后的长度，按 AAC 一帧 1024 个采样往上补齐（解码出来就这么长，ffprobe 的 durationMs 略短）。"""
    n = round(s.voiced_end * RATE) - round(s.voiced_start * RATE) + 2 * round(PAD_S * RATE)
    return math.ceil(n / AAC_FRAME) * AAC_FRAME / RATE


def head_voiced(s: Shape) -> bool:
    """原始那遍第一帧就有声：可能被切了头。"""
    return s.voiced_start < FRAME / RATE


@dataclass(frozen=True)
class Level:
    span: float  # 第一个有声的窗到最后一个（秒），中间的停顿也算
    loudness_dbfs: float  # 有声的窗的 RMS


def _block_energy(a: array[int]) -> list[float]:
    return [float(sum(x * x for x in a[i : i + FRAME])) for i in range(0, len(a) - FRAME + 1, FRAME)]


def level(pcm: bytes) -> Level:
    """UX 量测的做法（ux/tools/b6-measure/measure.py）：40 毫秒的窗、10 毫秒一跳；比最响的窗低 30 dB 以内、且高于
    −55 dBFS 的窗算有声。"""
    e = _block_energy(samples(pcm))
    wins = [sum(e[k : k + WIN]) / (WIN * FRAME) for k in range(len(e) - WIN + 1)]  # 窗的均方
    if not wins:
        return Level(0.0, -120.0)
    db = [dbfs(math.sqrt(w)) for w in wins]
    gate = max(max(db) - REL_GATE_DB, FLOOR_DBFS)
    on = [k for k, d in enumerate(db) if d > gate]
    if not on:
        return Level(0.0, -120.0)
    span = (on[-1] - on[0]) * FRAME / RATE + WIN * FRAME / RATE
    return Level(round(span, 3), round(dbfs(math.sqrt(sum(wins[k] for k in on) / len(on))), 2))


def _yin(fr: list[float], rate: int) -> bool:
    """这一窗找不找得到周期（YIN，累计均值归一化差值低于阈值）。"""
    w = len(fr)
    mean = sum(fr) / w
    x = [v - mean for v in fr]
    tmin, tmax = int(rate / F0_RANGE[1]), min(int(rate / F0_RANGE[0]), w // 2)
    total = 0.0
    for tau in range(1, tmax + 1):
        d = sum((x[i] - x[i + tau]) ** 2 for i in range(w - tau))
        total += d
        if tau >= tmin and total > 0 and d * tau / total < YIN_THRESH:
            return True
    return False


def pitched(pcm: bytes) -> float:
    """有音高的窗占几成：比最响的窗低 20 dB 以内的窗里，YIN（阈 0.15、60〜400 Hz）找得到周期的。三个采样取平均降到
    8 kHz 再算（纯 Python）。耳语、气声找不到周期（UX 量到メロス「ああ。」只有头 0.09 秒有音高）。"""
    a = samples(pcm)
    step = RATE // PITCH_RATE
    x = [sum(a[i : i + step]) / step for i in range(0, len(a) - step + 1, step)]
    hop, win = PITCH_RATE // 100, WIN * PITCH_RATE // 100
    frames = [x[k : k + win] for k in range(0, len(x) - win + 1, hop)]
    if not frames:
        return 0.0
    db = [dbfs(math.sqrt(sum(v * v for v in f) / win)) for f in frames]
    loud = [f for f, d in zip(frames, db, strict=True) if d > max(db) - PITCH_GATE_DB]
    return round(sum(_yin(f, PITCH_RATE) for f in loud) / len(loud), 2)


def wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def read_wav(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(f"{path.name}：要 24 kHz、单声道、16 位")
        return w.readframes(w.getnframes())


# —— 编码 ——

TP_TRIES = 6
TP_MARGIN_DB = 0.2


@dataclass(frozen=True)
class Encoded:
    data: bytes
    duration_ms: int
    true_peak_dbtp: float  # 成品的真峰值（假编码器：采样峰值）
    loudness_dbfs: float  # 成品的有声响度（level）


class Encoder(Protocol):
    suffix: str

    def encode(self, pcm: bytes, gain_db: float = 0.0) -> Encoded: ...


class FfmpegEncoder:
    """AAC-LC、单声道、24 kHz、48 kbps 的 m4a。去掉元数据、按位可复现（文件名里的 hash 才稳定）。

    `gain_db` 整句调音量；编完量真峰值（ebur128），超过 −1 dBTP 就加限幅器（alimiter，不自动补增益、补回延迟）
    重编，限幅按超出的量往下调，最多 6 次。没超的不加限幅器。"""

    suffix = ".m4a"

    def __init__(self) -> None:
        for tool in ("ffmpeg", "ffprobe"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"没有 {tool}（Mac 上：brew install ffmpeg）")

    def encode(self, pcm: bytes, gain_db: float = 0.0) -> Encoded:
        limit: float | None = None  # 限幅（dBFS）
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "in.wav", Path(d) / "out.m4a"
            src.write_bytes(wav(pcm))
            for _ in range(TP_TRIES):
                filters = []
                if gain_db:
                    filters.append(f"volume={gain_db:.2f}dB")
                if limit is not None:
                    filters.append(f"alimiter=limit={10 ** (limit / 20):.4f}:level=disabled:latency=1")
                subprocess.run(
                    [
                        "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
                        *(["-af", ",".join(filters)] if filters else []),
                        "-c:a", "aac", "-profile:a", "aac_low", "-ac", "1", "-ar", str(RATE), "-b:a", "48k",
                        "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
                        "-movflags", "+faststart", str(dst),
                    ],
                    check=True,
                )  # fmt: skip
                tp = true_peak(dst)
                if tp <= PEAK_DBFS:
                    return Encoded(dst.read_bytes(), probe_ms(dst), tp, level(decode(dst)).loudness_dbfs)
                limit = (PEAK_DBFS if limit is None else limit) - (tp - PEAK_DBFS) - TP_MARGIN_DB
        raise RuntimeError(f"压了 {TP_TRIES} 次真峰值还在 {tp:.1f} dBTP，超过 {PEAK_DBFS} dBTP")


def probe_ms(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return max(1, round(float(out) * 1000))


def true_peak(path: Path) -> float:
    """ffmpeg ebur128 的真峰值（dBTP），UX 量测用的同一个。"""
    err = subprocess.run(
        ["ffmpeg", "-nostdin", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stderr
    summary = err[err.rfind("Summary:") :]
    for line in summary[summary.find("True peak:") :].splitlines():
        if line.strip().startswith("Peak:"):
            value = line.split(":", 1)[1].split()[0]
            return -120.0 if value == "-inf" else float(value)
    raise RuntimeError("ebur128 没给出真峰值")


def decode(path: Path) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
        check=True,
        capture_output=True,
    ).stdout


class FakeEncoder:
    """CI 用：不调 ffmpeg，「编码」结果就是 WAV，长度按 PCM 算。音量在 Python 里调，峰值硬削到 −1 dBFS。"""

    suffix = ".wav"

    def encode(self, pcm: bytes, gain_db: float = 0.0) -> Encoded:
        if gain_db:
            g = 10 ** (gain_db / 20)
            ceiling = int(32768 * 10 ** (PEAK_DBFS / 20))
            pcm = to_bytes(array("h", (max(-ceiling, min(ceiling, round(x * g))) for x in samples(pcm))))
        peak = dbfs(max((abs(x) for x in samples(pcm)), default=0))
        return Encoded(wav(pcm), max(1, round(len(pcm) / 2 / RATE * 1000)), round(peak, 2), level(pcm).loudness_dbfs)
