"""Spans (data-design section 8): one Span each time the narrator calls the text model, carrying only IDs, counts, rule
names and durations, never the original words or the text of summaries and reasons.

B-2 first records them in memory and in the log (`zoujin.trace`, one Span per line); hooking up Cloud Trace
(OpenTelemetry) is the deployment card, and the attribute names follow this file.

Span（data-design 第 8 節）：ナレーターがテキストモデルを呼ぶたびに Span を 1 つ作り、ID、件数、規則名、所要時間だけを
持たせ、元の発言、要約や理由の文章は持たせない。

B-2 ではまずメモリとログ（`zoujin.trace`、1 行に 1 Span）に記録する。Cloud Trace（OpenTelemetry）への接続はデプロイの
カードで、属性名はここに従う。
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

# Only these attributes may go into a Span (values may only be numbers, booleans, short strings such as IDs and rule
# names, or lists of them)
# Span に入れられるのはこれらの属性だけ（値は数値、真偽値、ID や規則名のような短い文字列、またはそれらのリストのみ）
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
        # B-3: the action's kind, the set piece played, whether the plan went ahead, which try
        # B-3：アクションの kind、演じた固定演出、プランが実行されたか、何回目か
        "action_kind",
        "piece_id",
        "accepted",
        "tries",
        # B-4: the kind of a voided turn and how far it got; for intent confirmation, the answer, who answered, the
        # result, and which time in this playthrough
        # B-4：無効にしたターンの kind とどのステップまで進んだか。意図確認の回答、誰が答えたか、結果、
        # この周回で何回目か
        "turn_kind",
        "stage",
        "answer",
        "by",
        "result",
        "nth",
        # B-12: the kind of an output-side monitor hit (spoiler / harmful), fact IDs, RAI category, whether this line
        # made the session rebuild
        # B-12：出力側の監視でヒットした種類（spoiler / harmful）、事実 ID、RAI カテゴリ、
        # この一文でセッションを再構築したか
        "kind",
        "fact_ids",
        "category",
        "rebuild",
        # B-9: ending trigger, category, template or not, calls
        # B-9：エンディングの契機、分類、テンプレートか、呼び出し回数
        "trigger",
        "outcome",
        "template",
        "calls",
        # B-14: when the budget tier changes (budget), and the degradation reason
        # B-14：予算ティアが変わったとき（budget）、劣化の理由
        "run_cost_jpy_so_far",
        "tier",
        "degraded",
        # B-5: the persona ID and seed of a simulated playthrough (the Span of a playthrough start at the eval entry)
        # B-5：模擬周回のペルソナ ID、シード（評価の入口での周回開始の Span）
        "eval.persona",
        "eval.seed",
        # B-10: why a Live session was opened (warm / switch / rebuild / rebuild_turns / rebuild_goaway / arrival)
        # B-10：Live セッションを開いた理由（warm / switch / rebuild / rebuild_turns / rebuild_goaway / arrival）
        "reason",
        "prompt_chars",
        "notes",
        "first_audio_ms",
        "audio_s",
        "session_audio_s",
        "session_turn",
        # B-11: from disconnect to reconnect, how many sessions were taken over, how many recent turns were brought
        # back, which kind, whether it was a reconnect, whether the session was resumed
        # B-11：切断から再接続まで、引き継いだセッション数、持ち帰った直近の会話のターン数、どの種類か、再接続か、
        # セッションがつながったままか
        "gap_ms",
        "carried",
        "recent_turns",
        "resume_kind",
        "reconnect",
        "reused",
        # Data review #111: whether live.turn's usage was estimated at 0.01 dollars, whether the player interrupted,
        # the source of the character's subtitles
        # データ担当のレビュー #111：live.turn の使用量を 0.01 ドルで見積もったか、プレイヤーが割り込んだか、登場人物の
        # 字幕の出どころ
        "usage_estimated",
        "interrupted",
        "transcript_source",
        # B-13: which event a memory came from, which memory; on deletion, how many turns of original words were
        # cleared, whether a promise was voided, whether the session was rebuilt
        # B-13：記憶がどのイベントから来たか、どの記憶か。削除時に元の発言を何ターン消したか、約束を無効にしたか、
        # セッションを再構築したか
        "event_id",
        "memory_id",
        "turns",
        "voided",
        "rebuilt",
    }
)


@dataclass
class Span:
    name: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def set(self, **attrs: Any) -> None:
        for k, v in attrs.items():
            if k not in ATTRS:
                raise KeyError(f"Span does not accept this attribute / Span はこの属性を受け付けない: {k}")
            self.attrs[k] = v


@dataclass
class Tracer:
    """One per process; `spans` keeps the most recent ones (for tests to look at).

    プロセスごとに 1 つ。`spans` は直近のものを残す（テストが見る）。
    """

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
            # A Span that records an event supplies its own duration / 出来事を記録する Span は所要時間を自分で与える
            s.attrs.setdefault("duration_ms", round((time.perf_counter() - start) * 1000, 1))
            self.spans.append(s)
            del self.spans[: -self.keep]
            log.info("%s %s", name, json.dumps(s.attrs, ensure_ascii=False, sort_keys=True))

    def named(self, name: str) -> list[Mapping[str, Any]]:
        return [s.attrs for s in self.spans if s.name == name]
