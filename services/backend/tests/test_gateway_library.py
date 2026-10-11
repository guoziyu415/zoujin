"""H-1 的书房数据：真实 PostgreSQL、原网关登录/删除链路、历史版本、完成与生成中、账号隔离。"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, insert, select, update
from zoujin_backend.config import REPO
from zoujin_backend.db.tables import endings, playthroughs, turns

from .conftest import BOOK, LIBRARY, SCHEMAS, Env
from .test_gateway import Player, Services, invite
from .test_gateway import services as services  # noqa: PLC0414
from .test_gateway_b9 import sliced as sliced  # noqa: PLC0414
from .test_gateway_b9 import to_act4

pytestmark = pytest.mark.db


def seed_history(env: Env, owner: str, status: str, *, ready: bool = False, older: bool = False) -> str:
    async def main() -> str:
        engine = env.engine()
        book = next(b for v, b in LIBRARY.by_version.items() if v != BOOK.version) if older else BOOK
        pid, eid = env.ids.new("pt"), env.ids.new("end")
        try:
            async with engine.begin() as c:
                await c.execute(
                    insert(playthroughs).values(
                        playthrough_id=pid,
                        user_ref=owner,
                        book_id=book.book_id,
                        world_model_version=book.version,
                        role_id="role.traveler",
                        status=status,
                        ended_at=datetime.now(UTC) - timedelta(days=1 if older else 0),
                    )
                )
                if ready:
                    body = json.loads(
                        (REPO / "packages/contracts/examples/valid/data/Ending/canon-reunion.json").read_text()
                    )
                    body.update(playthroughId=pid, endingId=eid, worldModelVersion=book.version)
                    body = SCHEMAS.ending(body)
                    await c.execute(insert(endings).values(ending_id=eid, playthrough_id=pid, body=body))
            return pid
        finally:
            await engine.dispose()

    return asyncio.run(main())


def test_library_is_owner_scoped_persisted_versioned_and_delete_removes_history(env: Env, services: Services) -> None:
    p, other = Player(services.base), Player(services.base)
    try:
        p.call("books", 401, "GET", "/v1/books")
        p.call("library", 401, "GET", "/v1/library")
        code = invite(env)
        owner = p.login(code)["user"]["userRef"]
        other_owner = other.login(invite(env))["user"]["userRef"]
        empty = p.call("library", 200, "GET", "/v1/library")
        assert empty == {"activePlaythrough": None, "endings": [], "pendingEndings": []}
        books = p.call("books", 200, "GET", "/v1/books")["books"]
        assert len(books) == 1 and books[0]["bookId"] == "hashire-merosu"
        assert books[0]["worldModelVersion"] == BOOK.version and books[0]["availability"] == "available"
        p.start()
        finished = seed_history(env, owner, "ended", ready=True)
        old = seed_history(env, owner, "ended", ready=True, older=True)
        pending = seed_history(env, owner, "ended")
        abandoned = seed_history(env, owner, "abandoned", ready=True)
        foreign = seed_history(env, other_owner, "ended", ready=True)
        lib = p.call("library", 200, "GET", "/v1/library")
        assert lib["activePlaythrough"]["playthroughId"] == p.pid
        assert lib["activePlaythrough"]["bookId"] == "hashire-merosu"
        assert [e["playthroughId"] for e in lib["endings"]] == [finished, old]
        assert lib["endings"][1]["worldModelVersion"] != BOOK.version
        old_version = lib["endings"][1]["worldModelVersion"]
        legacy_path = f"/v1/books/hashire-merosu/manifest?worldModelVersion={old_version}"
        legacy = p.call("manifest", 200, "GET", legacy_path)
        latest = p.call("manifest", 200, "GET", "/v1/books/hashire-merosu/manifest")
        assert legacy["manifestVersion"] != latest["manifestVersion"]
        other.call("manifest", 404, "GET", legacy_path)
        p.call("manifest", 404, "GET", "/v1/books/hashire-merosu/manifest?worldModelVersion=no-such-version")
        assert [e["playthroughId"] for e in lib["pendingEndings"]] == [pending]
        assert foreign not in json.dumps(lib) and abandoned not in json.dumps(lib)
        assert "finalVars" not in json.dumps(lib) and "epilogue" not in json.dumps(lib)
        assert [e["playthroughId"] for e in other.call("library", 200, "GET", "/v1/library")["endings"]] == [foreign]
        other.call("ending", 403, "GET", f"/v1/playthroughs/{finished}/ending")
        other.call("playthrough-delete", 403, "DELETE", f"/v1/playthroughs/{finished}", {}, key="not-mine")
        p.call("playthrough-delete", 202, "DELETE", f"/v1/playthroughs/{finished}", {}, key="delete-finished")
        assert finished not in json.dumps(p.call("library", 200, "GET", "/v1/library"))
        p.call("ending", 404, "GET", f"/v1/playthroughs/{finished}/ending")
        # 用同一邀请码新登录（模拟换设备）仍看到服务端保存的旧结局和当前进度。
        with PlayerContext(services.base) as again:
            again.login(code)
            result = again.call("library", 200, "GET", "/v1/library")
            assert result["activePlaythrough"]["playthroughId"] == p.pid
            assert result["endings"][0]["playthroughId"] == old
    finally:
        p.close()
        other.close()


class PlayerContext(Player):
    def __enter__(self) -> Player:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def test_reading_the_library_does_not_create_runs_or_endings(env: Env, services: Services) -> None:
    p = Player(services.base)
    try:
        p.login(invite(env))
        for _ in range(3):
            p.call("books", 200, "GET", "/v1/books")
            p.call("library", 200, "GET", "/v1/library")

        async def counts() -> None:
            engine = env.engine()
            try:
                async with engine.connect() as c:
                    assert not (await c.execute(select(playthroughs))).first()
                    assert not (await c.execute(select(endings))).first()
            finally:
                await engine.dispose()

        asyncio.run(counts())
    finally:
        p.close()


def test_explicit_second_book_uses_its_own_manifest_and_pins_create_version(env: Env, tmp_path: Path) -> None:
    # 只在测试临时目录制作另一书的夹具，不往产品目录加入未制作的书。
    world = json.loads(BOOK.path.read_text()) if BOOK.path is not None else {}
    world["book"].update(id="test-library-book", title="テストの本")
    world["worldModelVersion"] = "test-library-book@1.0.0-test"
    path = tmp_path / "world.json"
    path.write_text(json.dumps(world))
    s = Services(env.url, extra={"ZJ_WORLDS": json.dumps([str(path)])})
    p = Player(s.base)
    try:
        p.login(invite(env))
        catalog = p.call("books", 200, "GET", "/v1/books")["books"]
        assert [b["bookId"] for b in catalog] == ["hashire-merosu", "test-library-book"]
        manifest = p.call("manifest", 200, "GET", "/v1/books/test-library-book/manifest")
        assert manifest["book"]["id"] == "test-library-book"
        made = p.call(
            "playthroughs-create",
            201,
            "POST",
            "/v1/playthroughs",
            {"bookId": "test-library-book", "roleId": "role.traveler"},
            key="second-book",
        )
        active = p.call("library", 200, "GET", "/v1/library")["activePlaythrough"]
        assert active["playthroughId"] == made["playthroughId"]
        assert active["bookId"] == "test-library-book" and active["worldModelVersion"] == world["worldModelVersion"]
    finally:
        p.close()
        s.stop()


def test_pending_ending_can_recover_from_home_without_websocket(env: Env, sliced: Services) -> None:
    p = Player(sliced.base)
    p.login(invite(env))
    try:
        to_act4(env, sliced, p)
        for i in range(4):
            p.send({"type": "action", "clientMsgId": f"end-{i}", "kind": "wait"})
            p.expect("action_result", clientMsgId=f"end-{i}", timeout=30)
            if any(m["type"] == "ending_started" for m in p.log):
                break
        p.expect("ending_ready", timeout=30)
        assert p.ws is not None
        p.ws.close()
        p.ws = None

        async def interrupted() -> None:
            engine = env.engine()
            try:
                async with engine.begin() as c:
                    await c.execute(delete(endings).where(endings.c.playthrough_id == p.pid))
                    await c.execute(
                        update(turns)
                        .where(turns.c.playthrough_id == p.pid, turns.c.kind == "ending")
                        .values(status="pending", lease_until=None, attempts=0)
                    )
            finally:
                await engine.dispose()

        asyncio.run(interrupted())
        lib = p.call("library", 200, "GET", "/v1/library")
        assert lib["endings"] == [] and lib["pendingEndings"][0]["playthroughId"] == p.pid
        endpoint = f"/v1/playthroughs/{p.pid}/ending"
        p.call("ending", 202, "GET", endpoint)
        deadline = time.monotonic() + 15
        while True:
            result = p.http.get(endpoint)
            if result.status_code == 200:
                break
            assert result.status_code == 202 and time.monotonic() < deadline
            time.sleep(0.1)
        eid = result.json()["endingId"]
        assert p.call("ending", 200, "GET", endpoint)["endingId"] == eid
        lib = p.call("library", 200, "GET", "/v1/library")
        assert lib["pendingEndings"] == [] and lib["endings"][0]["endingId"] == eid
    finally:
        p.close()
