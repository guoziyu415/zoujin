"""共用包 zoujin-llm（B-8 验收第 5 组）：账本、单价、模型档、回放的键、SDK 错误的转换。不联网、不用 Key。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from zoujin_llm import (
    PRICES_PATH,
    STATUSES,
    BudgetStop,
    ClaudePrices,
    Ledger,
    ModelCallFailed,
    RateLimited,
    claude_prices,
    mark_playthrough,
    model_tag,
    playthrough,
    read_lines,
    replay_key,
    tier_of,
    use_of,
)
from zoujin_llm.claude import translate

REPO = Path(__file__).resolve().parents[3]


def write(path: Path, *rows: dict[str, Any]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_ledger_caps_by_provider_and_item(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    write(
        path,
        {"kind": "extract", "costUsd": 0.5, "item": "x"},  # 最早的行没有 provider：算 Google
        {"provider": "google", "kind": "reply", "costUsd": 0.25},
        {"provider": "claude", "kind": "judge", "costUsd": 2.0, "item": "x"},
    )
    google = Ledger(path, "google", 1.0)
    claude = Ledger(path, "claude", 2.5, max_item_usd=3.0, item="x")
    assert google.spent_total() == pytest.approx(0.75) and claude.spent_total() == pytest.approx(2.0)
    assert claude.spent_on("x") == pytest.approx(2.5)  # 单项两本账合起来
    google.before(0.25)  # 正好到上限：不停
    with pytest.raises(BudgetStop, match=r"Google 账本已花 \$0\.7500.*总上限 \$1\.00"):
        google.before(0.26)
    with pytest.raises(BudgetStop, match=r"Claude 账本已花 \$2\.0000"):
        claude.before(0.6)
    with pytest.raises(BudgetStop, match=r"「x」已花 \$2\.5000.*单项上限 \$3\.00"):
        Ledger(path, "claude", 100.0, max_item_usd=3.0, item="x").before(0.6)
    Ledger(path, "claude", 100.0, max_item_usd=3.0).before(0.6)  # 没给 item：不判单项


def test_ledger_line_and_use(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "ledger.jsonl"
    Ledger(path, "claude", 1.0, item="b8-probe").add(
        kind="check", model="sonnet-5.5", usage={"inputTokens": 3}, cost=0.123456789
    )
    Ledger(path, "claude", 1.0, use="eval").add(kind="judge", model="opus-5.5", usage={}, cost=0.5)
    first, second = read_lines(path)
    assert set(first) == {"at", "provider", "kind", "model", "usage", "costUsd", "use", "item"}
    assert first["provider"] == "claude" and first["use"] == "product" and first["item"] == "b8-probe"
    assert first["costUsd"] == 0.12345679 and first["at"].endswith("Z") and first["model"] == "sonnet-5.5"
    assert second["use"] == "eval" and "item" not in second
    # 老行没有 use：评审员、AI 玩家算评测，其余算产品
    old_lines = ({"kind": "judge"}, {"kind": "player"}, {"kind": "extract"}, {"kind": "judge", "use": "product"})
    assert [use_of(x) for x in old_lines] == ["eval", "eval", "product", "product"]
    with pytest.raises(ValueError):
        Ledger(path, "openai", 1.0)
    with pytest.raises(ValueError):
        Ledger(path, "claude", 1.0, use="dev")


def test_ledger_time_status_and_playthrough(tmp_path: Path) -> None:
    """B-5 的三列：都可选；评测的一局里记的带 playthroughId，出了那一局就不带；老行照读，上限照算。"""
    path = tmp_path / "ledger.jsonl"
    write(path, {"provider": "claude", "kind": "extract", "costUsd": 0.5, "item": "s5"})  # 老行：没有这三列
    ledger = Ledger(path, "claude", 1.0, max_item_usd=1.0, item="s5")
    with playthrough("pt_01ABC"):
        ledger.record(kind="extract", model="sonnet-5.5", usage={}, cost=0.25, ms=812.6, status="ok")
        with playthrough(None):
            ledger.record(kind="judge", model="opus-5.5", usage={}, cost=0.0, ms=-1, status="error")
    ledger.record(kind="check", model="sonnet-5.5", usage={}, cost=0.1, status="timeout")
    ledger.add(kind="triage", model="haiku-5.5", usage={}, cost=0.0)  # 老写法照旧
    old, mine, outside, after, legacy = read_lines(path)
    assert (mine["ms"], mine["status"], mine["playthroughId"]) == (813, "ok", "pt_01ABC")
    assert (outside["ms"], outside["status"]) == (0, "error") and "playthroughId" not in outside
    assert "ms" not in after and "playthroughId" not in after and after["status"] == "timeout"
    assert not {"ms", "status", "playthroughId"} & set(legacy) and "ms" not in old
    assert ledger.spent_on("s5") == pytest.approx(0.85)
    with pytest.raises(BudgetStop):
        ledger.before(0.2)
    with pytest.raises(ValueError, match="status"):
        ledger.record(kind="x", model="sonnet-5.5", usage={}, cost=0.0, status="slow")
    assert STATUSES == ("ok", "timeout", "bad-output", "error")

    async def opened() -> None:  # 开局时 playthroughId 在协程里才有
        mark_playthrough("pt_02DEF")
        ledger.record(kind="extract", model="sonnet-5.5", usage={}, cost=0.0)

    asyncio.run(opened())
    assert read_lines(path)[-1]["playthroughId"] == "pt_02DEF"
    ledger.record(kind="extract", model="sonnet-5.5", usage={}, cost=0.0)
    assert "playthroughId" not in read_lines(path)[-1]  # 那个事件循环的上下文没带出来


def test_timed_records_time_and_status(tmp_path: Path) -> None:
    """数据评审第 4 题：调用包在 `timed()` 里，耗时和状态自动记（评审员、AI 玩家、叙事者同一个）。"""
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path, "claude", 1.0)
    with ledger.timed(kind="judge", model="opus-5.5", estimate=0.1) as bill:
        bill.done({"inputTokens": 5}, 0.02)
    with pytest.raises(ValueError), ledger.timed(kind="judge", model="opus-5.5", estimate=0.1) as bill:
        bill.done({"inputTokens": 5}, 0.03, ok=False)  # 回来了但不能用：钱照记
        raise ValueError("不合 Schema")
    with pytest.raises(ModelCallFailed), ledger.timed(kind="player", model="sonnet-5.5", estimate=0.1):
        raise ModelCallFailed("Claude HTTP 500")

    async def slow() -> None:
        with ledger.timed(kind="extract", model="sonnet-5.5", estimate=0.07):
            await asyncio.sleep(1)

    async def cut() -> None:
        await asyncio.wait_for(slow(), 0.02)

    with pytest.raises(TimeoutError):
        asyncio.run(cut())
    with pytest.raises(TimeoutError), ledger.timed(kind="judge", model="opus-5.5", estimate=0.05):
        raise TimeoutError  # 同步客户端自己的超时（数据评审 #117）：也按预计记 timeout
    with pytest.raises(BudgetStop), ledger.timed(kind="judge", model="opus-5.5", estimate=5.0):
        pass  # 超上限：不发、不记
    rows = read_lines(path)
    assert [(r["status"], r["costUsd"]) for r in rows] == [
        ("ok", 0.02),
        ("bad-output", 0.03),
        ("error", 0.0),
        ("timeout", 0.07),  # 取消的按预计记
        ("timeout", 0.05),
    ]
    assert all(isinstance(r["ms"], int) for r in rows) and rows[3]["ms"] >= 15


def test_model_tag_and_tier() -> None:
    assert model_tag("test-sonnet-5-5") == "sonnet-5.5" and model_tag("x-HAIKU-5-5-y") == "haiku-5.5"
    assert tier_of("sonnet-5.5") == "sonnet" and tier_of("test-opus-9-9") == "opus"
    for bad in ("gemini-3.8-flash", "sonnet", "x-sonnet-5-5-haiku-4-5", "sonnet-5"):
        with pytest.raises(ValueError):
            model_tag(bad)


def test_prices_cost_and_estimate() -> None:
    prices = claude_prices()
    assert prices is claude_prices()  # 只读一次
    sonnet, haiku = prices.price("sonnet-5.5"), prices.price("test-haiku-5-5")
    assert (sonnet.input, sonnet.output, sonnet.cache_read) == (2, 10, 0.1)
    assert (haiku.input, haiku.cache_read, haiku.tokenizer) == (0.1, 0.01, 1.3)
    usage = {"inputTokens": 1000, "cacheReadTokens": 17000, "cacheWriteTokens": 100, "outputTokens": 300}
    want = (1000 * 2 + 100 * 2 * 1.25 + 17000 * 0.1 + 300 * 10) / 1_000_000
    assert prices.cost("sonnet-5.5", usage) == pytest.approx(want)
    assert prices.cost("sonnet-5.5", usage, batch=True) == pytest.approx(want / 2)
    # 调用前的预计：字数 × 分词倍数，输出按上限
    assert prices.estimate_chars("haiku-5.5", 1000, 100) == pytest.approx((1301 * 0.1 + 100 * 0.5) / 1_000_000)
    assert prices.estimate_chars("sonnet-5.5", 1000, 100) == pytest.approx((1001 * 2 + 100 * 10) / 1_000_000)
    with pytest.raises(ValueError):
        prices.price("gemini-3.8-flash")
    assert ClaudePrices.from_json(json.loads(PRICES_PATH.read_text(encoding="utf-8"))) == prices


def test_only_one_price_list_in_the_repo() -> None:
    found = [p for p in REPO.rglob("claude-prices.json") if ".venv" not in p.parts and "node_modules" not in p.parts]
    assert found == [PRICES_PATH]


def test_replay_key() -> None:
    a, b = {"x": 1, "y": "あ"}, {"y": "あ", "x": 1}
    key = replay_key("claude", "sonnet-5.5", "p1", a)
    assert key == replay_key("claude", "sonnet-5.5", "p1", b)  # 键的顺序不算
    assert key.startswith("claude|sonnet-5.5|p1|") and len(key.split("|")[3]) == 64
    assert key != replay_key("google", "sonnet-5.5", "p1", a) != replay_key("claude", "sonnet-5.5", "p2", a)


def test_sdk_errors_lose_their_message() -> None:
    anthropic = pytest.importorskip("anthropic")  # SDK 只在可选依赖 real 里
    httpx = pytest.importorskip("httpx2")  # SDK 用的 httpx 分支
    secret = "sk-ant-test-marker-0000"
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def status(code: int) -> Any:
        resp = httpx.Response(code, request=req, json={"error": {"message": f"key {secret}"}})
        return anthropic.APIStatusError(f"boom {secret}", response=resp, body=None)

    for code in (429, 529):
        e = translate(status(code))
        assert isinstance(e, RateLimited) and str(code) in str(e) and secret not in str(e)
    e = translate(status(500))
    assert isinstance(e, ModelCallFailed) and "500" in str(e) and secret not in str(e)
    for kind, shown in (("authentication_error", " authentication_error"), (f"key {secret}", "")):
        resp = httpx.Response(400, request=req, json={})
        body = {"type": "error", "error": {"type": kind, "message": f"key {secret}"}}
        e = translate(anthropic.APIStatusError(f"boom {secret}", response=resp, body=body))
        assert str(e) == f"Claude HTTP 400{shown}（消息不记）"  # 错误的类型带上，认不出的不带
    for message, shown in (
        (f"output_config.format.schema: Schema is too complex for compilation. {secret}", "提示 schema-too-complex；"),
        ("thinking.type: adaptive is not supported with this effort", "提示 thinking；"),
        (f"bad key {secret}", ""),
    ):
        resp = httpx.Response(400, request=req, json={})
        body = {"type": "error", "error": {"type": "invalid_request_error", "message": message}}
        e = translate(anthropic.APIStatusError(f"boom {secret}", response=resp, body=body))
        assert str(e) == f"Claude HTTP 400 invalid_request_error（{shown}消息不记）"  # 只带写死的类名
    e = translate(anthropic.APIConnectionError(message=f"down {secret}", request=req))
    assert isinstance(e, ModelCallFailed) and secret not in str(e)


def test_batch_stop_keeps_inflight_cost_and_blocks_other_workers_next_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from zoujin_llm.errors import BatchHalted

    marker = tmp_path / "halted.json"
    monkeypatch.setenv("ZJ_EVAL_BATCH_HALT", str(marker))
    ledger = Ledger(tmp_path / "ledger.jsonl", "google", 5)
    started, stopped = Event(), Event()

    def active_worker() -> None:
        with ledger.timed(kind="reply", model="test", estimate=0.1) as bill:
            started.set()
            assert stopped.wait(5)
            bill.done({"outputTokens": 1}, 0.02)
        with pytest.raises(BatchHalted):
            with ledger.timed(kind="reply", model="test", estimate=0.1):
                pytest.fail("a new paid request must not start")

    def limiting_worker() -> None:
        assert started.wait(5)
        marker.write_text('{"stopType":"RateLimited"}')
        stopped.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(active_worker)
        second = pool.submit(limiting_worker)
        first.result()
        second.result()
    rows = read_lines(ledger.path)
    assert len(rows) == 1 and rows[0]["status"] == "ok" and rows[0]["costUsd"] == 0.02
