"""Claude 这一家（D-028、B-8）：模型档名、单价、回放的键、Anthropic 的连接。叙事者和评审员共用这一份。

- **模型 ID 不进仓库**：运行时由 Mac 上的环境变量或命令行给，回放、账本、报告里只写档名加版本（`model_tag()`，
  如 "sonnet-5.5"）。认不出档名的不调。
- **单价**只有一份：本包的 `claude-prices.json`，按档认（Haiku、Sonnet、Opus、Fable）。
- **回放的键** `<provider>|<模型>|<提示版本>|<请求的 sha256>`，Google 和 Claude 同一个函数，换了供应商查不到。
- **连接**：同步（评审员、Batch）、异步（叙事者）两个客户端都 `max_retries=0`，Key 只从环境变量 `ANTHROPIC_API_KEY`
  读（SDK 自己读，这里不碰）。SDK 的错误换成不带原消息的异常：429、529 → `RateLimited`，别的 →
  `ModelCallFailed`（只有状态码）。SDK 在可选依赖 `real` 里，只在真调时才 import。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from zoujin_llm.errors import ModelCallFailed, RateLimited

type Json = Any

PROVIDER = "claude"
TAG_RE = re.compile(r"(opus|sonnet|haiku|fable)-(\d+)-(\d+)")  # 模型 ID 里的档名和版本
PRICES_PATH = Path(__file__).with_name("claude-prices.json")
LIMITS = (429, 529)  # 限流、过载：第一次就停


def model_tag(model: str) -> str:
    """模型 ID → 档名加版本（"…-opus-5-5…" → "opus-5.5"）。回放的键、回放和账本的行、报告都用它，模型 ID 不进仓库。
    认不出（没有档名、档名不止一个、档名后面没有两段数字）就不调。"""
    hits = TAG_RE.findall(model.lower())
    if len({h[0] for h in hits}) != 1:
        raise ValueError(f"认不出模型 {model!r} 的档名和版本，不调")
    tier, major, minor = hits[0]
    return f"{tier}-{major}.{minor}"


def tier_of(model: str) -> str:
    """模型 ID 或档名加版本 → 档名（"sonnet-5.5" → "sonnet"）。"""
    return model_tag(model.replace(".", "-")).split("-")[0]


def canonical(request: Json) -> str:
    """规范化请求：键排序、不转义非 ASCII、没有多余空白。"""
    return json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def replay_key(provider: str, model: str, version: str, request: Json) -> str:
    """回放的键。model：Google 写模型 ID，Claude 写档名加版本。"""
    return f"{provider}|{model}|{version}|{hashlib.sha256(canonical(request).encode()).hexdigest()}"


# —— 单价 ——


@dataclass(frozen=True)
class Price:
    input: float  # 美元 / 百万 token
    output: float
    cache_read: float  # 缓存读取，各档不同
    tokenizer: float = 1.0  # 同样的文字比别的档多算几倍 token（Haiku 约 1.3），只用在调用前的预计


@dataclass(frozen=True)
class ClaudePrices:
    tiers: Mapping[str, Price]  # 模型档（opus / sonnet / haiku / fable）→ 单价
    batch_discount: float  # Batch 两头的折扣（0.5 = 半价）
    cache_write: float  # 缓存写入是输入价的几倍（5 分钟的）
    chars_per_token: float  # 估输入 token 用：日语、中文按每字一个 token 估，偏高

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> ClaudePrices:
        tiers = {
            k: Price(float(v["input"]), float(v["output"]), float(v["cacheRead"]), float(v.get("tokenizer", 1.0)))
            for k, v in d["perMTok"].items()
        }
        return cls(tiers, float(d["batchDiscount"]), float(d["cacheWriteMultiplier"]), float(d["charsPerToken"]))

    def price(self, model: str) -> Price:
        """按档认：模型 ID 或档名加版本里含哪个档名就用哪个，认不出就不调。"""
        hits = [t for t in self.tiers if t in model.lower()]
        if len(hits) != 1:
            raise ValueError(f"认不出模型 {model!r} 的价目档（{'/'.join(self.tiers)}），不调")
        return self.tiers[hits[0]]

    def cost(self, model: str, usage: Mapping[str, int], *, batch: bool = False) -> float:
        """usage：inputTokens（没走缓存的输入）、cacheReadTokens、cacheWriteTokens、outputTokens（含思考）。"""
        p = self.price(model)
        usd = (
            (usage.get("inputTokens", 0) + usage.get("cacheWriteTokens", 0) * self.cache_write) * p.input
            + usage.get("cacheReadTokens", 0) * p.cache_read
            + usage.get("outputTokens", 0) * p.output
        ) / 1_000_000
        return usd * (self.batch_discount if batch else 1.0)

    def estimate_chars(self, model: str, chars: int, max_output: int, *, batch: bool = False) -> float:
        """调用前的预计（偏高）：输入按字数估、不算缓存，乘这一档的分词倍数；输出按上限（思考也算输出）。"""
        p = self.price(model)
        tokens = int(chars / self.chars_per_token * p.tokenizer) + 1
        return self.cost(model, {"inputTokens": tokens, "outputTokens": max_output}, batch=batch)

    def estimate(self, model: str, request: Mapping[str, Json], *, batch: bool) -> float:
        """评审员的请求（system、user、schema、maxTokens）的预计。"""
        chars = len(request["system"]) + len(request["user"]) + len(canonical(request["schema"]))
        return self.estimate_chars(model, chars, int(request["maxTokens"]), batch=batch)


@cache
def claude_prices() -> ClaudePrices:
    return ClaudePrices.from_json(json.loads(PRICES_PATH.read_text(encoding="utf-8")))


# —— 和 API 之间 ——


@dataclass(frozen=True)
class Reply:
    text: str | None  # 第一段 text（结构化输出的 JSON）；没有时 None
    stop_reason: str | None
    # inputTokens（没走缓存的）、cacheReadTokens、cacheWriteTokens、outputTokens（含思考）、thinkingTokens（其中思考的，
    # 只用来看，算钱不再加）
    usage: dict[str, int]


def reply_of(msg: Any) -> Reply:
    """SDK 的 Message → Reply（只取文字和用量，思考的内容不取）。"""
    u = msg.usage
    usage = {
        "inputTokens": int(u.input_tokens),
        "outputTokens": int(u.output_tokens),
        "cacheReadTokens": int(u.cache_read_input_tokens or 0),
        "cacheWriteTokens": int(u.cache_creation_input_tokens or 0),
        "thinkingTokens": thinking_tokens(u),
    }
    text = next((b.text for b in msg.content if b.type == "text"), None)
    return Reply(text, msg.stop_reason, usage)


def thinking_tokens(usage: Any) -> int:
    details = getattr(usage, "output_tokens_details", None)
    return int(getattr(details, "thinking_tokens", 0) or 0)


def translate(e: BaseException) -> Exception:
    """SDK 的错误 → 不带原消息的异常。调用方 `raise translate(e) from None`，原消息不进日志和 Trace。"""
    import anthropic

    if isinstance(e, anthropic.APIStatusError):
        if e.status_code in LIMITS:
            return RateLimited(f"Claude 回 {e.status_code}（限流或过载），停下")
        return ModelCallFailed(f"Claude HTTP {e.status_code}（消息不记）")
    if isinstance(e, anthropic.APIError):  # 连接断开、超时
        return ModelCallFailed(f"Claude 连不上：{type(e).__name__}（消息不记）")
    return ModelCallFailed(f"Claude 调用出错：{type(e).__name__}（消息不记）")


# SDK 和它的 HTTP 库的调试日志带请求的全文（提示、玩家的话、模型 ID）和错误的原消息：只留 WARNING 以上
QUIET = ("anthropic", "httpx", "httpx2", "httpcore")


def quiet() -> None:
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)


def client() -> Any:
    """同步客户端（评审员、Batch）。Key 由 SDK 从 ANTHROPIC_API_KEY 读，不自己重试。"""
    import anthropic

    quiet()
    return anthropic.Anthropic(max_retries=0)


def async_client() -> Any:
    """异步客户端（叙事者）。"""
    import anthropic

    quiet()
    return anthropic.AsyncAnthropic(max_retries=0)


class AsyncTransport:
    """叙事者用的传输层：一次 Messages 调用。测试换成假的，不联网。"""

    def __init__(self, sdk: Any | None = None) -> None:
        quiet()
        self._sdk = sdk if sdk is not None else async_client()

    async def create(self, params: Json) -> Reply:
        import anthropic

        try:
            msg = await self._sdk.messages.create(**params)
        except anthropic.APIError as e:
            raise translate(e) from None
        return reply_of(msg)
