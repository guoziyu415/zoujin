"""网关和叙事者的日志设置。日志只写 ID 和计数，不写原话（data-design 第 8 节）。

异常只记类型和调用栈，不记异常消息：校验错误的消息里带着出错的那段数据（可能是玩家的话或人物的台词）。
uvicorn 自己的日志也走这里（`log_config=None`），ASGI 里没接住的异常同样不带消息。
开发开关（`ZJ_DEV=1`）下照常记全文，方便本地看。
"""

from __future__ import annotations

import logging
import traceback
from types import TracebackType

FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

type ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]


class NoMessage(logging.Formatter):
    def formatException(self, ei: ExcInfo) -> str:  # noqa: N802（logging 的方法名）
        etype, _, tb = ei
        name = f"{etype.__module__}.{etype.__qualname__}" if etype is not None else "?"
        return "Traceback (most recent call last):\n" + "".join(traceback.format_tb(tb)) + f"{name}（消息不记）"


def setup(level: str, *, dev: bool) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT) if dev else NoMessage(FORMAT))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
