"""B-19 在 WebSocket 上：开局时先开口的人走落地那一套（api-contract 3.11）。切片只有旅人，先开口的是老爺。"""

from __future__ import annotations

import pytest

from . import test_gateway_b3 as b3
from . import test_gateway_b4 as b4
from .conftest import OLD
from .test_gateway_b4 import Make, Play

inproc, play = b4.inproc, b4.play
sliced, player = b3.sliced, b3.player

pytestmark = pytest.mark.db


def test_the_opener_speaks_first_after_the_first_landing(inproc: Make, play: Play) -> None:
    s = inproc(0.2)
    p = play(s)
    welcome = p.log[0] if p.log and p.log[0]["type"] == "welcome" else p.find("welcome")
    arrival = welcome["pending"]["arrival"]
    assert arrival["opener"] == OLD and arrival["line"]
    p.send({"type": "act_landed", "actId": "act.1"})
    started = p.expect("turn_started", reason="arrival")
    assert started["speaker"] == OLD
    p.expect("transcript", turnId=started["turnId"], speaker=OLD, final=True)
    p.connect(last_seq=p.last_seq)
    assert "arrival" not in p.expect("welcome")["pending"]  # 落地过了，重连不再先开口
