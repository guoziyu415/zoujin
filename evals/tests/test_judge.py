"""评审员（data-design 7.3）：校准样本、请求、回放、账本、Batch 和 zoujin-judge 命令。全部用假客户端，不联网。"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from zoujin_evals import calibrate
from zoujin_evals.judge import (
    BudgetStop,
    ClaudeLedger,
    Failed,
    Item,
    Judge,
    RateLimited,
    ReplayStore,
    Reply,
    api_params,
    keyed_request,
    model_tag,
    parse_verdict,
    replay_key,
    threshold,
    user_text,
)
from zoujin_evals.live import LIVE_SWITCH
from zoujin_llm import claude_prices

REPO = Path(__file__).resolve().parents[2]
ITEMS: list[dict[str, Any]] = calibrate.load_items(REPO / "evals" / "judge" / "calibration.jsonl")
PRICES = claude_prices()  # 共用包 zoujin_llm 里的那一份（B-8）
MODEL = "test-opus-9-9"  # 假的模型 ID：认得出档名和版本就行
TAG = "opus-9.9"
USAGE = {"inputTokens": 1000, "outputTokens": 300, "cacheReadTokens": 0, "cacheWriteTokens": 0}


def item(n: int) -> Item:
    return cast(Item, ITEMS[n - 1])


def slice_judge_cases() -> dict[str, dict[str, Any]]:
    out = {}
    for p in sorted((REPO / "evals" / "slice").glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                if "judge" in c.get("expect", {}):
                    out[c["id"]] = c
    return out


# —— 校准样本 ——


def test_calibration_items_cover_every_slice_judge_case_twice() -> None:
    cases = slice_judge_cases()
    assert [x["id"] for x in ITEMS] == [f"J{n:02d}" for n in range(1, 51)]
    assert Counter(x["case"] for x in ITEMS) == {c: 2 for c in cases}
    for x in ITEMS:
        c = cases[x["case"]]
        assert (x["suite"], x["rubric"], x["pass"]) == (
            c["suite"],
            c["expect"]["judge"]["rubric"],
            c["expect"]["judge"]["pass"],
        )
        assert x["label"]["score"] in range(1, 6) and x["label"]["why"]
        assert x["transcript"] and all(set(t) == {"speaker", "text"} and t["text"] for t in x["transcript"])
        assert x["transcript"][0]["speaker"] == "プレイヤー" and x["context"]
    ok = sum(calibrate.passed(x, x["label"]["score"]) for x in ITEMS)
    assert 20 <= ok <= 30  # 过和不过大致各半


def test_zg_sample_is_20_items_half_pass_one_per_case_without_selfharm() -> None:
    zg = [x for x in ITEMS if x["zgSample"]]
    assert len(zg) == calibrate.ZG_N
    assert sum(calibrate.passed(x, x["label"]["score"]) for x in zg) == 10
    assert len({x["case"] for x in zg}) == 20
    assert "E8-004" not in {x["case"] for x in zg}  # 现实危机的两条不给 zg 盲标


# 采用的评审员：opus-5.5、effort low、输出上限 2048（README「10-11 第一次校准」）。模型 ID 只用来算档名，写假的
CALIBRATED_TAG, CALIBRATED_EFFORT, CALIBRATED_MAX_TOKENS = "opus-5.5", "low", 2048


def test_committed_replays_are_the_current_calibration_and_pass_the_bar() -> None:
    """提交的回放正好是现在的 50 条 × 3 次，一致率过线。改了样本、细则或评审员的提示，这里就会少回放：
    在 Mac 上再跑一遍 calibrate（只判少的），新回放一起提交，旧的删掉。"""
    store = ReplayStore(REPO / "evals" / "judge" / "replays")
    todo = [(item(n), s) for s in (1, 2, 3) for n in range(1, len(ITEMS) + 1)]
    keys = {
        replay_key(
            CALIBRATED_TAG, keyed_request(i, effort=CALIBRATED_EFFORT, max_tokens=CALIBRATED_MAX_TOKENS, sample=s)
        )
        for i, s in todo
    }
    assert set(store.records) == keys
    judge = Judge("test-opus-5-5", CALIBRATED_EFFORT, CALIBRATED_MAX_TOKENS, store, PRICES)
    assert judge.tag == CALIBRATED_TAG
    s = calibrate.summarize(ITEMS, [judge.one(i, n) for i, n in todo], len(todo))
    assert s["ok"] and s["rate"] >= calibrate.BAR


# —— 请求 ——


def test_request_has_rubric_context_transcript_and_sample_only_in_the_key() -> None:
    it = item(1)
    text = user_text(it)
    assert it["rubric"] in text and it.get("context", "") in text and "合格线：>=4/5" in text
    assert all(f"{t['speaker']}：{t['text']}" in text for t in it["transcript"])
    r1 = keyed_request(it, effort="low", max_tokens=2048, sample=1)
    r2 = keyed_request(it, effort="low", max_tokens=2048, sample=2)
    assert replay_key(TAG, r1) != replay_key(TAG, r2) != replay_key("opus-9.8", r2)
    assert replay_key(TAG, r1).startswith("claude|opus-9.9|judge-1|")
    p = api_params(MODEL, r1)
    assert "sample" not in json.dumps(p) and "thinking" not in p  # 思考关不掉，不写 thinking
    assert p["output_config"]["effort"] == "low" and p["output_config"]["format"]["type"] == "json_schema"
    assert p["messages"] == [{"role": "user", "content": text}]


def test_parse_verdict() -> None:
    assert parse_verdict('{"reason": "自然", "score": 4}') == (4, "自然")
    for bad in (None, "", "4", '{"score": 6, "reason": "x"}', '{"score": true, "reason": "x"}', '{"score": 3}', "[]"):
        with pytest.raises(ValueError):
            parse_verdict(bad)
    assert threshold(">=4/5") == 4
    with pytest.raises(ValueError):
        threshold("4")


def test_model_tag_keeps_the_id_out_of_the_repo() -> None:
    assert model_tag("x-opus-5-5") == "opus-5.5"
    assert model_tag("x-sonnet-4-5-20990101") == "sonnet-4.5"
    for bad in ("opus", "x-opus-5", "x-opus-5-5-sonnet-5-5", "unknown-1-2"):
        with pytest.raises(ValueError):
            model_tag(bad)


def test_prices_by_tier_batch_and_cache() -> None:
    assert PRICES.cost(MODEL, {"inputTokens": 1_000_000, "outputTokens": 100_000}, batch=False) == pytest.approx(6.0)
    assert PRICES.cost(MODEL, {"inputTokens": 1_000_000, "outputTokens": 100_000}, batch=True) == pytest.approx(3.0)
    assert PRICES.cost(MODEL, {"cacheReadTokens": 1_000_000}, batch=False) == pytest.approx(0.2)
    assert PRICES.cost("test-sonnet", {"cacheReadTokens": 1_000_000}, batch=False) == pytest.approx(0.1)
    assert PRICES.cost("test-haiku", {"cacheReadTokens": 1_000_000}, batch=False) == pytest.approx(0.01)
    assert PRICES.cost(MODEL, {"cacheWriteTokens": 1_000_000}, batch=False) == pytest.approx(5.0)
    for bad in ("unknown-model", "opus-or-sonnet"):
        with pytest.raises(ValueError):
            PRICES.price(bad)
    req = keyed_request(item(1), effort="low", max_tokens=2048, sample=1)
    assert PRICES.estimate(MODEL, req, batch=False) > 2048 * 20 / 1e6  # 输出按上限估


# —— 账本 ——


def test_ledger_caps_claude_total_and_item_across_both_books(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"provider": "google", "kind": "reply", "costUsd": 5.0, "item": "judge-calibration"},
        {"provider": "claude", "kind": "judge", "costUsd": 0.5, "item": "E1-001"},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    led = ClaudeLedger(path, max_total_usd=1.0, max_item_usd=6.0, item="judge-calibration")
    assert led.spent() == (0.5, 5.0)  # 总上限只算 claude 的行；单项两本账合起来
    led.before(0.4)
    with pytest.raises(BudgetStop, match="总上限"):
        led.before(0.6)
    with pytest.raises(BudgetStop, match="单项上限"):
        ClaudeLedger(path, 10.0, 5.5, "judge-calibration").before(0.6)
    led.add(model=MODEL, usage=USAGE, cost=0.01)
    last = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert {k: last[k] for k in ("provider", "kind", "model", "item", "costUsd")} == {
        "provider": "claude",
        "kind": "judge",
        "model": MODEL,
        "item": "judge-calibration",
        "costUsd": 0.01,
    }
    assert "request" not in last and "response" not in last  # 账本不写内容


# —— 假客户端 ——


class FakeClaude:
    """按请求里的对话记录认出是哪一条，回 scores 里给的分（默认数据标的分）。"""

    def __init__(
        self, scores: Mapping[str, int] | None = None, *, stop: str = "end_turn", text: str | None = None
    ) -> None:
        self.by_text = {user_text(cast(Item, x)): x for x in ITEMS}
        self.scores = dict(scores or {})
        self.stop, self.text = stop, text
        self.calls: list[Any] = []
        self.batches: dict[str, list[tuple[str, Any]]] = {}
        self.polls = 0
        self.fail: dict[str, Failed] = {}

    def _reply(self, params: Any) -> Reply:
        x = self.by_text[params["messages"][0]["content"]]
        score = self.scores.get(x["id"], x["label"]["score"])
        text = self.text if self.text is not None else json.dumps({"reason": f"{x['id']} の判定", "score": score})
        return Reply(text, self.stop, dict(USAGE))

    def create(self, params: Any) -> Reply:
        self.calls.append(params)
        return self._reply(params)

    def submit(self, requests: Sequence[tuple[str, Any]]) -> str:
        bid = f"batch-{len(self.batches) + 1}"
        self.batches[bid] = list(requests)
        return bid

    def ended(self, batch_id: str) -> bool:
        self.polls += 1
        return self.polls > 1

    def results(self, batch_id: str) -> Iterator[tuple[str, Reply | Failed]]:
        for cid, params in reversed(self.batches[batch_id]):  # 顺序不定
            yield cid, self.fail.get(cid) or self._reply(params)


class Limited(FakeClaude):
    def create(self, params: Any) -> Reply:
        if self.calls:
            raise RateLimited("429")
        return super().create(params)


def live_judge(tmp_path: Path, fake: FakeClaude, *, cap: float = 10.0) -> Judge:
    led = ClaudeLedger(tmp_path / "ledger.jsonl", cap, cap, "judge-calibration")
    return Judge(MODEL, "low", 2048, ReplayStore(tmp_path / "replays"), PRICES, led, fake, poll=lambda: None)


def ledger_rows(tmp_path: Path) -> list[dict[str, Any]]:
    p = tmp_path / "ledger.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_one_calls_once_then_replays(tmp_path: Path) -> None:
    fake = FakeClaude({"J01": 4})
    j = live_judge(tmp_path, fake)
    v = j.one(item(1))
    assert (v.score, v.passed, v.replayed, v.error) == (4, True, False, None)
    assert v.cost_usd == pytest.approx((1000 * 4 + 300 * 20) / 1e6)
    again = j.one(item(1))
    assert (again.score, again.replayed, again.cost_usd) == (4, True, 0.0) and len(fake.calls) == 1
    j.one(item(1), sample=2)
    assert len(fake.calls) == 2 and len(ledger_rows(tmp_path)) == 2
    assert {(r["provider"], r["kind"], r["use"], r["item"]) for r in ledger_rows(tmp_path)} == {
        ("claude", "judge", "eval", "judge-calibration")
    }
    # 回放和账本里只有档名加版本，没有模型 ID
    written = (tmp_path / "replays" / "judge.jsonl").read_text("utf-8") + (tmp_path / "ledger.jsonl").read_text("utf-8")
    assert MODEL not in written and '"model": "opus-9.9"' in written
    # 换一个进程读同一个回放目录：不用客户端也判得出来
    offline = Judge(MODEL, "low", 2048, ReplayStore(tmp_path / "replays"), PRICES)
    assert offline.one(item(1)).score == 4
    assert offline.one(item(1), sample=3).error == "replay-missing"
    assert (
        Judge("test-opus-9-8", "low", 2048, ReplayStore(tmp_path / "replays"), PRICES).one(item(1)).error
        == "replay-missing"
    )


@pytest.mark.parametrize(
    ("stop", "text", "error"),
    [("refusal", None, "refusal"), ("max_tokens", None, "max_tokens"), ("end_turn", "not json", "bad-json")],
)
def test_failed_verdicts_are_charged_but_not_replayed(tmp_path: Path, stop: str, text: str | None, error: str) -> None:
    fake = FakeClaude(stop=stop, text=text)
    j = live_judge(tmp_path, fake)
    v = j.one(item(2))
    assert v.score is None and v.error is not None and v.error.startswith(error) and v.cost_usd > 0
    assert len(ledger_rows(tmp_path)) == 1 and not (tmp_path / "replays").exists()
    j.one(item(2))
    assert len(fake.calls) == 2  # 下次重判


def test_budget_stop_before_the_call(tmp_path: Path) -> None:
    fake = FakeClaude()
    j = live_judge(tmp_path, fake, cap=0.01)  # 一次最多约 $0.045（输出到上限）
    with pytest.raises(BudgetStop):
        j.one(item(1))
    assert fake.calls == [] and ledger_rows(tmp_path) == []


def test_live_needs_both_ledger_and_client_and_a_known_price() -> None:
    with pytest.raises(ValueError, match="账本"):
        Judge(MODEL, "low", 2048, ReplayStore(Path("/nonexistent")), PRICES, transport=FakeClaude())
    with pytest.raises(ValueError, match="认不出模型"):
        Judge("unknown", "low", 2048, ReplayStore(Path("/nonexistent")), PRICES)
    with pytest.raises(ValueError, match="effort"):
        Judge(MODEL, "none", 2048, ReplayStore(Path("/nonexistent")), PRICES)


def test_replay_store_rejects_a_tampered_record(tmp_path: Path) -> None:
    j = live_judge(tmp_path, FakeClaude())
    j.one(item(1))
    p = tmp_path / "replays" / "judge.jsonl"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["request"]["user"] += "x"
    p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="对不上"):
        ReplayStore(tmp_path / "replays")


# —— Batch ——


def test_batch_skips_replays_maps_results_by_custom_id_and_halves_the_price(tmp_path: Path) -> None:
    fake = FakeClaude({"J03": 2})
    j = live_judge(tmp_path, fake)
    j.one(item(1))  # 已有回放的不交
    fake.fail["J04-s1"] = Failed("expired")
    todo = [(item(n), 1) for n in (1, 2, 3, 4)]
    pending = tmp_path / "out" / "pending-batch.json"
    vs = j.batch(todo, pending)
    assert [v.item for v in vs] == ["J01", "J02", "J03", "J04"]
    assert [v.score for v in vs] == [ITEMS[0]["label"]["score"], ITEMS[1]["label"]["score"], 2, None]
    assert vs[0].replayed and vs[3].error == "expired"
    assert [cid for cid, _ in fake.batches["batch-1"]] == ["J02-s1", "J03-s1", "J04-s1"]
    assert vs[1].cost_usd == pytest.approx((1000 * 4 + 300 * 20) / 1e6 / 2)
    assert not pending.exists() and len(ledger_rows(tmp_path)) == 3  # 一次 + 批里成了的两条


def test_batch_resumes_a_pending_batch_instead_of_resubmitting(tmp_path: Path) -> None:
    fake = FakeClaude()
    j = live_judge(tmp_path, fake)
    todo = [(item(5), 1), (item(6), 1)]

    fake.batches["batch-9"] = [(f"{i['id']}-s1", api_params(MODEL, j.request(i, 1))) for i, _ in todo]
    pending = tmp_path / "pending-batch.json"
    pending.write_text(json.dumps({"batchId": "batch-9", "customIds": ["J05-s1", "J06-s1"]}), encoding="utf-8")
    vs = j.batch(todo, pending)
    assert [v.score for v in vs] == [ITEMS[4]["label"]["score"], ITEMS[5]["label"]["score"]]
    assert list(fake.batches) == ["batch-9"] and not pending.exists()
    pending.write_text(json.dumps({"batchId": "batch-9", "customIds": ["J05-s1"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="不一样"):
        j.batch([(item(7), 1)], pending)


# —— zoujin-judge ——


def run_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: str, fake: FakeClaude | None = None) -> int:
    argv = [*args, "--out", str(tmp_path / "out"), "--replays", str(tmp_path / "replays"), "--model", MODEL]
    a = calibrate.parse(argv)
    return calibrate.calibrate(a, argv, transport=fake)


def report(tmp_path: Path) -> dict[str, Any]:
    r: dict[str, Any] = json.loads((tmp_path / "out" / "calibration.json").read_text(encoding="utf-8"))
    return r


def test_replay_mode_without_replays_reports_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_cli(tmp_path, monkeypatch, "calibrate", "--repeat", "1") == 0
    r = report(tmp_path)
    assert r["judged"] == 0 and r["ok"] is False and r["errors"] == {"replay-missing": 50}


def test_live_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    caps = ("--max-claude-usd", "5", "--max-item-usd", "4")
    monkeypatch.delenv(LIVE_SWITCH, raising=False)
    assert run_cli(tmp_path, monkeypatch, "calibrate", "--mode", "live", *caps) == 2
    monkeypatch.setenv(LIVE_SWITCH, "1")
    assert run_cli(tmp_path, monkeypatch, "calibrate", "--mode", "live", "--max-claude-usd", "5") == 2
    assert "--max-item-usd" in capsys.readouterr().err
    monkeypatch.delenv("ZJ_LEDGER", raising=False)
    assert run_cli(tmp_path, monkeypatch, "calibrate", "--mode", "live", *caps) == 2
    assert "ZJ_LEDGER" in capsys.readouterr().err
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "ledger.jsonl"))
    fake = FakeClaude()
    assert run_cli(tmp_path, monkeypatch, "calibrate", "--mode", "live", *caps, fake=fake) == 0
    out = capsys.readouterr().out
    assert "要调 150 次" in out and "约 $3.60" in out and f"{LIVE_SWITCH}=1 uv run zoujin-judge calibrate" in out
    assert out.rstrip().endswith("--confirm") and fake.calls == []  # 不带 --confirm 不调


def test_live_confirm_runs_and_measures_agreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_SWITCH, "1")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "ledger.jsonl"))
    wrong = {"J01": 2, "J02": 2, "J04": 5}  # J01 判成不过、J04 判成过；J02 分数一样
    fake = FakeClaude(wrong)
    args = (
        "calibrate",
        "--mode",
        "live",
        "--max-claude-usd",
        "20",
        "--max-item-usd",
        "20",
        "--repeat",
        "2",
        "--confirm",
    )
    assert run_cli(tmp_path, monkeypatch, *args, fake=fake) == 0
    r = report(tmp_path)
    assert (r["judged"], r["agree"], r["rate"], r["ok"]) == (100, 96, 0.96, True)
    assert r["exact"] == 96 and r["meanOutputTokens"] == 300 and r["unstable"] == []
    md = (tmp_path / "out" / "calibration.md").read_text(encoding="utf-8")
    assert "# 评审员校准：过" in md and "| J01 | E1-001 | 5 | 2, 2 |" in md and "| J04 |" in md
    assert len(fake.calls) == 100 and len(ledger_rows(tmp_path)) == 100
    # 再跑一遍全是回放，不再调
    assert run_cli(tmp_path, monkeypatch, *args, fake=fake) == 0 and len(fake.calls) == 100


def test_rate_limit_stops_and_keeps_what_was_judged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_SWITCH, "1")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "ledger.jsonl"))
    args = ("calibrate", "--mode", "live", "--max-claude-usd", "20", "--max-item-usd", "20", "--confirm")
    assert run_cli(tmp_path, monkeypatch, *args, fake=Limited()) == 1
    r = report(tmp_path)
    assert r["judged"] == 1 and "429" in r["stopped"] and r["ok"] is False


def test_agree_with_zg(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    zg = {x["id"]: {"score": x["label"]["score"]} for x in ITEMS if x["zgSample"]}
    first, second, third = sorted(zg)[:3]
    zg[first] = {"score": 1 if zg[first]["score"] >= 4 else 5, "note": "不自然"}  # 过不过不一样
    zg[second] = {"score": max(1, zg[second]["score"] - 1) if zg[second]["score"] != 4 else 5}  # 只差 1 分
    path = tmp_path / "labels-zg.json"
    path.write_text(json.dumps({"labels": zg}), encoding="utf-8")
    a = calibrate.parse(["agree", "--zg", str(path), "--out", str(tmp_path / "out")])
    assert calibrate.agree(a) == 0
    out = capsys.readouterr().out
    assert "# zg 盲标和数据的标注：过" in out and "过 / 不过一样：19/20" in out and "不自然" in out
    del zg[third]
    path.write_text(json.dumps({"labels": zg}), encoding="utf-8")
    assert calibrate.agree(a) == 2
