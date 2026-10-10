"""接口和数据契约对得上（C-1 卡 2）：抄过来的枚举和数据那边一样；接口在数据类型上加减的字段和 api-contract 写的一样。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from conftest import Contracts

Json = Any


def data_def(contracts: Contracts, file: str, pointer: str) -> Json:
    return contracts.resolve(f"data/{file}.schema.json", f"#{pointer}")


def api_def(contracts: Contracts, ref: str) -> Json:
    file, _, pointer = ref.partition("#")
    return contracts.resolve(f"api/{file}", f"#{pointer}")


def effect_variant(contracts: Contracts, op: str) -> Json:
    effect = data_def(contracts, "event", "/$defs/Effect")
    for v in effect["oneOf"]:
        v = contracts.resolve("data/event.schema.json", v["$ref"]) if "$ref" in v else v
        if v["properties"]["op"].get("const") == op:
            return v
    raise AssertionError(f"Effect 里没有 op = {op}")


def enum_of(contracts: Contracts, base: str, schema: Json) -> list[str]:
    if "$ref" in schema:
        return enum_of(contracts, base, contracts.resolve(base, schema["$ref"]))
    if "enum" in schema:
        return list(schema["enum"])
    raise AssertionError(f"不是枚举：{schema}")


def test_beat_change_matches_effect_beat_to(contracts: Contracts) -> None:
    api = api_def(contracts, "common.schema.json#/$defs/BeatChange")["enum"]
    data = enum_of(contracts, "data/event.schema.json", effect_variant(contracts, "beat")["properties"]["to"])
    assert api == data


def test_promise_change_matches_effect_promise_change(contracts: Contracts) -> None:
    api = api_def(contracts, "common.schema.json#/$defs/PromiseChange")["properties"]["change"]["enum"]
    data = enum_of(contracts, "data/event.schema.json", effect_variant(contracts, "promise")["properties"]["change"])
    assert api == data


def test_action_kind_is_affordance_kind_plus_move(contracts: Contracts) -> None:
    api = api_def(contracts, "ws/client.schema.json#/$defs/ActionMessage")["properties"]["kind"]["enum"]
    data = enum_of(
        contracts,
        "data/world-model.schema.json",
        data_def(contracts, "world-model", "/$defs/Affordance/properties/kind"),
    )
    assert api == [*data, "move"]


def test_timeline_beat_status_is_world_state_beats_with_canon(contracts: Contracts) -> None:
    """时间线节拍的 status 就是 WorldState.beats 的取值，只把 happened 叫作 canon（2.5）。"""
    api = api_def(contracts, "rest/timeline.schema.json#/$defs/TimelineBeatItem")["properties"]["status"]["enum"]
    beats = data_def(contracts, "world-state", "/$defs/WorldState/properties/beats/additionalProperties")
    data = enum_of(contracts, "data/world-state.schema.json", beats)
    assert sorted(api) == sorted("canon" if s == "happened" else s for s in data)


def test_ending_trigger_is_subset_of_data(contracts: Contracts) -> None:
    """接口的结局演出只有 deadline、story-closed（3.13）；abandoned 的局不演结局。"""
    api = api_def(contracts, "ws/server.schema.json#/$defs/EndingStartedMessage")["properties"]["trigger"]["enum"]
    data = enum_of(
        contracts, "data/ending.schema.json", data_def(contracts, "ending", "/$defs/Ending/properties/trigger")
    )
    assert set(api) == set(data) - {"abandoned"}


def test_telemetry_enums_match_messages(contracts: Contracts) -> None:
    """data-design 9.3：turn_retracted.result 和 turn_retract_result.status 一致；degraded_shown.reason 同 degraded。"""
    tele = "telemetry.schema.json#/$defs/"
    ws = "ws/server.schema.json#/$defs/"
    pairs = [
        ("TelemetryTurnRetracted", "result", "TurnRetractResultMessage", "status"),
        ("TelemetryDegradedShown", "reason", "DegradedMessage", "reason"),
    ]
    for t_def, t_prop, w_def, w_prop in pairs:
        t = api_def(contracts, tele + t_def)["properties"]["props"]["properties"][t_prop]["enum"]
        w = api_def(contracts, ws + w_def)["properties"][w_prop]["enum"]
        assert t == w, t_def


# 接口对象 → （对照的数据对象, 接口多的字段, 接口少的字段, 出处）。数据契约以后加字段，要不要给前端由 api-contract 定。
FIELD_DIFFS = [
    (
        "rest/ending.schema.json#/$defs/EndingCardView",
        ("ending", "/$defs/Ending/properties/card"),
        {"fallbackImageUrl"},
        set(),
        "2.8：card 由后端补 fallbackImageUrl",
    ),
    (
        "rest/ending.schema.json#/$defs/EndingView",
        ("ending", "/$defs/Ending"),
        {"you"},
        {"schemaVersion", "playthroughId", "worldModelVersion", "trigger", "t", "decidedAt", "player", "share"},
        "2.8：三层 world / you / characters 加 card；player 改叫 you",
    ),
    (
        "rest/ending.schema.json#/$defs/EndingWorldView",
        ("ending", "/$defs/Ending/properties/world"),
        {"outcomeId", "baseline", "epilogue"},
        {"outcome", "summary", "changedBeats", "finalVars", "variant", "signature"},
        "2.8：outcomeId = variant?.id ?? outcome，baseline = 没有 variant，epilogue 从 player 挪来；"
        "finalVars、changedBeats、signature 不给",
    ),
    (
        "rest/ending.schema.json#/$defs/EndingYouView",
        ("ending", "/$defs/Ending/properties/player"),
        set(),
        {"relationships", "epilogue", "lastScene"},
        "2.8：you.title = player.title.text，you.fate = player.fate.label",
    ),
    (
        "common.schema.json#/$defs/VisibleEvent",
        ("event", "/$defs/Event"),
        {"tLabel", "forPlayer", "visibleEffects", "promise"},
        {
            "schemaVersion",
            "playthroughId",
            "idempotencyKey",
            "worldModelVersion",
            "recordedAt",
            "origin",
            "beneficiary",
            "confirmed",
            "utteranceRefs",
            "effects",
            "check",
            "exitId",
            "plan",
        },
        "第 0 节「可见性」、2.4：只推玩家可见投影，check、origin 这类内部字段不推",
    ),
    (
        "common.schema.json#/$defs/MemoryView",
        ("memory", "/$defs/MemoryItem"),
        {"tLabel"},
        {
            "schemaVersion",
            "playthroughId",
            "character",
            "fromEvents",
            "trustDelta",
            "salience",
            "createdAt",
            "deletedAt",
        },
        "2.7：按人物分好，所以不重复 character；数值不给",
    ),
    (
        "common.schema.json#/$defs/PromiseView",
        ("memory", "/$defs/Promise"),
        {"direction", "eventId"},
        {"from", "to", "due", "template", "madeBy", "resolvedBy"},
        "2.7：from / to 换成 direction，eventId = madeBy",
    ),
]

# 同名字段但接口自己定了形状（各自在上面单独对照）
OWN_SHAPE = {("EndingView", "world"), ("EndingView", "card")}


@pytest.mark.parametrize(
    "api_ref,data_ref,added,removed,why", FIELD_DIFFS, ids=[f[0].rsplit("/", 1)[-1] for f in FIELD_DIFFS]
)
def test_field_diff(
    contracts: Contracts, api_ref: str, data_ref: tuple[str, str], added: set[str], removed: set[str], why: str
) -> None:
    api = api_def(contracts, api_ref)
    data = data_def(contracts, *data_ref)
    a, d = set(api["properties"]), set(data["properties"])
    assert (a - d, d - a) == (added, removed), why

    # 共有的字段直接用 JSON 指针引用数据那边的字段（字数等约束不抄第二份）
    name = api_ref.rsplit("/", 1)[-1]
    data_file, data_ptr = data_ref
    for field in sorted(a & d):
        if (name, field) in OWN_SHAPE:
            continue
        refs = [n["$ref"] for _, n in contracts.walk(api["properties"][field]) if isinstance(n, dict) and "$ref" in n]
        want = f"data/{data_file}.schema.json#{data_ptr}/properties/{field}"
        assert any(r.endswith(want) or f"{want}/" in r for r in refs), f"{name}.{field} 应该引用 {want}，现在是 {refs}"
