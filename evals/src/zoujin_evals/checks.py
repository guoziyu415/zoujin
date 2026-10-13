"""The 28 kinds of deterministic checks (evals/README.md "Deterministic checks").

Each check is a function (ctx, spec) -> reason for failing | None: None means pass; raise SkipCheck when it cannot be
judged. EvalNotImplemented and ReplayMissing raised by the backend's queries are not caught here; the runner records
them as skips by the exception.

A "committed" event = check.status is passed / rewritten / downgraded. The parts that can be judged by simulation
alone (replay, baseline, crossing the line) use W-1's zoujin_worldsim, the same rules as the narrator.

28 種類の決定的チェック（evals/README.md「決定的チェック」）。

各チェックは関数 (ctx, spec) -> 不合格の理由 | None：None は合格。判定できないときは SkipCheck を投げる。バックエンドの
クエリが投げる EvalNotImplemented、ReplayMissing はここでは受けず、ランナーが例外に応じてスキップとして記録する。

「コミットされた」イベント = check.status が passed / rewritten / downgraded。シミュレーションだけで判定できる部分
（リプレイ、ベースライン、一線越え）は W-1 の zoujin_worldsim を使い、ナレーターと同じ規則に従う。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from zoujin_worldsim import OCCURRED, Sim, SimState, apply, classify, initial_state, settle, world_state

from .api import EvalSession, Event, Json, StepResult
from .results import SkipCheck, not_implemented
from .text import JAPANESE_MIN, ending_texts, japanese_ratio, proper_nouns, verbatim

COMMITTED = {"passed", "rewritten", "downgraded"}
STEP_KINDS = (
    "to",
    "act",
    "deleteMemory",
    "deleteMemoryId",
    "confirm",
    "retract",
    "deletePlaythrough",
    "newPlaythrough",
    "advance",
    "silence",
    "propose",
    "choose",
)


def step_kind(step: Mapping[str, Json]) -> str:
    """Which kind a step is ({"to", "say"} is dialogue).

    ステップの種類（{"to", "say"} は会話）。
    """
    for k in STEP_KINDS:
        if k in step:
            return k
    raise ValueError(f"Unknown step {sorted(step)} / 不明なステップ {sorted(step)}")


def committed(e: Event) -> bool:
    return (e.get("check") or {}).get("status") in COMMITTED


def matches(e: Event, match: Mapping[str, Json]) -> bool:
    """Every field written in match is equal; for every entry in its effects there is one in the event's effects
    with the same values for the keys written (only var without value = any change to that variable).

    match に書かれたフィールドはすべて一致し、その effects の各項目について、書かれたキーが一致する項目がイベントの
    effects に 1 つある（var だけで value がない = その変数のあらゆる変更）。
    """
    for k in ("type", "actor", "origin", "beneficiary"):
        if k in match and e.get(k) != match[k]:
            return False
    effects = e.get("effects") or []
    return all(any(all(x.get(k) == v for k, v in m.items()) for x in effects) for m in match.get("effects", []))


def describe(events: Iterable[Event]) -> str:
    """The events listed in a failure reason: ID, type, actor, origin, status.

    不合格の理由に列挙するイベント：ID、種類、行為者、起点、ステータス。
    """
    parts = []
    for e in events:
        who = e.get("eventId") or "(no ID / ID なし)"
        status = (e.get("check") or {}).get("status")
        parts.append(f"{who} {e.get('type')}/{e.get('actor')}/{e.get('origin')}/{status}")
    return "; ".join(parts) or "(none / なし)"


@dataclass
class WorldIndex:
    """The world model and a few things often used from it.

    世界モデルと、そこからよく使ういくつかのもの。
    """

    raw: dict[str, Json]
    _canon: dict[str, dict[str, int]] = field(default_factory=dict)

    @cached_property
    def facts(self) -> dict[str, dict[str, Json]]:
        return {f["id"]: f for f in self.raw["facts"]}

    @cached_property
    def characters(self) -> list[str]:
        return [c["id"] for c in self.raw["characters"]]

    @cached_property
    def nouns(self) -> list[str]:
        return proper_nouns(self.raw)

    @property
    def watch_beat(self) -> str | None:
        wb: str | None = self.raw["clock"]["deadline"].get("watchBeat")
        return wb

    def canon_times(self, role: str) -> dict[str, int]:
        """When each beat happens on the canon path (sc.canon).

        原作の経路（sc.canon）で各ビートが発生する時刻。
        """
        if role not in self._canon:
            self._canon[role] = dict(Sim(self.raw).run({"id": "sc.canon"}, role=role)["times"])
        return self._canon[role]


@dataclass
class RunContext:
    """What the checks need after one run has gone through all its steps. Query results are cached for the run.

    1 回の実行が全ステップを終えた後にチェックが使うもの。クエリの結果はその回の中でキャッシュする。
    """

    world: WorldIndex
    case: Mapping[str, Json]
    session: EvalSession
    results: list[StepResult]  # the result of step n is results[n - 1] / ステップ n の結果は results[n - 1]
    # events() right after setup; None when the backend has not implemented events()
    # setup 直後の events() の結果。バックエンドが events() を未実装なら None
    setup_events: list[Event] | None
    # the steps the AI player actually took in a simulated game (recorded by the runner); None for ordinary cases
    # シミュレーション局で AI プレイヤーが実際に進んだステップ（ランナーが記録）。通常のケースは None
    played: list[Mapping[str, Json]] | None = None
    _cache: dict[Hashable, Json] = field(default_factory=dict)

    # ---------- Case / ケース ----------
    @property
    def steps(self) -> list[Mapping[str, Json]]:
        """The steps actually taken in this run: those written in the case, or for a simulated game those the AI player
        took (written the same way as the case's steps).

        この回で実際に進んだステップ：ケースに書かれたもの。シミュレーション局では AI プレイヤーが進んだもの（ケースの
        steps と同じ書き方）。
        """
        if self.played is not None:
            return self.played
        steps: list[Mapping[str, Json]] = self.case.get("steps", [])
        return steps

    @property
    def role(self) -> str:
        role: str = self.case["setup"]["role"]
        return role

    def last_to(self) -> int | None:
        return max((n for n, s in enumerate(self.steps, 1) if step_kind(s) == "to"), default=None)

    def player_lines(self) -> list[str]:
        """What the player said in this game: dialogue and end-of-act plans in the steps actually taken (for simulated
        games the runner records them itself and does not ask the backend).

        この局でプレイヤーが言ったこと：実際に進んだステップ内の会話と幕末のプラン（シミュレーション局はランナー自身が
        記録し、バックエンドには問い合わせない）。
        """
        return [s["say"] for s in self.steps if "say" in s] + [s["propose"] for s in self.steps if "propose" in s]

    # ---------- Step results / ステップの結果 ----------
    def result(self, n: int) -> StepResult:
        return self.results[n - 1]

    def value(self, n: int, key: str) -> Any:
        r: Mapping[str, Any] = self.result(n)
        if key not in r:
            raise not_implemented(f"StepResult.{key}")
        return r[key]

    def step_events(self, n: int) -> list[Event]:
        evs: list[Event] = self.value(n, "events")
        return evs

    def all_step_events(self) -> list[Event]:
        return [e for n in range(1, len(self.results) + 1) for e in self.step_events(n)]

    def committed_ids(self, n: int) -> set[str]:
        return {e["eventId"] for e in self.step_events(n) if committed(e) and e.get("eventId")}

    # ---------- Backend queries / バックエンドのクエリ ----------
    def query(self, name: str, *args: Hashable) -> Any:
        key = (name, args)
        if key not in self._cache:
            fn = getattr(self.session, name, None)
            if fn is None:
                raise not_implemented(name)
            self._cache[key] = fn(*args)
        return self._cache[key]

    def state(self) -> dict[str, Json]:
        st: dict[str, Json] = self.query("state")
        return st

    def events(self) -> list[Event]:
        evs: list[Event] = self.query("events")
        return evs

    def beat_time(self, beat: str) -> int | None:
        """When the beat happened (happened / altered): the t of the event that wrote this result.

        ビートが発生した（happened / altered）時刻：その結果を書いたイベントの t。
        """
        t = None
        for e in self.events():
            if committed(e) and any(
                x.get("op") == "beat" and x.get("beat") == beat and x.get("to") in OCCURRED
                for x in e.get("effects") or []
            ):
                t = e["t"]
        return t

    # ---------- Simulating with W-1 / W-1 でのシミュレーション ----------
    def fold(self, events: Iterable[Event]) -> SimState:
        """Apply these events in seq order from the role's opening state (the replay of contract 3.1).

        ロールの開始状態から seq 順にこれらのイベントを apply する（契約 3.1 のリプレイ）。
        """
        s = initial_state(self.world.raw, self.role)
        for e in events:
            s = apply(self.world.raw, s, e)
        return s


type Check = Callable[[RunContext, Mapping[str, Json]], str | None]

# ---------- Checks on the character's reply / 人物の返答を見るチェック ----------


def _reply(ctx: RunContext, spec: Mapping[str, Json]) -> str:
    n = spec.get("step", ctx.last_to())
    if ctx.result(n).get("characterTextMissing"):
        raise SkipCheck({"code": "no-character-text"})
    reply: str | None = ctx.value(n, "reply")
    return reply or ""


def check_japanese(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    r = japanese_ratio(_reply(ctx, spec))
    if r is None:
        return "No text in the reply / 返答に文字がない"
    if r >= JAPANESE_MIN:
        return None
    return (
        f"Kana and kanji are only {r:.0%} of letters (need ≥ {JAPANESE_MIN:.0%})"
        f" / かなと漢字は文字の {r:.0%} だけ（≥ {JAPANESE_MIN:.0%} が必要）"
    )


def check_not_mention_fact(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    reply = _reply(ctx, spec)
    hit = [t for t in ctx.world.facts[spec["fact"]].get("spoilerTerms", []) if t in reply]
    return f"Said spoiler terms of {spec['fact']}: {hit} / {spec['fact']} のネタバレ語を言った：{hit}" if hit else None


def check_no_terms(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    reply = _reply(ctx, spec)
    hit = [t for t in spec["terms"] if t in reply]
    return f"The reply contains {hit} / 返答に {hit} がある" if hit else None


def check_terms_any(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    reply = _reply(ctx, spec)
    if any(t in reply for t in spec["terms"]):
        return None
    return f"The reply has none of {spec['terms']} / 返答に {spec['terms']} のどれもない"


# ---------- Events / イベント ----------


def check_event(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    cands = ctx.step_events(spec["step"]) if "step" in spec else ctx.all_step_events()
    want_rules = set(spec.get("failedRulesAny", []))
    for e in cands:
        chk = e.get("check") or {}
        if (
            matches(e, spec["match"])
            and chk.get("status") in spec["statusIn"]
            and (not want_rules or want_rules & set(chk.get("failedRules", [])))
        ):
            return None
    return (
        f"No matching candidate event with status in {spec['statusIn']}"
        f" / ステータスが {spec['statusIn']} の一致する候補イベントがない; present / あるもの: {describe(cands)}"
    )


def check_no_event(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """Only what this case's turns committed: beats and deadlines that fall due (origin = schedule) do not count,
    unless match states the origin.

    このケースのターンがコミットしたものだけを見る：時刻が来たビートと期限（origin = schedule）は、match が origin を
    明記していない限り数えない。
    """
    m = spec["match"]
    hit = [
        e
        for e in ctx.all_step_events()
        if committed(e) and (e.get("origin") != "schedule" or m.get("origin") == "schedule") and matches(e, m)
    ]
    if not hit:
        return None
    return f"Committed events that should not exist / あってはならないイベントをコミットした: {describe(hit)}"


def check_world_unchanged(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """This case's turns committed no event with non-empty effects; beats settled by the schedule as the clock moves
    have the same results as in the baseline scenario. Baseline scenario = only the setup events, settled with W-1 to
    the same time.

    このケースのターンは effects が空でないイベントをコミットしていない。時計が進む間にスケジュールで決着したビートは、
    結果が元のシナリオと同じ。元のシナリオ = setup のイベントだけを W-1 で同じ時刻まで決着させたもの。
    """
    changed = [e for e in ctx.all_step_events() if committed(e) and e.get("effects") and e.get("origin") != "schedule"]
    if changed:
        return (
            "This case's turns committed world-changing events"
            f" / このケースのターンが世界を変えるイベントをコミットした: {describe(changed)}"
        )
    if ctx.setup_events is None:
        raise not_implemented("events")
    st = ctx.state()
    base = settle(ctx.world.raw, ctx.fold(ctx.setup_events), st["t"])[1]
    want = world_state(ctx.world.raw, base, st["playthroughId"])["beats"]
    diff = {
        b: f"{st['beats'].get(b)} (baseline / 元のシナリオ {v})" for b, v in want.items() if st["beats"].get(b) != v
    }
    if not diff:
        return None
    return (
        "Beats settled by the schedule differ from the baseline scenario"
        f" / スケジュールで決着したビートが元のシナリオと異なる: {diff}"
    )


def check_event_exists(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    ids = ctx.committed_ids(spec["fromStep"])
    if not ids:
        n = spec["fromStep"]
        return f"Step {n} has no committed event / ステップ {n} にコミットされたイベントがない"
    missing = ids - {e.get("eventId") for e in ctx.events()}
    if not missing:
        return None
    n = spec["fromStep"]
    return f"Events of step {n} are gone / ステップ {n} のイベントが消えた: {sorted(missing)}"


# ---------- State / 状態 ----------


def check_var(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    vars_ = ctx.state()["vars"]
    if spec["var"] not in vars_:
        return f"No {spec['var']} in the state / 状態に {spec['var']} がない"
    got = vars_[spec["var"]]
    return None if got == spec["equals"] else f"{spec['var']} = {got!r}, expected / 期待値 {spec['equals']!r}"


def check_beat(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    got = ctx.state()["beats"].get(spec["beat"])
    if got != spec["status"]:
        return f"{spec['beat']} is {got}, expected / 期待値 {spec['status']}"
    if "t" in spec:
        t = ctx.beat_time(spec["beat"])
        if t != spec["t"]:
            return f"{spec['beat']} happened at t={t}, expected t={spec['t']} / t={t} に発生、期待値 t={spec['t']}"
    return None


def check_schedule_shift(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """The beat's scheduled time (if it has no result yet) or the time it happened, minus the time it happens on the
    canon path.

    ビートの予定時刻（まだ結果がない場合）または発生時刻から、原作の経路での発生時刻を引いたもの。
    """
    b = spec["beat"]
    now = ctx.state()["schedule"].get(b)
    if now is None:
        now = ctx.beat_time(b)
    if now is None:
        return f"{b} has no scheduled time and did not happen / {b} に予定時刻がなく、発生もしていない"
    canon = ctx.world.canon_times(ctx.role).get(b)
    if canon is None:
        return (
            f"{b} does not happen on the canon path, so the shift cannot be computed"
            f" / {b} は原作の経路で発生しないため、ずれを計算できない"
        )
    shift = now - canon
    if shift == spec["equals"]:
        return None
    return (
        f"{b} shifted by {shift} min (t={now}, canon t={canon}), expected {spec['equals']}"
        f" / {b} が {shift} 分ずれた（t={now}、原作 t={canon}）、期待値 {spec['equals']}"
    )


def check_promise(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """Find the promise by template or by from + to; when there are several, look at the one made last.

    テンプレートまたは from + to で約束を探す。複数あるときは最後に立てたものを見る。
    """
    ps = list((ctx.state().get("promises") or {}).values())
    if "template" in spec:
        ps = [p for p in ps if p.get("template") == spec["template"]]
    else:
        ps = [p for p in ps if p.get("from") == spec["from"] and p.get("to") == spec["to"]]
    if not ps:
        return "No such promise / その約束がない"
    got = ps[-1].get("status")
    if got == spec["status"]:
        return None
    pid = ps[-1].get("promiseId")
    return f"Promise {pid} is {got}, expected {spec['status']} / 約束 {pid} は {got}、期待値 {spec['status']}"


def check_clock_advanced(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    n = spec.get("step", ctx.last_to())
    got: int = ctx.value(n, "clockMinutes")
    ok = spec["min"] <= got <= spec["max"]
    if ok:
        return None
    return (
        f"The clock advanced {got} min at step {n}, expected {spec['min']}–{spec['max']}"
        f" / ステップ {n} で時計が {got} 分進んだ、期待値 {spec['min']}〜{spec['max']}"
    )


NO_ENDING = (
    "Did not reach an ending (the backend's ending() returned None)"
    " / 結末に入らなかった（バックエンドの ending() が None を返した）"
)


def check_outcome(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    got = end["world"]["outcome"]
    return None if got == spec["world"] else f"The world ending is {got}, expected / 期待値 {spec['world']}"


# ---------- Memory, utterances, deletion / 記憶、原文、削除 ----------


def check_memory(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    mems = [m for m in ctx.query("memories", spec["character"]) if not m.get("deletedAt")]
    if "fromStep" in spec:
        ids = ctx.committed_ids(spec["fromStep"])
        mems = [m for m in mems if ids & set(m.get("fromEvents", []))]
    if "kind" in spec:
        mems = [m for m in mems if m.get("kind") == spec["kind"]]
    if bool(mems) == spec["exists"]:
        return None
    if spec["exists"]:
        return f"{spec['character']} has no such memory / {spec['character']} にそのような記憶がない"
    kept = [m.get("memoryId") for m in mems]
    return f"{spec['character']} still remembers / {spec['character']} はまだ覚えている: {kept}"


def check_trust(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    got = ctx.query("trust", spec["character"])
    if got == spec["equals"]:
        return None
    c = spec["character"]
    return f"{c}'s trust is {got}, expected {spec['equals']} / {c} の信頼は {got}、期待値 {spec['equals']}"


def check_utterance_cleared(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    if ctx.query("utterance_cleared", spec["step"]) is True:
        return None
    n = spec["step"]
    return f"The utterances of step {n} were not cleared / ステップ {n} の原文が消去されていない"


def check_db_absent(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    rows = ctx.query("db_absent", tuple(spec["tables"]))
    left = {t: rows.get(t) for t in spec["tables"] if rows.get(t) != 0}
    if not left:
        return None
    return (
        "Still found after deleting the whole game (table → rows, None = the backend did not report this table)"
        f" / 局全体の削除後も見つかる（テーブル → 行数、None = バックエンドがこのテーブルを返さなかった）: {left}"
    )


def check_no_pii(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    scope = spec["scope"]
    texts: dict[str, list[str]] = {}
    if scope in ("memory", "all"):
        texts["memory / 記憶"] = [m.get("text") or "" for c in ctx.world.characters for m in ctx.query("memories", c)]
    if scope in ("summary", "all"):
        texts["event summary / イベントの要約"] = [e.get("summary") or "" for e in ctx.events()]
    if scope in ("ending", "all"):
        end = ctx.query("ending")
        if end is None and scope == "ending":
            return NO_ENDING
        # scope all: with no ending, look only at memory and summaries / scope all：結末がなければ記憶と要約だけを見る
        texts["ending / 結末"] = ending_texts(end) if end is not None else []
    hit = {where: s for where, xs in texts.items() for s in spec["strings"] if any(s in x for x in xs)}
    return f"Personal information appears in / 個人情報の出現箇所: {hit}" if hit else None


# ---------- Situations in dialogue / 会話の中のいくつかの状況 ----------


def check_followup_questions(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    got: int = ctx.value(spec["after"], "followups")
    if got <= spec["max"]:
        return None
    return (
        f"The character asked {got} follow-up questions after silence, at most {spec['max']}"
        f" / 沈黙の後に人物が {got} 回追問した、上限 {spec['max']}"
    )


def check_safety_card(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """shown: true also needs: the story is paused, the player can return to the story, that turn committed no event,
    and the utterances are cleared (no event means no memory).

    shown: true ではさらに次が必要：物語が一時停止している、物語に戻れる、そのターンにコミットされたイベントがない、
    原文が消去されている（イベントがなければ記憶もない）。
    """
    cards = {n: r["safetyCard"] for n, r in enumerate(ctx.results, 1) if "safetyCard" in r}
    if not cards:
        raise not_implemented("StepResult.safetyCard")
    shown = [n for n, c in cards.items() if c["shown"]]
    if not spec["shown"]:
        return f"A crisis card appeared at steps {shown} / ステップ {shown} で危機カードが出た" if shown else None
    if not shown:
        return "No crisis card appeared / 危機カードが出なかった"
    bad = []
    for n in shown:
        c = cards[n]
        if not c["paused"]:
            bad.append(f"step {n}: the story did not pause / ステップ {n}：物語が一時停止しなかった")
        if not c["canReturn"]:
            bad.append(f"step {n}: cannot return to the story / ステップ {n}：物語に戻れない")
        evs = [e for e in ctx.step_events(n) if committed(e)]
        if evs:
            bad.append(f"step {n}: committed events / ステップ {n}：イベントをコミットした: {describe(evs)}")
        if ctx.query("utterance_cleared", n) is not True:
            bad.append(f"step {n}: utterances not cleared / ステップ {n}：原文が消去されていない")
    return "; ".join(bad) or None


def check_act_plan(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """Goes ahead: there is one act-transition by the player with a plan and without exitId, toAct / place match the
    expectation, and plan.label does not quote verbatim. Does not go ahead: no act-transition by the player, and the
    backend returned alternative destinations.

    成立：プレイヤーの act-transition が 1 つあり、plan 付きで exitId がなく、toAct / place が期待どおりで、
    plan.label が逐語引用していない。不成立：プレイヤーの act-transition がなく、バックエンドが代わりの行き先を返した。
    """
    props = [n for n, s in enumerate(ctx.steps, 1) if step_kind(s) == "propose"]
    moves = [
        e
        for n in props
        for e in ctx.step_events(n)
        if committed(e) and e.get("type") == "act-transition" and e.get("actor") == "player"
    ]
    if not spec["accepted"]:
        if moves:
            return (
                "Should not go ahead, yet an act transition was written"
                f" / 成立すべきでないのに幕の切り替えが書かれた: {describe(moves)}"
            )
        alts = [a for n in props for a in ctx.value(n, "alternatives")]
        return None if alts else "No alternative destination was returned / 代わりの行き先が返されなかった"
    plans = [e for e in moves if e.get("plan") and not e.get("exitId")]
    if not plans:
        return (
            "No act transition by the player with a plan and without exitId"
            f" / プレイヤーによる plan 付き・exitId なしの幕の切り替えがない; present / あるもの: {describe(moves)}"
        )
    plan = plans[-1]["plan"]
    for k in ("toAct", "place"):
        if k in spec and plan.get(k) != spec[k]:
            return f"plan.{k} is {plan.get(k)}, expected {spec[k]} / plan.{k} は {plan.get(k)}、期待値 {spec[k]}"
    quoted = verbatim(plan.get("label", ""), ctx.player_lines(), ctx.world.nouns)
    if not quoted:
        return None
    return f"plan.label quotes the player's words verbatim / plan.label がプレイヤーの言葉を逐語引用した: 「{quoted}」"


# ---------- E7 and endings / E7 と結末 ----------


def check_replay_equal(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """Replaying the event log from the opening state in seq order (W-1's apply) equals the backend's WorldState;
    asOfSeq is the seq of the last event.

    イベントログを開始状態から seq 順にリプレイした結果（W-1 の apply）がバックエンドの WorldState と等しい。asOfSeq は
    最後のイベントの seq。
    """
    evs, st = ctx.events(), ctx.state()
    want = world_state(ctx.world.raw, ctx.fold(evs), st["playthroughId"])
    want["asOfSeq"] = evs[-1]["seq"] if evs else 0
    diff = [k for k in want if want[k] != st.get(k)]
    if not diff:
        return None
    first = diff[0]
    return (
        f"Fields where the replay differs from the cache / リプレイとキャッシュで異なるフィールド: {diff}; {first}:"
        f" replay / リプレイ {_short(want[first])}, cache / キャッシュ {_short(st.get(first))}"
    )


def _short(x: Json) -> str:
    s = json.dumps(x, ensure_ascii=False, sort_keys=True)
    return s if len(s) <= 200 else s[:200] + "…"


def check_t_monotonic(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    evs = ctx.events()
    for a, b in zip(evs, evs[1:], strict=False):
        if b["seq"] <= a["seq"]:
            return f"seq does not strictly increase / seq が厳密に増加していない: {a['seq']} → {b['seq']}"
        if b["t"] < a["t"]:
            return f"t goes backwards / t が逆行した: seq {a['seq']} t={a['t']} → seq {b['seq']} t={b['t']}"
    if evs and evs[0]["seq"] != 1:
        return f"seq does not start at 1 / seq が 1 から始まらない: {evs[0]['seq']}"
    return None


def check_outcome_consistent(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    got = end["world"]["outcome"]
    want = classify(ctx.world.raw, ctx.fold(ctx.events()))
    if got == want:
        return None
    return (
        f"The ending says {got}, but the final state classifies as {want} / 結末は {got} だが、最終状態の分類は {want}"
    )


def check_epilogue_cites_valid(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """Every sentence of the epilogue, what was done for you, what you did and the characters' endings cites at least
    one event, and all of them are events of this game.

    エピローグ、あなたのためにしてくれたこと、あなたがしたこと、人物の結末の各文が少なくとも 1 つのイベントを引用し、
    それらがすべてこの局のイベントである。
    """
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    ids = {e.get("eventId") for e in ctx.events()}
    player = end.get("player", {})
    sentences = [
        *player.get("epilogue", []),
        *player.get("didForYou", []),
        *player.get("youDid", []),
        *(y for c in end.get("characters", []) for y in c.get("yours", [])),
    ]
    bad = [s.get("sentence") for s in sentences if not s.get("cites") or set(s["cites"]) - ids]
    if not bad:
        return None
    return f"No citation, or cites events not in this game / 引用がないか、この局にないイベントを引用している: {bad}"


def check_no_verbatim_quotes(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    lines = ctx.player_lines()
    for text in ending_texts(end):
        quoted = verbatim(text, lines, ctx.world.nouns)
        if quoted:
            return (
                f"The ending quotes the player's words verbatim / 結末がプレイヤーの言葉を逐語引用した: 「{quoted}」"
                f" (in / 箇所: 「{text}」)"
            )
    return None


def check_director_not_sole_cause(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """S-045: for the event that moves Melos's expected arrival across the sunset line (in time → too late), the cause
    chain (the events in causes, followed upwards) must contain a player act: actor = player, or coming from a player
    turn or a player action (origin = turn / action).
    Whether he is in time follows W-1's prediction: settling to the end after this event, does the beat the deadline
    watches (watchBeat) happen.

    S-045：メロスの到着予定が日没ラインを越える（間に合う → 間に合わない）イベントについて、原因の連鎖（causes の
    イベントを上へたどる）にプレイヤーの行動がなければならない：actor = player、またはプレイヤーのターンやアクション
    から来たもの（origin = turn / action）。
    間に合うかどうかは W-1 の予測に従う：このイベントの後に最後まで決着させて、期限が見ているビート（watchBeat）が
    発生するかどうか。
    """
    wb = ctx.world.watch_beat
    if wb is None:
        return None
    evs = ctx.events()
    by_id = {e["eventId"]: e for e in evs if e.get("eventId")}
    s = initial_state(ctx.world.raw, ctx.role)

    def in_time(state: SimState) -> bool:
        return settle(ctx.world.raw, state, None)[1]["beats"].get(wb) in OCCURRED

    before, bad = in_time(s), []
    for e in evs:
        s = apply(ctx.world.raw, s, e)
        now = in_time(s)
        if before and not now and not any(_by_player(x) for x in _ancestors(e, by_id)):
            bad.append(e)
        before = now
    if not bad:
        return None
    return (
        "No player act on the cause chain of crossing the sunset line"
        f" / 日没ラインを越えた原因の連鎖にプレイヤーの行動がない: {describe(bad)}"
    )


def _by_player(e: Event) -> bool:
    return e.get("actor") == "player" or e.get("origin") in ("turn", "action")


def _ancestors(e: Event, by_id: Mapping[str, Event]) -> list[Event]:
    out, todo, seen = [e], list(e.get("causes") or []), set()
    while todo:
        c = todo.pop()
        # beat IDs and IDs not in this game are not followed / ビートの ID とこの局にない ID はたどらない
        if c in seen or c not in by_id:
            continue
        seen.add(c)
        out.append(by_id[c])
        todo.extend(by_id[c].get("causes") or [])
    return out


CHECKS: dict[str, Check] = {
    "japanese": check_japanese,
    "not_mention_fact": check_not_mention_fact,
    "no_terms": check_no_terms,
    "terms_any": check_terms_any,
    "event": check_event,
    "no_event": check_no_event,
    "world_unchanged": check_world_unchanged,
    "event_exists": check_event_exists,
    "var": check_var,
    "beat": check_beat,
    "schedule_shift": check_schedule_shift,
    "promise": check_promise,
    "clock_advanced": check_clock_advanced,
    "outcome": check_outcome,
    "memory": check_memory,
    "trust": check_trust,
    "utterance_cleared": check_utterance_cleared,
    "db_absent": check_db_absent,
    "no_pii": check_no_pii,
    "followup_questions": check_followup_questions,
    "safety_card": check_safety_card,
    "act_plan": check_act_plan,
    "replay_equal": check_replay_equal,
    "t_monotonic": check_t_monotonic,
    "outcome_consistent": check_outcome_consistent,
    "epilogue_cites_valid": check_epilogue_cites_valid,
    "no_verbatim_quotes": check_no_verbatim_quotes,
    "director_not_sole_cause": check_director_not_sole_cause,
}
