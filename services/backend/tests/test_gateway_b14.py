"""B-14：预算和降级（假模型、假 Live，不花钱）。

一局花到 240 日元进节约档、300 日元改文字回答；每账号每天开局 5 次（429 先于 409）、语音 60 分钟（剩 5 分钟推
`limits`、用完 `degraded daily`）；全局语音开关；评测入口的 `budgetTier`；Trace 和指标列。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, update
from zoujin_backend import budget, eval_api
from zoujin_backend.db.tables import account_days, playthrough_metrics, playthroughs

from .conftest import OLD, Env
from .test_gateway import CREATE, Player, invite
from .test_gateway_b4 import InProc, Make, Play, db
from .test_gateway_b4 import inproc as inproc  # noqa: PLC0414 - pytest 的 fixture 按名字找
from .test_gateway_b4 import play as play  # noqa: PLC0414

pytestmark = pytest.mark.db

SPEED = 0.05
Json = Any


def spend(env: Env, pid: str, usd: float) -> None:
    """叙事者那边花了这么多（写进 cost_extract_usd）。"""

    async def put(c: Any) -> None:
        await c.execute(
            update(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == pid).values(cost_extract_usd=usd)
        )

    db(env, put)


def user_of(p: Player) -> str:
    return str(p.call("me", 200, "GET", "/v1/me")["user"]["userRef"])


def used_today(env: Env, user_id: str, *, runs: int | None = None, seconds: float | None = None) -> None:
    async def put(c: Any) -> None:
        await budget.count_run(c, user_id)  # 确保有这一行
        values: dict[str, Any] = {}
        if runs is not None:
            values["runs"] = runs
        if seconds is not None:
            values["voice_seconds"] = seconds
        await c.execute(
            update(account_days)
            .where(account_days.c.user_id == user_id, account_days.c.day == budget.jst_day())
            .values(**values)
        )

    db(env, put)


def metrics(env: Env, pid: str) -> Json:
    async def get(c: Any) -> Json:
        m = (await c.execute(select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == pid))).mappings()
        return dict(m.one())

    return db(env, get)


def tier(env: Env, pid: str) -> str:
    async def get(c: Any) -> str:
        return await budget.tier_of(c, pid)

    return db(env, get)


def voice_switch(env: Env, on: bool) -> None:
    async def put(c: Any) -> None:
        await budget.set_voice_enabled(c, on)

    db(env, put)


def spans(s: InProc, name: str) -> list[Json]:
    return [dict(x) for x in s.gw.tracer.named(name)]


# —— 不连库的 ——


def test_tiers_by_cost() -> None:
    assert budget.tier_for(239.9) == "normal"
    assert budget.tier_for(240) == "saving"
    assert budget.tier_for(299.9) == "saving"
    assert budget.tier_for(300) == "degraded"
    assert budget.tier_for(100, cap=100) == "degraded"
    assert budget.policy("saving").memory_inject == 4 and budget.policy("normal").memory_inject == 8
    assert budget.policy("degraded") == budget.policy("saving")


def test_day_is_japan_time() -> None:
    late = datetime(2026, 10, 11, 15, 30, tzinfo=UTC)  # 日本时间 10-12 00:30
    assert str(budget.jst_day(late)) == "2026-10-12"
    assert budget.seconds_to_midnight(datetime(2026, 10, 11, 14, 59, 0, tzinfo=UTC)) == 60
    assert budget.minutes_left(55.5 * 60) == 4 and budget.minutes_left(4000) == 0


def test_run_cap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(budget.CAP_ENV, "100")
    assert budget.tier_for(80) == "saving"


# —— 单局花费 ——


def test_saving_tier_shortens_the_brief(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    spend(env, p.pid, 1.7)  # 255 日元
    p.focus(OLD)
    assert tier(env, p.pid) == "saving"
    (opened,) = [o for o in s.live.opened if o.character == OLD]
    assert opened.system.count("口ぶりの例") <= 2
    (sp,) = spans(s, "budget")
    assert sp["tier"] == "saving" and sp["run_cost_jpy_so_far"] == 255 and sp["degraded"] is False
    m = metrics(env, p.pid)
    assert m["budget_saving_at"] is not None and m["degraded_at"] is None
    assert not [x for x in p.log if x["type"] == "degraded"]


def test_over_the_cap_characters_answer_in_text(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)
    spend(env, p.pid, 2.0)  # 300 日元
    t = p.text("もう一度、話を聞かせてください。")
    assert p.expect("degraded")["reason"] == "budget"
    final = p.expect("transcript", turnId=t, speaker=OLD, final=True)
    assert final["source"] == "live" and final["text"]
    # 文字回答：人物定稿在 turn_complete { audio: false } 之前（契约 3.3）
    assert p.expect("turn_complete", turnId=t)["audio"] is False
    assert p.index("transcript", turnId=t, speaker=OLD, final=True) < p.index("turn_complete", turnId=t)
    p.expect("turn_settled", turnId=t)  # 叙事者照常
    p.voice()
    assert p.expect("error")["error"]["code"] == "voice_unavailable"
    p.send({"type": "focus", "character": OLD})  # 再 focus 也不开会话
    assert p.expect("session_ready", character=OLD)["voiceAvailable"] is False
    m = metrics(env, p.pid)
    assert m["degraded_reason"] == "budget" and m["degraded_at"] is not None and m["budget_saving_at"] is not None
    assert float(m["cost_reply_usd"]) >= 0
    assert tier(env, p.pid) == "degraded"
    assert [x["tier"] for x in spans(s, "budget")] == ["degraded"]
    # 重连：welcome 里已经是降级，不再推 degraded
    p.ws.close()  # type: ignore[union-attr]
    p.ws = None
    p.connect(last_seq=p.last_seq)
    w = p.expect("welcome")
    assert w["voice"]["degraded"] is True and w["voice"]["enabled"] is True


# —— 每账号每天 ——


def test_sixth_run_today_is_429_before_409(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s, connect=False)  # 有一局进行中
    used_today(env, user_of(p), runs=budget.RUNS_PER_DAY)
    doc = p.call("playthroughs-create", 429, "POST", "/v1/playthroughs", CREATE, key="k-sixth")
    assert doc["error"]["code"] == "daily_limit" and 0 < doc["error"]["retryAfterSeconds"] <= 86400
    me = p.call("me", 200, "GET", "/v1/me")
    assert me["limits"]["runsToday"] == budget.RUNS_PER_DAY


def test_starting_counts_a_run(env: Env, inproc: Make) -> None:
    """开局记进 account_days（删局不退次数：不从 playthroughs 现数）。"""
    s = inproc(SPEED)
    p = Player(s.base)
    try:
        p.login(invite(env))
        assert p.call("me", 200, "GET", "/v1/me")["limits"]["runsToday"] == 0
        p.start()
        assert p.call("me", 200, "GET", "/v1/me")["limits"]["runsToday"] == 1
    finally:
        p.close()


def test_daily_voice_minutes_warn_then_degrade(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s, connect=False)
    user = user_of(p)
    used_today(env, user, seconds=55.5 * 60)
    p.connect(last_seq=p.last_seq)
    assert p.expect("welcome")["voice"]["minutesLeftToday"] == 4
    assert p.call("me", 200, "GET", "/v1/me")["limits"]["voiceMinutesLeft"] == 4
    p.focus(OLD)
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)
    assert p.find("limits")["voiceMinutesLeft"] <= budget.WARN_MINUTES
    t = p.text("もう少しだけ。")
    p.expect("turn_settled", turnId=t)
    assert len([x for x in p.log if x["type"] == "limits"]) == 1  # 一条连接一次
    used_today(env, user, seconds=budget.VOICE_MINUTES * 60)
    t = p.text("また話しましょう。")
    assert p.expect("degraded")["reason"] == "daily"
    assert p.expect("turn_complete", turnId=t)["audio"] is False
    assert metrics(env, p.pid)["degraded_reason"] == "daily"


def test_voice_seconds_are_counted(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)

    async def get(c: Any) -> float:
        return await budget.voice_seconds_today(c, user_of(p))

    assert db(env, get) > 0
    m = metrics(env, p.pid)
    assert float(m["voice_in_seconds"]) + float(m["voice_out_seconds"]) > 0


# —— 全局开关 ——


def test_voice_switch_off_then_on(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    s.gw.voice_ttl_s = 0
    p = play(s)
    voice_switch(env, False)
    p.send({"type": "focus", "character": OLD})
    assert p.expect("degraded")["reason"] == "service"
    assert p.expect("session_ready", character=OLD)["voiceAvailable"] is False
    t = p.text("こんにちは。")
    assert p.expect("turn_complete", turnId=t)["audio"] is False
    assert metrics(env, p.pid)["degraded_reason"] == "service"
    voice_switch(env, True)
    p.focus(OLD)
    assert p.log[-1]["voiceAvailable"] is True


# —— 评测入口 ——


def test_eval_setup_budget_tier(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    setup = {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "place": "place.syracuse-square"}
    s = eval_api.setup(setup | {"budgetTier": "saving"}, mode="text")
    assert tier(env, s.pid) == "saving"

    async def get(c: Any) -> str:
        return str(await c.scalar(select(playthroughs.c.budget_tier).where(playthroughs.c.playthrough_id == s.pid)))

    assert db(env, get) == "saving"
