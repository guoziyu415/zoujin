"""两边共用的错误。消息里只有状态码和我们自己写的话，不带 SDK 或 HTTP 的原消息（里面可能有项目 ID、Key 的片段）。"""

from __future__ import annotations


class Stop(Exception):
    """要整次停下的错误（运行器不是跳过这一例，而是停下）：`BudgetStop`、`RateLimited`。"""


class BudgetStop(Stop):
    """账本到上限了（单项或总上限），这次调用没有发出去。"""


class RateLimited(Stop):
    """模型回 429 或 529（限流、过载）。Mac 上的跑第一个就停，不自动重试（S-079）。"""


class ModelCallFailed(RuntimeError):
    """模型调用失败（别的 HTTP 错误、网络断开），按时限的规则重发一次。消息只有 HTTP 状态码。"""
