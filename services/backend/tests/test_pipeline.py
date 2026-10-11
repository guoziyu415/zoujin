"""叙事者流水线第 1〜5 步（B-2 验收第 2、3、4 组）：假模型 + 规则，不要数据库（起点在内存里推，同 test_rules）。

台词、摘要和即兴设定都是为测试写的，不取自 S-2 的样例和留出集。
"""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from zoujin_backend.clock import PART_OF_DAY, Labels
from zoujin_backend.config import DEADLINES
from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import BudgetStop, FakeText, RateLimited, TextResult, canonical
from zoujin_backend.narrator import rules
from zoujin_backend.narrator.pipeline import Counts, Extracted, Pipeline, Spend, TurnInput, Verified
from zoujin_backend.narrator.view import aliases, situation, state_view
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book
from zoujin_worldsim import SimState

from .conftest import SCHEMAS
from .test_rules import BOOK, OLD, at, cand

Json = Any

LINE = "こんばんは。この辺りに宿はありますか。"
REPLY = "……旅の方か。宿なら、広場の向こうにございます。"
TURN = TurnInput(character=OLD, player=LINE, reply=REPLY)
MINUTES = 10


def c(summary: str, effects: Sequence[Json], actor: str = OLD, **kw: Any) -> Json:
    return {"actor": actor, "type": "say", "summary": summary, "effects": list(effects), "needsConfirm": False, **kw}


IMPROV = c(
    "老爺は、若いころ羊を追っていたと話した",
    [{"op": "improv", "character": OLD, "statement": "老爺は昔、羊飼いだった"}],
)
TELL = c(
    "旅人は老爺に、村の牧人の話をした", [{"op": "learn", "character": OLD, "fact": "fact.melos-shepherd"}], "player"
)
PROMISE = c(
    "旅人は老爺を家まで送ると申し出た",
    [{"op": "promise", "change": "made", "from": "player", "to": OLD, "text": "家まで送る"}],
    "player",
)
LEND = c("旅人は老爺に外套を貸した", [{"op": "hold", "item": "item.cloak", "to": OLD, "from": "player"}], "player")
DRAPE = c("旅人は老爺の肩に外套をかけた", [{"op": "hold", "item": "item.cloak", "to": OLD, "from": "player"}], "player")
DOWN = c(
    "老爺は、昔のことを少しだけ話した", [{"op": "improv", "character": OLD, "statement": "老爺は昔、村に住んでいた"}]
)


def extract_rule(*cands: Json) -> Json:
    return {"kind": "extract", "output": {"candidates": list(cands)}}


def pipe(rules_: Sequence[Json] = (), deadlines: Mapping[str, float] | None = None) -> tuple[Pipeline, FakeText]:
    fake = FakeText(rules=list(rules_))
    return Pipeline(fake, SCHEMAS, IdGen(seed=7), Tracer(), dict(deadlines or DEADLINES)), fake


def kinds(fake: FakeText) -> list[str]:
    return [k for k, _ in fake.calls]


def run_turn(p: Pipeline, state: SimState, turn: TurnInput = TURN) -> tuple[Extracted, Verified, Spend]:
    async def go() -> tuple[Extracted, Verified, Spend]:
        spend = Spend()
        ex = await p.extract(BOOK, state, turn, spend)
        if ex.timed_out:
            return ex, Verified([], Counts()), spend
        return ex, await p.verify(BOOK, state, ex.candidates, turn, MINUTES, spend), spend

    return asyncio.run(go())


def statuses(v: Verified) -> list[tuple[str, int, list[str]]]:
    return [(x.check["status"], x.check["attempts"], x.check["failedRules"]) for x in v.checked]


# —— 第 1、2 步 ——


def test_chat_turn_skips_extraction() -> None:
    p, fake = pipe([{"kind": "triage", "output": {"route": "chat"}}])
    ex, v, _ = run_turn(p, at())
    assert kinds(fake) == ["triage"] and ex.candidates == [] and v.checked == []
    assert ex.counts.triage_skipped == 1


def test_extracted_and_all_pass() -> None:
    p, fake = pipe([extract_rule(IMPROV, LEND)])
    ex, v, _ = run_turn(p, at())
    assert kinds(fake) == ["triage", "extract", "check"]  # 两个候选合在一次检查里
    assert statuses(v) == [("passed", 1, []), ("passed", 1, [])]
    assert all("+sonnet-5.5/p" in x.check["checker"] for x in v.checked)
    assert v.checked[0].effects[0]["factId"].startswith("rf_")  # 提交时的 ID 已分配
    (_, check_req) = fake.calls[2]
    assert "factId" not in canonical(check_req) and "rf_" not in canonical(check_req)  # 请求里没有随机的 ID
    assert [x["index"] for x in check_req["candidates"]] == [0, 1]


def test_needs_confirm_drops_only_irreversible_candidates() -> None:
    prevent = c(
        "旅人は老爺を引き止め、メロスに会わせなかった", [{"op": "beat", "beat": "beat.03", "to": "prevented"}], "player"
    )
    custody = c(
        "旅人は自分から警吏に捕まった", [{"op": "set", "var": "var.player.custody", "value": "arrested"}], "player"
    )
    p, _ = pipe(
        [
            extract_rule(
                {**prevent, "needsConfirm": True}, {**custody, "needsConfirm": True}, {**IMPROV, "needsConfirm": True}
            )
        ]
    )
    ex, v, _ = run_turn(p, at())
    assert ex.counts.confirm_dropped == 2 and [x["summary"] for x in ex.candidates] == [IMPROV["summary"]]
    assert statuses(v) == [("passed", 1, [])]


def test_candidates_without_effects_are_not_events() -> None:
    p, _ = pipe([extract_rule(c("老爺はうなずいた", []), IMPROV)])
    ex, _, _ = run_turn(p, at())
    assert [x["summary"] for x in ex.candidates] == [IMPROV["summary"]]


# —— 第 3〜5 步 ——


def test_step3_failure_rewritten_once_then_passes() -> None:
    p, fake = pipe(
        [extract_rule(TELL), {"kind": "rewrite", "when": {"mode": "rewrite"}, "output": {"candidate": PROMISE}}]
    )
    _, v, _ = run_turn(p, at())
    assert statuses(v) == [("rewritten", 2, ["R4-knowledge"])]
    (x,) = v.checked
    assert x.candidate["summary"] == PROMISE["summary"] and x.effects[0]["promiseId"].startswith("prm_")
    assert "知らない" in x.check["reason"]
    assert kinds(fake) == ["triage", "extract", "rewrite", "check"]  # 第 3 步没过的不进第 4 步；改写后的过第 3、4 步
    (_, req) = fake.calls[2]
    assert req["mode"] == "rewrite" and req["failed"][0]["rule"] == "R4-knowledge"


def test_model_check_fails_three_times_then_downgrade_or_reject() -> None:
    sheep = {
        "kind": "check",
        "when": {"summaryContains": "羊を追"},
        "fail": {"rule": "R5-persona", "reason": "老爺らしくない"},
    }
    again = [
        {"kind": "rewrite", "when": {"mode": "rewrite"}, "times": 1, "output": {"candidate": {**IMPROV, "summary": x}}}
        for x in ("老爺は羊を追って暮らしたと話した", "老爺は羊を追った昔を語った")
    ]
    p, fake = pipe(
        [
            extract_rule(IMPROV),
            sheep,
            *again,
            {"kind": "rewrite", "when": {"mode": "downgrade"}, "output": {"candidate": DOWN}},
        ]
    )
    _, v, _ = run_turn(p, at())
    assert statuses(v) == [("downgraded", 3, ["R5-persona"])]
    assert (
        v.checked[0].effects[0]["statement"] == "老爺は昔、村に住んでいた"
        and v.checked[0].check["reason"] == "老爺らしくない"
    )
    assert kinds(fake).count("check") == 4 and kinds(fake).count("rewrite") == 3
    assert v.counts.downgraded == 1

    p, _ = pipe([extract_rule(IMPROV), sheep, *again])  # 降级做不到（假模型的默认）→ 拒绝
    _, v, _ = run_turn(p, at())
    assert statuses(v) == [("rejected", 3, ["R5-persona"])]
    (x,) = v.checked
    assert x.candidate["summary"] == IMPROV["summary"] and x.effects[0]["op"] == "improv"  # 原本的（提交时写空）
    assert not x.passed and x.check["reason"] == "老爺らしくない" and v.counts.rejected == 1


def test_unchanged_rewrite_is_not_checked_again() -> None:
    p, fake = pipe([extract_rule(TELL)])  # 改写原样（默认）、降级做不到
    _, v, _ = run_turn(p, at())
    assert statuses(v) == [("rejected", 3, ["R4-knowledge"])]
    assert kinds(fake) == ["triage", "extract", "rewrite", "rewrite", "rewrite"]
    assert v.checked[0].check["checker"] == rules.CHECKER


def test_earlier_results_change_later_candidates() -> None:
    p, _ = pipe([extract_rule(LEND, DRAPE)])
    _, v, _ = run_turn(p, at())
    assert statuses(v) == [("passed", 1, []), ("rejected", 3, ["R7-capability"])]  # 外套已经借出去了

    lend_fails = {"kind": "check", "when": {"summaryContains": "貸した"}, "fail": {"rule": "R5-persona"}}
    p, fake = pipe([extract_rule(LEND, DRAPE), lend_fails])
    _, v, _ = run_turn(p, at())
    assert statuses(v) == [("rejected", 3, ["R5-persona"]), ("passed", 1, [])]  # 前一个被否决，后一个重判就过了
    checks = [r for k, r in fake.calls if k == "check"]
    assert [len(r["candidates"]) for r in checks] == [1, 1]


def test_model_reason_never_copies_the_player() -> None:
    p, _ = pipe([extract_rule(IMPROV), {"kind": "check", "fail": {"rule": "R6-safety", "reason": f"「{LINE}」"}}])
    _, v, _ = run_turn(p, at())
    assert v.checked[0].check["reason"] == "物語に書けない内容が入っている"


def test_bad_effect_shape_is_r7_not_a_commit_error() -> None:
    odd = c("老爺は何かを知った", [{"op": "learn", "character": OLD, "fact": "fact.city-silent", "note": "x"}])
    p, _ = pipe([extract_rule(odd)])
    _, v, _ = run_turn(p, at())
    assert v.checked[0].check["status"] == "rejected" and v.checked[0].check["failedRules"] == ["R7-capability"]
    ghost = c("誰かが話した", [{"op": "improv", "character": OLD, "statement": "老爺は昔、船乗りだった"}], "narrator")
    p, _ = pipe([extract_rule(ghost)])
    _, v, _ = run_turn(p, at())
    assert v.checked[0].check["failedRules"] == ["R7-capability"]


# —— 别名 ——


def test_promises_and_run_facts_use_aliases_in_requests() -> None:
    s0 = at()
    s = rules.trial(BOOK.world, s0, PROMISE, rules.fill_ids(PROMISE["effects"], IdGen(seed=1)))
    s = rules.trial(BOOK.world, s, IMPROV, rules.fill_ids(IMPROV["effects"], IdGen(seed=2)))
    view = state_view(BOOK, s)
    text = canonical(view.doc)
    assert "prm_" not in text and "rf_" not in text and "prm#1" in text and "rf#1" in text
    real = {v: k for k, v in aliases(s).items()}
    kept = c("旅人は老爺を家まで送り届けた", [{"op": "promise", "change": "kept", "promiseId": "prm#1"}], "player")
    told = c("老爺は旅人に昔話をした", [{"op": "learn", "character": "player", "fact": "rf#1"}])
    p, fake = pipe([extract_rule(kept, told)])
    ex, v, _ = run_turn(p, s)
    assert ex.candidates[0]["effects"][0]["promiseId"] == real["prm#1"]
    assert ex.candidates[1]["effects"][0]["fact"] == real["rf#1"]
    assert statuses(v) == [("passed", 1, []), ("passed", 1, [])]
    (_, check_req) = [x for x in fake.calls if x[0] == "check"][0]
    assert "prm#1" in canonical(check_req) and "prm_" not in canonical(check_req)


# —— 时限 ——

FAST = {**DEADLINES, "triage": 0.05, "extract": 0.05, "check": 0.05, "rewrite": 0.05}
SLOW = 200


def spans(p: Pipeline, name: str) -> list[str]:
    return [s["status"] for s in p.tracer.named(name)]


def test_first_timeout_is_retried() -> None:
    p, fake = pipe([{"kind": "extract", "latencyMs": SLOW, "times": 1}, extract_rule(IMPROV)], FAST)
    ex, v, _ = run_turn(p, at())
    assert spans(p, "narrator.extract") == ["timeout", "ok"] and statuses(v) == [("passed", 1, [])]
    assert not ex.timed_out and ex.counts.timeouts == 0


def test_two_extract_timeouts_leave_only_the_clock() -> None:
    p, fake = pipe([{"kind": "extract", "latencyMs": SLOW}], FAST)
    ex, v, _ = run_turn(p, at())
    assert ex.timed_out and ex.candidates == [] and ex.counts.timeouts == 1
    assert kinds(fake) == ["triage", "extract", "extract"]


def test_two_triage_timeouts_count_as_maybe() -> None:
    p, fake = pipe([{"kind": "triage", "latencyMs": SLOW}, extract_rule(IMPROV)], FAST)
    ex, v, _ = run_turn(p, at())
    assert kinds(fake)[:3] == ["triage", "triage", "extract"] and statuses(v) == [("passed", 1, [])]
    assert ex.counts.timeouts == 0  # 分流超时不算超时降级


def test_two_check_timeouts_drop_the_candidates() -> None:
    p, _ = pipe([extract_rule(IMPROV), {"kind": "check", "latencyMs": SLOW}], FAST)
    _, v, _ = run_turn(p, at())
    assert v.timed_out and v.checked == [] and v.counts.timeouts == 1


def test_invalid_outputs_and_failed_calls_are_retried_once() -> None:
    no_flag = {
        "kind": "extract",
        "times": 1,
        "output": {"candidates": [{k: x for k, x in IMPROV.items() if k != "needsConfirm"}]},
    }
    p, _ = pipe([no_flag, extract_rule(IMPROV)])
    _, v, _ = run_turn(p, at())
    assert spans(p, "narrator.extract") == ["invalid", "ok"] and statuses(v) == [("passed", 1, [])]
    p, _ = pipe([{"kind": "check", "error": "unavailable", "times": 1}, extract_rule(IMPROV)])
    _, v, _ = run_turn(p, at())
    assert spans(p, "narrator.check") == ["error", "ok"]
    missing = {
        "kind": "check",
        "times": 2,
        "output": {"results": [{"index": 0, "rules": [{"rule": "R1-anchor", "status": "pass"}]}]},
    }
    p, _ = pipe([extract_rule(IMPROV), missing])  # 少了规则 = 输出不完整，两次都这样 → 超时降级
    _, v, _ = run_turn(p, at())
    assert spans(p, "narrator.check") == ["invalid", "invalid"] and v.timed_out


def test_rate_limit_and_budget_stop_are_not_retried() -> None:
    p, fake = pipe([{"kind": "triage", "error": "rate-limit"}])
    with pytest.raises(RateLimited):
        run_turn(p, at())
    assert kinds(fake) == ["triage"]

    class Broke:
        mode = "fake"

        async def call(self, kind: str, request: Json) -> TextResult:
            raise BudgetStop("到上限了")

    p = Pipeline(Broke(), SCHEMAS, IdGen())  # type: ignore[arg-type]
    with pytest.raises(BudgetStop):
        run_turn(p, at())


# —— 评测入口的 check()：范围 ——


def check_only(p: Pipeline, state: SimState, cand_: Json, scope: str) -> rules.Checked:
    return asyncio.run(p.check_only(BOOK, state, cand_, TURN, scope, Spend()))


def test_scope_scoped_and_all() -> None:
    s = at()
    clock = cand(s, [])
    bad = cand(s, [{"op": "learn", "character": OLD, "fact": "fact.melos-shepherd"}])
    good = cand(s, [{"op": "learn", "character": OLD, "fact": "fact.city-silent"}])
    for x, scope, called in (
        (clock, "scoped", False),
        (bad, "scoped", False),
        (good, "scoped", True),
        (clock, "all", True),
        (bad, "all", True),
    ):
        p, fake = pipe()
        got = check_only(p, s, x, scope)
        assert (kinds(fake) == ["check"]) is called, (x["effects"], scope)
        r5 = {r["rule"]: r["status"] for r in got.rules}["R5-persona"]
        assert r5 == ("pass" if called else "skipped")
        assert ("+sonnet-5.5/p" in got.check["checker"]) is called


# —— 文字模式的人物回答 ——


def test_reply_request_has_persona_and_situation() -> None:
    p, fake = pipe([{"kind": "reply", "output": {"text": "宿なら向こうにございます。"}}])
    got = asyncio.run(p.reply(BOOK, at(), TurnInput(character=OLD, player=LINE), Spend()))
    assert got == "宿なら向こうにございます。"
    ((_, req),) = fake.calls
    assert req["persona"]["name"] == BOOK.characters[OLD]["name"] and req["player"]["role"] == "role.traveler"
    assert "fact.city-silent" in req["situation"]["knows"] and "char.crowd" not in req["situation"]["present"]
    p, _ = pipe([{"kind": "reply", "error": "invalid"}])
    assert asyncio.run(p.reply(BOOK, at(), TurnInput(character=OLD, player=LINE), Spend())) is None


def test_reply_time_is_band_only_for_who_does_not_know_the_day_names() -> None:
    """S-086：日名带着情节（`clock.labels.daysKnownBy`）时，不知道那条事实的人物只拿到时段；没这个字段时照旧。"""

    def book(by: str | None) -> Book:
        w = copy.deepcopy(BOOK.world)
        w["clock"]["labels"].pop("daysKnownBy", None)
        if by:
            w["clock"]["labels"]["daysKnownBy"] = by
        return Book(BOOK.book_id, w, BOOK.scenes)

    def time(b: Book, s: SimState, who: str) -> str:
        t: str = situation(b, s, who, state_view(b, s))["time"]
        return t

    promise, plain = book("fact.promise"), book(None)
    night, day1 = at(checkpoint="sc.canon@t=1400"), at(checkpoint="sc.canon@t=2000")  # beat.05 之后；beat.06 之后
    assert time(promise, night, "char.king") == time(plain, night, OLD) == "約束の日・夜"
    assert time(promise, night, OLD) == time(promise, night, "char.selinuntius") == "夜"
    assert time(promise, day1, "char.selinuntius") == "一日目・午前" and time(promise, day1, OLD) == "午前"
    assert time(promise, at(), "char.king") == "日没前"  # 约定还没立，谁都不算知道


def test_reply_recent_beats_count_days_from_now() -> None:
    """S-092：局势带他亲历的节拍是什么时候（UX 的说法，一天从夜明け算起，不用日名）；没参与的、更早的不给。"""

    def recent(t: int, who: str) -> list[tuple[str, str]]:
        s = at(checkpoint=f"sc.canon@t={t}")
        return [(x["beat"], x["day"]) for x in situation(BOOK, s, who, state_view(BOOK, s))["recent"]]

    assert recent(1400, "char.king") == [("beat.05", "今夜")] and recent(1400, "char.selinuntius") == []
    assert recent(2000, "char.selinuntius") == [("beat.06", "昨夜")]
    assert recent(3600, "char.selinuntius") == [("beat.06", "おととい")]
    ago = BOOK.labels.ago
    assert ago(1440 + 60, 1410) == "今夜"  # 天亮前的深夜还算前一天
    assert (ago(1440 + 300, 1440 + 600), ago(1440 + 600, 1440 + 700), ago(1440 + 1000, 1440 + 1100)) == (
        "今朝",
        "今日の昼",
        "今日の夕方",
    )
    assert (ago(600, 1440 + 600), ago(1300, 1440 + 600), ago(600, 3 * 1440 + 600)) == ("昨日", "昨夜", "三日前")
    assert ago(10, 6000) is None


def test_part_of_day_covers_every_world() -> None:
    """S-092：worlds/ 下每个世界模型的每个时段名都在 PART_OF_DAY 里，第一段从零点开始、第二段（夜明け）算「朝」；
    数据改了时段名或加了一段先碰到这里。查不到不回退成「今日」，直接报错。"""
    worlds = sorted((Path(__file__).resolve().parents[3] / "worlds").glob("*/*/world.json"))
    assert worlds
    for path in worlds:
        labels = Labels(path)
        assert labels.bands[0][0] == 0 and PART_OF_DAY[labels.bands[1][1]] == "朝", path
    raw = json.loads(worlds[0].read_text(encoding="utf-8"))
    raw["clock"]["labels"]["bands"] = [*raw["clock"]["labels"]["bands"], [1430, "丑三つ"]]
    with pytest.raises(ValueError, match="丑三つ"):
        Labels(raw)


# —— Span 不含原话 ——


def test_spans_have_no_words() -> None:
    """原话、人物的回答、摘要、理由都不进 Span（data-design 第 8 节）：每样放一个记号，Span 里一个都找不到。"""
    said, answer, summary, why = "ゆびきりマーカー", "かえりみちマーカー", "ひみつのしるし", "こたえのしるし"
    p, _ = pipe(
        [
            extract_rule({**IMPROV, "summary": f"老爺は{summary}を見せた"}),
            {"kind": "check", "fail": {"rule": "R5-persona", "reason": why}},
        ]
    )
    run_turn(p, at(), TurnInput(character=OLD, player=f"{said}、宿はありますか", reply=answer))
    dumped = json.dumps([s.attrs for s in p.tracer.spans], ensure_ascii=False)
    assert p.tracer.spans and "R5-persona" in dumped
    assert not [m for m in (said, answer, summary, why) if m in dumped]
