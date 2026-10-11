"""`zoujin-probe`：Mac 上量一次 Claude 的延迟和 token（B-8 第 8 条）。线程和 CI 只跑不带 `--confirm` 的打印。

请求从假模型录下的回放里取（`ZJ_RECORD_REPLAYS`，例：E-0 切片用例跑一遍假模型），**不碰留出样本**：目录名里有
holdout 的不读。每种走 Claude 的提示取 `--per-kind` 个（同样的请求只算一个，不够就从头轮着用），串行调真模型：
流式量首字（第一段文字的第一个 token，开着思考时含思考的时间）和全部的时间，记输入、缓存、输出、思考的 token。

- 不带 `--confirm`：打印要调几次、预计花费（推算的和账本按的上限）和完整的命令，不调。
- 带 `--confirm`：要 Key、两档的模型 ID、账本、Claude 的总上限、单项上限都齐，少一样就只打印。记 Claude 那本账，
  `item` 是 b8-probe（单项上限按它判）。第一个 429、529 就停，到上限就停；别的 HTTP 错误跳过这种提示剩下的。
- 结果只有数字：`probe.jsonl` 每次调用一行（种类、档名加版本、状态、毫秒、token、花费），`summary.json` 每种的
  p50、p95 和平均。请求、回答的文字、模型 ID 和 Key 都不写。

Mac 上（Key 只在这一个终端里）：

    export ANTHROPIC_API_KEY="$(security find-generic-password -s zoujin-claude -w)"
    ZJ_CLAUDE_HAIKU=… ZJ_CLAUDE_SONNET=… ZJ_LEDGER=~/.zoujin/ledger.jsonl \\
      uv run --all-packages --extra real zoujin-probe --requests <录下的目录> --out <结果目录> \\
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
# 每次调用输出的 token（含思考）〔推算，B-8 卡单局成本表〕：只用来算「推算的」那个数，账本按输出上限判
TYPICAL_OUTPUT = {
    "triage": 30,
    "extract": 300,
    "check": 1200,
    "rewrite": 400,
    "narrate": 120,
    "plan": 600,
    "ending": 1000,  # 三层的文字，不思考（B-9 的 Mac 探针 10-11：平均约 970）
}
NEEDED_ENV = ("ANTHROPIC_API_KEY", "ZJ_CLAUDE_HAIKU", "ZJ_CLAUDE_SONNET", "ZJ_LEDGER")
ROWS, SUMMARY = "probe.jsonl", "summary.json"


def claude_kinds() -> list[str]:
    return [k for k in TEXT if spec(k).provider == "claude"]


# —— 请求 ——


def load(directory: Path) -> dict[str, list[Json]]:
    """回放格式的 JSONL（`<kind>.jsonl`）→ 每种 Claude 的提示去重后的请求，按文件里的顺序。"""
    if "holdout" in str(directory).lower():
        raise ConfigError("不读留出样本：请求目录的路径里有 holdout")
    if not directory.is_dir():
        raise ConfigError(f"请求目录不存在：{directory.name}")
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
    """每种取 n 个：不够就从头轮着用（同一个请求再调一次，量的还是那一档的延迟）。"""
    return [(kind, reqs[i % len(reqs)]) for kind, reqs in requests.items() for i in range(n)]


# —— 预计花费 ——


def estimates(prices: ClaudePrices, kind: str, request: Json, prefix: str) -> tuple[float, float]:
    """（推算的，账本按的上限）。推算：前缀和说明走缓存，输出按 TYPICAL_OUTPUT；上限：不算缓存、输出按上限。"""
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


# —— 流式调用 ——


class Timed:
    """叙事者的传输层换成流式：量首字和全部的时间，回答照样交给 `ClaudeText` 记账、验 Schema。"""

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


# —— 统计 ——


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


# —— 跑 ——


def gate(
    args: argparse.Namespace, argv: Sequence[str], picked: Sequence[tuple[str, Json]], env: Mapping[str, str]
) -> bool:
    """打印要调几次、预计花费和完整的命令；什么都齐了而且带了 --confirm 才返回 True。"""
    prices = claude_prices()
    library = Library(REPO / "worlds", REPO / "assets" / "scenes", Settings(database_url="").world)
    sums: dict[str, list[float]] = {}  # 种类 → [次数, 推算, 上限]
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
    print(f"小测：{len(picked)} 次调用，串行，记 Claude 那本账，item = {ITEM}")
    for kind, (n, likely, upper) in sums.items():
        print(f"  {kind:8} {spec(kind).model:11} {int(n):3} 次  推算 ${likely:.3f}  上限 ${upper:.3f}")
    likely_total, upper_total = (sum(v[i] for v in sums.values()) for i in (1, 2))
    print(f"预计花费：推算约 ${likely_total:.2f}（前缀和说明走缓存）")
    print(f"每次都按上限算是 ${upper_total:.2f}（不算缓存、输出按上限）")
    print(
        f"单项上限比的是这一项已花的实数加下一次的上限（最多 ${biggest:.3f}）："
        f"按推算要给到 ${likely_total + biggest:.2f}，不够就中途停下，已经跑完的照样写结果"
    )
    names = " ".join(f"{k}=…" for k in NEEDED_ENV) + (" ZJ_TEXT_MODELS=…" if env.get("ZJ_TEXT_MODELS") else "")
    rest = shlex.join(x for x in argv if x != "--confirm")
    print(f"命令：{names} uv run --all-packages --extra real zoujin-probe {rest} --confirm")
    missing = [f"没设 {k}" for k in NEEDED_ENV if not env.get(k)]
    if args.max_claude_usd is None:
        missing.append("少 --max-claude-usd")
    if args.max_item_usd is None:
        missing.append("少 --max-item-usd")
    if not args.confirm:
        missing.append("没带 --confirm")
    if missing:
        print("只打印，不调用：" + "；".join(missing))
        return False
    return True


async def run(args: argparse.Namespace, picked: Sequence[tuple[str, Json]], env: Mapping[str, str]) -> int:
    ledger = Path(env["ZJ_LEDGER"])
    if not ledger.is_absolute():
        raise ConfigError("ZJ_LEDGER 要写绝对路径")
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
                print(f"停下：{e}")
                break
            except ModelCallFailed as e:  # 没拿到回答，没记账
                row |= {"status": "error", "usage": {}, "costUsd": 0.0}
                skipped.add(kind)
                print(f"{kind}：{e}，这种剩下的跳过")
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            rows.append(row)
            print(f"{n}/{len(picked)} {kind} {row['status']} {row.get('totalMs', '-')} ms", flush=True)
    meta |= {"finishedAt": now_z(), "calls": len(rows), "stoppedBy": stopped}
    summary = {"meta": meta, "kinds": summarize(rows), "costUsd": round(sum(r["costUsd"] for r in rows), 6)}
    (out / SUMMARY).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for kind, s in summary["kinds"].items():
        print(
            f"{kind:8} {s['model']:11} 首字 p50 {s['firstTextMs']['p50']} p95 {s['firstTextMs']['p95']}"
            f"  全部 p50 {s['totalMs']['p50']} p95 {s['totalMs']['p95']} ms  {s['statuses']}"
        )
    print(f"共花 ${summary['costUsd']:.4f}；结果：{out / ROWS}、{out / SUMMARY}")
    return 3 if stopped else 0


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zoujin-probe", description="Mac 上量 Claude 的延迟和 token（B-8）")
    ap.add_argument("--requests", type=Path, required=True, help="假模型录下的回放目录（不是留出样本）")
    ap.add_argument("--out", type=Path, required=True, help="结果目录（只有数字）")
    ap.add_argument("--per-kind", type=int, default=20, help="每种提示调几次（默认 20）")
    ap.add_argument(
        "--kind", action="append", choices=claude_kinds(), help="只量这几种（可以写几次；不写是全部走 Claude 的）"
    )
    ap.add_argument("--max-item-usd", type=float, help=f"这次小测（item {ITEM}）的上限，真调时必填")
    ap.add_argument("--max-claude-usd", type=float, help="Claude 那本账的总上限（跨所有跑次累计，D-029），真调时必填")
    ap.add_argument("--confirm", action="store_true", help="zg 看过预计花费、同意了")
    argv = list(sys.argv[1:] if argv is None else argv)
    args = ap.parse_args(argv)
    e = os.environ if env is None else env
    try:
        requests = load(args.requests)
        if args.kind:
            requests = {k: v for k, v in requests.items() if k in args.kind}
        if not requests:
            raise ConfigError(f"{args.requests.name} 里没有走 Claude 的提示的请求")
        picked = pick(requests, args.per_kind)
        if not gate(args, argv, picked, e):
            return 0
        return asyncio.run(run(args, picked, e))
    except ConfigError as err:
        print(f"配置不对：{err}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
