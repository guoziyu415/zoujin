"""B-13 在网关上（验收第 1、4〜8 组的 REST 和 WebSocket 部分）：commit 带记忆和约定、記憶帳的三个接口、
删除当场生效（重建会话、forget 的 commit）、删除整局（202、4004、之后 404）。

网关和叙事者都在测试进程里（`test_gateway_b4.InProc`），叙事者的提取换成立约定的假规则。
"""

from __future__ import annotations

from typing import Any

import pytest
from zoujin_backend.gateway import brief
from zoujin_backend.models.text import FakeText
from zoujin_worldsim import initial_state

from . import test_gateway_b4 as b4
from .conftest import BOOK, OLD, Env
from .test_b13 import EXTRACT, OFFER, REMEMBERED
from .test_gateway import Player, invite
from .test_gateway_b4 import InProc, Make, Play, settle

inproc = b4.inproc  # pytest 的 fixture 按名字找
play = b4.play

pytestmark = pytest.mark.db

Json = Any

SPEED = 0.05


def promising(s: InProc) -> FakeText:
    """叙事者这边：玩家说「送り」就立一个送老爺回家的约定（同 test_b13）。"""
    text = FakeText(s.settings.fake_text, rules=[EXTRACT])
    s.narrator.text = text
    s.narrator.pipeline.text = text
    s.narrator.memorizer.text = text
    return text


def promise_turn(s: InProc, play: Play) -> tuple[Player, Json, str]:
    promising(s)
    p = play(s)
    p.focus(OLD)
    t = p.text(OFFER)
    commit = p.expect("commit", turnId=t)
    p.expect("turn_settled", turnId=t)
    return p, commit, t


def keeps_calls(s: InProc) -> int:
    text = s.gw.screener.text
    assert isinstance(text, FakeText)
    return [k for k, _ in text.calls].count("keeps")


def test_the_commit_carries_the_new_memory_and_promise(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p, commit, _ = promise_turn(s, play)
    (m,) = commit["memories"]
    assert m["character"] == OLD and m["change"] == "added" and m["kind"] == "promise" and m["text"] == REMEMBERED
    (pr,) = commit["promises"]
    assert pr["character"] == OLD and pr["direction"] == "playerToCharacter" and pr["status"] == "open"


def test_memory_book_impact_and_delete(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p, commit, turn_id = promise_turn(s, play)
    memory_id = commit["memories"][0]["memoryId"]
    promise_id = commit["promises"][0]["promiseId"]
    base = f"/v1/playthroughs/{p.pid}/memories"

    book = p.call("memories", 200, "GET", base)
    (old,) = [c for c in book["characters"] if c["character"] == OLD]
    assert [x["memoryId"] for x in old["memories"]] == [memory_id]
    assert old["memories"][0]["via"] == "witnessed" and old["memories"][0]["promiseId"] == promise_id
    assert [x["promiseId"] for x in old["promises"]] == [promise_id] and old["didForYou"] == []

    # 后果一句：第一次调模型，之后读缓存（这条约定的事件没有可见的结果，假模型回 null）
    impact = p.call("memory-impact", 200, "GET", f"{base}/{memory_id}/impact")
    assert impact == {"keeps": None, "voidsPromise": True}
    assert p.call("memory-impact", 200, "GET", f"{base}/{memory_id}/impact") == impact
    assert keeps_calls(s) == 1

    # 别人的局 403
    other = play(s, connect=False)
    other.call("memories", 403, "GET", base)
    other.call("memory-delete", 403, "DELETE", f"{base}/{memory_id}", {}, key="del-1")

    opened = len(s.live.opened)
    gone = p.call("memory-delete", 200, "DELETE", f"{base}/{memory_id}", {}, key="del-1")
    assert gone == {
        "memoryId": memory_id,
        "deleted": True,
        "character": OLD,
        "relationLabel": "様子を見ている",
        "relationLevel": 3,
        "promiseVoided": promise_id,
        "sessionRebuilt": True,
    }
    p.expect("session_preparing", character=OLD, reason="rebuild")
    p.expect("session_ready", character=OLD)
    settle(p)
    (forget,) = [m for m in p.log if m["type"] == "commit" and m["fromSeq"] > commit["seq"]]
    (ev,) = forget["events"]
    assert ev["type"] == "forget" and ev["promise"] == {"promiseId": promise_id, "change": "voided"}
    assert forget["memories"] == [
        {
            "character": OLD,
            "change": "deleted",
            "memoryId": memory_id,
            "relationLabel": "様子を見ている",
            "relationLevel": 3,
        }
    ]
    assert forget["promises"][0]["status"] == "voided"
    # 新会话里没有删了的那一轮
    (new,) = s.live.opened[opened:]
    assert all(r.player != OFFER for r in new.recent) and REMEMBERED not in new.system
    assert "家まで送る" not in new.system and "なかったこと" not in new.system  # 约定和 forget 事件也不在（UX 评审）

    # 同一个键重放一样；之后查不到、后果 404、换个键再删 404
    assert p.call("memory-delete", 200, "DELETE", f"{base}/{memory_id}", {}, key="del-1") == gone
    book = p.call("memories", 200, "GET", base)
    (old,) = [c for c in book["characters"] if c["character"] == OLD]
    assert old["memories"] == [] and old["promises"][0]["status"] == "voided"
    p.call("memory-impact", 404, "GET", f"{base}/{memory_id}/impact")
    p.call("memory-delete", 404, "DELETE", f"{base}/{memory_id}", {}, key="del-2")
    p.call("memory-delete", 400, "DELETE", f"{base}/{memory_id}", {})  # 没带 Idempotency-Key
    settle(p)
    assert p.last_seq == forget["seq"]


def test_delete_without_an_open_session_does_not_rebuild(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p, commit, _ = promise_turn(s, play)
    p.ws.close()  # type: ignore[union-attr]
    p.ws = None
    memory_id = commit["memories"][0]["memoryId"]
    gone = p.call("memory-delete", 200, "DELETE", f"/v1/playthroughs/{p.pid}/memories/{memory_id}", {}, key="d")
    assert gone["sessionRebuilt"] is False and not s.gw.parked


def test_delete_playthrough(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p, _, _ = promise_turn(s, play)
    assert p.call("playthrough-delete", 202, "DELETE", f"/v1/playthroughs/{p.pid}", {}, key="end") is None
    p.expect("#closed", code=4004)
    p.call("snapshot", 404, "GET", f"/v1/playthroughs/{p.pid}/snapshot")
    p.call("memories", 404, "GET", f"/v1/playthroughs/{p.pid}/memories")
    assert p.call("playthrough-delete", 202, "DELETE", f"/v1/playthroughs/{p.pid}", {}, key="end") is None
    p.call("playthrough-delete", 404, "DELETE", f"/v1/playthroughs/{p.pid}", {}, key="again")
    fresh = Player(s.base)
    try:
        fresh.login(invite(env))
        fresh.call("playthrough-delete", 404, "DELETE", "/v1/playthroughs/pt_01M4NK0000000000000000000", {}, key="x")
    finally:
        fresh.close()


def test_memories_go_into_the_brief_after_the_situation() -> None:
    st = initial_state(BOOK.world, "role.traveler")
    out = brief.build(BOOK, st, OLD, memories=["家まで送ってくれた旅の人"]).system
    assert "# 覚えていること\n- 家まで送ってくれた旅の人" in out
    assert out.index("# いまの状況") < out.index("# 覚えていること") < out.index("# 話し相手")
    assert "# 覚えていること" not in brief.build(BOOK, st, OLD).system


def test_impact_is_null_and_not_cached_when_the_model_fails(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p, commit, _ = promise_turn(s, play)
    text = s.gw.screener.text
    assert isinstance(text, FakeText)
    text.rules.insert(0, text._rule({"kind": "keeps", "error": "unavailable", "times": 1}, "<test>"))
    path = f"/v1/playthroughs/{p.pid}/memories/{commit['memories'][0]['memoryId']}/impact"
    assert p.call("memory-impact", 200, "GET", path)["keeps"] is None
    assert p.call("memory-impact", 200, "GET", path)["keeps"] is None
    assert keeps_calls(s) == 2  # 出错的那次没缓存，第二次又算了
