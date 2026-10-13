"""Steps 1-5 of the narrator pipeline (B-2, backend-design 2.4): triage → extraction → deterministic rules → model
check → rewrite, downgrade or reject.

Step 7 (single-transaction commit) is in `narrator/core.py`; step 0 (safety screening) only has an interface:
`TurnInput.flags`. Step 6 (intent confirmation, B-4): in dialogue, candidates that extraction marked as needing
confirmation and that are major irreversible things go through steps 3-5 as usual and are handed to the narrator with
`confirm` (whether the character asked back, and the counter-question); those that pass are stored as drafts
(`narrator/confirm.py`); such candidates from actions are dropped as in B-2 (B-4 doesn't change actions).
While a draft is open, a turn addressed to the character who asked back isn't triaged, and extraction judges one more
thing: whether the line answers the question (`confirmAnswer`).

- **Deadlines**: every call has a deadline (`config.DEADLINES`); on timeout, output that fails the Schema, or a failed
  call, cancel and resend once right away. If the second try also fails: triage continues as "maybe"; for extraction,
  check and rewrite, this turn commits only the clock event, drops the candidates, and `playthrough_metrics` records
  one timeout. `BudgetStop` isn't resent; it is raised and stops the whole run. `RateLimited` (429, 529) depends on
  `on_rate_limit`: runs on the Mac (S-2, evals, small tests) use "stop" and stop at the first one (S-079); serving
  players uses "degrade": resend once per the deadline rule above, and if that fails too, commit only the clock event
  for this turn and record one timeout in `playthrough_metrics` (backend-design 2.4's degradation, B-8).
- **IDs**: promise and improvised-fact IDs are assigned before step 3 (trial application needs them), but never enter
  requests to the model: the state and candidates in requests use aliases (`narrator/view.py`), so the same situation
  gives the same request and replay keys match.
- **Order of steps 3 and 4**: first run step 3 in order (earlier passing ones are trial-applied to the state first),
  then put the candidates that passed step 3 and have non-empty `effects` into one check call; then settle each
  candidate's result in order (ones rejected by the model no longer count toward later state, and later ones are
  re-judged in step 3). Failures are rewritten with the failed rules and reasons and go back to step 3, at most 2
  rewrites (`attempts` ≤ 3); if they still fail they are downgraded, and the downgraded one must also pass steps 3
  and 4, otherwise it is rejected. Downgrading doesn't count as another attempt (`attempts` is the count capped by the 2
  rewrites; contract section 3 max 3).
- A candidate without effects is not an event (dropped if extraction gives one; a rewrite or downgrade to no effects
  counts as impossible).

ナレーターのパイプラインの第 1〜5 ステップ（B-2、backend-design 2.4）：振り分け → 抽出 → 決定的な規則 → モデルの検査 →
書き換え、格下げ、または却下。

第 7 ステップ（単一トランザクションのコミット）は `narrator/core.py`。第 0 ステップ（安全スクリーニング）はインター
フェースだけ：`TurnInput.flags`。第 6 ステップ（意図の確認、B-4）：対話で、抽出が確認要と印を付けた不可逆な大きなことの
候補は通常どおり第 3〜5 ステップを通し、`confirm`（登場人物が聞き返したか、聞き返しの一文）を付けてナレーターに渡す。
通ったものは下書きとして保存する（`narrator/confirm.py`）。アクションでのこうした候補は B-2 のとおり捨てる
（B-4 はアクションを変えない）。下書きが開いている間、聞き返した登場人物に向けたターンは振り分けず、抽出はもう 1 つ
判定する：その一言が返答かどうか（`confirmAnswer`）。

- **時間制限**：呼び出しごとに締め切りがある（`config.DEADLINES`）。タイムアウト、出力が Schema を通らない、呼び出しの
  失敗のときは取り消してすぐ 1 回だけ送り直す。2 回目もだめなら：振り分けは「可能性あり」として続ける。抽出、検査、
  書き換えなら、このターンは時計のイベントだけをコミットし、候補は捨て、`playthrough_metrics` にタイムアウトを 1 回
  記録する。`BudgetStop` は送り直さず上に投げ、全体を止める。`RateLimited`（429、529）は `on_rate_limit` 次第：
  Mac での実行（S-2、評価、小テスト）は "stop" で最初の 1 回で止める（S-079）。プレイヤー向けは "degrade" で、上の
  時間制限の規則どおり 1 回送り直し、それでもだめならこのターンは時計のイベントだけをコミットし、
  `playthrough_metrics` にタイムアウトを 1 回記録する（backend-design 2.4 の格下げ、B-8）。
- **ID**：約束と即興設定の ID は第 3 ステップの前に割り当てる（試算に要る）が、モデルへのリクエストには入れない：
  リクエストの状態と候補は別名を使い（`narrator/view.py`）、同じ局面なら同じリクエストになり、リプレイのキーが一致する。
- **第 3・4 ステップの順序**：まず第 3 ステップを順に実行し（先に通ったものを状態に試算する）、次に第 3 ステップを通り
  `effects` が空でない候補を 1 回の検査呼び出しにまとめる。それから各候補の結果を順に決める（モデルに却下された前の
  候補は後の状態に入れず、後の候補は第 3 ステップを判定し直す）。通らないものは失敗した規則と理由を付けて書き換え、
  第 3 ステップに戻す。書き換えは最大 2 回（`attempts` ≤ 3）。それでも通らなければ格下げし、格下げしたものも第 3・4
  ステップを通らなければ却下する。格下げは試行回数に数えない（`attempts` は書き換え上限 2 回に対応する数で、契約第 3 節
  で最大 3）。
- 効果のない候補はイベントではない（抽出が出してきても使わない。書き換えや格下げで効果がなくなったらできないとみなす）。
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

# The original once + at most 2 rewrites (contract CheckResult.attempts ≤ 3).
# 元の 1 回 + 書き換え最大 2 回（契約 CheckResult.attempts ≤ 3）。
MAX_TRIES = 3
# Step 6 events (S-040): making a beat prevented / altered, or changing the hostage's or the player's situation.
# 第 6 ステップの対象となるイベント（S-040）：ビートを prevented / altered にする、
# または人質やプレイヤーの立場を変える。
IRREVERSIBLE_BEAT = ("prevented", "altered")
IRREVERSIBLE_VARS = ("var.hostage.who", "var.hostage.fate", "var.player.custody")
# The line used when the model judges fail without a reason (or the reason copies the player's words).
# モデルが fail と判定したのに理由がない（または理由がプレイヤーの言葉の書き写し）ときに使う一文。
MODEL_REASON = {
    "R1-anchor": "物語の要と食い違っている",
    "R5-persona": "この人物の性格や目的からは考えにくい",
    "R6-safety": "物語に書けない内容が入っている",
}
FORM = ("R7-capability", "bad-shape", SHAPE["bad-op"][1])


class CallFailed(Exception):
    """A prompt kind got no usable output in two tries (timeout, Schema failure, call failure).

    あるプロンプトで 2 回とも使える出力が得られなかった（タイムアウト、Schema を通らない、呼び出しの失敗）。
    """

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(frozen=True)
class TurnInput:
    """This turn: who is addressed (`character`), the player's words, the character's reply, voice or text, step 0
    flags, and the action (B-3).

    このターン：誰に話すか（`character`）、プレイヤーの発話、登場人物の返答、音声かテキストか、第 0 ステップの印、
    アクション（B-3）。
    """

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
        """The request's `turn`: the player's words appear only here (the real client puts them in the `<utterance>`
        data field).

        リクエストの `turn`：発話はここにだけ入る（本番クライアントは `<utterance>` のデータフィールドに入れる）。
        """
        d: Json = {"character": self.character, "mode": self.mode, "player": self.player}
        if self.reply is not None:
            d["reply"] = self.reply
        if self.act is not None:
            d["act"] = copy.deepcopy(dict(self.act))
        return d


@dataclass
class Counts:
    """Counts for one turn (`playthrough_metrics`). Rewrites, downgrades and rejections are counted by each candidate's
    final result.

    1 ターンの集計（`playthrough_metrics`）。書き換え、格下げ、却下は候補の最終結果で数える。
    """

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
    """How much each prompt kind cost in this turn (USD), including retries, calls cancelled on timeout and invalid
    output (the money is already spent), so it matches the ledger.

    このターンで各プロンプトにかかった金額（米ドル）。やり直し、タイムアウトで取り消した呼び出し、不合格の出力も含める
    （お金はもう使っている）ので、台帳と一致する。
    """

    usd: dict[str, float] = field(default_factory=dict)

    def add(self, r: TextResult) -> None:
        self.charge(r.kind, r.cost_usd)

    def charge(self, kind: str, usd: float) -> None:
        self.usd[kind] = self.usd.get(kind, 0.0) + usd


@dataclass
class Extracted:
    # Normalized (real IDs; t, dt and place are filled in before step 3 from the state at that time).
    # 正規化済み（本当の ID。t、dt、place は第 3 ステップの前にその時点の状態から補う）。
    candidates: list[Json]
    counts: Counts
    timed_out: bool = False
    # B-4: one per candidate; {"asked", "question"} for candidates needing confirmation, None otherwise.
    # B-4：candidates と 1 対 1 で、確認が要る候補は {"asked", "question"}、それ以外は None。
    confirm: list[Json | None] = field(default_factory=list)
    # While a draft is open: the line answers the counter-question (yes / no); None if it isn't an answer.
    # 下書きが開いている間：この一言が聞き返しへの返答（yes / no）。返答でなければ None。
    answer: str | None = None


@dataclass
class Verified:
    checked: list[Checked]
    counts: Counts
    timed_out: bool = False


@dataclass
class _Try:
    """One attempt for a candidate: the step 3 result and the step 4 result (None if not run).

    1 つの候補の 1 回の試行：第 3 ステップの結果と第 4 ステップの結果（実行していなければ None）。
    """

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


# —— Normalizing candidates (model output → candidates the narrator uses) ——
# —— 候補の正規化（モデルの出力 → ナレーターが使う候補） ——


def _effect_in(e: Mapping[str, Any], view: View) -> Json:
    out = copy.deepcopy(dict(e))
    op = out.get("op")
    if op == "promise":
        if out.get("change") == "made":
            # New promise IDs are assigned at commit / 新しい約束の ID はコミット時に割り当てる
            out.pop("promiseId", None)
        elif "promiseId" in out:
            out["promiseId"] = view.real(out["promiseId"])
    elif op == "improv":
        out.pop("factId", None)
    elif op == "learn":
        out["fact"] = view.real(out.get("fact"))
    return out


def normalize(raw: Mapping[str, Any], view: View, book: Book) -> Json:
    """A candidate from the model → a narrator candidate: fill in defaults, map aliases back to real IDs, and keep only
    beats from the world model as causes.

    モデルが出した候補 → ナレーターの候補：既定値を補い、別名を本当の ID に戻し、
    causes には世界モデルにあるビートだけを残す。
    """
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
    """The `action` in an extraction request (B-3): the kind, target and item of the player's action. The acts of
    plans, exits and en-route choices are not actions.

    抽出リクエストの `action`（B-3）：プレイヤーのアクションの kind、対象、物。プラン、出口、道中の二択の act は
    アクションではない。
    """
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
    """The t, dt and place step 3 needs: the time this turn started, this turn's minutes (R3 measures travel against
    them), and the player's place. At commit, as in B-0, it is written at t0 with dt 0, and the turn's minutes go into
    the event that only advances the clock.

    第 3 ステップが要る t、dt、place：このターンの開始時刻、このターンの分数（R3 が道のりを測る）、
    プレイヤーのいる場所。
    コミット時は B-0 のとおり t0、dt 0 で書き、このターンの分数は時計を進めるだけのイベントが受け持つ。
    """
    return {**cand, "t": state["t"], "dt": minutes, "place": state["vars"]["var.player.location"]}


def public(cand: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], view: View) -> Json:
    """The candidate as shown to the model: newly assigned IDs removed, existing ones replaced with aliases.

    モデルに見せる候補：新たに割り当てた ID は除き、既存のものは別名に置き換える。
    """
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


# —— Pipeline / パイプライン ——


@dataclass
class Pipeline:
    text: TextModel
    schemas: SchemaBook
    ids: IdGen
    tracer: Tracer = field(default_factory=Tracer)
    deadlines: Mapping[str, float] = field(default_factory=lambda: dict(DEADLINES))
    # "stop": runs (stop at the first 429/529); "degrade": serving players (treat it as this try failing).
    # "stop"：実行（最初の 429・529 で止める）。"degrade"：プレイヤー向け（今回の失敗として扱う）。
    on_rate_limit: str = "stop"

    # Calls: deadline, one resend, Schema, Span / 呼び出し：時間制限、1 回の再送、Schema、Span

    async def call(
        self,
        kind: str,
        request: Json,
        spend: Spend,
        *,
        span: Mapping[str, Any],
        extra: Callable[[Json], Mapping[str, Any] | None] | None = None,
    ) -> TextResult:
        """extra: a check beyond the Schema (raise BadOutput if it fails, counted as a resend); returns attributes to
        add to the Span.

        extra：Schema 以外の検査（通らなければ BadOutput を投げ、再送として数える）。Span に加える属性を返す。
        """
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
                        raise BadOutput(
                            f"{kind} output fails the Schema / {kind} の出力が Schema を通らない"
                        ) from None
                    attrs = extra(r.output) if extra is not None else None
                # A cancelled call may already be billed: the real client booked an estimate, and this turn's spend
                # records the same amount.
                # 取り消した呼び出しはすでに課金されているかもしれない：本番クライアントは見積もりで記帳しており、
                # このターンの支出にも同じ額を記録する。
                except TimeoutError:
                    cost = self.text.cancelled_cost(kind, request)
                    spend.charge(kind, cost)
                    sp.set(status="timeout", cost_usd=round(cost, 6))
                    continue
                except BadOutput as e:
                    # The real client only learns the answer is invalid after receiving it; no result came back, but
                    # the money is spent.
                    # 本番クライアントは返答を受け取ってから不合格と分かる。結果は返っていないが、お金はもう使っている。
                    if got is None:
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

    # Steps 1 and 2 / 第 1・2 ステップ

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
        """drafts: keep candidates needing confirmation, with `confirm` (dialogue); drop them when False (actions).
        confirm: the open draft (the counter-question `prompt` and the matter's `summary`); if given, no triage, and
        extraction also judges `confirmAnswer`.

        drafts：確認が要る候補を残し、`confirm` を付ける（対話）。False なら捨てる（アクション）。confirm：開いている
        下書き（聞き返しの一文 `prompt` と、その件の `summary`）。渡されたら振り分けず、
        抽出が `confirmAnswer` も判定する。
        """
        counts = Counts()
        span = {"world_model_version": book.version, **(span or {})}
        names = {
            "player": book.roles[state["role"]]["name"],
            "character": book.characters.get(turn.character or "", {}).get("name"),
        }
        action = act_doc(turn.act)
        # Actions (B-3) aren't triaged: doing something always means looking for events; nor are turns while a
        # counter-question awaits an answer.
        # アクション（B-3）は振り分けない：何かをしたならイベントを探す。聞き返しが返答を待っている間も振り分けない。
        if action is None and confirm is None:
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
                # Triage timed out twice: treat as "maybe" / 振り分けが 2 回ともタイムアウト：「可能性あり」とする
                route = "maybe"
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
                if not drafts:  # actions: as in B-2, unconfirmed = no / アクション：B-2 のとおり、未確認 = いいえ
                    counts.confirm_dropped += 1
                    continue
                ask = {"asked": bool(raw.get("asked")), "question": raw.get("question")}
            cands.append(c)
            asks.append(ask)
        answer = r.output.get("confirmAnswer") if confirm is not None else None
        return Extracted(cands, counts, confirm=asks, answer=answer)

    # Steps 3-5 / 第 3〜5 ステップ

    def step3(self, book: Book, state: SimState, cand: Json, effects: list[Json], turn: TurnInput) -> list[Hit]:
        """The deterministic rules, plus the shape of effects (those not matching the contract's Effect are rejected
        under R7, so they don't fail only at commit) and that the actor exists.

        決定的な規則に、効果の形（契約の Effect に合わないものは R7 で却下し、コミット時に初めてエラーになるのを防ぐ）と
        行為者の存在を加える。
        """
        hits = []
        bad_actor = cand.get("actor") not in ("player", *book.characters)
        if cand.get("actor") == "system" and (turn.act or {}).get("kind") == "world":
            # B-16: the director's environmental changes (bells, the sky, the city gate).
            # B-16：ディレクターによる環境の変化（鐘の音、空模様、城門）。
            bad_actor = False
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
        """Step 4: one call judges R1 (the part only written in text), R5 and R6 for several candidates. Returns
        {rule: {status, reason}} per candidate.

        第 4 ステップ：1 回の呼び出しで複数の候補の R1（文章にだけ書かれた部分）、R5、R6 を判定する。候補ごとに
        {規則: {status, reason}} を返す。
        """
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
                raise BadOutput("Check output is missing candidates or rules / 検査の出力に候補か規則が欠けている")
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
                    # The reason must not copy the player's words either / 理由もプレイヤーの言葉を書き写さない
                    reason = MODEL_REASON[x["rule"]]
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
        # Rule names only, no reasons / 規則名だけで、理由は含めない
        why = list(dict.fromkeys(f["rule"] for f in request["failed"]))
        r = await self.call("rewrite", request, spend, span={**span, "mode": mode, "failed_rules": why})
        raw = r.output["candidate"]
        if raw is None:
            return None
        c = normalize(raw, view, book)
        return c if c["effects"] else None

    async def _judge(
        self, book: Book, state: SimState, t: _Try, turn: TurnInput, spend: Spend, span: Mapping[str, Any]
    ) -> _Try:
        """One attempt: step 3, then step 4 if it passed and has effects.

        1 回の試行：第 3 ステップ。通って効果があれば第 4 ステップを実行する。
        """
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
        """Steps 3-5. If rewrite or check times out twice: the whole turn only moves the clock (`timed_out`), and the
        candidates are dropped.

        第 3〜5 ステップ。書き換えか検査が 2 回ともタイムアウトしたら、ターン全体で時計だけを進め（`timed_out`）、
        候補は捨てる。
        """
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
        # Step 3, in order; passing ones are trial-applied to the state first.
        # 第 3 ステップを順に。通ったものは先に状態に試算する。
        first: list[_Try] = []
        now = state
        for cand in candidates:
            t = self._try(book, now, cand, turn, minutes)
            first.append(t)
            if not t.hits:
                now = trial(world, now, t.cand, t.effects)
        # Step 4: those that passed step 3 and have effects go into one call.
        # 第 4 ステップ：第 3 ステップを通り効果のあるものを 1 回の呼び出しにまとめる。
        scoped = [t for t in first if not t.hits and t.effects]
        if scoped:
            for t, row in zip(scoped, await self.model_check(book, state, scoped, turn, spend, span), strict=True):
                t.model = row
        # Settle results in order: earlier rejected ones don't count toward later state; later ones redo step 3.
        # 結果を順に決める：前に却下されたものは後の状態に入れず、後のものは第 3 ステップを判定し直す。
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
        """Step 5: rewrite failures (at most twice); if they still fail, downgrade; if that fails, reject.

        第 5 ステップ：通らないものを書き換え（最大 2 回）、それでもだめなら格下げし、さらにだめなら却下する。
        """
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
            # Rewritten back to the same thing: same result, no need to check again.
            # 元どおりに書き戻された：結果は同じなので検査し直さない。
            if _same(cand, last.cand):
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

    # check() for the eval entry point: step 3 + step 4 within the given scope, no rewriting, no commit.
    # 評価の入口の check()：第 3 ステップ + 範囲に応じて第 4 ステップ。書き換えもコミットもしない。

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
        """Raise `CallFailed` if both tries time out (the eval entry point raises it as is; the S-2 runner records a
        timeout).

        2 回ともタイムアウトしたら `CallFailed` を投げる（評価の入口はそのまま投げ、
        S-2 のランナーがタイムアウトとして記録する）。
        """
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

    # Text-mode character replies / テキストモードの登場人物の返答

    async def reply(
        self, book: Book, state: SimState, turn: TurnInput, spend: Spend, *, notes: Sequence[str] = ()
    ) -> str | None:
        """The character replies in text (`reply`). If both tries fail, return None (the eval entry point's
        `characterTextMissing`).
        notes: hints that B-12's output-side monitoring adds to the situation notes; put into `situation.notes` only
        when there are some (without them the request is as before and replay keys don't change).

        登場人物がテキストで返答する（`reply`）。2 回ともだめなら None を返す（評価の入口の `characterTextMissing`）。
        notes：B-12 の出力側の監視が状況説明に加えるヒント。
        あるときだけ `situation.notes` に入れる（なければリクエストは
        従来どおりで、リプレイのキーも変わらない）。
        """
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

    # Suggested lines (B-21, ux-design 7.8) / 候補の発話（B-21、ux-design 7.8）

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
        """The player has just finished a turn with who (or just walked up to them): 2-3 suggested lines
        `[{text, kind}]`. All questions counts as invalid and is resent once; if both tries fail, return None (no
        suggestions this turn).

        プレイヤーが who と 1 ターン話し終えた（または目の前まで来た）ところ：候補の発話 2〜3 個 `[{text, kind}]`。
        すべて問いかけなら不合格として 1 回送り直す。2 回ともだめなら None を返す（このターンは候補を出さない）。
        """
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
                raise BadOutput("All suggestions are questions / 候補がすべて問いかけ")
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
    """`check.checker`: the rules version, plus the check prompt's model and version if step 4 ran.

    `check.checker`：規則のバージョン。第 4 ステップを実行したら検査プロンプトのモデルとバージョンも付ける。
    """
    if not model_ran:
        return CHECKER
    model, version = model_and_version("check")
    return f"{CHECKER}+{model}/{version}"


def result(status: str, attempts: int, fails: Sequence[tuple[str, str]], model_ran: bool) -> Json:
    """The contract's CheckResult. failedRules in R1-R7 order (the first is the main rule); reason is the main rule's
    first failure reason.

    契約の CheckResult。failedRules は R1〜R7 の順（最初が主な規則）で、reason は主な規則が最初に失敗したときの理由。
    """
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
