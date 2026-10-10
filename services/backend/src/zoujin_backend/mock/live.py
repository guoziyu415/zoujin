"""一局的实时部分：剧本推进、当前连接、发消息前的自检。

剧本是一局一个，跟着局走，不跟着连接走：断线期间剧本照样往下走（commit 记下来，重连时按 `hello.lastSeq` 补发），
其他消息没人收就丢掉。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from zoujin_backend import audio
from zoujin_backend.clock import Labels
from zoujin_backend.mock.scripts import Step
from zoujin_backend.mock.state import Playthrough
from zoujin_backend.mock.templates import MISSING, TemplateError, render
from zoujin_backend.schemas import SchemaBook, SchemaError

log = logging.getLogger("zoujin.mock")

# mock 自己回的消息也交给剧本（剧本可以等 hello、focus），剧本不等时不必在终端记一行
QUIET = {"hello", "near", "far", "focus", "unfocus", "turn_retract", "ping"}

# {{t+10}}、{{tLabel+10}}：当前故事时间往后若干分钟（剧本不写死时刻，导览里前后剧本接得上）
LATER = re.compile(r"^(t|tLabel)\+(\d+)$")

Json = Any


class Link:
    """一条 WebSocket 连接对 mock 的样子（ws.py 实现）。"""

    async def send_json(self, msg: Json) -> None:
        raise NotImplementedError

    async def send_bytes(self, data: bytes) -> None:
        raise NotImplementedError

    async def close(self, code: int, reason: str = "") -> None:
        raise NotImplementedError


@dataclass
class TurnContext:
    """剧本里一组步骤（一个 on 到下一个 on 之间）的变量。"""

    kind: str | None = None  # voice / text：这一组是语音还是文字触发的
    trigger: Json = field(default_factory=dict)
    trigger_turn: str | None = None  # 触发消息自己的 turnId；这一轮作废了，这一组剩下的步骤就不做
    turn_id: str | None = None  # {{turnId}}：这一组的轮次（newServerTurn 之后是服务端那一轮）
    turn_seq: int | None = None
    player_turn_id: str | None = None  # {{playerTurnId}}：最近一次玩家发起的轮次
    server_turn_id: str | None = None
    server_turn_seq: int | None = None


class Live:
    def __init__(
        self,
        pt: Playthrough,
        book: SchemaBook,
        labels: Labels,
        *,
        speed: float,
        strict: bool,
    ) -> None:
        self.pt = pt
        self.book = book
        self.labels = labels
        self.speed = speed
        self.strict = strict
        self.link: Link | None = None
        self.inbox: deque[Json] = deque()
        self.arrived = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.steps: list[Step] = []
        self.ctx = TurnContext()
        self.finished = asyncio.Event()
        self.sent_types: list[str] = []  # 测试和覆盖检查用
        self.streaming: str | None = None  # 正在发音频的那一轮
        self.cut: set[str] = set()  # 被玩家打断的轮次：剩下的音频和人物的中途字幕不再发
        self.vars: dict[str, Any] = {}  # 剧本的 set

    # —— 剧本 ——

    def start(self, steps: list[Step]) -> None:
        self.stop()
        self.steps = steps
        self.ctx = TurnContext()
        self.vars.clear()
        self.inbox.clear()
        self.finished.clear()
        self.task = asyncio.get_running_loop().create_task(self._run())

    def stop(self) -> None:
        if self.task is not None and not self.task.done():
            self.task.cancel()
        self.task = None

    async def _run(self) -> None:
        try:
            for step in self.steps:
                if step.cond and not self._holds(step):
                    continue
                if step.on:
                    msg = await self._wait_for(step.on, step.timeout_ms)
                    self._new_group(msg)
                if step.when is not None and step.when != self.ctx.kind:
                    continue
                if self.ctx.trigger_turn is not None and self.ctx.trigger_turn in self.pt.retracted:
                    continue  # 这一轮已作废，剩下的步骤不做（3.6）
                await self._sleep(step.delay_ms)
                if step.new_server_turn:
                    self._new_server_turn()
                await self._do(step)
            log.info("剧本走完了（%s）", self.pt.pid)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("剧本出错，停在这里")
            if self.strict:
                raise
        finally:
            self.finished.set()

    def _holds(self, step: Step) -> bool:
        return all(self.lookup(name) in values for name, values in step.cond)

    def _new_group(self, msg: Json) -> None:
        old = self.ctx
        ctx = TurnContext(
            trigger=msg,
            turn_id=old.turn_id,
            turn_seq=old.turn_seq,
            player_turn_id=old.player_turn_id,
            server_turn_id=old.server_turn_id,
            server_turn_seq=old.server_turn_seq,
        )
        if msg["type"] in ("activity_start", "activity_end"):
            ctx.kind = "voice"
        elif msg["type"] in ("text", "act_propose"):
            ctx.kind = "text"
        if "turnId" in msg:
            ctx.turn_id = ctx.trigger_turn = ctx.player_turn_id = msg["turnId"]
            ctx.turn_seq = msg.get("turnSeq")
        self.ctx = ctx

    def _new_server_turn(self) -> None:
        self.pt.server_turn_seq += 1
        # 之后这一组的 {{turnId}}、{{turnSeq}} 指服务端这一轮（3.1：turnSeq 最高位为 1）
        self.ctx.turn_id = self.ctx.server_turn_id = self.pt.ids.new("turn")
        self.ctx.turn_seq = self.ctx.server_turn_seq = self.pt.server_turn_seq

    async def _sleep(self, ms: int) -> None:
        await asyncio.sleep(ms / 1000 * self.speed if ms and self.speed else 0)

    async def _wait_for(self, types: tuple[str, ...], timeout_ms: int | None = None) -> Json:
        loop = asyncio.get_running_loop()
        deadline = None if timeout_ms is None else loop.time() + timeout_ms / 1000 * self.speed
        while True:
            while self.inbox:
                msg = self.inbox.popleft()
                if msg["type"] in types:
                    return msg
                level = logging.DEBUG if msg["type"] in QUIET else logging.INFO
                log.log(level, "剧本在等 %s，忽略 %s", "/".join(types), msg["type"])
            self.arrived.clear()
            if deadline is None:
                await self.arrived.wait()
                continue
            try:
                await asyncio.wait_for(self.arrived.wait(), max(0.0, deadline - loop.time()))
            except TimeoutError:
                if not self.inbox:
                    return {"type": "timeout"}

    def lookup(self, name: str) -> Any:
        c = self.ctx
        if name.startswith("id:"):
            _, prefix, key = name.split(":", 2)
            return self.pt.named_id(prefix, key)
        t = self.pt.snapshot["clock"]["t"]
        later = LATER.match(name)
        if later:
            at = t + int(later.group(2))
            return at if later.group(1) == "t" else self.labels.label(at)
        simple: dict[str, Any] = {
            "playthroughId": self.pt.pid,
            "roleId": self.pt.role_id,
            "turnId": c.turn_id,
            "turnSeq": c.turn_seq,
            "playerTurnId": c.player_turn_id,
            "interrupted": c.turn_id is not None and c.turn_id in self.cut,
            "serverTurnId": c.server_turn_id,
            "serverTurnSeq": c.server_turn_seq,
            "lastSeq": self.pt.last_seq,
            "t": t,
            "tLabel": self.pt.snapshot["clock"]["tLabel"],
        }
        if name in simple:
            return simple[name] if simple[name] is not None else MISSING
        if name.startswith("trigger."):
            return c.trigger.get(name.removeprefix("trigger."), MISSING)
        if name.startswith("var."):
            return self.vars.get(name.removeprefix("var."), MISSING)
        return MISSING

    async def _do(self, step: Step) -> None:
        if step.send is not None:
            try:
                msg = render(step.send, self.lookup)
            except TemplateError as e:
                raise TemplateError(f"{step.source}：{e}") from e
            if msg["type"] == "transcript" and not msg["final"] and msg["turnId"] in self.cut:
                return  # 被打断了，人物不再往下说
            await self.emit(msg, unchecked=step.unchecked, hidden=step.hidden, source=step.source)
        elif step.audio is not None:
            await self._stream(step)
        elif step.assign is not None:
            self.vars.update(render(step.assign, self.lookup))
        elif step.close is not None:
            if self.link is not None:
                code, reason = step.close
                link, self.link = self.link, None
                await link.close(code, reason)

    async def _stream(self, step: Step) -> None:
        a = step.audio
        assert a is not None
        turn_id, turn_seq = self.ctx.turn_id, self.ctx.turn_seq
        if turn_seq is None:
            raise TemplateError(f"{step.source}：音频不知道是哪一轮的 turnSeq")
        self.streaming = turn_id
        try:
            for pcm in audio.chunks(a.seconds, a.chunk_ms):
                if self.link is None or turn_id in self.pt.retracted or turn_id in self.cut:
                    return
                await self.link.send_bytes(audio.frame(turn_seq, pcm))
                await self._sleep(a.chunk_ms)
        finally:
            self.streaming = None

    async def interrupt(self, new_turn: str) -> None:
        """玩家在人物说话时按下说话或发文字（3.2）：旧的一轮不再发分片，确认打断（3.3 interrupted）。"""
        old = self.streaming
        if old is not None and old != new_turn and old not in self.cut:
            self.cut.add(old)
            await self.emit({"type": "interrupted", "turnId": old})

    # —— 发 ——

    async def emit(self, msg: Json, *, unchecked: bool = False, hidden: int | None = None, source: str = "") -> None:
        """自检、改状态、发出去。不过 Schema 的不发，在终端报错（strict 时抛出）。"""
        try:
            if msg["type"] == "commit":
                self.pt.number_commit(msg, hidden)
            if msg["type"] == "act_transition":
                self.pt.fill_snapshot(msg["snapshot"])
            out = msg if unchecked else self.book.server_message(msg)
        except (SchemaError, ValueError) as e:
            log.error("不发 %s（%s）：%s", msg.get("type"), source or "mock", e)
            if self.strict:
                raise
            return
        self.pt.on_sent(out)
        self.sent_types.append(out["type"])
        if self.link is not None:
            await self.link.send_json(out)
        elif out["type"] != "commit":
            log.info("没有连接，%s 丢掉", out["type"])

    # —— 收 ——

    def deliver(self, msg: Json) -> None:
        """给剧本的客户端消息。"""
        self.inbox.append(msg)
        self.arrived.set()

    async def detach(self, link: Link) -> None:
        if self.link is link:
            self.link = None

    async def attach(self, link: Link) -> None:
        old, self.link = self.link, link
        if old is not None:
            with contextlib.suppress(Exception):
                await old.close(4009, "opened elsewhere")  # 同一局在别的标签页打开（第 4 节）
