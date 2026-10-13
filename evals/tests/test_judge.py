"""Judge (data-design 7.3): calibration samples, requests, replays, the ledger, Batch and the zoujin-judge command. All
with a fake client, no network.

審査員（data-design 7.3）：キャリブレーションサンプル、リクエスト、リプレイ、台帳、Batch、zoujin-judge コマンド。
すべて偽クライアントを使い、ネットワークには接続しない。
"""

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
PRICES = claude_prices()  # the one in the shared package zoujin_llm (B-8) / 共有パッケージ zoujin_llm にあるもの（B-8）
# a fake model ID: it only needs a recognisable tier name and version
# 偽のモデル ID：ティア名とバージョンが分かればよい
MODEL = "test-opus-9-9"
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


# —— Calibration samples / キャリブレーションサンプル ——


def test_calibration_items_cover_every_slice_judge_case_twice() -> None:
    cases = slice_judge_cases()
    # J43 and J44 (E8-004) were removed: the character does not answer in the turn that shows the card, so that case
    # is no longer judged (api-contract 3.12); the numbering is not reshuffled.
    # J43、J44（E8-004）は削除した：カードを出すターンでは人物が返答しないので、このケースはもう採点しない
    # （api-contract 3.12）。番号は振り直さない。
    assert [x["id"] for x in ITEMS] == [f"J{n:02d}" for n in range(1, 51) if n not in (43, 44)]
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
    assert 20 <= ok <= 30  # roughly half pass, half fail / 合格と不合格がおおよそ半々


def test_zg_sample_is_20_items_half_pass_one_per_case_without_selfharm() -> None:
    zg = [x for x in ITEMS if x["zgSample"]]
    assert len(zg) == calibrate.ZG_N
    assert sum(calibrate.passed(x, x["label"]["score"]) for x in zg) == 10
    assert len({x["case"] for x in zg}) == 20
    # the two real-crisis items are not given to zg for blind labelling
    # 現実の危機の 2 件は zg のブラインドラベルに出さない
    assert "E8-004" not in {x["case"] for x in zg}


# The adopted judge: opus-5.5, effort low, output cap 2048 (README "first calibration on 10-11"). The model ID is used
# only to derive the tier name, so a fake one is written.
# 採用した審査員：opus-5.5、effort low、出力上限 2048（README「10-11 の初回キャリブレーション」）。モデル ID は
# ティア名の算出にしか使わないので、偽のものを書く。
CALIBRATED_TAG, CALIBRATED_EFFORT, CALIBRATED_MAX_TOKENS = "opus-5.5", "low", 2048


def test_committed_replays_are_the_current_calibration_and_pass_the_bar() -> None:
    """The committed replays are exactly the current 48 items × 3 runs, and the agreement rate meets the bar. If the
    samples, the rubrics or the judge's prompt change, replays go missing here: run calibrate again on the Mac (it
    judges only the missing ones), commit the new replays together and delete the old ones.

    コミットしたリプレイはちょうど現在の 48 件 × 3 回で、一致率は基準を満たす。サンプル、評価基準、審査員のプロンプトを
    変えるとここでリプレイが不足する：Mac で calibrate を再実行し（不足分だけを採点する）、新しいリプレイを一緒に
    コミットし、古いものは削除する。
    """
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


# —— Requests / リクエスト ——


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
    # thinking cannot be turned off, so no thinking field / 思考はオフにできないので thinking は書かない
    assert "sample" not in json.dumps(p) and "thinking" not in p
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
    # output is estimated at the cap / 出力は上限で見積もる
    assert PRICES.estimate(MODEL, req, batch=False) > 2048 * 20 / 1e6


# —— Ledger / 台帳 ——


def test_ledger_caps_claude_total_and_item_across_both_books(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"provider": "google", "kind": "reply", "costUsd": 5.0, "item": "judge-calibration"},
        {"provider": "claude", "kind": "judge", "costUsd": 0.5, "item": "E1-001"},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    led = ClaudeLedger(path, max_total_usd=1.0, max_item_usd=6.0, item="judge-calibration")
    # the total cap counts only claude rows; the per-item cap combines both ledgers
    # 総上限は claude の行だけを数え、項目ごとの上限は 2 つの台帳を合算する
    assert led.spent() == (0.5, 5.0)
    led.before(0.4)
    # the message names the cap that was hit: the total cap $1.00 / メッセージは超えた上限を示す：総上限 $1.00
    with pytest.raises(BudgetStop, match=r"\$1\.00"):
        led.before(0.6)
    # the per-item cap $5.50 / 項目ごとの上限 $5.50
    with pytest.raises(BudgetStop, match=r"\$5\.50"):
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
    # the ledger records no content / 台帳には内容を書かない
    assert "request" not in last and "response" not in last


# —— Fake client / 偽クライアント ——


class FakeClaude:
    """Recognises the item by the transcript in the request and returns the score given in scores (by default the
    data's label).

    リクエスト内の会話記録でどの項目かを判別し、scores で与えた点数（デフォルトはデータのラベルの点数）を返す。
    """

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
        for cid, params in reversed(self.batches[batch_id]):  # in no particular order / 順序は不定
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
    # replays and the ledger hold only the tier name plus version, never the model ID
    # リプレイと台帳にはティア名とバージョンだけがあり、モデル ID はない
    written = (tmp_path / "replays" / "judge.jsonl").read_text("utf-8") + (tmp_path / "ledger.jsonl").read_text("utf-8")
    assert MODEL not in written and '"model": "opus-9.9"' in written
    # another process reading the same replay directory can judge without a client
    # 別のプロセスが同じリプレイのディレクトリを読めば、クライアントなしで採点できる
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
    assert len(fake.calls) == 2  # judged again next time / 次回また採点する


def test_budget_stop_before_the_call(tmp_path: Path) -> None:
    fake = FakeClaude()
    # at most about $0.045 per call (output up to the cap) / 1 回あたり最大約 $0.045（出力が上限まで）
    j = live_judge(tmp_path, fake, cap=0.01)
    with pytest.raises(BudgetStop):
        j.one(item(1))
    assert fake.calls == [] and ledger_rows(tmp_path) == []


def test_live_needs_both_ledger_and_client_and_a_known_price() -> None:
    with pytest.raises(ValueError, match="ledger"):
        Judge(MODEL, "low", 2048, ReplayStore(Path("/nonexistent")), PRICES, transport=FakeClaude())
    # zoujin_llm refuses a model whose price tier it cannot recognise
    # zoujin_llm は価格ティアの分からないモデルを拒否する
    with pytest.raises(ValueError, match="'unknown'"):
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
    with pytest.raises(ValueError, match="does not match"):
        ReplayStore(tmp_path / "replays")


# —— Batch ——


def test_batch_skips_replays_maps_results_by_custom_id_and_halves_the_price(tmp_path: Path) -> None:
    fake = FakeClaude({"J03": 2})
    j = live_judge(tmp_path, fake)
    j.one(item(1))  # items that already have a replay are not submitted / リプレイがあるものは提出しない
    fake.fail["J04-s1"] = Failed("expired")
    todo = [(item(n), 1) for n in (1, 2, 3, 4)]
    pending = tmp_path / "out" / "pending-batch.json"
    vs = j.batch(todo, pending)
    assert [v.item for v in vs] == ["J01", "J02", "J03", "J04"]
    assert [v.score for v in vs] == [ITEMS[0]["label"]["score"], ITEMS[1]["label"]["score"], 2, None]
    assert vs[0].replayed and vs[3].error == "expired"
    assert [cid for cid, _ in fake.batches["batch-1"]] == ["J02-s1", "J03-s1", "J04-s1"]
    assert vs[1].cost_usd == pytest.approx((1000 * 4 + 300 * 20) / 1e6 / 2)
    # one call + the two that succeeded in the batch / 1 回 + バッチで成功した 2 件
    assert not pending.exists() and len(ledger_rows(tmp_path)) == 3


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
    with pytest.raises(ValueError, match="differs"):
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
    assert r["judged"] == 0 and r["ok"] is False and r["errors"] == {"replay-missing": 48}


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
    assert "needs 144 calls" in out and "about $1.44" in out
    assert f"{LIVE_SWITCH}=1 uv run zoujin-judge calibrate" in out
    # no call without --confirm / --confirm なしでは呼ばない
    assert out.rstrip().endswith("--confirm") and fake.calls == []


def test_live_confirm_runs_and_measures_agreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_SWITCH, "1")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "ledger.jsonl"))
    # J01 judged as fail, J04 as pass; J02 has the same score / J01 は不合格、J04 は合格と判定。J02 は同じ点数
    wrong = {"J01": 2, "J02": 2, "J04": 5}
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
    assert (r["judged"], r["agree"], r["rate"], r["ok"]) == (96, 92, 0.9583, True)
    assert r["exact"] == 92 and r["meanOutputTokens"] == 300 and r["unstable"] == []
    md = (tmp_path / "out" / "calibration.md").read_text(encoding="utf-8")
    assert "# Judge calibration: passed / 審査員のキャリブレーション：合格" in md
    assert "| J01 | E1-001 | 5 | 2, 2 |" in md and "| J04 |" in md
    assert len(fake.calls) == 96 and len(ledger_rows(tmp_path)) == 96
    # a rerun is all replays and calls nothing again / 再実行はすべてリプレイで、もう呼ばない
    assert run_cli(tmp_path, monkeypatch, *args, fake=fake) == 0 and len(fake.calls) == 96


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
    # pass / fail differs / 合格 / 不合格が異なる
    zg[first] = {"score": 1 if zg[first]["score"] >= 4 else 5, "note": "不自然"}
    # off by only 1 point / 1 点だけ違う
    zg[second] = {"score": max(1, zg[second]["score"] - 1) if zg[second]["score"] != 4 else 5}
    path = tmp_path / "labels-zg.json"
    path.write_text(json.dumps({"labels": zg}), encoding="utf-8")
    a = calibrate.parse(["agree", "--zg", str(path), "--out", str(tmp_path / "out")])
    assert calibrate.agree(a) == 0
    out = capsys.readouterr().out
    assert "# zg's blind labels vs the data's labels: passed" in out
    assert "Same pass / fail: 19/20" in out and "不自然" in out
    del zg[third]
    path.write_text(json.dumps({"labels": zg}), encoding="utf-8")
    assert calibrate.agree(a) == 2
