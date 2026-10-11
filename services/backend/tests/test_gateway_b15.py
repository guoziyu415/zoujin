"""B-15 在 WebSocket 上：第一遍 signal 的复核带上下文、复核期间人物停住、复核说是故事就降成小提示，
第二次 ambiguous 复核说是故事就不暂停。用 B-4 的 `InProc`；复核的假规则插在 fixture 的规则前面。
"""

from __future__ import annotations

import time
from typing import Any, cast

import pytest
from zoujin_backend.models.text import FakeText

from . import test_gateway_b3 as b3
from . import test_gateway_b4 as b4
from .conftest import OLD, Env
from .test_gateway_b4 import InProc, Make, Play, metrics

inproc, play = b4.inproc, b4.play
sliced, player = b3.sliced, b3.player

pytestmark = pytest.mark.db

Json = Any

LINE = "城の上で叫んでやる。"  # 假分类器判 signal，护栏词不命中
AMBIGUOUS = "ここで終わりにしたい。"


def rules(s: InProc, *rs: Json) -> FakeText:
    text = cast(FakeText, s.gw.screener.text)
    for r in reversed(rs):
        text.rules.insert(0, text._rule(r, "<test>"))
    return text


def signal(contains: str) -> Json:
    out = {"selfHarm": "signal", "injection": False}
    return {"kind": "safety", "when": {"playerContains": contains}, "output": out}


def review(contains: str, story: bool, ms: int = 0) -> Json:
    out = {"story": story}
    return {"kind": "safety_review", "when": {"playerContains": contains}, "output": out, "latencyMs": ms}


def test_a_story_line_is_held_then_released_with_the_hint(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.2)
    text = rules(s, signal("城の上で"), review("城の上で", True, ms=800))
    p = play(s)
    p.focus(OLD)
    t0 = time.monotonic()
    turn = p.text(LINE)
    p.expect("transcript", turnId=turn, speaker=OLD)
    assert time.monotonic() - t0 >= 0.7  # 复核期间人物没开口
    assert p.expect("turn_settled", turnId=turn)["outcome"] != "paused"
    assert p.find("safety_hint")
    assert p.find("transcript", turnId=turn, speaker=OLD, final=True)["text"]
    asked = [req for kind, req in text.calls if kind == "safety_review"]
    assert len(asked) == 1 and asked[0]["context"]["character"]
    m = metrics(env, p.pid)
    assert (m["safety_reviews"], m["safety_downgrades"], m["safety_pauses"], m["safety_hints"]) == (1, 1, 0, 1)


def test_review_saying_real_pauses_and_drops_the_held_reply(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.2)
    rules(s, signal("城の上で"), review("城の上で", False, ms=300))
    p = play(s)
    p.focus(OLD)
    turn = p.text(LINE)
    p.expect("safety_pause")
    assert p.find("turn_settled", turnId=turn)["outcome"] == "paused"
    time.sleep(0.5)
    assert not [m for m in p.log if m.get("turnId") == turn and m.get("speaker") == OLD]
    m = metrics(env, p.pid)
    assert (m["safety_reviews"], m["safety_downgrades"], m["safety_pauses"]) == (1, 0, 1)


def test_second_ambiguous_told_story_does_not_pause(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.2)
    rules(s, review("終わり", True))
    p = play(s)
    p.focus(OLD)
    first = p.text(AMBIGUOUS)
    p.expect("safety_hint")
    p.expect("turn_settled", turnId=first)
    second = p.text(AMBIGUOUS)
    assert p.expect("turn_settled", turnId=second)["outcome"] != "paused"
    assert not [m for m in p.log if m["type"] == "safety_pause"]
    m = metrics(env, p.pid)
    assert (m["safety_ambiguous"], m["safety_pauses"], m["safety_reviews"], m["safety_downgrades"]) == (2, 0, 1, 1)
