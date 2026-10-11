"""网关和叙事者的配置，只从环境变量读（B-0、B-2）。

没有任何云凭证、项目 ID、Key 的配置项：`ZJ_MODEL=real` 时真客户端自己读 Mac 上显式设的项目和地区
（`models/vertex.py`）、Claude 的模型 ID 和 Key（`models/claude.py`），别的模式不读。每种提示走哪家、哪个模型（Claude
只写档名加版本）、思考多深、时限多长只写在这里（B-8）。本地开发用 `compose.yaml` 里的值。
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

# services/backend/src/zoujin_backend/config.py → 仓库根
REPO = Path(__file__).resolve().parents[4]

type ModelMode = Literal["fake", "replay", "real"]
MODEL_MODES: tuple[ModelMode, ...] = ("fake", "replay", "real")

type Provider = Literal["google", "claude"]


@dataclass(frozen=True)
class TextSpec:
    """一种提示怎么调（B-8 卡的清单）。fake、replay 只用 provider 和 model 算回放的键。"""

    provider: Provider
    # Google：模型 ID；Claude：档名加版本（`zoujin_llm.model_tag` 的写法）。回放的键、账本、`check.checker` 用它；
    # Claude 的模型 ID 只在 Mac 上用环境变量给（CLAUDE_TIERS），认出来的档名加版本要和这里一样才调
    model: str
    deadline: float  # 每次调用的时限（秒），超时取消、立刻重发一次（backend-design 2.4）〔暂定，S-5 定〕
    max_output: int  # 输出上限，含思考
    # Google：thinkingLevel（LOW、MEDIUM），None = 不设；
    # Claude：disabled（Haiku 能关）、between_tools（不先思考，Sonnet 最低就是它）、adaptive（自适应）
    thinking: str | None = None
    effort: str | None = None  # Claude：output_config.effort（low、medium…），None = 不传
    temperature: float | None = None  # 只有 Google 用：Claude 的 Messages API 没有这个参数（SDK 1.13 起）


# 提示类型 → 怎么调（B-8，D-028：能用 Claude 的全部用 Claude；`reply` 只在评测里替 Live 当人物，留在 Google，S-085 ①）。
# 提取和检查先用 Sonnet，S-2 和第一遍切片评测再量一遍 Haiku，按 S-085 ③ 定换不换
TEXT: dict[str, TextSpec] = {
    "triage": TextSpec("claude", "haiku-5.5", 5.0, 256, thinking="disabled"),
    "extract": TextSpec("claude", "sonnet-5.5", 15.0, 4096, thinking="between_tools", effort="low"),
    "check": TextSpec("claude", "sonnet-5.5", 15.0, 8192, thinking="adaptive", effort="medium"),
    "rewrite": TextSpec("claude", "sonnet-5.5", 15.0, 4096, thinking="between_tools", effort="low"),
    "reply": TextSpec("google", "gemini-3.8-flash", 15.0, 1024, thinking="LOW", temperature=0.8),
    "narrate": TextSpec("claude", "sonnet-5.5", 10.0, 1024, thinking="between_tools", effort="low"),
    "plan": TextSpec("claude", "sonnet-5.5", 15.0, 4096, thinking="adaptive", effort="low"),
    # B-12：安全筛查（S-072 的 3 秒时限，超时重发一次；B-8 的表定 Haiku、关思考）
    "safety": TextSpec("claude", "haiku-5.5", 3.0, 64, thinking="disabled"),
}
TEXT_MODELS: dict[str, str] = {k: v.model for k, v in TEXT.items()}
DEADLINES: dict[str, float] = {k: v.deadline for k, v in TEXT.items()}
# Claude 的档 → Mac 上给模型 ID 的环境变量（ID 不进仓库，和数据的评审员一样）
CLAUDE_TIERS: dict[str, str] = {"haiku": "ZJ_CLAUDE_HAIKU", "sonnet": "ZJ_CLAUDE_SONNET"}
# 临时换档（S-085 ③：S-2 和切片评测再用 Haiku 量一遍）：`ZJ_TEXT_MODELS=check=haiku-5.5,extract=haiku-5.5`。
# 只能换 Claude 那几种的档名加版本，思考和 effort 照旧；回放的键、账本、`check.checker` 跟着变
OVERRIDE_ENV = "ZJ_TEXT_MODELS"
_TAG = re.compile(r"(haiku|sonnet)-\d+\.\d+")


def text_spec(kind: str, env: Mapping[str, str] | None = None) -> TextSpec:
    """这种提示这次怎么调：`TEXT` 加上 `ZJ_TEXT_MODELS` 的换档。"""
    base = TEXT[kind]
    value = (os.environ if env is None else env).get(OVERRIDE_ENV, "")
    for part in (x.strip() for x in value.split(",")):
        name, _, tag = part.partition("=")
        if name.strip() != kind:
            continue
        tag = tag.strip()
        if base.provider != "claude" or not _TAG.fullmatch(tag):
            raise ConfigError(f"{OVERRIDE_ENV} 只能把 Claude 的提示换成 haiku-x.y 或 sonnet-x.y，得到 {part!r}")
        return replace(base, model=tag)
    return base


# Google 的单价：每 100 万 token 的美元（docs/data/cost/pricing-2026-10-06.md，global 端点）。Claude 的单价在共用包
# `zoujin_llm` 的 claude-prices.json，只有那一份。按账单上的标价记：3.8 Flash 到 2026 年底
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
    # real 时：账本（JSONL，两本账同一个文件，和 E-0 live、评审员同一个）、两家各自的总上限（跨所有跑次累计：D-027 的
    # Google 50 美元、D-029 的 Claude 100 美元）、记在哪一项下和这一项的上限、录回放的目录。上限由运行器从命令行参数
    # 设进环境（S-2 的 zoujin-s2、E-0 的 live），没有默认值
    ledger: Path | None = None
    max_google_usd: float | None = None
    max_claude_usd: float | None = None
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
            max_claude_usd=float(e["ZJ_MAX_CLAUDE_USD"]) if e.get("ZJ_MAX_CLAUDE_USD") else None,
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
