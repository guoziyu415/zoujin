"""Prompts and output JSON Schemas for the text model (B-2, backend-design 2.4; the Schemas are internal to the backend
and are not part of the contract).

Each prompt kind has one system instruction (`prompt_texts/<kind>.txt`) and one output Schema; the version = a hash of
the two together, written into the Trace, the replay keys and `check.checker`. Changing the text or the Schema changes
the version, so old replays are no longer found (`ReplayMissing`) and must be re-recorded.
The examples in the prompts were all written for this purpose and are not taken from the S-2 samples or the holdout set.

The request (`request`) is JSON assembled by the backend, and replays compute their key from it; the real client
(`models/vertex.py`) arranges it into the model's input: the world model prefix goes first (its content does not change
within a version, so it benefits from implicit caching), and the words of the player and characters go only into
`<utterance>` data fields.

テキストモデルのプロンプトと出力の JSON Schema（B-2、backend-design 2.4。Schema はバックエンド内部のもので、契約には
入らない）。

プロンプトの種類ごとにシステム指示（`prompt_texts/<kind>.txt`）と出力 Schema が 1 つずつあり、バージョン = 両者を
合わせたハッシュで、Trace、リプレイのキー、`check.checker` に書き込まれる。テキストか Schema を変えるとバージョンが
変わり、古いリプレイは見つからなくなる（`ReplayMissing`）ので、録り直す必要がある。
プロンプト内の例はすべてここのために書いたもので、S-2 のサンプルやホールドアウトセットからは取っていない。

リクエスト（`request`）はバックエンドが組み立てた JSON で、リプレイはそれからキーを計算する。実クライアント
（`models/vertex.py`）はそれをモデルの入力に並べる：世界モデルのプレフィックスを先頭に置き（同じバージョン内では内容が
変わらないので暗黙キャッシュが効く）、プレイヤーと登場人物の発言は `<utterance>` データフィールドにだけ入れる。
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
MODEL_RULES = ["R1-anchor", "R5-persona", "R6-safety"]  # rules judged in step 4 / 第 4 ステップで判定する規則


TEXTS = Path(__file__).parent / "prompt_texts"


def text(kind: str) -> str:
    """Prompt texts live in `prompt_texts/<kind>.txt` (written by paragraph, not wrapped to a line width; reviewers read
    the files directly).

    プロンプトのテキストは `prompt_texts/<kind>.txt` に置く（段落ごとに書き、行幅で折り返さない。レビュアーはファイルを
    直接読む）。
    """
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

# B-4: candidates that need confirmation get two more fields (whether the character is already asking back in this
# turn, and the line asking back); while a question asked back awaits an answer, confirmAnswer is also judged
# B-4：確認が必要な候補には 2 項目が増える（登場人物がこのターンですでに聞き返しているか、聞き返しの一文）。
# 聞き返しが回答待ちのときは confirmAnswer も判定する
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

# B-3: one line of 地の文 for an action (status per the judgment), and whether a plan stated at the end of an act can go
# ahead
# B-3：アクションの地の文 1 行（status は判定どおり）、幕末に語ったプランが実行できるか
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

# B-12: safety screening of every player line (backend-design 5.5, S-072). The judging rules are the spike's
# CLASSIFY_PROMPT_V2, word for word; only 「発話：{text}」 is replaced with the <utterance> data field, and the output
# is fixed by the Schema. No world model prefix
# B-12：プレイヤーの発言ごとの安全審査（backend-design 5.5、S-072）。判定規則は spike の CLASSIFY_PROMPT_V2 で、一字も
# 変えない。「発話：{text}」を <utterance> データフィールドに置き換え、出力を Schema で固定しただけ。世界モデルの
# プレフィックスは付けない
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

# B-9 / B-17: the three-layer ending (each sentence cites events from this playthrough; the counts, lengths, citations
# and claims are checked by the validation in `narrator/ending.py`, and this only defines the shape).
# B-17 adds `variant` (the world ending generated for this playthrough, null if none) and the characters' endings'
# `claims` (the final state they assert, may be an empty array)
# B-9 / B-17：3 層のエンディング（各文はこの周回のイベントを引用する。件数、文字数、引用、主張は `narrator/ending.py`
# の検証が見ており、ここでは形だけを定める）。
# B-17 で追加：`variant`（この周回で生成した世界のエンディング。なければ null）と登場人物のエンディングの `claims`
# （主張する最終状態。空配列でもよい）
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
CLAIM = {
    "type": "object",
    "properties": {
        "var": {"type": "string", "minLength": 1},
        "value": {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "null"}]},
    },
    "required": ["var", "value"],
    "additionalProperties": False,
}
VARIANT = {
    "anyOf": [
        {
            "type": "object",
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1},
                "summary": {"type": "string", "minLength": 1},
                "claims": {"type": "array", "items": CLAIM},
                "cites": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["id", "title", "summary", "claims", "cites"],
            "additionalProperties": False,
        },
        {"type": "null"},
    ]
}
ENDING = Prompt(
    "ending",
    text("ending"),
    {
        "type": "object",
        "properties": {
            "variant": VARIANT,
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
                        "claims": {"type": "array", "items": CLAIM},
                    },
                    "required": ["character", "yours", "claims"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["variant", "epilogue", "contrast", "subtitle", "cardContrast", "you", "characters"],
        "additionalProperties": False,
    },
)

# B-17: the model check of the ending (backend-design 2.9 step 4): whether the three layers make sense together. When
# they do not, fields lists which fields (written the same way as the rewrite's problems, e.g. "epilogue[1]",
# "characters.char.king[0]", "variant")
# B-17：エンディングのモデルチェック（backend-design 2.9 第 4 ステップ）：3 層のあいだで筋が通るか。通らないときは
# fields にどのフィールドかを書く（書き直しの problems と同じ書き方。例："epilogue[1]"、"characters.char.king[0]"、
# "variant"）
ENDING_CHECK = Prompt(
    "ending-check",
    text("ending-check"),
    {
        "type": "object",
        "properties": {
            "coherent": {"type": "boolean"},
            "fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["coherent", "fields"],
        "additionalProperties": False,
    },
)

# B-13: a one-line memory from the character's point of view (reads only the events' summaries and results, not the
# original words; length, personal information and imperative sentences are filtered again by `narrator/memory.py`),
# and the one line of "consequences that will not be undone" in the 記憶帳 deletion confirmation (null if none)
# B-15 (S-072 ⑤): when the first pass judges signal, it is reviewed again with context, and only story = true lowers it
# to ambiguous
# B-13：登場人物の視点での記憶 1 行（イベントの要約と結果だけを読み、元の発言は読まない。長さ、個人情報、命令文は
# `narrator/memory.py` がさらにふるいにかける）と、記憶帳の削除確認にある「取り消されない結果」の一文（なければ null）
# B-15（S-072 ⑤）：1 回目で signal と判定したときは文脈付きで再確認し、story = true のときだけ ambiguous に下げる
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

# B-21: suggested lines (ux-design 7.8, the suggestions in api-contract 3.5)
# B-21：発言候補（ux-design 7.8、api-contract 3.5 の suggestions）
SUGGEST = Prompt(
    "suggest",
    text("suggest"),
    {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "minLength": 1, "maxLength": 40},
                        "kind": {"enum": ["ask", "act", "accept", "decline"]},
                    },
                    "required": ["text", "kind"],
                    "additionalProperties": False,
                },
                "minItems": 2,
                "maxItems": 3,
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
)

# B-16: world advance (backend-design 2.6): the plans of characters who are not present, settling promises, and director
# events. The rules and the director rules are judged by `narrator/advance.py`; this only defines the shape
# B-16：世界の進行（backend-design 2.6）：その場にいない登場人物のプラン、約束の清算、ディレクターのイベント。規則と
# ディレクターの規則は `narrator/advance.py` が判定し、ここでは形だけを定める
WORLD = Prompt(
    "world",
    text("world"),
    {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "t": {"type": "integer"},
                        "actor": {"type": "string", "minLength": 1},
                        "origin": {"enum": ["plan", "director"]},
                        "type": {"enum": ["action", "move", "learn", "say"]},
                        "place": {"type": "string", "minLength": 1},
                        "summary": {"type": "string", "minLength": 1},
                        "causes": {"type": "array", "items": {"type": "string"}},
                        "effects": {"type": "array", "items": EFFECT},
                        "beneficiary": {"type": "string"},
                    },
                    "required": ["t", "actor", "origin", "type", "place", "summary", "causes", "effects"],
                },
            }
        },
        "required": ["events"],
    },
)

PROMPTS: dict[str, Prompt] = {
    p.kind: p
    for p in (
        TRIAGE,
        EXTRACT,
        CHECK,
        REWRITE,
        REPLY,
        NARRATE,
        PLAN,
        ENDING,
        ENDING_CHECK,
        SAFETY,
        SAFETY_REVIEW,
        MEMORY,
        KEEPS,
        SUGGEST,
        WORLD,
    )
}
