"""真文本模型：Anthropic API 上的 Claude（B-8，D-028；`ZJ_MODEL=real`，只在 zg 的 Mac 上跑）。线程和 CI 从不调用。

- 走 zg 的 Anthropic API 额度，不走 Vertex 上的 Claude。Key 只从环境变量 `ANTHROPIC_API_KEY` 读（Mac 上从钥匙串读进
  那一个终端），由 SDK 自己读，这里只查有没有设，不碰它的值。Key、模型 ID 不进日志、Trace、回放、账本和异常消息。
- **模型 ID 不进仓库**：Mac 上用 `ZJ_CLAUDE_HAIKU`、`ZJ_CLAUDE_SONNET` 给（`config.CLAUDE_TIERS`），认出来的档名加版本
  要和 `config.TEXT` 里写的一样才调（例：配置写 sonnet-5.5，给的 ID 认出来是 sonnet-5.6 就不调）。回放、账本、
  `check.checker` 里只有档名加版本。
- 每次调用：system 第一段放世界模型前缀，第二段放这种提示的说明，两段后面各打一个缓存点（前缀同一档的各种提示共用，
  说明同一种提示共用）；状态、这一轮、请求字段放 user（渲染沿用
  `models/render.py`）。输出用 `output_config.format`（JSON Schema）定死，思考和 effort 按 `config.TEXT`。不传
  `temperature`：Anthropic 的 Python SDK 1.13.0 的 `messages.create` 没有这个参数，输出的稳不稳靠 Schema 和思考的档。
- **Schema**：发给 API 的那份（`api_schema()`）去掉 API 不支持的关键字（长度、数值范围、`maxItems`），对象一律
  `additionalProperties: false`；候选事件的 `effects` 换成按 op 分开的写法（`API_EFFECT`），不然只剩 `op` 一个字段。
  幕末打算的联合类型压到和提取差不多（`PLAN_EFFECT`、`PLAN_ALTERNATIVE_API`）。
  收到以后照旧用完整的 Schema 在本地验，不过就 `BadOutput`，按时限的规则重发。
- 调用前按预计花费查账本（`BudgetStop`），调用后按实际用量记账（`provider: "claude"`、`use: "product"`）；被时限
  取消的按预计记（可能已经计费，宁多记）。`refusal`、`max_tokens` 也算这次失败，钱照记。每行带耗时和状态（B-5：
  `ok`、`timeout`、`bad-output`；没有回应的记 `error`、花费 0）。
- 429、529 → `RateLimited`（Mac 上的跑第一个就停；服务玩家时叙事者按时限的规则处理，`Pipeline.on_rate_limit`）；
  别的 HTTP 错误 → `ModelCallFailed`，只有状态码。
"""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Protocol

import jsonschema
from zoujin_llm import ClaudePrices, Ledger, Reply, canonical, claude_prices, model_tag, tier_of

from zoujin_backend.config import CLAUDE_TIERS, TEXT, ConfigError, ModelMode, Settings
from zoujin_backend.models.prompts import EFFECT, PLAN_ALTERNATIVE, PROMPTS
from zoujin_backend.models.render import render_body, world_prefix
from zoujin_backend.models.text import BadOutput, TextResult, model_and_version, spec
from zoujin_backend.world import Library

Json = Any

KEY_ENV = "ANTHROPIC_API_KEY"

# —— 发给 API 的 Schema ——

# API 不支持的关键字（Anthropic 结构化输出的说明，2026-10-11 查的）：本地验的完整 Schema 里照样有，拦得住
UNSUPPORTED = (
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "maxItems",
    "uniqueItems",
)
MAX_OPTIONAL = 24  # 一个请求里不在 required 里的参数，合计
MAX_UNIONS = 16  # 一个请求里用 anyOf 或类型数组的参数，合计

_ID: Json = {"type": "string"}
_VALUE: Json = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "null"}]}
_WHO_OR_NONE: Json = {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _variant(op: str, props: Mapping[str, Json], required: list[str]) -> Json:
    return {
        "type": "object",
        "properties": {"op": {"const": op}, **props},
        "required": ["op", *required],
        "additionalProperties": False,
    }


# 契约的 Effect（data/event.schema.json，按 op 分 8 种）给模型的写法：ID 都是字符串（ID 对不对由第 3 步的规则和
# 契约查），去掉模型不该写的三项（EFFECT_DROPPED）。本地验照旧用 prompts.EFFECT（只要求 op），提交前再过契约
EFFECT_VARIANTS: dict[str, Json] = {
    "set": _variant("set", {"var": _ID, "value": _VALUE}, ["var", "value"]),
    "inc": _variant("inc", {"var": _ID, "by": {"type": "integer"}}, ["var", "by"]),
    "beat": _variant(
        "beat",
        {
            "beat": _ID,
            "to": {"enum": ["happened", "prevented", "delayed", "hastened", "altered"]},
            "minutes": {"type": "integer"},
            "note": {"type": "string"},
        },
        ["beat", "to"],
    ),
    "learn": _variant("learn", {"character": _ID, "fact": _ID}, ["character", "fact"]),
    "relocate": _variant("relocate", {"character": _ID, "place": _ID, "spot": _ID}, ["character", "place"]),
    "promise": _variant(
        "promise",
        {
            "promiseId": _ID,
            "change": {"enum": ["made", "kept", "broken", "voided"]},
            "from": _ID,
            "to": _ID,
            "text": {"type": "string"},
            "due": {
                "type": "object",
                "properties": {"t": {"type": "integer"}, "beat": _ID},
                "additionalProperties": False,
            },
            "template": _ID,
        },
        ["change"],
    ),
    "improv": _variant("improv", {"character": _ID, "statement": {"type": "string"}}, ["character", "statement"]),
    "hold": _variant("hold", {"item": _ID, "to": _WHO_OR_NONE, "from": _WHO_OR_NONE}, ["item", "to"]),
}
# 契约里有、给模型的写法里没有的：set 的 from（旧值，叙事者不用）、beat 的 outcomes（altered 的新结果，嵌套的 Effect，
# API 不支持递归）、improv 的 factId（叙事者分配，请求里也去掉了）
EFFECT_DROPPED = {"set": {"from"}, "beat": {"outcomes"}, "improv": {"factId"}}
API_EFFECT: Json = {"anyOf": list(EFFECT_VARIANTS.values())}
# 幕末打算的 Schema 要小：B-8 小测（10-11）里提取（4 个联合类型）、改写（5 个）都过了，幕末打算原来有 10 个
# （effects 出现两次，每次带 set 的 value、hold 的 to 和 from，alternative 又是三选一），第一次调用就回 400
# invalid_request_error。文档说联合类型的编译代价是指数的、超了内部的上限回 400；原因是推测的，补跑时 `translate()`
# 带的提示会说清。所以 effects 只给自己不带联合类型的几种（提示只让写 learn 这类：不写约定，也用不上 set、hold），
# 写了也照旧按本地的完整 Schema 验
PLAN_OPS = ("inc", "beat", "learn", "relocate", "improv")
PLAN_EFFECT: Json = {"anyOf": [EFFECT_VARIANTS[op] for op in PLAN_OPS]}
# alternative 发给 API 的写法：本地的三种（给定去处 {exit}、另一个打算 {label, with, effects}、null）并成「字段都
# 可选的一个对象或 null」，少一层三选一。写出来的照旧按 PLAN_ALTERNATIVE 在本地验，`plans.alternative()` 按有没有
# exit、label 认
PLAN_ALTERNATIVE_API: Json = {
    "anyOf": [
        {
            "type": "object",
            "properties": {
                "exit": _ID,
                "label": {"type": "string"},
                "with": {"type": "array", "items": _ID},
                "effects": {"type": "array", "items": PLAN_EFFECT},
            },
            "additionalProperties": False,
        },
        {"type": "null"},
    ]
}


def _api(node: Json, effect: Json) -> Json:
    if isinstance(node, list):
        return [_api(x, effect) for x in node]
    if not isinstance(node, dict):
        return node
    if node == EFFECT:
        return copy.deepcopy(effect)
    if node == PLAN_ALTERNATIVE:
        return copy.deepcopy(PLAN_ALTERNATIVE_API)
    out: dict[str, Json] = {}
    for k, v in node.items():
        if k in UNSUPPORTED:
            continue
        if k == "properties":
            out[k] = {name: _api(sub, effect) for name, sub in v.items()}
        elif k == "minItems":
            out[k] = min(int(v), 1)
        else:
            out[k] = _api(v, effect)
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


@cache
def api_schema(kind: str) -> Json:
    """发给 API 的那份 Schema（本地验的仍是 `PROMPTS[kind].schema`）。算一次，之后共用同一份（不要改它）。"""
    return _api(PROMPTS[kind].schema, PLAN_EFFECT if kind == "plan" else API_EFFECT)


def schema_problems(schema: Json) -> list[str]:
    """本地查发给 API 的 Schema：没有不支持的关键字，对象都是 additionalProperties: false，可选参数和联合类型不超数。"""
    problems: list[str] = []
    optional = unions = 0

    def walk(node: Json, path: str) -> None:
        nonlocal optional, unions
        if isinstance(node, list):
            for i, x in enumerate(node):
                walk(x, f"{path}[{i}]")
            return
        if not isinstance(node, dict):
            return
        if not node:
            problems.append(f"{path}：空的 Schema")
        for k in UNSUPPORTED:
            if k in node:
                problems.append(f"{path}：有 {k}")
        if node.get("minItems", 0) > 1:
            problems.append(f"{path}：minItems 只能是 0 或 1")
        if "anyOf" in node or isinstance(node.get("type"), list):
            unions += 1
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is not False:
                problems.append(f"{path}：对象没有 additionalProperties: false")
            props = node.get("properties", {})
            optional += len(set(props) - set(node.get("required", [])))
            for name, sub in props.items():
                walk(sub, f"{path}.{name}")
        for k in ("items", "anyOf", "allOf"):
            if k in node:
                walk(node[k], f"{path}/{k}")

    walk(schema, "$")
    if optional > MAX_OPTIONAL:
        problems.append(f"可选参数 {optional} 个，超过 {MAX_OPTIONAL}")
    if unions > MAX_UNIONS:
        problems.append(f"联合类型 {unions} 个，超过 {MAX_UNIONS}")
    return problems


# —— 请求 ——


def params(kind: str, request: Mapping[str, Any], prefix: str, model_id: str) -> Json:
    """一次 Messages 调用的参数。model_id 只在这里出现，不进回放和账本。"""
    sp = spec(kind)
    cached = {"cache_control": {"type": "ephemeral"}}
    # 两个缓存点：世界模型前缀（同一档的各种提示共用）、再加这种提示的说明（同一种提示的每次调用共用）
    system: list[Json] = [{"type": "text", "text": prefix, **cached}] if prefix else []
    system.append({"type": "text", "text": PROMPTS[kind].text, **cached})
    output: Json = {"format": {"type": "json_schema", "schema": api_schema(kind)}}
    if sp.effort:
        output["effort"] = sp.effort
    p: Json = {
        "model": model_id,
        "max_tokens": sp.max_output,
        "system": system,
        "messages": [{"role": "user", "content": render_body(kind, request) or "（入力なし）"}],
        "output_config": output,
    }
    if sp.thinking:
        p["thinking"] = {"type": sp.thinking}
    return p


def estimate_usd(prices: ClaudePrices, kind: str, p: Mapping[str, Any]) -> float:
    """调用前的预计花费，偏高：输入按字数（乘这一档的分词倍数）、不算缓存，输出按上限。"""
    chars = sum(len(b["text"]) for b in p["system"]) + len(p["messages"][0]["content"])
    chars += len(canonical(p["output_config"]["format"]["schema"]))
    return prices.estimate_chars(spec(kind).model, chars, int(p["max_tokens"]))


# —— 客户端 ——


class Transport(Protocol):
    async def create(self, params: Json) -> Reply: ...


@dataclass
class ClaudeText:
    transport: Transport
    ledger: Ledger
    worlds: Callable[[str], Json]  # worldModelVersion → 世界模型
    ids: Mapping[str, str]  # 档名（haiku、sonnet）→ 模型 ID（Mac 的环境变量给的）
    prices: ClaudePrices = field(default_factory=claude_prices)
    mode: ModelMode = "real"
    _prefix: dict[str, str] = field(default_factory=dict)

    def prefix(self, version: str | None) -> str:
        if version is None:
            return ""
        if version not in self._prefix:
            self._prefix[version] = world_prefix(self.worlds(version))
        return self._prefix[version]

    def params(self, kind: str, request: Json) -> Json:
        return params(kind, request, self.prefix(request.get("worldModelVersion")), self.ids[tier_of(spec(kind).model)])

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return estimate_usd(self.prices, kind, self.params(kind, request))

    async def call(self, kind: str, request: Json) -> TextResult:
        tag, version = model_and_version(kind)
        p = self.params(kind, request)
        guess = estimate_usd(self.prices, kind, p)
        with self.ledger.timed(kind=kind, model=tag, estimate=guess) as bill:
            got = await self.transport.create(p)
            cost = self.prices.cost(tag, got.usage)
            bad: str | None = None
            output: Json = None
            if got.stop_reason in ("refusal", "max_tokens"):
                bad = f"{kind}：Claude 停在 {got.stop_reason}"
            else:
                try:
                    output = json.loads(got.text or "")
                    jsonschema.validate(output, PROMPTS[kind].schema)
                except (ValueError, jsonschema.ValidationError):
                    bad = f"{kind} 的输出不是合 Schema 的 JSON"
            bill.done(got.usage, cost, ok=bad is None)
        if bad is not None:
            raise BadOutput(bad, cost)
        return TextResult(output, kind, tag, version, dict(got.usage), cost)


def claude_ids(env: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """Mac 上给的模型 ID：配置里用到的每一档都要给，认出来的档名加版本要和配置一样。返回（档 → ID，问题）。
    问题里只写环境变量的名字和认出来的档名加版本，不写 ID 本身。"""
    want: dict[str, str] = {}
    problems: list[str] = []
    for kind in TEXT:
        s = spec(kind)
        if s.provider != "claude":
            continue
        tier = tier_of(s.model)
        if want.setdefault(tier, s.model) != s.model:
            problems.append(f"同一档配了两个版本：{want[tier]}、{s.model}")
    ids: dict[str, str] = {}
    for tier, tag in sorted(want.items()):
        name = CLAUDE_TIERS[tier]
        value = env.get(name, "")
        if not value:
            problems.append(f"没设 {name}")
            continue
        try:
            got = model_tag(value)
        except ValueError:
            problems.append(f"{name} 认不出档名和版本")
            continue
        if got != tag:
            problems.append(f"{name} 认出来是 {got}，配置要的是 {tag}")
            continue
        ids[tier] = value
    return ids, problems


def claude_text(
    settings: Settings,
    *,
    ledger: Ledger | None = None,
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
) -> ClaudeText:
    """按 Settings 和 Mac 的环境变量建真客户端。少一样就退出，不发请求：Key、每一档的模型 ID、账本、Claude 的总上限
    （ZJ_MAX_CLAUDE_USD，D-029，没有默认值）。"""
    e = os.environ if env is None else env
    ids, problems = claude_ids(e)
    if not e.get(KEY_ENV):
        problems.insert(0, f"没设 {KEY_ENV}（Mac 上从钥匙串读进这个终端的环境变量）")
    if ledger is None and (settings.ledger is None or settings.max_claude_usd is None):
        problems.append("要账本和 Claude 的总上限：ZJ_LEDGER、ZJ_MAX_CLAUDE_USD，没有默认值")
    if problems:
        raise ConfigError("ZJ_MODEL=real 调 Claude：" + "；".join(problems) + "。不调用")
    if ledger is None:
        assert settings.ledger is not None and settings.max_claude_usd is not None
        ledger = Ledger(settings.ledger, "claude", settings.max_claude_usd, settings.max_item_usd, settings.ledger_item)
    if transport is None:
        from zoujin_llm.claude import AsyncTransport  # 只在真调时 import SDK（可选依赖 real）

        try:
            transport = AsyncTransport()
        except ImportError as err:  # pragma: no cover - 只在 Mac 上
            raise ConfigError("ZJ_MODEL=real 要可选依赖组 real：uv sync --extra real") from err
    library = Library(settings.worlds, settings.scenes, settings.world)
    return ClaudeText(transport=transport, ledger=ledger, worlds=lambda v: library.version(v).world, ids=ids)
