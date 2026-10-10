"""文本模型的接口和两种实现（B-0 第 6 条）：假模型（`fake`）和回放（`replay`）。真模型不在这里。

- 假模型：每种提示一个确定的、过 Schema 的默认输出，对任何请求都有回答。`fixtures/fake-text/*.json` 里的规则按
  提示类型和简单条件覆盖默认值，剧本要的特定输出放那里。
- 回放：按（模型、提示版本、规范化请求的 sha256）从 `fixtures/model-replays/*.jsonl` 查，查不到抛 `ReplayMissing`，
  不悄悄回空、不退回假模型。

回放一行的格式（以后在 Mac 上录真模型、E-0 的 live 存回放都用它）：
`key`、`kind`（提示类型）、`provider`、`model`、`promptVersion`、`request`（脱敏后）、`response`、`usage`
（`inputTokens`、`outputTokens`）、`costUsd`、`recordedAt`（以 Z 结尾）。
`key` = `<model>|<promptVersion>|<请求的 sha256>`。
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from zoujin_backend.config import TEXT_MODELS, ModelMode
from zoujin_backend.models.prompts import PROMPTS

log = logging.getLogger("zoujin.models")

Json = Any

PROVIDER = "google"  # 产品路径的模型都是这一家（E-0 卡：回放带 provider）


class ReplayMissing(LookupError):
    """回放里查不到这次调用（回放缺失或过期）。E-0 按类名认。"""


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


def canonical(request: Json) -> str:
    """规范化请求：键排序、不转义非 ASCII、没有多余空白。"""
    return json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def replay_key(model: str, prompt_version: str, request: Json) -> str:
    return f"{model}|{prompt_version}|{hashlib.sha256(canonical(request).encode()).hexdigest()}"


def _model_and_version(kind: str) -> tuple[str, str]:
    if kind not in PROMPTS:
        raise ValueError(f"没有这种提示：{kind}")
    return TEXT_MODELS[kind], PROMPTS[kind].version


# —— 假模型 ——

DEFAULTS: dict[str, Json] = {
    "extract": {"candidates": []},  # 没有候选事件：只走时钟
    "reply": {"text": "……そうか。"},
}

NO_USAGE = {"inputTokens": 0, "outputTokens": 0}


def _matches(when: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    """fake-text 规则的条件，每个键都满足才算：`playerContains` 看玩家的话里有没有这几个字，
    其他键要等于请求里同名的值。"""
    for k, v in when.items():
        if k == "playerContains":
            if v not in (request.get("player") or ""):
                return False
        elif request.get(k) != v:
            return False
    return True


class FakeText:
    mode: ModelMode = "fake"

    def __init__(self, rules_dir: Path | None) -> None:
        self.rules: list[dict[str, Any]] = []
        if rules_dir is not None and rules_dir.is_dir():
            for p in sorted(rules_dir.glob("*.json")):
                doc = json.loads(p.read_text(encoding="utf-8"))
                for r in doc["rules"]:
                    if r["kind"] not in DEFAULTS:
                        raise ValueError(f"{p.name}：没有这种提示 {r['kind']}")
                    self.rules.append({**r, "source": p.name})

    async def call(self, kind: str, request: Json) -> TextResult:
        model, version = _model_and_version(kind)
        output = DEFAULTS[kind]
        for r in self.rules:
            if r["kind"] == kind and _matches(r.get("when", {}), request):
                output = r["output"]
                break
        return TextResult(copy.deepcopy(output), kind, model, version, dict(NO_USAGE), 0.0)


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
        model, version = _model_and_version(kind)
        key = replay_key(model, version, request)
        rec = self.records.get(key)
        if rec is None:
            raise ReplayMissing(f"回放缺失或过期：{kind}（{model}，提示 {version}）")
        return TextResult(
            copy.deepcopy(rec["response"]), kind, model, version, dict(rec["usage"]), float(rec["costUsd"])
        )


def record(kind: str, request: Json, response: Json, *, recorded_at: str, cost_usd: float = 0.0) -> Json:
    """一行回放（测试和 fixture 用；真模型的录制在 M2）。"""
    model, version = _model_and_version(kind)
    return {
        "key": replay_key(model, version, request),
        "kind": kind,
        "provider": PROVIDER,
        "model": model,
        "promptVersion": version,
        "request": request,
        "response": response,
        "usage": dict(NO_USAGE),
        "costUsd": cost_usd,
        "recordedAt": recorded_at,
    }


def text_model(mode: ModelMode, *, fake_rules: Path | None, replays: Path) -> TextModel:
    if mode == "fake":
        return FakeText(fake_rules)
    return ReplayText(replays)
