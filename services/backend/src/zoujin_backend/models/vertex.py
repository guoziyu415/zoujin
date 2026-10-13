"""Real text model: Gemini on Vertex AI (`ZJ_MODEL=real`, runs only on zg's Mac, G-7). Threads in the project and CI
never call it. Since B-8 only the prompts whose provider in `config.TEXT` is google remain (`reply`, standing in for
Live as the character in evals); everything else goes through `models/claude.py`.

- Authentication uses the application default credentials from the gcloud login on the Mac (ADC, `google-auth`,
  optional dependency group `real`); there is no API key.
- **The project ID and region are read only from explicitly set environment variables** (`ZJ_VERTEX_PROJECT`,
  `ZJ_VERTEX_LOCATION`), and only under real; if unset, exit without sending a request. The default project inferred by
  ADC or gcloud is not used (gcloud's default configuration on the Mac is not for this project). The project ID never
  goes into logs, the Trace, replays, the ledger or exception messages: transport errors become `ModelCallFailed`
  without the original message.
- Uses REST (`generateContent`, httpx), and the transport layer can be swapped for a fake (tests use
  `httpx.MockTransport`, with no network).
- Each call: render the prompt (world model prefix first) → check the ledger caps (`BudgetStop`) → call (429 →
  `RateLimited`, stop at the first one) → record in the ledger → validate the output against the Schema (failure →
  `BadOutput`, resent by the pipeline under the time-limit rules). When `ZJ_RECORD_REPLAYS` is set,
  `models.text.Recording` records one replay line.
- A call cancelled by the time limit is recorded at the estimated cost (it may already have been billed, so better to
  over-record). Every line carries the duration and status (B-5: `ok`, `timeout`, `bad-output`; no response is
  recorded as `error` with cost 0).

実テキストモデル：Vertex AI 上の Gemini（`ZJ_MODEL=real`、zg の Mac 上でのみ実行、G-7）。プロジェクト内のスレッドと CI
は決して呼び出さない。B-8 以降は `config.TEXT` で provider が google のプロンプト（評価で Live の代わりに登場人物を
務める `reply`）だけが残り、それ以外は `models/claude.py` を通る。

- 認証は Mac 上で gcloud にログインしたアプリケーションのデフォルト認証情報（ADC、`google-auth`、オプション依存
  グループ `real`）を使い、API キーはない。
- **プロジェクト ID とリージョンは明示的に設定した環境変数からだけ読む**（`ZJ_VERTEX_PROJECT`、`ZJ_VERTEX_LOCATION`）。
  real のときだけ読み、未設定ならリクエストを送らずに終了する。ADC や gcloud
  が推定したデフォルトのプロジェクトは使わない（Mac 上の gcloud のデフォルト設定はこのプロジェクトのものではない）。
  プロジェクト ID はログ、Trace、リプレイ、台帳、例外メッセージに入れない：
  トランスポート層のエラーは元のメッセージを含まない `ModelCallFailed` に置き換える。
- REST（`generateContent`、httpx）を使い、トランスポート層は偽物に差し替えられる（テストは `httpx.MockTransport`
  を使い、ネットワークに出ない）。
- 呼び出しごとに：プロンプトをレンダリング（世界モデルのプレフィックスを先頭）→ 台帳で上限を判定（`BudgetStop`）→
  呼び出し（429 → `RateLimited`、最初の 1 回で止まる）→ 台帳に記録 → 出力を Schema で検証（通らなければ
  `BadOutput`。パイプラインが時間制限の規則で再送する）。`ZJ_RECORD_REPLAYS` を設定していれば
  `models.text.Recording` がリプレイを 1 行録る。
- 時間制限で取り消された呼び出しは見積もり費用で記録する（すでに課金されているかもしれないので、多めに記録する）。
  各行に所要時間と状態を付ける（B-5：`ok`、`timeout`、`bad-output`。応答がないものは `error`、費用 0）。
"""

from __future__ import annotations

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
    """The ADC access token, refreshed when it is about to expire. Takes only the credentials, not the project returned
    by google.auth.default().

    ADC のアクセストークン。期限が近づいたら更新する。認証情報だけを取り、google.auth.default() が返すプロジェクトは
    使わない。
    """

    def __init__(self) -> None:
        try:
            import google.auth
            import google.auth.transport.requests
        except ImportError as e:  # pragma: no cover - only on the Mac / Mac 上のみ
            raise ConfigError(
                "ZJ_MODEL=real needs the optional dependency group real: uv sync --extra real / "
                "ZJ_MODEL=real にはオプション依存グループ real が必要：uv sync --extra real"
            ) from e
        # The second return value is the inferred project: not used / 2 つ目の戻り値は推定したプロジェクト：使わない
        self._creds, _ = google.auth.default(scopes=[SCOPE])
        self._request = google.auth.transport.requests.Request()
        self._at = 0.0

    def token(self) -> str:  # pragma: no cover - only on the Mac / Mac 上のみ
        if not self._creds.valid or time.monotonic() - self._at > 45 * 60:
            # google-auth does not annotate this method / google-auth のこのメソッドには型注釈がない
            self._creds.refresh(self._request)  # type: ignore[no-untyped-call]
            self._at = time.monotonic()
        return str(self._creds.token)


class Transport(Protocol):
    async def generate(self, model: str, body: Json) -> Generated: ...


class RestTransport:
    """Vertex AI's `generateContent` (REST). The global endpoint and the regional endpoints have different addresses.

    Vertex AI の `generateContent`（REST）。global エンドポイントとリージョンのエンドポイントはアドレスが異なる。
    """

    def __init__(self, project: str, location: str, auth: Auth, client: httpx.AsyncClient | None = None) -> None:
        # httpx's INFO logs carry the full URL (which contains the project ID)
        # httpx の INFO ログには完全な URL（プロジェクト ID を含む）が出る
        for name in ("httpx", "httpcore"):
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
            raise ModelCallFailed(
                "Network error (message not logged) / ネットワークエラー（メッセージは記録しない）"
            ) from None
        if resp.status_code == 429:
            raise RateLimited(
                "The model returned 429 (quota or rate limit); stopping / "
                "モデルが 429 を返した（利用枠またはレート制限）。停止する",
                provider="google",
                status=429,
                retry_after=resp.headers.get("retry-after"),
            )
        if resp.status_code >= 400:
            raise ModelCallFailed(f"HTTP {resp.status_code} (message not logged / メッセージは記録しない)")
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
    """The estimated cost before a call, on the high side: input at one token per character, output at the cap.

    呼び出し前の見積もり費用（高め）：入力は 1 文字 1 トークン、出力は上限で見積もる。
    """
    usage = {"inputTokens": chars, "outputTokens": spec(kind).max_output}
    return cost_usd(model, usage, regional=regional)


# —— Client / クライアント ——


@dataclass
class RealText:
    transport: Transport
    ledger: Ledger
    worlds: Callable[[str], Json]  # worldModelVersion → world model / worldModelVersion → 世界モデル
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
        with self.ledger.timed(kind=kind, model=model, estimate=guess) as bill:
            got = await self.transport.generate(model, req)
            cost = cost_usd(model, got.usage, regional=self.regional)
            try:
                output = json.loads(got.text)
                jsonschema.validate(output, PROMPTS[kind].schema)
            except (ValueError, jsonschema.ValidationError):
                bill.done(got.usage, cost, ok=False)
                raise BadOutput(
                    f"{kind}: output is not JSON matching the Schema / 出力が Schema に合う JSON ではない", cost
                ) from None
            bill.done(got.usage, cost)
        return TextResult(output, kind, model, version, dict(got.usage), cost)


def vertex_env(env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """Called only under real: the project and region are read only from these two environment variables; if unset,
    exit (no request is sent, and no default project is inferred).

    real のときだけ呼ぶ：プロジェクトとリージョンはこの 2 つの環境変数からだけ読み、未設定なら終了する（リクエストは
    送らず、デフォルトのプロジェクトも推定しない）。
    """
    e = os.environ if env is None else env
    project, location = e.get(PROJECT_ENV, ""), e.get(LOCATION_ENV, "")
    if not project or not location:
        raise ConfigError(
            f"ZJ_MODEL=real requires {PROJECT_ENV} and {LOCATION_ENV} to be set explicitly (only on the Mac); they are "
            f"not set, so not calling / ZJ_MODEL=real では {PROJECT_ENV} と {LOCATION_ENV} を明示的に設定する必要が"
            "ある（Mac 上のみ）。未設定なので呼び出さない"
        )
    return project, location


def real_text(
    settings: Settings,
    *,
    ledger: Ledger | None = None,
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
) -> RealText:
    """Build the real client from Settings. The ledger and the total cap are required (ZJ_LEDGER, ZJ_MAX_GOOGLE_USD, or
    the ledger passed in by the S-2 runner).

    Settings から実クライアントを作る。台帳と総上限は必須（ZJ_LEDGER、ZJ_MAX_GOOGLE_USD、または S-2 のランナーが
    渡す ledger）。
    """
    project, location = vertex_env(env)
    if ledger is None:
        if settings.ledger is None or settings.max_google_usd is None:
            raise ConfigError(
                "ZJ_MODEL=real needs a ledger and Google's total cap: ZJ_LEDGER, ZJ_MAX_GOOGLE_USD, with no defaults / "
                "ZJ_MODEL=real には台帳と Google の総上限が必要：ZJ_LEDGER、ZJ_MAX_GOOGLE_USD。デフォルト値はない"
            )
        ledger = Ledger(settings.ledger, settings.max_google_usd, settings.max_item_usd, settings.ledger_item)
    library = Library(settings.worlds, settings.scenes, settings.world, settings.released_worlds)
    return RealText(
        transport=transport or RestTransport(project, location, AdcAuth()),
        ledger=ledger,
        worlds=lambda v: library.version(v).world,
        regional=location != "global",
    )
