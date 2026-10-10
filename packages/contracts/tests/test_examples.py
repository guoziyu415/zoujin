"""接口的例子（C-1 第 4、5 条）：合法例子全过、反例按写明的原因不过；每种消息和每个响应都有例子；
全部合法例子（数据的也算）经 pydantic 解析再导出不变。数据例子对 Schema 的校验在 test_data_schemas.py。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from jsonschema import ValidationError
from pydantic import TypeAdapter
from zoujin_contracts.generated import api, data

if TYPE_CHECKING:
    from conftest import Contracts

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
VALID_API = EXAMPLES / "valid" / "api"
INVALID_API = EXAMPLES / "invalid" / "api"
VALID = sorted(VALID_API.rglob("*.json"))
INVALID = sorted(INVALID_API.rglob("*.json"))
VALID_DATA = sorted((EXAMPLES / "valid" / "data").glob("*/*.json"))

# 每个反例该在哪个位置（JSON 指针，不带开头的 /）、因为哪个关键字被拒。新加反例在这里加一行，
# 免得它因为别的原因被拒、测不到想测的东西。WebSocket 的反例 type 没写错时对那一种消息校验，写错了对整个联合。
INVALID_BECAUSE: dict[str, tuple[str, str]] = {
    "error/ErrorResponse/unknown-code.json": ("enum", "error/code"),
    "rest/ending/200/card-extra-field.json": ("additionalProperties", "card"),
    "rest/ending/200/card-title-too-long.json": ("maxLength", "card/title"),
    "rest/events/query/limit-over-50.json": ("maximum", "limit"),
    "rest/me/200/missing-limits.json": ("required", ""),
    "rest/playthroughs-create/409/without-active-playthrough.json": ("required", ""),
    "rest/snapshot/200/line-before-promise.json": ("not", "deadline"),
    "rest/snapshot/200/melos-minutes-without-melos.json": ("type", "actions/0/melosMinutes"),
    "rest/snapshot/200/relation-label-without-level.json": ("dependentRequired", "characters/0"),
    "rest/snapshot/200/unknown-activity.json": ("enum", "characters/0/activity"),
    "rest/telemetry/request/empty-batch.json": ("minItems", "events"),
    "rest/telemetry/request/transcript-in-props.json": ("additionalProperties", "events/0/props"),
    "rest/timeline/200/unknown-beat-with-title.json": ("not", "days/0/items/2"),
    "ws/client/act_choose/option-not-exit.json": ("pattern", "optionId"),
    "ws/client/act_propose/text-too-long.json": ("maxLength", "text"),
    "ws/client/activity_start/turn-id-prefix.json": ("pattern", "turnId"),
    "ws/client/activity_start/turn-seq-over-uint32.json": ("maximum", "turnSeq"),
    "ws/client/activity_start/turn-seq-server-range.json": ("maximum", "turnSeq"),
    "ws/client/activity_start/turn-seq-zero.json": ("minimum", "turnSeq"),
    "ws/client/near/extra-field.json": ("additionalProperties", ""),
    "ws/client/near/missing-character.json": ("required", ""),
    "ws/client/near/type-typo.json": ("oneOf", ""),
    "ws/client/text/correction-without-replaces.json": ("required", ""),
    "ws/client/text/replaces-without-correction.json": ("not", ""),
    "ws/client/text/text-too-long.json": ("maxLength", "text"),
    "ws/server/act_ended/three-en-route-choices.json": ("maxItems", "options/0/enRoute/choices"),
    "ws/server/commit/added-memory-without-text.json": ("required", "memories/0"),
    "ws/server/commit/event-id-prefix.json": ("pattern", "events/0/eventId"),
    "ws/server/commit/internal-field-leaked.json": ("additionalProperties", "events/0"),
    "ws/server/commit/missing-patch.json": ("required", ""),
    "ws/server/commit/reveal-kind.json": ("enum", "reveal/kind"),
    "ws/server/degraded/voice-true.json": ("const", "voice"),
    "ws/server/limits/negative.json": ("minimum", "voiceMinutesLeft"),
    "ws/server/transcript/character-final-without-source.json": ("required", ""),
    "ws/server/transcript/null-text-not-fallback.json": ("const", "source"),
    "ws/server/transcript/partial-with-source.json": ("not", ""),
    "ws/server/turn_started/client-turn-seq.json": ("minimum", "turnSeq"),
}


def example_id(p: Path) -> str:
    return p.relative_to(EXAMPLES).as_posix()


def load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def all_errors(errors: list[ValidationError]) -> Iterator[ValidationError]:
    """连同 oneOf / anyOf 各分支里的错误一起。"""
    for e in errors:
        yield e
        yield from all_errors(list(e.context or []))


def explain(errors: list[ValidationError]) -> str:
    return "\n".join(f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in errors)


@pytest.mark.parametrize("path", VALID, ids=example_id)
def test_valid_example(contracts: Contracts, path: Path) -> None:
    rel = path.relative_to(VALID_API)
    base, ref, name = contracts.example_target(rel)
    doc = load(path)
    if rel.parts[0] == "ws":
        assert doc["type"] == name, "ws 例子放在以 type 命名的目录里"
        # 先对这一种消息本身校验，出错时信息比整个 oneOf 的好读
        single = contracts.validator(base, f"#/$defs/{contracts.ws_types(rel.parts[1])[name]}")
        errors = list(single.iter_errors(doc))
        assert not errors, explain(errors)
    errors = list(contracts.validator(base, ref).iter_errors(doc))
    assert not errors, explain(errors)


@pytest.mark.parametrize("path", INVALID, ids=example_id)
def test_invalid_example_fails_for_the_stated_reason(contracts: Contracts, path: Path) -> None:
    rel = path.relative_to(INVALID_API)
    key = rel.as_posix()
    assert key in INVALID_BECAUSE, f"{key}：在 INVALID_BECAUSE 里写明它为什么不过"
    base, ref, name = contracts.example_target(rel)
    doc = load(path)
    assert not contracts.validator(base, ref).is_valid(doc), "反例应该不过"
    if rel.parts[0] == "ws" and doc.get("type") == name:
        # type 没写错的反例，对它自己那种消息找原因（不是因为落到了别的消息上才不过）
        ref = f"#/$defs/{contracts.ws_types(rel.parts[1])[name]}"
    found = {
        (e.validator, "/".join(map(str, e.absolute_path)))
        for e in all_errors(list(contracts.validator(base, ref).iter_errors(doc)))
    }
    keyword, where = INVALID_BECAUSE[key]
    assert (keyword, where) in found, f"{key}：没有在 {where!r} 报 {keyword}，实际 {sorted(found)}"


def test_invalid_because_has_no_stale_entries() -> None:
    assert set(INVALID_BECAUSE) == {p.relative_to(INVALID_API).as_posix() for p in INVALID}


def test_every_message_and_response_has_an_example(contracts: Contracts) -> None:
    have = {p.relative_to(VALID_API).parent.as_posix() for p in VALID}
    missing = []
    for side in ("client", "server"):
        missing += [f"ws/{side}/{t}" for t in contracts.ws_types(side) if f"ws/{side}/{t}" not in have]
    for name, ep in contracts.endpoints().items():
        wanted = [s for s, ref in ep["responses"].items() if ref is not None]
        wanted += ["request"] if "request" in ep else []
        missing += [f"rest/{name}/{w}" for w in wanted if f"rest/{name}/{w}" not in have]
    assert not missing, "缺例子：\n" + "\n".join(missing)


# —— pydantic ——


def api_adapter(contracts: Contracts, rel: Path) -> TypeAdapter[Any]:
    base, ref, _ = contracts.example_target(rel)
    if rel.parts[0] == "ws":
        return TypeAdapter(api.ClientMessage if rel.parts[1] == "client" else api.ServerMessage)
    def_name = ref.rsplit("/", 1)[-1]
    schema = contracts.resolve(base, ref)
    return TypeAdapter(getattr(api, schema.get("title", def_name)))


def data_adapter(contracts: Contracts, def_name: str) -> TypeAdapter[Any]:
    """数据例子的目录名是 $defs 名；生成的类型名有 title 时用 title（例：Promise → StoryPromise）。"""
    for doc in contracts.data().values():
        if def_name in doc.get("$defs", {}):
            return TypeAdapter(getattr(data, doc["$defs"][def_name].get("title", def_name)))
    raise AssertionError(f"数据 Schema 里没有 {def_name}")


def assert_round_trip(ta: TypeAdapter[Any], doc: Any) -> None:
    """解析再导出（by_alias，只导出给了的字段，所以显式的 null 留着）后和原文件相同。"""
    parsed = ta.validate_python(doc)
    assert ta.dump_python(parsed, mode="json", by_alias=True, exclude_unset=True) == doc


@pytest.mark.parametrize("path", VALID, ids=example_id)
def test_pydantic_round_trip_api(contracts: Contracts, path: Path) -> None:
    rel = path.relative_to(VALID_API)
    if rel.parts[0] == "rest" and rel.parts[2] in ("query", "params"):
        pytest.skip("路径参数和查询参数不经 pydantic")
    assert_round_trip(api_adapter(contracts, rel), load(path))


@pytest.mark.parametrize("path", VALID_DATA, ids=example_id)
def test_pydantic_round_trip_data(contracts: Contracts, path: Path) -> None:
    assert_round_trip(data_adapter(contracts, path.parent.name), load(path))
