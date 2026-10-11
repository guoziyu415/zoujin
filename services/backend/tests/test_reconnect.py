"""重连时再推一次的幕切换（api-contract 第 4 节，v1.0.12）：网关的 `again()`，不要库。"""

from __future__ import annotations

from typing import Any

from zoujin_backend.gateway.ws import again

Json = Any

TALK: Json = {"push": [{"type": "turn_settled", "turnId": "turn_a"}], "seq": 4}
CHOSEN: Json = {
    "push": [
        {"type": "set_piece", "pieceId": "piece.x", "lines": []},
        {"type": "act_transition", "fromActId": "act.1", "toActId": "act.4"},
    ],
    "seq": 9,
}
PLANNED: Json = {
    "push": [
        {"type": "act_plan_result", "clientMsgId": "c1", "accepted": True},
        {"type": "act_transition", "fromActId": "act.1", "toActId": "act.4"},
    ],
    "seq": 9,
}


def test_only_the_last_commit_s_act_change_for_a_client_not_past_it() -> None:
    assert again([TALK, CHOSEN], 4, 9) == [CHOSEN["push"][1]]  # 固定演出不补（3.14），只推 act_transition
    assert again([TALK, CHOSEN], 9, 9) == [CHOSEN["push"][1]]  # 收到了提交，不一定收到了 act_transition
    assert again([TALK, PLANNED], 4, 9) == PLANNED["push"]  # 打算成行：连同 act_plan_result，顺序不变
    assert again([TALK, CHOSEN], 10, 10) == []  # 之后又有提交：已经落地了
    assert again([CHOSEN, {**TALK, "seq": 10}], 4, 10) == []
    assert again([TALK, None, {"seq": 5}], 0, 5) == []  # 没有幕切换；兜底的、没有 push 的轮次跳过
