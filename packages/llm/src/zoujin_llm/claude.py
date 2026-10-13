"""The Claude provider (D-028, B-8): model tier names, prices, replay keys, and the Anthropic connection. The narrator
and the judge share this one copy.

- **Model IDs stay out of the repo**: they are given at runtime by environment variables or the command line on the Mac;
  replays, the ledger and reports record only the tier name plus version (`model_tag()`, e.g. "sonnet-5.5"). A model
  whose tier name cannot be recognized is not called.
- **Prices** exist in one place only: this package's `claude-prices.json`, matched by tier (Haiku, Sonnet, Opus, Fable).
- **Replay keys** `<provider>|<model>|<prompt version>|<sha256 of the request>`: Google and Claude use the same
  function, and a key is not found after switching providers.
- **Connection**: both the sync client (judge, Batch) and the async client (narrator) use `max_retries=0`; the key is
  read only from the environment variable `ANTHROPIC_API_KEY` (the SDK reads it itself; this code does not touch it).
  SDK errors are turned into exceptions without the original message: 429, 529 → `RateLimited`, anything else →
  `ModelCallFailed` (status code only). The SDK is in the optional dependency `real` and is imported only for real
  calls.

Claude というプロバイダ（D-028、B-8）：モデルのティア名、単価、リプレイのキー、Anthropic への接続。ナレーターと審査員は
この 1 つを共用する。

- **モデル ID はリポジトリに入れない**：実行時に Mac 上の環境変数かコマンドラインで与え、リプレイ、台帳、レポートには
  ティア名とバージョンだけを書く（`model_tag()`、例 "sonnet-5.5"）。ティア名を判別できないものは呼び出さない。
- **単価**は 1 か所だけ：このパッケージの `claude-prices.json` で、ティアで照合する（Haiku、Sonnet、Opus、Fable）。
- **リプレイのキー** `<provider>|<モデル>|<プロンプトバージョン>|<リクエストの sha256>`。Google と Claude
  で同じ関数を使い、プロバイダを変えると見つからない。
- **接続**：同期（審査員、Batch）と非同期（ナレーター）の 2 つのクライアントはどちらも `max_retries=0`。キーは環境変数
  `ANTHROPIC_API_KEY` からだけ読む（SDK 自身が読み、ここでは触らない）。SDK のエラーは元のメッセージを含まない例外に
  変える：429、529 → `RateLimited`、それ以外 → `ModelCallFailed`（ステータスコードのみ）。SDK はオプション依存 `real`
  にあり、実際に呼び出すときだけ import する。
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
# Tier name and version in a model ID
# モデル ID 内のティア名とバージョン
TAG_RE = re.compile(r"(opus|sonnet|haiku|fable)-(\d+)-(\d+)")
PRICES_PATH = Path(__file__).with_name("claude-prices.json")
LIMITS = (429, 529)  # rate limited, overloaded: stop at the first one / レート制限、過負荷：最初の 1 回で止まる


def model_tag(model: str) -> str:
    """Model ID → tier name plus version ("…-opus-5-5…" → "opus-5.5"). Replay keys, replay and ledger lines, and
    reports all use it, so model IDs stay out of the repo. If it cannot be recognized (no tier name, more than one tier
    name, or the tier name is not followed by two numbers), the model is not called.

    モデル ID → ティア名とバージョン（"…-opus-5-5…" → "opus-5.5"）。リプレイのキー、リプレイと台帳の行、レポートはすべて
    これを使い、モデル ID はリポジトリに入れない。判別できない場合（ティア名がない、ティア名が複数ある、ティア名の後に
    2 つの数字がない）は呼び出さない。
    """
    hits = TAG_RE.findall(model.lower())
    if len({h[0] for h in hits}) != 1:
        raise ValueError(
            f"Unrecognized model {model!r}: no tier name and version; not calling / "
            f"モデル {model!r} のティア名とバージョンを判別できないため、呼び出さない"
        )
    tier, major, minor = hits[0]
    return f"{tier}-{major}.{minor}"


def tier_of(model: str) -> str:
    """Model ID or tier name plus version → tier name ("sonnet-5.5" → "sonnet").

    モデル ID またはティア名とバージョン → ティア名（"sonnet-5.5" → "sonnet"）。
    """
    return model_tag(model.replace(".", "-")).split("-")[0]


def canonical(request: Json) -> str:
    """Normalize a request: sorted keys, non-ASCII not escaped, no extra whitespace.

    リクエストの正規化：キーをソートし、非 ASCII はエスケープせず、余分な空白を入れない。
    """
    return json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def replay_key(provider: str, model: str, version: str, request: Json) -> str:
    """The replay key. model: the model ID for Google, the tier name plus version for Claude.

    リプレイのキー。model：Google はモデル ID、Claude はティア名とバージョン。
    """
    return f"{provider}|{model}|{version}|{hashlib.sha256(canonical(request).encode()).hexdigest()}"


# —— Prices / 単価 ——


@dataclass(frozen=True)
class Price:
    input: float  # US dollars per million tokens / 100 万トークンあたりの米ドル
    output: float
    cache_read: float  # cache reads, different per tier / キャッシュ読み取り。ティアごとに異なる
    # How many times more tokens the same text counts as than in other tiers (Haiku about 1.3); used only for the
    # estimate before a call
    # 同じ文字列をほかのティアの何倍のトークンに数えるか（Haiku は約 1.3）。呼び出し前の見積もりにだけ使う
    tokenizer: float = 1.0


@dataclass(frozen=True)
class ClaudePrices:
    tiers: Mapping[str, Price]  # model tier (opus / sonnet / haiku / fable) → price / モデルのティア → 単価
    # Batch discount on both input and output (0.5 = half price)
    # Batch の入出力の割引（0.5 = 半額）
    batch_discount: float
    # Cache-write multiple of the input price (5-minute)
    # キャッシュ書き込みは入力単価の何倍か（5 分間）
    cache_write: float
    # For estimating input tokens: Japanese and Chinese are estimated at one token per character, on the high side
    # 入力トークンの見積もり用：日本語と中国語は 1 文字 1 トークンで見積もり、高めになる
    chars_per_token: float

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> ClaudePrices:
        tiers = {
            k: Price(float(v["input"]), float(v["output"]), float(v["cacheRead"]), float(v.get("tokenizer", 1.0)))
            for k, v in d["perMTok"].items()
        }
        return cls(tiers, float(d["batchDiscount"]), float(d["cacheWriteMultiplier"]), float(d["charsPerToken"]))

    def price(self, model: str) -> Price:
        """Match by tier: use whichever tier name the model ID or tier name plus version contains; if it cannot be
        recognized, do not call.

        ティアで照合する：モデル ID またはティア名とバージョンに含まれるティア名を使う。判別できなければ呼び出さない。
        """
        hits = [t for t in self.tiers if t in model.lower()]
        if len(hits) != 1:
            raise ValueError(
                f"Unrecognized model {model!r}: no price tier ({'/'.join(self.tiers)}); not calling / "
                f"モデル {model!r} の価格ティア（{'/'.join(self.tiers)}）を判別できないため、呼び出さない"
            )
        return self.tiers[hits[0]]

    def cost(self, model: str, usage: Mapping[str, int], *, batch: bool = False) -> float:
        """usage: inputTokens (input not served from the cache), cacheReadTokens, cacheWriteTokens, outputTokens
        (including thinking).

        usage：inputTokens（キャッシュを通らなかった入力）、cacheReadTokens、cacheWriteTokens、
        outputTokens（思考を含む）。
        """
        p = self.price(model)
        usd = (
            (usage.get("inputTokens", 0) + usage.get("cacheWriteTokens", 0) * self.cache_write) * p.input
            + usage.get("cacheReadTokens", 0) * p.cache_read
            + usage.get("outputTokens", 0) * p.output
        ) / 1_000_000
        return usd * (self.batch_discount if batch else 1.0)

    def estimate_chars(self, model: str, chars: int, max_output: int, *, batch: bool = False) -> float:
        """The estimate before a call (on the high side): input is estimated from the character count, ignoring the
        cache, times this tier's tokenizer multiple; output is taken at the cap (thinking also counts as output).

        呼び出し前の見積もり（高め）：入力は文字数から見積もり、キャッシュは考えず、このティアのトークナイザー倍率を
        掛ける。出力は上限で見積もる（思考も出力に数える）。
        """
        p = self.price(model)
        tokens = int(chars / self.chars_per_token * p.tokenizer) + 1
        return self.cost(model, {"inputTokens": tokens, "outputTokens": max_output}, batch=batch)

    def estimate(self, model: str, request: Mapping[str, Json], *, batch: bool) -> float:
        """The estimate for a judge request (system, user, schema, maxTokens).

        審査員のリクエスト（system、user、schema、maxTokens）の見積もり。
        """
        chars = len(request["system"]) + len(request["user"]) + len(canonical(request["schema"]))
        return self.estimate_chars(model, chars, int(request["maxTokens"]), batch=batch)


@cache
def claude_prices() -> ClaudePrices:
    return ClaudePrices.from_json(json.loads(PRICES_PATH.read_text(encoding="utf-8")))


# —— Talking to the API / API とのやりとり ——


@dataclass(frozen=True)
class Reply:
    # The first text block (structured output JSON); None if absent
    # 最初の text ブロック（構造化出力の JSON）。なければ None
    text: str | None
    stop_reason: str | None
    # inputTokens (not served from the cache), cacheReadTokens, cacheWriteTokens, outputTokens (including thinking),
    # thinkingTokens (the thinking part of those, for information only; not added again when computing cost)
    # inputTokens（キャッシュを通らなかったもの）、cacheReadTokens、cacheWriteTokens、outputTokens（思考を含む）、
    # thinkingTokens（そのうちの思考分。参考用で、費用計算では重ねて足さない）
    usage: dict[str, int]


def reply_of(msg: Any) -> Reply:
    """SDK Message → Reply (takes only the text and usage, not the thinking content).

    SDK の Message → Reply（テキストと使用量だけを取り、思考の内容は取らない）。
    """
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


# The API error type (`error.type`, e.g. authentication_error): contains no IDs or keys, and tells apart problems with
# the key, the request or the quota
# API エラーの種類（`error.type`、例 authentication_error）：ID もキーも含まず、キー、リクエスト、利用枠のどれの問題かを
# 見分けるのに使う
ERROR_TYPE = re.compile(r"[a-z_]{1,40}")


def error_type(e: BaseException) -> str:
    t = getattr(e, "type", None)
    return f" {t}" if isinstance(t, str) and ERROR_TYPE.fullmatch(t) else ""


# The original message is not recorded; only these words are used to recognize the category, and the hardcoded class
# name here is attached (not one word of the message gets out). Earlier entries are matched first
# 元のメッセージは記録しない。これらの語だけでどの種類かを見分け、ここに固定で書いた種類名を付ける（メッセージの文字は
# 一つも外に出さない）。先に書いたものから照合する
HINTS = (
    ("too complex", "schema-too-complex"),
    ("optional parameter", "too-many-optional"),
    ("union", "too-many-unions"),
    ("output_config", "output-config"),
    ("schema", "schema"),
    ("thinking", "thinking"),
    ("effort", "effort"),
    ("max_tokens", "max-tokens"),
    ("cache_control", "cache-control"),
    ("credit", "billing"),
    ("model", "model"),
)


def hint(e: BaseException) -> str:
    body = getattr(e, "body", None)
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return ""
    low = message.lower()
    return next((f"hint {tag}; " for word, tag in HINTS if word in low), "")


def translate(e: BaseException) -> Exception:
    """SDK error → an exception without the original message. Callers `raise translate(e) from None`, so the original
    message never reaches logs or the Trace.

    SDK のエラー → 元のメッセージを含まない例外。呼び出し側は `raise translate(e) from None` とし、元のメッセージは
    ログにも Trace にも入らない。
    """
    import anthropic

    if isinstance(e, anthropic.APIStatusError):
        if e.status_code in LIMITS:
            return RateLimited(
                f"Claude returned {e.status_code} (rate limited or overloaded); stopping / "
                f"Claude が {e.status_code} を返した（レート制限または過負荷）。停止する",
                provider="claude",
                status=e.status_code,
                retry_after=e.response.headers.get("retry-after"),
            )
        return ModelCallFailed(
            f"Claude HTTP {e.status_code}{error_type(e)} ({hint(e)}message not logged / メッセージは記録しない)"
        )
    if isinstance(e, anthropic.APIError):  # connection dropped, timeout / 接続切断、タイムアウト
        return ModelCallFailed(
            f"Claude unreachable / Claude に接続できない: {type(e).__name__} "
            "(message not logged / メッセージは記録しない)"
        )
    return ModelCallFailed(
        f"Claude call failed / Claude の呼び出しでエラー: {type(e).__name__} "
        "(message not logged / メッセージは記録しない)"
    )


# Debug logs of the SDK and its HTTP libraries carry the full request (prompt, the player's words, model ID) and the
# original error message: keep only WARNING and above
# SDK とその HTTP ライブラリのデバッグログにはリクエストの全文（プロンプト、プレイヤーの発話、モデル ID）とエラーの元の
# メッセージが含まれる：WARNING 以上だけを残す
QUIET = ("anthropic", "httpx", "httpx2", "httpcore")


def quiet() -> None:
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)


def client() -> Any:
    """The sync client (judge, Batch). The SDK reads the key from ANTHROPIC_API_KEY; it does not retry on its own.

    同期クライアント（審査員、Batch）。キーは SDK が ANTHROPIC_API_KEY から読み、自分では再試行しない。
    """
    import anthropic

    quiet()
    return anthropic.Anthropic(max_retries=0)


def async_client() -> Any:
    """The async client (narrator).

    非同期クライアント（ナレーター）。
    """
    import anthropic

    quiet()
    return anthropic.AsyncAnthropic(max_retries=0)


class AsyncTransport:
    """The narrator's transport layer: one Messages call. Tests swap in a fake and do not go online.

    ナレーター用のトランスポート層：Messages の呼び出し 1 回。テストでは偽物に差し替え、ネットワークに出ない。
    """

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
