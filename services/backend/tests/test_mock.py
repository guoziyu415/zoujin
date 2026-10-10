"""B-1 mock 的契约测试：真的 uvicorn、真的 WebSocket 客户端（B-1「验收」）。

- 每个剧本在 `--speed 0` 下跑完：收到的每条消息都过 Schema，剧本没有报错地走到最后。
- 导览按 0.04 倍的时间跑一遍：要靠时机的情形（打断、作废、按按钮回答确认、结局先 202 后 200）照真的样子检查，
  并做覆盖检查（3.3 的服务端消息除 event_rejected 都出现过）。
- REST 的 16 个接口、409 → 删除 → 重新开局、expire-session、drop 之后补发不重不漏。
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect
from websockets.typing import Origin
from zoujin_backend.mock import scripts
from zoujin_backend.mock.app import create_app
from zoujin_backend.mock.core import COOKIE, REPO, Config, Mock
from zoujin_backend.mock.ids import IdGen
from zoujin_backend.mock.schemas import SERVER, SchemaBook, SchemaError

Json = Any

BOOK = SchemaBook(REPO / "packages" / "contracts" / "schemas")
SESSIONS = REPO / "fixtures" / "sessions"
EXAMPLES = REPO / "packages" / "contracts" / "examples" / "valid" / "api" / "rest"
TIMED_SPEED = 0.04
MELOS = "char.melos"
OLD = "char.old-man"


# —— 服务和客户端 ——


class Server:
    """在后台线程里跑真的 uvicorn（和 `zoujin-mock` 同一个 WebSocket 实现），端口由系统分配。"""

    def __init__(self, speed: float) -> None:
        self.app = create_app(Config(speed=speed, strict=True, seed=7))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port: int = self.sock.getsockname()[1]
        config = uvicorn.Config(self.app, ws="websockets-sansio", log_level="warning", lifespan="off")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.sock]}, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def mock(self) -> Mock:
        m: Mock = self.app.state.mock
        return m

    def __enter__(self) -> Server:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            assert time.monotonic() < deadline, "mock 没起来"
            time.sleep(0.01)
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.sock.close()


def rest_ok(endpoint: str, status: int, r: httpx.Response) -> Json:
    """状态码对，响应体（有的话）过 Schema；接口没单列的错误状态按第 5 节的错误形状查。"""
    assert r.status_code == status, (endpoint, r.status_code, r.text)
    responses = BOOK.endpoint(endpoint)["responses"]
    base, ref = f"api/rest/{endpoint}.schema.json", responses.get(str(status), "")
    if not ref and status >= 400:
        base, ref = "api/error.schema.json", "#/$defs/ErrorResponse"
    if ref is None:
        assert not r.content
        return None
    doc = r.json()
    errs = BOOK.errors(base, ref, doc)
    assert not errs, (endpoint, errs)
    return doc


class Player:
    """前端的样子：REST 用 httpx，WebSocket 用 websockets 的同步客户端。收到的每条消息都再按 Schema 查一遍。"""

    def __init__(self, server: Server, timed: bool) -> None:
        self.server = server
        self.timed = timed
        self.http = httpx.Client(base_url=server.base, headers={"Origin": server.base}, timeout=10, trust_env=False)
        self.ws: ClientConnection | None = None
        self.log: list[Json] = []  # 收到的全部；二进制帧记成 {"type": "#audio"}，连接关闭记成 {"type": "#closed"}
        self.pos = 0  # expect 读到哪里
        self.seq = 0  # 这条连接上的 turnSeq
        self.last_seq = 0
        self.pid = ""
        self.ids = IdGen(11)
        self.hit: set[str] = set()  # 回过 Schema 校验的 REST 接口

    # —— REST ——

    def call(self, endpoint: str, status: int, path: str, body: Json = None, *, key: bool = False) -> Json:
        method = BOOK.endpoint(endpoint)["method"]
        headers = {"Idempotency-Key": str(uuid.uuid4())} if key else {}
        if method in ("POST", "DELETE"):
            headers["Content-Type"] = "application/json"  # 第 0 节：改数据的请求都要（没有请求体也要）
        content = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        r = self.http.request(method, path, content=content, headers=headers)
        self.hit.add(endpoint)
        return rest_ok(endpoint, status, r)

    def login(self) -> None:
        self.call("auth-login", 200, "/v1/auth/login", {"inviteCode": "mock"})

    def start(self, scenario: str) -> None:
        r = self.http.post("/__mock/scenario", json={"name": scenario})
        assert r.status_code == 200, r.text
        doc = self.call(
            "playthroughs-create",
            201,
            "/v1/playthroughs",
            {"bookId": "hashire-merosu", "roleId": "role.traveler"},
            key=True,
        )
        self.pid = doc["playthroughId"]
        self.connect()

    # —— WebSocket ——

    def open(self) -> ClientConnection:
        cookie = self.http.cookies.get(COOKIE)
        return connect(
            f"ws://127.0.0.1:{self.server.port}/v1/playthroughs/{self.pid}/live",
            origin=Origin(self.server.base),
            additional_headers={"Cookie": f"{COOKIE}={cookie}"},
            proxy=None,
            open_timeout=10,
            max_queue=None,
            legacy=True,  # 直接拿到连接（websockets 17 的写法），Player 自己管关闭
        )

    def connect(self) -> Json:
        self.ws = self.open()
        self.seq = 0  # turnSeq 只在一条连接内有效（3.1）
        self.send({"type": "hello", "lastSeq": self.last_seq, "clientVersion": "web-test"})
        return self.expect("welcome")

    def send(self, msg: Json) -> None:
        assert self.ws is not None
        self.ws.send(json.dumps(msg, ensure_ascii=False))

    def _read(self, timeout: float) -> None:
        assert self.ws is not None
        try:
            data = self.ws.recv(timeout=timeout)
        except TimeoutError:
            return
        except ConnectionClosed as e:
            self.log.append({"type": "#closed", "code": e.rcvd.code if e.rcvd is not None else 1006})
            self.ws = None
            return
        if isinstance(data, bytes):
            assert data[0] == 0x02 and len(data) > 5
            self.log.append({"type": "#audio", "turnSeq": int.from_bytes(data[1:5], "big")})
            return
        item = json.loads(data)
        if item["type"] != "future_feature":
            errs = BOOK.errors(SERVER, "#", item)
            assert not errs, (item, errs)
        if item["type"] == "commit":
            self.last_seq = item["seq"]
        self.log.append(item)

    def expect(self, type_: str, timeout: float = 10, **fields: Any) -> Json:
        """往后读，直到一条 type 和字段都对上的消息（跳过的照样留在 log 里）。"""
        deadline = time.monotonic() + timeout
        while True:
            while self.pos < len(self.log):
                item = self.log[self.pos]
                self.pos += 1
                if item["type"] == type_ and all(item.get(k) == v for k, v in fields.items()):
                    return item
            left = deadline - time.monotonic()
            if left <= 0 or self.ws is None:
                recent = [x["type"] for x in self.log[-20:] if x["type"] != "#audio"]
                raise AssertionError(f"没等到 {type_} {fields}；最近收到 {recent}")
            self._read(left)

    def find(self, type_: str, **fields: Any) -> list[Json]:
        return [x for x in self.log if x["type"] == type_ and all(x.get(k) == v for k, v in fields.items())]

    # —— 玩家的动作 ——

    def focus(self, character: str) -> None:
        self.send({"type": "focus", "character": character})
        self.expect("session_ready", character=character)

    def press(self, purpose: str | None = None) -> tuple[str, int]:
        self.seq += 1
        turn = self.ids.new("turn"), self.seq
        msg = {"type": "activity_start", "turnId": turn[0], "turnSeq": turn[1]}
        if purpose:
            msg["purpose"] = purpose
        self.send(msg)
        assert self.ws is not None
        for _ in range(2):  # 上行麦克风音频：16 kHz、40 ms 一帧（mock 不听）
            self.ws.send(bytes([0x01]) + turn[1].to_bytes(4, "big") + bytes(1280))
        return turn

    def release(self, turn: tuple[str, int]) -> str:
        self.send({"type": "activity_end", "turnId": turn[0], "turnSeq": turn[1]})
        return turn[0]

    def speak(self) -> str:
        return self.release(self.press())

    def say(self, text: str, via: str = "typed", **extra: Any) -> str:
        self.seq += 1
        turn_id = self.ids.new("turn")
        self.send({"type": "text", "turnId": turn_id, "turnSeq": self.seq, "text": text, "via": via, **extra})
        return turn_id

    def msg_id(self) -> str:
        return str(uuid.uuid4())

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
        self.http.close()


def kind(item: Json) -> str:
    """一轮里的消息归成 3.5 示例里的样子。"""
    if item["type"] == "transcript":
        who = "player" if item["speaker"] == "player" else "char"
        return f"transcript:{who}:{'final' if item['final'] else 'partial'}"
    return str(item["type"])


def in_order(items: list[str], wanted: list[str]) -> bool:
    it = iter(items)
    return all(w in it for w in wanted)


def turn_items(p: Player, turn_id: str, turn_seq: int | None = None) -> list[Json]:
    return [
        x
        for x in p.log
        if x.get("turnId") == turn_id or (x["type"] == "#audio" and turn_seq is not None and x["turnSeq"] == turn_seq)
    ]


# —— 每个剧本里玩家要做的事（和 fixtures/sessions/README.md 一致）——


def play_full_turn(p: Player) -> None:
    p.focus(MELOS)
    turn = p.press()
    p.release(turn)
    settled = p.expect("turn_settled", turnId=turn[0])
    assert settled["outcome"] == "committed" and settled["minutes"] == 10
    kinds = [kind(x) for x in turn_items(p, turn[0], turn[1])]
    assert in_order(
        kinds,
        [
            "transcript:player:partial",
            "transcript:player:final",
            "#audio",
            "transcript:char:partial",
            "turn_complete",
            "transcript:char:final",
            "suggestions",
            "commit",
            "turn_settled",
        ],
    ), kinds
    (commit,) = p.find("commit", turnId=turn[0])
    (event,) = commit["events"]
    assert settled["eventIds"] == [event["eventId"]] and event["keyMoment"]
    assert commit["memories"][0]["change"] == "added"
    step = commit["reveal"]["chain"][0]
    assert step["eventId"] == event["eventId"] and step["seq"] == event["seq"]
    assert commit["fromSeq"] == event["seq"]


def play_small_talk(p: Player) -> None:
    p.focus(OLD)
    turn_id = p.say("もうすぐ日が暮れますね。")
    settled = p.expect("turn_settled", turnId=turn_id)
    assert settled["outcome"] == "no_change" and settled["eventIds"] == [] and settled["minutes"] == 10
    (commit,) = p.find("commit", turnId=turn_id)
    assert commit["events"] == [] and list(commit["patch"]) == ["clock"]


def play_interrupt(p: Player) -> None:
    p.focus(MELOS)
    first = p.press()
    p.release(first)
    p.expect("#audio", turnSeq=first[1])
    second = p.press()  # 人物说话时按下 = 打断（3.2）
    if p.timed:
        p.expect("interrupted", turnId=first[0])
    p.release(second)
    p.expect("turn_settled", turnId=first[0])
    p.expect("turn_settled", turnId=second[0])
    if p.timed:
        cut = next(i for i, x in enumerate(p.log) if x["type"] == "interrupted")
        assert not [x for x in p.log[cut:] if x["type"] == "#audio" and x["turnSeq"] == first[1]]
        assert not p.find("turn_complete", turnId=first[0])
        (final,) = p.find("transcript", turnId=first[0], speaker=MELOS, final=True)
        assert final["text"] == "いかにも、メロスだ。妹の"


def play_retract(p: Player) -> None:
    p.focus(OLD)
    first = p.say("王様のことを、聞いてもいいですか。")
    p.expect("turn_complete", turnId=first)
    p.send({"type": "turn_retract", "turnId": first})  # 「言い直す」
    result = p.expect("turn_retract_result", turnId=first)
    if p.timed:
        assert result["status"] == "retracted"
        p.expect("turn_settled", turnId=first, outcome="retracted", minutes=0)
        p.expect("session_preparing", character=OLD, reason="rebuild")
    second = p.say("今夜の宿を探しています。")
    p.expect("turn_settled", turnId=second)
    p.send({"type": "turn_retract", "turnId": second})
    assert p.expect("turn_retract_result", turnId=second)["status"] == "too_late"
    third = p.speak()
    p.expect("transcript", turnId=third, speaker="player", final=True)
    p.send({"type": "turn_retract", "turnId": third})  # 识别改正（3.6 第 6 条）
    fixed = p.say("王城は、どっちですか。", via="correction", replaces=third)
    result = p.expect("turn_retract_result", turnId=third)
    p.expect("turn_settled", turnId=fixed)
    if p.timed:
        assert result["status"] == "retracted"
        assert not p.find("commit", turnId=first) and not p.find("commit", turnId=third)


def play_confirm(p: Player) -> None:
    p.focus(MELOS)
    first = p.say("何かあったら、私が力になります。")
    confirm = p.expect("confirm", character=MELOS)
    p.send({"type": "confirm_answer", "draftId": confirm["draftId"], "optionId": "yes"})
    p.expect("confirm_closed", draftId=confirm["draftId"], optionId="yes", by="button")
    assert p.expect("turn_settled", turnId=first)["outcome"] == "committed"
    (commit,) = p.find("commit", turnId=first)
    assert commit["events"][0]["promise"]["change"] == "made" and commit["promises"][0]["status"] == "open"
    second = p.say("私も、王城へ一緒に行きます。")
    started = p.expect("turn_started", reason="confirm", speaker=MELOS)
    assert started["turnSeq"] > 0x80000000
    confirm = p.expect("confirm")
    p.expect("confirm_closed", draftId=confirm["draftId"], optionId=None, by="timeout")
    assert p.expect("turn_settled", turnId=second)["outcome"] == "no_change"


def play_approach(p: Player) -> None:
    p.expect("approach", character=OLD, kind="request")
    p.send({"type": "approach_arrived", "character": OLD})
    started = p.expect("turn_started", reason="approach", speaker=OLD)
    assert started["turnSeq"] > 0x80000000
    p.expect("#audio", turnSeq=started["turnSeq"])
    p.expect("suggestions", turnId=started["turnId"])
    p.focus(OLD)
    answer = p.say("手伝います", via="chip")
    p.expect("turn_settled", turnId=answer)
    msg_id = p.msg_id()
    p.send(
        {"type": "action", "clientMsgId": msg_id, "actionId": "act_help_old-man_cart", "kind": "help", "target": OLD}
    )
    result = p.expect("action_result", clientMsgId=msg_id)
    assert result["status"] == "done" and result["minutes"] == 60
    commit = p.log[p.log.index(result) - 1]
    assert commit["type"] == "commit" and [e["eventId"] for e in commit["events"]] == result["eventIds"]


def play_act_end(p: Player, voice: bool) -> None:
    p.expect("turn_started", reason="leaving", speaker=MELOS)
    ended = p.expect("act_ended", actId="act.1")
    p.send({"type": "act_choose", "clientMsgId": p.msg_id(), "optionId": "exit.9.nowhere"})
    assert p.expect("error")["error"]["code"] == "invalid_choice"
    if voice:
        turn = p.press(purpose="act_plan")
        p.release(turn)
        p.expect("transcript", turnId=turn[0], speaker="player", final=True)
        plan = p.expect("act_plan_result", turnId=turn[0])
    else:
        msg_id = p.msg_id()
        p.send({"type": "act_propose", "clientMsgId": msg_id, "text": "夜明けを待って村へ向かいたい"})
        plan = p.expect("act_plan_result", clientMsgId=msg_id)
    assert not plan["accepted"] and plan["triesLeft"] == 1
    assert ended["options"] and plan["alternative"]["optionId"].startswith("plan_")
    p.send({"type": "act_choose", "clientMsgId": p.msg_id(), "optionId": plan["alternative"]["optionId"]})
    transition = p.expect("act_transition", fromActId="act.1", toActId="act.4")
    assert transition["snapshot"]["lastSeq"] == p.last_seq
    assert transition["snapshot"]["pending"]["actEnd"] is None
    snap = p.call("snapshot", 200, f"/v1/playthroughs/{p.pid}/snapshot")
    assert snap["actId"] == "act.4" and snap["clock"]["t"] == 5370


def play_goaway(p: Player) -> None:
    p.focus(OLD)
    turn_id = p.say("市場は、もう閉まったのですか。")
    p.expect("goaway", reason="deploy")
    assert p.expect("#closed")["code"] == 1012
    if p.timed:
        time.sleep(0.4)  # 断线期间这一轮判完
    welcome = p.connect()
    p.expect("commit", turnId=turn_id)  # 补发（timed）或重连后照常推
    if p.timed:
        assert welcome["lastTurn"]["turnId"] == turn_id and welcome["lastTurn"]["status"] == "settled"
        assert p.log.index(welcome) < p.log.index(p.find("commit", turnId=turn_id)[0])


def play_other_tab(p: Player) -> None:
    p.focus(OLD)
    old = p.ws
    assert old is not None
    p.connect()  # 同一局在别的标签页打开
    with pytest.raises(ConnectionClosed) as closed:
        while True:
            old.recv(timeout=10)
    assert closed.value.rcvd is not None and closed.value.rcvd.code == 4009
    p.focus(OLD)
    p.expect("turn_settled", turnId=p.say("もうすぐ日が暮れますね。"))


def play_safety(p: Player) -> None:
    p.focus(OLD)
    first = p.say("……もう、ここで終わりにしたい。")
    p.expect("safety_hint")
    assert p.expect("turn_settled", turnId=first)["outcome"] == "no_change"
    second = p.say("本当に、もう終わりにしたいんです。")
    p.expect("turn_settled", turnId=second, outcome="paused", minutes=0)
    p.expect("safety_pause")
    p.send({"type": "safety_resume"})
    p.expect("safety_resumed")


def play_ending(p: Player) -> None:
    p.expect("ending_started", trigger="story-closed")
    if p.timed:
        p.call("ending", 202, f"/v1/playthroughs/{p.pid}/ending")
    ready = p.expect("ending_ready")
    ending = p.call("ending", 200, f"/v1/playthroughs/{p.pid}/ending")
    assert ending["endingId"] == ready["endingId"]
    cue = [c["cue"] for c in p.find("commit") if c["cue"] is not None]
    assert cue == [{"kind": "arrival_capped", "speaker": None, "text": "この足なら、陽の沈む前に着く。"}]


def play_late_transcript(p: Player, text: bool) -> None:
    p.focus(OLD)
    turn_id = p.say("お名前を、伺ってもいいですか。" if text else "この噴水は、古いのですか。")
    complete = p.expect("turn_complete", turnId=turn_id, audio=True)
    final = p.expect("transcript", turnId=turn_id, speaker=OLD, final=True, source="fallback")
    assert p.log.index(complete) < p.log.index(final)
    assert not p.find("transcript", turnId=turn_id, speaker=OLD, final=False)
    assert (final["text"] is not None) == text
    p.expect("turn_settled", turnId=turn_id)


def play_no_audio(p: Player) -> None:
    p.focus(OLD)
    turn = p.press()
    p.release(turn)
    complete = p.expect("turn_complete", turnId=turn[0], audio=False)
    assert complete["metrics"]["serverReleaseToFirstAudioMs"] is None
    p.expect("turn_settled", turnId=turn[0], outcome="no_response", minutes=0)
    assert not p.find("#audio", turnSeq=turn[1])


def play_degraded(p: Player) -> None:
    p.expect("degraded", reason="budget")
    p.send({"type": "focus", "character": OLD})
    p.expect("session_ready", character=OLD, voiceAvailable=False)
    turn_id = p.say("刑場には、何があるのですか。")
    p.expect("transcript", turnId=turn_id, speaker=OLD, final=True)
    p.expect("turn_complete", turnId=turn_id, audio=False)
    p.expect("turn_settled", turnId=turn_id, outcome="no_change", minutes=15)


def play_limits(p: Player) -> None:
    p.expect("limits", voiceMinutesLeft=5)
    assert p.call("me", 200, "/v1/me")["limits"]["voiceMinutesLeft"] == 5


def play_future_message(p: Player) -> None:
    p.expect("future_feature")
    p.expect("narration")


TOUR = [
    "full-turn",
    "small-talk",
    "approach",
    "confirm",
    "interrupt",
    "retract",
    "late-transcript",
    "transcript-failed",
    "no-audio",
    "safety",
    "goaway",
    "limits",
    "future-message",
    "act-end",
    "degraded",
    "ending",
]


def play(name: str, p: Player, *, in_tour: bool = False) -> None:
    plays: dict[str, Callable[[], None]] = {
        "full-turn": lambda: play_full_turn(p),
        "small-talk": lambda: play_small_talk(p),
        "interrupt": lambda: play_interrupt(p),
        "retract": lambda: play_retract(p),
        "confirm": lambda: play_confirm(p),
        "approach": lambda: play_approach(p),
        "act-end": lambda: play_act_end(p, voice=not in_tour),
        "goaway": lambda: play_goaway(p),
        "other-tab": lambda: play_other_tab(p),
        "safety": lambda: play_safety(p),
        "ending": lambda: play_ending(p),
        "late-transcript": lambda: play_late_transcript(p, text=True),
        "transcript-failed": lambda: play_late_transcript(p, text=False),
        "no-audio": lambda: play_no_audio(p),
        "degraded": lambda: play_degraded(p),
        "limits": lambda: play_limits(p),
        "future-message": lambda: play_future_message(p),
        "tour": lambda: play_tour(p),
    }
    plays[name]()


def play_tour(p: Player) -> None:
    for name in TOUR:
        play(name, p, in_tour=True)


def wait_finished(server: Server, pid: str) -> None:
    """剧本走到最后，而且没有报错（strict：剧本或自检出错时任务带着异常结束）。"""
    live = server.mock.lives[pid]
    deadline = time.monotonic() + 10
    while live.task is None or not live.task.done():
        assert time.monotonic() < deadline, "剧本没走完"
        time.sleep(0.01)
    assert not live.task.cancelled() and live.task.exception() is None
    assert live.finished.is_set()


# —— fixtures ——


@pytest.fixture(scope="module")
def fast() -> Iterator[Server]:
    with Server(speed=0) as s:
        yield s


@pytest.fixture(scope="module")
def timed() -> Iterator[Server]:
    with Server(speed=TIMED_SPEED) as s:
        yield s


def new_player(server: Server, *, timed: bool = False) -> Player:
    r = httpx.post(f"{server.base}/__mock/reset", trust_env=False)
    assert r.status_code == 200
    p = Player(server, timed)
    p.login()
    return p


# —— 剧本 ——


def test_every_scenario_has_a_play() -> None:
    names = scripts.names(SESSIONS)
    assert len([n for n in names if n != "tour"]) >= 17
    for n in names:
        assert n in {*TOUR, "other-tab", "tour"}, n


@pytest.mark.parametrize("name", scripts.names(SESSIONS))
def test_scenario_runs_at_speed_0(fast: Server, name: str) -> None:
    p = new_player(fast)
    try:
        p.start(name)
        play(name, p)
        wait_finished(fast, p.pid)
    finally:
        p.close()


def test_tour_in_scaled_time_covers_every_server_message(timed: Server) -> None:
    p = new_player(timed, timed=True)
    try:
        p.start("tour")
        p.send({"type": "ping"})
        p.expect("pong")
        p.send({"type": "no_such_message"})
        assert p.expect("error")["error"]["code"] == "invalid_request"
        play("tour", p)
        wait_finished(timed, p.pid)
        seen = {x["type"] for x in p.log}
        missing = set(BOOK.ws_types("server")) - {"event_rejected"} - seen
        assert not missing, f"没有剧本发过：{sorted(missing)}"
        sent = {e["eventId"] for c in p.find("commit") for e in c["events"]}
        ending = p.call("ending", 200, f"/v1/playthroughs/{p.pid}/ending")
        cited = {i for part in ending["you"]["youDid"] + ending["world"]["epilogue"] for i in part["cites"]}
        assert cited <= sent, cited - sent
    finally:
        p.close()


# —— REST、状态和控制接口 ——


def test_rest_endpoints(fast: Server) -> None:
    p = new_player(fast)
    create = {"bookId": "hashire-merosu", "roleId": "role.traveler"}
    try:
        rest_ok("auth-login", 401, p.http.post("/v1/auth/login", json={"inviteCode": "wrong"}))
        assert p.call("me", 200, "/v1/me")["activePlaythrough"] is None
        p.call("manifest", 200, "/v1/books/hashire-merosu/manifest")
        p.start("small-talk")
        busy = p.call("playthroughs-create", 409, "/v1/playthroughs", create, key=True)
        assert busy["activePlaythrough"]["playthroughId"] == p.pid
        base = f"/v1/playthroughs/{p.pid}"
        p.call("snapshot", 200, f"{base}/snapshot")
        p.call("timeline", 200, f"{base}/timeline")
        p.call("why", 200, f"{base}/why?target=beat.03")
        book = p.call("memories", 200, f"{base}/memories")
        (melos,) = [c for c in book["characters"] if c["character"] == MELOS]
        promise_memory = next(m for m in melos["memories"] if m["promiseId"] is not None)
        mid = promise_memory["memoryId"]
        assert p.call("memory-impact", 200, f"{base}/memories/{mid}/impact")["voidsPromise"]
        deleted = p.call("memory-delete", 200, f"{base}/memories/{mid}", key=True)
        assert deleted["memoryId"] == mid and deleted["promiseVoided"] == promise_memory["promiseId"]
        p.expect("session_preparing", character=MELOS, reason="rebuild")
        book = p.call("memories", 200, f"{base}/memories")
        (melos,) = [c for c in book["characters"] if c["character"] == MELOS]
        assert mid not in {m["memoryId"] for m in melos["memories"]}
        assert melos["promises"][0]["status"] == "voided"
        p.call("memory-delete", 404, f"{base}/memories/{mid}", key=True)
        t = p.call("snapshot", 200, f"{base}/snapshot")["clock"]["t"]
        advanced = p.call("test-advance", 200, f"/v1/test/playthroughs/{p.pid}/advance", {"minutes": 60})
        assert advanced["clock"]["t"] == t + 60
        assert p.expect("commit")["patch"]["clock"]["t"] == t + 60
        telemetry = json.loads((EXAMPLES / "telemetry" / "request" / "talk-turn.json").read_text(encoding="utf-8"))
        p.call("telemetry", 204, "/v1/telemetry", telemetry)
        p.call("playthrough-delete", 202, base, key=True)
        assert p.call("me", 200, "/v1/me")["activePlaythrough"] is None
        # 删除之后可以重新开局（F-0 的「新しく始める」）；这一局用结局剧本，取结局
        p.pid = p.call("playthroughs-create", 201, "/v1/playthroughs", create, key=True)["playthroughId"]
        assert p.http.post("/__mock/scenario", json={"name": "ending"}).status_code == 200
        p.last_seq = 0
        p.connect()
        p.expect("ending_ready")
        p.call("ending", 200, f"/v1/playthroughs/{p.pid}/ending")
        events = p.call("events", 200, f"/v1/playthroughs/{p.pid}/events?afterSeq=0&limit=50")
        commits = [c for c in p.log[p.log.index(p.find("welcome")[-1]) :] if c["type"] == "commit"]
        assert [e["eventId"] for e in events["events"]] == [e["eventId"] for c in commits for e in c["events"]]
        assert events["lastSeq"] == p.last_seq
        p.call("auth-logout", 204, "/v1/auth/logout")
        rest_ok("me", 401, p.http.get("/v1/me"))
        assert p.hit == set(BOOK.endpoints()), set(BOOK.endpoints()) - p.hit
    finally:
        p.close()


def test_deleted_playthrough_closes_with_4004(fast: Server) -> None:
    p = new_player(fast)
    try:
        p.start("small-talk")
        p.call("playthrough-delete", 202, f"/v1/playthroughs/{p.pid}", key=True)
        assert p.expect("#closed")["code"] == 4004
        ws = p.open()
        with pytest.raises(ConnectionClosed) as closed:
            ws.recv(timeout=10)
        assert closed.value.rcvd is not None and closed.value.rcvd.code == 4004
    finally:
        p.close()


def test_expire_session(fast: Server) -> None:
    p = new_player(fast)
    try:
        p.start("small-talk")
        assert p.http.post("/__mock/expire-session").json() == {"expired": True}
        assert p.expect("#closed")["code"] == 4001
        rest_ok("me", 401, p.http.get("/v1/me"))
        ws = p.open()
        with pytest.raises(ConnectionClosed) as closed:
            ws.recv(timeout=10)
        assert closed.value.rcvd is not None and closed.value.rcvd.code == 4001
    finally:
        p.close()


def test_drop_then_reconnect_replays_commits_once(timed: Server) -> None:
    p = new_player(timed, timed=True)
    try:
        p.start("ending")
        p.expect("commit")
        assert p.http.post("/__mock/drop").json() == {"dropped": 1}
        assert p.expect("#closed")["code"] == 1006  # 没有关闭帧：断网
        wait_finished(timed, p.pid)  # 断线期间剧本照样走完，commit 记下来
        p.connect()
        p.expect("commit")
        p.expect("commit")
        commits = p.find("commit")
        assert len(commits) == 3
        for before, after in zip(commits, commits[1:], strict=False):
            assert after["fromSeq"] == before["seq"] + 1
        events = p.call("events", 200, f"/v1/playthroughs/{p.pid}/events?afterSeq=0")
        assert [e["eventId"] for e in events["events"]] == [e["eventId"] for c in commits for e in c["events"]]
    finally:
        p.close()


def test_cross_site_requests_are_refused(fast: Server) -> None:
    p = new_player(fast)
    try:
        p.start("small-talk")
        body = {"bookId": "hashire-merosu", "roleId": "role.traveler"}
        evil = {"Origin": "https://evil.example", "Idempotency-Key": str(uuid.uuid4())}
        rest_ok("playthroughs-create", 403, p.http.post("/v1/playthroughs", json=body, headers=evil))
        plain = {"Content-Type": "text/plain", "Idempotency-Key": str(uuid.uuid4())}
        rest_ok("playthroughs-create", 403, p.http.post("/v1/playthroughs", content=json.dumps(body), headers=plain))
        cookie = p.http.cookies.get(COOKIE)
        ws = connect(
            f"ws://127.0.0.1:{fast.port}/v1/playthroughs/{p.pid}/live",
            origin=Origin("https://evil.example"),
            additional_headers={"Cookie": f"{COOKIE}={cookie}"},
            proxy=None,
            legacy=True,
        )
        with pytest.raises(ConnectionClosed) as closed:
            ws.recv(timeout=10)
        assert closed.value.rcvd is not None and closed.value.rcvd.code == 4003
    finally:
        p.close()


def test_idempotency_key(fast: Server) -> None:
    p = new_player(fast)
    try:
        key = {"Idempotency-Key": str(uuid.uuid4())}
        body = {"bookId": "hashire-merosu", "roleId": "role.traveler"}
        first = p.http.post("/v1/playthroughs", json=body, headers=key)
        again = p.http.post("/v1/playthroughs", json=body, headers=key)
        assert first.status_code == again.status_code == 201 and first.json() == again.json()
        other = p.http.post("/v1/playthroughs", json={**body, "roleId": "role.shepherd"}, headers=key)
        assert rest_ok("playthroughs-create", 422, other)["error"]["code"] == "idempotency_conflict"
        missing = p.http.post("/v1/playthroughs", json=body)
        assert rest_ok("playthroughs-create", 400, missing)["error"]["code"] == "invalid_request"
    finally:
        p.close()


# —— 剧本格式和自检 ——


def test_script_errors_are_caught_at_load(tmp_path: Path) -> None:
    (tmp_path / "typo.jsonl").write_text('{"sned": {"type": "pong"}}\n', encoding="utf-8")
    (tmp_path / "a.jsonl").write_text('{"include": "b"}\n', encoding="utf-8")
    (tmp_path / "b.jsonl").write_text('{"include": "a"}\n', encoding="utf-8")
    with pytest.raises(scripts.ScriptError, match="sned"):
        scripts.load(tmp_path, "typo")
    with pytest.raises(scripts.ScriptError, match="a → b → a"):
        scripts.load(tmp_path, "a")


def test_messages_that_fail_the_schema_are_not_sent() -> None:
    async def run(strict: bool) -> list[str]:
        m = Mock(Config(strict=strict, scenario="small-talk"))
        pt = m.create(m.new_session(), "role.traveler")
        live = m.live(pt)
        bad = {"type": "narration"}  # 少了 line
        if strict:
            with pytest.raises(SchemaError):
                await live.emit(bad)
        else:
            await live.emit(bad)
        await live.emit({"type": "narration", "line": "日が傾いてきた。"})
        return live.sent_types

    assert asyncio.run(run(strict=True)) == ["narration"]
    assert asyncio.run(run(strict=False)) == ["narration"]
