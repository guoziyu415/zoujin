"""假的 Vertex Live 服务（B-10 的测试用）：本机 127.0.0.1 上的 WebSocket，按脚本回 `setupComplete`、两边的转写、音频、
`interrupted`、`turnComplete`、用量、`goAway`，也能中途断开、不回 setup。台词是为测试写的，声音是静音的 PCM。

一个连接一份 `Script`；每收到一轮（`activityEnd`，或 `clientContent` 的 `turnComplete: true` 且角色是 user）就照
`Script.replies` 的下一条回。收到的消息都记在 `Conn.got` 里，测试查 setup 和发出去的东西。
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

Json = Any
CHUNK = bytes(960 * 2)  # 40 ms 的 24 kHz 静音


@dataclass
class Reply:
    player: str = ""  # 玩家一侧的转写（语音一轮）
    text: list[str] = field(default_factory=lambda: ["……そうか。"])  # 人物一侧的转写，分几段
    chunks: int = 3  # 音频分片
    late: list[str] = field(default_factory=list)  # turnComplete 之后才到的人物文字
    late_player: str = ""  # turnComplete 之后才到的玩家文字
    usage: Json | None = field(
        default_factory=lambda: {
            "promptTokenCount": 100,
            "candidatesTokenCount": 50,
            "totalTokenCount": 150,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 100}],
            "candidatesTokensDetails": [{"modality": "AUDIO", "tokenCount": 50}],
        }
    )
    goaway: bool = False  # 回答之前先发 goAway
    drop_after_audio: bool = False  # 出了第一个音频就断开
    delay: float = 0.0  # 每条消息之间等几秒


@dataclass
class Script:
    replies: list[Reply] = field(default_factory=list)
    setup: str = "ok"  # ok / silent（不回）/ close（直接关）/ wrong（第一条不是 setupComplete）


@dataclass
class Conn:
    got: list[Json] = field(default_factory=list)
    closed: bool = False

    @property
    def setup(self) -> Json:
        return self.got[0]["setup"]

    def sent(self, key: str) -> list[Json]:
        return [m for m in self.got if key in m]


@dataclass
class FakeVertexLive:
    scripts: list[Script] = field(default_factory=list)  # 按连接的先后用；用完都用最后一份
    conns: list[Conn] = field(default_factory=list)
    url: str = ""

    def script(self) -> Script:
        n = len(self.conns) - 1
        return self.scripts[min(n, len(self.scripts) - 1)] if self.scripts else Script()

    async def handler(self, ws: ServerConnection) -> None:
        conn = Conn()
        self.conns.append(conn)
        script = self.script()
        try:
            conn.got.append(json.loads(await ws.recv()))
            if script.setup == "silent":
                await ws.wait_closed()
                return
            if script.setup == "close":
                await ws.close(1011, "setup failed")
                return
            if script.setup == "wrong":
                await ws.send(json.dumps({"serverContent": {}}))
                return
            await ws.send(json.dumps({"setupComplete": {}}))
            replies = iter(script.replies)
            async for raw in ws:
                msg = json.loads(raw)
                conn.got.append(msg)
                ri = msg.get("realtimeInput") or {}
                cc = msg.get("clientContent") or {}
                ask = "activityEnd" in ri or (
                    cc.get("turnComplete") and any(t.get("role") == "user" for t in cc.get("turns", []))
                )
                if ask:
                    r = next(replies, Reply())
                    if not await self.play(ws, r):
                        return
        except Exception:  # noqa: BLE001 - 客户端关了
            pass
        finally:
            conn.closed = True

    async def play(self, ws: ServerConnection, r: Reply) -> bool:
        async def send(m: Json) -> None:
            if r.delay:
                await asyncio.sleep(r.delay)
            await ws.send(json.dumps(m, ensure_ascii=False))

        if r.goaway:
            await send({"goAway": {"timeLeft": "50s"}})
        if r.player:
            await send({"serverContent": {"inputTranscription": {"text": r.player}}})
        for i in range(r.chunks):
            data = base64.b64encode(CHUNK).decode("ascii")
            await send({"serverContent": {"modelTurn": {"parts": [{"inlineData": {"data": data}}]}}})
            if r.drop_after_audio:
                await ws.close(1011, "internal")
                return False
            if i < len(r.text):
                await send({"serverContent": {"outputTranscription": {"text": r.text[i]}}})
        for rest in r.text[r.chunks :]:
            await send({"serverContent": {"outputTranscription": {"text": rest}}})
        await send({"serverContent": {"turnComplete": True}})
        if r.late_player:
            await send({"serverContent": {"inputTranscription": {"text": r.late_player}}})
        for x in r.late:
            await send({"serverContent": {"outputTranscription": {"text": x}}})
        if r.usage is not None:
            await send({"usageMetadata": r.usage})
        return True


@asynccontextmanager
async def running(*scripts: Script) -> AsyncIterator[FakeVertexLive]:
    fake = FakeVertexLive(list(scripts))
    async with serve(fake.handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        fake.url = f"ws://127.0.0.1:{port}"
        yield fake
        with contextlib.suppress(Exception):
            server.close()
