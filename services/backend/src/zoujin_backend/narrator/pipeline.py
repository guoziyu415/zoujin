"""叙事者流水线的第 1〜5 步（B-2，backend-design 2.4）：分流 → 提取 → 确定性规则 → 模型检查 → 改写、降级或拒绝。

第 7 步（单事务提交）在 `narrator/core.py`；第 0 步（安全筛查）只有接口：`TurnInput.flags`。第 6 步（意图确认，B-4）：
对话里提取标了要确认、又是不可逆的大事的候选照常过第 3〜5 步，带着 `confirm`（人物反问了没有、反问的一句）交给
叙事者，过了的存成草稿（`narrator/confirm.py`）；动作里的这种候选照 B-2 丢弃（B-4 不改动作）。
草稿开着时，对着反问的人物说的一轮不分流，提取多判一项：这句话是不是在回答（`confirmAnswer`）。

- **时限**：每次调用有截止时间（`config.DEADLINES`），超时、输出不过 Schema、调用失败就取消、立刻重发一次。
  第二次还不行：分流当作「可能」继续；提取、检查、改写的，这一轮只提交时钟事件、候选丢弃，
  `playthrough_metrics` 记一次超时。
  `BudgetStop` 不重发，往上抛，整次停下。`RateLimited`（429、529）看 `on_rate_limit`：Mac 上的跑（S-2、评测、小测）
  是 "stop"，第一个就停（S-079）；服务玩家时是 "degrade"，按上面的时限规则重发一次，还不行就这一轮只提交时钟事件，
  `playthrough_metrics` 记一次超时（backend-design 2.4 的降级，B-8）。
- **ID**：约定和即兴设定的 ID 在第 3 步前分配（试算要用），但不进给模型的请求：请求里的状态和候选用别名
  （`narrator/view.py`），同样的局面请求一样，回放的键才对得上。
- **第 3、4 步的顺序**：先按顺序跑第 3 步（前面通过的先试算进状态），再把过了第 3 步、`effects` 不为空的候选合在一次
  检查调用里；然后按顺序定每个候选的结果（前面被模型否决的不再算进后面的状态，后面的重判第 3 步）。不过的带着失败的
  规则和理由改写，回到第 3 步，最多改写 2 次（`attempts` ≤ 3）；还不过就降级，降级的也要过第 3、4 步，否则拒绝。
  降级不另算一次尝试（`attempts` 是改写上限 2 次的那个数，契约第 3 节最大 3）。
- 没有效果的候选不是事件（提取给了就不要；改写、降级成没有效果的算做不到）。
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import jsonschema
from zoujin_backend.config import DEADLINES
from zoujin_backend.ids import IdGen
from zoujin_backend.models.prompts import MODEL_RULES, PROMPTS
from zoujin_backend.models.text import (
    BadOutput,
    ModelCallFailed,
    RateLimited,
    TextModel,
    TextResult,
    model_and_version,
    spec,
)
from zoujin_backend.narrator.rules import (
    CHECKER,
    RULES,
    SHAPE,
    VERBATIM,
    Checked,
    Hit,
    Turn,
    fill_ids,
    judge,
    lcs_len,
    rule_rows,
    trial,
)
from zoujin_backend.narrator.view import View, persona, player_card, situation, state_view
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book
from zoujin_worldsim import SimState

Json = Any

MAX_TRIES = 3  # 原本 1 次 + 改写最多 2 次（契约 CheckResult.attempts ≤ 3）
# 第 6 步那类事件（S-040）：让节拍 prevented / altered，或改变人质、玩家的身份处境
IRREVERSIBLE_BEAT = ("prevented", "altered")
IRREVERSIBLE_VARS = ("var.hostage.who", "var.hostage.fate", "var.player.custody")
MODEL_REASON = {  # 模型判 fail 却没给理由（或理由照抄了玩家的话）时用的一句
    "R1-anchor": "物語の要と食い違っている",
    "R5-persona": "この人物の性格や目的からは考えにくい",
    "R6-safety": "物語に書けない内容が入っている",
}
FORM = ("R7-capability", "bad-shape", SHAPE["bad-op"][1])


class CallFailed(Exception):
    """一种提示两次都没拿到能用的输出（超时、不过 Schema、调用失败）。"""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(frozen=True)
class TurnInput:
    """这一轮：对谁说（`character`）、玩家的原话、人物的回答、语音还是文字、第 0 步的标记、动作（B-3）。"""

    character: str | None
    player: str | None
    reply: str | None = None
    mode: str = "text"
    flags: frozenset[str] = frozenset()
    act: Mapping[str, Any] | None = None

    @property
    def rules(self) -> Turn:
        return Turn(said=self.player or "", act=self.act, flags=self.flags)

    def doc(self) -> Json:
        """请求里的 `turn`：原话只在这里（真客户端放进 `<utterance>` 数据字段）。"""
        d: Json = {"character": self.character, "mode": self.mode, "player": self.player}
        if self.reply is not None:
            d["reply"] = self.reply
        if self.act is not None:
            d["act"] = copy.deepcopy(dict(self.act))
        return d


@dataclass
class Counts:
    """一轮的计数（`playthrough_metrics`）。改写、降级、拒绝按候选的最后结果数。"""

    triage_skipped: int = 0
    confirm_dropped: int = 0
    timeouts: int = 0
    rewritten: int = 0
    downgraded: int = 0
    rejected: int = 0

    def __add__(self, o: Counts) -> Counts:
        return Counts(**{k: getattr(self, k) + getattr(o, k) for k in self.__dataclass_fields__})


@dataclass
class Spend:
    """这一轮各类提示花了多少（美元），重来的、超时被取消的、输出不合格的也算（钱已经花了），和账本对得上。"""

    usd: dict[str, float] = field(default_factory=dict)

    def add(self, r: TextResult) -> None:
        self.charge(r.kind, r.cost_usd)

    def charge(self, kind: str, usd: float) -> None:
        self.usd[kind] = self.usd.get(kind, 0.0) + usd


@dataclass
class Extracted:
    candidates: list[Json]  # 规范化以后的（真 ID；t、dt、place 在第 3 步前按当时的状态补）
    counts: Counts
    timed_out: bool = False
    # B-4：和 candidates 一一对应，要确认的候选是 {"asked", "question"}，其余 None
    confirm: list[Json | None] = field(default_factory=list)
    answer: str | None = None  # 草稿开着时：这句话在回答反问（yes / no），不是在回答为 None


@dataclass
class Verified:
    checked: list[Checked]
    counts: Counts
    timed_out: bool = False


@dataclass
class _Try:
    """一个候选的一次尝试：第 3 步的结果和第 4 步的结果（没跑是 None）。"""

    cand: Json
    effects: list[Json]
    hits: list[Hit]
    model: dict[str, Json] | None = None

    @property
    def fails(self) -> list[tuple[str, str]]:
        out = [(h.rule, h.reason) for h in self.hits]
        out += [(r, m["reason"]) for r, m in (self.model or {}).items() if m["status"] == "fail"]
        return out

    @property
    def ok(self) -> bool:
        return not self.fails


# —— 候选的规范化（模型输出 → 叙事者用的候选） ——


def _effect_in(e: Mapping[str, Any], view: View) -> Json:
    out = copy.deepcopy(dict(e))
    op = out.get("op")
    if op == "promise":
        if out.get("change") == "made":
            out.pop("promiseId", None)  # 新约定的 ID 提交时分配
        elif "promiseId" in out:
            out["promiseId"] = view.real(out["promiseId"])
    elif op == "improv":
        out.pop("factId", None)
    elif op == "learn":
        out["fact"] = view.real(out.get("fact"))
    return out


def normalize(raw: Mapping[str, Any], view: View, book: Book) -> Json:
    """模型给的候选 → 叙事者的候选：补默认值，别名换回真 ID，只留世界模型里有的节拍做 causes。"""
    c: Json = {
        "actor": raw.get("actor") or "player",
        "type": raw.get("type") or "say",
        "origin": raw.get("origin") or "turn",
        "summary": str(raw.get("summary") or ""),
        "causes": [x for x in raw.get("causes") or [] if x in book.beats],
        "effects": [_effect_in(e, view) for e in raw.get("effects") or []],
        "needsConfirm": bool(raw.get("needsConfirm")),
    }
    b = raw.get("beneficiary")
    if b == "player" or b in book.characters:
        c["beneficiary"] = b
    return c


def act_doc(act: Mapping[str, Any] | None) -> Json | None:
    """提取请求里的 `action`（B-3）：玩家做的动作的 kind、对象、物品。打算、出口、过场的 act 不是动作。"""
    if not act or "kind" not in act or act["kind"] in ("plan", "en-route", "go"):
        return None
    params = act.get("params") or {}
    return {"kind": act["kind"], "target": act.get("target"), "item": params.get("item")}


def irreversible(cand: Mapping[str, Any]) -> bool:
    for e in cand.get("effects", []):
        if e.get("op") == "beat" and e.get("to") in IRREVERSIBLE_BEAT:
            return True
        if e.get("op") == "set" and e.get("var") in IRREVERSIBLE_VARS:
            return True
    return False


def situate(cand: Mapping[str, Any], state: SimState, minutes: int) -> Json:
    """第 3 步要的 t、dt、place：这一轮开始的时刻、这一轮的分钟（R3 量路程）、玩家所在地点。提交时照 B-0 写在 t0、dt 0，
    这一轮的分钟由只推进时钟的那条事件走。"""
    return {**cand, "t": state["t"], "dt": minutes, "place": state["vars"]["var.player.location"]}


def public(cand: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], view: View) -> Json:
    """给模型看的候选：分配的新 ID 去掉，已有的换成别名。"""
    effs = []
    for e in effects:
        x = copy.deepcopy(dict(e))
        if x.get("op") == "promise":
            if x.get("change") == "made":
                x.pop("promiseId", None)
            elif "promiseId" in x:
                x["promiseId"] = view.alias(x["promiseId"])
        elif x.get("op") == "improv":
            x.pop("factId", None)
        elif x.get("op") == "learn":
            x["fact"] = view.alias(x["fact"])
        effs.append(x)
    keep = ("actor", "type", "origin", "summary", "causes", "beneficiary", "t", "dt", "place")
    return {**{k: cand[k] for k in keep if k in cand}, "effects": effs, "needsConfirm": bool(cand.get("needsConfirm"))}


# —— 流水线 ——


@dataclass
class Pipeline:
    text: TextModel
    schemas: SchemaBook
    ids: IdGen
    tracer: Tracer = field(default_factory=Tracer)
    deadlines: Mapping[str, float] = field(default_factory=lambda: dict(DEADLINES))
    on_rate_limit: str = "stop"  # "stop"：跑（第一个 429、529 就停）；"degrade"：服务玩家（当作这一次失败）

    # 调用：时限、重发一次、Schema、Span

    async def call(
        self,
        kind: str,
        request: Json,
        spend: Spend,
        *,
        span: Mapping[str, Any],
        extra: Callable[[Json], Mapping[str, Any] | None] | None = None,
    ) -> TextResult:
        """extra：Schema 之外的检查（不过就抛 BadOutput，按重发算），返回要加到 Span 上的属性。"""
        model, version = model_and_version(kind)
        for attempt in (1, 2):
            with self.tracer.span(
                f"narrator.{kind}",
                provider=spec(kind).provider,
                model=model,
                prompt_version=version,
                attempt=attempt,
                **span,
            ) as sp:
                got: TextResult | None = None
                try:
                    r = got = await asyncio.wait_for(self.text.call(kind, request), self.deadlines[kind])
                    spend.add(r)
                    try:
                        jsonschema.validate(r.output, PROMPTS[kind].schema)
                    except jsonschema.ValidationError:
                        raise BadOutput(f"{kind} 的输出不过 Schema") from None
                    attrs = extra(r.output) if extra is not None else None
                except TimeoutError:  # 被取消的调用可能已经计费：真客户端按预计记了账，这一轮的花费记同一个数
                    cost = self.text.cancelled_cost(kind, request)
                    spend.charge(kind, cost)
                    sp.set(status="timeout", cost_usd=round(cost, 6))
                    continue
                except BadOutput as e:
                    if got is None:  # 真客户端拿到回答才知道不合格，没返回结果，钱已经花了
                        spend.charge(kind, e.cost_usd)
                    sp.set(status="invalid", cost_usd=round(e.cost_usd if got is None else got.cost_usd, 6))
                    continue
                except ModelCallFailed:
                    sp.set(status="error")
                    continue
                except RateLimited:
                    if self.on_rate_limit == "stop":
                        raise
                    sp.set(status="rate_limited")
                    continue
                sp.set(
                    status="ok",
                    tokens_in=r.usage.get("inputTokens", 0),
                    tokens_out=r.usage.get("outputTokens", 0),
                    tokens_cached=r.usage.get("cachedTokens", r.usage.get("cacheReadTokens", 0)),
                    tokens_thought=r.usage.get("thoughtTokens", r.usage.get("thinkingTokens", 0)),
                    cost_usd=round(r.cost_usd, 6),
                    **(attrs or {}),
                )
                return r
        raise CallFailed(kind)

    # 第 1、2 步

    async def extract(
        self,
        book: Book,
        state: SimState,
        turn: TurnInput,
        spend: Spend,
        span: Mapping[str, Any] | None = None,
        *,
        drafts: bool = False,
        confirm: Mapping[str, Any] | None = None,
    ) -> Extracted:
        """drafts：要确认的候选留下来、带上 `confirm`（对话）；False 时丢弃（动作）。confirm：开着的草稿（反问的那一句
        `prompt`、那件事的 `summary`），给了就不分流，提取多判 `confirmAnswer`。"""
        counts = Counts()
        span = {"world_model_version": book.version, **(span or {})}
        names = {
            "player": book.roles[state["role"]]["name"],
            "character": book.characters.get(turn.character or "", {}).get("name"),
        }
        action = act_doc(turn.act)
        if action is None and confirm is None:  # 动作（B-3）不分流：做了就要找事件；有反问在等回答的也不分流
            try:
                r = await self.call(
                    "triage",
                    {"names": names, "turn": turn.doc()},
                    spend,
                    span=span,
                    extra=lambda o: {"route": o["route"]},
                )
                route = r.output["route"]
            except CallFailed:
                route = "maybe"  # 分流两次都超时：当作「可能」
            if route == "chat":
                counts.triage_skipped = 1
                return Extracted([], counts)
        view = state_view(book, state)
        request = {"worldModelVersion": book.version, "state": view.doc, "turn": turn.doc()}
        if action is not None:
            request["action"] = action
        if confirm is not None:
            request["confirm"] = {"prompt": confirm["prompt"], "summary": confirm["summary"]}
        try:
            r = await self.call(
                "extract", request, spend, span=span, extra=lambda o: {"candidate_count": len(o["candidates"])}
            )
        except CallFailed:
            counts.timeouts = 1
            return Extracted([], counts, timed_out=True)
        cands: list[Json] = []
        asks: list[Json | None] = []
        for raw in r.output["candidates"]:
            c = normalize(raw, view, book)
            if not c["effects"]:
                continue
            ask = None
            if c["needsConfirm"] and irreversible(c):
                if not drafts:  # 动作：照 B-2，没确认 = 不是
                    counts.confirm_dropped += 1
                    continue
                ask = {"asked": bool(raw.get("asked")), "question": raw.get("question")}
            cands.append(c)
            asks.append(ask)
        answer = r.output.get("confirmAnswer") if confirm is not None else None
        return Extracted(cands, counts, confirm=asks, answer=answer)

    # 第 3〜5 步

    def step3(self, book: Book, state: SimState, cand: Json, effects: list[Json], turn: TurnInput) -> list[Hit]:
        """确定性规则，加效果的形状（不合契约 Effect 的按 R7 否决，免得提交时才出错）和行为者存在。"""
        hits = []
        bad_actor = cand.get("actor") not in ("player", *book.characters)
        if bad_actor or any(self.schemas.effect_errors(e) for e in effects):
            hits.append(Hit(*FORM))
        return hits + judge(book.world, state, cand, effects, turn.rules)

    async def model_check(
        self,
        book: Book,
        state: SimState,
        tries: Sequence[_Try],
        turn: TurnInput,
        spend: Spend,
        span: Mapping[str, Any],
    ) -> list[dict[str, Json]]:
        """第 4 步：一次调用判几个候选的 R1（只写在文字里的）、R5、R6。返回每个候选 {规则: {status, reason}}。"""
        view = state_view(book, state)
        request = {
            "worldModelVersion": book.version,
            "state": view.doc,
            "turn": turn.doc(),
            "candidates": [{"index": i, **public(t.cand, t.effects, view)} for i, t in enumerate(tries)],
        }
        n = len(tries)

        def complete(out: Json) -> Mapping[str, Any]:
            got = {r["index"]: {x["rule"] for x in r["rules"]} for r in out["results"]}
            if any(got.get(i) != set(MODEL_RULES) for i in range(n)):
                raise BadOutput("检查的输出缺了候选或规则")
            bad = {x["rule"] for r in out["results"] if r["index"] < n for x in r["rules"] if x["status"] == "fail"}
            return {"failed_rules": [x for x in RULES if x in bad]}

        r = await self.call("check", request, spend, span={**span, "candidate_count": n}, extra=complete)
        rows: list[dict[str, Json]] = [{} for _ in range(n)]
        for res in r.output["results"]:
            if res["index"] >= n:
                continue
            for x in res["rules"]:
                reason = x.get("reason") or MODEL_REASON[x["rule"]]
                if turn.player and lcs_len(turn.player, reason) >= VERBATIM:
                    reason = MODEL_REASON[x["rule"]]  # 理由也不照抄玩家的话
                row = {"status": x["status"]} | ({"reason": reason} if x["status"] == "fail" else {})
                rows[res["index"]][x["rule"]] = row
        return rows

    def _try(self, book: Book, state: SimState, cand: Json, turn: TurnInput, minutes: int) -> _Try:
        c = situate(cand, state, minutes)
        effects = fill_ids(c["effects"], self.ids)
        return _Try(c, effects, self.step3(book, state, c, effects, turn))

    async def _rewrite(
        self,
        book: Book,
        state: SimState,
        last: _Try,
        mode: str,
        fails: Sequence[tuple[str, str]],
        turn: TurnInput,
        spend: Spend,
        span: Mapping[str, Any],
    ) -> Json | None:
        view = state_view(book, state)
        request = {
            "worldModelVersion": book.version,
            "state": view.doc,
            "turn": turn.doc(),
            "mode": mode,
            "candidate": public(last.cand, last.effects, view),
            "failed": [{"rule": r, "reason": why} for r, why in _uniq(fails)],
        }
        why = list(dict.fromkeys(f["rule"] for f in request["failed"]))  # 只有规则名，不带理由
        r = await self.call("rewrite", request, spend, span={**span, "mode": mode, "failed_rules": why})
        raw = r.output["candidate"]
        if raw is None:
            return None
        c = normalize(raw, view, book)
        return c if c["effects"] else None

    async def _judge(
        self, book: Book, state: SimState, t: _Try, turn: TurnInput, spend: Spend, span: Mapping[str, Any]
    ) -> _Try:
        """一次尝试：第 3 步，过了而且有效果就跑第 4 步。"""
        if not t.hits and t.effects and t.model is None:
            (t.model,) = await self.model_check(book, state, [t], turn, spend, span)
        return t

    async def verify(
        self,
        book: Book,
        state: SimState,
        candidates: Sequence[Json],
        turn: TurnInput,
        minutes: int,
        spend: Spend,
        span: Mapping[str, Any] | None = None,
    ) -> Verified:
        """第 3〜5 步。改写、检查两次都超时：整轮只走时钟（`timed_out`），候选丢弃。"""
        span = {"world_model_version": book.version, **(span or {})}
        try:
            return await self._verify(book, state, candidates, turn, minutes, spend, span)
        except CallFailed:
            return Verified([], Counts(timeouts=1), timed_out=True)

    async def _verify(
        self,
        book: Book,
        state: SimState,
        candidates: Sequence[Json],
        turn: TurnInput,
        minutes: int,
        spend: Spend,
        span: Mapping[str, Any],
    ) -> Verified:
        world = book.world
        # 第 3 步，按顺序；过了的先试算进状态
        first: list[_Try] = []
        now = state
        for cand in candidates:
            t = self._try(book, now, cand, turn, minutes)
            first.append(t)
            if not t.hits:
                now = trial(world, now, t.cand, t.effects)
        # 第 4 步：过了第 3 步、有效果的合在一次调用里
        scoped = [t for t in first if not t.hits and t.effects]
        if scoped:
            for t, row in zip(scoped, await self.model_check(book, state, scoped, turn, spend, span), strict=True):
                t.model = row
        # 按顺序定结果：前面被否决的不算进后面的状态，后面的重判第 3 步
        out: list[Checked] = []
        counts = Counts()
        now = state
        for t in first:
            again = self._try(book, now, t.cand, turn, minutes)
            if [h.code for h in again.hits] != [h.code for h in t.hits]:
                t = await self._judge(book, now, again, turn, spend, span)
            checked = await self._settle(book, now, t, turn, minutes, spend, span)
            out.append(checked)
            st = checked.check["status"]
            counts.rewritten += st == "rewritten"
            counts.downgraded += st == "downgraded"
            counts.rejected += st == "rejected"
            if checked.passed:
                now = trial(world, now, checked.candidate, checked.effects)
        return Verified(out, counts)

    async def _settle(
        self,
        book: Book,
        state: SimState,
        first: _Try,
        turn: TurnInput,
        minutes: int,
        spend: Spend,
        span: Mapping[str, Any],
    ) -> Checked:
        """第 5 步：不过的改写（最多 2 次），还不过就降级，再不过拒绝。"""
        model_ran = first.model is not None
        if first.ok:
            return self._checked(first, "passed", 1, [], model_ran)
        fails = list(first.fails)
        last, tries = first, 1
        while tries < MAX_TRIES:
            tries += 1
            cand = await self._rewrite(book, state, last, "rewrite", fails, turn, spend, span)
            if cand is None:
                break
            if _same(cand, last.cand):  # 原样改回来：同样的结果，不再检查
                continue
            t = await self._judge(book, state, self._try(book, state, cand, turn, minutes), turn, spend, span)
            model_ran = model_ran or t.model is not None
            if t.ok:
                return self._checked(t, "rewritten", tries, fails, model_ran)
            fails += t.fails
            last = t
        cand = await self._rewrite(book, state, first, "downgrade", fails, turn, spend, span)
        if cand is not None:
            t = await self._judge(book, state, self._try(book, state, cand, turn, minutes), turn, spend, span)
            model_ran = model_ran or t.model is not None
            if t.ok:
                return self._checked(t, "downgraded", tries, fails, model_ran)
        return self._checked(first, "rejected", tries, fails, model_ran)

    def _checked(
        self, t: _Try, status: str, attempts: int, fails: Sequence[tuple[str, str]], model_ran: bool
    ) -> Checked:
        check = result(status, attempts, fails, model_ran)
        cand = {k: v for k, v in t.cand.items() if k != "needsConfirm"}
        return Checked(cand, t.effects, check, rule_rows(t.hits, t.model), t.hits)

    # 评测入口的 check()：第 3 步 + 按范围跑第 4 步，不改写、不提交

    async def check_only(
        self,
        book: Book,
        state: SimState,
        cand: Json,
        turn: TurnInput,
        model_checks: str,
        spend: Spend,
        span: Mapping[str, Any] | None = None,
    ) -> Checked:
        """两次都超时抛 `CallFailed`（评测入口照样抛，S-2 的运行器记成超时）。"""
        c = {**cand}
        c.setdefault("t", state["t"])
        c.setdefault("dt", 0)
        c.setdefault("place", state["vars"]["var.player.location"])
        c.setdefault("origin", "turn")
        effects = fill_ids(c.get("effects", []), self.ids)
        t = _Try(c, effects, self.step3(book, state, c, effects, turn))
        if model_checks == "all" or (model_checks == "scoped" and not t.hits and t.effects):
            attrs = {"world_model_version": book.version, **(span or {})}
            (t.model,) = await self.model_check(book, state, [t], turn, spend, attrs)
        check = result("rejected" if t.fails else "passed", 1, t.fails, t.model is not None)
        return Checked(c, effects, check, rule_rows(t.hits, t.model), t.hits)

    # 文字模式的人物回答

    async def reply(
        self, book: Book, state: SimState, turn: TurnInput, spend: Spend, *, notes: Sequence[str] = ()
    ) -> str | None:
        """人物用文字回答（`reply`）。两次都不行返回 None（评测入口的 `characterTextMissing`）。
        notes：B-12 输出侧监控给局势说明加的提示，有才放进 `situation.notes`（没有时请求和以前一样，回放的键不变）。"""
        who = turn.character
        if who is None or who not in book.characters:
            return None
        view = state_view(book, state)
        request = {
            "worldModelVersion": book.version,
            "character": who,
            "persona": persona(book, state, who),
            "situation": situation(book, state, who, view) | ({"notes": list(notes)} if notes else {}),
            "player": player_card(book, state, who),
            "turn": {"character": who, "mode": turn.mode, "player": turn.player},
        }
        try:
            r = await self.call("reply", request, spend, span={"world_model_version": book.version, "character": who})
        except CallFailed:
            return None
        return str(r.output["text"])

    # 候选话语（B-21，ux-design 7.8）

    async def suggest(
        self,
        book: Book,
        state: SimState,
        who: str,
        spend: Spend,
        *,
        player: str | None = None,
        reply: str | None = None,
        actions: Sequence[str] = (),
    ) -> list[Json] | None:
        """玩家刚和 who 说完一轮（或刚走到他面前）：2〜3 个候选话语 `[{text, kind}]`。全是问句按不合格重发一次；
        两次都不行返回 None（这一轮不出候选）。"""
        if who not in book.characters:
            return None
        view = state_view(book, state)
        request: Json = {
            "worldModelVersion": book.version,
            "character": who,
            "persona": persona(book, state, who),
            "situation": situation(book, state, who, view),
            "player": player_card(book, state, who),
            "actions": list(actions),
        }
        if player is not None or reply is not None:
            request["turn"] = {"character": who, "player": player, "reply": reply}

        def not_all_questions(out: Json) -> Mapping[str, Any] | None:
            if all(x["kind"] == "ask" for x in out["items"]):
                raise BadOutput("候选全是问句")
            return {"candidate_count": len(out["items"])}

        try:
            r = await self.call(
                "suggest",
                request,
                spend,
                span={"world_model_version": book.version, "character": who},
                extra=not_all_questions,
            )
        except CallFailed:
            return None
        return [{"text": str(x["text"]), "kind": str(x["kind"])} for x in r.output["items"]]


def checker(model_ran: bool) -> str:
    """`check.checker`：规则版本，跑了第 4 步再加检查提示的模型和版本。"""
    if not model_ran:
        return CHECKER
    model, version = model_and_version("check")
    return f"{CHECKER}+{model}/{version}"


def result(status: str, attempts: int, fails: Sequence[tuple[str, str]], model_ran: bool) -> Json:
    """契约的 CheckResult。failedRules 按 R1〜R7 的顺序（第一条是主规则），reason 是主规则第一次失败的理由。"""
    rules = [r for r in RULES if any(f == r for f, _ in fails)]
    check: Json = {"status": status, "attempts": attempts, "failedRules": rules, "checker": checker(model_ran)}
    if rules:
        check["reason"] = next(why for f, why in fails if f == rules[0])
    return check


def _uniq(fails: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for f in fails:
        if f not in out:
            out.append(f)
    return out


def _same(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    keys = ("actor", "type", "summary", "effects", "causes", "beneficiary")
    return all(a.get(k) == b.get(k) for k in keys)


__all__ = ["CallFailed", "Counts", "Extracted", "Pipeline", "Spend", "TurnInput", "Verified"]
