"""`zoujin-probe`（B-8 验收第 6 组）：不带 --confirm 只打印；带了串行跑，第一个 429、529 就停，到上限就停，
结果只有数字。

真跑的那几条用 `httpx2.MockTransport` 接住 SDK 的流式请求（SSE），不联网；CI 里没装可选依赖 real 的任务跳过。
请求取 CI 的回放（假模型录的、为测试写的台词）。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from zoujin_backend import probe
from zoujin_backend.config import REPO
from zoujin_backend.models.prompts import PROMPTS

Json = Any

KEY = "sk-ant-test-marker-0000"
ENV = {
    "ANTHROPIC_API_KEY": KEY,
    "ZJ_CLAUDE_HAIKU": "test-haiku-5-5-idmark",
    "ZJ_CLAUDE_SONNET": "test-sonnet-5-5-idmark",
}
FIXTURE = REPO / "fixtures" / "model-replays" / "b0-minimal.jsonl"
RECORDS = [json.loads(x) for x in FIXTURE.read_text(encoding="utf-8").splitlines()]
WORDS = ["宿", "老爺", "羊"]  # 请求和回答里的字：结果文件里不该有


@pytest.fixture
def requests(tmp_path: Path) -> Path:
    d = tmp_path / "requests"
    d.mkdir()
    (d / "b0.jsonl").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    return d


def test_load_takes_only_claude_kinds_once(requests: Path) -> None:
    got = probe.load(requests)
    assert list(got) == ["triage", "extract", "check", "rewrite"]  # reply 留在 Google，不量
    assert [len(v) for v in got.values()] == [1, 1, 1, 2]  # 同样的请求只算一个
    picked = probe.pick(got, 3)
    assert [k for k, _ in picked].count("rewrite") == 3 and len(picked) == 12


def test_ending_requests_print_an_estimate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """B-9 验收第 13 条：切片两条路的结局请求（b9-ending.jsonl）各 10 次，不带 --confirm 只打印估价。"""
    d = tmp_path / "requests"
    d.mkdir()
    (d / "b9.jsonl").write_text((FIXTURE.parent / "b9-ending.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    assert [len(v) for v in probe.load(d).values()] == [2]
    argv = ["--requests", str(d), "--out", str(tmp_path / "out"), "--kind", "ending", "--per-kind", "20"]
    assert probe.main([*argv, "--max-item-usd", "1", "--max-claude-usd", "100"], env=ENV) == 0
    printed = capsys.readouterr().out
    assert "小测：20 次调用" in printed and "预计花费" in printed and not (tmp_path / "out").exists()


def test_holdout_is_never_read(tmp_path: Path) -> None:
    d = tmp_path / "data" / "evals" / "holdout" / "requests"
    d.mkdir(parents=True)
    (d / "x.jsonl").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    assert probe.main(["--requests", str(d), "--out", str(tmp_path / "out")], env=ENV) == 2


def test_without_confirm_it_only_prints(requests: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    argv = ["--requests", str(requests), "--out", str(out), "--per-kind", "5", "--max-item-usd", "2"]
    env = ENV | {"ZJ_LEDGER": str(tmp_path / "ledger.jsonl")}
    assert probe.main([*argv, "--max-claude-usd", "100"], env=env) == 0  # 没带 --confirm
    printed = capsys.readouterr().out
    assert "小测：20 次调用" in printed and "预计花费" in printed and "只打印，不调用：没带 --confirm" in printed
    (cmd,) = [x for x in printed.splitlines() if x.startswith("命令：")]
    assert (
        "uv run --all-packages --extra real zoujin-probe" in cmd
        and cmd.endswith("--confirm")
        and cmd.count("--confirm") == 1
    )
    assert "sonnet-5.5" in printed and KEY not in printed and "idmark" not in printed
    assert probe.main([*argv, "--confirm"], env=ENV) == 0  # 少账本、少总上限：也只打印
    printed = capsys.readouterr().out
    assert "没设 ZJ_LEDGER" in printed and "少 --max-claude-usd" in printed
    assert not out.exists() and not (tmp_path / "ledger.jsonl").exists()
    only = [*argv, "--max-claude-usd", "100", "--kind", "check", "--kind", "rewrite"]
    assert probe.main(only, env=env) == 0  # 只补跑某几种
    printed = capsys.readouterr().out
    assert "小测：10 次调用" in printed and "  check " in printed and "  triage " not in printed


# —— 真跑（假的 SSE） ——


def kind_of(body: Json) -> str:
    return next(k for k, p in PROMPTS.items() if p.text == body["system"][-1]["text"])


def sse(output: Json, thinking: bool) -> bytes:
    text = json.dumps(output, ensure_ascii=False)
    events: list[Json] = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "x",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 900,
                    "output_tokens": 1,
                    "cache_read_input_tokens": 17000,
                    "cache_creation_input_tokens": 0,
                },
            },
        }
    ]
    i = 0
    if thinking:
        events += [
            {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "考え中"}},
            {"type": "content_block_stop", "index": 0},
        ]
        i = 1
    events += [
        {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": text[:5]}},
        {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": text[5:]}},
        {"type": "content_block_stop", "index": i},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 200, "output_tokens_details": {"thinking_tokens": 40 if thinking else 0}},
        },
        {"type": "message_stop"},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode()


def answering(fail: Callable[[str, int], int | None] = lambda kind, n: None) -> Callable[[Any], Any]:
    httpx = pytest.importorskip("httpx2")
    responses = {r["kind"]: r["response"] for r in RECORDS}
    seen: dict[str, int] = {}

    def handler(r: Any) -> Any:
        assert r.headers["x-api-key"] == KEY
        body = json.loads(r.content)
        assert body["stream"] is True
        kind = kind_of(body)
        seen[kind] = seen.get(kind, 0) + 1
        code = fail(kind, seen[kind])
        if code is not None:
            return httpx.Response(code, json={"type": "error", "error": {"type": "x", "message": f"key {KEY}"}})
        out = responses[kind]
        return httpx.Response(200, content=sse(out, kind != "triage"), headers={"content-type": "text/event-stream"})

    return handler


def run_probe(
    tmp_path: Path, requests: Path, monkeypatch: pytest.MonkeyPatch, handler: Callable[[Any], Any], item_usd: str = "2"
) -> tuple[int, Path]:
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)  # SDK 自己从环境变量读 Key
    sdk = anthropic.AsyncAnthropic(max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    real = probe.Timed
    monkeypatch.setattr(probe, "Timed", lambda: real(sdk))
    out = tmp_path / "out"
    argv = ["--requests", str(requests), "--out", str(out), "--per-kind", "3", "--max-item-usd", item_usd]
    env = ENV | {"ZJ_LEDGER": str(tmp_path / "ledger.jsonl")}
    return probe.main([*argv, "--max-claude-usd", "100", "--confirm"], env=env), out


def test_a_run_writes_only_numbers(
    tmp_path: Path, requests: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run_probe(tmp_path, requests, monkeypatch, answering())
    assert code == 0
    rows = [json.loads(x) for x in (out / probe.ROWS).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 12 and {r["status"] for r in rows} == {"ok"}
    assert all(r["totalMs"] >= r["firstTextMs"] >= 0 for r in rows)
    assert rows[0]["usage"] == {
        "inputTokens": 900,
        "cacheReadTokens": 17000,
        "cacheWriteTokens": 0,
        "outputTokens": 200,
        "thinkingTokens": 0,
    }
    summary = json.loads((out / probe.SUMMARY).read_text(encoding="utf-8"))
    check = summary["kinds"]["check"]
    assert check["model"] == "sonnet-5.5" and check["calls"] == 3 and check["thinkingTokens"] == 40
    assert set(check["totalMs"]) == {"p50", "p95", "max"} and summary["meta"]["stoppedBy"] is None
    assert summary["meta"]["requests"] == "requests"  # 只写目录名，不写 Mac 上的路径
    ledger = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(ledger) == 12 and {(x["provider"], x["item"], x["use"]) for x in ledger} == {
        ("claude", "b8-probe", "product")
    }
    assert summary["costUsd"] == pytest.approx(sum(x["costUsd"] for x in ledger), abs=1e-6)
    written = (out / probe.ROWS).read_text(encoding="utf-8") + (out / probe.SUMMARY).read_text(encoding="utf-8")
    for word in (KEY, "idmark", *WORDS):
        assert word not in written and word not in capsys.readouterr().out, word


@pytest.mark.parametrize("code", [429, 529])
def test_the_first_limit_stops_the_run(
    code: int, tmp_path: Path, requests: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, out = run_probe(
        tmp_path, requests, monkeypatch, answering(lambda kind, n: code if kind == "extract" and n == 2 else None)
    )
    assert exit_code == 3
    rows = [json.loads(x) for x in (out / probe.ROWS).read_text(encoding="utf-8").splitlines()]
    assert [r["kind"] for r in rows] == ["triage"] * 3 + ["extract"]  # 第二次提取 429：停下，后面的都不调
    summary = json.loads((out / probe.SUMMARY).read_text(encoding="utf-8"))
    assert summary["meta"]["stoppedBy"] == "RateLimited"
    assert KEY not in capsys.readouterr().out


def test_other_errors_skip_that_kind(tmp_path: Path, requests: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, out = run_probe(tmp_path, requests, monkeypatch, answering(lambda kind, n: 400 if kind == "check" else None))
    assert code == 0
    rows = [json.loads(x) for x in (out / probe.ROWS).read_text(encoding="utf-8").splitlines()]
    assert [(r["kind"], r["status"]) for r in rows if r["kind"] == "check"] == [("check", "error")]
    assert [r["kind"] for r in rows].count("rewrite") == 3


def test_the_item_cap_stops_the_run(tmp_path: Path, requests: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, out = run_probe(tmp_path, requests, monkeypatch, answering(), item_usd="0.05")
    assert code == 3
    summary = json.loads((out / probe.SUMMARY).read_text(encoding="utf-8"))
    assert summary["meta"]["stoppedBy"] == "BudgetStop" and summary["costUsd"] <= 0.05
