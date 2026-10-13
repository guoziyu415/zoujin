"""The API and the data contracts line up (C-1 card 2): copied enums match the data side, and the fields the API adds
to or removes from data types match what api-contract says.

API とデータ契約が一致する（C-1 カード 2）：写した列挙はデータ側と同じで、API がデータ型に加減したフィールドは
api-contract の記述どおり。
"""

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
    raise AssertionError(f"No op = {op} in Effect / Effect に op = {op} がない")


def enum_of(contracts: Contracts, base: str, schema: Json) -> list[str]:
    if "$ref" in schema:
        return enum_of(contracts, base, contracts.resolve(base, schema["$ref"]))
    if "enum" in schema:
        return list(schema["enum"])
    raise AssertionError(f"Not an enum / 列挙ではない：{schema}")


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
    """The status of timeline beats is the values of WorldState.beats, with happened renamed to canon (2.5).

    タイムラインのビートの status は WorldState.beats の値そのもので、happened だけを canon と呼ぶ（2.5）。
    """
    api = api_def(contracts, "rest/timeline.schema.json#/$defs/TimelineBeatItem")["properties"]["status"]["enum"]
    beats = data_def(contracts, "world-state", "/$defs/WorldState/properties/beats/additionalProperties")
    data = enum_of(contracts, "data/world-state.schema.json", beats)
    assert sorted(api) == sorted("canon" if s == "happened" else s for s in data)


def test_ending_trigger_is_subset_of_data(contracts: Contracts) -> None:
    """The API's ending staging has only deadline and story-closed (3.13); abandoned playthroughs get no ending staging.

    API のエンディング演出は deadline と story-closed だけ（3.13）。abandoned のプレイではエンディングを演じない。
    """
    api = api_def(contracts, "ws/server.schema.json#/$defs/EndingStartedMessage")["properties"]["trigger"]["enum"]
    data = enum_of(
        contracts, "data/ending.schema.json", data_def(contracts, "ending", "/$defs/Ending/properties/trigger")
    )
    assert set(api) == set(data) - {"abandoned"}


def test_telemetry_enums_match_messages(contracts: Contracts) -> None:
    """data-design 9.3: turn_retracted.result matches turn_retract_result.status; degraded_shown.reason matches
    degraded; ending_performed.trigger matches ending_started.

    data-design 9.3：turn_retracted.result は turn_retract_result.status と一致し、degraded_shown.reason は
    degraded と、ending_performed.trigger は ending_started と同じ。
    """
    tele = "telemetry.schema.json#/$defs/"
    ws = "ws/server.schema.json#/$defs/"
    pairs = [
        ("TelemetryTurnRetracted", "result", "TurnRetractResultMessage", "status"),
        ("TelemetryDegradedShown", "reason", "DegradedMessage", "reason"),
        ("TelemetryEndingPerformed", "trigger", "EndingStartedMessage", "trigger"),
    ]
    for t_def, t_prop, w_def, w_prop in pairs:
        t = api_def(contracts, tele + t_def)["properties"]["props"]["properties"][t_prop]["enum"]
        w = api_def(contracts, ws + w_def)["properties"][w_prop]["enum"]
        assert t == w, t_def


# API object → (data object it is compared with, fields the API adds, fields the API drops, source). When the data
# contracts add fields later, api-contract decides whether the frontend gets them.
# API のオブジェクト → （比較するデータのオブジェクト、API で増えるフィールド、API で減るフィールド、出典）。
# 今後データ契約にフィールドが増えたとき、フロントエンドに渡すかどうかは api-contract が決める。
FIELD_DIFFS = [
    (
        "rest/ending.schema.json#/$defs/EndingCardView",
        ("ending", "/$defs/Ending/properties/card"),
        {"fallbackImageUrl"},
        set(),
        "2.8: the backend adds fallbackImageUrl to card / 2.8：card にはバックエンドが fallbackImageUrl を補う",
    ),
    (
        "rest/ending.schema.json#/$defs/EndingView",
        ("ending", "/$defs/Ending"),
        {"you"},
        {"schemaVersion", "playthroughId", "worldModelVersion", "trigger", "t", "decidedAt", "player", "share"},
        "2.8: three layers world / you / characters plus card; player is renamed you / "
        "2.8：world / you / characters の 3 層と card。player は you と呼び替える",
    ),
    (
        "rest/ending.schema.json#/$defs/EndingWorldView",
        ("ending", "/$defs/Ending/properties/world"),
        {"outcomeId", "baseline", "epilogue"},
        {"outcome", "summary", "changedBeats", "finalVars", "variant", "signature"},
        "2.8: outcomeId = variant?.id ?? outcome, baseline = no variant, epilogue moved over from player; "
        "finalVars, changedBeats and signature are not sent / "
        "2.8：outcomeId = variant?.id ?? outcome、baseline = variant なし、epilogue は player から移す。"
        "finalVars、changedBeats、signature は送らない",
    ),
    (
        "rest/ending.schema.json#/$defs/EndingYouView",
        ("ending", "/$defs/Ending/properties/player"),
        set(),
        {"relationships", "epilogue", "lastScene"},
        "2.8: you.title = player.title.text, you.fate = player.fate.label / "
        "2.8：you.title = player.title.text、you.fate = player.fate.label",
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
        'Section 0 "Visibility", 2.4: only the player-visible projection is pushed; internal fields such as '
        "check and origin are not / 第 0 節「可視性」、2.4：プレイヤーに見える射影だけを送り、check や origin のような"
        "内部フィールドは送らない",
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
        "2.7: already grouped by character, so character is not repeated; numeric values are not sent / "
        "2.7：登場人物ごとに分けてあるので character は繰り返さない。数値は送らない",
    ),
    (
        "common.schema.json#/$defs/PromiseView",
        ("memory", "/$defs/Promise"),
        {"direction", "eventId"},
        {"from", "to", "due", "template", "madeBy", "resolvedBy"},
        "2.7: from / to are replaced by direction, eventId = madeBy / "
        "2.7：from / to は direction に置き換え、eventId = madeBy",
    ),
]

# Fields with the same name whose shape the API defines itself (each compared separately above)
# 同名のフィールドだが API が独自に形を決めたもの（それぞれ上で個別に比較している）
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

    # Shared fields reference the data-side field directly by JSON pointer (constraints such as lengths are not copied)
    # 共通のフィールドは JSON ポインタでデータ側のフィールドを直接参照する（字数などの制約を二重に書かない）
    name = api_ref.rsplit("/", 1)[-1]
    data_file, data_ptr = data_ref
    for field in sorted(a & d):
        if (name, field) in OWN_SHAPE:
            continue
        refs = [n["$ref"] for _, n in contracts.walk(api["properties"][field]) if isinstance(n, dict) and "$ref" in n]
        want = f"data/{data_file}.schema.json#{data_ptr}/properties/{field}"
        assert any(r.endswith(want) or f"{want}/" in r for r in refs), (
            f"{name}.{field} should reference {want}, but has {refs} / "
            f"{name}.{field} は {want} を参照すべきだが、現在は {refs}"
        )
