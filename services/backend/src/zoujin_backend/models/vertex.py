"""真文本模型：Vertex AI 上的 Gemini（`ZJ_MODEL=real`，只在 zg 的 Mac 上跑，G-7）。项目里的线程和 CI 从不调用。
B-8 以后只剩 `config.TEXT` 里 provider 是 google 的提示（评测里替 Live 当人物的 `reply`），其余走 `models/claude.py`。

- 认证用 Mac 上 gcloud 登录的应用默认凭证（ADC，`google-auth`，可选依赖组 `real`），没有 API Key。
- **项目 ID 和地区只从显式设的环境变量读**（`ZJ_VERTEX_PROJECT`、`ZJ_VERTEX_LOCATION`），只在 real 时读；没设就退出，
  不发请求。不用 ADC 或 gcloud 推断出来的默认项目（Mac 上 gcloud 的默认配置不是这个项目的）。项目 ID 不进日志、
  Trace、回放、账本和异常消息：传输层的错误换成不带原消息的 `ModelCallFailed`。
- 走 REST（`generateContent`，httpx），传输层可以换成假的（测试用 `httpx.MockTransport`，不联网）。
- 每次调用：渲染提示（世界模型前缀放最前）→ 账本判上限（`BudgetStop`）→ 调用（429 → `RateLimited`，第一个就停）→
  记账 → 输出过 Schema（不过 → `BadOutput`，由流水线按时限的规则重发）。设了 `ZJ_RECORD_REPLAYS` 时由
  `models.text.Recording` 录一行回放。
- 被时限取消的调用按预计花费记账（可能已经计费了，宁多记）。每行带耗时和状态（B-5：`ok`、`timeout`、`bad-output`；
  没有回应的记 `error`、花费 0）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import jsonschema

from zoujin_backend.config import ConfigError, ModelMode, Settings
from zoujin_backend.models.ledger import Ledger, cost_usd
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.render import render, render_turn, world_prefix
from zoujin_backend.models.text import BadOutput, ModelCallFailed, RateLimited, TextResult, model_and_version, spec
from zoujin_backend.world import Library

__all__ = ["RealText", "body", "estimate_usd", "real_text", "render", "render_turn", "world_prefix"]

Json = Any

PROJECT_ENV = "ZJ_VERTEX_PROJECT"
LOCATION_ENV = "ZJ_VERTEX_LOCATION"
SCOPE = "https://www.googleapis.com/auth/cloud-platform"


@dataclass(frozen=True)
class Generated:
    text: str
    usage: dict[str, int]


class Auth(Protocol):
    def token(self) -> str: ...


class AdcAuth:
    """ADC 的访问令牌，快过期了再刷新。只取凭证，不用 google.auth.default() 返回的项目。"""

    def __init__(self) -> None:
        try:
            import google.auth
            import google.auth.transport.requests
        except ImportError as e:  # pragma: no cover - 只在 Mac 上
            raise ConfigError("ZJ_MODEL=real 要可选依赖组 real：uv sync --extra real") from e
        self._creds, _ = google.auth.default(scopes=[SCOPE])  # 第二个返回值是推断的项目：不用
        self._request = google.auth.transport.requests.Request()
        self._at = 0.0

    def token(self) -> str:  # pragma: no cover - 只在 Mac 上
        if not self._creds.valid or time.monotonic() - self._at > 45 * 60:
            self._creds.refresh(self._request)  # type: ignore[no-untyped-call]  # google-auth 这个方法没标类型
            self._at = time.monotonic()
        return str(self._creds.token)


class Transport(Protocol):
    async def generate(self, model: str, body: Json) -> Generated: ...


class RestTransport:
    """Vertex AI 的 `generateContent`（REST）。global 端点和地区端点的地址不同。"""

    def __init__(self, project: str, location: str, auth: Auth, client: httpx.AsyncClient | None = None) -> None:
        for name in ("httpx", "httpcore"):  # httpx 的 INFO 日志带完整的 URL（里面有项目 ID）
            logging.getLogger(name).setLevel(logging.WARNING)
        self._project = project
        self._location = location
        self._auth = auth
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    def url(self, model: str) -> str:
        host = (
            "aiplatform.googleapis.com" if self._location == "global" else f"{self._location}-aiplatform.googleapis.com"
        )
        path = f"projects/{self._project}/locations/{self._location}/publishers/google/models/{model}:generateContent"
        return f"https://{host}/v1/{path}"

    async def generate(self, model: str, body: Json) -> Generated:
        headers = {"Authorization": f"Bearer {self._auth.token()}", "Content-Type": "application/json"}
        try:
            resp = await self._client.post(self.url(model), json=body, headers=headers)
        except httpx.HTTPError:
            raise ModelCallFailed("网络错误（消息不记）") from None
        if resp.status_code == 429:
            raise RateLimited("模型回 429（配额或限流），停下")
        if resp.status_code >= 400:
            raise ModelCallFailed(f"HTTP {resp.status_code}（消息不记）")
        data = resp.json()
        parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        u = data.get("usageMetadata") or {}
        usage = {
            "inputTokens": int(u.get("promptTokenCount", 0)),
            "cachedTokens": int(u.get("cachedContentTokenCount", 0)),
            "outputTokens": int(u.get("candidatesTokenCount", 0)),
            "thoughtTokens": int(u.get("thoughtsTokenCount", 0)),
        }
        return Generated(text, usage)


def body(kind: str, user: str) -> Json:
    prompt, sp = PROMPTS[kind], spec(kind)
    config: Json = {
        "responseMimeType": "application/json",
        "responseJsonSchema": prompt.schema,
        "maxOutputTokens": sp.max_output,
    }
    if sp.temperature is not None:
        config["temperature"] = sp.temperature
    if sp.thinking:
        config["thinkingConfig"] = {"thinkingLevel": sp.thinking}
    return {
        "systemInstruction": {"parts": [{"text": prompt.text}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": config,
    }


def estimate_usd(model: str, kind: str, chars: int, *, regional: bool) -> float:
    """调用前的预计花费，偏高：输入按一字一个 token，输出按上限。"""
    usage = {"inputTokens": chars, "outputTokens": spec(kind).max_output}
    return cost_usd(model, usage, regional=regional)


# —— 客户端 ——


@dataclass
class RealText:
    transport: Transport
    ledger: Ledger
    worlds: Callable[[str], Json]  # worldModelVersion → 世界模型
    regional: bool
    mode: ModelMode = "real"
    _prefix: dict[str, str] = field(default_factory=dict)

    def prefix(self, version: str | None) -> str:
        if version is None:
            return ""
        if version not in self._prefix:
            self._prefix[version] = world_prefix(self.worlds(version))
        return self._prefix[version]

    def _user(self, kind: str, request: Json) -> str:
        return render(kind, request, self.prefix(request.get("worldModelVersion")))

    def _guess(self, kind: str, user: str) -> float:
        model, _ = model_and_version(kind)
        return estimate_usd(model, kind, len(user) + len(PROMPTS[kind].text), regional=self.regional)

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return self._guess(kind, self._user(kind, request))

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = model_and_version(kind)
        user = self._user(kind, request)
        req = body(kind, user)
        guess = self._guess(kind, user)
        self.ledger.before(guess)
        start = time.perf_counter()
        try:
            got = await self.transport.generate(model, req)
        except asyncio.CancelledError:  # 时限到了被取消：可能已经计费，按预计记
            self.ledger.record(kind=kind, model=model, usage={}, cost=guess, ms=_ms(start), status="timeout")
            raise
        except Exception:  # 没有回应（连不上、5xx、429）：记一行，花费 0
            self.ledger.record(kind=kind, model=model, usage={}, cost=0.0, ms=_ms(start), status="error")
            raise
        ms = _ms(start)
        cost = cost_usd(model, got.usage, regional=self.regional)
        try:
            output = json.loads(got.text)
            jsonschema.validate(output, PROMPTS[kind].schema)
        except (ValueError, jsonschema.ValidationError):
            self.ledger.record(kind=kind, model=model, usage=got.usage, cost=cost, ms=ms, status="bad-output")
            raise BadOutput(f"{kind} 的输出不是合 Schema 的 JSON", cost) from None
        self.ledger.record(kind=kind, model=model, usage=got.usage, cost=cost, ms=ms, status="ok")
        return TextResult(output, kind, model, version, dict(got.usage), cost)


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def vertex_env(env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """real 时才调：项目和地区只从这两个环境变量读，没设就退出（不发请求，不推断默认项目）。"""
    e = os.environ if env is None else env
    project, location = e.get(PROJECT_ENV, ""), e.get(LOCATION_ENV, "")
    if not project or not location:
        raise ConfigError(f"ZJ_MODEL=real 要显式设 {PROJECT_ENV} 和 {LOCATION_ENV}（只在 Mac 上），没设，不调用")
    return project, location


def real_text(
    settings: Settings,
    *,
    ledger: Ledger | None = None,
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
) -> RealText:
    """按 Settings 建真客户端。账本和总上限必须给（ZJ_LEDGER、ZJ_MAX_GOOGLE_USD，或 S-2 运行器传进来的 ledger）。"""
    project, location = vertex_env(env)
    if ledger is None:
        if settings.ledger is None or settings.max_google_usd is None:
            raise ConfigError("ZJ_MODEL=real 要账本和 Google 的总上限：ZJ_LEDGER、ZJ_MAX_GOOGLE_USD，没有默认值")
        ledger = Ledger(settings.ledger, settings.max_google_usd, settings.max_item_usd, settings.ledger_item)
    library = Library(settings.worlds, settings.scenes, settings.world)
    return RealText(
        transport=transport or RestTransport(project, location, AdcAuth()),
        ledger=ledger,
        worlds=lambda v: library.version(v).world,
        regional=location != "global",
    )
