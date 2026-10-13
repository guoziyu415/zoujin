"""The eval observer must associate retries by logical request, without changing production input, fallbacks or
spend.

評価のオブザーバーは再試行を論理的なリクエストごとに関連づけなければならず、本番の入力、フォールバック、費用は変えない。
"""

import asyncio
from typing import Any

import pytest
from zoujin_backend.eval_diagnostics import ObservedPipeline, ending_observations
from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import FakeText, ModelCallFailed, TextResult
from zoujin_backend.narrator.pipeline import CallFailed, Spend
from zoujin_backend.trace import Tracer
from zoujin_llm import RateLimited

from .conftest import SCHEMAS


def test_ending_rejections_and_retry_are_preserved_without_text_or_model_ids() -> None:
    tracer = Tracer()
    assert ending_observations(tracer) == {"coverage": "not-recorded", "spans": []}
    with tracer.span("narrator.ending", attempt=1, status="rejected", failed_rules=["length"], model="private"):
        pass
    with tracer.span("narrator.ending", attempt=2, status="ok", failed_rules=[]):
        pass
    with tracer.span("narrator.ending-check", status="rejected"):
        pass
    with tracer.span("narrator.ending.done", calls=2, template=True, failed_rules=["coherence"]):
        pass
    observed = ending_observations(tracer)
    assert observed["coverage"] == "captured"
    assert observed["spans"][0] == {
        "name": "narrator.ending",
        "attempt": 1,
        "status": "rejected",
        "failed_rules": ["length"],
    }
    assert observed["spans"][-1]["failed_rules"] == ["coherence"]
    assert observed["spans"][-1]["template"] is True
    assert len(observed["spans"]) == 4
    assert all("model" not in s for s in observed["spans"])


class Failing(FakeText):
    attempts = 0

    async def call(self, kind: str, request: Any) -> TextResult:
        self.attempts += 1
        if self.attempts == 1:
            raise ModelCallFailed("once")
        return await super().call(kind, request)


def test_successful_retry_is_one_recovered_logical_call() -> None:
    text = Failing()
    observed = ObservedPipeline(text, SCHEMAS, IdGen(seed=1))
    spend = Spend()
    result = asyncio.run(observed.call("triage", {}, spend, span={}))
    assert result.output == {"route": "maybe"}
    assert observed.observations == [
        {
            "callId": 1,
            "kind": "triage",
            "status": "ok",
            "attempts": [
                {"attempt": 1, "status": "error"},
                {"attempt": 2, "status": "ok"},
            ],
        }
    ]
    assert spend.usd["triage"] == result.cost_usd


def test_terminal_failure_and_rate_limit_are_not_recovered() -> None:
    class AlwaysFails(FakeText):
        async def call(self, kind: str, request: Any) -> TextResult:
            raise ModelCallFailed("failed")

    p = ObservedPipeline(AlwaysFails(), SCHEMAS, IdGen(seed=1))
    with pytest.raises(CallFailed):
        asyncio.run(p.call("triage", {}, Spend(), span={}))
    assert p.observations[0]["status"] == "failed"
    assert len(p.observations[0]["attempts"]) == 2

    class Limited(FakeText):
        async def call(self, kind: str, request: Any) -> TextResult:
            raise RateLimited("stop")

    p.text = Limited()
    with pytest.raises(RateLimited):
        asyncio.run(p.call("triage", {}, Spend(), span={}))
    assert p.observations[1]["status"] == "stopped"
    assert len(p.observations[1]["attempts"]) == 1


def test_rate_limit_diagnostics_exclude_arbitrary_header_values() -> None:
    assert RateLimited("stop", provider="google", status=429, retry_after="30").diagnostics == {
        "provider": "google",
        "httpStatus": 429,
        "retryAfterSeconds": 30,
    }
    assert RateLimited("stop", provider="secret", status=418, retry_after="secret").diagnostics == {}
