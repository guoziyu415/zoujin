"""B-19：2 つの新しい役柄（石屋の弟子、村の牧童）の始まり：最初に話しかける人物、呼び方、開始時の助け合いを
状況説明に入れる。

完全版の世界モデル（`1.0.0-draft`）を読むだけで、データベースにはつながない。着地して先に話しかける WebSocket 上の
確認は `test_gateway_b19.py` にある。
"""

from __future__ import annotations

import pytest
from zoujin_backend.config import REPO
from zoujin_backend.gateway import brief
from zoujin_backend.narrator import roles
from zoujin_backend.world import Library
from zoujin_worldsim import initial_state

DRAFT = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
LIB = Library(REPO / "worlds", REPO / "assets" / "scenes", DRAFT)
_book = LIB.book("hashire-merosu")
assert _book is not None
BOOK = _book


@pytest.mark.parametrize(
    ("role", "who", "act"),
    [
        ("role.traveler", "char.old-man", "act.1"),
        ("role.apprentice", "char.selinuntius", "act.1"),
        ("role.shepherd-boy", "char.melos", "act.3"),
    ],
)
def test_each_role_has_an_opener_at_its_start(role: str, who: str, act: str) -> None:
    got = roles.start_arrival(BOOK, role)
    assert got == {"actId": act, "line": BOOK.roles[role]["summary"], "opener": who}


def test_a_role_without_an_opening_aid_has_no_opener() -> None:
    assert roles.start_arrival(BOOK, "role.guard") is None  # 第 2 版の役柄で、世界モデルにはまだ開始時の助け合いがない
    assert roles.start_arrival(BOOK, "role.nobody") is None


def test_the_apprentice_brief_names_the_address_and_the_opening_aid() -> None:
    state = initial_state(BOOK.world, "role.apprentice")
    text = brief.build(BOOK, state, "char.selinuntius").system
    assert "石屋の弟子（顔見知り）" in text
    assert "呼び方：おまえ／弟子よ" in text
    assert "相手があなたにしてくれそうなこと：親方の留守、工房を守ると約束する" in text
    assert "託す" not in text  # 「相手があなたに」の項目はあとのこと：登場人物に渡さない（ネタバレ）


def test_the_shepherd_boy_brief_for_melos() -> None:
    state = initial_state(BOOK.world, "role.shepherd-boy")
    state["t"] = BOOK.roles["role.shepherd-boy"]["startT"]
    text = brief.build(BOOK, state, "char.melos").system
    assert "村の牧童（顔見知り）" in text and "呼び方：坊主" in text
    assert "相手があなたにしてくれそうなこと：よろめいて村に戻ったメロスに水を一杯差し出す" in text
    assert "三日のうちに戻るという約束" not in text


def test_the_opening_aid_leaves_the_brief_after_the_start_act() -> None:
    state = initial_state(BOOK.world, "role.apprentice")
    state["t"] = 1440  # 第二幕
    text = brief.build(BOOK, state, "char.selinuntius").system
    assert "呼び方：おまえ／弟子よ" in text
    assert "相手があなたにしてくれそうなこと" not in text


def test_other_characters_get_only_the_address() -> None:
    state = initial_state(BOOK.world, "role.apprentice")
    assert roles.brief_lines(BOOK, state, "char.king") == ["呼び方：おまえ／弟子よ"]


def test_a_done_aid_leaves_the_brief() -> None:
    state = initial_state(BOOK.world, "role.traveler")
    assert any("家まで送る" in x for x in roles.brief_lines(BOOK, state, "char.old-man"))
    state["vars"]["var.player.walkedOldManHome"] = True
    assert roles.brief_lines(BOOK, state, "char.old-man") == ["呼び方：旅の方"]
