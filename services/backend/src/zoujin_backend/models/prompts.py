"""文本模型的提示和输出的 JSON Schema（B-2，backend-design 2.4；Schema 是后端内部的，不进契约）。

每种提示一份系统指令（`prompt_texts/<kind>.txt`）和一个输出 Schema；版本号 = 两者一起的哈希，写进 Trace、回放的键和
`check.checker`。改了文本或 Schema，版本号就变，旧的回放查不到（`ReplayMissing`），要重新录。
提示里的例子都是为这里写的，不取自 S-2 的样例和留出集。

请求（`request`）是后端拼好的 JSON，回放按它算键；真客户端（`models/vertex.py`）把它排成模型的输入：世界模型前缀放最前
（同一版本内容不变，吃隐式缓存），玩家和人物的话只放在 `<utterance>` 数据字段里。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Json = Any

RULE_NAMES = ["R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"]
MODEL_RULES = ["R1-anchor", "R5-persona", "R6-safety"]  # 第 4 步判的规则


TEXTS = Path(__file__).parent / "prompt_texts"


def text(kind: str) -> str:
    """提示文本放在 `prompt_texts/<kind>.txt`（按段落写，不按行宽折行；评审直接看文件）。"""
    return (TEXTS / f"{kind}.txt").read_text(encoding="utf-8").rstrip("\n")


@dataclass(frozen=True)
class Prompt:
    kind: str
    text: str
    schema: Json = field(default_factory=dict)

    @property
    def version(self) -> str:
        body = self.text + "\n" + json.dumps(self.schema, sort_keys=True, ensure_ascii=False)
        return "p" + hashlib.sha256(body.encode()).hexdigest()[:12]


EFFECT = {
    "type": "object",
    "properties": {"op": {"enum": ["set", "inc", "beat", "learn", "relocate", "promise", "improv", "hold"]}},
    "required": ["op"],
}
CANDIDATE = {
    "type": "object",
    "properties": {
        "actor": {"type": "string", "minLength": 1},
        "type": {"enum": ["say", "action", "move", "learn"]},
        "origin": {"enum": ["turn", "action"]},
        "summary": {"type": "string", "minLength": 1},
        "causes": {"type": "array", "items": {"type": "string"}},
        "effects": {"type": "array", "items": EFFECT},
        "beneficiary": {"type": "string"},
        "needsConfirm": {"type": "boolean"},
    },
    "required": ["actor", "type", "summary", "effects", "needsConfirm"],
}

TRIAGE = Prompt(
    "triage",
    text("triage"),
    {
        "type": "object",
        "properties": {"route": {"enum": ["chat", "maybe"]}},
        "required": ["route"],
        "additionalProperties": False,
    },
)

EXTRACT = Prompt(
    "extract",
    text("extract"),
    {
        "type": "object",
        "properties": {"candidates": {"type": "array", "maxItems": 3, "items": CANDIDATE}},
        "required": ["candidates"],
    },
)

CHECK = Prompt(
    "check",
    text("check"),
    {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "minimum": 0},
                        "rules": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "rule": {"enum": MODEL_RULES},
                                    "status": {"enum": ["pass", "fail"]},
                                    "reason": {"type": "string"},
                                },
                                "required": ["rule", "status"],
                            },
                        },
                    },
                    "required": ["index", "rules"],
                },
            }
        },
        "required": ["results"],
    },
)

REWRITE = Prompt(
    "rewrite",
    text("rewrite"),
    {
        "type": "object",
        "properties": {"candidate": {"anyOf": [CANDIDATE, {"type": "null"}]}},
        "required": ["candidate"],
    },
)

REPLY = Prompt(
    "reply",
    text("reply"),
    {
        "type": "object",
        "properties": {"text": {"type": "string", "minLength": 1}},
        "required": ["text"],
        "additionalProperties": False,
    },
)

PROMPTS: dict[str, Prompt] = {p.kind: p for p in (TRIAGE, EXTRACT, CHECK, REWRITE, REPLY)}
