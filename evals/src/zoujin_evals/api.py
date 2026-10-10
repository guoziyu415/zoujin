"""运行器怎么调后端的评测入口 zoujin_backend.eval_api（api-contract 第 7 节；B-0 第 9 条做最小版）。

这里只写运行器依赖的形状，后端照着实现，不用继承这里的类：

- 模块级函数 setup(setup, *, mode) 开一局，返回一个会话。setup 是用例的 setup 原样（运行器不推演、不补字段），
  mode 是用例的 mode（text / voice）。
- 会话上每种步骤一个方法，每次调用算一步，步骤号从 1 起，和用例 steps 的下标一致（delete_memory 的 from_step、
  retract 的 step、utterance_cleared 的 step 都按这个数）。每一步返回 StepResult。
- 查询随时可调：state()、events()、memories()、trust()、utterance_cleared()、db_absent()、ending()。
- 没做的步骤和查询抛 EvalNotImplemented("名字")；回放里查不到抛 ReplayMissing。运行器按异常的类名认，
  所以后端自己定义这两个类就行。会话上没有的方法也当作没做。
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, Protocol, TypedDict

type Json = Any
type Event = dict[str, Json]  # 契约第 3 节的 Event


class SafetyCard(TypedDict):
    """危机卡片（S-043、S-057）。"""

    shown: bool  # 这一步出了卡片
    paused: bool  # 故事暂停了（暂停期间没有事件、人物不开口）
    canReturn: bool  # 玩家能从卡片回到故事


class StepResult(TypedDict):
    """一步的结果（api-contract 第 7 节「每一步返回」）。

    后端给不了的字段可以不给，用到它的检查记「跳过：后端未实现（StepResult.字段）」。"""

    reply: NotRequired[str | None]  # 人物回答的文字；人物没开口时 None
    characterTextMissing: NotRequired[bool]  # 人物开口了但没有文字（backend-design 3.1），记「无原话」
    events: NotRequired[list[Event]]  # 这一步产生的全部候选事件，被否决的也给；提交了的带 eventId
    clockMinutes: NotRequired[int]  # 时钟前进了几分钟
    safetyCard: NotRequired[SafetyCard]
    plan: NotRequired[dict[str, Json] | None]  # 幕末打算成行时的 plan（契约 Event.plan）
    alternatives: NotRequired[list[dict[str, Json]]]  # 幕末打算不成行时后端回的替代去处
    followups: NotRequired[int]  # silence 之后人物追问了几次
    traceId: NotRequired[str]


class EvalSession(Protocol):
    """一局。步骤和查询的参数名照 api-contract 第 7 节，Python 里用蛇形。"""

    def say(self, to: str, text: str) -> StepResult: ...
    def act(self, kind: str, target: str | None, params: Mapping[str, Json]) -> StepResult: ...
    def delete_memory(self, character: str, from_step: int) -> StepResult: ...
    def retract(self, step: int) -> StepResult: ...
    def delete_playthrough(self) -> StepResult: ...
    def new_playthrough(self) -> StepResult: ...
    def advance(self, minutes: int) -> StepResult: ...
    def silence(self, seconds: int) -> StepResult: ...
    def propose(self, text: str) -> StepResult: ...
    def choose(self, exit: str, en_route: int | None = None) -> StepResult: ...

    def state(self) -> dict[str, Json]: ...  # 契约 3.1 的 WorldState
    def events(self) -> list[Event]: ...  # 这一局全部事件（含评测布置的、被否决的），按 seq
    def memories(self, character: str) -> list[dict[str, Json]]: ...  # 契约 4 的 MemoryItem，含已删除的
    def trust(self, character: str) -> int: ...
    def utterance_cleared(self, step: int) -> bool: ...  # 这一步那一轮的原话（玩家和人物的）都清空了
    def db_absent(self, tables: Sequence[str]) -> Mapping[str, int]: ...  # 每张表里还查得到这一局的几行
    def ending(self) -> dict[str, Json]: ...  # 契约第 5 节的 Ending


class EvalApi(Protocol):
    def setup(self, setup: Mapping[str, Json], *, mode: Literal["text", "voice"]) -> EvalSession: ...


BACKEND_MODULE = "zoujin_backend.eval_api"


def load_backend() -> EvalApi | None:
    """后端的评测入口；B-0 还没有时返回 None（每例都记「跳过：后端未实现（eval_api）」）。"""
    try:
        module: EvalApi = importlib.import_module(BACKEND_MODULE)
    except ModuleNotFoundError as e:
        if e.name is not None and BACKEND_MODULE.startswith(e.name):
            return None
        raise
    return module


class EvalNotImplemented(Exception):
    """运行器自己用：会话上没有这个步骤或查询的方法，和后端抛的同名异常一样处理。"""


def not_implemented(e: BaseException) -> str | None:
    """后端说「没做」的异常：返回没做的东西的名字，不是这种异常返回 None。"""
    if any(c.__name__ == "EvalNotImplemented" for c in type(e).__mro__):
        return str(e.args[0]) if e.args else "?"
    return None


def replay_missing(e: BaseException) -> bool:
    """回放里查不到（B-0 的 ReplayMissing）：按「回放缺失或过期」记，不当作通过，也不退回假模型。"""
    return any(c.__name__ == "ReplayMissing" for c in type(e).__mro__)
