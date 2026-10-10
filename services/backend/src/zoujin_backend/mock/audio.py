"""合成的人物音频（api-contract 3.1 的下行帧）：不放任何真人或模型录的声音。"""

from __future__ import annotations

import math
import sys
from array import array
from collections.abc import Iterator

RATE = 24_000  # 下行 24 kHz、PCM16 小端、单声道
FRAME_CHARACTER = 0x02


def frame(turn_seq: int, pcm: bytes) -> bytes:
    """字节 0 类型，1–4 turnSeq（uint32 大端），5– PCM。"""
    return bytes([FRAME_CHARACTER]) + turn_seq.to_bytes(4, "big") + pcm


def chunks(seconds: float, chunk_ms: int) -> Iterator[bytes]:
    """像说话一样一阵一阵的低音量哼声（每秒约 4 个音节），按 chunk_ms 切片。"""
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
