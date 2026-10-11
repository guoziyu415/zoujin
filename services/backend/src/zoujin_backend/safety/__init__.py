"""玩家每一句的安全筛查（B-12，backend-design 2.4 第 0 步、5.5；api-contract 3.12）。

三样并行：
- **分类器**（提示 `safety`，Claude Haiku，S-072 的 v2 规则）：自伤、求助信号（signal / ambiguous / none）和注入。
  3 秒时限，
  超时、输出不合格、调用失败就立刻重发一次；第二次还不行 → `unscreened`（不暂停，叙事者按最保守的判）。
  模型拒答 → `harmful`。
- **Model Armor**（第二层，S-085 ②）：PI 在 MEDIUM 以上算注入，RAI 只认 HIGH 算有害，SDP 命中算个人信息。1 秒没回、出错
  就当没命中，`armor_failed` 记一次。
- **个人信息规则**（`safety.pii`，自己的规则为主）：存下的原话用掩码后的 `masked`。

B-15（S-072 ⑤）：分类器带上下文（对谁说、在哪、人物上一句，`Context`）；第一遍判 signal 时，护栏（`safety.guard`）
没命中就用更强的模型带同样的上下文复核（提示 `safety_review`），复核说是故事里的话才降成 ambiguous；复核超时、出错、
拒答都保留 signal。同一局第二次 ambiguous 也先复核（`second_look`），是故事里的话就不升级成暂停（卡第 6 节的 C）。

判定结果、分数都不进日志和 Trace（S-057、S-069 ③）：Span 只有耗时、第几次、
状态（ok / timeout / invalid / error / refused）。
`Screen` 只活在内存里，网关和评测入口拿它决定暂停、小提示和交给叙事者的标记。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import jsonschema

from zoujin_backend.models.armor import DEADLINE_S as ARMOR_DEADLINE_S
from zoujin_backend.models.armor import NONE, Armor, ArmorFailed, ArmorResult, cost_usd
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import (
    BadOutput,
    ModelCallFailed,
    RateLimited,
    Refused,
    Stop,
    TextModel,
    model_and_version,
    spec,
)
from zoujin_backend.safety import pii
from zoujin_backend.safety.guard import decided
from zoujin_backend.trace import Tracer

type SelfHarm = Literal["signal", "ambiguous", "none", "unscreened"]

# 交给叙事者的标记（turns.flags，narrator/rules.py 的 FLAG_REASON）
INJECTION, PII, HARMFUL, UNSCREENED, AMBIGUOUS = "injection", "pii", "harmful", "unscreened", "ambiguous"
FLAGS = frozenset({INJECTION, PII, HARMFUL, UNSCREENED, AMBIGUOUS})

SAFETY_REVIEW = True  # B-15：第一遍 signal 的复核（False = B-12 的做法）
PREVIOUS_MAX = 120  # 人物上一句最多带几个字（截断不加省略号）

type Reviewed = Literal["kept", "downgraded", "guarded", "failed"]


@dataclass(frozen=True)
class Context:
    """分类器和复核看的上下文（B-15）：玩家对谁说（名字）、在哪（地点名）、这个人物上一句。都可以缺。"""

    character: str | None = None
    place: str | None = None
    previous: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.character:
            out["character"] = self.character
        if self.place:
            out["place"] = self.place
        if self.previous:
            out["previous"] = self.previous[:PREVIOUS_MAX]
        return out


@dataclass(frozen=True)
class Screen:
    """一句话的筛查结果。self_harm：分类器的判定（两次都没判出来 = unscreened）；flags：交给叙事者的标记；
    masked：个人信息换成「〔個人情報〕」以后的原话（存进 utterances 的是它）。"""

    self_harm: SelfHarm
    flags: frozenset[str]
    masked: str | None
    refused: bool = False
    armor_failed: bool = False
    armor: ArmorResult = NONE
    attempts: int = 0
    duration_ms: float = 0.0
    cost_usd: float = 0.0  # 分类器（含重发、超时取消的那次）
    armor_usd: float = 0.0
    reviewed: Reviewed | None = None  # B-15：复核走了哪条路（只进指标和 Trace 的状态）
    story: bool = False  # B-15：复核说这句是故事里的话（第二次 ambiguous 不升级）
    review_usd: float = 0.0

    @property
    def unscreened(self) -> bool:
        return self.self_harm == "unscreened"


NOT_SCREENED = Screen("none", frozenset(), None)


@dataclass
class Screener:
    text: TextModel
    armor: Armor
    tracer: Tracer = field(default_factory=Tracer)
    deadline: float | None = None  # None = config.TEXT["safety"] 的时限（3 秒）
    armor_deadline: float = ARMOR_DEADLINE_S
    raise_stops: bool = False  # True（Mac 上的 safety-eval）：账本到上限、429 整次停下；False（服务玩家）：当作这次失败
    review: bool = SAFETY_REVIEW
    review_deadline: float | None = None  # None = config.TEXT["safety_review"] 的时限（2.5 秒）

    async def screen(
        self,
        said: str | None,
        context: Context | None = None,
        on_review: Callable[[], None] | None = None,
        **span: object,
    ) -> Screen:
        """on_review：要复核时先叫它（网关在这时扣住人物还没发出去的声音和字幕，UX 对 B-15 的意见 1）。"""
        if not said or not said.strip():
            return Screen("none", frozenset(), said)
        t0 = time.perf_counter()
        (self_harm, injection, refused, attempts, cost), got = await asyncio.gather(
            self.classify(said, context, **span), self._armor(said)
        )
        reviewed: Reviewed | None = None
        story = False
        review_usd = 0.0
        if self_harm == "signal":
            if decided(said):
                reviewed = "guarded"  # 说出决定、手段、时间、告别：不复核（S-072 ⑤）
            elif self.review:
                if on_review is not None:
                    on_review()
                verdict, review_usd = await self.check_story(said, context, **span)
                if verdict is None:
                    reviewed = "failed"
                elif verdict:
                    self_harm, reviewed, story = "ambiguous", "downgraded", True
                else:
                    reviewed = "kept"
        armor_failed = got is None
        ar = got or NONE
        flags: set[str] = set()
        if injection or ar.injection:
            flags.add(INJECTION)
        if refused or ar.harmful or ar.uri:
            flags.add(HARMFUL)
        hits = pii.find(said)
        if hits or ar.pii:
            flags.add(PII)
        if self_harm == "unscreened":
            flags.add(UNSCREENED)
        if self_harm == "ambiguous":
            flags.add(AMBIGUOUS)
        return Screen(
            self_harm,
            frozenset(flags),
            pii.mask(said) if hits else said,
            refused=refused,
            armor_failed=armor_failed,
            armor=ar,
            attempts=attempts,
            duration_ms=(time.perf_counter() - t0) * 1000,
            cost_usd=cost,
            armor_usd=cost_usd(self.armor, said),
            reviewed=reviewed,
            story=story,
            review_usd=review_usd,
        )

    async def second_look(self, s: Screen, said: str | None, context: Context | None = None, **span: object) -> Screen:
        """同一局第二次 ambiguous（要升级成暂停之前）：没复核过就复核一次（卡第 6 节的 C）。复核失败照旧升级。"""
        if not said or s.self_harm != "ambiguous" or s.reviewed is not None or not self.review:
            return s
        verdict, usd = await self.check_story(said, context, **span)
        reviewed: Reviewed = "failed" if verdict is None else ("downgraded" if verdict else "kept")
        return replace(s, reviewed=reviewed, story=bool(verdict), review_usd=s.review_usd + usd)

    async def check_story(self, said: str, context: Context | None, **span: object) -> tuple[bool | None, float]:
        """复核（提示 `safety_review`，一次，不重发）：(story，花费)。

        超时、出错、拒答、输出不合格 → None（保留 signal）。
        """
        kind = "safety_review"
        model, version = model_and_version(kind)
        request = self._request(said, context)
        deadline = self.review_deadline if self.review_deadline is not None else spec(kind).deadline
        with self.tracer.span(
            "safety.review", provider=spec(kind).provider, model=model, prompt_version=version, **span
        ) as sp:
            try:
                r = await asyncio.wait_for(self.text.call(kind, request), deadline)
                jsonschema.validate(r.output, PROMPTS[kind].schema)
            except TimeoutError:
                sp.set(status="timeout")
                return None, self.text.cancelled_cost(kind, request)
            except Refused as e:
                sp.set(status="refused")
                return None, e.cost_usd
            except BadOutput as e:
                sp.set(status="invalid")
                return None, e.cost_usd
            except jsonschema.ValidationError:
                sp.set(status="invalid")
                return None, r.cost_usd
            except (ModelCallFailed, RateLimited, Stop) as e:
                if self.raise_stops and not isinstance(e, ModelCallFailed):
                    raise
                sp.set(status="error")
                return None, 0.0
            sp.set(status="ok", cost_usd=round(r.cost_usd, 6))
            return bool(r.output["story"]), r.cost_usd

    @staticmethod
    def _request(said: str, context: Context | None) -> dict[str, Any]:
        """分类器和复核的请求：没有上下文时和 B-12 一样（回放的键不变）。"""
        ctx = context.to_json() if context is not None else {}
        return {"turn": {"player": said}, **({"context": ctx} if ctx else {})}

    async def classify(
        self, said: str, context: Context | None = None, **span: object
    ) -> tuple[SelfHarm, bool, bool, int, float]:
        """(selfHarm, injection, refused, 调了几次, 花费)。拒答不重发（同一句再问还是拒答），按有害输入处理。"""
        kind = "safety"
        model, version = model_and_version(kind)
        request = self._request(said, context)
        deadline = self.deadline if self.deadline is not None else spec(kind).deadline
        cost = 0.0
        for attempt in (1, 2):
            with self.tracer.span(
                "safety.classify",
                provider=spec(kind).provider,
                model=model,
                prompt_version=version,
                attempt=attempt,
                **span,
            ) as sp:
                try:
                    r = await asyncio.wait_for(self.text.call(kind, request), deadline)
                    jsonschema.validate(r.output, PROMPTS[kind].schema)
                except TimeoutError:
                    sp.set(status="timeout")
                    cost += self.text.cancelled_cost(kind, request)
                    continue
                except Refused as e:
                    sp.set(status="refused")
                    return "none", False, True, attempt, cost + e.cost_usd
                except BadOutput as e:
                    sp.set(status="invalid")
                    cost += e.cost_usd
                    continue
                except jsonschema.ValidationError:
                    sp.set(status="invalid")
                    cost += r.cost_usd
                    continue
                except ModelCallFailed:
                    sp.set(status="error")
                    continue
                except RateLimited:
                    if self.raise_stops:
                        raise
                    sp.set(status="rate_limited")
                    continue
                except Stop:
                    if self.raise_stops:
                        raise
                    sp.set(status="stopped")
                    return "unscreened", False, False, attempt, cost
                cost += r.cost_usd
                sp.set(status="ok", cost_usd=round(r.cost_usd, 6))
                return r.output["selfHarm"], bool(r.output["injection"]), False, attempt, cost
        return "unscreened", False, False, 2, cost

    async def _armor(self, said: str) -> ArmorResult | None:
        """第二层：1 秒没回、出错 → None（当没命中，记一次 armor_failed）。回放查不到照样抛出去。"""
        try:
            return await asyncio.wait_for(self.armor.screen_prompt(said), self.armor_deadline)
        except (TimeoutError, ArmorFailed):
            return None


@dataclass
class SafetyState:
    """这一局的安全状态（playthroughs.safety）。"""

    paused: bool = False
    hinted: bool = False
    ambiguous: int = 0

    @classmethod
    def of(cls, d: dict[str, object] | None) -> SafetyState:
        d = d or {}
        return cls(bool(d.get("paused")), bool(d.get("hinted")), int(d.get("ambiguous") or 0))  # type: ignore[call-overload]

    def to_json(self) -> dict[str, object]:
        return {"paused": self.paused, "hinted": self.hinted, "ambiguous": self.ambiguous}


type Decision = Literal["pause", "hint", "pass"]


def decide(screen: Screen, st: SafetyState) -> Decision:
    """S-069 / S-043：signal → 暂停；ambiguous 一局第一次 → 小提示，第二次 → 暂停；别的照常。改 st（调用方写回库）。"""
    if screen.self_harm == "signal":
        st.paused = True
        return "pause"
    if screen.self_harm == "ambiguous":
        st.ambiguous += 1
        if st.ambiguous >= 2 and not screen.story:  # B-15：复核说是故事里的话就不升级
            st.paused = True
            return "pause"
        if not st.hinted:
            st.hinted = True
            return "hint"
    return "pass"


def counts_of(s: Screen, decision: str) -> dict[str, float]:
    """`playthrough_metrics` 加的几样（列名按数据评审 #112）。标记的轮数只算交给了叙事者的（暂停的不算）。"""
    out: dict[str, float] = {}
    if s.cost_usd:
        out["cost_safety_usd"] = s.cost_usd
    if s.armor_usd:
        out["cost_armor_usd"] = s.armor_usd
    if s.review_usd:
        out["cost_safety_review_usd"] = s.review_usd
    if s.reviewed == "guarded":
        out["safety_guarded"] = 1
    elif s.reviewed is not None:
        out["safety_reviews"] = 1
        if s.reviewed == "downgraded":
            out["safety_downgrades"] = 1
        elif s.reviewed == "failed":
            out["safety_review_failed"] = 1
    for flag, col in (
        ("unscreened", "safety_unscreened"),
        ("refused", "safety_refused"),
        ("armor_failed", "armor_errors"),
    ):
        if getattr(s, flag):
            out[col] = 1
    if s.self_harm == "ambiguous":
        out["safety_ambiguous"] = 1
    if decision == "pause":
        out["safety_pauses"] = 1
        return out
    if decision == "hint":
        out["safety_hints"] = 1
    for flag in (INJECTION, PII, HARMFUL):
        if flag in s.flags:
            out[f"safety_{flag}"] = 1
    return out
