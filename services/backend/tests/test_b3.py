"""B-3（动作和幕末）的验收，第 1〜7 组：快照、动作、固定演出、收幕和幕末、评测入口、不记原话、迁移。

走评测入口（和网关同一条路：写任务、叫叙事者），世界模型用切片版（`ZJ_WORLD`）；过场二选一用完整草稿的第三幕。
WebSocket 上的顺序和落地在 `test_gateway_b3.py`。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from alembic import command
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_backend import eval_api
from zoujin_backend.config import REPO, async_url
from zoujin_backend.db import store
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import events, playthrough_metrics, playthroughs, turns
from zoujin_backend.gateway.core import Gateway
from zoujin_backend.models.live import FakeLive
from zoujin_backend.models.text import FakeText
from zoujin_backend.narrator.actions import ACT_ENDED_LINE, CHECKER_MOVE
from zoujin_backend.narrator.core import Result
from zoujin_backend.narrator.plans import LABEL_FALLBACK, REFUSAL_FALLBACK
from zoujin_backend.projection import snapshot
from zoujin_backend.trace import Tracer
from zoujin_worldsim import settle

from .conftest import LIBRARY, OLD, SCHEMAS, Env, alembic_config, truncate

pytestmark = pytest.mark.db

Json = Any

SLICE = REPO / "worlds" / "hashire-merosu" / "1.0.0-slice" / "world.json"
DRAFT = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
WALKED = {
    "effects": [{"op": "set", "var": "var.player.walkedOldManHome", "value": True}],
    "note": "第一幕で老爺を家まで送った（aid.old-man.listen）",
}
GROUND = "place.execution-ground"
PROMISE = "fact.promise"
CITY, HOME = "exit.1.city", "exit.1.old-man"
ACCEPTED = "町の人たちに、メロスの約束のことを話して回ります。"  # fixtures/fake-text/b3-slice.json 认「約束」
REFUSED = "メロスを追いかけて、村まで一緒に行きます。"


class Game:
    """评测入口的一局，加上直接看库：局上记的、每一轮的 turns.result、快照、网关推的 commit。"""

    def __init__(self, s: eval_api.Session) -> None:
        self.s = s

    def _engine(self) -> AsyncEngine:
        return create_async_engine(self.s.settings.database_url, poolclass=NullPool)

    def row(self) -> Json:
        async def main() -> Json:
            engine = self._engine()
            try:
                async with engine.connect() as c:
                    return await store.playthrough(c, self.s.pid)
            finally:
                await engine.dispose()

        return eval_api._run(main())

    def turn(self, turn_id: str) -> Json:
        async def main() -> Json:
            engine = self._engine()
            try:
                async with engine.connect() as c:
                    r = (await c.execute(select(turns).where(turns.c.turn_id == turn_id))).mappings().one()
                    return dict(r)
            finally:
                await engine.dispose()

        return eval_api._run(main())

    def metrics(self) -> Json:
        async def main() -> Json:
            engine = self._engine()
            try:
                async with engine.connect() as c:
                    q = select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == self.s.pid)
                    return dict((await c.execute(q)).mappings().one())
            finally:
                await engine.dispose()

        return eval_api._run(main())

    def snap(self) -> Json:
        st = eval_api._run(self.s._state())
        return snapshot(self.s.book, self.s.pid, self.s.role, "active", st, st["seq"], Run.of(self.row()))

    def commits(self, after_seq: int) -> list[Json]:
        """网关会推的 commit（和 WebSocket 同一个函数）。"""

        async def main() -> list[Json]:
            engine = self._engine()
            gw = Gateway(
                settings=self.s.settings,
                engine=engine,
                library=LIBRARY,
                schemas=SCHEMAS,
                live=FakeLive(self.s.settings.fake_voice, speed=0),
                narrator=None,  # type: ignore[arg-type]
            )
            try:
                msgs, _ = await gw.commits(self.s.pid, after_seq)
                return msgs
            finally:
                await engine.dispose()

        return eval_api._run(main())

    def task(self, kind: str, request: Json, said: str | None = None) -> Result:
        r, _ = eval_api._run(self.s._task(kind, request, said))
        return r

    def push(self, step: Json) -> list[Json]:
        result = self.turn(step["traceId"])["result"]
        assert result is not None
        return list(result["push"])

    @property
    def seq(self) -> int:
        return int(self.row()["last_seq"])


@pytest.fixture
def game(env: Env, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Game]]:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.setenv("ZJ_WORLD", str(SLICE))
    monkeypatch.delenv("ZJ_MODEL", raising=False)

    def make(checkpoint: str, *, walked: bool = False, world: Any = SLICE, **setup: Any) -> Game:
        monkeypatch.setenv("ZJ_WORLD", str(world))
        doc = {"role": "role.traveler", "checkpoint": checkpoint, **setup}
        if walked:
            doc["events"] = [*doc.get("events", []), WALKED]
        return Game(eval_api.setup(doc, mode="text"))

    yield make


def by_id(xs: list[Json], key: str = "id") -> dict[str, Json]:
    return {x[key]: x for x in xs}


def types(push: list[Json]) -> list[str]:
    return [m["type"] for m in push]


def beat_t(g: Game, beat: str) -> int | None:
    """这个 beat 发生的时刻（世界状态里只有状态，时刻看事件）。"""
    ts = [
        e["t"]
        for e in g.s.events()
        if e["check"]["status"] == "passed" and {"op": "beat", "to": "happened", "beat": beat} in e["effects"]
    ]
    return ts[-1] if ts else None


# —— 第 1 组：快照 ——


def test_snapshot_actions_interactables_and_player_spot(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.02")
    snap = g.snap()
    (help_,) = snap["actions"]
    assert help_["actionId"] == "act_walk-old-man-home" and help_["kind"] == "help" and help_["target"] == OLD
    assert help_["estimatedMinutes"] == 30 and help_["enabled"] is True and help_["melos"] is None
    things = by_id(snap["interactables"])
    door = things["obj.workshop-door"]
    assert (door["kind"], door["spot"], door["estimatedMinutes"]) == ("examine", "workshop-door", 0)
    exits = [x for x in snap["interactables"] if x["kind"] == "go"]
    assert {x["id"] for x in exits} == {"way.castle", "way.road-to-city"} and all(x["enabled"] for x in exits)
    assert snap["player"]["spot"] == "plaza-southwest"  # 广场的起点

    step = g.s.act("help", OLD, {})
    assert (step["status"], step["clockMinutes"], step["aid"]) == ("done", 30, "aid.old-man.listen")
    (ev,) = [e for e in step["events"] if e["actor"] == "player"]
    assert (ev["type"], ev["origin"], ev["dt"], ev["check"]["status"]) == ("action", "action", 30, "passed")
    assert ev["beneficiary"] == OLD  # 为老爺做的（E6-011 的牧童给水同样）
    assert g.turn(step["traceId"])["result"]["playerSpot"] == "old-man-house-side"
    snap = g.snap()
    assert snap["actions"] == [] and snap["player"]["spot"] == "old-man-house-side"
    assert by_id(snap["characters"])[OLD]["spot"] == "old-man-house"
    # commit 在 action_result 之前（结果记在 turns.result 里，网关推完 commit 才照着推）；patch 只给 spot
    (commit,) = [m for m in g.commits(ev["seq"] - 1) if m["fromSeq"] == ev["seq"]]
    assert commit["patch"]["player"] == {"spot": "old-man-house-side"}
    assert types(g.push(step)) == ["action_result"]


def test_deadline_waits_for_the_gate_to_tell_the_promise(game: Callable[..., Game]) -> None:
    """S-077 ⑪⑫：beat.05 发生了、玩家不知道约定时不出期限；城门那一场让玩家知道。"""
    g = game("sc.canon@beat.05", place=GROUND)
    assert g.s.state()["beats"]["beat.05"] == "happened"
    snap = g.snap()
    assert snap["deadline"] == {"shown": False} and snap["forecast"] is None

    before = g.seq
    step = g.s.act("go", "place.castle", {})
    assert step["status"] == "refused" and step["setPiece"] == "piece.gate-promise" and "narration" not in step
    rejected, learned = step["events"]
    assert rejected["type"] == "move" and rejected["check"]["status"] == "rejected"
    assert "R7-capability" in rejected["check"]["failedRules"]
    assert learned["type"] == "learn" and learned["actor"] == "char.guards" and learned["origin"] == "action"
    assert learned["effects"] == [{"op": "learn", "character": "player", "fact": PROMISE}]
    assert (learned["dt"], learned["check"]["checker"]) == (0, "set-piece")
    assert types(g.push(step)) == ["action_result", "set_piece"]
    snap = g.snap()
    assert snap["deadline"]["shown"] is True and snap["forecast"] is not None
    (commit,) = g.commits(before)
    assert commit["patch"]["deadline"]["shown"] is True and commit["patch"]["forecast"] == snap["forecast"]

    again = g.s.act("go", "place.castle", {})
    assert again["setPiece"] == "piece.gate-again"
    third = g.s.act("go", "place.castle", {})  # once 的都演过了：叙事者说一行
    assert third["pieces"] == [] and third["narration"]


# —— 第 2 组：动作 ——


def test_move_writes_one_event_and_the_patch_has_no_spot(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.03")
    before = g.seq
    step = g.s.act("move", GROUND, {})
    assert (step["status"], step["clockMinutes"]) == ("done", 0)
    (ev,) = step["events"]
    assert (ev["type"], ev["actor"], ev["dt"]) == ("move", "player", 0)
    assert ev["check"] == {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_MOVE}
    (commit,) = g.commits(before)
    assert commit["patch"]["player"] == {"place": GROUND}  # 不带 spot：前端不把人挪到起点
    assert g.snap()["player"] == {"roleId": "role.traveler", "place": GROUND, "spot": "stake-front"}

    seq = g.seq
    refused = g.s.act("move", "place.castle", {})  # 旅人进不去王城
    assert (refused["status"], refused["events"], refused["clockMinutes"]) == ("refused", [], 0)
    assert g.seq == seq and g.commits(seq) == []
    shut = g.s.act("move", "place.stonemason-workshop", {})  # beat.06 之前：门关着的固定演出
    assert shut["setPiece"] == "piece.workshop-door-closed"


def test_affordance_whose_condition_fails_is_refused_with_a_rejected_event(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.02", walked=True)
    assert g.snap()["actions"] == []
    request = {"clientMsgId": "c1", "kind": "help", "target": OLD, "actionId": "act_walk-old-man-home"}
    r = g.task("action", request)
    assert r.info["status"] == "refused" and r.minutes == 0
    (ev,) = r.events
    assert ev["check"]["status"] == "rejected" and ev["effects"] == []


def test_go_to_the_castle_is_refused_and_block_goes_through_extract(game: Callable[..., Game]) -> None:
    """E4-107：旅人进不了王城（R7），没被抓、还在刑场；没有对应情境动作的 block 走提取（不分流）。"""
    g = game("sc.canon@beat.04", place=GROUND)
    step = g.s.act("go", "place.castle", {})
    (ev,) = step["events"]
    assert step["status"] == "refused" and ev["check"]["status"] == "rejected"
    assert "R7-capability" in ev["check"]["failedRules"]
    st = g.s.state()
    assert st["vars"]["var.player.location"] == GROUND and st["vars"]["var.player.custody"] == "free"

    assert isinstance(g.s.text, FakeText)
    g.s.text.calls.clear()
    step = g.s.act("block", "char.guards", {})
    kinds = [k for k, _ in g.s.text.calls]
    assert kinds[0] == "extract" and "triage" not in kinds
    assert g.s.text.calls[0][1]["action"] == {"kind": "block", "target": "char.guards", "item": None}
    assert step["status"] == "refused" and step["events"] == []  # 假模型的提取没有候选


def test_examine_the_workshop_door(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.03", place="place.stonemason-workshop")
    first = g.s.act("examine", "obj.workshop-door", {})
    assert (first["setPiece"], first["events"], first["clockMinutes"]) == ("piece.workshop-knock", [], 0)
    second = g.s.act("examine", "obj.workshop-door", {})
    assert second["pieces"] == [] and second["narration"]
    dark = game("sc.canon@beat.06", place="place.stonemason-workshop").s.act("examine", "obj.workshop-door", {})
    assert dark["setPiece"] == "piece.workshop-knock-dark"


# —— 第 3 组：节拍时机的固定演出 ——


def test_beat_set_piece_only_when_the_player_is_there(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.03", place=GROUND)
    g.s.advance(20)
    step = g.s.say(OLD, "……")  # 这一轮的 10 分钟里 beat.04 到点
    assert types(g.push(step)) == ["set_piece", "turn_settled"]
    assert g.push(step)[0]["pieceId"] == "piece.gate-taken"
    assert g.row()["played_pieces"] == ["piece.gate-taken"]

    away = game("sc.canon@beat.03")  # 玩家在广场
    step = away.s.advance(60)
    assert away.turn(step["traceId"])["result"]["pieces"] == []


def test_gate_taken_again_after_being_turned_away(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.03", place=GROUND)
    turned = g.s.act("go", "place.castle", {})
    assert turned["setPiece"] == "piece.gate-turned-away"
    step = g.s.advance(60)
    assert g.turn(step["traceId"])["result"]["pieces"] == ["piece.gate-taken-again"]


# —— 第 4 组：收幕和幕末 ——


def test_act_ends_after_beat_07_and_queued_turns_get_no_world(game: Callable[..., Game], env: Env) -> None:
    g = game("sc.canon@beat.06", walked=True)
    assert g.row()["act_end"] is None
    advance = {"minutes": 600}

    async def queue() -> list[str]:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                a = await store.enqueue(c, g.s.ids, g.s.pid, kind="advance", minutes=advance["minutes"])
                t = await store.enqueue(c, g.s.ids, g.s.pid, kind="talk", input_mode="text", character=OLD)
                await store.add_utterance(c, g.s.ids, g.s.pid, t, speaker="player", text="……", t=0)
                await store.add_utterance(c, g.s.ids, g.s.pid, t, speaker=OLD, text="……", t=0, source="live")
                x = await store.enqueue(
                    c,
                    g.s.ids,
                    g.s.pid,
                    kind="action",
                    client_msg_id="c9",
                    request={"clientMsgId": "c9", "kind": "wait"},
                )
            await g.s._narrator(engine).run(g.s.pid)
            return [a, t, x]
        finally:
            await engine.dispose()

    a, t, x = eval_api._run(queue())
    st = g.s.state()
    assert st["beats"]["beat.07"] == "happened" and st["t"] == beat_t(g, "beat.07")
    push = g.turn(a)["result"]["push"]
    assert types(push)[-1] == "act_ended"
    ended = push[-1]
    assert ended == {"type": "act_ended", **g.row()["act_end"]}
    options = by_id(ended["options"], "optionId")
    assert list(options) == [CITY, HOME]
    assert {o["where"] for o in options.values()} == {"刑場・三日目の夕方"}
    assert (options[CITY]["sub"], options[HOME]["sub"]) == ("西の門が見える所で", "老爺があなたを覚えている")
    assert (options[CITY]["with"], options[HOME]["with"]) == ([], [OLD])
    assert ended["freeform"] == {"allowed": True, "triesLeft": 2} and ended["recapLines"] == []
    talk = g.turn(t)
    assert talk["outcome"] == "no_response" and talk["result"]["push"] == [
        {"type": "turn_settled", "turnId": t, "outcome": "no_response", "eventIds": [], "minutes": 0}
    ]
    action = g.turn(x)["result"]
    assert action["reason"] == "act-ended" and action["push"] == [
        {
            "type": "action_result",
            "clientMsgId": "c9",
            "status": "refused",
            "eventIds": [],
            "minutes": 0,
            "narration": ACT_ENDED_LINE,
        }
    ]
    m = g.metrics()
    assert (m["actions"], m["actions_act_ended"]) == (0, 1)
    assert len(game("sc.canon@beat.07").row()["act_end"]["options"]) == 1  # 没送过老爺：一个去处


def test_choose_the_given_exits(game: Callable[..., Game]) -> None:
    """E4-102、E4-104、E4-103：事件按契约 2.8.1，第四幕 t = 5370；玩家和老爺各站各的点；beat.s1 还没到。"""
    for exit_id, me, old, opener in (
        (HOME, "stake-front", "stake-front-side", OLD),
        (CITY, "ground-west", "stake-front", None),
    ):
        g = game("sc.canon@beat.07", walked=True)
        step = g.s.choose(exit_id)
        evs = step["events"]
        first, last = evs[0], evs[-1]
        assert (first["actor"], first["type"], first["origin"], first["exitId"]) == (
            "player",
            "act-transition",
            "act",
            exit_id,
        )
        assert first["check"]["checker"] == "world-exit" and first["check"]["status"] == "passed"
        assert (last["actor"], last["type"], last["t"]) == ("system", "act-transition", 5370)
        assert last["effects"] == [
            {"op": "set", "var": "var.act.current", "value": "act.4"},
            {"op": "set", "var": "var.player.location", "value": GROUND},
        ]
        assert all(e["type"] == "beat" for e in evs[1:-1]) and step["toAct"] == "act.4"
        st = g.s.state()
        assert st["vars"]["var.act.current"] == "act.4" and st["t"] == 5370
        assert st["beats"]["beat.s1"] == "pending"
        row = g.row()
        assert (row["player_spot"], row["act_end"], row["plan_tries"]) == (me, None, 0)
        assert (row["arrival"] or {}).get("opener") == opener
        (transition,) = g.push(step)
        assert transition["type"] == "act_transition" and (transition["fromActId"], transition["toActId"]) == (
            "act.1",
            "act.4",
        )
        assert transition["snapshot"] == g.snap() and transition["snapshot"]["player"]["spot"] == me
        assert by_id(transition["snapshot"]["characters"])[OLD]["spot"] == old
        assert transition["arrival"].get("opener") == opener and transition["arrival"]["line"]
        assert transition["snapshot"]["deadline"]["shown"] is True  # 去处的效果让玩家知道了约定（S-077 ⑫）

    g = game("sc.canon@beat.07")  # 没送过老爺
    seq = g.seq
    step = g.s.choose(HOME)
    assert (step["error"], step["events"]) == ("invalid_choice", []) and g.seq == seq
    assert types(g.push(step)) == ["error"] and g.push(step)[0]["error"]["code"] == "invalid_choice"


def test_city_then_sunset_follows_the_original(game: Callable[..., Game]) -> None:
    """E5-101：选 city，再等 120 分：beat.s1 在 5400、beat.24 在 5460。"""
    g = game("sc.canon@beat.07")
    g.s.choose(CITY)
    g.s.advance(120)
    assert (beat_t(g, "beat.s1"), beat_t(g, "beat.24")) == (5400, 5460)


def test_a_plan_that_goes(game: Callable[..., Game]) -> None:
    """E4-105、E5-102：成行的打算写玩家的 act-transition（带 plan、不带 exitId），落点照 Act.plan；群众知道了约定，
    beat.24 时演 crowd-makes-way，beat.24 的时刻不变。"""
    g = game("sc.canon@beat.07")
    step = g.s.propose(ACCEPTED)
    assert step["accepted"] is True and step["plan"] == {
        "label": "メロスの約束を、町の人々に知らせて回る",
        "toAct": "act.4",
        "place": GROUND,
        "t": 5370,
    }
    (move,) = [e for e in step["events"] if e["actor"] == "player"]
    assert move["type"] == "act-transition" and "exitId" not in move
    assert {"op": "learn", "character": "char.crowd", "fact": PROMISE} in move["effects"]
    assert {"op": "learn", "character": "player", "fact": PROMISE} in move["effects"]
    assert g.row()["player_spot"] == "stake-front"
    result, transition = g.push(step)
    assert result["type"] == "act_plan_result" and result["clientMsgId"] == f"eval-{g.s.steps}"
    assert result["narration"] == ["あなたは、メロスの約束を、町の人々に知らせて回ることにした。"]
    assert transition["type"] == "act_transition" and "arrival" in transition
    assert g.metrics()["plans_accepted"] == 1
    later = g.s.advance(120)
    assert "piece.crowd-makes-way" in g.turn(later["traceId"])["result"]["pieces"]
    assert beat_t(g, "beat.24") == 5460

    plain = game("sc.canon@beat.07")
    plain.s.choose(CITY)
    later = plain.s.advance(120)
    assert "piece.crowd-makes-way" not in plain.turn(later["traceId"])["result"]["pieces"]


def test_a_plan_that_does_not_go(game: Callable[..., Game]) -> None:
    """E4-012、E4-106：不成行没有事件，试次减一，带替代去处；第三次回 invalid_request；选替代去处按成行处理。"""
    g = game("sc.canon@beat.07")
    seq = g.seq
    one = g.s.propose(REFUSED)
    assert (one["accepted"], one["events"], one["triesLeft"]) == (False, [], 1) and g.seq == seq
    assert one["alternative"]["optionId"] == CITY and one["alternatives"] == [one["alternative"]]
    assert g.row()["act_end"]["freeform"] == {"allowed": True, "triesLeft": 1}
    two = g.s.propose(REFUSED)
    assert two["triesLeft"] == 0 and g.row()["act_end"]["freeform"] == {"allowed": False, "triesLeft": 0}
    three = g.s.propose(REFUSED)
    assert three["error"] == "invalid_request" and three["events"] == []
    assert g.metrics()["plans_refused"] == 2
    step = g.s.choose(one["alternative"]["optionId"])
    assert step["toAct"] == "act.4" and g.row()["plan_alternative"] is None


def test_choosing_another_plan_as_the_alternative(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.07")
    g.s.text = FakeText(
        rules=[
            {
                "kind": "plan",
                "output": {
                    "accepted": False,
                    "label": None,
                    "with": [],
                    "effects": [],
                    "narration": ["いまからでは、村までは追いつけない。"],
                    "alternative": {"label": "刑場のそばで、夕方を待つ"},
                },
            }
        ]
    )
    step = g.s.propose(REFUSED)
    alt = step["alternative"]
    assert alt["optionId"].startswith("plan_") and alt["label"] == "刑場のそばで、夕方を待つ"
    chosen = g.s.choose(alt["optionId"])
    (move,) = [e for e in chosen["events"] if e["actor"] == "player"]
    assert move["plan"]["label"] == "刑場のそばで、夕方を待つ" and "exitId" not in move
    assert g.row()["player_spot"] == "stake-front"


def test_en_route_choice_moves_the_target_time(game: Callable[..., Game]) -> None:
    """完整草稿第三幕的 exit.3.road：过场二选一。选「急かす」先写 action 事件，alignTo 让目标时刻提前 40 分；
    没带 enRouteChoice 等于选最后一个，不写事件。"""
    setup = {
        "events": [
            {
                "effects": [
                    {"op": "set", "var": "var.act.current", "value": "act.3"},
                    {"op": "set", "var": "var.player.location", "value": "place.village"},
                ],
                "note": "第三幕、村にいる",
            }
        ]
    }
    g = game("sc.canon@beat.14", world=DRAFT, **setup)
    (road,) = g.row()["act_end"]["options"]
    assert road["optionId"] == "exit.3.road" and [c["melosMinutes"] for c in road["enRoute"]["choices"]] == [-40, None]
    step = g.s.choose("exit.3.road", 0)
    first = step["events"][0]
    assert (first["type"], first["origin"], first["exitId"]) == ("action", "act", "exit.3.road")
    assert {"op": "beat", "beat": "beat.16", "to": "prevented"} in first["effects"]
    assert step["events"][-1]["t"] == 4960

    plain = game("sc.canon@beat.14", world=DRAFT, **setup)
    step = plain.s.choose("exit.3.road")
    assert step["events"][0]["type"] == "act-transition" and step["events"][-1]["t"] == 5000


def test_the_promise_not_made_keeps_the_deadline_hidden(game: Callable[..., Game]) -> None:
    """S-077 ⑫：约定没成立的局，去处的 learn 照写，期限一行仍不出。按 atLatest 收幕，结算到 atLatest。"""
    g = game("sc.canon@beat.04", events=[{"effects": [{"op": "beat", "beat": "beat.05", "to": "prevented"}]}])
    step = g.s.advance(600)
    assert g.s.state()["t"] == 1560 and step["clockMinutes"] == 360 and g.row()["act_end"] is not None
    step = g.s.choose(CITY)
    assert {"op": "learn", "character": "player", "fact": PROMISE} in step["events"][0]["effects"]
    assert g.snap()["deadline"] == {"shown": False} and g.snap()["forecast"] is None


def test_skipped_beats_where_the_player_was_teach_nothing(game: Callable[..., Game]) -> None:
    """幕切换第 3 步玩家一律算不在场：节拍落在玩家原来的地点，也不 learn 它的 public 事实、不演固定演出。"""
    g = game("sc.canon@beat.07", place="place.melos-home")
    st = eval_api._run(g.s._state())
    drafts, _ = settle(g.s.book.world, st, 5370, player_present=True)
    taught = [e for d in drafts for e in d["event"]["effects"] if e["op"] == "learn" and e["character"] == "player"]
    assert taught  # 在场的话会知道婚礼的事
    step = g.s.choose(CITY)
    learns = [
        e for ev in step["events"][1:] for e in ev["effects"] if e["op"] == "learn" and e["character"] == "player"
    ]
    assert learns == [] and step["pieces"] == []


# —— 第 6 组：不记原话 ——


def test_plan_words_stay_out_of_logs_and_bad_labels_are_replaced(
    game: Callable[..., Game], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    g = game("sc.canon@beat.07")
    g.s.tracer = Tracer()
    marker = "合言葉はミズイロノカサ"
    label = "連絡は090-1234-5678まで"
    g.s.text = FakeText(
        rules=[
            {
                "kind": "plan",
                "output": {
                    "accepted": True,
                    "label": label,
                    "with": [],
                    "effects": [],
                    "narration": [],
                    "alternative": None,
                },
            }
        ]
    )
    step = g.s.propose(f"{marker}。町の人に話して回ります。")
    assert step["accepted"] is True and step["plan"]["label"] == LABEL_FALLBACK
    assert g.push(step)[0]["narration"] == [f"あなたは、{LABEL_FALLBACK}ことにした。"]
    spans = json.dumps([s.attrs for s in g.s.tracer.spans], ensure_ascii=False)
    assert any(s.name == "narrator.plan" for s in g.s.tracer.spans)
    for word in (marker, label, LABEL_FALLBACK):
        assert word not in caplog.text and word not in spans

    # 照抄玩家原话 8 字以上的理由：换成固定的说法
    h = game("sc.canon@beat.07")
    said = "王城の地下牢から友を連れ出す"
    h.s.text = FakeText(
        rules=[
            {
                "kind": "plan",
                "output": {
                    "accepted": False,
                    "label": None,
                    "with": [],
                    "effects": [],
                    "narration": [f"{said}のは無理だ"],
                    "alternative": None,
                },
            }
        ]
    )
    refused = h.s.propose(f"今夜、{said}つもりです。")
    assert refused["narration"] == [REFUSAL_FALLBACK]


def test_clearing_plan_texts_keeps_the_events(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.07")
    one = g.s.propose(REFUSED)
    two = g.s.propose(ACCEPTED)
    before = g.s.events()

    async def clear(turn_ids: list[str] | None) -> int:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                return await store.clear_plan_texts(c, g.s.pid, turn_ids)
        finally:
            await engine.dispose()

    assert eval_api._run(clear([one["traceId"]])) == 1
    cleared = g.turn(one["traceId"])["result"]
    assert cleared["cleared"] is True and "narration" not in cleared["push"][0]
    assert "label" not in cleared["push"][0]["alternative"]
    assert "narration" in g.turn(two["traceId"])["result"]["push"][0]
    assert eval_api._run(clear(None)) == 1  # 第一轮清过了，只清第二轮
    assert "narration" not in g.turn(two["traceId"])["result"]["push"][0]
    assert g.s.events() == before


# —— 第 7 组：迁移 ——


def test_migration_0003_goes_down_and_up(migrated: str) -> None:
    truncate(migrated)
    cfg = alembic_config(migrated)
    engine = create_async_engine(async_url(migrated), poolclass=NullPool)

    async def columns(table: str) -> set[str]:
        async with engine.connect() as c:
            return set(await c.run_sync(lambda sc: {x["name"] for x in inspect(sc).get_columns(table)}))

    try:
        command.downgrade(cfg, "0002")
        assert "act_end" not in eval_api._run(columns("playthroughs"))
        assert "result" not in eval_api._run(columns("turns"))
        command.upgrade(cfg, "head")
        assert {
            "player_spot",
            "played_pieces",
            "act_end",
            "plan_tries",
            "plan_alternative",
            "arrival",
        } <= eval_api._run(columns("playthroughs"))
        assert {"cost_narrate_usd", "cost_plan_usd", "actions", "actions_act_ended"} <= eval_api._run(
            columns("playthrough_metrics")
        )
    finally:
        command.upgrade(cfg, "head")
        eval_api._run(engine.dispose())


def test_deleting_a_playthrough_takes_its_run_and_results(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.07")
    g.s.propose(REFUSED)

    async def main() -> tuple[int, int]:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                await c.execute(delete(playthroughs).where(playthroughs.c.playthrough_id == g.s.pid))
            async with engine.connect() as c:
                n_turns = await c.scalar(
                    select(func.count()).select_from(turns).where(turns.c.playthrough_id == g.s.pid)
                )
                n_events = await c.scalar(
                    select(func.count()).select_from(events).where(events.c.playthrough_id == g.s.pid)
                )
            return int(n_turns or 0), int(n_events or 0)
        finally:
            await engine.dispose()

    assert eval_api._run(main()) == (0, 0)
