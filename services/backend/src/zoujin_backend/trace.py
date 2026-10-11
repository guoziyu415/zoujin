"""Span（data-design 第 8 节）：叙事者每次调文本模型一个 Span，只带 ID、计数、规则名和耗时，不带原话、摘要和理由的文字。

B-2 先记进内存和日志（`zoujin.trace`，一行一个 Span）；接 Cloud Trace（OpenTelemetry）是部署的卡，属性名照这里。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("zoujin.trace")

# 只有这些属性能进 Span（值只能是数、布尔、ID 和规则名这样的短字符串，或它们的列表）
ATTRS = frozenset(
    {
        "playthrough_id",
        "turn_id",
        "trace_id",
        "character",
        "input_mode",
        "provider",
        "model",
        "prompt_version",
        "world_model_version",
        "candidate_count",
        "status",
        "failed_rules",
        "attempt",
        "mode",
        "tokens_in",
        "tokens_out",
        "tokens_cached",
        "tokens_thought",
        "cost_usd",
        "duration_ms",
        "route",
        "action_kind",  # B-3：动作的 kind、演的固定演出、打算成没成行、第几次
        "piece_id",
        "accepted",
        "tries",
        "turn_kind",  # B-4：作废的一轮的 kind、到了哪一步；意图确认的回答、谁答的、结果、这一局第几次
        "stage",
        "answer",
        "by",
        "result",
        "nth",
        "kind",  # B-12：输出侧监控命中的种类（spoiler / harmful）、事实 ID、RAI 类别、这一句让会话重建了没有
        "fact",
        "category",
        "rebuild",
        "reason",  # B-10：Live 会话为什么开（warm / switch / rebuild / rebuild_turns / rebuild_goaway / arrival）
        "prompt_chars",
        "notes",
        "first_audio_ms",
        "audio_s",
        "session_audio_s",
        "session_turn",
        "gap_ms",  # B-11：断线到重连、接手了几条会话、带回几轮最近对话、哪一种、是不是重连、会话是不是接上的
        "carried",
        "recent_turns",
        "resume_kind",
        "reconnect",
        "reused",
        "usage_estimated",  # #111 数据评审：live.turn 的用量是不是按 0.01 美元估的、玩家打断没有、人物字幕的来源
        "interrupted",
        "transcript_source",
    }
)


@dataclass
class Span:
    name: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def set(self, **attrs: Any) -> None:
        for k, v in attrs.items():
            if k not in ATTRS:
                raise KeyError(f"Span 不收这个属性：{k}")
            self.attrs[k] = v


@dataclass
class Tracer:
    """一个进程一个；`spans` 留最近的（测试看）。"""

    keep: int = 1000
    spans: list[Span] = field(default_factory=list)

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[Span]:
        s = Span(name)
        s.set(**attrs)
        start = time.perf_counter()
        try:
            yield s
        finally:
            s.set(duration_ms=round((time.perf_counter() - start) * 1000, 1))
            self.spans.append(s)
            del self.spans[: -self.keep]
            log.info("%s %s", name, json.dumps(s.attrs, ensure_ascii=False, sort_keys=True))

    def named(self, name: str) -> list[Mapping[str, Any]]:
        return [s.attrs for s in self.spans if s.name == name]
