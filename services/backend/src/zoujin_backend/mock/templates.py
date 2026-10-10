"""剧本和固定数据里的占位符：`{{名字}}`、`{{名字|默认值}}`。

整个字符串就是一个占位符时，换成变量的原值（数字、null 也行）；嵌在字符串里时换成文字。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

PLACEHOLDER = re.compile(r"\{\{([^{}|]+)(?:\|([^{}]*))?\}\}")

Lookup = Callable[[str], Any]


class TemplateError(Exception):
    pass


class Missing:
    """lookup 找不到变量时返回它（变量的值本身可以是 None）。"""


MISSING = Missing()


def _value(lookup: Lookup, name: str, default: str | None) -> Any:
    v = lookup(name.strip())
    if v is MISSING:
        if default is None:
            raise TemplateError(f"占位符 {{{{{name}}}}} 没有值")
        return default
    return v


def render(node: Any, lookup: Lookup) -> Any:
    if isinstance(node, str):
        whole = PLACEHOLDER.fullmatch(node)
        if whole:
            return _value(lookup, whole.group(1), whole.group(2))
        return PLACEHOLDER.sub(lambda m: str(_value(lookup, m.group(1), m.group(2))), node)
    if isinstance(node, list):
        return [render(v, lookup) for v in node]
    if isinstance(node, dict):
        return {k: render(v, lookup) for k, v in node.items()}
    return node
