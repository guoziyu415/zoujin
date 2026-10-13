"""The two judgments in the S-068 retest go through Claude (D-028: the judge and the scoring of the post-fix S-068
retest move to Claude; S-086).

- Model: Sonnet 5.5, adaptive thinking, effort low, structured output (`output_config.format`). The model ID is read
  only from the Mac's environment variable `ZJ_CLAUDE_SONNET`, and it is called only if the recognized tier plus
  version is sonnet-5.5; results and the ledger record only the tier plus version.
- The key is read by the SDK from `ANTHROPIC_API_KEY` (on the Mac, read from the keychain into that one terminal);
  here we only check that it is set.
- Spend: recorded in the Claude ledger (`ZJ_CLAUDE_LEDGER`, on the Mac ~/.zoujin/ledger.jsonl, the same file as the
  narrator and the judge; the spike's own `ZJ_LEDGER` is the Live ledger), with `item` s068-judge and `use` eval.
  Before a call the total cap and per-item cap are checked against a high estimate; after the call the actual usage
  is recorded.
- The description of this one character at this one moment goes in system with a cache breakpoint (shared by the
  dozens of judgments of one scenario); the player's words and the character's answer go in user.
- 429, 529 → the whole run stops (`common.QuotaHit`); cap reached → `common.BudgetExceeded`; other errors (400 and
  the like) also stop it (`common.Stopped`), otherwise every later question would open a Live session for nothing.
  Continue with `--resume`.

S-068 再テストの 2 種類の判定は Claude で行う（D-028：審査員と、S-068 修正後の再テストの採点を Claude に移す。S-086）。

- モデル：Sonnet 5.5、適応型思考、effort low、構造化出力（`output_config.format`）。モデル ID は Mac の環境変数
  `ZJ_CLAUDE_SONNET` からのみ読み、認識したティア名＋バージョンが sonnet-5.5 のときだけ呼ぶ。結果と台帳には
  ティア名＋バージョンだけを書く。
- キーは SDK が `ANTHROPIC_API_KEY` から読む（Mac ではキーチェーンからその端末にだけ読み込む）。ここでは設定の有無だけ確認する。
- 費用：Claude の台帳（`ZJ_CLAUDE_LEDGER`、Mac では ~/.zoujin/ledger.jsonl、ナレーター・審査員と同じファイル。
  spike 自身の `ZJ_LEDGER` は Live の台帳）に記録し、`item` は s068-judge、`use` は eval。呼び出し前に高めの見積もりで
  総上限と項目別上限を確認し、呼び出し後に実際の使用量で記録する。
- この登場人物のこの時点の説明は system に置いてキャッシュポイントを付け（同じシナリオの数十回の判定で共有）、
  プレイヤーの発話と登場人物の返答は user に置く。
- 429、529 → 実行全体を止める（`common.QuotaHit`）。上限到達 → `common.BudgetExceeded`。その他のエラー（400 など）でも
  止める（`common.Stopped`）。止めないと以降の問いごとに Live を無駄に開くことになる。`--resume` で続きから実行する。
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from zoujin_llm import BudgetStop, Ledger, ModelCallFailed, RateLimited, claude_prices, model_tag
from zoujin_llm.claude import AsyncTransport

from . import common

TAG = "sonnet-5.5"
ITEM = "s068-judge"
MAX_TOKENS = 2048
TIMEOUT_S = 90.0
# Rough output size of one judgment (thinking included); only used to print the projected cost
# 1 回の判定の出力（思考を含む）のおおよその量。見積もり費用の表示にだけ使う
TYPICAL_OUTPUT = 400
ENV = ("ANTHROPIC_API_KEY", "ZJ_CLAUDE_SONNET", "ZJ_CLAUDE_LEDGER")


def api_schema(schema: Any) -> Any:
    """Schema sent to the API: every object gets additionalProperties: false (required by structured output).

    API に送る Schema：オブジェクトにはすべて additionalProperties: false を付ける（構造化出力の要件）。
    """
    if isinstance(schema, list):
        return [api_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: api_schema(v) for k, v in schema.items()}
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def missing(env: Mapping[str, str]) -> list[str]:
    return [k for k in ENV if not env.get(k)]


def likely_usd(system_chars: int, user_chars: int, calls_per_system: int) -> float:
    """Projected cost of one call: the same system text writes the cache the first time and reads it afterwards
    (characters are converted to tokens on the high side, as in the ledger); output is taken as TYPICAL_OUTPUT.

    1 回あたりの見積もり費用：同じ system は初回にキャッシュを書き、以降は読む（文字数からトークンへの換算は台帳と同じく
    高め）。出力は TYPICAL_OUTPUT で見積もる。
    """
    prices = claude_prices()
    p = prices.price(TAG)
    tokens = lambda chars: chars / prices.chars_per_token * p.tokenizer
    write = tokens(system_chars) * p.input * prices.cache_write
    read = tokens(system_chars) * p.cache_read * max(calls_per_system - 1, 0)
    per_call = (write + read) / max(calls_per_system, 1) + tokens(user_chars) * p.input + TYPICAL_OUTPUT * p.output
    return per_call / 1_000_000


def upper_usd(system_chars: int, user_chars: int, schema: Any) -> float:
    """High estimate (what the ledger compares against before a call): no caching, output at the maximum.

    高めの見積もり（呼び出し前に台帳が比較するのはこの値）：キャッシュは考慮せず、出力は上限で計算する。
    """
    chars = system_chars + user_chars + len(json.dumps(schema, ensure_ascii=False))
    return claude_prices().estimate_chars(TAG, chars, MAX_TOKENS)


class ClaudeJudge:
    def __init__(self, *, max_total_usd: float, max_item_usd: float, env: Mapping[str, str] | None = None) -> None:
        e = os.environ if env is None else env
        if missing(e):
            raise common.Stopped(
                f"Claude judging is missing environment variables / Claude の判定に必要な環境変数がありません: "
                f"{', '.join(missing(e))}"
            )
        self.model_id = e["ZJ_CLAUDE_SONNET"]
        if model_tag(self.model_id) != TAG:
            raise common.Stopped(
                f"ZJ_CLAUDE_SONNET is not recognized as {TAG}; not calling / "
                f"ZJ_CLAUDE_SONNET が {TAG} と認識されないため呼び出しません"
            )
        self.ledger = Ledger(Path(e["ZJ_CLAUDE_LEDGER"]).expanduser(), "claude", max_total_usd, max_item_usd, ITEM, "eval")
        self.transport = AsyncTransport()

    async def __call__(
        self, kind: str, system: str, user: str, schema: Any, *, attempts: list[dict] | None = None
    ) -> dict:
        api = api_schema(schema)
        params = {
            "model": self.model_id,
            "max_tokens": MAX_TOKENS,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": api}},
        }
        upper = upper_usd(len(system), len(user), api)
        for attempt in (1, 2):
            began = time.perf_counter()
            diagnostic = {"stage": kind, "attempt": attempt}
            try:
                with self.ledger.timed(kind=kind, model=TAG, estimate=upper) as bill:
                    reply = await asyncio.wait_for(self.transport.create(params), timeout=TIMEOUT_S)
                    usable = reply.stop_reason == "end_turn" and reply.text is not None
                    try:
                        result = json.loads(reply.text) if usable else None
                    except (ValueError, TypeError):
                        bill.done(reply.usage, claude_prices().cost(TAG, reply.usage), ok=False)
                        raise
                    bill.done(reply.usage, claude_prices().cost(TAG, reply.usage), ok=usable)
                    if not usable:
                        raise common.Stopped(
                            f"Claude judgment did not end normally / Claude の判定が正常に終了しませんでした ({reply.stop_reason})"
                        )
            except BudgetStop as exc:
                diagnostic.update(status="budget-stop", errorType=type(exc).__name__)
                raise common.BudgetExceeded(str(exc)) from None
            except TimeoutError as exc:
                diagnostic.update(status="timeout", errorType=type(exc).__name__)
                if attempt == 2:
                    raise common.Stopped(
                        f"Claude judgment took over {TIMEOUT_S:.0f} s twice / Claude の判定が 2 回とも {TIMEOUT_S:.0f} 秒を超えました"
                    ) from None
                print(f"  (judgment took over {TIMEOUT_S:.0f} s, retrying once / 判定が {TIMEOUT_S:.0f} 秒を超えたので 1 回再試行)")
                continue
            except RateLimited as exc:
                diagnostic.update(status="error", errorType=type(exc).__name__)
                raise common.QuotaHit(str(exc)) from None
            except ModelCallFailed as exc:
                diagnostic.update(status="error", errorType=type(exc).__name__)
                raise common.Stopped(str(exc)) from None
            except Exception as exc:
                diagnostic.update(status="bad-output", errorType=type(exc).__name__)
                raise
            else:
                diagnostic["status"] = "ok"
                return result
            finally:
                diagnostic["ms"] = round((time.perf_counter() - began) * 1000)
                if attempts is not None:
                    attempts.append(diagnostic)
        raise AssertionError("unreachable")
