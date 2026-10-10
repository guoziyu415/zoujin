"""mock 的总状态和配置；REST（rest.py）和 WebSocket（ws.py）都从这里拿。"""

from __future__ import annotations

import copy
import json
import logging
import secrets
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from zoujin_backend.clock import Labels
from zoujin_backend.ids import IdGen
from zoujin_backend.mock import scripts
from zoujin_backend.mock.live import Live
from zoujin_backend.mock.state import Playthrough, Session
from zoujin_backend.mock.templates import MISSING, render
from zoujin_backend.schemas import SchemaBook

log = logging.getLogger("zoujin.mock")

Json = Any

# services/backend/src/zoujin_backend/mock/core.py → 仓库根
REPO = Path(__file__).resolve().parents[5]
INVITE_CODE = "mock"  # 只认这一个码（B-1）
COOKIE = "zj_session"
DEFAULT_SCENARIO = "tour"


@dataclass(frozen=True)
class Config:
    repo: Path = REPO
    speed: float = 1.0
    scenario: str = DEFAULT_SCENARIO
    strict: bool = False  # 测试用：剧本或自检出错时抛出，不只是在终端报错
    allow_origins: tuple[str, ...] = ()
    seed: int | None = None

    @property
    def fixtures(self) -> Path:
        return self.repo / "fixtures"

    @property
    def sessions_dir(self) -> Path:
        return self.fixtures / "sessions"

    @property
    def rest_dir(self) -> Path:
        return self.fixtures / "mock" / "rest"

    @property
    def schemas(self) -> Path:
        return self.repo / "packages" / "contracts" / "schemas"

    @property
    def world(self) -> Path:
        return self.repo / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"


@cache
def _read(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Mock:
    config: Config
    book: SchemaBook = field(init=False)
    labels: Labels = field(init=False)
    ids: IdGen = field(init=False)
    scenario: str = field(init=False)
    sessions: dict[str, Session] = field(default_factory=dict)
    playthroughs: dict[str, Playthrough] = field(default_factory=dict)
    lives: dict[str, Live] = field(default_factory=dict)
    idempotency: dict[tuple[str, str], tuple[str, int, bytes]] = field(default_factory=dict)
    login_failures: int = 0

    def __post_init__(self) -> None:
        self.book = SchemaBook(self.config.schemas)
        self.labels = Labels(self.config.world)
        self.ids = IdGen(self.config.seed)
        self.scenario = self.config.scenario
        scripts.load(self.config.sessions_dir, self.scenario)  # 启动时就发现剧本写错

    def reset(self) -> None:
        for live in self.lives.values():
            live.stop()
        self.sessions.clear()
        self.playthroughs.clear()
        self.lives.clear()
        self.idempotency.clear()
        self.login_failures = 0
        self.scenario = self.config.scenario

    # —— 固定数据 ——

    def fixture(self, rel: str) -> Json:
        return copy.deepcopy(_read(self.config.rest_dir / rel))

    def rendered(self, rel: str, pt: Playthrough | None = None, **extra: Any) -> Json:
        def lookup(name: str) -> Any:
            if name in extra:
                return extra[name]
            if pt is not None:
                if name == "playthroughId":
                    return pt.pid
                if name.startswith("id:"):
                    _, prefix, key = name.split(":", 2)
                    return pt.named_id(prefix, key)
            return MISSING

        return render(self.fixture(rel), lookup)

    def manifest(self, book_id: str) -> Json | None:
        path = self.config.rest_dir / "manifest" / f"{book_id}.json"
        return self.fixture(f"manifest/{book_id}.json") if path.is_file() else None

    # —— 会话和局 ——

    def new_session(self) -> Session:
        s = Session(sid=secrets.token_urlsafe(24), user_ref=self.ids.new("u"))
        self.sessions[s.sid] = s
        return s

    def session(self, sid: str | None) -> Session | None:
        s = self.sessions.get(sid or "")
        return s if s is not None and not s.expired else None

    def active(self, s: Session) -> Playthrough | None:
        for pt in self.playthroughs.values():
            if pt.owner == s.sid and pt.status == "active":
                return pt
        return None

    def active_ref(self, pt: Playthrough) -> Json:
        roles = {r["roleId"]: r["name"] for r in (self.manifest("hashire-merosu") or {"roles": []})["roles"]}
        return {
            "playthroughId": pt.pid,
            "roleId": pt.role_id,
            "roleName": roles.get(pt.role_id, pt.role_id),
            "actId": pt.snapshot["actId"],
            "tLabel": pt.snapshot["clock"]["tLabel"],
            "updatedAt": pt.updated_at,
        }

    def create(self, s: Session, role_id: str) -> Playthrough:
        pt = Playthrough(pid=self.ids.new("pt"), owner=s.sid, role_id=role_id, snapshot={}, ids=self.ids)
        snap = self.rendered("snapshot.json", pt)
        snap["player"]["roleId"] = role_id
        pt.snapshot = snap
        self.playthroughs[pt.pid] = pt
        return pt

    def live(self, pt: Playthrough) -> Live:
        if pt.pid not in self.lives:
            self.lives[pt.pid] = Live(pt, self.book, self.labels, speed=self.config.speed, strict=self.config.strict)
        return self.lives[pt.pid]

    def start_script(self, pt: Playthrough) -> None:
        self.live(pt).start(scripts.load(self.config.sessions_dir, self.scenario))

    def set_scenario(self, name: str) -> None:
        """换剧本：之后的局用它；正在跑的局从头跑新剧本（发过的 commit 留着，序号接着走）。"""
        scripts.load(self.config.sessions_dir, name)
        self.scenario = name
        for pid, live in self.lives.items():
            pt = self.playthroughs[pid]
            if live.task is not None and pt.status == "active":
                pt.names.clear()  # 重跑的剧本发新的事件 ID，不和已发的撞
                self.start_script(pt)

    def advance(self, pt: Playthrough, minutes: int) -> Json:
        """快进（非生产，第 7 节）：只改时钟，推一条只带 patch.clock 的 commit，序号接得上。"""
        t = pt.snapshot["clock"]["t"] + minutes
        commit: Json = {
            "type": "commit",
            "events": [],
            "patch": {"clock": {"t": t, "tLabel": self.labels.label(t)}},
            "memories": [],
            "promises": [],
            "narration": [],
            "cue": None,
            "reveal": None,
        }
        return commit
