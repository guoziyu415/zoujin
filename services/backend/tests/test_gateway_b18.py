"""B-18：其余 5 个可对话人物（王、セリヌンティウス、妹、花婿、フィロストラトス）接进叙事者和 Live。

完整世界模型（1.0.0-draft）里七个人物都 `talkable`。假 Live 每人一串台词（`fixtures/fake-voice/lines.json`），
叙事者用假文本模型；不花钱。
"""

from __future__ import annotations

from typing import Any

import pytest
from zoujin_backend import eval_api
from zoujin_backend.config import DEFAULT_WORLD, Settings
from zoujin_backend.gateway import brief
from zoujin_backend.world import Library
from zoujin_worldsim import initial_state

from . import test_gateway_b4 as b4
from .conftest import Env
from .test_gateway import Player, invite
from .test_gateway_b4 import Make

inproc = b4.inproc  # pytest 的 fixture 按名字找

pytestmark = pytest.mark.db

SPEED = 0.05
NEW = ("char.king", "char.selinuntius", "char.sister", "char.groom", "char.philostratus")
# 人物 → 他所在的地点、能到那里的身份（eval 的 setup 直接放到那里）
WHERE = {
    "char.king": ("role.castle-maid", "place.castle"),
    "char.selinuntius": ("role.apprentice", "place.stonemason-workshop"),
    "char.philostratus": ("role.apprentice", "place.stonemason-workshop"),
    "char.sister": ("role.shepherd-boy", "place.melos-home"),
    "char.groom": ("role.shepherd-boy", "place.groom-house"),
}
Json = Any


def draft_book() -> Any:
    st = Settings(database_url="unused")
    return Library(st.worlds, st.scenes, DEFAULT_WORLD).current


def test_all_seven_are_talkable_with_a_voice() -> None:
    from zoujin_backend.gateway.app import voices_of

    book = draft_book()
    voices = voices_of()
    for who in NEW:
        assert book.characters[who]["talkable"] and voices.get(who), who


def test_brief_for_each_new_character() -> None:
    book = draft_book()
    for who in NEW:
        role, _ = WHERE[who]
        b = brief.build(book, initial_state(book.world, role), who)
        assert f"名前：{book.characters[who]['name']}" in b.system
        assert "口調：" in b.system and "# いまの状況" in b.system


@pytest.mark.parametrize("who", NEW)
def test_narrator_answers_each_new_character_where_he_is(env: Env, monkeypatch: pytest.MonkeyPatch, who: str) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    monkeypatch.delenv("ZJ_WORLD", raising=False)
    role, place = WHERE[who]
    s = eval_api.setup({"role": role, "checkpoint": "sc.canon@t=1080", "place": place}, mode="text")
    step = s.say(who, "こんにちは。少しお話ししてもいいですか。")
    assert step["reply"] and not step["characterTextMissing"]


def test_live_talks_with_each_new_character(env: Env, inproc: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(b4, "SLICE", DEFAULT_WORLD)
    s = inproc(SPEED)
    s.gw.manifest = None  # 王座之间、村子还没有场景包；这里只测对话的链路
    p = Player(s.base)
    try:
        p.login(invite(env))
        body = {"bookId": "hashire-merosu", "roleId": "role.apprentice"}
        made = p.call("playthroughs-create", 201, "POST", "/v1/playthroughs", body, key="b18")
        p.pid, p.last_seq = made["playthroughId"], made["snapshot"]["lastSeq"]
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        for who in NEW:
            p.focus(who)
            t = p.text(s.live.lines[who][0].player)
            final = p.expect("transcript", turnId=t, speaker=who, final=True)
            assert final["text"] == s.live.lines[who][0].reply
            p.expect("turn_settled", turnId=t)
            opened = [o for o in s.live.opened if o.character == who][-1]
            assert "# あなた" in opened.system
    finally:
        p.close()
