"""A fake Vertex Live service (for B-10's tests): a WebSocket on the local 127.0.0.1 that, following a script, returns
`setupComplete`, transcriptions on both sides, audio, `interrupted`, `turnComplete`, usage and `goAway`, and can also
drop mid-way or not answer setup. The lines are written for tests, and the audio is silent PCM.

One `Script` per connection; each time a turn is received (`activityEnd`, or `clientContent` with `turnComplete: true`
and the role user), it answers with the next entry in `Script.replies`. All received messages are recorded in
`Conn.got`, where tests check the setup and what was sent.

偽の Vertex Live サービス（B-10 のテスト用）：ローカルの 127.0.0.1 上の WebSocket で、スクリプトに従って
`setupComplete`、両側の書き起こし、音声、`interrupted`、`turnComplete`、使用量、`goAway` を返す。途中で切断したり、
setup に答えなかったりもできる。セリフはテスト用に書いたもので、音声は無音の PCM。

接続ごとに `Script` が 1 つ。ターンを受け取るたびに（`activityEnd`、または role が user で `turnComplete: true` の
`clientContent`）、`Script.replies` の次の項目で答える。受け取ったメッセージはすべて `Conn.got` に記録し、テストは
そこで setup と送られた内容を確認する。
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

Json = Any
CHUNK = bytes(960 * 2)  # 40 ms of 24 kHz silence / 40 ms の 24 kHz 無音


@dataclass
class Reply:
    player: str = ""  # player-side transcription (voice turn) / プレイヤー側の書き起こし（音声ターン）
    # Character-side transcription, in several pieces / 登場人物側の書き起こし（いくつかに分ける）
    text: list[str] = field(default_factory=lambda: ["……そうか。"])
    chunks: int = 3  # audio chunks / 音声チャンク
    # Character text that arrives only after turnComplete / turnComplete の後に届く登場人物のテキスト
    late: list[str] = field(default_factory=list)
    late_player: str = ""  # player text arriving after turnComplete / turnComplete の後に届くプレイヤーのテキスト
    usage: Json | None = field(
        default_factory=lambda: {
            "promptTokenCount": 100,
            "candidatesTokenCount": 50,
            "totalTokenCount": 150,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 100}],
            "candidatesTokensDetails": [{"modality": "AUDIO", "tokenCount": 50}],
        }
    )
    goaway: bool = False  # send goAway before answering / 返答の前に goAway を送る
    drop_after_audio: bool = False  # drop after the first audio / 最初の音声を出したら切断する
    delay: float = 0.0  # seconds to wait between messages / メッセージ間の待ち秒数


@dataclass
class Script:
    replies: list[Reply] = field(default_factory=list)
    # ok / silent (no answer) / close (close at once) / wrong (the first message is not setupComplete)
    # ok / silent（答えない）/ close（すぐ閉じる）/ wrong（最初のメッセージが setupComplete ではない）
    setup: str = "ok"
    # If setup meets this condition, close with 1007 as Vertex does for a field it does not accept
    # setup がこの条件に合えば、Vertex が受け付けないフィールドのときと同じく 1007 で閉じる
    reject: Callable[[Json], bool] | None = None


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
    # Used in order of connection; once exhausted, the last one is used / 接続順に使い、尽きたら最後のものを使う
    scripts: list[Script] = field(default_factory=list)
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
            if script.reject is not None and script.reject(conn.setup):
                await ws.close(
                    1007, "Invalid JSON payload at projects/my-proj-123/locations/l: unknown name thinkingConfig"
                )
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
        except Exception:  # noqa: BLE001 - the client closed / クライアントが閉じた
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
