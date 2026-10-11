"""网关和叙事者端到端（B-0 验收第 1、2、6、7 组）：真 PostgreSQL，两个进程，前端的样子（httpx + websockets）。

收到的每条 WebSocket 消息和 REST 响应都在客户端再按 C-1 的 Schema 查一遍（第 2 组；网关发之前也查过）。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect
from websockets.typing import Origin
from zoujin_backend.admin import create_invites, replay
from zoujin_backend.config import COOKIE, REPO
from zoujin_backend.db.tables import invite_codes
from zoujin_backend.gateway.auth import new_invite_code
from zoujin_backend.ids import IdGen
from zoujin_backend.schemas import SERVER

from .conftest import LIBRARY, OLD, SCHEMAS, Env

pytestmark = pytest.mark.db

Json = Any
CREATE = {"bookId": "hashire-merosu", "roleId": "role.traveler"}
IDS = IdGen()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Proc:
    """`zoujin-gateway` / `zoujin-narrator` 起成单独的进程（和 compose 里一样，只是端口随机）。"""

    def __init__(self, module: str, port: int, env: dict[str, str]) -> None:
        code = f"import sys; from {module} import main; main(sys.argv[1:])"
        self.port = port
        self.p = subprocess.Popen(
            [sys.executable, "-c", code, "--port", str(port), "--log-level", "warning"],
            env=env,
            cwd=REPO,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.p.poll() is not None:
                raise RuntimeError(f"{module} 没起来（{self.p.returncode}）")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"{module} 30 秒没起来")

    def stop(self) -> None:
        if self.p.poll() is None:
            self.p.send_signal(signal.SIGTERM)
            try:
                self.p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait()


def service_env(url: str, narrator_port: int, speed: str = "0", extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ZJ_")}
    env.update(DATABASE_URL=url, ZJ_DEV="1", ZJ_SPEED=speed, ZJ_NARRATOR_URL=f"http://127.0.0.1:{narrator_port}")
    env.update(extra or {})
    return env


class Services:
    def __init__(self, url: str, speed: str = "0", extra: dict[str, str] | None = None) -> None:
        """extra：再加的环境变量（B-3 的测试用 `ZJ_WORLD` 换切片版）。"""
        n_port, g_port = free_port(), free_port()
        env = service_env(url, n_port, speed, extra)
        self.narrator = Proc("zoujin_backend.narrator.app", n_port, env)
        self.gateway = Proc("zoujin_backend.gateway.app", g_port, env)
        self.base = f"http://127.0.0.1:{g_port}"
        self.narrator_url = f"http://127.0.0.1:{n_port}"

    def stop(self) -> None:
        self.gateway.stop()
        self.narrator.stop()


@pytest.fixture(scope="module")
def services(migrated: str) -> Iterator[Services]:
    s = Services(migrated)
    try:
        yield s
    finally:
        s.stop()


def invite(env: Env) -> str:
    async def main() -> str:
        engine = env.engine()
        try:
            (code,) = await create_invites(engine, 1)
        finally:
            await engine.dispose()
        return code

    return asyncio.run(main())


class Player:
    """REST 用 httpx，WebSocket 用 websockets 的同步客户端。收到的都按 Schema 查。"""

    def __init__(self, base: str) -> None:
        self.base = base
        self.http = httpx.Client(base_url=base, headers={"Origin": base}, timeout=30)
        self.ws: ClientConnection | None = None
        self.log: list[Json] = []
        self.pos = 0
        self.pid = ""
        self.last_seq = 0
        self.seq = 0

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
        self.http.close()

    def call(
        self, endpoint: str, status: int, method: str, path: str, body: Json = None, key: str | None = None
    ) -> Json:
        headers = {"Idempotency-Key": key} if key else {}
        r = self.http.request(method, path, json=body, headers=headers)
        assert r.status_code == status, (r.status_code, r.text)
        if not r.content:
            return None
        doc = r.json()
        name = f"api/rest/{endpoint}.schema.json"
        ref = SCHEMAS.endpoint(endpoint)["responses"].get(str(status))
        if ref is None:  # 第 5 节的错误（400、422 等）各接口通用，x-endpoint 里没逐个列
            assert status >= 400
            name, ref = "api/error.schema.json", "#/$defs/ErrorResponse"
        assert SCHEMAS.errors(name, ref, doc) == []
        return doc

    def login(self, code: str) -> Json:
        return self.call("auth-login", 200, "POST", "/v1/auth/login", {"inviteCode": code})

    def start(self) -> Json:
        made = self.call("playthroughs-create", 201, "POST", "/v1/playthroughs", CREATE, key=f"k-{time.monotonic()}")
        self.pid = made["playthroughId"]
        self.last_seq = made["snapshot"]["lastSeq"]
        return made

    def connect(self, last_seq: int | None = None, origin: str | None = None) -> ClientConnection:
        cookie = self.http.cookies.get(COOKIE)
        headers = {"Cookie": f"{COOKIE}={cookie}"} if cookie else {}
        ws = connect(
            f"ws://{self.base.removeprefix('http://')}/v1/playthroughs/{self.pid}/live",
            origin=Origin(origin or self.base),
            additional_headers=headers,
            open_timeout=10,
        )
        self.ws = ws
        self.seq = 0
        if last_seq is not None:
            self.send({"type": "hello", "lastSeq": last_seq, "clientVersion": "test"})
        return ws

    def send(self, msg: Json) -> None:
        assert self.ws is not None
        self.ws.send(json.dumps(msg, ensure_ascii=False))

    def _read(self, timeout: float) -> None:
        assert self.ws is not None
        try:
            frame = self.ws.recv(timeout=timeout)
        except TimeoutError:
            return
        except ConnectionClosed as e:
            self.log.append({"type": "#closed", "code": e.rcvd.code if e.rcvd else None})
            self.ws = None
            return
        if isinstance(frame, bytes):
            assert frame[0] == 0x02 and len(frame) > 5
            self.log.append({"type": "#audio", "turnSeq": int.from_bytes(frame[1:5], "big"), "bytes": len(frame) - 5})
            return
        msg = json.loads(frame)
        assert SCHEMAS.errors(SERVER, "#", msg) == [], msg
        if msg["type"] == "commit":
            assert msg["fromSeq"] == self.last_seq + 1, (msg["fromSeq"], self.last_seq)
            self.last_seq = msg["seq"]
        self.log.append(msg)

    def expect(self, type_: str, timeout: float = 15, **fields: Any) -> Json:
        deadline = time.monotonic() + timeout
        while True:
            while self.pos < len(self.log):
                item = self.log[self.pos]
                self.pos += 1
                if item["type"] == type_ and all(item.get(k) == v for k, v in fields.items()):
                    return item
            left = deadline - time.monotonic()
            if left <= 0 or self.ws is None:
                raise AssertionError(f"没等到 {type_} {fields}；最近 {[x['type'] for x in self.log[-15:]]}")
            self._read(left)

    def focus(self, character: str) -> None:
        self.send({"type": "focus", "character": character})
        self.expect("session_ready", character=character)

    def index(self, type_: str, **fields: Any) -> int:
        """log 里第一条这样的消息的位置。"""
        return next(
            i for i, m in enumerate(self.log) if m["type"] == type_ and all(m.get(k) == v for k, v in fields.items())
        )

    def find(self, type_: str, **fields: Any) -> Json:
        hits = [m for m in self.log if m["type"] == type_ and all(m.get(k) == v for k, v in fields.items())]
        assert len(hits) == 1, (type_, fields, len(hits))
        return hits[0]

    def turn_id(self) -> str:
        return IDS.new("turn")

    def voice(self) -> str:
        turn_id, seq = self.turn_id(), self.seq + 1
        self.seq = seq
        self.send({"type": "activity_start", "turnId": turn_id, "turnSeq": seq})
        assert self.ws is not None
        for _ in range(3):
            self.ws.send(bytes([0x01]) + seq.to_bytes(4, "big") + bytes(1280))
        self.send({"type": "activity_end", "turnId": turn_id, "turnSeq": seq})
        return turn_id

    def text(self, text: str) -> str:
        turn_id, seq = self.turn_id(), self.seq + 1
        self.seq = seq
        self.send({"type": "text", "turnId": turn_id, "turnSeq": seq, "text": text, "via": "typed"})
        return turn_id


@pytest.fixture(scope="module")
def slow(migrated: str) -> Iterator[Services]:
    """ZJ_SPEED=1：人物按真实节奏说话（一句几秒），打断和断线才有固定的窗口。"""
    s = Services(migrated, speed="1")
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture
def player(env: Env, services: Services) -> Iterator[Player]:
    p = Player(services.base)
    p.login(invite(env))
    try:
        yield p
    finally:
        p.close()


def types_for(p: Player, turn_id: str, start: int) -> list[str]:
    out: list[str] = []
    for m in p.log[start:]:
        if m["type"] == "#audio" or m.get("turnId") == turn_id:
            label = m["type"]
            if m["type"] == "transcript":
                label += (
                    f":{'player' if m['speaker'] == 'player' else 'character'}:{'final' if m['final'] else 'partial'}"
                )
            if not out or out[-1] != label or label != "#audio":
                out.append(label)
    return out


def test_voice_turn_then_text_turn(env: Env, player: Player) -> None:
    p = player
    made = p.start()
    snap = p.call("snapshot", 200, "GET", f"/v1/playthroughs/{p.pid}/snapshot")
    assert snap == made["snapshot"] and snap["clock"]["t"] == 1050
    p.connect(last_seq=p.last_seq)
    welcome = p.expect("welcome")
    assert welcome["lastSeq"] == p.last_seq and welcome["lastTurn"] is None
    p.send({"type": "focus", "character": OLD})
    p.expect("session_preparing", character=OLD, reason="switch")
    p.expect("session_ready", character=OLD)

    start = len(p.log)
    voice = p.voice()
    settled = p.expect("turn_settled", turnId=voice)
    assert types_for(p, voice, start) == [
        "transcript:player:partial",
        "transcript:player:final",
        "#audio",
        "transcript:character:partial",
        "#audio",
        "transcript:character:partial",
        "#audio",
        "turn_complete",
        "transcript:character:final",
        "commit",
        "turn_settled",
    ]
    final = p.find("transcript", turnId=voice, speaker=OLD, final=True)
    assert final["source"] == "live" and final["text"]
    complete = p.find("turn_complete", turnId=voice)
    assert complete["audio"] is True and complete["metrics"]["serverReleaseToFirstAudioMs"] is not None
    commit = p.find("commit", turnId=voice)
    assert commit["fromSeq"] == snap["lastSeq"] + 1 and commit["patch"]["clock"]["t"] == 1060
    assert settled["minutes"] == 10 and settled["outcome"] in ("committed", "no_change", "rejected")

    start = len(p.log)
    text = p.text("この市は、ずいぶん静かですね。")
    p.expect("turn_settled", turnId=text)
    kinds = types_for(p, text, start)
    assert kinds[0] == "#audio" and kinds[-3:] == ["transcript:character:final", "commit", "turn_settled"]
    assert "turn_complete" in kinds and not any(k.startswith("transcript:player") for k in kinds)
    assert p.find("commit", turnId=text)["fromSeq"] == commit["seq"] + 1

    evs = p.call("events", 200, "GET", f"/v1/playthroughs/{p.pid}/events?afterSeq=0&limit=50")
    assert evs["lastSeq"] == p.last_seq
    tl = p.call("timeline", 200, "GET", f"/v1/playthroughs/{p.pid}/timeline")
    assert tl["lastSeq"] == p.last_seq
    shown = [i["eventId"] for d in tl["days"] for i in d["items"] if i["kind"] == "event"]
    assert {e["eventId"] for e in evs["events"]} <= set(shown)
    if shown:
        why = p.call("why", 200, "GET", f"/v1/playthroughs/{p.pid}/why?target={shown[-1]}")
        assert why["chain"][-1]["eventId"] == shown[-1]
    r = p.http.get(f"/v1/playthroughs/{p.pid}/why?target=beat.24")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    me = p.call("me", 200, "GET", "/v1/me")
    assert me["activePlaythrough"]["playthroughId"] == p.pid and me["activePlaythrough"]["tLabel"] == "約束の日・夕方"

    async def check_replay() -> list[str] | None:
        engine = env.engine()
        try:
            return await replay(engine, LIBRARY, p.pid)
        finally:
            await engine.dispose()

    assert asyncio.run(check_replay()) == []


def test_reconnect_replays_missing_commits(player: Player) -> None:
    p = player
    p.start()
    before = p.last_seq
    p.connect(last_seq=before)
    p.expect("welcome")
    p.focus(OLD)
    first = p.text("こんばんは。")
    p.expect("turn_settled", turnId=first)
    second = p.text("この市は、ずいぶん静かですね。")
    p.expect("turn_settled", turnId=second)
    assert p.ws is not None
    p.ws.close()
    # 重连，说自己只收到开局：补发两轮的 commit，序号接得上
    p.log, p.pos, p.last_seq = [], 0, before
    p.connect(last_seq=before)
    welcome = p.expect("welcome")
    assert welcome["lastTurn"]["turnId"] == second and welcome["lastTurn"]["status"] == "settled"
    assert welcome["lastTurn"]["playerText"] == "この市は、ずいぶん静かですね。"
    assert welcome["lastTurn"]["characterText"]
    replayed = [p.expect("commit", turnId=first), p.expect("commit", turnId=second)]
    assert replayed[0]["fromSeq"] == before + 1 and replayed[1]["seq"] == welcome["lastSeq"]
    p.send({"type": "ping"})
    p.expect("pong")
    assert not [m for m in p.log if m["type"] == "turn_settled"]  # 判完的轮次不再推


def test_auth_cookie_origin_and_ownership(env: Env, services: Services, player: Player) -> None:
    p = player
    p.start()
    anon = httpx.Client(base_url=services.base, headers={"Origin": services.base})
    assert anon.get("/v1/me").status_code == 401
    r = anon.get(f"/v1/playthroughs/{p.pid}/snapshot")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    bad = anon.post("/v1/auth/login", json={"inviteCode": new_invite_code()})  # 格式对、库里没有
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_invite"

    def closed_with(ws_player: Player, origin: str | None = None) -> int | None:
        ws_player.connect(origin=origin)
        with pytest.raises(ConnectionClosed) as e:
            ws_player.send({"type": "ping"})
            while True:
                assert ws_player.ws is not None
                ws_player.ws.recv(timeout=10)
        return e.value.rcvd.code if e.value.rcvd else None

    stranger = Player(services.base)
    stranger.pid = p.pid
    assert closed_with(stranger) == 4001  # 没有 Cookie
    assert closed_with(p, origin="http://evil.example") == 4003  # Origin 不对
    other = Player(services.base)
    other.login(invite(env))
    other.pid = p.pid
    assert closed_with(other) == 4003  # 别人的局
    r = other.http.get(f"/v1/playthroughs/{p.pid}/snapshot")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    cross = p.http.post(
        "/v1/playthroughs", json=CREATE, headers={"Origin": "http://evil.example", "Idempotency-Key": "x"}
    )
    assert cross.status_code == 403
    plain = p.http.post("/v1/playthroughs", content=json.dumps(CREATE), headers={"Content-Type": "text/plain"})
    assert plain.status_code == 403

    # 邀请码：大小写、空格、多余的短横线、I/L/O 的写法都认；库里只有哈希
    code = invite(env)
    messy = "  " + code.upper().replace("-", " - ").replace("1", "l").replace("0", "o") + " "
    again = Player(services.base)
    assert again.login(messy)["user"]["userRef"] == again.login(code)["user"]["userRef"]

    async def stored() -> list[Any]:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                return [tuple(r) for r in (await c.execute(select(invite_codes))).all()]
        finally:
            await engine.dispose()

    rows = asyncio.run(stored())
    assert len(rows) == 3  # player、other 和上面这个
    assert all(code not in str(r) and code.removeprefix("inv-") not in str(r) for r in rows)

    p.call("auth-logout", 204, "POST", "/v1/auth/logout", {})
    assert p.http.get("/v1/me").status_code == 401
    for c in (stranger, other, again, anon):
        c.close()


def test_other_tab_closes_the_old_connection_with_4009(player: Player) -> None:
    p = player
    p.start()
    old = p.connect(last_seq=p.last_seq)
    p.expect("welcome")
    p.connect(last_seq=p.last_seq)
    with pytest.raises(ConnectionClosed) as e:
        while True:
            old.recv(timeout=10)
    assert e.value.rcvd is not None and e.value.rcvd.code == 4009
    p.focus(OLD)
    p.expect("turn_settled", turnId=p.text("こんばんは。"))


def test_idempotency_and_one_active_playthrough(player: Player) -> None:
    p = player
    first = p.call("playthroughs-create", 201, "POST", "/v1/playthroughs", CREATE, key="same")
    again = p.call("playthroughs-create", 201, "POST", "/v1/playthroughs", CREATE, key="same")
    assert again == first
    conflict = {"bookId": "hashire-merosu", "roleId": "role.apprentice"}
    p.call("playthroughs-create", 422, "POST", "/v1/playthroughs", conflict, key="same")
    busy = p.call("playthroughs-create", 409, "POST", "/v1/playthroughs", CREATE, key="other")
    assert busy["activePlaythrough"]["playthroughId"] == first["playthroughId"]
    r = p.http.post("/v1/playthroughs", json=CREATE)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"


def test_same_key_at_the_same_time_gets_the_same_201(env: Env, services: Services) -> None:
    """断网重试会用同一个键并发：排队处理，都拿到同一个 201（前端评审 #26 第 5 条）。"""
    p = Player(services.base)
    p.login(invite(env))
    clients = [
        httpx.Client(base_url=services.base, headers={"Origin": services.base}, cookies=p.http.cookies, timeout=30)
        for _ in range(3)
    ]
    try:
        with ThreadPoolExecutor(len(clients)) as pool:
            rs = list(
                pool.map(
                    lambda c: c.post("/v1/playthroughs", json=CREATE, headers={"Idempotency-Key": "together"}), clients
                )
            )
        assert [r.status_code for r in rs] == [201, 201, 201], [r.text for r in rs]
        assert len({r.json()["playthroughId"] for r in rs}) == 1
    finally:
        for c in clients:
            c.close()
        p.close()


def test_back_to_back_turns_each_settle_after_their_commit(player: Player) -> None:
    """前端评审 #26 第 1、2 条：不等回答连发，每一轮都交上去，人物定稿、commit、turn_settled 各一条，
    turn_settled 在它自己的 commit 之后。速度 0 时多数轮次是被下一轮打断的。"""
    p = player
    p.start()
    p.connect(last_seq=p.last_seq)
    p.expect("welcome")
    p.focus(OLD)
    ids = [p.text(f"{i + 1}つ目の質問です。") for i in range(12)]
    deadline = time.monotonic() + 60
    while len(settled := [m["turnId"] for m in p.log if m["type"] == "turn_settled"]) < len(ids):
        assert time.monotonic() < deadline and p.ws is not None, settled
        p._read(1)
    assert settled == ids  # 叙事者按玩家发的顺序判
    for t in ids:
        said = [m for m in p.log if m["type"] == "transcript" and m.get("turnId") == t and m["speaker"] == OLD]
        finals = [m for m in said if m["final"]]
        assert len([m for m in p.log if m["type"] == "turn_settled" and m.get("turnId") == t]) == 1, t
        assert p.index("commit", turnId=t) < p.index("turn_settled", turnId=t), t
        cut = [m for m in p.log if m["type"] == "interrupted" and m.get("turnId") == t]
        complete = [m for m in p.log if m["type"] == "turn_complete" and m.get("turnId") == t]
        assert len(cut) + len(complete) == 1, t  # 被打断的没有 turn_complete
        # 说完的一条定稿；被打断的说到哪定稿到哪，还没出字的没有定稿
        assert len(finals) == (1 if complete or len(said) > len(finals) else 0), t


def test_cut_in_while_the_character_speaks(env: Env, slow: Services) -> None:
    """人物说到一半发下一轮：旧的一轮 interrupted、半句定稿、不再有音频，照样 commit 和 turn_settled；
    这些都在新的一轮之前（3.2、3.3）。"""
    p = Player(slow.base)
    p.login(invite(env))
    try:
        p.start()
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        p.focus(OLD)
        first = p.text("こんばんは。")
        half = p.expect("transcript", turnId=first, speaker=OLD, final=False)
        second = p.text("待ってください。")
        p.expect("turn_settled", turnId=second, timeout=30)
        cut = p.index("interrupted", turnId=first)
        assert cut < min(i for i, m in enumerate(p.log) if m.get("turnId") == second)
        final = p.find("transcript", turnId=first, speaker=OLD, final=True)
        assert final["source"] == "live" and final["text"] == half["text"]
        assert not [m for m in p.log if m["type"] == "turn_complete" and m.get("turnId") == first]
        assert not [m for m in p.log[cut:] if m["type"] == "#audio" and m["turnSeq"] == 1]
        assert p.index("commit", turnId=first) < p.index("turn_settled", turnId=first)
        assert p.find("turn_complete", turnId=second)["audio"] is True
    finally:
        p.close()


def test_disconnect_while_speaking_leaves_the_turn_lost(env: Env, slow: Services) -> None:
    """人物还没说完就断线：这一轮不交给叙事者，重连时 lastTurn.status = lost（第 4 节）。
    断了马上重连也一样：hello 先等旧连接把这一轮写下来，不会拿上一轮当 lastTurn、让前端重发（#100 评审）。"""
    p = Player(slow.base)
    p.login(invite(env))
    try:
        p.start()
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        p.focus(OLD)
        t = p.text("こんばんは。")
        p.expect("transcript", turnId=t, speaker=OLD, final=False)
        assert p.ws is not None
        p.ws.close()
        p.log, p.pos = [], 0
        p.connect(last_seq=p.last_seq)  # 不等：网关这时可能还没处理完断线
        last = p.expect("welcome")["lastTurn"]
        assert last is not None and last["turnId"] == t and last["status"] == "lost"
        assert last["playerText"] == "こんばんは。"
        p.send({"type": "ping"})
        p.expect("pong")
        assert not [m for m in p.log if m.get("turnId") == t]  # 没有 commit、turn_settled
    finally:
        p.close()


def test_reconnect_while_the_old_connection_is_still_open_sees_the_lost_turn(env: Env, slow: Services) -> None:
    """换了网络、服务端还没发现旧连接断了，前端就连上来：新连接踢掉旧的（4009），hello 等旧连接把人物没说完的
    那一轮写成 lost 再回 welcome。lastTurn 不能是上一轮，否则前端照规矩重发，人物答两次（#100 评审）。"""
    p = Player(slow.base)
    p.login(invite(env))
    try:
        p.start()
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        p.focus(OLD)
        first = p.text("こんばんは。")
        p.expect("turn_settled", turnId=first, timeout=30)
        t = p.text("待ってください。")
        p.expect("transcript", turnId=t, speaker=OLD, final=False)
        old = p.ws
        assert old is not None
        p.log, p.pos = [], 0
        p.connect(last_seq=p.last_seq)
        last = p.expect("welcome")["lastTurn"]
        assert last is not None and last["turnId"] == t and last["status"] == "lost", last
        p.send({"type": "ping"})
        p.expect("pong")
        assert not [m for m in p.log if m.get("turnId") == t]
        with contextlib.suppress(Exception):
            old.close()
    finally:
        p.close()


def test_reconnect_while_the_player_is_still_holding_sees_the_lost_turn(env: Env, slow: Services) -> None:
    """玩家按着说话键时断了线（没有 activity_end）：这一轮也记成 lost，重连的 lastTurn 是它，前端才会让人物说
    「もう一度」；它不交给叙事者，不会有 turn_settled（#109 评审）。"""
    p = Player(slow.base)
    p.login(invite(env))
    try:
        p.start()
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        p.focus(OLD)
        first = p.text("こんばんは。")
        p.expect("turn_settled", turnId=first, timeout=30)
        t, seq = p.turn_id(), p.seq + 1
        p.seq = seq
        p.send({"type": "activity_start", "turnId": t, "turnSeq": seq})
        old = p.ws
        assert old is not None
        for _ in range(3):
            old.send(bytes([0x01]) + seq.to_bytes(4, "big") + bytes(1280))
        p.send({"type": "ping"})
        p.expect("pong")
        p.log, p.pos = [], 0
        p.connect(last_seq=p.last_seq)
        last = p.expect("welcome")["lastTurn"]
        assert last is not None and last["turnId"] == t and last["status"] == "lost", last
        p.send({"type": "ping"})
        p.expect("pong")
        assert not [m for m in p.log if m.get("turnId") == t]
        with contextlib.suppress(Exception):
            old.close()
    finally:
        p.close()


def test_routes_b0_does_not_mount_are_404(player: Player) -> None:
    p = player
    p.start()
    for path in (f"/v1/playthroughs/{p.pid}/share", "/v1/nothing"):
        r = p.http.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", path
    r = p.http.get("/v1/playthroughs/pt_00000000000000000000000000/snapshot")
    assert r.status_code == 404


def test_bad_and_unhandled_messages(player: Player) -> None:
    p = player
    p.start()
    p.connect()
    p.text("こんばんは。")  # hello 之前：回 error，不处理（不然这一轮的 turn_settled 永远不来）
    assert p.expect("error")["error"]["code"] == "invalid_request"
    p.send({"type": "hello", "lastSeq": p.last_seq, "clientVersion": "test"})
    p.expect("welcome")
    p.text("こんばんは。")  # 还没 focus 人物
    assert p.expect("error")["error"]["code"] == "invalid_request"
    for who in ("char.crowd", "char.nobody"):  # 不能说话的、不存在的
        p.send({"type": "focus", "character": who})
        assert p.expect("error")["error"]["code"] == "invalid_request"
    p.send({"type": "focus"})  # 少了 character
    assert p.expect("error")["error"]["code"] == "invalid_request"
    assert p.ws is not None
    p.ws.send("not json")
    assert p.expect("error")["error"]["code"] == "invalid_request"
    p.send({"type": "near", "character": OLD})  # 合 Schema、B-0 不处理：忽略，不断开
    p.send({"type": "ping"})
    p.expect("pong")


def test_sigterm_sends_goaway_then_1012(env: Env, migrated: str) -> None:
    s = Services(migrated)
    try:
        p = Player(s.base)
        p.login(invite(env))
        p.start()
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        s.gateway.p.send_signal(signal.SIGTERM)
        goaway = p.expect("goaway")
        assert goaway["reason"] == "deploy" and goaway["reconnectAfterMs"] > 0
        assert p.expect("#closed")["code"] == 1012
        s.gateway.p.wait(timeout=15)
        p.close()
    finally:
        s.stop()
