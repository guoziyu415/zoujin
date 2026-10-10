"""结果的形状：每例每次每条检查是过、不过、跳过之一（E-0 卡第 2 条），跳过带原因。"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

type Status = Literal["pass", "fail", "skip"]
type SkipCode = Literal["not-implemented", "needs-live-model", "replay-missing", "no-character-text", "timeout"]


class Skip(TypedDict):
    code: SkipCode
    name: NotRequired[str]  # not-implemented：没做的步骤或查询的名字


class CheckResult(TypedDict):
    index: int  # expect.deterministic 里的第几条，从 1 起；判分是 0
    type: str  # 检查的 type；判分是 "judge"
    status: Status
    reason: NotRequired[str]  # 不过的原因（中文）
    skip: NotRequired[Skip]
    score: NotRequired[int]  # 判分：1〜5（rubric 和 pass 条件在用例的 expect.judge 里）


class RunResult(TypedDict):
    run: int  # 第几次，从 1 起
    status: Status  # 有一条不过就是不过；没有不过、有跳过就是跳过；全过才是过
    checks: list[CheckResult]
    judge: NotRequired[CheckResult]
    skip: NotRequired[Skip]  # 这一次整个没跑完：回放缺失或过期、超时
    error: NotRequired[str]  # 后端抛了「没做」以外的异常：这一次算不过
    traceIds: list[str]


class CaseResult(TypedDict):
    id: str
    suite: str
    title: str
    mode: str
    runs: int
    deletes: NotRequired[bool]  # 有删除步骤（deleteMemory / deletePlaythrough）：E6 的硬指标只算这些例
    skip: NotRequired[Skip]  # 整例跳过：setup 或某一步后端没做（每次都一样，只试第一次）
    results: NotRequired[list[RunResult]]


class SkipCheck(Exception):
    """检查判不了：跳过，带原因。"""

    def __init__(self, skip: Skip) -> None:
        super().__init__(skip)
        self.skip = skip


def not_implemented(name: str) -> SkipCheck:
    return SkipCheck({"code": "not-implemented", "name": name})


def skip_label(s: Skip) -> str:
    """报告里的写法。"""
    match s["code"]:
        case "not-implemented":
            return f"跳过：后端未实现（{s.get('name', '?')}）"
        case "needs-live-model":
            return "跳过：要真模型"
        case "replay-missing":
            return "回放缺失或过期"
        case "no-character-text":
            return "无原话"
        case "timeout":
            return "超时"


def run_status(checks: list[CheckResult], judge: CheckResult | None = None) -> Status:
    """一条都没判（只有判分的用例只跑确定性检查时）也是跳过。"""
    statuses = [c["status"] for c in checks] + ([judge["status"]] if judge else [])
    if "fail" in statuses:
        return "fail"
    return "skip" if "skip" in statuses or not statuses else "pass"
