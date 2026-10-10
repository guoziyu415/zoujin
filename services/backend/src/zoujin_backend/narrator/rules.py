"""叙事者第 3 步的骨架：只用 W-1 的 check_effects（引用存在、值合法、变量范围、valueRequires）判候选事件。

R1〜R7 的确定性规则和第 4 步的模型检查（R5、R6）是 M2 叙事者卡的；这里把 check_effects 的问题按下表记到最接近的
规则上，其余规则记 skipped。CheckResult.checker 写明这一点，评测和 Trace 能分出来。
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_backend.ids import IdGen
from zoujin_worldsim import SimState, apply, check_effects

Json = Any

RULES = ("R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability")
CHECKER = "b0:w1-check_effects"  # 只跑了 W-1 的检查；R1〜R7 本体没做
# check_effects 的问题 → 最接近的规则（S-2 的标注集里同类的违规按这个记）
CODE_RULE = {
    "beat-happened": "R1-anchor",  # 候选事件让原作节拍直接发生
    "beat-has-result": "R2-precondition",
    "bad-state": "R2-precondition",
    "value-requires": "R2-precondition",
    "unknown-id": "R7-capability",
    "bad-value": "R7-capability",
    "bad-op": "R7-capability",
    "duplicate-id": "R7-capability",
}
SKIPPED_REASON = "B-0 只查 W-1 的 check_effects"


@dataclass
class Checked:
    """一个候选事件和它的检查结果。effects 是候选原本的（promiseId 等已补上）；提交时被否决的写空 effects。"""

    candidate: Json
    effects: list[Json]
    check: Json
    rules: list[Json] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.check["status"] == "passed")


def fill_ids(effects: Sequence[Mapping[str, Any]], ids: IdGen) -> list[Json]:
    """约定成立时分配 promiseId，即兴设定没有 factId 时分配（提交时才分配，S-2 的候选不带）。"""
    out = []
    for given in effects:
        e: dict[str, Any] = copy.deepcopy(dict(given))
        if e.get("op") == "promise" and e.get("change") == "made" and not e.get("promiseId"):
            e["promiseId"] = ids.new("prm")
        if e.get("op") == "improv" and not e.get("factId"):
            e["factId"] = ids.new("rf")
        out.append(e)
    return out


def check_one(world: Json, state: SimState, effects: list[Json], origin: str) -> tuple[Json, list[Json]]:
    problems = check_effects(world, state, effects, origin)
    failed = sorted({CODE_RULE.get(p["code"], "R7-capability") for p in problems}, key=RULES.index)
    rules = []
    for r in RULES:
        hit = [p for p in problems if CODE_RULE.get(p["code"], "R7-capability") == r]
        if hit:
            rules.append({"rule": r, "status": "fail", "reason": hit[0].get("note") or hit[0]["message"]})
        else:
            rules.append({"rule": r, "status": "skipped", "reason": SKIPPED_REASON})
    check: Json = {
        "status": "rejected" if problems else "passed",
        "attempts": 1,
        "failedRules": failed,
        "checker": CHECKER,
    }
    if problems:
        check["reason"] = problems[0].get("note") or problems[0]["message"]
    return check, rules


def check_candidates(world: Json, state: SimState, candidates: Sequence[Json], ids: IdGen) -> list[Checked]:
    """按顺序查：前面通过的候选先试算进状态，后面的在它之后判（同一轮里的约定、节拍改动接得上）。"""
    out = []
    trial = state
    for cand in candidates:
        effects = fill_ids(cand.get("effects", []), ids)
        origin = cand.get("origin", "turn")
        check, rules = check_one(world, trial, effects, origin)
        out.append(Checked(dict(cand), effects, check, rules))
        if not check["failedRules"] and effects:
            trial = apply(world, trial, {"t": trial["t"], "dt": 0, "origin": origin, "type": "say", "effects": effects})
    return out
