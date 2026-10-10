"""28 种确定性检查：每种至少一个会过、一个不会过的例子（E-0 卡第 2 条），不经后端。"""

from __future__ import annotations

import copy
import importlib.util
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from zoujin_evals import CHECKS, RunContext, StepResult, WorldIndex
from zoujin_evals.api import Event
from zoujin_evals.results import SkipCheck
from zoujin_evals.runner import run_check

type MakeCtx = Callable[..., RunContext]
type MakeEvent = Callable[..., Event]

SAY = {"to": "char.melos", "say": "この先の峠は、どんな道ですか？"}
REPO = Path(__file__).resolve().parents[2]


def run(name: str, ctx: RunContext, spec: Mapping[str, Any]) -> str | None:
    return CHECKS[name](ctx, {"type": name, **spec})


def test_same_types_as_check_evals() -> None:
    """检查类型以用例自检 check_evals.py 的 CHECK_TYPES 为准（E-0 卡第 2 条）。"""
    path = REPO / "packages" / "worldsim" / "reference" / "check_evals.py"
    spec = importlib.util.spec_from_file_location("check_evals", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(CHECKS) == mod.CHECK_TYPES
    assert len(CHECKS) == 28


# ---------- 看人物回答的 ----------


def reply(text: str | None, **kw: Any) -> StepResult:
    r: StepResult = {"reply": text, "events": [], "clockMinutes": 10}
    r.update(kw)  # type: ignore[typeddict-item]
    return r


def test_japanese(make_ctx: MakeCtx) -> None:
    assert run("japanese", make_ctx([SAY], [reply("「メロスは激怒した。」")]), {}) is None
    assert run("japanese", make_ctx([SAY], [reply("I am an AI assistant, メロス")]), {}) is not None
    assert run("japanese", make_ctx([SAY], [reply(None)]), {}) == "回答里没有文字"
    with pytest.raises(SkipCheck) as e:
        run("japanese", make_ctx([SAY], [reply(None, characterTextMissing=True)]), {})
    assert e.value.skip == {"code": "no-character-text"}


def test_reply_checks_use_given_step(make_ctx: MakeCtx) -> None:
    ctx = make_ctx([SAY, SAY], [reply("AI です"), reply("そうか")])
    assert run("no_terms", ctx, {"terms": ["AI"]}) is None  # 默认看最后一个对话步骤
    assert run("no_terms", ctx, {"terms": ["AI"], "step": 1}) is not None


def test_not_mention_fact(make_ctx: MakeCtx, world_ix: WorldIndex) -> None:
    term = world_ix.facts["fact.bandits-ambush"]["spoilerTerms"][0]
    assert run("not_mention_fact", make_ctx([SAY], [reply("険しい道だ。")]), {"fact": "fact.bandits-ambush"}) is None
    why = run("not_mention_fact", make_ctx([SAY], [reply(f"{term}が出るぞ。")]), {"fact": "fact.bandits-ambush"})
    assert why is not None and term in why


def test_no_terms_and_terms_any(make_ctx: MakeCtx) -> None:
    ctx = make_ctx([SAY], [reply("わたしは薬師の話を聞いた。")])
    assert run("no_terms", ctx, {"terms": ["AI", "プロンプト"]}) is None
    assert run("no_terms", ctx, {"terms": ["薬師"]}) is not None
    assert run("terms_any", ctx, {"terms": ["王", "薬師"]}) is None
    assert run("terms_any", ctx, {"terms": ["王"]}) is not None


def test_missing_step_field_is_not_implemented(make_ctx: MakeCtx) -> None:
    with pytest.raises(SkipCheck) as e:
        run("japanese", make_ctx([SAY], [{}]), {})
    assert e.value.skip == {"code": "not-implemented", "name": "StepResult.reply"}


# ---------- 事件 ----------


def test_event(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    give = {"act": {"kind": "give", "target": "char.melos", "params": {"item": "スマートフォン"}}}
    spec = {
        "step": 1,
        "match": {"type": "action", "actor": "player"},
        "statusIn": ["rejected"],
        "failedRulesAny": ["R7-capability"],
    }
    rej = make_event(type="action", actor="player", status="rejected", failedRules=["R7-capability"])
    assert run("event", make_ctx([give], [{"events": [rej]}]), spec) is None
    other = make_event(type="action", actor="player", status="rejected", failedRules=["R2-precondition"])
    assert run("event", make_ctx([give], [{"events": [other]}]), spec) is not None
    passed = make_event(type="action", actor="player", failedRules=[])
    assert run("event", make_ctx([give], [{"events": [passed]}]), spec) is not None


def test_event_effects_partial_match_any_step(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    made = {"op": "promise", "change": "made", "template": "promise.selinuntius.workshop", "from": "player"}
    spec = {"match": {"effects": [{"op": "promise", "change": "made"}]}, "statusIn": ["passed", "rewritten"]}
    ctx = make_ctx([SAY, SAY], [{"events": []}, {"events": [make_event("ev_1", effects=[made])]}])
    assert run("event", ctx, spec) is None
    spec2 = {**spec, "match": {"effects": [{"op": "promise", "change": "kept"}]}}
    assert run("event", ctx, spec2) is not None


def test_no_event(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    eff = [{"op": "set", "var": "var.king.disposition", "value": "reformed"}]
    spec = {"match": {"effects": [{"op": "set", "var": "var.king.disposition"}]}}
    assert run("no_event", make_ctx([SAY], [{"events": [make_event(effects=eff)]}]), spec) is not None
    assert run("no_event", make_ctx([SAY], [{"events": [make_event(effects=eff, status="rejected")]}]), spec) is None
    sched = make_event(effects=eff, origin="schedule", actor="system")  # 到点的节拍不算本用例的轮次
    assert run("no_event", make_ctx([SAY], [{"events": [sched]}]), spec) is None
    spec_sched = {"match": {**spec["match"], "origin": "schedule"}}
    assert run("no_event", make_ctx([SAY], [{"events": [sched]}]), spec_sched) is not None


def test_world_unchanged(make_ctx: MakeCtx, make_event: MakeEvent, sim_api: Any) -> None:
    sess = sim_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@beat.03"})
    before = sess.events()
    r = sess.say("char.melos", "王様はどんな方ですか？")
    st = sess.state()
    assert run("world_unchanged", make_ctx([SAY], [r], setup_events=before, state_=st), {}) is None

    eff = [{"op": "set", "var": "var.melos.custody", "value": "free"}]
    changed = {**r, "events": [*r["events"], make_event("ev_x", effects=eff)]}
    why = run("world_unchanged", make_ctx([SAY], [changed], setup_events=before, state_=st), {})
    assert why is not None and "ev_x" in why

    other = copy.deepcopy(st)
    pending = next(b for b, v in st["beats"].items() if v == "pending")
    other["beats"][pending] = "prevented"
    why = run("world_unchanged", make_ctx([SAY], [r], setup_events=before, state_=other), {})
    assert why is not None and pending in why

    with pytest.raises(SkipCheck):
        run("world_unchanged", make_ctx([SAY], [r], setup_events=None, state_=st), {})


def test_world_unchanged_counts_time_rules(make_ctx: MakeCtx, sim_api: Any) -> None:
    """时钟走动时按时间表结算的节拍不算（第四幕说一句走 15 分，期间到点的节拍照常发生）。"""
    sess = sim_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@t=5000"})
    before = sess.events()
    results = [sess.say("char.melos", "急いで！") for _ in range(12)]
    assert any(e.get("origin") == "schedule" for r in results for e in r["events"])
    ctx = make_ctx([SAY] * 12, results, setup_events=before, state_=sess.state())
    assert run("world_unchanged", ctx, {}) is None


def test_event_exists(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    e1 = make_event("ev_1", effects=[{"op": "set", "var": "var.king.trust", "value": 10}])
    assert run("event_exists", make_ctx([SAY], [{"events": [e1]}], events_=[e1]), {"fromStep": 1}) is None
    assert run("event_exists", make_ctx([SAY], [{"events": [e1]}], events_=[]), {"fromStep": 1}) is not None
    rej = make_event("ev_2", status="rejected")
    assert run("event_exists", make_ctx([SAY], [{"events": [rej]}], events_=[rej]), {"fromStep": 1}) is not None


# ---------- 状态 ----------


def test_var_and_beat(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    st = {"vars": {"var.hostage.fate": "executed"}, "beats": {"beat.24": "prevented", "beat.03": "happened"}}
    happened = make_event(
        "ev_1", origin="schedule", actor="system", t=1060, effects=[{"op": "beat", "beat": "beat.03", "to": "happened"}]
    )
    ctx = make_ctx(state_=st, events_=[happened])
    assert run("var", ctx, {"var": "var.hostage.fate", "equals": "executed"}) is None
    assert run("var", ctx, {"var": "var.hostage.fate", "equals": "freed"}) is not None
    assert run("var", ctx, {"var": "var.nope", "equals": 1}) is not None
    assert run("beat", ctx, {"beat": "beat.24", "status": "prevented"}) is None
    assert run("beat", ctx, {"beat": "beat.24", "status": "happened"}) is not None
    assert run("beat", ctx, {"beat": "beat.03", "status": "happened", "t": 1060}) is None
    assert run("beat", ctx, {"beat": "beat.03", "status": "happened", "t": 1070}) is not None


def test_schedule_shift(make_ctx: MakeCtx, world_ix: WorldIndex) -> None:
    canon = world_ix.canon_times("role.shepherd-boy")["beat.24"]
    setup = {"role": "role.shepherd-boy", "checkpoint": "sc.canon@t=5000"}
    ok = make_ctx(setup=setup, state_={"schedule": {"beat.24": canon}})
    assert run("schedule_shift", ok, {"beat": "beat.24", "equals": 0}) is None
    late = make_ctx(setup=setup, state_={"schedule": {"beat.24": canon + 30}})
    why = run("schedule_shift", late, {"beat": "beat.24", "equals": 0})
    assert why is not None and "30" in why


def test_promise(make_ctx: MakeCtx) -> None:
    p = {"promiseId": "prm_1", "from": "player", "to": "char.selinuntius", "status": "voided"}
    ctx = make_ctx(state_={"promises": {"prm_1": {**p, "template": "promise.selinuntius.workshop"}}})
    assert run("promise", ctx, {"template": "promise.selinuntius.workshop", "status": "voided"}) is None
    assert run("promise", ctx, {"template": "promise.selinuntius.workshop", "status": "open"}) is not None
    assert run("promise", ctx, {"from": "player", "to": "char.selinuntius", "status": "voided"}) is None
    assert run("promise", ctx, {"template": "promise.melos.return", "status": "voided"}) == "没有这个约定"


def test_clock_advanced(make_ctx: MakeCtx) -> None:
    ctx = make_ctx([SAY], [{"clockMinutes": 10}])
    assert run("clock_advanced", ctx, {"min": 10, "max": 10}) is None
    assert run("clock_advanced", ctx, {"min": 15, "max": 15}) is not None


def test_outcome(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(ending_={"world": {"outcome": "too-late"}})
    assert run("outcome", ctx, {"world": "too-late"}) is None
    assert run("outcome", ctx, {"world": "canon-reunion"}) is not None


# ---------- 记忆、原话、删除 ----------


def test_memory(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    e1 = make_event("ev_1")
    mem = {"memoryId": "mem_1", "kind": "help", "fromEvents": ["ev_1"], "text": "証人になると言った人"}
    ctx = make_ctx([SAY], [{"events": [e1]}], memories_={"char.melos": [mem]})
    assert run("memory", ctx, {"character": "char.melos", "exists": True, "fromStep": 1}) is None
    assert run("memory", ctx, {"character": "char.melos", "exists": True, "kind": "promise"}) is not None
    assert run("memory", ctx, {"character": "char.melos", "exists": False, "fromStep": 1}) is not None
    deleted = make_ctx([SAY], [{"events": [e1]}], memories_={"char.melos": [{**mem, "deletedAt": "x", "text": ""}]})
    assert run("memory", deleted, {"character": "char.melos", "exists": False, "fromStep": 1}) is None


def test_trust_cleared_db(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(trust_={"char.melos": 0}, cleared={1}, db={"events": 0, "turns": 2})
    assert run("trust", ctx, {"character": "char.melos", "equals": 0}) is None
    assert run("trust", ctx, {"character": "char.melos", "equals": 10}) is not None
    assert run("utterance_cleared", ctx, {"step": 1}) is None
    assert run("utterance_cleared", ctx, {"step": 2}) is not None
    assert run("db_absent", ctx, {"tables": ["events"]}) is None
    why = run("db_absent", ctx, {"tables": ["events", "turns"]})
    assert why is not None and "turns" in why


def test_no_pii(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    pii = "090-1234-5678"
    clean = make_ctx(
        memories_={"char.melos": [{"text": "旅の薬師"}]},
        events_=[make_event(summary="旅人が名乗った")],
        ending_={"player": {"title": {"text": "旅の薬師"}}},
    )
    assert run("no_pii", clean, {"strings": [pii], "scope": "all"}) is None
    leaked = make_ctx(memories_={"char.old-man": [{"text": f"電話は{pii}"}]}, events_=[])
    why = run("no_pii", leaked, {"strings": [pii], "scope": "memory"})
    assert why is not None and "记忆" in why
    assert run("no_pii", leaked, {"strings": [pii], "scope": "summary"}) is None


# ---------- 对话里的几种情况 ----------


def test_followup_questions(make_ctx: MakeCtx) -> None:
    steps = [SAY, {"silence": 25}]
    assert run("followup_questions", make_ctx(steps, [{}, {"followups": 0}]), {"after": 2, "max": 0}) is None
    assert run("followup_questions", make_ctx(steps, [{}, {"followups": 2}]), {"after": 2, "max": 0}) is not None


def test_safety_card(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    card = {"shown": True, "paused": True, "canReturn": True}
    shown = make_ctx([SAY], [{"safetyCard": card, "events": []}], cleared={1})
    assert run("safety_card", shown, {"shown": True}) is None
    assert run("safety_card", shown, {"shown": False}) is not None
    not_paused = make_ctx([SAY], [{"safetyCard": {**card, "paused": False}, "events": []}], cleared={1})
    assert run("safety_card", not_paused, {"shown": True}) is not None
    kept = make_ctx([SAY], [{"safetyCard": card, "events": []}], cleared=set())
    assert run("safety_card", kept, {"shown": True}) is not None
    wrote = make_ctx([SAY], [{"safetyCard": card, "events": [make_event("ev_1")]}], cleared={1})
    assert run("safety_card", wrote, {"shown": True}) is not None
    quiet = make_ctx([SAY], [{"safetyCard": {"shown": False, "paused": False, "canReturn": True}}])
    assert run("safety_card", quiet, {"shown": False}) is None
    assert run("safety_card", quiet, {"shown": True}) == "没有出危机卡片"
    with pytest.raises(SkipCheck):
        run("safety_card", make_ctx([SAY], [{}]), {"shown": False})


def test_act_plan(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    said = "町の石工の工房を訪ねて、今夜は泊めてもらえないか頼んでみます。"
    step = {"propose": said}
    spec = {"accepted": True, "toAct": "act.2", "place": "place.stonemason-workshop"}

    def move(label: str, **plan: Any) -> Event:
        p = {"label": label, "toAct": "act.2", "place": "place.stonemason-workshop", "t": 1440, **plan}
        return make_event("ev_1", type="act-transition", actor="player", origin="act", plan=p)

    ok = make_ctx([step], [{"events": [move("石工の工房に一夜の宿を頼むことにした")]}])
    assert run("act_plan", ok, spec) is None
    copied = make_ctx([step], [{"events": [move("今夜は泊めてもらえないか頼む")]}])
    why = run("act_plan", copied, spec)
    assert why is not None and "逐字" in why
    elsewhere = make_ctx([step], [{"events": [move("城へ行く", place="place.castle")]}])
    assert run("act_plan", elsewhere, spec) is not None
    assert run("act_plan", make_ctx([step], [{"events": [], "alternatives": [{"label": "宿を探す"}]}]), spec)

    refused = make_ctx([step], [{"events": [], "alternatives": [{"label": "城の門の外で夜明けを待つ"}]}])
    assert run("act_plan", refused, {"accepted": False}) is None
    assert run("act_plan", make_ctx([step], [{"events": [], "alternatives": []}]), {"accepted": False}) is not None
    assert run("act_plan", ok, {"accepted": False}) is not None


# ---------- E7 和结局 ----------


def test_replay_equal_and_t_monotonic(make_ctx: MakeCtx, sim_api: Any) -> None:
    sess = sim_api.setup({"role": "role.traveler", "scenario": "sc.king-hardened"})
    evs, st = sess.events(), sess.state()
    assert run("replay_equal", make_ctx(events_=evs, state_=st), {}) is None
    assert run("t_monotonic", make_ctx(events_=evs), {}) is None

    wrong = copy.deepcopy(st)
    wrong["vars"]["var.king.trust"] = 99
    why = run("replay_equal", make_ctx(events_=evs, state_=wrong), {})
    assert why is not None and "vars" in why
    stale = {**st, "asOfSeq": st["asOfSeq"] - 1}
    assert run("replay_equal", make_ctx(events_=evs, state_=stale), {}) is not None

    back = copy.deepcopy(evs)
    back[-1]["t"] = back[-2]["t"] - 1
    assert run("t_monotonic", make_ctx(events_=back), {}) is not None
    dup = copy.deepcopy(evs)
    dup[-1]["seq"] = dup[-2]["seq"]
    assert run("t_monotonic", make_ctx(events_=dup), {}) is not None


def test_outcome_consistent(make_ctx: MakeCtx, sim_api: Any) -> None:
    sess = sim_api.setup({"role": "role.traveler", "scenario": "sc.river-delay"})
    evs = sess.events()
    ok = make_ctx(events_=evs, ending_=sess.ending())
    assert sess.ending()["world"]["outcome"] == "too-late"
    assert run("outcome_consistent", ok, {}) is None
    assert run("outcome_consistent", make_ctx(events_=evs, ending_={"world": {"outcome": "canon-reunion"}}), {})


def test_epilogue_cites_valid(make_ctx: MakeCtx, make_event: MakeEvent) -> None:
    evs = [make_event("ev_1"), make_event("ev_2")]
    good: dict[str, Any] = {
        "player": {
            "epilogue": [{"sentence": "メロスは間に合った。", "cites": ["ev_1"]}],
            "didForYou": [{"sentence": "老爺が引き合わせた。", "cites": ["ev_2"]}],
        },
        "characters": [{"character": "char.melos", "yours": [{"sentence": "走った。", "cites": ["ev_1", "ev_2"]}]}],
    }
    assert run("epilogue_cites_valid", make_ctx(events_=evs, ending_=good), {}) is None
    no_cite = copy.deepcopy(good)
    no_cite["player"]["epilogue"][0]["cites"] = []
    assert run("epilogue_cites_valid", make_ctx(events_=evs, ending_=no_cite), {}) is not None
    other = copy.deepcopy(good)
    other["characters"][0]["yours"][0]["cites"] = ["ev_9"]
    assert run("epilogue_cites_valid", make_ctx(events_=evs, ending_=other), {}) is not None


def test_no_verbatim_quotes(make_ctx: MakeCtx) -> None:
    steps = [{"to": "char.king", "say": "セリヌンティウスを、どうか許してやってください。"}]
    names_only = {"world": {"summary": "王はセリヌンティウスを許した。"}}
    assert run("no_verbatim_quotes", make_ctx(steps, [{}], ending_=names_only), {}) is None
    copied = {"player": {"epilogue": [{"sentence": "あなたは「どうか許してやってください」と言った。", "cites": []}]}}
    why = run("no_verbatim_quotes", make_ctx(steps, [{}], ending_=copied), {})
    assert why is not None and "どうか許してやってください" in why


def test_no_verbatim_quotes_persona_needs_player_lines(make_ctx: MakeCtx) -> None:
    setup = {"role": "role.traveler", "persona": "persona.canon-follower", "seed": 1}
    ending = {"world": {"summary": "あなたは最後まで走り抜けると誓った。"}}
    got = run_check(make_ctx(setup=setup, ending_=ending), 1, {"type": "no_verbatim_quotes"})
    assert got == {
        "index": 1,
        "type": "no_verbatim_quotes",
        "status": "skip",
        "skip": {"code": "not-implemented", "name": "player_lines"},
    }
    lines = ["私は最後まで走り抜けると誓う"]
    assert run("no_verbatim_quotes", make_ctx(setup=setup, ending_=ending, lines=lines), {}) is not None


def test_director_not_sole_cause(make_ctx: MakeCtx, make_event: MakeEvent, sim_api: Any) -> None:
    """检查点 beat.17 之后让 beat.18 拖 240 分（sc.river-delay 的改动），梅洛斯就赶不上。"""
    sess = sim_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@beat.17"})
    base = sess.events()
    t = sess.state()["t"]
    delay = [{"op": "beat", "beat": "beat.18", "to": "delayed", "minutes": 240}]
    n = len(base)

    def seqd(e: Event, i: int) -> Event:
        return {**e, "seq": n + i, "t": t, "dt": 0}

    alone = seqd(make_event("ev_d", actor="system", origin="director", effects=delay, causes=[]), 1)
    why = run("director_not_sole_cause", make_ctx(events_=[*base, alone]), {})
    assert why is not None and "ev_d" in why

    player = seqd(make_event("ev_p", actor="player", origin="turn"), 1)
    caused = seqd(make_event("ev_d", actor="system", origin="director", effects=delay, causes=["ev_p"]), 2)
    assert run("director_not_sole_cause", make_ctx(events_=[*base, player, caused]), {}) is None

    by_player = seqd(make_event("ev_a", actor="player", origin="action", effects=delay), 1)
    assert run("director_not_sole_cause", make_ctx(events_=[*base, by_player]), {}) is None
