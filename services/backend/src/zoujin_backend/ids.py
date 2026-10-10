"""运行时 ID：前缀 + ULID（api-contract 第 0 节）。"""

from __future__ import annotations

import random
import time

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class IdGen:
    """ULID = 48 位毫秒时间 + 80 位随机。seed 固定时随机部分可复现（测试用）。"""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def ulid(self) -> str:
        n = (int(time.time() * 1000) << 80) | self._rng.getrandbits(80)
        return "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(26)))

    def new(self, prefix: str) -> str:
        return f"{prefix}_{self.ulid()}"
