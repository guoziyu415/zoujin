"""提示的渲染（B-2，B-8 从 `models/vertex.py` 挪出来两家共用）：请求（后端拼好的 JSON，回放按它算键）→ 模型的输入。

- 世界模型前缀：只留叙事者要的字段，同一版本内容不变。Google 放在用户内容最前吃隐式缓存；Claude 放在 system 的第一段，
  打缓存点（`models/claude.py`）。
- 玩家和人物的话只放在 `<utterance>` 数据字段里，尖括号换成全角，不能借它关掉标签。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

Json = Any


def _escape(text: str | None) -> str:
    """原话放进 <utterance> 数据字段前，把尖括号换成全角，不能借它关掉标签。"""
    return (text or "").replace("<", "＜").replace(">", "＞")


def world_prefix(world: Json) -> str:
    """世界模型前缀：只留叙事者要的字段，去掉出处（`cite`、`inferred`、`note`），同一版本内容不变，放在最前吃隐式缓存。"""
    keep = {
        "characters": (
            "id",
            "name",
            "summary",
            "traits",
            "goals",
            "knows",
            "initialPlace",
            "group",
            "talkable",
            "mutualAid",
            "promiseTemplates",
            "plans",
            "items",
        ),
        "places": ("id", "name", "description", "adjacent", "sceneRef"),
        "facts": ("id", "statement", "trueFrom", "visibility", "spoilerTerms"),
        "beats": (
            "id",
            "order",
            "title",
            "summary",
            "kind",
            "window",
            "place",
            "participants",
            "preconditions",
            "outcomes",
        ),
        "stateVars": ("id", "type", "values", "min", "max", "default", "description", "valueRequires"),
        "affordances": ("id", "kind", "label", "place", "roles", "when", "target", "minutes", "effects"),
        "items": ("id", "name", "portable", "at"),
        "roles": ("id", "name", "access", "initialKnowledge"),
    }
    doc: Json = {"worldModelVersion": world["worldModelVersion"], "anchors": world["anchors"]}
    for key, fields in keep.items():
        doc[key] = [{k: x[k] for k in fields if k in x} for x in world.get(key, [])]
    doc["globalRules"] = [
        {k: g[k] for k in ("id", "text", "statement") if k in g} for g in world.get("globalRules", [])
    ]
    return "<world>\n" + json.dumps(_plain(doc), ensure_ascii=False, separators=(",", ":")) + "\n</world>"


def _plain(x: Json) -> Json:
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items() if k not in ("cite", "inferred", "note")}
    if isinstance(x, list):
        return [_plain(v) for v in x]
    return x


def render_turn(turn: Mapping[str, Any]) -> str:
    who = turn.get("character") or ""
    lines = [f'<utterance speaker="player">{_escape(turn.get("player"))}</utterance>']
    if turn.get("reply") is not None:
        lines.append(f'<utterance speaker="{who}">{_escape(turn.get("reply"))}</utterance>')
    rest = {k: v for k, v in turn.items() if k not in ("player", "reply")}
    return "<turn>\n" + json.dumps(rest, ensure_ascii=False) + "\n" + "\n".join(lines) + "\n</turn>"


def render_parts(kind: str, request: Mapping[str, Any]) -> list[str]:
    """一次调用里前缀以外的数据，一段一段：状态 → 这一轮 → 这种提示自己的字段。"""
    parts: list[str] = []
    if "state" in request:
        parts.append("<state>\n" + json.dumps(request["state"], ensure_ascii=False) + "\n</state>")
    if "turn" in request:
        parts.append(render_turn(request["turn"]))
    if "action" in request:  # B-3：提取的输入里玩家做的动作（kind、对象、物品），数据字段
        parts.append("<action>\n" + json.dumps(request["action"], ensure_ascii=False) + "\n</action>")
    if "confirm" in request:  # B-4：提取的输入里在等回答的反问（反问的一句、那件事的摘要），数据字段
        parts.append("<confirm>\n" + json.dumps(request["confirm"], ensure_ascii=False) + "\n</confirm>")
    rest = {k: v for k, v in request.items() if k not in ("state", "turn", "action", "confirm", "worldModelVersion")}
    if rest:
        parts.append(f"<{kind}>\n" + json.dumps(rest, ensure_ascii=False) + f"\n</{kind}>")
    return parts


def render_body(kind: str, request: Mapping[str, Any]) -> str:
    """Claude 的用户内容（前缀在 system 里）。"""
    return "\n\n".join(render_parts(kind, request))


def render(kind: str, request: Mapping[str, Any], prefix: str) -> str:
    """Google 一次调用的用户内容：前缀 → 状态 → 这一轮 → 这种提示自己的字段（都是数据）。前缀放最前吃隐式缓存。"""
    return "\n\n".join([prefix, *render_parts(kind, request)])
