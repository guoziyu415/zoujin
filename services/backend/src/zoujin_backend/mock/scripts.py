"""剧本：`fixtures/sessions/<名字>.jsonl`，一行一步（写法见那个目录的 README）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 一轮对话的触发：语音松手或发文字（F-0 先走文字）
ALIASES = {"turn": ("activity_end", "text")}
ACTIONS = ("send", "audio", "close", "set", "include")
KEYS = {"on", "timeoutMs", "if", "when", "delayMs", "newServerTurn", "unchecked", "hidden", "note", *ACTIONS}


class ScriptError(Exception):
    pass


@dataclass(frozen=True)
class Audio:
    seconds: float
    chunk_ms: int


@dataclass(frozen=True)
class Step:
    source: str  # 「剧本名:行号」，报错用
    on: tuple[str, ...] = ()
    timeout_ms: int | None = None  # 等 on 等不到：到点以 {"type": "timeout"} 开始这一组
    cond: tuple[tuple[str, tuple[Any, ...]], ...] = ()  # if：变量名 → 可取的值，全部满足才做这一步
    when: str | None = None
    delay_ms: int = 0
    new_server_turn: bool = False
    send: dict[str, Any] | None = None
    unchecked: bool = False
    hidden: int | None = None
    audio: Audio | None = None
    close: tuple[int, str] | None = None
    assign: dict[str, Any] | None = None  # set：剧本变量，之后用 {{var.名字}} 和 if 读


def _types(v: Any, where: str) -> tuple[str, ...]:
    items = [v] if isinstance(v, str) else v
    if not isinstance(items, list) or not items or not all(isinstance(x, str) for x in items):
        raise ScriptError(f"{where}：on 是一种或几种客户端消息的 type")
    out: list[str] = []
    for x in items:
        out.extend(ALIASES.get(x, (x,)))
    return tuple(out)


def _step(raw: dict[str, Any], where: str) -> Step:
    unknown = set(raw) - KEYS
    if unknown:
        raise ScriptError(f"{where}：不认识的键 {sorted(unknown)}")
    actions = [a for a in ACTIONS if a in raw]
    if len(actions) > 1:
        raise ScriptError(f"{where}：一步只做一件事，这里有 {actions}")
    when = raw.get("when")
    if when not in (None, "voice", "text"):
        raise ScriptError(f"{where}：when 只能是 voice 或 text")
    delay = raw.get("delayMs", 0)
    if not isinstance(delay, int) or delay < 0:
        raise ScriptError(f"{where}：delayMs 是非负整数")
    if ("unchecked" in raw or "hidden" in raw) and "send" not in raw:
        raise ScriptError(f"{where}：unchecked、hidden 只用在 send 上")
    timeout = raw.get("timeoutMs")
    if timeout is not None and ("on" not in raw or not isinstance(timeout, int) or timeout < 0):
        raise ScriptError(f"{where}：timeoutMs 是非负整数，只用在 on 上")
    assign = raw.get("set")
    if assign is not None and (not isinstance(assign, dict) or not assign):
        raise ScriptError(f"{where}：set 是 {{变量名: 值}}")
    audio = None
    if "audio" in raw:
        a = raw["audio"]
        audio = Audio(float(a["seconds"]), int(a.get("chunkMs", 40)))
    close = None
    if "close" in raw:
        close = (int(raw["close"]["code"]), str(raw["close"].get("reason", "")))
    send = raw.get("send")
    if send is not None and (not isinstance(send, dict) or "type" not in send):
        raise ScriptError(f"{where}：send 是一条带 type 的服务端消息")
    cond = raw.get("if", {})
    if not isinstance(cond, dict):
        raise ScriptError(f"{where}：if 是 {{变量名: 值或值的列表}}")
    return Step(
        source=where,
        on=_types(raw["on"], where) if "on" in raw else (),
        timeout_ms=timeout,
        cond=tuple((k, tuple(v) if isinstance(v, list) else (v,)) for k, v in cond.items()),
        when=when,
        delay_ms=delay,
        new_server_turn=bool(raw.get("newServerTurn", False)),
        send=send,
        unchecked=bool(raw.get("unchecked", False)),
        hidden=raw.get("hidden"),
        audio=audio,
        close=close,
        assign=assign,
    )


def load(directory: Path, name: str, _stack: tuple[str, ...] = ()) -> list[Step]:
    """读一个剧本，`include` 就地展开。"""
    if name in _stack:
        raise ScriptError(f"剧本互相 include：{' → '.join((*_stack, name))}")
    path = directory / f"{name}.jsonl"
    if not path.is_file():
        raise ScriptError(f"没有剧本 {name}（{path}）")
    steps: list[Step] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{name}:{n}"
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            raise ScriptError(f"{where}：不是 JSON：{e}") from e
        if not isinstance(raw, dict):
            raise ScriptError(f"{where}：一行是一个对象")
        if "include" in raw:
            if set(raw) - {"include", "note"}:
                raise ScriptError(f"{where}：include 那一行只写 include（和 note）")
            steps.extend(load(directory, raw["include"], (*_stack, name)))
            continue
        steps.append(_step(raw, where))
    return steps


def names(directory: Path) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.jsonl"))
