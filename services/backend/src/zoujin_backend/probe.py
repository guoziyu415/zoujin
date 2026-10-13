"""`zoujin-probe`: measure Claude's latency and tokens once on the Mac (B-8 item 8). Threads and CI only run the
print-only mode without `--confirm`.

Requests come from replays recorded with the fake model (`ZJ_RECORD_REPLAYS`, e.g. one fake-model run of the E-0 slice
cases), **never the holdout samples**: directories whose name contains holdout are not read. For each prompt kind that
goes to Claude, take `--per-kind` requests (identical requests count once; if there are not enough, cycle from the
start) and call the real model serially: stream to measure time to first text (the first token of the first text
block; with thinking on, it includes the thinking time) and total time, and record input, cache, output and thinking
tokens.

- Without `--confirm`: print how many calls, the estimated cost (the estimate and the cap the ledger checks against)
  and the full command; make no calls.
- With `--confirm`: the key, both tiers' model IDs, the ledger, Claude's total cap and the item cap must all be present;
  if any is missing it only prints. Records in Claude's ledger with `item` b8-probe (the item cap is checked against
  it). Stops at the first 429 or 529, and stops at the cap; other HTTP errors skip the rest of that prompt kind.
- Results are numbers only: `probe.jsonl` has one line per call (kind, tier name plus version, status, milliseconds,
  tokens, cost), `summary.json` each kind's p50, p95 and mean. Requests, answer text, model IDs and the key are never
  written.

`zoujin-probe`：Mac 上で Claude のレイテンシーとトークンを 1 回測る（B-8 第 8 項）。スレッドと CI では `--confirm`
なしの表示だけを実行する。

リクエストは偽モデルで録ったリプレイ（`ZJ_RECORD_REPLAYS`、例：E-0 のスライスのケースを偽モデルで 1 回実行したもの）から
取り、**ホールドアウトサンプルには触れない**：ディレクトリ名に holdout を含むものは読まない。Claude を使うプロンプトの
種類ごとに `--per-kind` 件を取り（同じリクエストは 1 件と数え、足りなければ先頭から繰り返す）、本物のモデルを
直列に呼ぶ：ストリーミングで最初の文字（最初のテキストブロックの最初のトークン。思考がオンのときは思考の時間を含む）
までの時間と全体の時間を測り、入力・キャッシュ・出力・思考のトークンを記録する。

- `--confirm` なし：呼び出し回数、予想費用（推算と、台帳が判定に使う上限）と完全なコマンドを表示し、呼び出さない。
- `--confirm` あり：キー、2 つのティアのモデル ID、台帳、Claude の総上限、項目の上限がすべて必要で、1 つでも欠ければ
  表示だけにする。Claude の台帳に記録し、`item` は b8-probe（項目の上限はこれで判定する）。最初の 429・529 で止まり、
  上限に達しても止まる。ほかの HTTP エラーはそのプロンプトの種類の残りをスキップする。
- 結果は数字だけ：`probe.jsonl` は呼び出しごとに 1 行（種類、ティア名とバージョン、状態、ミリ秒、トークン、費用）、
  `summary.json` は種類ごとの p50・p95・平均。リクエスト、回答の文章、モデル ID、キーは書かない。

On the Mac (the key lives only in this one terminal) / Mac 上で（キーはこの 1 つのターミナルにだけ置く）:

    export ANTHROPIC_API_KEY="$(security find-generic-password -s zoujin-claude -w)"
    ZJ_CLAUDE_HAIKU=… ZJ_CLAUDE_SONNET=… ZJ_LEDGER=~/.zoujin/ledger.jsonl \\
      uv run --all-packages --extra real zoujin-probe --requests <recorded dir> --out <results dir> \\
      --max-item-usd 2 --max-claude-usd 100
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import shlex
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from zoujin_llm import BudgetStop, ClaudePrices, ModelCallFailed, RateLimited, Reply, canonical, claude_prices, now_z

from zoujin_backend.config import REPO, TEXT, ConfigError, Settings
from zoujin_backend.models.claude import api_schema, claude_text, estimate_usd, params
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.render import world_prefix
from zoujin_backend.models.text import BadOutput, key_of, spec
from zoujin_backend.world import Library

Json = Any

ITEM = "b8-probe"
# Output tokens per call (including thinking) [estimated, from card B-8's per-playthrough cost table]: used only for
# the "estimated" figure; the ledger checks against the output limit
# 1 回の呼び出しの出力トークン（思考を含む）〔推算、B-8 カードの 1 プレイあたりコスト表〕：
# 「推算」の数字を出すためだけに使い、台帳は出力の上限で判定する
TYPICAL_OUTPUT = {
    "triage": 30,
    "extract": 300,
    "check": 1200,
    "rewrite": 400,
    "narrate": 120,
    "plan": 600,
    "safety": 15,
    # Three layers of text, no thinking (B-9's Mac probe 10-11: about 970 on average)
    # 3 層の文章、思考なし（B-9 の Mac プローブ 10-11：平均約 970）
    "ending": 1000,
    # B-17: judge one bool and a few field names, with thinking [estimated]
    # B-17：bool 1 つといくつかのフィールド名を判定、思考あり〔推算〕
    "ending-check": 600,
    "memory": 30,  # B-13: one line of about 20 characters plus weight / 20 文字ほどの一文と weight
    "keeps": 25,  # B-13: one consequence line within 30 characters, or null / 30 文字以内の結果の一文か null
    "world": 800,  # B-16: a few events, plus thinking / いくつかのイベントと思考
}
NEEDED_ENV = ("ANTHROPIC_API_KEY", "ZJ_CLAUDE_HAIKU", "ZJ_CLAUDE_SONNET", "ZJ_LEDGER")
ROWS, SUMMARY = "probe.jsonl", "summary.json"


def claude_kinds() -> list[str]:
    return [k for k in TEXT if spec(k).provider == "claude"]


# —— Requests / リクエスト ——


def load(directory: Path) -> dict[str, list[Json]]:
    """Replay-format JSONL (`<kind>.jsonl`) → deduplicated requests for each Claude prompt kind, in file order.

    リプレイ形式の JSONL（`<kind>.jsonl`）→ Claude のプロンプトの種類ごとに重複を除いたリクエスト。ファイル内の順。
    """
    if "holdout" in str(directory).lower():
        raise ConfigError(
            "Holdout samples are never read: the request directory path contains holdout / "
            "ホールドアウトサンプルは読まない：リクエストディレクトリのパスに holdout が含まれる"
        )
    if not directory.is_dir():
        raise ConfigError(f"Request directory does not exist / リクエストディレクトリが存在しない: {directory.name}")
    wanted = set(claude_kinds())
    by_kind: dict[str, dict[str, Json]] = {}
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            kind = rec.get("kind")
            if kind in wanted:
                by_kind.setdefault(kind, {}).setdefault(key_of(kind, rec["request"]), rec["request"])
    return {k: list(by_kind[k].values()) for k in claude_kinds() if k in by_kind}


def pick(requests: Mapping[str, Sequence[Json]], n: int) -> list[tuple[str, Json]]:
    """Take n per kind: if there are not enough, cycle from the start (calling the same request again still measures
    that tier's latency).

    種類ごとに n 件取る：足りなければ先頭から繰り返す（同じリクエストをもう一度呼んでも、
    測るのはそのティアのレイテンシー）。
    """
    return [(kind, reqs[i % len(reqs)]) for kind, reqs in requests.items() for i in range(n)]


# —— Estimated cost / 予想費用 ——


def estimates(prices: ClaudePrices, kind: str, request: Json, prefix: str) -> tuple[float, float]:
    """(estimate, the cap the ledger uses). Estimate: the prefix and instructions hit the cache, output per
    TYPICAL_OUTPUT; cap: no cache, output at the limit.

    （推算、台帳が使う上限）。推算：プレフィックスと説明はキャッシュを使い、出力は TYPICAL_OUTPUT。上限：キャッシュを
    数えず、出力は上限で計算。
    """
    p = params(kind, request, prefix, "-")
    upper = estimate_usd(prices, kind, p)
    tag = spec(kind).model
    price = prices.price(tag)

    def tokens(chars: int) -> int:
        return int(chars / prices.chars_per_token * price.tokenizer) + 1

    cached = tokens(sum(len(b["text"]) for b in p["system"]))
    fresh = tokens(len(p["messages"][0]["content"]) + len(canonical(api_schema(kind))))
    likely = prices.cost(tag, {"cacheReadTokens": cached, "inputTokens": fresh, "outputTokens": TYPICAL_OUTPUT[kind]})
    return likely, upper


# —— Streaming calls / ストリーミング呼び出し ——


class Timed:
    """Swaps the narrator's transport for streaming: measures time to first text and total time; the answer still goes
    to `ClaudeText` for the ledger and Schema validation.

    ナレーターのトランスポートをストリーミングに替える：最初の文字までの時間と全体の時間を測り、回答はこれまでどおり
    `ClaudeText` に渡して台帳への記録と Schema の検証を行う。
    """

    def __init__(self, sdk: Any | None = None) -> None:
        from zoujin_llm.claude import async_client, quiet

        quiet()
        self._sdk = sdk if sdk is not None else async_client()
        self.last: dict[str, float | None] = {}

    async def create(self, p: Json) -> Reply:
        import anthropic
        from zoujin_llm.claude import thinking_tokens, translate

        started = time.perf_counter()
        first: float | None = None
        index: int | None = None
        parts: list[str] = []
        usage: dict[str, int] = {}
        stop: str | None = None
        try:
            stream = await self._sdk.messages.create(**p, stream=True)
            async for ev in stream:
                if ev.type == "message_start":
                    u = ev.message.usage
                    usage["inputTokens"] = int(u.input_tokens)
                    usage["cacheReadTokens"] = int(u.cache_read_input_tokens or 0)
                    usage["cacheWriteTokens"] = int(u.cache_creation_input_tokens or 0)
                elif ev.type == "content_block_start" and index is None and ev.content_block.type == "text":
                    index = ev.index
                elif ev.type == "content_block_delta" and ev.index == index and ev.delta.type == "text_delta":
                    if first is None:
                        first = time.perf_counter() - started
                    parts.append(ev.delta.text)
                elif ev.type == "message_delta":
                    stop = ev.delta.stop_reason
                    usage["outputTokens"] = int(ev.usage.output_tokens)
                    usage["thinkingTokens"] = thinking_tokens(ev.usage)
        except anthropic.APIError as e:
            raise translate(e) from None
        total = time.perf_counter() - started
        self.last = {"firstTextMs": None if first is None else round(first * 1000), "totalMs": round(total * 1000)}
        return Reply("".join(parts) if index is not None else None, stop, usage)


# —— Statistics / 統計 ——


def nearest_rank(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def summarize(rows: Sequence[Json]) -> dict[str, Json]:
    out: dict[str, Json] = {}
    for kind in dict.fromkeys(r["kind"] for r in rows):
        mine = [r for r in rows if r["kind"] == kind]
        ok = [r for r in mine if r["status"] == "ok"]
        s: dict[str, Json] = {
            "model": mine[0]["model"],
            "calls": len(mine),
            "statuses": {st: [r["status"] for r in mine].count(st) for st in dict.fromkeys(r["status"] for r in mine)},
            "costUsd": round(sum(r["costUsd"] for r in mine), 6),
        }
        for name in ("firstTextMs", "totalMs"):
            values = [float(r[name]) for r in ok if r.get(name) is not None]
            s[name] = {
                "p50": nearest_rank(values, 0.5),
                "p95": nearest_rank(values, 0.95),
                "max": max(values, default=None),
            }
        for name in ("inputTokens", "cacheReadTokens", "cacheWriteTokens", "outputTokens", "thinkingTokens"):
            values = [float(r["usage"].get(name, 0)) for r in mine if r["usage"]]
            s[name] = round(sum(values) / len(values)) if values else None
        out[kind] = s
    return out


# —— Run / 実行 ——


def gate(
    args: argparse.Namespace, argv: Sequence[str], picked: Sequence[tuple[str, Json]], env: Mapping[str, str]
) -> bool:
    """Print how many calls, the estimated cost and the full command; return True only if everything is present and
    --confirm was given.

    呼び出し回数、予想費用、完全なコマンドを表示する。すべて揃っていて --confirm があるときだけ True を返す。
    """
    prices = claude_prices()
    library = Library(REPO / "worlds", REPO / "assets" / "scenes", Settings(database_url="").world)
    sums: dict[str, list[float]] = {}  # kind → [count, estimate, cap] / 種類 → [回数, 推算, 上限]
    biggest = 0.0
    for kind, request in picked:
        version = request.get("worldModelVersion")
        prefix = world_prefix(library.version(version).world) if version else ""
        likely, upper = estimates(prices, kind, request, prefix)
        acc = sums.setdefault(kind, [0.0, 0.0, 0.0])
        acc[0] += 1
        acc[1] += likely
        acc[2] += upper
        biggest = max(biggest, upper)
    print(
        f"Probe: {len(picked)} calls, serial, recorded in Claude's ledger, item = {ITEM} / "
        f"小テスト：{len(picked)} 回の呼び出し、直列、Claude の台帳に記録、item = {ITEM}"
    )
    for kind, (n, likely, upper) in sums.items():
        print(
            f"  {kind:8} {spec(kind).model:11} {int(n):3} calls / 回  estimate / 推算 ${likely:.3f}"
            f"  cap / 上限 ${upper:.3f}"
        )
    likely_total, upper_total = (sum(v[i] for v in sums.values()) for i in (1, 2))
    print(
        f"Estimated cost: about ${likely_total:.2f} by estimate (prefix and instructions cached) / "
        f"予想費用：推算で約 ${likely_total:.2f}（プレフィックスと説明はキャッシュを使う）"
    )
    print(
        f"At the cap for every call: ${upper_total:.2f} (no cache, output at the limit) / "
        f"毎回上限で計算すると ${upper_total:.2f}（キャッシュなし、出力は上限で計算）"
    )
    print(
        f"The item cap is compared with this item's actual spend so far plus the next call's cap (at most "
        f"${biggest:.3f}): by the estimate give it ${likely_total + biggest:.2f}; if that is not enough the run stops "
        "midway and results already finished are still written / "
        f"項目の上限は、この項目のこれまでの実際の支出に次の 1 回の上限（最大 ${biggest:.3f}）を足したものと比べる："
        f"推算では ${likely_total + biggest:.2f} にしておく必要があり、足りなければ途中で止まり、"
        "終わった分の結果はそのまま書く"
    )
    names = " ".join(f"{k}=…" for k in NEEDED_ENV) + (" ZJ_TEXT_MODELS=…" if env.get("ZJ_TEXT_MODELS") else "")
    rest = shlex.join(x for x in argv if x != "--confirm")
    print(f"Command / コマンド: {names} uv run --all-packages --extra real zoujin-probe {rest} --confirm")
    missing = [f"{k} not set / {k} が未設定" for k in NEEDED_ENV if not env.get(k)]
    if args.max_claude_usd is None:
        missing.append("missing --max-claude-usd / --max-claude-usd がない")
    if args.max_item_usd is None:
        missing.append("missing --max-item-usd / --max-item-usd がない")
    if not args.confirm:
        missing.append("no --confirm / --confirm がない")
    if missing:
        print("Printing only, no calls / 表示のみで呼び出さない: " + "; ".join(missing))
        return False
    return True


async def run(args: argparse.Namespace, picked: Sequence[tuple[str, Json]], env: Mapping[str, str]) -> int:
    ledger = Path(env["ZJ_LEDGER"])
    if not ledger.is_absolute():
        raise ConfigError("ZJ_LEDGER must be an absolute path / ZJ_LEDGER には絶対パスを書く")
    settings = Settings(
        database_url="",
        model="real",
        ledger=ledger,
        max_claude_usd=args.max_claude_usd,
        ledger_item=ITEM,
        max_item_usd=args.max_item_usd,
    )
    timed = Timed()
    rt = claude_text(settings, transport=timed, env=env)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    rows: list[Json] = []
    skipped: set[str] = set()
    stopped: str | None = None
    meta = {
        "startedAt": now_z(),
        "item": ITEM,
        "requests": args.requests.name,
        "requestsSha256": hashlib.sha256(canonical([key_of(k, r) for k, r in picked]).encode()).hexdigest(),
        "perKind": args.per_kind,
        "promptVersions": {k: PROMPTS[k].version for k in dict.fromkeys(k for k, _ in picked)},
    }
    with (out / ROWS).open("w", encoding="utf-8") as f:
        for n, (kind, request) in enumerate(picked, 1):
            if kind in skipped:
                continue
            row: Json = {"n": n, "kind": kind, "model": spec(kind).model, "at": now_z()}
            try:
                got = await rt.call(kind, request)
                row |= {"status": "ok", "usage": got.usage, "costUsd": round(got.cost_usd, 8), **timed.last}
            except BadOutput as e:
                row |= {"status": "invalid", "usage": {}, "costUsd": round(e.cost_usd, 8), **timed.last}
            except (RateLimited, BudgetStop) as e:
                stopped = type(e).__name__
                print(f"Stopped / 停止: {e}")
                break
            except ModelCallFailed as e:  # No answer, nothing recorded / 回答が得られず、台帳にも記録していない
                row |= {"status": "error", "usage": {}, "costUsd": 0.0}
                skipped.add(kind)
                print(f"{kind}: {e}; skipping the rest of this kind / この種類の残りはスキップする")
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            rows.append(row)
            print(f"{n}/{len(picked)} {kind} {row['status']} {row.get('totalMs', '-')} ms", flush=True)
    meta |= {"finishedAt": now_z(), "calls": len(rows), "stoppedBy": stopped}
    summary = {"meta": meta, "kinds": summarize(rows), "costUsd": round(sum(r["costUsd"] for r in rows), 6)}
    (out / SUMMARY).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for kind, s in summary["kinds"].items():
        print(
            f"{kind:8} {s['model']:11} first text / 最初の文字 p50 {s['firstTextMs']['p50']}"
            f" p95 {s['firstTextMs']['p95']}  total / 全体 p50 {s['totalMs']['p50']} p95 {s['totalMs']['p95']} ms"
            f"  {s['statuses']}"
        )
    print(f"Total spent / 合計費用 ${summary['costUsd']:.4f}; results / 結果: {out / ROWS}, {out / SUMMARY}")
    return 3 if stopped else 0


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="zoujin-probe",
        description="Measure Claude's latency and tokens on the Mac (B-8) / "
        "Mac 上で Claude のレイテンシーとトークンを測る（B-8）",
    )
    ap.add_argument(
        "--requests",
        type=Path,
        required=True,
        help="Replay directory recorded with the fake model (not holdout samples) / "
        "偽モデルで録ったリプレイのディレクトリ（ホールドアウトサンプルではない）",
    )
    ap.add_argument(
        "--out", type=Path, required=True, help="Results directory (numbers only) / 結果のディレクトリ（数字だけ）"
    )
    ap.add_argument(
        "--per-kind",
        type=int,
        default=20,
        help="How many calls per prompt kind (default 20) / プロンプトの種類ごとの呼び出し回数（デフォルト 20）",
    )
    ap.add_argument(
        "--kind",
        action="append",
        choices=claude_kinds(),
        help="Measure only these kinds (repeatable; default is every kind that goes to Claude) / "
        "この種類だけを測る（複数回指定可。指定しなければ Claude を使うすべての種類）",
    )
    ap.add_argument(
        "--max-item-usd",
        type=float,
        help=f"Cap for this probe (item {ITEM}); required for real calls / "
        f"今回の小テスト（item {ITEM}）の上限。本当に呼ぶときは必須",
    )
    ap.add_argument(
        "--max-claude-usd",
        type=float,
        help="Total cap of Claude's ledger (accumulated across all runs, D-029); required for real calls / "
        "Claude の台帳の総上限（すべての実行で累計、D-029）。本当に呼ぶときは必須",
    )
    ap.add_argument(
        "--confirm",
        action="store_true",
        help="zg has seen the estimated cost and agreed / zg が予想費用を確認して同意した",
    )
    argv = list(sys.argv[1:] if argv is None else argv)
    args = ap.parse_args(argv)
    e = os.environ if env is None else env
    try:
        requests = load(args.requests)
        if args.kind:
            requests = {k: v for k, v in requests.items() if k in args.kind}
        if not requests:
            raise ConfigError(
                f"No requests for prompt kinds that go to Claude in {args.requests.name} / "
                f"{args.requests.name} に Claude を使うプロンプトのリクエストがない"
            )
        picked = pick(requests, args.per_kind)
        if not gate(args, argv, picked, e):
            return 0
        return asyncio.run(run(args, picked, e))
    except ConfigError as err:
        print(f"Bad configuration / 設定が正しくない: {err}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
