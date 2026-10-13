"""评测专用的调用终态观察；不改正式时限、重试或模型输入。"""

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
    """保存结局校验的规则名和尝试状态，不保存文本、提示、模型 ID 或玩家输入。"""
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
        # 每次逻辑调用有自己的收集器；并发候选不会依靠相邻日志猜配对。
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
