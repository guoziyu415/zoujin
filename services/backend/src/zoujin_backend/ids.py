"""Runtime IDs: prefix + ULID (api-contract section 0).

ランタイム ID：プレフィックス + ULID（api-contract 第 0 節）。
"""

from __future__ import annotations

import random
import time

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class IdGen:
    """ULID = 48-bit millisecond time + 80 random bits. With a fixed seed the random part is reproducible (for tests).

    ULID = 48 ビットのミリ秒時刻 + 80 ビットの乱数。seed を固定すると乱数部分が再現できる（テスト用）。
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def ulid(self) -> str:
        n = (int(time.time() * 1000) << 80) | self._rng.getrandbits(80)
        return "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(26)))

    def new(self, prefix: str) -> str:
        return f"{prefix}_{self.ulid()}"
