"""Real text model: Claude on the Anthropic API (B-8, D-028; `ZJ_MODEL=real`, runs only on zg's Mac). Threads and CI
never call it.

- Uses zg's Anthropic API quota, not Claude on Vertex. The key is read only from the environment variable
  `ANTHROPIC_API_KEY` (on the Mac, read from the keychain into that one terminal), by the SDK itself; this code only
  checks whether it is set and never touches its value. Keys and model IDs never go into logs, the Trace, replays, the
  ledger or exception messages.
- **Model IDs stay out of the repo**: on the Mac they are given by `ZJ_CLAUDE_HAIKU`, `ZJ_CLAUDE_SONNET`
  (`config.CLAUDE_TIERS`), and a model is called only if the recognized tier name plus version matches what
  `config.TEXT` says (e.g. if the configuration says sonnet-5.5 and the given ID is recognized as sonnet-5.6, it is not
  called). Replays, the ledger and `check.checker` contain only the tier name plus version.
- Each call: the first system block holds the world model prefix and the second holds this prompt kind's instructions,
  with a cache breakpoint after each (the prefix is shared by all prompt kinds of the same tier, the instructions by
  every call of the same prompt kind); state, this turn and the request fields go into user (rendering reuses
  `models/render.py`). The output is fixed by `output_config.format` (JSON Schema), and thinking and effort follow
  `config.TEXT`. `temperature` is not passed: `messages.create` in Anthropic's Python SDK 1.13.0 has no such parameter,
  so output stability relies on the Schema and the thinking level.
- **Schema**: the copy sent to the API (`api_schema()`) drops keywords the API does not support (lengths, numeric
  ranges, `maxItems`), and every object gets `additionalProperties: false`; candidate events' `effects` are replaced by
  a per-op form (`API_EFFECT`), since otherwise only the `op` field would remain. The unions of the end-of-act plan are
  squeezed down to about the size of extraction's (`PLAN_EFFECT`, `PLAN_ALTERNATIVE_API`).
  On receipt, the output is still validated locally against the full Schema; if it fails, `BadOutput`, resent under
  the time-limit rules.
- Before a call, the ledger is checked against the estimated cost (`BudgetStop`); after a call, the actual usage is
  recorded (`provider: "claude"`, `use: "product"`); a call cancelled by the time limit is recorded at the estimate (it
  may already have been billed, so better to over-record). `refusal` and `max_tokens` also count as a failed call, and
  the cost is still recorded. Every line carries the duration and status (B-5: `ok`, `timeout`, `bad-output`; no
  response is recorded as `error` with cost 0).
- 429, 529 → `RateLimited` (runs on the Mac stop at the first one; when serving players, the narrator handles it under
  the time-limit rules, `Pipeline.on_rate_limit`); other HTTP errors → `ModelCallFailed`, status code only.

実テキストモデル：Anthropic API 上の Claude（B-8、D-028。`ZJ_MODEL=real`、zg の Mac 上でのみ実行）。スレッドと CI は
決して呼び出さない。

- zg の Anthropic API の利用枠を使い、Vertex 上の Claude は使わない。キーは環境変数 `ANTHROPIC_API_KEY` からだけ読み
  （Mac ではキーチェーンからその 1 つのターミナルに読み込む）、SDK 自身が読む。ここでは設定されているかだけを確認し、
  値には触れない。キーとモデル ID はログ、Trace、リプレイ、台帳、例外メッセージに入れない。
- **モデル ID はリポジトリに入れない**：Mac では `ZJ_CLAUDE_HAIKU`、`ZJ_CLAUDE_SONNET` で与え（`config.CLAUDE_TIERS`）、
  判別したティア名とバージョンが `config.TEXT` の記載と一致するときだけ呼び出す（例：設定が sonnet-5.5 で、与えた ID が
  sonnet-5.6 と判別されたら呼び出さない）。リプレイ、台帳、`check.checker` にはティア名とバージョンだけを書く。
- 呼び出しごとに：system の 1 つ目のブロックに世界モデルのプレフィックス、2 つ目にこのプロンプト種別の説明を置き、
  それぞれの後にキャッシュポイントを打つ（プレフィックスは同じティアの各プロンプトで共用、説明は同じプロンプト種別で
  共用）。状態、このターン、リクエストのフィールドは user に置く（レンダリングは `models/render.py` を流用）。出力は
  `output_config.format`（JSON Schema）で固定し、思考と effort は `config.TEXT` に従う。`temperature` は渡さない：
  Anthropic の Python SDK 1.13.0 の `messages.create` にはこのパラメータがなく、出力の安定性は Schema と思考のレベルに
  頼る。
- **Schema**：API に送るもの（`api_schema()`）からは API が対応しないキーワード（長さ、数値範囲、`maxItems`）を除き、
  オブジェクトはすべて `additionalProperties: false` にする。候補イベントの `effects` は op ごとに分けた書き方
  （`API_EFFECT`）に置き換える。そうしないと `op` フィールドしか残らない。幕末のプランのユニオン型は抽出と同程度まで
  減らす（`PLAN_EFFECT`、`PLAN_ALTERNATIVE_API`）。
  受け取った後は従来どおり完全な Schema でローカルに検証し、通らなければ `BadOutput` として時間制限の規則で再送する。
- 呼び出し前は見積もり費用で台帳を確認し（`BudgetStop`）、呼び出し後は実際の使用量で記録する（`provider: "claude"`、
  `use: "product"`）。時間制限で取り消されたものは見積もりで記録する（すでに課金されているかもしれないので、多めに
  記録する）。`refusal`、`max_tokens` もこの呼び出しの失敗とみなし、費用は記録する。各行に所要時間と状態を付ける
  （B-5：`ok`、`timeout`、`bad-output`。応答がないものは `error`、費用 0）。
- 429、529 → `RateLimited`（Mac 上の実行は最初の 1 回で止まる。プレイヤーに提供しているときは、ナレーターが時間制限の
  規則で扱う。`Pipeline.on_rate_limit`）。それ以外の HTTP エラー → `ModelCallFailed`、ステータスコードのみ。
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
from zoujin_backend.models.text import BadOutput, Refused, TextResult, model_and_version, spec
from zoujin_backend.world import Library

Json = Any

KEY_ENV = "ANTHROPIC_API_KEY"

# —— The Schema sent to the API / API に送る Schema ——

# Keywords the API does not support (per Anthropic's structured output docs, checked 2026-10-11): they stay in the full
# Schema used for local validation, which still catches violations
# API が対応しないキーワード（Anthropic の構造化出力の説明、2026-10-11 に確認）：ローカル検証用の完全な Schema には
# そのまま残しており、そこで止められる
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
MAX_OPTIONAL = 24  # parameters not in required, in total per request / required にないパラメータ、1 リクエストの合計
MAX_UNIONS = 16  # parameters using anyOf or type arrays, in total per request / anyOf か型の配列を使うパラメータの合計

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


# The contract's Effect (data/event.schema.json, 8 kinds by op) as written for the model: IDs are all strings (whether
# an ID is right is checked by step 3's rules and the contract), minus the three items the model should not write
# (EFFECT_DROPPED). Local validation still uses prompts.EFFECT (requires only op), and the contract is checked again
# before committing
# 契約の Effect（data/event.schema.json、op ごとに 8 種類）をモデル向けに書いたもの：ID はすべて文字列（ID が正しいかは
# 第 3 ステップの規則と契約が確認する）。モデルが書くべきでない 3 項目（EFFECT_DROPPED）を除く。ローカル検証は従来どおり
# prompts.EFFECT（op だけを要求）を使い、コミット前に改めて契約を通す
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
# In the contract but not in the form given to the model: set's from (the old value, unused by the narrator), beat's
# outcomes (the new results of altered, nested Effects; the API does not support recursion), improv's factId (assigned
# by the narrator, and also removed from the request)
# 契約にはあるが、モデル向けの書き方にはないもの：set の from（古い値。ナレーターは使わない）、beat の outcomes
# （altered の新しい結果で、入れ子の Effect。API は再帰に対応しない）、improv の factId（ナレーターが割り当てる。
# リクエストからも除いている）
EFFECT_DROPPED = {"set": {"from"}, "beat": {"outcomes"}, "improv": {"factId"}}
API_EFFECT: Json = {"anyOf": list(EFFECT_VARIANTS.values())}
# The end-of-act plan's Schema must be small: in the B-8 small test (10-11), extraction (4 unions) and rewrite (5)
# both passed, but the end-of-act plan originally had 10 (effects appeared twice, each with set's value and hold's to
# and from, and alternative was a choice of three), and the very first call returned 400 invalid_request_error. The
# docs say the compile cost of unions is exponential and exceeding an internal limit returns 400; the cause is a guess,
# and the hint carried by `translate()` will make it clear on a rerun. So effects only offers the kinds that contain no
# unions themselves (the prompt only asks for things like learn: no promises, and set and hold are not needed); whatever
# is written is still validated locally against the full Schema
# 幕末のプランの Schema は小さくする：B-8 の小テスト（10-11）では抽出（ユニオン型 4 個）と書き換え（5 個）は通ったが、
# 幕末のプランは元は 10 個あり（effects が 2 回現れ、それぞれに set の value、hold の to と from があり、alternative は
# 3 択だった）、最初の呼び出しで 400 invalid_request_error が返った。ドキュメントによればユニオン型のコンパイルコストは
# 指数的で、内部の上限を超えると 400 を返す。原因は推測で、再実行時に `translate()` が付けるヒントで明らかになる。
# そのため effects にはユニオン型を含まない種類だけを与える（プロンプトは learn のようなものだけを書かせる：約束は
# 書かず、set、hold も使わない）。書かれたものは従来どおりローカルの完全な Schema で検証する
PLAN_OPS = ("inc", "beat", "learn", "relocate", "improv")
PLAN_EFFECT: Json = {"anyOf": [EFFECT_VARIANTS[op] for op in PLAN_OPS]}
# alternative as sent to the API: the three local forms (a given destination {exit}, another plan {label, with,
# effects}, null) are merged into "one object whose fields are all optional, or null", removing one level of
# three-way choice. What is written is still validated locally against PLAN_ALTERNATIVE, and `plans.alternative()`
# tells them apart by whether exit or label is present
# API に送る alternative の書き方：ローカルの 3 種類（与えられた行き先 {exit}、別のプラン {label, with, effects}、
# null）を「フィールドがすべて省略可能な 1 つのオブジェクトか null」にまとめ、3 択を 1 段減らす。書かれたものは従来
# どおり PLAN_ALTERNATIVE でローカルに検証し、`plans.alternative()` は exit と label の有無で見分ける
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
    """The Schema sent to the API (local validation still uses `PROMPTS[kind].schema`). Computed once, then the same
    copy is shared (do not modify it).

    API に送る Schema（ローカル検証は引き続き `PROMPTS[kind].schema`）。1 回だけ計算し、以後は同じものを共用する
    （変更しないこと）。
    """
    return _api(PROMPTS[kind].schema, PLAN_EFFECT if kind == "plan" else API_EFFECT)


def schema_problems(schema: Json) -> list[str]:
    """Check the Schema sent to the API locally: no unsupported keywords, every object has additionalProperties:
    false, and the number of optional parameters and unions stays within the limits.

    API に送る Schema をローカルで確認する：対応しないキーワードがなく、オブジェクトはすべて additionalProperties:
    false で、省略可能なパラメータとユニオン型の数が上限を超えない。
    """
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
            problems.append(f"{path}: empty Schema / 空の Schema")
        for k in UNSUPPORTED:
            if k in node:
                problems.append(f"{path}: has {k} / {k} がある")
        if node.get("minItems", 0) > 1:
            problems.append(f"{path}: minItems must be 0 or 1 / minItems は 0 か 1 のみ")
        if "anyOf" in node or isinstance(node.get("type"), list):
            unions += 1
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is not False:
                problems.append(
                    f"{path}: object without additionalProperties: false / "
                    "オブジェクトに additionalProperties: false がない"
                )
            props = node.get("properties", {})
            optional += len(set(props) - set(node.get("required", [])))
            for name, sub in props.items():
                walk(sub, f"{path}.{name}")
        for k in ("items", "anyOf", "allOf"):
            if k in node:
                walk(node[k], f"{path}/{k}")

    walk(schema, "$")
    if optional > MAX_OPTIONAL:
        problems.append(
            f"{optional} optional parameters, over {MAX_OPTIONAL} / "
            f"省略可能なパラメータが {optional} 個で {MAX_OPTIONAL} を超える"
        )
    if unions > MAX_UNIONS:
        problems.append(f"{unions} unions, over {MAX_UNIONS} / ユニオン型が {unions} 個で {MAX_UNIONS} を超える")
    return problems


# —— Requests / リクエスト ——


def params(kind: str, request: Mapping[str, Any], prefix: str, model_id: str) -> Json:
    """The parameters of one Messages call. model_id appears only here and never goes into replays or the ledger.

    Messages の 1 回の呼び出しのパラメータ。model_id はここにだけ現れ、リプレイにも台帳にも入らない。
    """
    sp = spec(kind)
    cached = {"cache_control": {"type": "ephemeral"}}
    # Two cache breakpoints: the world model prefix (shared by all prompt kinds of the same tier), then this prompt
    # kind's instructions (shared by every call of the same prompt kind)
    # キャッシュポイントは 2 つ：世界モデルのプレフィックス（同じティアの各プロンプトで共用）と、
    # このプロンプト種別の説明（同じプロンプト種別の各呼び出しで共用）
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
    """The estimated cost before a call, on the high side: input by character count (times this tier's tokenizer
    multiple), ignoring the cache; output at the cap.

    呼び出し前の見積もり費用（高め）：入力は文字数（このティアのトークナイザー倍率を掛ける）で、キャッシュは考えず、
    出力は上限で見積もる。
    """
    chars = sum(len(b["text"]) for b in p["system"]) + len(p["messages"][0]["content"])
    chars += len(canonical(p["output_config"]["format"]["schema"]))
    return prices.estimate_chars(spec(kind).model, chars, int(p["max_tokens"]))


# —— Client / クライアント ——


class Transport(Protocol):
    async def create(self, params: Json) -> Reply: ...


@dataclass
class ClaudeText:
    transport: Transport
    ledger: Ledger
    worlds: Callable[[str], Json]  # worldModelVersion → world model / worldModelVersion → 世界モデル
    # Tier name (haiku, sonnet) → model ID (given by environment variables on the Mac)
    # ティア名（haiku、sonnet）→ モデル ID（Mac の環境変数で与えたもの）
    ids: Mapping[str, str]
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
            refused = got.stop_reason == "refusal"
            if got.stop_reason in ("refusal", "max_tokens"):
                bad = f"{kind}: Claude stopped at {got.stop_reason} / Claude が {got.stop_reason} で停止"
            else:
                try:
                    output = json.loads(got.text or "")
                    jsonschema.validate(output, PROMPTS[kind].schema)
                except (ValueError, jsonschema.ValidationError):
                    bad = f"{kind}: output is not JSON matching the Schema / 出力が Schema に合う JSON ではない"
            bill.done(got.usage, cost, ok=bad is None)
        # Safety screening treats it as harmful input (5.5, B-12); other prompts resend, like BadOutput
        # 安全審査は有害な入力として扱う（5.5、B-12）。それ以外のプロンプトは BadOutput と同じく再送する
        if refused:
            raise Refused(f"{kind}: Claude refused to answer / Claude が回答を拒否", cost)
        if bad is not None:
            raise BadOutput(bad, cost)
        return TextResult(output, kind, tag, version, dict(got.usage), cost)


def claude_ids(env: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """The model IDs given on the Mac: every tier used in the configuration must be given, and the recognized tier name
    plus version must match the configuration. Returns (tier → ID, problems). Problems name only the environment
    variable and the recognized tier name plus version, never the ID itself.

    Mac で与えたモデル ID：設定で使う各ティアについて与える必要があり、
    判別したティア名とバージョンは設定と一致しなければならない。（ティア → ID、問題）を返す。
    問題には環境変数の名前と判別したティア名とバージョンだけを書き、ID そのものは書かない。
    """
    want: dict[str, str] = {}
    problems: list[str] = []
    for kind in TEXT:
        s = spec(kind)
        if s.provider != "claude":
            continue
        tier = tier_of(s.model)
        if want.setdefault(tier, s.model) != s.model:
            problems.append(
                f"two versions configured for the same tier / 同じティアに 2 つのバージョンが設定されている: "
                f"{want[tier]}, {s.model}"
            )
    ids: dict[str, str] = {}
    for tier, tag in sorted(want.items()):
        name = CLAUDE_TIERS[tier]
        value = env.get(name, "")
        if not value:
            problems.append(f"{name} is not set / {name} が設定されていない")
            continue
        try:
            got = model_tag(value)
        except ValueError:
            problems.append(f"{name}: cannot recognize the tier name and version / ティア名とバージョンを判別できない")
            continue
        if got != tag:
            problems.append(
                f"{name} is recognized as {got}, but the configuration wants {tag} / "
                f"{name} は {got} と判別されたが、設定は {tag}"
            )
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
    """Build the real client from Settings and the Mac's environment variables. If anything is missing, exit without
    sending a request: the key, each tier's model ID, the ledger, Claude's total cap (ZJ_MAX_CLAUDE_USD, D-029, no
    default).

    Settings と Mac の環境変数から実クライアントを作る。1 つでも欠けていればリクエストを送らずに終了する：キー、
    各ティアのモデル ID、台帳、Claude の総上限（ZJ_MAX_CLAUDE_USD、D-029、デフォルト値なし）。
    """
    e = os.environ if env is None else env
    ids, problems = claude_ids(e)
    if not e.get(KEY_ENV):
        problems.insert(
            0,
            f"{KEY_ENV} is not set (on the Mac, read it from the keychain into this terminal's environment) / "
            f"{KEY_ENV} が設定されていない（Mac ではキーチェーンからこのターミナルの環境変数に読み込む）",
        )
    if ledger is None and (settings.ledger is None or settings.max_claude_usd is None):
        problems.append(
            "a ledger and Claude's total cap are required: ZJ_LEDGER, ZJ_MAX_CLAUDE_USD, with no defaults / "
            "台帳と Claude の総上限が必要：ZJ_LEDGER、ZJ_MAX_CLAUDE_USD。デフォルト値はない"
        )
    if problems:
        raise ConfigError(
            "ZJ_MODEL=real calling Claude / ZJ_MODEL=real で Claude を呼び出す: "
            + "; ".join(problems)
            + ". Not calling / 呼び出さない"
        )
    if ledger is None:
        assert settings.ledger is not None and settings.max_claude_usd is not None
        ledger = Ledger(settings.ledger, "claude", settings.max_claude_usd, settings.max_item_usd, settings.ledger_item)
    if transport is None:
        # Import the SDK only for real calls (optional dependency real)
        # 実際に呼び出すときだけ SDK を import する（オプション依存 real）
        from zoujin_llm.claude import AsyncTransport

        try:
            transport = AsyncTransport()
        except ImportError as err:  # pragma: no cover - only on the Mac / Mac 上のみ
            raise ConfigError(
                "ZJ_MODEL=real needs the optional dependency group real: uv sync --extra real / "
                "ZJ_MODEL=real にはオプション依存グループ real が必要：uv sync --extra real"
            ) from err
    library = Library(settings.worlds, settings.scenes, settings.world, settings.released_worlds)
    return ClaudeText(transport=transport, ledger=ledger, worlds=lambda v: library.version(v).world, ids=ids)
