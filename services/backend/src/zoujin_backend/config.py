"""网关和叙事者的配置，只从环境变量读（B-0）。

没有任何云凭证、项目 ID 的配置项；模型 ID 只写在这里（`TEXT_MODELS`）。本地开发用 `compose.yaml` 里的值。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# services/backend/src/zoujin_backend/config.py → 仓库根
REPO = Path(__file__).resolve().parents[4]

type ModelMode = Literal["fake", "replay"]
MODEL_MODES: tuple[ModelMode, ...] = ("fake", "replay")

# 提示类型 → 正式环境用的文本模型（backend-design 第 7 节）。B-0 只用来算回放的键，不调用
TEXT_MODELS: dict[str, str] = {
    "extract": "gemini-3.8-flash",
    "reply": "gemini-3.8-flash",
}

# 开新局用的世界模型。`ZJ_WORLD`（world.json 的绝对路径，E-0 的运行器这样设，`--slice` 时是切片版）换掉它；
# 不按目录名排序挑最新的：切片（1.0.0-slice）排在 1.0.0-draft 后面，排序会让新局悄悄落到切片上
DEFAULT_WORLD = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"

COOKIE = "zj_session"
SESSION_DAYS = 30  # 会话 Cookie 30 天，每次使用滑动续期（backend-design 5.2）


class ConfigError(ValueError):
    pass


def model_mode(env: Mapping[str, str] | None = None) -> ModelMode:
    """`ZJ_MODEL` 只认 fake（默认）和 replay；B-0 没有真模型的实现。"""
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
    replays: Path = field(default=REPO / "fixtures" / "model-replays")
    world: Path = DEFAULT_WORLD  # 开新局用的世界模型；已有的局按自己锁定的版本

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
        )
