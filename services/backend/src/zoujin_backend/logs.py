"""Logging setup for the gateway and narrator. Logs carry only IDs and counts, never the original words (data-design
section 8).

Exceptions log only their type and stack trace, never the exception message: a validation error message contains the
offending piece of data (possibly the player's words or a character's line). uvicorn's own logging goes through here
too (`log_config=None`), so exceptions not caught inside ASGI also carry no message. With the dev switch (`ZJ_DEV=1`)
full text is logged as usual, for convenience when looking locally.

ゲートウェイとナレーターのログ設定。ログには ID と件数だけを書き、発話の原文は書かない（data-design 第 8 節）。

例外は型とスタックトレースだけを記録し、例外メッセージは記録しない：
検証エラーのメッセージには問題のデータ（プレイヤーの発話や登場人物のセリフかもしれない）が含まれるため。
uvicorn 自身のログもここを通す（`log_config=None`）ので、ASGI 内で捕まえきれなかった例外もメッセージを持たない。
開発スイッチ（`ZJ_DEV=1`）では、ローカルで見やすいよう全文を通常どおり記録する。
"""

from __future__ import annotations

import logging
import traceback
from types import TracebackType

FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

type ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]


class NoMessage(logging.Formatter):
    def formatException(self, ei: ExcInfo) -> str:  # noqa: N802 (logging method name / logging のメソッド名)
        etype, _, tb = ei
        name = f"{etype.__module__}.{etype.__qualname__}" if etype is not None else "?"
        return (
            "Traceback (most recent call last):\n"
            + "".join(traceback.format_tb(tb))
            + f"{name} (message not logged / メッセージは記録しない)"
        )


def setup(level: str, *, dev: bool) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT) if dev else NoMessage(FORMAT))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
