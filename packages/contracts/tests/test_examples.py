"""API examples (C-1 items 4 and 5): every valid example passes and every invalid one fails for its stated reason;
every message and every response has an example; every valid example (data ones included) is unchanged after a
pydantic parse and dump. Validation of the data examples against the Schemas is in test_data_schemas.py.

API の例（C-1 第 4、5 項）：正しい例はすべて通り、反例は明記した理由で通らない。すべてのメッセージとレスポンスに
例がある。正しい例はすべて（データの例も含め）pydantic で解析して出力し直しても変わらない。データの例の Schema
による検証は test_data_schemas.py にある。
"""

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

# For each invalid example: where (JSON pointer without the leading /) and by which keyword it should be rejected.
# Add a line here for each new invalid example, so that it does not get rejected for some other reason and miss what
# it is meant to test. A WebSocket invalid example with a correct type is validated against that one message kind;
# with a wrong type, against the whole union.
# 各反例がどの位置（先頭の / を除いた JSON ポインタ）で、どのキーワードによって拒否されるべきか。反例を追加したら
# ここに 1 行加える。そうしないと別の理由で拒否されて、テストしたいことがテストされない。WebSocket の反例は、type が
# 正しければそのメッセージの種類に対して、誤っていればユニオン全体に対して検証する。
INVALID_BECAUSE: dict[str, tuple[str, str]] = {
    "error/ErrorResponse/unknown-code.json": ("enum", "error/code"),
    "rest/ending/200/card-extra-field.json": ("additionalProperties", "card"),
    "rest/ending/200/card-title-too-long.json": ("maxLength", "card/title"),
    "rest/ending/200/missing-card.json": ("required", ""),
    "rest/events/query/limit-over-50.json": ("maximum", "limit"),
    "rest/manifest/200/set-piece-voice-index-zero.json": ("pattern", "setPieceVoices"),
    "rest/me/200/missing-limits.json": ("required", ""),
    "rest/playthroughs-create/409/without-active-playthrough.json": ("required", ""),
    "rest/snapshot/200/character-without-spot.json": ("required", "characters/0"),
    "rest/snapshot/200/group-with-spot.json": ("not", "characters/1"),
    "rest/snapshot/200/line-before-promise.json": ("not", "deadline"),
    "rest/snapshot/200/melos-minutes-without-melos.json": ("type", "actions/0/melosMinutes"),
    "rest/snapshot/200/relation-label-without-level.json": ("dependentRequired", "characters/0"),
    "rest/snapshot/200/unknown-activity.json": ("enum", "characters/0/activity"),
    "rest/telemetry/request/empty-batch.json": ("minItems", "events"),
    "rest/telemetry/request/histogram-8-bins.json": ("minItems", "events/0/props/frameTimeHistogram"),
    "rest/telemetry/request/transcript-in-props.json": ("additionalProperties", "events/0/props"),
    "rest/timeline/200/unknown-beat-with-title.json": ("not", "days/0/items/2"),
    "rest/timeline/200/unknown-beat-with-cite.json": ("not", "days/0/items/2"),
    "rest/timeline/200/unknown-beat-with-place.json": ("not", "days/0/items/2"),
    "ws/client/act_choose/option-not-exit.json": ("pattern", "optionId"),
    "ws/client/act_landed/missing-act-id.json": ("required", ""),
    "ws/client/action/move-without-target.json": ("required", ""),
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
    "ws/server/act_ended/option-without-where.json": ("required", "options/0"),
    "ws/server/act_ended/sub-too-long.json": ("maxLength", "options/0/sub"),
    "ws/server/act_ended/three-en-route-choices.json": ("maxItems", "options/0/enRoute/choices"),
    "ws/server/act_transition/arrival-without-line.json": ("required", "arrival"),
    "ws/server/action_result/both-narration-and-set-piece.json": ("not", ""),
    "ws/server/action_result/neither-narration-nor-set-piece.json": ("required", ""),
    "ws/server/act_plan_result/both-client-msg-id-and-turn-id.json": ("not", ""),
    "ws/server/act_plan_result/neither-client-msg-id-nor-turn-id.json": ("required", ""),
    "ws/server/commit/added-memory-without-text.json": ("required", "memories/0"),
    "ws/server/commit/event-id-prefix.json": ("pattern", "events/0/eventId"),
    "ws/server/commit/internal-field-leaked.json": ("additionalProperties", "events/0"),
    "ws/server/commit/missing-patch.json": ("required", ""),
    "ws/server/commit/reveal-kind.json": ("enum", "reveal/kind"),
    "ws/server/degraded/voice-true.json": ("const", "voice"),
    "ws/server/limits/negative.json": ("minimum", "voiceMinutesLeft"),
    "ws/server/set_piece/line-with-both.json": ("additionalProperties", "lines/0"),
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
    """Including the errors inside each oneOf / anyOf branch.

    oneOf / anyOf の各分岐内のエラーも含める。
    """
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
        assert doc["type"] == name, (
            "ws examples go in a directory named after their type / ws の例は type 名のディレクトリに置く"
        )
        # Validate against this message kind first; its errors are easier to read than those of the whole oneOf
        # まずこのメッセージの種類そのものに対して検証する。エラーが oneOf 全体のものより読みやすい
        single = contracts.validator(base, f"#/$defs/{contracts.ws_types(rel.parts[1])[name]}")
        errors = list(single.iter_errors(doc))
        assert not errors, explain(errors)
    errors = list(contracts.validator(base, ref).iter_errors(doc))
    assert not errors, explain(errors)


@pytest.mark.parametrize("path", INVALID, ids=example_id)
def test_invalid_example_fails_for_the_stated_reason(contracts: Contracts, path: Path) -> None:
    rel = path.relative_to(INVALID_API)
    key = rel.as_posix()
    assert key in INVALID_BECAUSE, (
        f"{key}: state in INVALID_BECAUSE why it fails / なぜ通らないかを INVALID_BECAUSE に明記する"
    )
    base, ref, name = contracts.example_target(rel)
    doc = load(path)
    assert not contracts.validator(base, ref).is_valid(doc), "An invalid example should fail / 反例は通らないはず"
    if rel.parts[0] == "ws" and doc.get("type") == name:
        # For an invalid example with a correct type, look for the reason in its own message kind (it must not fail
        # only because it fell through to another message)
        # type が正しい反例は、自分のメッセージの種類で原因を探す（別のメッセージに当てはめられたせいで
        # 通らないのではない）
        ref = f"#/$defs/{contracts.ws_types(rel.parts[1])[name]}"
    found = {
        (e.validator, "/".join(map(str, e.absolute_path)))
        for e in all_errors(list(contracts.validator(base, ref).iter_errors(doc)))
    }
    keyword, where = INVALID_BECAUSE[key]
    assert (keyword, where) in found, (
        f"{key}: no {keyword} reported at {where!r}; got {sorted(found)} / "
        f"{where!r} で {keyword} が報告されていない。実際は {sorted(found)}"
    )


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
    assert not missing, "Missing examples / 例が足りない：\n" + "\n".join(missing)


# —— pydantic ——


def api_adapter(contracts: Contracts, rel: Path) -> TypeAdapter[Any]:
    base, ref, _ = contracts.example_target(rel)
    if rel.parts[0] == "ws":
        return TypeAdapter(api.ClientMessage if rel.parts[1] == "client" else api.ServerMessage)
    def_name = ref.rsplit("/", 1)[-1]
    schema = contracts.resolve(base, ref)
    return TypeAdapter(getattr(api, schema.get("title", def_name)))


def data_adapter(contracts: Contracts, def_name: str) -> TypeAdapter[Any]:
    """A data example's directory name is the $defs name; the generated type name is the title when there is one
    (e.g. Promise → StoryPromise).

    データの例のディレクトリ名は $defs の名前。生成される型名は title があれば title になる
    （例：Promise → StoryPromise）。
    """
    for doc in contracts.data().values():
        if def_name in doc.get("$defs", {}):
            return TypeAdapter(getattr(data, doc["$defs"][def_name].get("title", def_name)))
    raise AssertionError(f"{def_name} not in the data Schemas / データの Schema に {def_name} がない")


def assert_round_trip(ta: TypeAdapter[Any], doc: Any) -> None:
    """After parsing and dumping again (by_alias, dumping only the fields that were given, so explicit nulls stay)
    the result equals the original file.

    解析して出力し直した結果（by_alias、与えられたフィールドだけを出力するので明示的な null は残る）が元のファイルと
    同じになる。
    """
    parsed = ta.validate_python(doc)
    assert ta.dump_python(parsed, mode="json", by_alias=True, exclude_unset=True) == doc


@pytest.mark.parametrize("path", VALID, ids=example_id)
def test_pydantic_round_trip_api(contracts: Contracts, path: Path) -> None:
    rel = path.relative_to(VALID_API)
    if rel.parts[0] == "rest" and rel.parts[2] in ("query", "params"):
        pytest.skip(
            "Path and query parameters do not go through pydantic / "
            "パスパラメータとクエリパラメータは pydantic を通さない"
        )
    assert_round_trip(api_adapter(contracts, rel), load(path))


@pytest.mark.parametrize("path", VALID_DATA, ids=example_id)
def test_pydantic_round_trip_data(contracts: Contracts, path: Path) -> None:
    assert_round_trip(data_adapter(contracts, path.parent.name), load(path))
