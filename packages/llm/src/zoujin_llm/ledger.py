"""The ledger (S-079 ④, dev-plan Z-8): the Google and Claude ledgers are kept in the same JSONL file; caps are checked
before a call, and the actual cost is recorded after it.

- One line: `at` (UTC, ending in Z), `provider` ("google" / "claude"), `kind` (prompt kind, "judge", "player"…), `model`
  (the model ID for Google; only the tier name plus version for Claude, e.g. "sonnet-5.5"), `usage`, `costUsd`, `use`,
  and `item` if any. The content of requests and replies is not written, nor are keys or project IDs. The earliest
  lines have no `provider` and count as Google.
- `use` is marked by which path the call belongs to, not by whether it runs in an eval: the narrator's steps, safety
  classification, memories, endings, Live and pre-recorded lines are "product" (also when run in an eval); the judge
  and the AI player are "eval". S-5's per-playthrough cost adds up only product. Old lines lack this column and are
  inferred by `use_of()`.
- The total cap counts only that provider's own lines (D-027's 50 dollars for Google, D-029's 100 dollars for Claude,
  both cumulative across all runs); the per-item cap is checked only when `item` is given: the cost of the same item
  across both ledgers plus this call (data #49).
- The file is reread on every cap check: several runs on the Mac may be recording at the same time.
- The three columns added in B-5 are all optional, and old lines without them are read as usual: `ms` (how long this
  call took, from sending to receiving everything; a timed-out call is recorded up to its cancellation, and the resend
  after a timeout is recorded as a separate line), `status` (`STATUSES`), `playthroughId` (present only for calls made
  within an eval playthrough: the eval entry point marks it with `playthrough()`; a random ID in the test database,
  not personal information). Lines with these columns are written with `record()`; `add()` is the old way. Wrap the
  call in `timed()` and the duration and status are recorded automatically.

台帳（S-079 ④、dev-plan Z-8）：Google と Claude の 2 つの台帳を同じ JSONL ファイルに記録し、呼び出し前に上限を確認し、
呼び出し後に実際の費用を記録する。

- 1 行：`at`（UTC、末尾は Z）、`provider`（"google" / "claude"）、`kind`（プロンプトの種類、"judge"、"player"…）、
  `model`（Google はモデル ID、Claude はティア名とバージョンだけ。例 "sonnet-5.5"）、`usage`、`costUsd`、`use`、あれば
  `item`。リクエストと返答の内容は書かず、キーやプロジェクト ID も書かない。最初の数行には `provider` がなく、Google の
  ものとみなす。
- `use` は呼び出しがどの経路に属するかで付け、評価の中で実行されたかどうかでは付けない：ナレーターの各ステップ、安全
  分類、記憶、エンディング、Live、事前収録セリフは "product"（評価の中で実行しても同じ）。審査員と AI プレイヤーは
  "eval"。S-5 の 1 周回あたりのコストは product だけを足す。古い行にはこの列がなく、`use_of()` で推定する。
- 総上限はそのプロバイダ自身の行だけを数える（D-027 の Google 50 ドル、D-029 の Claude 100 ドル。どちらもすべての実行に
  わたる累計）。項目ごとの上限は `item` が与えられたときだけ判定する：同じ item の 2 つの台帳を合わせた費用に今回の分を
  足す（データ #49）。
- 上限の判定のたびにファイルを読み直す：Mac 上では複数の実行が同時に記録していることがある。
- B-5 で追加した 3 列はどれも省略可能で、古い行になくてもそのまま読む：`ms`（この呼び出しの所要時間。送信から受信完了
  まで。タイムアウトしたものは取り消しまでを記録し、タイムアウト後の再送は別の行に記録する）、`status`（`STATUSES`）、
  `playthroughId`（評価の周回の中で呼び出したときだけ付く：評価の入口が `playthrough()` で付ける。テスト用データベースの
  ランダムな ID で、個人情報ではない）。これらの列付きの行は `record()` で書き、`add()` は古い書き方。呼び出しを
  `timed()` で包めば、所要時間と状態は自動で記録される。
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

from zoujin_llm.errors import BudgetStop, check_batch_halt

PROVIDERS = {"google": "Google", "claude": "Claude"}
# When an old line has no use, these kinds count as eval and the rest as product
# 古い行に use がないとき、これらの種類は評価、それ以外は製品とみなす
EVAL_KINDS = ("judge", "player")
# ok: it came back and is usable; timeout: cancelled at the time limit (recorded at the estimate); bad-output: it came
# back but stopped at refusal / max_tokens, or failed the Schema; error: no response (connection dropped, 5xx, 429),
# cost 0
# ok：返ってきて使える。timeout：時間制限で取り消された（見積もりで記録）。bad-output：返ってきたが refusal /
# max_tokens で止まった、または Schema を通らない。error：応答がない（接続切断、5xx、429）、費用 0
STATUSES = ("ok", "timeout", "bad-output", "error")

# An eval playthrough: lines recorded during it carry playthroughId (eval_api marks every step; asyncio.run and the
# tasks it creates all carry this context)
# 評価の周回：その間に記録した行には playthroughId が付く（eval_api が各ステップで付ける。asyncio.run とそれが作る
# タスクはすべてこのコンテキストを引き継ぐ）
_PLAYTHROUGH: ContextVar[str | None] = ContextVar("zoujin_ledger_playthrough", default=None)


@contextmanager
def playthrough(pid: str | None) -> Iterator[None]:
    """Ledger lines recorded during this block carry `playthroughId` (None: they do not).

    この間に記録した台帳の行には `playthroughId` が付く（None：付けない）。
    """
    token = _PLAYTHROUGH.set(pid)
    try:
        yield
    finally:
        _PLAYTHROUGH.reset(token)


def mark_playthrough(pid: str | None) -> None:
    """Mark it in the current context (when a playthrough starts, the playthroughId only exists inside the coroutine).

    現在のコンテキストに付ける（周回の開始時、playthroughId はコルーチンの中にしかない）。
    """
    _PLAYTHROUGH.set(pid)


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def use_of(line: Mapping[str, Any]) -> str:
    """Whether a ledger line belongs to product or eval: use `use` if present; old lines are inferred from `kind`.

    台帳の 1 行が製品と評価のどちらに属するか：`use` があればそれを使い、古い行は `kind` から推定する。
    """
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
    provider: str  # this ledger: "google" or "claude" / この台帳："google" または "claude"
    # This provider's total cap (the cumulative amount already in the ledger also counts)
    # このプロバイダの総上限（台帳にすでにある累計も数える）
    max_total_usd: float
    max_item_usd: float | None = None  # per-item cap: this item across both ledgers / 項目ごとの上限：2 つの台帳の合計
    # Which item lines are recorded under (an S-2 entry, an E-0 case, "b8-probe"…)
    # どの項目の下に記録するか（S-2 の項目、E-0 のケース、"b8-probe"…）
    item: str | None = None
    use: str = "product"

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            raise ValueError(
                f"Unknown ledger {self.provider!r} ({' / '.join(PROVIDERS)}) / "
                f"不明な台帳 {self.provider!r}（{' / '.join(PROVIDERS)}）"
            )
        if self.use not in ("product", "eval"):
            raise ValueError(
                f"use must be product or eval, got {self.use!r} / "
                f"use は product か eval のみ。受け取った値 {self.use!r}"
            )

    def spent_total(self) -> float:
        """This provider's cumulative cost (what the total cap is compared with).

        このプロバイダの累計（総上限と比べるのはこれ）。
        """
        lines = read_lines(self.path)
        return sum(float(x.get("costUsd", 0.0)) for x in lines if x.get("provider", "google") == self.provider)

    def spent_on(self, item: str) -> float:
        """This item's cumulative cost across both ledgers (what the per-item cap is compared with).

        この項目の 2 つの台帳を合わせた累計（項目ごとの上限と比べるのはこれ）。
        """
        return sum(float(x.get("costUsd", 0.0)) for x in read_lines(self.path) if x.get("item") == item)

    def before(self, estimate_usd: float) -> None:
        """Before a call: if the cumulative cost plus this call's estimate exceeds a cap, raise BudgetStop (this call is
        not sent).

        呼び出し前：累計 + 今回の見積もりが上限を超えたら BudgetStop を投げる（今回の呼び出しは送らない）。
        """
        check_batch_halt()
        so_far = self.spent_total()
        if so_far + estimate_usd > self.max_total_usd:
            raise BudgetStop(
                f"{PROVIDERS[self.provider]} ledger has spent ${so_far:.4f}; with this call's estimate"
                f" ${estimate_usd:.4f} it exceeds the total cap ${self.max_total_usd:.2f} / "
                f"{PROVIDERS[self.provider]} の台帳は ${so_far:.4f} 使用済みで、今回の見積もり ${estimate_usd:.4f}"
                f" を足すと総上限 ${self.max_total_usd:.2f} を超える"
            )
        if self.item is not None and self.max_item_usd is not None:
            on_item = self.spent_on(self.item)
            if on_item + estimate_usd > self.max_item_usd:
                raise BudgetStop(
                    f'"{self.item}" has spent ${on_item:.4f}; with this call\'s estimate ${estimate_usd:.4f}'
                    f" it exceeds the per-item cap ${self.max_item_usd:.2f} / "
                    f"「{self.item}」は ${on_item:.4f} 使用済みで、今回の見積もり ${estimate_usd:.4f}"
                    f" を足すと項目ごとの上限 ${self.max_item_usd:.2f} を超える"
                )

    def add(self, *, kind: str, model: str, usage: Mapping[str, int], cost: float) -> None:
        """The pre-B-5 way of writing (no duration or status), still used by the data team's judge subclass.

        B-5 より前の書き方（所要時間と状態なし）。データ担当の審査員のサブクラスがまだ使っている。
        """
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
        """Record one line. ms: from sending to receiving everything (up to cancellation for a timeout); status: one of
        `STATUSES`.

        1 行を記録する。ms：送信から受信完了まで（タイムアウトしたものは取り消しまで）。status：`STATUSES` のいずれか。
        """
        if status is not None and status not in STATUSES:
            raise ValueError(
                f"status must be one of {' / '.join(STATUSES)}, got {status!r} / "
                f"status は {' / '.join(STATUSES)} のいずれか。受け取った値 {status!r}"
            )
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
        """One call: first check the caps against the estimate (`before`), then start timing. After getting the reply,
        `bill.done(usage, cost, ok=…)` records one line (`ok` / `bad-output`); leaving without done: cancellation or
        `TimeoutError` (the time limit was reached, by an outer `wait_for` or the client's own timeout) is recorded as
        `timeout` at the estimate (it may already have been billed, so better to over-record), and any other exception
        (unreachable, 5xx, 429) is recorded as `error` with cost 0. Exceptions are re-raised as usual. When the SDK's
        own timeout exception is not a `TimeoutError`, the caller catches it and does `raise TimeoutError from e`.

        1 回の呼び出し：まず見積もりで上限を判定し（`before`）、それから計時する。返答を受け取ったら
        `bill.done(usage, cost, ok=…)` で 1 行記録する（`ok` / `bad-output`）。done せずに抜けた場合：取り消しまたは
        `TimeoutError`（時間制限に達した。外側の `wait_for` かクライアント自身のタイムアウト）は見積もりで `timeout` と
        記録し（すでに課金されているかもしれないので、多めに記録する）、それ以外の例外（接続できない、5xx、429）は
        `error`、費用 0 と記録する。例外はそのまま投げ直す。SDK 自身のタイムアウト例外が `TimeoutError` でない場合は、
        呼び出し側が捕まえて `raise TimeoutError from e` とする。

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
    """This one call inside `Ledger.timed()`.

    `Ledger.timed()` の中のこの 1 回の呼び出し。
    """

    ledger: Ledger
    kind: str
    model: str
    estimate: float
    start: float = field(default_factory=time.perf_counter)
    written: bool = False

    def done(self, usage: Mapping[str, int], cost: float, *, ok: bool = True) -> None:
        """Got a reply: ok=False means it came back but is unusable (stopped at refusal / max_tokens, or failed the
        Schema); the cost is recorded as usual.

        返答を受け取った：ok=False は返ってきたが使えない（refusal / max_tokens で止まった、または Schema を通らない）
        ことを表し、費用はそのまま記録する。
        """
        self.write(usage, cost, "ok" if ok else "bad-output")

    def write(self, usage: Mapping[str, int], cost: float, status: str) -> None:
        ms = (time.perf_counter() - self.start) * 1000
        self.ledger.record(kind=self.kind, model=self.model, usage=usage, cost=cost, ms=ms, status=status)
        self.written = True
