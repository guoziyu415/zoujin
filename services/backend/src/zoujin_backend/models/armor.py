"""Model Armor (B-12, S-085 ②: the second layer of safety screening; backend-design 5.5, 2.11).

Not a generative model but Google's filtering service: player input goes through `sanitizeUserPrompt` (the second layer
for injection, a supplement for personal information, harmful content counts only at HIGH), and character output goes
through `sanitizeModelResponse` (2.11). Three implementations:

- Fake (`fake`, default): the rules in `fixtures/fake-armor/*.json`, matching substrings in the text, and able to
  inject latency and errors; with no rules, nothing matches.
- Replay (`replay`): `fixtures/model-replays/armor/*.jsonl` (a subdirectory: the text model's replays read only the
  level above), key = `armor|<template config version>|<method>|<sha256 of the text>`; if not found, raises
  `ReplayMissing` (it is not silently treated as no match).
- Real (`real`, only on zg's Mac): REST, region us-central1 (asia-northeast1 does not support multi-language detection,
  S-4); the project and template names are given by environment variables (`ZJ_ARMOR_PROJECT`, `ZJ_ARMOR_TEMPLATE`),
  and the credentials are gcloud's ADC. The project, the template's resource name and the address never go into logs
  or exception messages.

The template's configuration is in `armor_template()`: all four RAI categories on at LOW and above (judging counts only
HIGH, measuring can see the lower levels), SDP basic, PI and jailbreak, malicious URLs, multi-language detection;
**logging off** (backend-design 5.4: if on, it would write the original text into Cloud Logging).

Model Armor（B-12、S-085 ②：安全審査の第 2 層。backend-design 5.5、2.11）。

生成モデルではなく Google のフィルタリングサービス：プレイヤーの入力は `sanitizeUserPrompt` を通し（インジェクションの
第 2 層、個人情報の補完、有害な内容は HIGH だけを認める）、登場人物の出力は `sanitizeModelResponse` を通す（2.11）。
実装は 3 つ：

- 偽物（`fake`、デフォルト）：`fixtures/fake-armor/*.json` のルールで、テキスト内の部分文字列で一致させ、遅延やエラーも
  注入できる。ルールがなければ何も一致しない。
- リプレイ（`replay`）：`fixtures/model-replays/armor/*.jsonl`（サブディレクトリ：テキストモデルのリプレイは 1 つ上の
  階層だけを読む）、キー = `armor|<テンプレート設定のバージョン>|<メソッド>|<テキストの sha256>`。見つからなければ
  `ReplayMissing` を投げる（黙って一致なしとはしない）。
- 本物（`real`、zg の Mac 上のみ）：REST、リージョン us-central1（asia-northeast1 は多言語検出に対応していない、S-4）。
  プロジェクトとテンプレートの名前は環境変数（`ZJ_ARMOR_PROJECT`、`ZJ_ARMOR_TEMPLATE`）で与え、認証情報は gcloud の
  ADC。プロジェクト、テンプレートのリソース名、アドレスはログにも例外メッセージにも入れない。

テンプレートの設定は `armor_template()` にある：RAI の 4 カテゴリはすべて LOW 以上で有効（判定では HIGH だけを認め、
計測では低いレベルも見える）、SDP basic、PI とジェイルブレイク、悪意のあるリンク、多言語検出。**ログは無効**
（backend-design 5.4：有効にすると原文が Cloud Logging に書かれる）。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
from zoujin_llm.errors import check_batch_halt

from zoujin_backend.config import REPO, ConfigError, ModelMode
from zoujin_backend.models.text import ReplayMissing

log = logging.getLogger("zoujin.armor")

Json = Any
Method = Literal["prompt", "response"]

LEVELS = ("LOW_AND_ABOVE", "MEDIUM_AND_ABOVE", "HIGH")
RAI_TYPES = ("dangerous", "harassment", "hate_speech", "sexually_explicit")
LOCATION = "us-central1"
PROJECT_ENV = "ZJ_ARMOR_PROJECT"
TEMPLATE_ENV = "ZJ_ARMOR_TEMPLATE"
# The price per call [estimate: 0.10 dollars per million tokens per the price list, about one token per Japanese
# character; the free quota is for the whole account and is not spread per playthrough]
# 1 回の呼び出しの単価〔推定：価格表で 100 万トークンあたり 0.10 ドル、日本語は 1 文字およそ 1 トークン。無料枠は
# アカウント全体のもので、周回ごとには割り振らない〕
USD_PER_MILLION_CHARS = 0.10
# Second layer: no answer within 1 second counts as no match (S-4 measured p50 282 ms, p95 556 ms)
# 第 2 層：1 秒以内に返らなければ一致なしとみなす（S-4 の実測 p50 282 ms、p95 556 ms）
DEADLINE_S = 1.0
SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class ArmorFailed(RuntimeError):
    """The call failed (network, HTTP error, timeout). The message contains only the status code.

    呼び出しが失敗した（ネットワーク、HTTP エラー、タイムアウト）。メッセージにはステータスコードだけを入れる。
    """


@dataclass(frozen=True)
class ArmorResult:
    """A flat result (same shape as the spike's `parse`). pi: the confidence level when PI and jailbreak matched, None
    if not; rai: matched category → confidence level; sdp: matched infoTypes (type names only); uri: malicious URL.

    フラットな結果（spike の `parse` と同じ形）。pi：PI とジェイルブレイクに一致したときの信頼度レベル、一致しなければ
    None。rai：一致したカテゴリ → 信頼度レベル。sdp：一致した infoType（種類名のみ）。uri：悪意のあるリンク。
    """

    pi: str | None = None
    rai: Mapping[str, str] = field(default_factory=dict)
    sdp: tuple[str, ...] = ()
    uri: bool = False

    @property
    def injection(self) -> bool:
        """The second layer for injection: PI at MEDIUM or above (S-4: the LOW level misjudged many harsh words within
        the story).

        インジェクションの第 2 層：PI が MEDIUM 以上（S-4：LOW レベルは物語の中の荒い言葉を多く誤判定した）。
        """
        return self.pi in ("MEDIUM_AND_ABOVE", "HIGH")

    @property
    def harmful(self) -> bool:
        """Harmful content counts only at HIGH (S-4: LOW wrongly blocked 8/14 and MEDIUM 4/14 harsh lines within the
        story, HIGH 0/14).

        有害な内容は HIGH だけを認める（S-4：物語の中の荒い言葉を LOW は 8/14、MEDIUM は 4/14 誤って止め、HIGH は
        0/14）。
        """
        return any(v == "HIGH" for v in self.rai.values())

    @property
    def pii(self) -> bool:
        return bool(self.sdp)

    def to_json(self) -> Json:
        return {"pi": self.pi, "rai": dict(self.rai), "sdp": list(self.sdp), "uri": self.uri}

    @staticmethod
    def from_json(d: Mapping[str, Any]) -> ArmorResult:
        return ArmorResult(d.get("pi"), dict(d.get("rai") or {}), tuple(d.get("sdp") or ()), bool(d.get("uri")))


NONE = ArmorResult()


class Armor(Protocol):
    mode: ModelMode

    async def screen_prompt(self, text: str) -> ArmorResult: ...
    async def screen_response(self, text: str) -> ArmorResult: ...


# —— Template / テンプレート ——


def cost_usd(armor: Armor, text: str) -> float:
    """How much this call records (`cost_armor_usd`): only real calls record a cost; fake and replay are 0.

    この呼び出しで記録する額（`cost_armor_usd`）：本物だけが記録し、偽物とリプレイは 0。
    """
    return len(text) * USD_PER_MILLION_CHARS / 1_000_000 if armor.mode == "real" else 0.0


def armor_template() -> Json:
    """The production template configuration (the REST Template resource, same shape as the spike's `make_template`).
    Logging off.

    本番用のテンプレート設定（REST の Template リソースで、spike の `make_template` と同じ形）。ログは無効。
    """
    return {
        "filterConfig": {
            "raiSettings": {
                "raiFilters": [{"filterType": t.upper(), "confidenceLevel": "LOW_AND_ABOVE"} for t in RAI_TYPES]
            },
            "sdpSettings": {"basicConfig": {"filterEnforcement": "ENABLED"}},
            "piAndJailbreakFilterSettings": {"filterEnforcement": "ENABLED", "confidenceLevel": "LOW_AND_ABOVE"},
            "maliciousUriFilterSettings": {"filterEnforcement": "ENABLED"},
        },
        "templateMetadata": {
            "multiLanguageDetection": {"enableMultiLanguageDetection": True},
            "logTemplateOperations": False,
            "logSanitizeOperations": False,
        },
    }


def template_version() -> str:
    """The template configuration's version (used in replay keys): when the configuration changes, old replays are
    no longer found.

    テンプレート設定のバージョン（リプレイのキーに使う）：設定を変えると古いリプレイは見つからなくなる。
    """
    return "t" + hashlib.sha256(json.dumps(armor_template(), sort_keys=True).encode()).hexdigest()[:12]


def replay_key(method: Method, text: str) -> str:
    return f"armor|{template_version()}|{method}|{hashlib.sha256(text.encode()).hexdigest()}"


# —— Parsing the REST response / REST の応答の解析 ——


def _matched(d: Mapping[str, Any] | None) -> bool:
    return bool(d) and (d or {}).get("matchState") == "MATCH_FOUND"


def parse(data: Mapping[str, Any]) -> ArmorResult:
    """`sanitizationResult` → ArmorResult. Unrecognized keys are ignored.

    `sanitizationResult` → ArmorResult。判別できないキーは無視する。
    """
    results = (data.get("sanitizationResult") or {}).get("filterResults") or {}
    pi: str | None = None
    rai: dict[str, str] = {}
    sdp: set[str] = set()
    uri = False
    for fr in results.values():
        r = fr.get("piAndJailbreakFilterResult")
        if _matched(r):
            pi = r.get("confidenceLevel") if r.get("confidenceLevel") in LEVELS else "LOW_AND_ABOVE"
        r = fr.get("raiFilterResult")
        if r:
            for t, tr in (r.get("raiFilterTypeResults") or {}).items():
                if _matched(tr):
                    rai[str(t).lower()] = tr.get("confidenceLevel") or "LOW_AND_ABOVE"
        r = fr.get("sdpFilterResult")
        if r:
            insp = r.get("inspectResult") or {}
            if _matched(insp):
                sdp |= {str(f.get("infoType")) for f in insp.get("findings") or [] if f.get("infoType")}
                if not sdp:
                    sdp.add("UNKNOWN")
        r = fr.get("maliciousUriFilterResult")
        if _matched(r):
            uri = True
    return ArmorResult(pi, rai, tuple(sorted(sdp)), uri)


# —— Fake / 偽物 ——

FAKE_ARMOR = REPO / "fixtures" / "fake-armor"


class FakeArmor:
    """Rules: `{"method": "prompt" | "response" (omitted = both match), "contains": "…", "result": {...ArmorResult},
    "error": "unavailable" | "timeout", "latencyMs": N}`; the first match wins.

    ルール：`{"method": "prompt" | "response"（省略 = 両方に一致）, "contains": "…", "result": {...ArmorResult},
    "error": "unavailable" | "timeout", "latencyMs": N}`。最初に一致したものが有効。
    """

    mode: ModelMode = "fake"

    def __init__(self, rules_dir: Path | None = None, rules: list[Json] | None = None) -> None:
        self.rules: list[Json] = []
        if rules_dir is not None and rules_dir.is_dir():
            for p in sorted(rules_dir.glob("*.json")):
                self.rules.extend(json.loads(p.read_text(encoding="utf-8"))["rules"])
        self.rules.extend(rules or [])
        self.calls: list[tuple[str, str]] = []

    async def _screen(self, method: Method, text: str) -> ArmorResult:
        self.calls.append((method, text))
        for r in self.rules:
            if r.get("method", method) != method or r.get("contains", "") not in text:
                continue
            if r.get("latencyMs"):
                await asyncio.sleep(r["latencyMs"] / 1000)
            if r.get("error") == "unavailable":
                raise ArmorFailed("Fake Armor: call failed / 偽 Armor：呼び出しが失敗")
            return ArmorResult.from_json(r.get("result") or {})
        return NONE

    async def screen_prompt(self, text: str) -> ArmorResult:
        return await self._screen("prompt", text)

    async def screen_response(self, text: str) -> ArmorResult:
        return await self._screen("response", text)


# —— Replay / リプレイ ——


class ReplayArmor:
    mode: ModelMode = "replay"

    def __init__(self, replay_dir: Path) -> None:
        self.rows: dict[str, ArmorResult] = {}
        if replay_dir.is_dir():
            for p in sorted((replay_dir / "armor").glob("*.jsonl")):
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        row = json.loads(line)
                        self.rows[row["key"]] = ArmorResult.from_json(row["response"])

    def _get(self, method: Method, text: str) -> ArmorResult:
        key = replay_key(method, text)
        if key not in self.rows:
            raise ReplayMissing(
                f"This call is not in the Model Armor replays / Model Armor のリプレイにこの呼び出しがない ({method})"
            )
        return self.rows[key]

    async def screen_prompt(self, text: str) -> ArmorResult:
        return self._get("prompt", text)

    async def screen_response(self, text: str) -> ArmorResult:
        return self._get("response", text)


# —— Real (only on the Mac) / 本物（Mac 上のみ） ——


class RealArmor:  # pragma: no cover - runs only on the Mac / Mac 上でのみ実行
    mode: ModelMode = "real"

    def __init__(self, project: str, template: str, client: httpx.AsyncClient | None = None) -> None:
        from zoujin_backend.models.vertex import AdcAuth

        # httpx's INFO logs carry the full URL (which contains the project ID)
        # httpx の INFO ログには完全な URL（プロジェクト ID を含む）が出る
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)
        self._auth = AdcAuth()
        self._base = (
            f"https://modelarmor.{LOCATION}.rep.googleapis.com/v1/"
            f"projects/{project}/locations/{LOCATION}/templates/{template}"
        )
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self.latencies_ms: list[float] = []

    async def _post(self, verb: str, body: Json) -> ArmorResult:
        check_batch_halt()
        headers = {"Authorization": f"Bearer {self._auth.token()}", "Content-Type": "application/json"}
        t0 = time.perf_counter()
        try:
            resp = await self._client.post(f"{self._base}:{verb}", json=body, headers=headers)
        except httpx.HTTPError:
            raise ArmorFailed(
                "Network error (message not logged) / ネットワークエラー（メッセージは記録しない）"
            ) from None
        self.latencies_ms.append((time.perf_counter() - t0) * 1000)
        if resp.status_code >= 400:
            raise ArmorFailed(f"HTTP {resp.status_code} (message not logged / メッセージは記録しない)")
        return parse(resp.json())

    async def screen_prompt(self, text: str) -> ArmorResult:
        return await self._post("sanitizeUserPrompt", {"userPromptData": {"text": text}})

    async def screen_response(self, text: str) -> ArmorResult:
        return await self._post("sanitizeModelResponse", {"modelResponseData": {"text": text}})


# Only on the Mac, after zg approves / Mac 上のみ、zg の承認後
def create_template(project: str, template: str) -> int:  # pragma: no cover
    """Create the production template in zg's GCP project (`armor-template --confirm`). Returns the HTTP status code;
    the message is not logged.

    zg の GCP プロジェクトに本番用のテンプレートを作る（`armor-template --confirm`）。HTTP ステータスコードを返し、
    メッセージは記録しない。
    """
    from zoujin_backend.models.vertex import AdcAuth

    auth = AdcAuth()
    url = f"https://modelarmor.{LOCATION}.rep.googleapis.com/v1/projects/{project}/locations/{LOCATION}/templates"
    headers = {"Authorization": f"Bearer {auth.token()}", "Content-Type": "application/json"}
    resp = httpx.post(url, params={"templateId": template}, json=armor_template(), headers=headers, timeout=30.0)
    return resp.status_code


def armor(mode: ModelMode, *, fake_rules: Path | None = None, replays: Path | None = None) -> Armor:
    if mode == "fake":
        return FakeArmor(fake_rules if fake_rules is not None else FAKE_ARMOR)
    if mode == "replay":
        if replays is None:
            raise ConfigError(
                "ZJ_MODEL=replay needs a replay directory / ZJ_MODEL=replay にはリプレイのディレクトリが必要"
            )
        return ReplayArmor(replays)
    project, template = os.environ.get(PROJECT_ENV), os.environ.get(TEMPLATE_ENV)
    if not project or not template:
        raise ConfigError(
            f"Model Armor under ZJ_MODEL=real needs {PROJECT_ENV} and {TEMPLATE_ENV} / "
            f"ZJ_MODEL=real の Model Armor には {PROJECT_ENV} と {TEMPLATE_ENV} が必要"
        )
    return RealArmor(project, template)
