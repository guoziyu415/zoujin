"""Synthetic character audio (api-contract 3.1 downstream frames): contains no recorded human or model voice.

合成した人物の音声（api-contract 3.1 の下りフレーム）：実在の人やモデルが録音した声は一切含まない。
"""

from __future__ import annotations

import math
import sys
from array import array
from collections.abc import Iterator

RATE = 24_000  # Downstream: 24 kHz, PCM16 little-endian, mono / 下り：24 kHz、PCM16 リトルエンディアン、モノラル
FRAME_CHARACTER = 0x02


def frame(turn_seq: int, pcm: bytes) -> bytes:
    """Byte 0 is the type, 1–4 the turnSeq (uint32 big-endian), 5– the PCM.

    バイト 0 が種別、1–4 が turnSeq（uint32 ビッグエンディアン）、5– が PCM。
    """
    return bytes([FRAME_CHARACTER]) + turn_seq.to_bytes(4, "big") + pcm


def chunks(seconds: float, chunk_ms: int) -> Iterator[bytes]:
    """A low-volume hum in bursts like speech (about 4 syllables a second), cut into chunk_ms pieces.

    話し声のように断続する小さなハミング（毎秒約 4 音節）を chunk_ms ごとに切り分ける。
    """
    total = max(1, round(seconds * RATE))
    per = max(1, RATE * chunk_ms // 1000)
    for start in range(0, total, per):
        samples = array("h")
        for i in range(start, min(start + per, total)):
            t = i / RATE
            syllable = max(0.0, math.sin(math.pi * 4 * t)) ** 2
            fade = min(1.0, i / 480, (total - i) / 480)
            pitch = 190 + 25 * math.sin(math.pi * 0.7 * t)
            samples.append(int(2600 * syllable * fade * math.sin(2 * math.pi * pitch * t)))
        if sys.byteorder == "big":
            samples.byteswap()
        yield samples.tobytes()
