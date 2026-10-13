"""Budget and degradation (B-14, backend-design 5.2, 5.3, S-019). Shared by the narrator and the gateway; all state is
in the database.

| Tier | When | Who does what |
|---|---|---|
| Normal `normal` | cost < 80% of 300 yen | — |
| Saving `saving` | ≥ 240 yen | shorter situation, memories 8 → 4, no mid-act world advance, suggestions on 「？」 |
| Degraded `degraded` | ≥ 300 yen | gateway: `degraded { reason: "budget" }` before the next turn, text answers |

(Saving is `Policy`; in degraded the narrator carries on as usual.)

What the saving tier does now: 口ぶりの例 4 → 2, さっきまでの会話 6 → 3 turns, 覚えていること 8 → 4 items; the mid-act
world advance and suggested lines are not there yet (B-16, B-21), and the cards doing them read `policy(tier)`.

- A playthrough's cost = the sum of all `cost_*_usd` in `playthrough_metrics` × 150 (data-design section 3, same
  conversion as `s5.py`).
- The tier only goes up, never down; the gateway calls `refresh()` before every turn starts and on `focus`; on entering
  a tier it records `budget_saving_at`, `degraded_at`, and the Trace records one `budget` (without text).
- Per account per day (cut over at midnight Japan time): 5 playthrough starts and 60 minutes of voice, recorded in
  `account_days` (deleting a playthrough does not refund a start).
- Global voice switch: `voice_enabled` in `app_settings`, changed with `zoujin-admin voice off|on`. Automatic circuit
  breaking and alerts follow the deployment card.

予算と劣化動作（B-14、backend-design 5.2、5.3、S-019）。ナレーターとゲートウェイが共用し、状態はすべて
データベースにある。

| ティア | いつ | 誰が何をするか |
|---|---|---|
| 通常 `normal` | 1 周回の費用 < 300 円の 80% | — |
| 節約 `saving` | ≥ 240 円 | 状況説明を短く、記憶 8 → 4、幕の中盤の世界の進行を停止、発言候補は「？」で |
| 劣化 `degraded` | ≥ 300 円 | ゲートウェイ：次のターンの前に `degraded { reason: "budget" }`、テキストで答える |

（節約は `Policy`。劣化でもナレーターは通常どおり動く。）

節約ティアで今できていること：口ぶりの例 4 → 2、さっきまでの会話 6 → 3 ターン、覚えていること 8 → 4 件。幕ごとの中盤の
世界の進行と発言候補はまだない（B-16、B-21）。それらを担うカードが `policy(tier)` を読む。

- 1 周回の費用 = `playthrough_metrics` のすべての `cost_*_usd` の合計 × 150（data-design 第 3 節、換算は
  `s5.py` と同じ）。
- ティアは上がるだけで下がらない。ゲートウェイは各ターンの開始前と `focus` のときに `refresh()` を呼ぶ。ティアに入ると
  `budget_saving_at`、`degraded_at` を記録し、Trace に `budget` を 1 件記録する（テキストは含まない）。
- アカウントごと、1 日ごと（日本時間 0 時で切り替え）：周回の開始 5 回、音声 60 分。`account_days` に記録する（周回を
  削除しても回数は戻らない）。
- 全体の音声スイッチ：`app_settings` の `voice_enabled`。`zoujin-admin voice off|on` で変える。自動遮断とアラートは
  デプロイのカードに従う。
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

USD_JPY = 150.0  # same as s5.py / s5.py と同じ
# PRD 7.4's per-playthrough cap; ZJ_RUN_CAP_JPY can change it (tests, tuning before R1)
# PRD 7.4 の 1 周回の上限。ZJ_RUN_CAP_JPY で変更できる（テスト、R1 前の調整）
RUN_CAP_JPY = 300.0
CAP_ENV = "ZJ_RUN_CAP_JPY"
SAVING_RATIO = 0.8
RUNS_PER_DAY = 5
VOICE_MINUTES = 60
# Push limits once at 5 minutes left (ux-design section 12)
# 残り 5 分で limits を 1 回送る（ux-design 第 12 節）
WARN_MINUTES = 5
JST = timezone(timedelta(hours=9))

TIERS = ("normal", "saving", "degraded")
COSTS = tuple(c for c in playthrough_metrics.c if c.name.startswith("cost_"))


@dataclass(frozen=True)
class Policy:
    """What a tier does. In degraded, the narrator follows the saving tier.

    ティアごとのやり方。degraded のナレーターは節約ティアに従う。
    """

    # how many 「口ぶりの例」 lines in the Live system instruction
    # Live のシステム指示の「口ぶりの例」の数
    brief_samples: int
    # How many turns of 「さっきまでの会話」 are carried into a new session
    # 新しいセッションに持ち込む「さっきまでの会話」のターン数
    recent_turns: int
    # how many memories are injected (read by the memory card)
    # 注入する記憶の件数（記憶のカードが読む）
    memory_inject: int
    # Mid-act world advance in every act (read by the world advance card)
    # 幕ごとの中盤の世界の進行（世界の進行のカードが読む）
    mid_act_progression: bool
    # Suggested lines are generated only when the player taps 「？」 (read by the suggested lines card)
    # 発言候補はプレイヤーが「？」をタップしたときだけ生成する（発言候補のカードが読む）
    candidates_on_demand: bool


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
    """Raise the tier by cost (only up, never down) and return the current tier. When it goes up, record the time and
    a Trace `budget`.

    費用に応じてティアを上げ（上がるだけで下がらない）、現在のティアを返す。上がったら時刻と Trace の `budget`
    を記録する。
    """
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
    if not done.rowcount:  # raised elsewhere at the same time / 別の場所で同時に上がった
        return await tier_of(c, pid)
    await _mark(c, pid, want, "budget")
    if tracer is not None:
        with tracer.span(
            "budget", playthrough_id=pid, run_cost_jpy_so_far=round(jpy), tier=want, degraded=want == "degraded"
        ):
            pass
    return want


async def set_tier(c: Any, pid: str, tier: str) -> None:
    """The eval entry point's `setup.budgetTier` (E6): set the tier directly.

    評価の入口の `setup.budgetTier`（E6）：ティアを直接設定する。
    """
    await c.execute(update(playthroughs).where(playthroughs.c.playthrough_id == pid).values(budget_tier=tier))
    await _mark(c, pid, tier, "budget")


async def mark_degraded(c: Any, pid: str, reason: str) -> None:
    """The first degradation in this playthrough (for any reason): record `degraded_at` and the reason; later ones do
    not change it.

    この周回で最初の劣化（理由は問わない）：`degraded_at` と理由を記録し、以後は変えない。
    """
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


# —— Per account per day / アカウントごと、1 日ごと ——


def jst_day(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(JST).date()


def seconds_to_midnight(now: datetime | None = None) -> int:
    """Seconds until the next midnight Japan time (`retryAfterSeconds` of `429 daily_limit`).

    日本時間の次の 0 時までの秒数（`429 daily_limit` の `retryAfterSeconds`）。
    """
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


# —— Global voice switch / 全体の音声スイッチ ——


async def voice_enabled(c: Any) -> bool:
    v = await c.scalar(select(app_settings.c.value).where(app_settings.c.key == "voice_enabled"))
    return v is None or bool(v)


async def set_voice_enabled(c: Any, on: bool) -> None:
    stmt = insert(app_settings).values(key="voice_enabled", value=on)
    await c.execute(
        stmt.on_conflict_do_update(index_elements=[app_settings.c.key], set_={"value": on, "updated_at": func.now()})
    )
