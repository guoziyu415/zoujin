"""Eval-only observation of how calls finally ended; does not change the production deadlines, retries or model input.

評価専用の、呼び出しの最終状態の観測。本番のタイムアウト、再試行、モデル入力は変えない。
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from zoujin_llm import Stop

from zoujin_backend.models.text import TextResult
from zoujin_backend.narrator.pipeline import CallFailed, Pipeline, Spend
from zoujin_backend.trace import Span, Tracer


def ending_observations(tracer: Tracer) -> dict[str, Any]:
    """Keep the rule names and attempt status of the ending validation; never the text, prompts, model IDs or player
    input.

    エンディング検証のルール名と試行の状態を保存し、文章、プロンプト、モデル ID、プレイヤーの入力は保存しない。
    """
    names = {"narrator.ending", "narrator.ending-check", "narrator.ending.done", "narrator.ending.unclassified"}
    keys = {"attempt", "status", "failed_rules", "calls", "template", "reason"}
    spans = [
        {"name": s.name, **{k: v for k, v in s.attrs.items() if k in keys}} for s in tracer.spans if s.name in names
    ]
    return {"coverage": "captured" if spans else "not-recorded", "spans": spans}


@dataclass
class CallTracer(Tracer):
    parent: Tracer = field(default_factory=Tracer)

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[Span]:
        # Each logical call has its own collector; concurrent candidates do not rely on neighbouring logs to guess
        # pairs.
        # 論理的な呼び出しごとに専用のコレクターを持つ。並行する候補は、隣のログからペアを推測することに頼らない。
        with self.parent.span(name, **attrs) as span:
            try:
                yield span
            finally:
                self.spans.append(span)


@dataclass
class ObservedPipeline(Pipeline):
    observations: list[dict[str, Any]] = field(default_factory=list)

    async def call(
        self,
        kind: str,
        request: dict[str, Any],
        spend: Spend,
        *,
        span: Mapping[str, Any],
        extra: Callable[[dict[str, Any]], Mapping[str, Any] | None] | None = None,
    ) -> TextResult:
        record: dict[str, Any] = {
            "callId": len(self.observations) + 1,
            "kind": kind,
            "status": "running",
            "attempts": [],
        }
        self.observations.append(record)
        captured = CallTracer(parent=self.tracer)
        pipeline = Pipeline(self.text, self.schemas, self.ids, captured, self.deadlines, self.on_rate_limit)
        try:
            result = await pipeline.call(kind, request, spend, span=span, extra=extra)
        except CallFailed:
            record["status"] = "failed"
            raise
        except Stop:
            record["status"] = "stopped"
            raise
        except BaseException:
            record["status"] = "interrupted"
            raise
        else:
            record["status"] = "ok"
            return result
        finally:
            record["attempts"] = [
                {"attempt": s.attrs["attempt"], "status": s.attrs.get("status", "interrupted")} for s in captured.spans
            ]
