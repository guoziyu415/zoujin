"""S-5 的报告（B-5 第 6 条）：模拟局的单局花费、换算到 40 轮和 60 轮、延迟、叙事者的计数。只有数字。

    uv run zoujin-s5 --ledger <账本.jsonl> --runs <运行器的 report.json> --out <目录> [--item s5]

- 读三样：
  - 账本（`ZJ_LEDGER` 那个文件）：`item` 的行（默认 `s5`），按 `playthroughId` 分到每一局；
  - 跑模拟局的那个库（`DATABASE_URL`）：每局的 `playthrough_metrics`、对话轮的时刻（把账本的行按时刻分到第几轮）；
  - 运行器的 `report.json`：`cases[].results[]` 里每次运行的 `playthroughId`、`persona`、`seed`，和 `steps[]`
    （每一步的 `kind`、`elapsedMs`）。
- 写 `report.json` 和 `report.md`。不读也不写原话、AI 玩家说的话、人物的回答、结局的文字。
- 单局的产品花费只加 `use: "product"` 的行，不算 `reply`（文字模式里它替 Live 当人物，S-085 ①）；Live 按 results-s1
  8.5 的公式另算（`LIVE`，〔推算〕）。`use: "eval"`（评审员、AI 玩家）单列，不算进单局花费。
- 换算：切片里有的种类用实测；没有的（世界推进、安全分类、记忆、候选话语）照 B-8「单局成本」的推算（`MISSING`，
  〔推算〕）。每轮花费随轮数涨时按趋势外推（PM #99）。1 美元 = 150 日元，和 PRD 7.4 的 300 日元、节约档 240 日元比。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_llm import read_lines, use_of

from zoujin_backend.config import DEADLINES, ConfigError, Settings
from zoujin_backend.db.tables import playthrough_metrics, turns

Json = Any

YEN = 150  # 1 美元
CAP_YEN = 300  # PRD 7.4 的单局上限
SAVER_YEN = 240  # 节约档
TURNS = (40, 60)  # 20 分钟、30 分钟（PRD 7.4）
STRESS_TURNS = 60  # 压力档：60 轮，每轮都检查、2 次尝试
STRESS_CHECKS = 2
SEARCH_TURNS = 200  # 越线的轮数找到这里为止
NOT_IN_COST = ("reply",)  # 文字模式里替 Live 当人物；正式版里人物的话是 Live 说的
PER_GAME = ("ending", "ending-check")  # 一局一次的种类（B-9 的结局），不按轮换算
MISMATCH = 0.01  # 账本和 playthrough_metrics 差超过 1% 就标出来
NO_DATA = "没有数据"
MARGIN = 1.2  # 时限的建议：p99 加两成，向上取整到秒

# playthrough_metrics 的花费列 ↔ 账本的 kind
METRIC_COSTS = {
    "triage": "cost_triage_usd",
    "extract": "cost_extract_usd",
    "check": "cost_check_usd",
    "rewrite": "cost_rewrite_usd",
    "narrate": "cost_narrate_usd",
    "plan": "cost_plan_usd",
}
# 叙事者的计数（第 4 项），从 playthrough_metrics 读；B-9 以后有的列没有就不列
COUNTS = (
    "turns",
    "turns_retracted",
    "turns_triage_skipped",
    "turns_timed_out",
    "candidates_rewritten",
    "candidates_downgraded",
    "candidates_rejected",
    "candidates_confirm_dropped",
    "confirms_asked",
    "actions",
    "plans_accepted",
    "plans_refused",
    "endings_templated",
)


@dataclass(frozen=True)
class Live:
    """Live 语音每轮的花费〔推算〕：输入按 results-s1 8.5 的实测拟合（每轮 base + 每秒已在会话里的音频 per_audio_s），
    输出按数据成本模型的价目（人物的音频和两边的转写）。会话每 rebuild_every 轮重建一次（backend-design 第 8 节）；
    每轮的秒数是 R1 以前的假设（数据成本模型的 player_s、char_s）。"""

    base: float = 0.00086
    per_audio_s: float = 0.0000788
    player_s: float = 9.0
    char_s: float = 9.0
    rebuild_every: int = 8
    out_audio_per_s: float = 25 * 12.00 / 1_000_000  # 25 token/秒 × 输出音频 12 美元 / 百万 token
    out_text_per_s: float = 6 * 4.50 / 1_000_000  # 转写 6 token/秒 × 输出文字 4.5 美元 / 百万 token

    def turn(self, k: int) -> float:
        """会话里第 k 轮（从 0 数）。"""
        heard = k * (self.player_s + self.char_s) + self.player_s
        out = self.char_s * self.out_audio_per_s + (self.player_s + self.char_s) * self.out_text_per_s
        return self.base + self.per_audio_s * heard + out

    def cost(self, turns: int) -> float:
        return sum(self.turn(i % self.rebuild_every) for i in range(turns))


@dataclass(frozen=True)
class Estimate:
    """切片里还没有的一种调用〔推算，B-8「单局成本」〕：一次多少钱，一局几次 = fixed + per_turn × 轮数。"""

    per_call: float
    fixed: float
    per_turn: float

    def calls(self, turns: int) -> float:
        return self.fixed + self.per_turn * turns

    def cost(self, turns: int) -> float:
        return self.per_call * self.calls(turns)


LIVE = Live()
WORLD = "world"  # 世界推进单列（Q-B8 的第三个选项是减少它）
MISSING: dict[str, Estimate] = {
    # 幕切换 3 + 关键时刻 4 + 每 8 轮一次；40 轮 12 次共 $0.31
    WORLD: Estimate(0.31 / 12, 7, 1 / 8),
    "safety": Estimate(0.007 / 44, 0, 1.1),  # 每句一次（玩家和人物开口），40 轮 44 次
    "memory": Estimate(0.003 / 20, 0, 0.5),
    "candidates": Estimate(0.007 / 24, 0, 0.6),
}
ENDING_ESTIMATE = 0.11 + 0.02  # 结局生成加检查〔推算〕：切片的账本里没有 ending 的行时用


# —— 读 ——


def runs_of(report: Mapping[str, Json]) -> list[Json]:
    """运行器 report.json 里带 playthroughId 的每次运行：{playthroughId, case, persona, seed, steps}。"""
    out = []
    for case in report.get("cases", []):
        for r in case.get("results", []):
            if not r.get("playthroughId"):
                continue
            out.append(
                {
                    "playthroughId": r["playthroughId"],
                    "case": case.get("id"),
                    "persona": r.get("persona", case.get("setup", {}).get("persona")),
                    "seed": r.get("seed", case.get("setup", {}).get("seed")),
                    "steps": [
                        {"kind": s.get("kind"), "elapsedMs": s["elapsedMs"]}
                        for s in r.get("steps", [])
                        if isinstance(s.get("elapsedMs"), int | float)
                    ],
                }
            )
    return out


async def _db(url: str, pids: Sequence[str]) -> tuple[dict[str, Json], dict[str, list[Json]]]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as c:
            rows = (
                await c.execute(select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id.in_(pids)))
            ).mappings()
            metrics = {r["playthrough_id"]: {k: _num(v) for k, v in r.items()} for r in rows}
            q = (
                select(turns.c.playthrough_id, turns.c.kind, turns.c.status, turns.c.created_at, turns.c.settled_at)
                .where(turns.c.playthrough_id.in_(pids))
                .order_by(turns.c.created_at)
            )
            by_pt: dict[str, list[Json]] = defaultdict(list)
            for t in (await c.execute(q)).mappings():
                by_pt[t["playthrough_id"]].append(dict(t))
    finally:
        await engine.dispose()
    return metrics, dict(by_pt)


def _num(v: Any) -> Any:
    return float(v) if hasattr(v, "is_finite") else v  # Numeric → float


def _at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# —— 算 ——


def percentile(xs: Sequence[float], p: float) -> float:
    """最近秩（不插值）：p95 就是排序后第 ceil(0.95 n) 个。"""
    s = sorted(xs)
    return float(s[max(0, math.ceil(p / 100 * len(s)) - 1)])


def spread(xs: Sequence[float]) -> Json:
    if not xs:
        return NO_DATA
    return {
        "n": len(xs),
        "p50": percentile(xs, 50),
        "p95": percentile(xs, 95),
        "p99": percentile(xs, 99),
        "max": float(max(xs)),
    }


def by_kind(rows: Iterable[Mapping[str, Json]]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[str(r["kind"])] += float(r.get("costUsd", 0.0))
    return dict(sorted(out.items()))


def product_rows(rows: Iterable[Mapping[str, Json]]) -> list[Mapping[str, Json]]:
    return [r for r in rows if use_of(r) == "product" and r.get("kind") not in NOT_IN_COST]


def per_turn_costs(rows: Sequence[Mapping[str, Json]], talks: Sequence[Mapping[str, Json]]) -> list[float]:
    """这一局每一轮对话的叙事者花费：账本的行按记账时刻分到它之前最近的那一轮（动作、幕末算进前一轮；第一轮之前的
    开局算进第一轮）。一局一次的种类不算。"""
    if not talks:
        return []
    starts = [t["created_at"] for t in talks]
    out = [0.0] * len(talks)
    for r in rows:
        if r.get("kind") in PER_GAME:
            continue
        at = _at(str(r["at"]))
        i = max(0, sum(1 for s in starts if s <= at) - 1)
        out[i] += float(r.get("costUsd", 0.0))
    return out


def trend(series: Sequence[Sequence[float]]) -> Json:
    """每轮花费对轮数的最小二乘（各局的点放在一起，轮数从 1 数）。斜率不大于 0 就按平均。"""
    pts = [(i + 1, c) for s in series for i, c in enumerate(s)]
    if not pts:
        return {"mean": 0.0, "slope": 0.0, "intercept": 0.0, "points": 0, "rising": False}
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    var = sum((x - mx) ** 2 for x, _ in pts)
    slope = sum((x - mx) * (y - my) for x, y in pts) / var if var else 0.0
    rising = slope > 0
    return {
        "mean": my,
        "slope": slope if rising else 0.0,
        "intercept": my - slope * mx if rising else my,
        "points": n,
        "rising": rising,
    }


def narrator_cost(t: Mapping[str, float], turns: int) -> float:
    """前 turns 轮的叙事者花费：c(i) = intercept + slope × i 的和（不升就是平均 × 轮数）。"""
    return t["intercept"] * turns + t["slope"] * turns * (turns + 1) / 2


def scaled(
    t: Mapping[str, float],
    shares: Mapping[str, float],
    ending: float,
    turns: int,
    *,
    check_factor: float = 1.0,
) -> Json:
    """换算到 turns 轮：实测的叙事者（按趋势）分到各种类、世界推进单列、切片里没有的〔推算〕、Live〔推算〕、结局。
    压力档：检查那一份乘 check_factor（每轮都检查、2 次 ÷ 实测的每轮检查次数）。"""
    narr = narrator_cost(t, turns)
    kinds = {k: narr * share for k, share in shares.items()}
    if "check" in kinds:
        kinds["check"] *= check_factor
    est = {k: e.cost(turns) for k, e in MISSING.items()}
    world = est.pop(WORLD)
    live = LIVE.cost(turns)
    total = sum(kinds.values()) + world + sum(est.values()) + live + ending
    return {
        "turns": turns,
        "narrator": {k: round(v, 6) for k, v in kinds.items()},
        "world": round(world, 6),
        "estimated": {k: round(v, 6) for k, v in est.items()},
        "live": round(live, 6),
        "ending": round(ending, 6),
        "totalUsd": round(total, 6),
        "totalYen": round(total * YEN, 1),
        "share": {k: round(v / total, 4) for k, v in {**kinds, WORLD: world, **est, "live": live}.items()}
        if total
        else {},
        "overSaver": total * YEN >= SAVER_YEN,
        "overCap": total * YEN >= CAP_YEN,
    }


def crossing(t: Mapping[str, float], ending: float, yen: float) -> int | None:
    """一局在第几轮越过 yen 日元（叙事者按趋势、切片里没有的和 Live 按推算、结局一次）。SEARCH_TURNS 轮以内
    没越过：None。"""
    for n in range(1, SEARCH_TURNS + 1):
        usd = narrator_cost(t, n) + sum(e.cost(n) for e in MISSING.values()) + LIVE.cost(n) + ending
        if usd * YEN >= yen:
            return n
    return None


def cache_share(rows: Iterable[Mapping[str, Json]]) -> Json:
    """缓存读取占输入的比例：Claude 是 cacheReadTokens / (输入 + 缓存读 + 缓存写)，Google 是
    cachedTokens / inputTokens。"""
    out: Json = {}
    for provider in ("claude", "google"):
        cached = total = 0
        for r in rows:
            if r.get("provider", "google") != provider:
                continue
            u = r.get("usage", {})
            if provider == "claude":
                cached += u.get("cacheReadTokens", 0)
                total += u.get("inputTokens", 0) + u.get("cacheReadTokens", 0) + u.get("cacheWriteTokens", 0)
            else:
                cached += u.get("cachedTokens", 0)
                total += u.get("inputTokens", 0)
        out[provider] = round(cached / total, 4) if total else NO_DATA
    return out


def latency(rows: Sequence[Mapping[str, Json]], deadlines: Mapping[str, float]) -> Json:
    """每种调用：耗时的分布、超过时限的比例、超时（重发）的次数、没有回应的、回来不能用的。老行没有 ms：没有数据。"""
    out: Json = {}
    for kind in sorted({str(r["kind"]) for r in rows}):
        mine = [r for r in rows if r["kind"] == kind]
        ms = [float(r["ms"]) for r in mine if "ms" in r]
        limit = deadlines.get(kind)
        timeouts = sum(1 for r in mine if r.get("status") == "timeout")
        late = sum(1 for r in mine if "ms" in r and r.get("status") != "timeout" and limit and r["ms"] > limit * 1000)
        out[kind] = {
            "calls": len(mine),
            "ms": spread(ms),
            "deadlineS": limit,
            "overDeadline": round((late + timeouts) / len(mine), 4) if ms else NO_DATA,
            "timeouts": timeouts,
            "errors": sum(1 for r in mine if r.get("status") == "error"),
            "badOutput": sum(1 for r in mine if r.get("status") == "bad-output"),
        }
    return out


def advice(lat: Mapping[str, Json]) -> dict[str, Json]:
    """时限的建议：p99 加两成，向上取整到秒（只是建议，改代码另开 PR）。"""
    out: dict[str, Json] = {}
    for kind, v in lat.items():
        out[kind] = math.ceil(v["ms"]["p99"] * MARGIN / 1000) if isinstance(v["ms"], dict) else NO_DATA
    return out


def report(
    rows: Sequence[Mapping[str, Json]],
    runs: Sequence[Mapping[str, Json]],
    metrics: Mapping[str, Mapping[str, Json]],
    talks: Mapping[str, Sequence[Mapping[str, Json]]],
    endings: Mapping[str, Sequence[Mapping[str, Json]]] | None = None,
    deadlines: Mapping[str, float] = DEADLINES,
) -> Json:
    """全部是纯计算（测试直接调）。talks：每局的对话轮（created_at 升序）；endings：每局的结局任务（有 settled_at）。"""
    plays = []
    series = []
    measured_kinds: dict[str, float] = defaultdict(float)
    endings_usd: list[float] = []
    check_calls = total_turns = 0
    for run in runs:
        pid = run["playthroughId"]
        mine = [r for r in rows if r.get("playthroughId") == pid]
        product = product_rows(mine)
        kinds = by_kind(product)
        m = metrics.get(pid, {})
        n_turns = len(talks.get(pid, []))
        live = LIVE.cost(n_turns)
        mismatch = {}
        for kind, col in METRIC_COSTS.items():
            if col in m:
                ledger_usd, db_usd = kinds.get(kind, 0.0), float(m[col])
                if abs(ledger_usd - db_usd) > MISMATCH * max(ledger_usd, db_usd, 1e-9) and max(ledger_usd, db_usd) > 0:
                    mismatch[kind] = {"ledger": round(ledger_usd, 6), "metrics": round(db_usd, 6)}
        cost = sum(kinds.values())
        per_turn = per_turn_costs(product, talks.get(pid, []))
        series.append(per_turn)
        for k, v in kinds.items():
            if k not in PER_GAME:
                measured_kinds[k] += v
        ending = sum(v for k, v in kinds.items() if k in PER_GAME)
        if ending:
            endings_usd.append(ending)
        check_calls += sum(1 for r in product if r["kind"] == "check")
        total_turns += n_turns
        plays.append(
            {
                "playthroughId": pid,
                "case": run.get("case"),
                "persona": run.get("persona"),
                "seed": run.get("seed"),
                "turns": n_turns,
                "costByKind": {k: round(v, 6) for k, v in kinds.items()},
                "narratorUsd": round(cost, 6),
                "liveUsd": round(live, 6),
                "totalUsd": round(cost + live, 6),
                "totalYen": round((cost + live) * YEN, 1),
                "metricsMismatch": mismatch,
                "counts": {k: m[k] for k in COUNTS if k in m},
                "evalUsd": round(sum(float(r.get("costUsd", 0.0)) for r in mine if use_of(r) == "eval"), 6),
            }
        )
    t = trend(series)
    narr_total = sum(measured_kinds.values())
    shares = {k: v / narr_total for k, v in measured_kinds.items()} if narr_total else {}
    ending = sum(endings_usd) / len(endings_usd) if endings_usd else ENDING_ESTIMATE
    per_turn_checks = check_calls / total_turns if total_turns else 0.0
    out_scaled = {str(n): scaled(t, shares, ending, n) for n in TURNS}
    out_scaled["stress"] = scaled(
        t,
        shares,
        ending,
        STRESS_TURNS,
        check_factor=max(1.0, STRESS_CHECKS / per_turn_checks) if per_turn_checks else 1.0,
    )
    ours = {r["playthroughId"] for r in runs}
    eval_rows = [r for r in rows if use_of(r) == "eval"]
    steps: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for s in run.get("steps", []):
            steps[str(s.get("kind"))].append(float(s["elapsedMs"]))
    ending_ms = [
        (e["settled_at"] - e["created_at"]).total_seconds() * 1000
        for pid in ours
        for e in (endings or {}).get(pid, [])
        if e.get("settled_at") is not None
    ]
    product_all = product_rows([r for r in rows if r.get("playthroughId") in ours])
    lat = latency(product_all, deadlines)
    return {
        "params": {
            "yenPerUsd": YEN,
            "capYen": CAP_YEN,
            "saverYen": SAVER_YEN,
            "live": asdict(LIVE),
            "missing": {k: asdict(v) for k, v in MISSING.items()},
            "endingEstimateUsd": None if endings_usd else ENDING_ESTIMATE,
            "estimated": "live、missing、endingEstimateUsd 是〔推算〕",
        },
        "playthroughs": plays,
        "perTurn": {k: round(v, 8) for k, v in t.items()} | {"rising": t["rising"], "points": t["points"]},
        "scaled": out_scaled,
        "crossing": {str(SAVER_YEN): crossing(t, ending, SAVER_YEN), str(CAP_YEN): crossing(t, ending, CAP_YEN)},
        "cacheRead": cache_share(product_all),
        "latency": lat,
        "steps": {k: spread(v) for k, v in sorted(steps.items())} or NO_DATA,
        "endingMs": spread(ending_ms),
        "deadlineAdvice": advice(lat),
        "eval": {"usd": round(sum(float(r.get("costUsd", 0.0)) for r in eval_rows), 6), "byKind": by_kind(eval_rows)},
    }


# —— 写 ——


def markdown(r: Mapping[str, Json]) -> str:
    def money(usd: float) -> str:
        return f"${usd:.3f}（{usd * YEN:.0f} 円）"

    lines = [
        "# S-5 报告",
        "",
        "只有数字。Live、切片里还没有的种类、没有实测时的结局是〔推算〕（参数在 report.json 的 params）。",
        "",
        "## 每局",
        "",
        "| 局 | 画像 | 种子 | 轮数 | 叙事者 | Live〔推算〕 | 合计 | 和 metrics 对不上 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for p in r["playthroughs"]:
        bad = "、".join(p["metricsMismatch"]) or "—"
        lines.append(
            f"| {p['playthroughId']} | {p['persona']} | {p['seed']} | {p['turns']} | ${p['narratorUsd']:.4f} | "
            f"${p['liveUsd']:.4f} | {money(p['totalUsd'])} | {bad} |"
        )
    t = r["perTurn"]
    lines += [
        "",
        "## 每轮的叙事者花费",
        "",
        f"平均 ${t['mean']:.5f}；{'随轮数涨：按趋势外推' if t['rising'] else '不随轮数涨：按平均'}"
        f"（斜率 ${t['slope']:.6f}/轮，{t['points']} 个点）。",
        "",
        "## 换算",
        "",
        "| | 40 轮 | 60 轮 | 压力（60 轮，每轮检查 2 次） |",
        "|---|---:|---:|---:|",
    ]
    cols = [r["scaled"]["40"], r["scaled"]["60"], r["scaled"]["stress"]]
    names = sorted({k for c in cols for k in c["share"]})
    for k in names:
        lines.append(f"| {k} | " + " | ".join(f"{c['share'].get(k, 0) * 100:.1f}%" for c in cols) + " |")
    lines.append("| **合计** | " + " | ".join(money(c["totalUsd"]) for c in cols) + " |")
    cross = r["crossing"]
    lines += [
        "",
        f"越过节约档 {SAVER_YEN} 円：第 {cross[str(SAVER_YEN)] or f'{SEARCH_TURNS}+'} 轮；"
        f"越过上限 {CAP_YEN} 円：第 {cross[str(CAP_YEN)] or f'{SEARCH_TURNS}+'} 轮。",
        "",
        f"缓存读取占输入：Claude {r['cacheRead']['claude']}，Google {r['cacheRead']['google']}。",
        "",
        "## 延迟（毫秒）",
        "",
        "| 种类 | 次数 | p50 | p95 | p99 | 最长 | 时限（秒） | 超时限 | 超时重发 | 没回应 | 不能用 | 建议时限（秒） |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind, v in r["latency"].items():
        ms = v["ms"]
        cells = [f"{ms[k]:.0f}" for k in ("p50", "p95", "p99", "max")] if isinstance(ms, dict) else [NO_DATA] * 4
        over = f"{v['overDeadline'] * 100:.1f}%" if isinstance(v["overDeadline"], float) else NO_DATA
        lines.append(
            f"| {kind} | {v['calls']} | "
            + " | ".join(cells)
            + f" | {v['deadlineS'] or '—'} | {over} | {v['timeouts']} | "
            f"{v['errors']} | {v['badOutput']} | {r['deadlineAdvice'][kind]} |"
        )
    lines += ["", "每一步（玩家说完到提交，elapsedMs）："]
    steps = r["steps"]
    if isinstance(steps, dict):
        for kind, v in steps.items():
            lines.append(f"- {kind}：p50 {v['p50']:.0f}、p95 {v['p95']:.0f}（{v['n']} 步）")
    else:
        lines.append(f"- {NO_DATA}")
    e = r["endingMs"]
    ending = f"p50 {e['p50']:.0f}、最长 {e['max']:.0f}" if isinstance(e, dict) else NO_DATA
    lines.append(f"- 结局从开始到存好：{ending}")
    lines += [
        "",
        "## 叙事者的计数",
        "",
        "| 局 | " + " | ".join(COUNTS) + " |",
        "|---|" + "---:|" * len(COUNTS),
    ]
    for p in r["playthroughs"]:
        lines.append(f"| {p['playthroughId']} | " + " | ".join(str(p["counts"].get(k, "—")) for k in COUNTS) + " |")
    lines += ["", "## 评审员和 AI 玩家（不算进单局）", "", f"合计 ${r['eval']['usd']:.4f}。", ""]
    return "\n".join(lines)


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="zoujin-s5", description="S-5：模拟局的单局花费、换算、延迟（只有数字）")
    p.add_argument("--ledger", type=Path, help="账本（默认 ZJ_LEDGER）")
    p.add_argument("--item", default="s5", help="只看这一项的行（默认 s5）")
    p.add_argument("--runs", type=Path, required=True, help="运行器的 report.json（每次运行带 playthroughId）")
    p.add_argument("--out", type=Path, required=True, help="写 report.json、report.md 的目录")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse(argv)
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        print(f"配置不对：{e}", file=sys.stderr)
        return 2
    ledger = args.ledger or settings.ledger
    if ledger is None or not ledger.is_file():
        print("没有账本：给 --ledger 或设 ZJ_LEDGER", file=sys.stderr)
        return 2
    rows = [r for r in read_lines(ledger) if args.item is None or r.get("item") == args.item]
    runs = runs_of(json.loads(args.runs.read_text(encoding="utf-8")))
    if not runs:
        print("report.json 里没有带 playthroughId 的运行", file=sys.stderr)
        return 2
    metrics, all_turns = asyncio.run(_db(settings.database_url, [r["playthroughId"] for r in runs]))
    talks = {
        pid: [t for t in ts if t["kind"] == "talk" and t["status"] != "retracted"] for pid, ts in all_turns.items()
    }
    endings = {pid: [t for t in ts if t["kind"] == "ending"] for pid, ts in all_turns.items()}
    out = report(rows, runs, metrics, talks, endings, settings.deadlines)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "report.md").write_text(markdown(out), encoding="utf-8")
    print(f"报告：{args.out / 'report.md'}，{args.out / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
