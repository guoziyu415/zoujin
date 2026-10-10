"""日志不记异常消息（data-design 第 8 节：日志只写 ID 和计数）；开发开关下照常记。

客户端消息不合 Schema 时只记字段路径和规则名。
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest
from zoujin_backend import logs

from .conftest import SCHEMAS

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


def test_schema_problems_name_the_field_not_the_value() -> None:
    """玩家的原话可能就在出错的字段里：日志只写路径和规则名（REST 的请求体和 WebSocket 的消息都是）。"""
    text = LINE * 10  # 超过 200 字
    ws = SCHEMAS.client_errors(
        {"type": "text", "turnId": "turn_" + "0" * 26, "turnSeq": 1, "text": text, "via": "typed"}
    )
    rest = SCHEMAS.request_errors("auth-login", "request", {"inviteCode": text})
    assert ws == ["/text: maxLength"]
    assert rest == ["/inviteCode: maxLength"]
