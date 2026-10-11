"""照读出来的 PCM（16 位、24 kHz、单声道，Live 的下行格式）：分析、裁静音、调音量、编码成 AAC。

- 有声的范围按 10 毫秒一帧的 RMS 判：高于 `SILENCE_DBFS` 算有声。截断和裁头尾用它。
- 截断：原始那一遍最后 0.1 秒还有声音（没落到静音）。
- 裁头尾：先查截断再裁，有声范围前后各留 80 毫秒（相槌头 20、尾 80；硬起头的各 50）；原始那遍头尾不够的补静音。
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
import statistics
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
# 相槌两头合计只留 0.1 秒：UX 的「有声 ≤ 0.5 秒、整个文件 ≤ 0.6 秒」两条才是一个意思（两头各 80 毫秒时文件那条更紧，
# 有声只能到 0.44 秒；Mac 上第二次真跑 15 遍里好几遍只差这一点）。头 20 毫秒、尾 80 毫秒（声音早出来，尾巴留着收音）；
# 起头有台阶的（第一帧有声就离最响的帧不到 6 dB，硬起头）头尾各 50 毫秒（UX）
AIZUCHI_PADS = (0.02, 0.08)
AIZUCHI_STEP_PADS = (0.05, 0.05)
ONSET_STEP_DB = 6.0
PEAK_DBFS = -1.0  # 真峰值的上限（dBTP）
WIN = 4  # level 的窗：4 帧 = 40 毫秒
REL_GATE_DB = 30.0
FLOOR_DBFS = -55.0
MERGE_GAP_S = 0.06
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
    onset_db: float | None = None  # 第一帧有声比最响的一帧低多少 dB（≥ 0）；None = 没有声音
    span: float | None = None  # level 量的有声范围（UX 的做法）；None = 没量，按 speech
    loudness_dbfs: float | None = None
    pitched: float | None = None  # 有音高的窗占几成；None = 没量（只给要比的句子量，慢）
    pitch_hz: float | None = None  # 有音高的窗的基频中位数
    sounding: float | None = None  # 不算停顿的有声时间

    @property
    def speech(self) -> float:
        """有声范围的长度（中间的停顿也算）。长度检查都用它，不用整段（头尾的静音每遍不一样）。"""
        return max(0.0, self.voiced_end - self.voiced_start)


def shape(pcm: bytes, *, pitch: bool = False) -> Shape:
    a = samples(pcm)
    n = len(a)
    frame_db = [dbfs(_rms(a, i, min(n, i + FRAME))) for i in range(0, n, FRAME)]
    voiced = [d > SILENCE_DBFS for d in frame_db]
    first = next((i for i, v in enumerate(voiced) if v), None)
    last = next((i for i in range(len(voiced) - 1, -1, -1) if voiced[i]), None)
    tail = max(0, n - int(RATE * TAIL_S))
    peak = max((abs(x) for x in a), default=0)
    lv = level(pcm)
    pt = pitch_of(pcm) if pitch else None
    return Shape(
        seconds=n / RATE,
        voiced_start=(first * FRAME / RATE) if first is not None else n / RATE,
        voiced_end=min(n, (last + 1) * FRAME) / RATE if last is not None else n / RATE,
        tail_voiced=n > 0 and dbfs(_rms(a, tail, n)) > SILENCE_DBFS,
        peak_dbfs=dbfs(peak),
        onset_db=None if first is None else round(max(frame_db) - frame_db[first], 1),
        span=lv.span,
        loudness_dbfs=lv.loudness_dbfs,
        sounding=lv.sounding,
        pitched=pt.pitched if pt else None,
        pitch_hz=pt.median_hz if pt else None,
    )


def trim(pcm: bytes, s: Shape, pads: tuple[float, float] = (PAD_S, PAD_S)) -> bytes:
    """有声范围前后各留 80 毫秒（相槌见 `aizuchi_pads`）。原始那遍一开头就有声（UX 量到メロス「ああ。」头 10 毫秒
    −29 dB）或结尾不够的，补静音补够。"""
    n = len(pcm) // 2
    start = round(s.voiced_start * RATE) - round(pads[0] * RATE)
    end = round(s.voiced_end * RATE) + round(pads[1] * RATE)
    body = pcm[max(0, start) * 2 : min(n, end) * 2]
    return bytes(2 * max(0, -start)) + body + bytes(2 * max(0, end - n))


def aizuchi_pads(s: Shape) -> tuple[float, float]:
    step = s.onset_db is not None and s.onset_db < ONSET_STEP_DB
    return AIZUCHI_STEP_PADS if step else AIZUCHI_PADS


def released_seconds(s: Shape, pads: tuple[float, float]) -> float:
    """裁好、补够静音以后的长度。按 AAC 补帧之前算（补的是静音，UX）。"""
    return round(s.speech + pads[0] + pads[1], 3)


def head_voiced(s: Shape) -> bool:
    """原始那遍第一帧就有声：可能被切了头。"""
    return s.voiced_start < FRAME / RATE


@dataclass(frozen=True)
class Level:
    span: float  # 第一个有声的窗到最后一个（秒），中间的停顿也算
    loudness_dbfs: float  # 有声的窗的 RMS
    sounding: float = 0.0  # 不算停顿的有声时间（不到 60 毫秒的停顿并起来）：语速用


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
    hop, win = FRAME / RATE, WIN * FRAME / RATE
    segs = [[on[0], on[0]]]
    for k in on[1:]:
        if (k - segs[-1][1] - 1) * hop < MERGE_GAP_S:
            segs[-1][1] = k
        else:
            segs.append([k, k])
    sounding = sum((b - a) * hop + win for a, b in segs)
    span = (on[-1] - on[0]) * hop + win
    loud = dbfs(math.sqrt(sum(wins[k] for k in on) / len(on)))
    return Level(round(span, 3), round(loud, 2), round(sounding, 3))


def _yin(fr: list[float], rate: int) -> float | None:
    """这一窗的基频（Hz）；找不到周期（累计均值归一化差值都不低于阈值）为 None。和 UX 的一样：过阈以后再往下走到谷底，
    抛物线插值。"""
    w = len(fr)
    mean = sum(fr) / w
    x = [v - mean for v in fr]
    tmin, tmax = int(rate / F0_RANGE[1]), min(int(rate / F0_RANGE[0]), w // 2)
    cmnd = [1.0]
    total = 0.0
    found: int | None = None
    for tau in range(1, tmax + 1):
        d = sum((x[i] - x[i + tau]) ** 2 for i in range(w - tau))
        total += d
        cmnd.append(d * tau / total if total > 0 else 1.0)
        if found is None and tau >= tmin and cmnd[tau] < YIN_THRESH:
            found = tau
        elif found is not None and cmnd[tau] >= cmnd[tau - 1]:
            break
    if found is None:
        return None
    best = found
    while best + 1 < len(cmnd) and cmnd[best + 1] < cmnd[best]:
        best += 1
    off = 0.0
    if best + 1 < len(cmnd):
        a, b, c = cmnd[best - 1], cmnd[best], cmnd[best + 1]
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if den else 0.0
    return rate / (best + off)


@dataclass(frozen=True)
class Pitch:
    pitched: float  # 有音高的窗占几成
    median_hz: float | None  # 有音高的窗的基频中位数


def pitch_of(pcm: bytes) -> Pitch:
    """比最响的窗低 20 dB 以内的窗里，YIN（阈 0.15、60〜400 Hz）找得到周期的占几成、基频中位数。三个采样取平均降到
    8 kHz 再算（纯 Python）。耳语、气声找不到周期（UX 量到メロス「ああ。」只有头 0.09 秒有音高）。"""
    a = samples(pcm)
    step = RATE // PITCH_RATE
    x = [sum(a[i : i + step]) / step for i in range(0, len(a) - step + 1, step)]
    hop, win = PITCH_RATE // 100, WIN * PITCH_RATE // 100
    frames = [x[k : k + win] for k in range(0, len(x) - win + 1, hop)]
    if not frames:
        return Pitch(0.0, None)
    db = [dbfs(math.sqrt(sum(v * v for v in f) / win)) for f in frames]
    loud = [f for f, d in zip(frames, db, strict=True) if d > max(db) - PITCH_GATE_DB]
    f0 = [f for f in (_yin(fr, PITCH_RATE) for fr in loud) if f is not None]
    return Pitch(round(len(f0) / len(loud), 2), round(statistics.median(f0), 1) if f0 else None)


def pitched(pcm: bytes) -> float:
    return pitch_of(pcm).pitched


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
