"""文本模型的提示和输出的 JSON Schema（B-2，backend-design 2.4；Schema 是后端内部的，不进契约）。

每种提示一份系统指令（`prompt_texts/<kind>.txt`）和一个输出 Schema；版本号 = 两者一起的哈希，写进 Trace、回放的键和
`check.checker`。改了文本或 Schema，版本号就变，旧的回放查不到（`ReplayMissing`），要重新录。
提示里的例子都是为这里写的，不取自 S-2 的样例和留出集。

请求（`request`）是后端拼好的 JSON，回放按它算键；真客户端（`models/vertex.py`）把它排成模型的输入：世界模型前缀放最前
（同一版本内容不变，吃隐式缓存），玩家和人物的话只放在 `<utterance>` 数据字段里。
"""

from __future__ import annotations

import copy
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
CANDIDATE: Json = {
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

# B-4：要确认的候选多两项（人物这一轮是不是已经在反问、反问的一句）；有反问在等回答时多判一项 confirmAnswer
EXTRACT_CANDIDATE: Json = copy.deepcopy(CANDIDATE)
EXTRACT_CANDIDATE["properties"] |= {"asked": {"type": "boolean"}, "question": {"type": "string"}}

EXTRACT = Prompt(
    "extract",
    text("extract"),
    {
        "type": "object",
        "properties": {
            "candidates": {"type": "array", "maxItems": 3, "items": EXTRACT_CANDIDATE},
            "confirmAnswer": {"enum": ["yes", "no", None]},
        },
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

# B-3：动作的一行地の文（status 按判定），幕末说出的打算能不能成行
NARRATE = Prompt(
    "narrate",
    text("narrate"),
    {
        "type": "object",
        "properties": {"text": {"type": "string", "minLength": 1}},
        "required": ["text"],
        "additionalProperties": False,
    },
)

PLAN_ALTERNATIVE = {
    "anyOf": [
        {"type": "object", "properties": {"exit": {"type": "string", "minLength": 1}}, "required": ["exit"]},
        {
            "type": "object",
            "properties": {
                "label": {"type": "string", "minLength": 1},
                "with": {"type": "array", "items": {"type": "string"}},
                "effects": {"type": "array", "items": EFFECT},
            },
            "required": ["label"],
        },
        {"type": "null"},
    ]
}

PLAN = Prompt(
    "plan",
    text("plan"),
    {
        "type": "object",
        "properties": {
            "accepted": {"type": "boolean"},
            "label": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]},
            "with": {"type": "array", "items": {"type": "string"}},
            "effects": {"type": "array", "items": EFFECT},
            "narration": {"type": "array", "maxItems": 2, "items": {"type": "string", "minLength": 1}},
            "alternative": PLAN_ALTERNATIVE,
        },
        "required": ["accepted", "label", "with", "effects", "narration", "alternative"],
    },
)

# B-12：玩家每一句的安全筛查（backend-design 5.5，S-072）。判定规则是 spike 的 CLASSIFY_PROMPT_V2，字不改；
# 只把「発話：{text}」换成 <utterance> 数据字段，输出用 Schema 定死。不带世界模型前缀
SAFETY = Prompt(
    "safety",
    text("safety"),
    {
        "type": "object",
        "properties": {
            "selfHarm": {"enum": ["signal", "ambiguous", "none"]},
            "injection": {"type": "boolean"},
        },
        "required": ["selfHarm", "injection"],
        "additionalProperties": False,
    },
)

# B-9：切片的简化结局（三层，每句引用这一局的事件；条数、字数、引用由 `narrator/ending.py` 的校验管，这里只管形状）
CITED = {
    "type": "object",
    "properties": {
        "sentence": {"type": "string", "minLength": 1},
        "cites": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sentence", "cites"],
    "additionalProperties": False,
}
CITED_TEXT = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "minLength": 1},
        "cites": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "cites"],
    "additionalProperties": False,
}
ENDING = Prompt(
    "ending",
    text("ending"),
    {
        "type": "object",
        "properties": {
            "epilogue": {"type": "array", "items": CITED},
            "contrast": {
                "type": "object",
                "properties": {
                    "original": {"type": "string", "minLength": 1},
                    "yours": {"type": "string", "minLength": 1},
                    "beat": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]},
                },
                "required": ["original", "yours", "beat"],
                "additionalProperties": False,
            },
            "subtitle": {"type": "string", "minLength": 1},
            "cardContrast": {"type": "string", "minLength": 1},
            "you": {
                "type": "object",
                "properties": {
                    "title": CITED_TEXT,
                    "fate": CITED_TEXT,
                    "didForYou": {"type": "array", "items": CITED},
                    "youDid": {"type": "array", "items": CITED},
                },
                "required": ["title", "fate", "didForYou", "youDid"],
                "additionalProperties": False,
            },
            "characters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string", "minLength": 1},
                        "yours": {"type": "array", "items": CITED},
                    },
                    "required": ["character", "yours"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["epilogue", "contrast", "subtitle", "cardContrast", "you", "characters"],
        "additionalProperties": False,
    },
)

# B-13：人物视角的一句记忆（只读事件的摘要和结果，不读原话；长度、个人信息、命令句由 `narrator/memory.py` 再过滤），
# 和记憶帳删除确认里「不会撤销的后果」一句（没有就是 null）
# B-15（S-072 ⑤）：第一遍判 signal 时带上下文复核，story = true 才降成 ambiguous
SAFETY_REVIEW = Prompt(
    "safety_review",
    text("safety_review"),
    {
        "type": "object",
        "properties": {"story": {"type": "boolean"}},
        "required": ["story"],
        "additionalProperties": False,
    },
)
MEMORY = Prompt(
    "memory",
    text("memory"),
    {
        "type": "object",
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "weight": {"type": "integer", "minimum": 1, "maximum": 3},
        },
        "required": ["text", "weight"],
        "additionalProperties": False,
    },
)
KEEPS = Prompt(
    "keeps",
    text("keeps"),
    {
        "type": "object",
        "properties": {"keeps": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]}},
        "required": ["keeps"],
        "additionalProperties": False,
    },
)

PROMPTS: dict[str, Prompt] = {
    p.kind: p
    for p in (TRIAGE, EXTRACT, CHECK, REWRITE, REPLY, NARRATE, PLAN, ENDING, SAFETY, SAFETY_REVIEW, MEMORY, KEEPS)
}
