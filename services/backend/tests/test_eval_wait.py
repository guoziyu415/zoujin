"""Found in a real simulation: when leaving the execution ground in the final act, waiting must not be refused
forever and stop the clock.

本物のシミュレーションで見つかった問題：最後の幕で刑場を離れるとき、
待機がずっと refused になって時計が止まってはならない。
"""

import pytest
from zoujin_backend import eval_api
from zoujin_backend.config import DEFAULT_WORLD
from zoujin_backend.narrator.actions import wait_limit

from .conftest import Env

pytestmark = pytest.mark.db


@pytest.mark.parametrize("place", ["place.syracuse-square", "place.stonemason-workshop"])
def test_final_act_wait_reaches_authoritative_ending_without_local_beat(
    env: Env, monkeypatch: pytest.MonkeyPatch, place: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.setenv("ZJ_WORLD", str(DEFAULT_WORLD))
    monkeypatch.setenv("ZJ_MODEL", "fake")
    session = eval_api.setup(
        {
            "role": "role.traveler",
            "checkpoint": "sc.canon@t=4605",
            "place": place,
            "events": [{"effects": [{"op": "set", "var": "var.act.current", "value": "act.4"}]}],
        }
    )
    try:
        before = session._run(session._state())
        assert before["vars"]["var.act.current"] == "act.4"
        assert wait_limit(session.book, before) == session.book.world["clock"]["deadline"]["t"]
        result = session.act("wait", None, {})
        assert result["status"] == "done" and result["clockMinutes"] > 0
        view = session.view()["snapshot"]
        assert view["status"] == "ended"
        assert session.ending() is not None
        after = session._run(session._state())
        assert after["t"] <= session.book.acts["act.4"]["end"]["atLatest"]
        assert session.act("wait", None, {})["status"] == "refused"
        assert session._run(session._state())["t"] == after["t"]
    finally:
        session.close()
