"""Model Armor（B-12，S-085 ②：安全筛查的第二层；backend-design 5.5、2.11）。

不是生成模型，是 Google 的过滤服务：玩家输入过 `sanitizeUserPrompt`（注入的第二层、个人信息的补充、有害内容只认 HIGH），
人物输出过 `sanitizeModelResponse`（2.11）。三种实现：

- 假的（`fake`，默认）：`fixtures/fake-armor/*.json` 的规则，按文字里的子串命中，也能注入延迟和错误；
  没有规则就全不命中。
- 回放（`replay`）：`fixtures/model-replays/armor/*.jsonl`（子目录：文本模型的回放只读上一层），
  键 = `armor|<模板配置的版本>|<方法>|<文字的 sha256>`，查不到抛
  `ReplayMissing`（不悄悄当没命中）。
- 真的（`real`，只在 zg 的 Mac 上）：REST，区域 us-central1（asia-northeast1 不支持多语言检测，S-4），
  项目和模板名从环境变量
  给（`ZJ_ARMOR_PROJECT`、`ZJ_ARMOR_TEMPLATE`），凭证是 gcloud 的 ADC。项目、模板的资源名、地址不进日志和异常消息。

模板的配置在 `armor_template()`：RAI 四类都开在 LOW 以上（判的时候只认 HIGH，量的时候能看到低档）、SDP basic、
PI 和越狱、
恶意链接、多语言检测；**不开日志**（backend-design 5.4：开了会把原文写进 Cloud Logging）。
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
# 每次调用的单价〔推算：按价目表每百万 token 0.10 美元、日语一字约一 token；免费额度是整个账户的，不按局摊〕
USD_PER_MILLION_CHARS = 0.10
DEADLINE_S = 1.0  # 第二层：1 秒没回就当没命中（S-4 实测 p50 282 ms、p95 556 ms）
SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class ArmorFailed(RuntimeError):
    """调用失败（网络、HTTP 错误、超时）。消息里只有状态码。"""


@dataclass(frozen=True)
class ArmorResult:
    """扁平的结果（spike 的 `parse` 同形）。pi：PI 和越狱命中时的置信档，没命中 None；rai：命中的类别 → 置信档；
    sdp：命中的 infoType（只有类型名）；uri：恶意链接。"""

    pi: str | None = None
    rai: Mapping[str, str] = field(default_factory=dict)
    sdp: tuple[str, ...] = ()
    uri: bool = False

    @property
    def injection(self) -> bool:
        """注入的第二层：PI 在 MEDIUM 以上（S-4：LOW 档在故事里的狠话上误判多）。"""
        return self.pi in ("MEDIUM_AND_ABOVE", "HIGH")

    @property
    def harmful(self) -> bool:
        """有害内容只认 HIGH（S-4：LOW 8/14、MEDIUM 4/14 误拦故事里的狠话，HIGH 0/14）。"""
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


# —— 模板 ——


def cost_usd(armor: Armor, text: str) -> float:
    """这一次调用记多少（`cost_armor_usd`）：只有真的记，假的和回放是 0。"""
    return len(text) * USD_PER_MILLION_CHARS / 1_000_000 if armor.mode == "real" else 0.0


def armor_template() -> Json:
    """正式用的模板配置（REST 的 Template 资源，和 spike 的 `make_template` 同形）。日志不开。"""
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
    """模板配置的版本（回放的键用）：配置改了，旧的回放查不到。"""
    return "t" + hashlib.sha256(json.dumps(armor_template(), sort_keys=True).encode()).hexdigest()[:12]


def replay_key(method: Method, text: str) -> str:
    return f"armor|{template_version()}|{method}|{hashlib.sha256(text.encode()).hexdigest()}"


# —— 解析 REST 的回答 ——


def _matched(d: Mapping[str, Any] | None) -> bool:
    return bool(d) and (d or {}).get("matchState") == "MATCH_FOUND"


def parse(data: Mapping[str, Any]) -> ArmorResult:
    """`sanitizationResult` → ArmorResult。认不出来的键忽略。"""
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


# —— 假的 ——

FAKE_ARMOR = REPO / "fixtures" / "fake-armor"


class FakeArmor:
    """规则：`{"method": "prompt" | "response"（不写 = 两样都认）, "contains": "…", "result": {...ArmorResult},
    "error": "unavailable" | "timeout", "latencyMs": N}`，第一条命中的算。"""

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
                raise ArmorFailed("假 Armor：调用失败")
            return ArmorResult.from_json(r.get("result") or {})
        return NONE

    async def screen_prompt(self, text: str) -> ArmorResult:
        return await self._screen("prompt", text)

    async def screen_response(self, text: str) -> ArmorResult:
        return await self._screen("response", text)


# —— 回放 ——


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
            raise ReplayMissing(f"Model Armor 的回放里没有这次调用（{method}）")
        return self.rows[key]

    async def screen_prompt(self, text: str) -> ArmorResult:
        return self._get("prompt", text)

    async def screen_response(self, text: str) -> ArmorResult:
        return self._get("response", text)


# —— 真的（只在 Mac 上） ——


class RealArmor:  # pragma: no cover - 只在 Mac 上跑
    mode: ModelMode = "real"

    def __init__(self, project: str, template: str, client: httpx.AsyncClient | None = None) -> None:
        from zoujin_backend.models.vertex import AdcAuth

        for name in ("httpx", "httpcore"):  # httpx 的 INFO 日志带完整的 URL（里面有项目 ID）
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
            raise ArmorFailed("网络错误（消息不记）") from None
        self.latencies_ms.append((time.perf_counter() - t0) * 1000)
        if resp.status_code >= 400:
            raise ArmorFailed(f"HTTP {resp.status_code}（消息不记）")
        return parse(resp.json())

    async def screen_prompt(self, text: str) -> ArmorResult:
        return await self._post("sanitizeUserPrompt", {"userPromptData": {"text": text}})

    async def screen_response(self, text: str) -> ArmorResult:
        return await self._post("sanitizeModelResponse", {"modelResponseData": {"text": text}})


def create_template(project: str, template: str) -> int:  # pragma: no cover - 只在 Mac 上，zg 点头以后
    """在 zg 的 GCP 项目里建正式用的模板（`armor-template --confirm`）。返回 HTTP 状态码，消息不记。"""
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
            raise ConfigError("ZJ_MODEL=replay 要回放目录")
        return ReplayArmor(replays)
    project, template = os.environ.get(PROJECT_ENV), os.environ.get(TEMPLATE_ENV)
    if not project or not template:
        raise ConfigError(f"ZJ_MODEL=real 的 Model Armor 要 {PROJECT_ENV} 和 {TEMPLATE_ENV}")
    return RealArmor(project, template)
