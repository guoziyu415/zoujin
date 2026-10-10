"""日志不记异常消息（data-design 第 8 节：日志只写 ID 和计数）；开发开关下照常记。"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest
from zoujin_backend import logs

LINE = "さっき、村の牧人だという若い男とすれ違いました。"
MESSAGE = f"校验不过：{LINE}"


@pytest.fixture
def restore_root() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def logged(dev: bool) -> str:
    logs.setup("info", dev=dev)
    out = io.StringIO()
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(out)
    try:
        raise ValueError(MESSAGE)
    except ValueError:
        logging.getLogger("zoujin.test").exception("处理 %s 出错", "turn_01")
    return out.getvalue()


def test_exception_message_is_not_logged(restore_root: None) -> None:
    text = logged(dev=False)
    assert "处理 turn_01 出错" in text and "builtins.ValueError（消息不记）" in text
    assert "Traceback" in text and "test_logs.py" in text
    assert LINE not in text


def test_dev_logs_everything(restore_root: None) -> None:
    assert f"ValueError: {MESSAGE}" in logged(dev=True)
