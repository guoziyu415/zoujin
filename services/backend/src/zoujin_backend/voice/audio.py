"""照读出来的 PCM（16 位、24 kHz、单声道，Live 的下行格式）：分析、裁静音、限峰值、编码成 AAC。

- 有声的范围按 10 毫秒一帧的 RMS 判：高于 `SILENCE_DBFS` 算有声。
- 截断：原始那一遍最后 0.1 秒还有声音（没落到静音）。
- 裁头尾：先查截断再裁，有声范围前后各留 80 毫秒。
- 音量不归一化（和对话时的 Live 接得上，ux-design 16.2 第 3 样），只把超过 −1 dBFS 的峰值压到 −1 dBFS。
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
PEAK_DBFS = -1.0


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

    @property
    def speech(self) -> float:
        """有声范围的长度（中间的停顿也算）。长度检查都用它，不用整段（头尾的静音每遍不一样）。"""
        return max(0.0, self.voiced_end - self.voiced_start)


def shape(pcm: bytes) -> Shape:
    a = samples(pcm)
    n = len(a)
    voiced = [dbfs(_rms(a, i, min(n, i + FRAME))) > SILENCE_DBFS for i in range(0, n, FRAME)]
    first = next((i for i, v in enumerate(voiced) if v), None)
    last = next((i for i in range(len(voiced) - 1, -1, -1) if voiced[i]), None)
    tail = max(0, n - int(RATE * TAIL_S))
    peak = max((abs(x) for x in a), default=0)
    return Shape(
        seconds=n / RATE,
        voiced_start=(first * FRAME / RATE) if first is not None else n / RATE,
        voiced_end=min(n, (last + 1) * FRAME) / RATE if last is not None else n / RATE,
        tail_voiced=n > 0 and dbfs(_rms(a, tail, n)) > SILENCE_DBFS,
        peak_dbfs=dbfs(peak),
    )


def trim(pcm: bytes, s: Shape) -> bytes:
    """有声范围前后各留 80 毫秒。"""
    start = max(0, int((s.voiced_start - PAD_S) * RATE))
    end = min(len(pcm) // 2, int(math.ceil((s.voiced_end + PAD_S) * RATE)))
    return pcm[start * 2 : end * 2]


def limit_peak(pcm: bytes) -> bytes:
    """峰值超过 −1 dBFS 才整体压下来；没超过的原样（不归一化）。"""
    a = samples(pcm)
    peak = max((abs(x) for x in a), default=0)
    ceiling = 32768 * 10 ** (PEAK_DBFS / 20)
    if peak <= ceiling:
        return pcm
    gain = ceiling / peak
    return to_bytes(array("h", (int(x * gain) for x in a)))


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


@dataclass(frozen=True)
class Encoded:
    data: bytes
    duration_ms: int


class Encoder(Protocol):
    suffix: str

    def encode(self, pcm: bytes) -> Encoded: ...


class FfmpegEncoder:
    """AAC-LC、单声道、24 kHz、48 kbps 的 m4a。去掉元数据、按位可复现（文件名里的 hash 才稳定）。"""

    suffix = ".m4a"

    def __init__(self) -> None:
        for tool in ("ffmpeg", "ffprobe"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"没有 {tool}（Mac 上：brew install ffmpeg）")

    def encode(self, pcm: bytes) -> Encoded:
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "in.wav", Path(d) / "out.m4a"
            src.write_bytes(wav(pcm))
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
                    "-c:a", "aac", "-profile:a", "aac_low", "-ac", "1", "-ar", str(RATE), "-b:a", "48k",
                    "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
                    "-movflags", "+faststart", str(dst),
                ],
                check=True,
            )  # fmt: skip
            return Encoded(dst.read_bytes(), probe_ms(dst))


def probe_ms(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return max(1, round(float(out) * 1000))


class FakeEncoder:
    """CI 用：不调 ffmpeg，「编码」结果就是 WAV，长度按 PCM 算。"""

    suffix = ".wav"

    def encode(self, pcm: bytes) -> Encoded:
        return Encoded(wav(pcm), max(1, round(len(pcm) / 2 / RATE * 1000)))
