"""Prompt rendering (B-2; in B-8 moved out of `models/vertex.py` to be shared by both providers): request (JSON
assembled by the backend, from which replays compute their key) → the model's input.

- World model prefix: keeps only the fields the narrator needs, and its content does not change within a version.
  Google puts it at the very start of the user content to benefit from implicit caching; Claude puts it as the first
  block of system, with a cache breakpoint (`models/claude.py`).
- The words of the player and characters go only into `<utterance>` data fields, with angle brackets replaced by
  full-width ones, so they cannot be used to close the tag.

プロンプトのレンダリング（B-2。B-8 で `models/vertex.py` から切り出し、両プロバイダで共用）：リクエスト（バックエンドが
組み立てた JSON で、リプレイはそれからキーを計算する）→ モデルの入力。

- 世界モデルのプレフィックス：ナレーターに必要なフィールドだけを残し、同じバージョン内では内容が変わらない。Google は
  ユーザーコンテンツの先頭に置いて暗黙キャッシュを効かせ、Claude は system の最初のブロックに置いてキャッシュポイントを
  打つ（`models/claude.py`）。
- プレイヤーと登場人物の発言は `<utterance>` データフィールドにだけ入れ、山括弧を全角に置き換えて、それを使ってタグを
  閉じられないようにする。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

Json = Any


def _escape(text: str | None) -> str:
    """Before original words go into an <utterance> data field, replace angle brackets with full-width ones so they
    cannot be used to close the tag.

    元の発言を <utterance> データフィールドに入れる前に、山括弧を全角に置き換え、
    それを使ってタグを閉じられないようにする。
    """
    return (text or "").replace("<", "＜").replace(">", "＞")


def world_prefix(world: Json) -> str:
    """World model prefix: keeps only the fields the narrator needs and drops the sources (`cite`, `inferred`, `note`);
    its content does not change within a version, and it goes first to benefit from implicit caching.

    世界モデルのプレフィックス：ナレーターに必要なフィールドだけを残し、出典（`cite`、`inferred`、`note`）を除く。同じ
    バージョン内では内容が変わらず、先頭に置いて暗黙キャッシュを効かせる。
    """
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


def render_context(ctx: Mapping[str, Any]) -> str:
    """B-15: the context for safety screening (who is being spoken to, where, the character's previous line). The
    character's previous line also goes only into an <utterance> data field.

    B-15：安全審査の文脈（誰に話しているか、どこか、登場人物の直前の一言）。登場人物の直前の一言も <utterance>
    データフィールドにだけ入れる。
    """
    head = {k: ctx[k] for k in ("character", "place") if ctx.get(k)}
    lines = [json.dumps(head, ensure_ascii=False)]
    if ctx.get("previous"):
        lines.append(f'<utterance speaker="character">{_escape(ctx["previous"])}</utterance>')
    return "<context>\n" + "\n".join(lines) + "\n</context>"


def render_parts(kind: str, request: Mapping[str, Any]) -> list[str]:
    """The data in one call other than the prefix, block by block: state → this turn → this prompt kind's own fields.

    1 回の呼び出しのうちプレフィックス以外のデータをブロックごとに：状態 → このターン →
    このプロンプト種別自身のフィールド。
    """
    parts: list[str] = []
    if "state" in request:
        parts.append("<state>\n" + json.dumps(request["state"], ensure_ascii=False) + "\n</state>")
    if "turn" in request:
        parts.append(render_turn(request["turn"]))
    # B-3: the action the player took in the extraction input (kind, object, item), a data field
    # B-3：抽出の入力にあるプレイヤーのアクション（kind、対象、アイテム）。データフィールド
    if "action" in request:
        parts.append("<action>\n" + json.dumps(request["action"], ensure_ascii=False) + "\n</action>")
    # B-4: the question asked back that awaits an answer in the extraction input (the question, the matter's summary),
    # a data field
    # B-4：抽出の入力にある回答待ちの聞き返し（聞き返しの一文、その件の要約）。データフィールド
    if "confirm" in request:
        parts.append("<confirm>\n" + json.dumps(request["confirm"], ensure_ascii=False) + "\n</confirm>")
    if "context" in request:
        parts.append(render_context(request["context"]))
    skip = ("state", "turn", "action", "confirm", "context", "worldModelVersion")
    rest = {k: v for k, v in request.items() if k not in skip}
    if rest:
        parts.append(f"<{kind}>\n" + json.dumps(rest, ensure_ascii=False) + f"\n</{kind}>")
    return parts


def render_body(kind: str, request: Mapping[str, Any]) -> str:
    """Claude's user content (the prefix is in system).

    Claude のユーザーコンテンツ（プレフィックスは system にある）。
    """
    return "\n\n".join(render_parts(kind, request))


def render(kind: str, request: Mapping[str, Any], prefix: str) -> str:
    """The user content of one Google call: prefix → state → this turn → this prompt kind's own fields (all data).
    The prefix goes first to benefit from implicit caching.

    Google の 1 回の呼び出しのユーザーコンテンツ：プレフィックス → 状態 → このターン → このプロンプト種別自身の
    フィールド（すべてデータ）。プレフィックスを先頭に置いて暗黙キャッシュを効かせる。
    """
    return "\n\n".join([prefix, *render_parts(kind, request)])
