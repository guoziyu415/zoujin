"""预算和降级（B-14，backend-design 5.2、5.3，S-019）。叙事者和网关共用，状态都在库里。

| 档 | 什么时候 | 谁做什么 |
|---|---|---|
| 正常 `normal` | 一局花费 < 300 日元的 80% | — |
| 节约 `saving` | ≥ 240 日元 | 局势说明短一些、记忆 8 → 4、中段世界推进停、候选话语按「？」（`Policy`） |
| 降级 `degraded` | ≥ 300 日元 | 网关：下一轮开始前 `degraded { reason: "budget" }`，人物改文字回答；叙事者照常 |

节约档现在做到的：口ぶりの例 4 → 2、さっきまでの会話 6 → 3 轮、覚えていること 8 → 4 条；每幕中段的世界推进、
候选话语还没有（B-16、B-21），做它们的卡读 `policy(tier)`。

- 一局的花费 = `playthrough_metrics` 里全部 `cost_*_usd` 之和 × 150（data-design 第 3 节，换算同 `s5.py`）。
- 档位只升不降，网关在每一轮开始前和 `focus` 时 `refresh()`；进档时记 `budget_saving_at`、`degraded_at`，
  Trace 记一条 `budget`（不带文字）。
- 每账号每天（日本时间 0 点切）：开局 5 次、语音 60 分钟，记在 `account_days`（删局不退次数）。
- 全局语音开关：`app_settings` 的 `voice_enabled`，`zoujin-admin voice off|on` 改。自动熔断和告警跟部署的卡。
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from zoujin_backend.db.tables import account_days, app_settings, playthrough_metrics, playthroughs
from zoujin_backend.trace import Tracer

USD_JPY = 150.0  # 同 s5.py
RUN_CAP_JPY = 300.0  # PRD 7.4 的单局上限；ZJ_RUN_CAP_JPY 可改（测试、R1 前调数）
CAP_ENV = "ZJ_RUN_CAP_JPY"
SAVING_RATIO = 0.8
RUNS_PER_DAY = 5
VOICE_MINUTES = 60
WARN_MINUTES = 5  # 剩 5 分钟推一次 limits（ux-design 第 12 节）
JST = timezone(timedelta(hours=9))

TIERS = ("normal", "saving", "degraded")
COSTS = tuple(c for c in playthrough_metrics.c if c.name.startswith("cost_"))


@dataclass(frozen=True)
class Policy:
    """一档的做法。degraded 的叙事者照节约档。"""

    brief_samples: int  # Live 系统指令里「口ぶりの例」几句
    recent_turns: int  # 带进新会话的「さっきまでの会話」几轮
    memory_inject: int  # 记忆注入几条（记忆的卡读）
    mid_act_progression: bool  # 每幕中段的世界推进（世界推进的卡读）
    candidates_on_demand: bool  # 候选话语只在玩家点「？」时生成（候选话语的卡读）


POLICY = {
    "normal": Policy(
        brief_samples=4, recent_turns=6, memory_inject=8, mid_act_progression=True, candidates_on_demand=False
    ),
    "saving": Policy(
        brief_samples=2, recent_turns=3, memory_inject=4, mid_act_progression=False, candidates_on_demand=True
    ),
}


def policy(tier: str) -> Policy:
    return POLICY["normal" if tier == "normal" else "saving"]


def run_cap_jpy() -> float:
    raw = os.environ.get(CAP_ENV, "")
    return float(raw) if raw else RUN_CAP_JPY


def tier_for(jpy: float, cap: float | None = None) -> str:
    cap = run_cap_jpy() if cap is None else cap
    if jpy >= cap:
        return "degraded"
    if jpy >= cap * SAVING_RATIO:
        return "saving"
    return "normal"


async def run_cost_jpy(c: Any, pid: str) -> float:
    row = (await c.execute(select(*COSTS).where(playthrough_metrics.c.playthrough_id == pid))).first()
    return sum(float(x or 0) for x in row) * USD_JPY if row is not None else 0.0


async def tier_of(c: Any, pid: str) -> str:
    return str(
        await c.scalar(select(playthroughs.c.budget_tier).where(playthroughs.c.playthrough_id == pid)) or "normal"
    )


async def refresh(c: Any, pid: str, tracer: Tracer | None = None) -> str:
    """按花费升档（只升不降），返回现在的档。升了记时刻和 Trace 的 `budget`。"""
    cur = await tier_of(c, pid)
    jpy = await run_cost_jpy(c, pid)
    want = tier_for(jpy)
    if TIERS.index(want) <= TIERS.index(cur):
        return cur
    lower = TIERS[: TIERS.index(want)]
    done = await c.execute(
        update(playthroughs)
        .where(playthroughs.c.playthrough_id == pid, playthroughs.c.budget_tier.in_(lower))
        .values(budget_tier=want)
    )
    if not done.rowcount:  # 别处同时升了
        return await tier_of(c, pid)
    await _mark(c, pid, want, "budget")
    if tracer is not None:
        with tracer.span(
            "budget", playthrough_id=pid, run_cost_jpy_so_far=round(jpy), tier=want, degraded=want == "degraded"
        ):
            pass
    return want


async def set_tier(c: Any, pid: str, tier: str) -> None:
    """评测入口的 `setup.budgetTier`（E6）：直接设档。"""
    await c.execute(update(playthroughs).where(playthroughs.c.playthrough_id == pid).values(budget_tier=tier))
    await _mark(c, pid, tier, "budget")


async def mark_degraded(c: Any, pid: str, reason: str) -> None:
    """这一局第一次降级（任何原因）：记 `degraded_at` 和原因，之后的不改。"""
    m = playthrough_metrics.c
    await c.execute(
        update(playthrough_metrics)
        .where(m.playthrough_id == pid, m.degraded_at.is_(None))
        .values(degraded_at=func.now(), degraded_reason=reason)
    )


async def _mark(c: Any, pid: str, tier: str, reason: str) -> None:
    if tier == "normal":
        return
    m = playthrough_metrics.c
    await c.execute(
        update(playthrough_metrics)
        .where(m.playthrough_id == pid, m.budget_saving_at.is_(None))
        .values(budget_saving_at=func.now())
    )
    if tier == "degraded":
        await mark_degraded(c, pid, reason)


# —— 每账号每天 ——


def jst_day(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(JST).date()


def seconds_to_midnight(now: datetime | None = None) -> int:
    """到日本时间下一个 0 点还有几秒（`429 daily_limit` 的 `retryAfterSeconds`）。"""
    now = (now or datetime.now(UTC)).astimezone(JST)
    nxt = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=JST)
    return max(1, math.ceil((nxt - now).total_seconds()))


async def _today(c: Any, user_id: str) -> Any:
    return (
        await c.execute(
            select(account_days.c.runs, account_days.c.voice_seconds).where(
                account_days.c.user_id == user_id, account_days.c.day == jst_day()
            )
        )
    ).first()


async def runs_today(c: Any, user_id: str) -> int:
    row = await _today(c, user_id)
    return int(row.runs) if row is not None else 0


async def voice_seconds_today(c: Any, user_id: str) -> float:
    row = await _today(c, user_id)
    return float(row.voice_seconds) if row is not None else 0.0


def minutes_left(used_s: float) -> int:
    return max(0, math.floor((VOICE_MINUTES * 60 - used_s) / 60))


async def count_run(c: Any, user_id: str) -> None:
    stmt = insert(account_days).values(user_id=user_id, day=jst_day(), runs=1)
    await c.execute(
        stmt.on_conflict_do_update(
            index_elements=[account_days.c.user_id, account_days.c.day], set_={"runs": account_days.c.runs + 1}
        )
    )


async def add_voice(c: Any, user_id: str, seconds: float) -> None:
    if seconds <= 0:
        return
    stmt = insert(account_days).values(user_id=user_id, day=jst_day(), voice_seconds=round(seconds, 1))
    await c.execute(
        stmt.on_conflict_do_update(
            index_elements=[account_days.c.user_id, account_days.c.day],
            set_={"voice_seconds": account_days.c.voice_seconds + round(seconds, 1)},
        )
    )


# —— 全局语音开关 ——


async def voice_enabled(c: Any) -> bool:
    v = await c.scalar(select(app_settings.c.value).where(app_settings.c.key == "voice_enabled"))
    return v is None or bool(v)


async def set_voice_enabled(c: Any, on: bool) -> None:
    stmt = insert(app_settings).values(key="voice_enabled", value=on)
    await c.execute(
        stmt.on_conflict_do_update(index_elements=[app_settings.c.key], set_={"value": on, "updated_at": func.now()})
    )
