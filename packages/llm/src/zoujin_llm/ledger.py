"""账本（S-079 ④、dev-plan Z-8）：Google 和 Claude 两本账记在同一个 JSONL 文件里，调用前查上限、调用后记实际花费。

- 一行：`at`（UTC，Z 结尾）、`provider`（"google" / "claude"）、`kind`（提示类型、"judge"、"player"…）、`model`
  （Google 写模型 ID，Claude 只写档名加版本，如 "sonnet-5.5"）、`usage`、`costUsd`、`use`，有的话 `item`。
  不写请求和回答的内容，也不写 Key、项目 ID。最早的几行没有 `provider`，算 Google 的。
- `use` 按调用属于哪条路径标，不按是不是在评测里跑：叙事者各步、安全分类、记忆、结局、Live、预录句是 "product"
  （在评测里跑也是）；评审员、AI 玩家是 "eval"。S-5 的单局成本只加 product。老行没有这一列，按 `use_of()` 推。
- 总上限只算自己那家的行（D-027 的 Google 50 美元、D-029 的 Claude 100 美元，都是跨所有跑次的累计）；单项上限只在
  给了 `item` 时判：同一个 item 两本账合起来的花费加这一次（数据 #49）。
- 每次判上限都重读文件：Mac 上可能有几个跑同时在记。
- B-5 加的三列，都是可选的，老行没有也照读：`ms`（这一次调用的耗时，发出到收完；超时的记到取消为止，超时重发另记
  一行）、`status`（`STATUSES`）、`playthroughId`（在评测的一局里调用时才有：评测入口用 `playthrough()` 标上；测试库
  里的随机 ID，不是个人信息）。带这几列用 `record()` 写，`add()` 是老写法。调用包在 `timed()` 里，耗时和状态自动记。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zoujin_llm.errors import BudgetStop

PROVIDERS = {"google": "Google", "claude": "Claude"}
EVAL_KINDS = ("judge", "player")  # 老行没有 use 时，这几种算评测，其余算产品
# ok：回来了、能用；timeout：时限到了被取消（按预计记）；bad-output：回来了但停在 refusal / max_tokens，或不过 Schema；
# error：没有回应（连接断了、5xx、429），花费 0
STATUSES = ("ok", "timeout", "bad-output", "error")

# 评测的一局：这期间记的行带 playthroughId（eval_api 每一步标上；asyncio.run 和它建的任务都带着这个上下文）
_PLAYTHROUGH: ContextVar[str | None] = ContextVar("zoujin_ledger_playthrough", default=None)


@contextmanager
def playthrough(pid: str | None) -> Iterator[None]:
    """这段时间里记的账带 `playthroughId`（None：不带）。"""
    token = _PLAYTHROUGH.set(pid)
    try:
        yield
    finally:
        _PLAYTHROUGH.reset(token)


def mark_playthrough(pid: str | None) -> None:
    """在当前上下文里标上（开局时 playthroughId 在协程里才有）。"""
    _PLAYTHROUGH.set(pid)


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def use_of(line: Mapping[str, Any]) -> str:
    """一行账属于产品还是评测：有 `use` 就用它，老行按 `kind` 推。"""
    use = line.get("use")
    if isinstance(use, str):
        return use
    return "eval" if line.get("kind") in EVAL_KINDS else "product"


def read_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


@dataclass
class Ledger:
    path: Path
    provider: str  # 这一本账："google" 或 "claude"
    max_total_usd: float  # 这一家的总上限（账本里已有的累计也算）
    max_item_usd: float | None = None  # 单项上限：这一项两本账合起来
    item: str | None = None  # 记在哪一项下（S-2 的条目、E-0 的用例、"b8-probe"…）
    use: str = "product"

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            raise ValueError(f"不认识的账本 {self.provider!r}（{' / '.join(PROVIDERS)}）")
        if self.use not in ("product", "eval"):
            raise ValueError(f"use 只能是 product 或 eval，得到 {self.use!r}")

    def spent_total(self) -> float:
        """这一家的累计（总上限比的是它）。"""
        lines = read_lines(self.path)
        return sum(float(x.get("costUsd", 0.0)) for x in lines if x.get("provider", "google") == self.provider)

    def spent_on(self, item: str) -> float:
        """这一项两本账合起来的累计（单项上限比的是它）。"""
        return sum(float(x.get("costUsd", 0.0)) for x in read_lines(self.path) if x.get("item") == item)

    def before(self, estimate_usd: float) -> None:
        """调用前：累计 + 这一次的预计超过上限就抛 BudgetStop（不发这次调用）。"""
        so_far = self.spent_total()
        if so_far + estimate_usd > self.max_total_usd:
            raise BudgetStop(
                f"{PROVIDERS[self.provider]} 账本已花 ${so_far:.4f}，加上这次预计 ${estimate_usd:.4f}"
                f" 超过总上限 ${self.max_total_usd:.2f}"
            )
        if self.item is not None and self.max_item_usd is not None:
            on_item = self.spent_on(self.item)
            if on_item + estimate_usd > self.max_item_usd:
                raise BudgetStop(
                    f"「{self.item}」已花 ${on_item:.4f}，加上这次预计 ${estimate_usd:.4f}"
                    f" 超过单项上限 ${self.max_item_usd:.2f}"
                )

    def add(self, *, kind: str, model: str, usage: Mapping[str, int], cost: float) -> None:
        """B-5 以前的写法（不带耗时和状态），数据的评审员的子类还在用。"""
        self.record(kind=kind, model=model, usage=usage, cost=cost)

    def record(
        self,
        *,
        kind: str,
        model: str,
        usage: Mapping[str, int],
        cost: float,
        ms: float | None = None,
        status: str | None = None,
    ) -> None:
        """记一行。ms：发出到收完（超时的到取消为止）；status：`STATUSES` 之一。"""
        if status is not None and status not in STATUSES:
            raise ValueError(f"status 只能是 {' / '.join(STATUSES)}，得到 {status!r}")
        line: dict[str, object] = {
            "at": now_z(),
            "provider": self.provider,
            "kind": kind,
            "model": model,
            "usage": dict(usage),
            "costUsd": round(cost, 8),
            "use": self.use,
        }
        if self.item is not None:
            line["item"] = self.item
        if ms is not None:
            line["ms"] = max(0, round(ms))
        if status is not None:
            line["status"] = status
        pid = _PLAYTHROUGH.get()
        if pid:
            line["playthroughId"] = pid
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")

    @contextmanager
    def timed(self, *, kind: str, model: str, estimate: float) -> Iterator[Bill]:
        """一次调用：先按预计判上限（`before`），再计时。拿到回答以后 `bill.done(usage, cost, ok=…)` 记一行
        （`ok` / `bad-output`）；没 done 就出来的：被取消或 `TimeoutError`（时限到了，外面的 `wait_for` 或客户端自己的
        超时）按预计记 `timeout`（可能已经计费，宁多记），别的异常（连不上、5xx、429）记 `error`、花费 0。异常照旧抛出。
        SDK 自己的超时异常不是 `TimeoutError` 的，调用方接住以后 `raise TimeoutError from e`。

            with ledger.timed(kind="judge", model=tag, estimate=guess) as bill:
                reply = client.messages.create(...)
                bill.done(reply.usage, cost, ok=reply.stop_reason != "refusal")
        """
        self.before(estimate)
        bill = Bill(self, kind, model, estimate)
        try:
            yield bill
        except (asyncio.CancelledError, TimeoutError):
            if not bill.written:
                bill.write({}, estimate, "timeout")
            raise
        except Exception:
            if not bill.written:
                bill.write({}, 0.0, "error")
            raise


@dataclass
class Bill:
    """`Ledger.timed()` 里的这一次调用。"""

    ledger: Ledger
    kind: str
    model: str
    estimate: float
    start: float = field(default_factory=time.perf_counter)
    written: bool = False

    def done(self, usage: Mapping[str, int], cost: float, *, ok: bool = True) -> None:
        """拿到了回答：ok=False 是回来了但不能用（停在 refusal / max_tokens，或不过 Schema），钱照记。"""
        self.write(usage, cost, "ok" if ok else "bad-output")

    def write(self, usage: Mapping[str, int], cost: float, status: str) -> None:
        ms = (time.perf_counter() - self.start) * 1000
        self.ledger.record(kind=self.kind, model=self.model, usage=usage, cost=cost, ms=ms, status=status)
        self.written = True
