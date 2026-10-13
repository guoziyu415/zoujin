"""两边共用的错误。消息里只有状态码和我们自己写的话，不带 SDK 或 HTTP 的原消息（里面可能有项目 ID、Key 的片段）。"""

from __future__ import annotations

import os
from pathlib import Path


class Stop(Exception):
    """要整次停下的错误（运行器不是跳过这一例，而是停下）：`BudgetStop`、`RateLimited`。"""


class BudgetStop(Stop):
    """账本到上限了（单项或总上限），这次调用没有发出去。"""


class RateLimited(Stop):
    """模型回 429 或 529（限流、过载）。Mac 上的跑第一个就停，不自动重试（S-079）。"""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostics: dict[str, str | int] = {}
        if provider in ("google", "claude"):
            self.diagnostics["provider"] = provider
        if status in (429, 529):
            self.diagnostics["httpStatus"] = status
        # 只收数字秒数；不保存供应商原文、项目、模型或任意响应头。
        if retry_after and retry_after.isascii() and retry_after.isdecimal() and len(retry_after) <= 8:
            self.diagnostics["retryAfterSeconds"] = int(retry_after)


class ModelCallFailed(RuntimeError):
    """模型调用失败（别的 HTTP 错误、网络断开），按时限的规则重发一次。消息只有 HTTP 状态码。"""


class BatchHalted(Stop):
    """有限评测的另一 worker 已停止；不取消在途请求，不再发起新请求。"""


def check_batch_halt() -> None:
    marker = os.environ.get("ZJ_EVAL_BATCH_HALT")
    if marker and Path(marker).exists():
        raise BatchHalted("批次已停止，保留本局证据；不再调用模型")
