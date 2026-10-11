"""S-068 重测的两种判定走 Claude（D-028：评审员、S-068 修完复测的判分挪到 Claude；S-086）。

- 型号：Sonnet 5.5，自适应思考、effort low，结构化输出（`output_config.format`）。模型 ID 只从 Mac 的环境变量
  `ZJ_CLAUDE_SONNET` 读，认出来的档名加版本要是 sonnet-5.5 才调；结果、账本里只写档名加版本。
- Key 由 SDK 从 `ANTHROPIC_API_KEY` 读（Mac 上从钥匙串读进那一个终端），这里只查有没有设。
- 账：记 Claude 那本（`ZJ_CLAUDE_LEDGER`，Mac 上是 ~/.zoujin/ledger.jsonl，和叙事者、评审员同一个文件；
  spike 自己的 `ZJ_LEDGER` 记的是 Live 那本），`item` 是 s068-judge，`use` 是 eval。调用前按偏高的预计查总上限
  和单项上限，调用后按实际用量记。
- 这一个人物、这一个时刻的说明放 system 并打缓存点（同一个情景的几十次判定共用），玩家的话和人物的回答放 user。
- 429、529 → 整个跑停下（`common.QuotaHit`）；到上限 → `common.BudgetExceeded`；别的错误（400 之类）也停
  （`common.Stopped`），不然后面每一问都白开一次 Live。用 `--resume` 接着跑。
"""

from __future__ import annotations

import asyncio
import json
import os
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
TYPICAL_OUTPUT = 400  # 一次判定的输出（含思考）大约多少，只用来打印推算的花费
ENV = ("ANTHROPIC_API_KEY", "ZJ_CLAUDE_SONNET", "ZJ_CLAUDE_LEDGER")


def api_schema(schema: Any) -> Any:
    """发给 API 的 Schema：对象一律 additionalProperties: false（结构化输出的要求）。"""
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
    """推算的一次花费：同一段 system 第一次写缓存、之后读缓存（字数换 token 和账本一样偏高）；输出按 TYPICAL_OUTPUT。"""
    prices = claude_prices()
    p = prices.price(TAG)
    tokens = lambda chars: chars / prices.chars_per_token * p.tokenizer
    write = tokens(system_chars) * p.input * prices.cache_write
    read = tokens(system_chars) * p.cache_read * max(calls_per_system - 1, 0)
    per_call = (write + read) / max(calls_per_system, 1) + tokens(user_chars) * p.input + TYPICAL_OUTPUT * p.output
    return per_call / 1_000_000


def upper_usd(system_chars: int, user_chars: int, schema: Any) -> float:
    """偏高的预计（账本在调用前比的就是它）：不算缓存，输出按上限。"""
    chars = system_chars + user_chars + len(json.dumps(schema, ensure_ascii=False))
    return claude_prices().estimate_chars(TAG, chars, MAX_TOKENS)


class ClaudeJudge:
    def __init__(self, *, max_total_usd: float, max_item_usd: float, env: Mapping[str, str] | None = None) -> None:
        e = os.environ if env is None else env
        if missing(e):
            raise common.Stopped(f"Claude 的判定少环境变量：{'、'.join(missing(e))}")
        self.model_id = e["ZJ_CLAUDE_SONNET"]
        if model_tag(self.model_id) != TAG:
            raise common.Stopped(f"ZJ_CLAUDE_SONNET 认出来不是 {TAG}，不调")
        self.ledger = Ledger(Path(e["ZJ_CLAUDE_LEDGER"]).expanduser(), "claude", max_total_usd, max_item_usd, ITEM, "eval")
        self.transport = AsyncTransport()

    async def __call__(self, kind: str, system: str, user: str, schema: Any) -> dict:
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
            try:
                self.ledger.before(upper)
            except BudgetStop as exc:
                raise common.BudgetExceeded(str(exc)) from None
            try:
                reply = await asyncio.wait_for(self.transport.create(params), timeout=TIMEOUT_S)
            except TimeoutError:
                # 取消了的可能已经计费：按偏高的预计记，宁多记
                self.ledger.add(kind=kind, model=TAG, usage={}, cost=upper)
                if attempt == 2:
                    raise common.Stopped(f"Claude 的判定两次超过 {TIMEOUT_S:.0f} 秒") from None
                print(f"  （判定超过 {TIMEOUT_S:.0f} 秒，重试一次）")
                continue
            except RateLimited as exc:
                raise common.QuotaHit(str(exc)) from None
            except ModelCallFailed as exc:
                raise common.Stopped(str(exc)) from None
            self.ledger.add(kind=kind, model=TAG, usage=reply.usage, cost=claude_prices().cost(TAG, reply.usage))
            if reply.stop_reason != "end_turn" or reply.text is None:
                raise common.Stopped(f"Claude 的判定没有正常结束（{reply.stop_reason}）")
            return json.loads(reply.text)
        raise AssertionError("unreachable")
