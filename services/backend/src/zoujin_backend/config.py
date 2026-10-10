"""网关和叙事者的配置，只从环境变量读（B-0、B-2）。

没有任何云凭证、项目 ID 的配置项：`ZJ_MODEL=real` 时真客户端自己读 Mac 上显式设的项目和地区（`models/vertex.py`），
别的模式不读。模型 ID、思考档、时限和价目只写在这里。本地开发用 `compose.yaml` 里的值。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# services/backend/src/zoujin_backend/config.py → 仓库根
REPO = Path(__file__).resolve().parents[4]

type ModelMode = Literal["fake", "replay", "real"]
MODEL_MODES: tuple[ModelMode, ...] = ("fake", "replay", "real")

# 提示类型 → 文本模型和思考档（backend-design 2.4、第 7 节）。fake、replay 只用它们算回放的键
TEXT_MODELS: dict[str, str] = {
    "triage": "gemini-3.5-flash-lite",
    "extract": "gemini-3.8-flash",
    "check": "gemini-3.8-flash",
    "rewrite": "gemini-3.8-flash",
    "reply": "gemini-3.8-flash",
    "narrate": "gemini-3.8-flash",
    "plan": "gemini-3.8-flash",
}
THINKING: dict[str, str | None] = {
    "triage": None,
    "extract": "LOW",
    "check": "MEDIUM",
    "rewrite": "LOW",
    "reply": "LOW",
    "narrate": "LOW",
    "plan": "LOW",
}
# 每次调用的时限（秒），超时取消、立刻重发一次（backend-design 2.4）。〔暂定，S-5 定〕
DEADLINES: dict[str, float] = {
    "triage": 5.0,
    "extract": 15.0,
    "check": 15.0,
    "rewrite": 15.0,
    "reply": 15.0,
    "narrate": 10.0,
    "plan": 15.0,
}
# 每 100 万 token 的美元（docs/data/cost/pricing-2026-10-06.md，global 端点）。按账单上的标价记：3.8 Flash 到 2026 年底
# 的五折是事后返还，账本不扣，到上限停得比实花早，不会晚。地区端点（非 global）贵 10%
PRICES: dict[str, dict[str, float]] = {
    "gemini-3.8-flash": {"input": 1.50, "cachedInput": 0.15, "output": 7.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "cachedInput": 0.03, "output": 2.50},
}
REGIONAL_MARKUP = 1.10

# 开新局用的世界模型。`ZJ_WORLD`（world.json 的绝对路径，E-0 的运行器这样设，`--slice` 时是切片版）换掉它；
# 不按目录名排序挑最新的：切片（1.0.0-slice）排在 1.0.0-draft 后面，排序会让新局悄悄落到切片上
DEFAULT_WORLD = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"

REPLAYS = REPO / "fixtures" / "model-replays"

COOKIE = "zj_session"
SESSION_DAYS = 30  # 会话 Cookie 30 天，每次使用滑动续期（backend-design 5.2）


class ConfigError(ValueError):
    pass


def model_mode(env: Mapping[str, str] | None = None) -> ModelMode:
    """`ZJ_MODEL`：fake（默认）、replay、real（只在 zg 的 Mac 上，G-7）。"""
    value = (os.environ if env is None else env).get("ZJ_MODEL", "fake")
    for m in MODEL_MODES:
        if value == m:
            return m
    raise ConfigError(f"ZJ_MODEL 只能是 {' / '.join(MODEL_MODES)}，得到 {value!r}")


def world_path(env: Mapping[str, str] | None = None) -> Path:
    """`ZJ_WORLD`：world.json 的绝对路径；没设就是 `DEFAULT_WORLD`。"""
    value = (os.environ if env is None else env).get("ZJ_WORLD", "")
    if not value:
        return DEFAULT_WORLD
    path = Path(value)
    if not path.is_absolute():
        raise ConfigError(f"ZJ_WORLD 要写 world.json 的绝对路径，得到 {value!r}")
    if not path.is_file():
        raise ConfigError(f"ZJ_WORLD 指的文件不存在：{value}")
    return path


def async_url(url: str) -> str:
    """postgresql://… → SQLAlchemy 的 psycopg 3 驱动写法。"""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str  # postgresql+psycopg://…
    model: ModelMode = "fake"
    # 开发开关：会话 Cookie 不带 Secure（本地 http）、narrator 不查调用方的 OIDC 令牌
    dev: bool = False
    allow_origins: tuple[str, ...] = ()  # 同源以外还放行的 Origin（前端开发服务器）
    narrator_url: str = "http://127.0.0.1:8002"
    repo: Path = REPO
    speed: float = 1.0  # 假 Live 的间隔乘这个数：0 = 不等（测试）
    fake_voice: Path = field(default=REPO / "fixtures" / "fake-voice")
    fake_text: Path = field(default=REPO / "fixtures" / "fake-text")
    replays: Path = REPLAYS  # ZJ_REPLAYS 换成别的目录（例：留出集的回放，不进仓库）
    world: Path = DEFAULT_WORLD  # 开新局用的世界模型；已有的局按自己锁定的版本
    deadlines: Mapping[str, float] = field(default_factory=lambda: dict(DEADLINES))
    # real 时：账本（JSONL，和 E-0 live 的 Google 账本同一个文件）、Google 那本账的总上限、记在哪一项下和这一项的上限、
    # 录回放的目录。上限由运行器从命令行参数设进环境（S-2 的 zoujin-s2、E-0 的 live），没有默认值
    ledger: Path | None = None
    max_google_usd: float | None = None
    ledger_item: str | None = None
    max_item_usd: float | None = None
    record_replays: Path | None = None

    @property
    def schemas(self) -> Path:
        return self.repo / "packages" / "contracts" / "schemas"

    @property
    def worlds(self) -> Path:
        return self.repo / "worlds"

    @property
    def scenes(self) -> Path:
        return self.repo / "assets" / "scenes"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        url = e.get("DATABASE_URL")
        if not url:
            raise ConfigError("没有 DATABASE_URL（本地：docker compose up db，见 services/backend/README.md）")
        origins = tuple(o.strip() for o in e.get("ZJ_ALLOW_ORIGINS", "").split(",") if o.strip())
        return cls(
            database_url=async_url(url),
            model=model_mode(e),
            dev=e.get("ZJ_DEV", "") == "1",
            allow_origins=origins,
            narrator_url=e.get("ZJ_NARRATOR_URL", cls.narrator_url),
            speed=float(e.get("ZJ_SPEED", "1")),
            world=world_path(e),
            ledger=_path(e, "ZJ_LEDGER"),
            max_google_usd=float(e["ZJ_MAX_GOOGLE_USD"]) if e.get("ZJ_MAX_GOOGLE_USD") else None,
            ledger_item=e.get("ZJ_LEDGER_ITEM") or None,
            max_item_usd=float(e["ZJ_MAX_ITEM_USD"]) if e.get("ZJ_MAX_ITEM_USD") else None,
            record_replays=_path(e, "ZJ_RECORD_REPLAYS"),
            replays=_path(e, "ZJ_REPLAYS") or REPLAYS,
        )


def _path(env: Mapping[str, str], name: str) -> Path | None:
    value = env.get(name, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        raise ConfigError(f"{name} 要写绝对路径，得到 {value!r}")
    return path
