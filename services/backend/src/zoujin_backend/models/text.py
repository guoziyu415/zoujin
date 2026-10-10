"""文本模型的接口和三种实现：假模型（`fake`）、回放（`replay`）、真模型（`real`，`models/vertex.py`，只在 Mac 上）。

- 假模型：每种提示一个确定的、过 Schema 的默认输出（分流 = 可能，提取 = 没有候选，检查 = 全过，改写 = 原样，
  降级 = 做不到，回答 = 一句固定的话）。`fixtures/fake-text/*.json` 的规则按提示类型和条件覆盖默认值，也能注入延迟和
  错误（测时限、重发和 429）。规则的写法见 `fixtures/fake-text/README.md`。
- 回放：按（模型、提示版本、规范化请求的 sha256）从 `fixtures/model-replays/*.jsonl` 查，查不到抛 `ReplayMissing`，
  不悄悄回空、不退回假模型。

回放一行的格式（Mac 上录真模型、E-0 的 live 存回放都用它）：
`key`、`kind`（提示类型）、`provider`、`model`、`promptVersion`、`request`（脱敏后）、`response`、`usage`
（`inputTokens`、`outputTokens`，真模型另有 `cachedTokens`、`thoughtTokens`）、`costUsd`、`recordedAt`（以 Z 结尾）。
`key` = `<model>|<promptVersion>|<请求的 sha256>`。
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from zoujin_backend.config import TEXT_MODELS, ModelMode
from zoujin_backend.models.prompts import MODEL_RULES, PROMPTS

if TYPE_CHECKING:
    from zoujin_backend.config import Settings

log = logging.getLogger("zoujin.models")

Json = Any

PROVIDER = "google"  # 产品路径的模型都是这一家（E-0 卡：回放带 provider）


class ReplayMissing(LookupError):
    """回放里查不到这次调用（回放缺失或过期）。E-0 按类名认。"""


class Stop(Exception):
    """要整次停下的错误（运行器不是跳过这一例，而是停下）：`BudgetStop`、`RateLimited`。"""


class BudgetStop(Stop):
    """账本到上限了（单项或总上限），这次调用没有发出去。"""


class RateLimited(Stop):
    """模型回 429（或同类的配额错误）。第一个就停，不自动重试（dev-plan 2.5）。"""


class BadOutput(ValueError):
    """模型的输出不是 JSON 或不过 Schema：算这次调用失败，按时限的规则重发一次。`cost_usd`：这次调用已经花的钱
    （真客户端拿到了回答才知道不合格，已经记了账；叙事者把它也加进这一轮的花费）。"""

    def __init__(self, message: str, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd


class ModelCallFailed(RuntimeError):
    """模型调用失败（HTTP 错误、网络断开），按时限的规则重发一次。消息只有 HTTP 状态码和提示类型，不带原消息
    （里面可能有项目 ID）。"""


@dataclass(frozen=True)
class TextResult:
    output: Json
    kind: str
    model: str
    prompt_version: str
    usage: dict[str, int]
    cost_usd: float


class TextModel(Protocol):
    mode: ModelMode

    async def call(self, kind: str, request: Json) -> TextResult: ...

    def cancelled_cost(self, kind: str, request: Json) -> float:
        """这次调用被时限取消时记多少钱（真客户端按调用前的预计，和账本那行同一个数；假模型、回放是 0）。"""
        ...


def canonical(request: Json) -> str:
    """规范化请求：键排序、不转义非 ASCII、没有多余空白。"""
    return json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def replay_key(model: str, prompt_version: str, request: Json) -> str:
    return f"{model}|{prompt_version}|{hashlib.sha256(canonical(request).encode()).hexdigest()}"


def model_and_version(kind: str) -> tuple[str, str]:
    if kind not in PROMPTS:
        raise ValueError(f"没有这种提示：{kind}")
    return TEXT_MODELS[kind], PROMPTS[kind].version


# —— 假模型 ——

NO_USAGE = {"inputTokens": 0, "outputTokens": 0}


def _check_all_pass(request: Mapping[str, Any]) -> Json:
    n = len(request.get("candidates", []))
    return {"results": [{"index": i, "rules": [{"rule": r, "status": "pass"} for r in MODEL_RULES]} for i in range(n)]}


def _rewrite_same(request: Mapping[str, Any]) -> Json:
    return {"candidate": copy.deepcopy(request.get("candidate")) if request.get("mode") == "rewrite" else None}


NARRATE_LINES = {  # 假模型的一行地の文：每种 status 一句（为测试写的）
    "done": "あなたは、そうした。",
    "partial": "思ったようには、いかなかった。",
    "refused": "それは、いまはかなわなかった。",
}

DEFAULTS: dict[str, Callable[[Mapping[str, Any]], Json]] = {
    "triage": lambda r: {"route": "maybe"},
    "extract": lambda r: {"candidates": []},  # 没有候选事件：只走时钟
    "check": _check_all_pass,
    "rewrite": _rewrite_same,  # 改写 = 原样；降级 = 做不到
    "reply": lambda r: {"text": "……そうか。"},
    "narrate": lambda r: {"text": NARRATE_LINES.get(str(r.get("status")), NARRATE_LINES["done"])},
    "plan": lambda r: {  # 不成行，替代去处是第一个给定去处（B-3 卡「接口」）
        "accepted": False,
        "label": None,
        "with": [],
        "effects": [],
        "narration": ["その道は、いまは開けていなかった。"],
        "alternative": {"exit": r["options"][0]["optionId"]} if r.get("options") else None,
    },
}
ERRORS = ("rate-limit", "invalid", "unavailable")


def _summaries(request: Mapping[str, Any]) -> list[str]:
    cands = request.get("candidates") or ([request["candidate"]] if request.get("candidate") else [])
    return [str(c.get("summary", "")) for c in cands]


def _matches(when: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    """fake-text 规则的条件，每个键都满足才算：`playerContains` / `replyContains` 看这一轮的原话里有没有这几个字，
    `summaryContains` 看候选的摘要，`character` 比这一轮的人物，其他键要等于请求里同名的值。"""
    turn = request.get("turn") or {}
    for k, v in when.items():
        if k == "playerContains":
            ok = v in (turn.get("player") or "")
        elif k == "replyContains":
            ok = v in (turn.get("reply") or "")
        elif k == "summaryContains":
            ok = any(v in s for s in _summaries(request))
        elif k == "character":
            ok = (turn.get("character") or request.get("character")) == v
        else:
            ok = request.get(k) == v
        if not ok:
            return False
    return True


class FakeText:
    mode: ModelMode = "fake"

    def __init__(self, rules_dir: Path | None = None, rules: list[Json] | None = None) -> None:
        self.rules: list[dict[str, Any]] = []
        self.used: dict[int, int] = {}  # 规则序号 → 用过几次（`times`）
        self.calls: list[tuple[str, Json]] = []  # 测试看调用了什么
        if rules_dir is not None and rules_dir.is_dir():
            for p in sorted(rules_dir.glob("*.json")):
                for r in json.loads(p.read_text(encoding="utf-8"))["rules"]:
                    self.rules.append(self._rule(r, p.name))
        for r in rules or []:
            self.rules.append(self._rule(r, "<test>"))

    @staticmethod
    def _rule(r: Json, source: str) -> dict[str, Any]:
        if r["kind"] not in DEFAULTS:
            raise ValueError(f"{source}：没有这种提示 {r['kind']}")
        if r.get("error") not in (None, *ERRORS):
            raise ValueError(f"{source}：不认识的 error {r['error']!r}（{' / '.join(ERRORS)}）")
        return {**r, "source": source}

    def _pick(self, kind: str, request: Json) -> dict[str, Any] | None:
        for i, r in enumerate(self.rules):
            if r["kind"] != kind or not _matches(r.get("when", {}), request):
                continue
            if "times" in r and self.used.get(i, 0) >= r["times"]:
                continue
            self.used[i] = self.used.get(i, 0) + 1
            return r
        return None

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = model_and_version(kind)
        self.calls.append((kind, copy.deepcopy(request)))
        rule = self._pick(kind, request)
        output = DEFAULTS[kind](request)
        if rule is not None:
            if rule.get("latencyMs"):
                await asyncio.sleep(rule["latencyMs"] / 1000)
            if rule.get("error") == "rate-limit":
                raise RateLimited(f"假模型：{kind} 回 429（{rule['source']}）")
            if rule.get("error") == "invalid":
                raise BadOutput(f"假模型：{kind} 的输出不过 Schema（{rule['source']}）")
            if rule.get("error") == "unavailable":
                raise ModelCallFailed(f"假模型：{kind} 调用失败（{rule['source']}）")
            if "output" in rule:
                output = copy.deepcopy(rule["output"])
            elif "fail" in rule and kind == "check":
                output = _check_failing(request, rule)
        return TextResult(output, kind, model, version, dict(NO_USAGE), 0.0)

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return 0.0


def _check_failing(request: Mapping[str, Any], rule: Mapping[str, Any]) -> Json:
    """`fail` 的简写：摘要含 `when.summaryContains` 的候选（没写就是全部）这条规则判 fail，其余全过。"""
    out = _check_all_pass(request)
    needle = rule.get("when", {}).get("summaryContains")
    for res, cand in zip(out["results"], request.get("candidates", []), strict=True):
        if needle is None or needle in str(cand.get("summary", "")):
            for row in res["rules"]:
                if row["rule"] == rule["fail"]["rule"]:
                    row["status"] = "fail"
                    row["reason"] = rule["fail"].get("reason", "モデル検査で不合格")
    return out


# —— 回放 ——


class ReplayText:
    mode: ModelMode = "replay"

    def __init__(self, replay_dir: Path) -> None:
        self.records: dict[str, Json] = {}
        for p in sorted(replay_dir.glob("*.jsonl")):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                rec = json.loads(line)
                want = replay_key(rec["model"], rec["promptVersion"], rec["request"])
                if rec["key"] != want:
                    raise ValueError(f"{p.name}:{n} 的 key 和内容对不上（应为 {want}）")
                self.records[rec["key"]] = rec

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = model_and_version(kind)
        key = replay_key(model, version, request)
        rec = self.records.get(key)
        if rec is None:
            raise ReplayMissing(f"回放缺失或过期：{kind}（{model}，提示 {version}）")
        return TextResult(
            copy.deepcopy(rec["response"]), kind, model, version, dict(rec["usage"]), float(rec["costUsd"])
        )

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return 0.0


def record(
    kind: str,
    request: Json,
    response: Json,
    *,
    recorded_at: str,
    usage: Mapping[str, int] | None = None,
    cost_usd: float = 0.0,
) -> Json:
    """一行回放（假模型录的 fixture、真模型录的回放都用它）。"""
    model, version = model_and_version(kind)
    return {
        "key": replay_key(model, version, request),
        "kind": kind,
        "provider": PROVIDER,
        "model": model,
        "promptVersion": version,
        "request": request,
        "response": response,
        "usage": dict(usage or NO_USAGE),
        "costUsd": cost_usd,
        "recordedAt": recorded_at,
    }


class Recording:
    """录回放（`ZJ_RECORD_REPLAYS=<目录>`）：每次成功的调用按回放格式在 `<目录>/<kind>.jsonl` 追加一行。
    Mac 上录真模型用；假模型也能录（测试回放这条路）。只录合成输入（S-2 的条目、评测用例），不录真人玩家的话。"""

    def __init__(self, inner: TextModel, directory: Path) -> None:
        self.inner = inner
        self.mode: ModelMode = inner.mode
        self.directory = directory

    async def call(self, kind: str, request: Json) -> TextResult:
        r = await self.inner.call(kind, request)
        line = record(kind, request, r.output, recorded_at=now_z(), usage=r.usage, cost_usd=r.cost_usd)
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / f"{kind}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
        return r

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return self.inner.cancelled_cost(kind, request)


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def text_model(
    mode: ModelMode, *, fake_rules: Path | None, replays: Path, settings: Settings | None = None
) -> TextModel:
    """settings 给了、设了 `record_replays`：fake 和 real 的调用录下来（replay 不录）。"""
    inner: TextModel
    if mode == "fake":
        inner = FakeText(fake_rules)
    elif mode == "replay":
        return ReplayText(replays)
    else:
        if settings is None:
            raise ValueError("ZJ_MODEL=real 要用 Settings 建客户端（账本、上限、录回放的目录）")
        from zoujin_backend.models.vertex import real_text  # 只在 real 时 import，别的模式不碰真客户端

        inner = real_text(settings)
    if settings is not None and settings.record_replays is not None:
        return Recording(inner, settings.record_replays)
    return inner
