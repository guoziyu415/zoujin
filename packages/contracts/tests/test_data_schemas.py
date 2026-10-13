"""JSON Schemas of the data contracts (C-2): meta-Schema, examples, comparison with contracts.md, closed objects,
and validation of the data files in the repo.

No network: the 8 Schemas reference each other only with relative $refs, and all are loaded into the registry from
local files.

データ契約の JSON Schema（C-2）：メタ Schema、例、contracts.md との突き合わせ、オブジェクトが閉じていること、
リポジトリ内のデータファイルの検証。

ネットワークは使わない：8 つの Schema は互いに相対 $ref だけで参照し、すべてローカルファイルから registry に読み込む。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[1]
SCHEMAS = PKG / "schemas" / "data"
EXAMPLES = PKG / "examples"
CONTRACTS_MD = REPO / "docs" / "data" / "contracts.md"

# The 8 files and their $defs (the table in the C-2 card). common also holds shared definitions (IDs, times, etc.),
# which are not contracts.md types and are not compared.
# 8 つのファイルとそれぞれの $defs（C-2 カードの表）。common にはほかに共通定義（ID、時刻など）があるが、
# contracts.md の型ではないので突き合わせには含めない。
TYPES_BY_FILE: dict[str, list[str]] = {
    "common": ["Cite"],
    "playthrough": ["Playthrough"],
    "world-model": (
        "WorldModel Character DesignLine MutualAid PromiseTemplate Place Scene Fact Beat BeatVariant Activity Condition"
        " CausalEdge Clock StateVar Role Act ActExit EnRoute EnRouteChoice WorldEnding EndingSignature Affordance Item"
        " SetPiece WorldObject"
    ).split(),
    "event": ["Event", "Effect", "CheckResult"],
    "utterance": ["Utterance"],
    "world-state": ["WorldState", "RunFact"],
    "memory": ["MemoryItem", "Relationship", "Promise"],
    "ending": ["Ending", "CharacterEnding"],
}
MAIN_TYPE = {
    "playthrough": "Playthrough",
    "world-model": "WorldModel",
    "event": "Event",
    "utterance": "Utterance",
    "world-state": "WorldState",
    "memory": "MemoryItem",
    "ending": "Ending",
}
FILE_OF = {t: f for f, ts in TYPES_BY_FILE.items() for t in ts}
COMMON_DEFS = set(
    "Cite SchemaVersion StoryTime TLabel RecordedAt Actor WorldEndingId"
    " PlaythroughId TurnId EventId MemoryId UtteranceId EndingId PromiseId RunFactId"
    " CharacterId PlaceId SceneId ActId BeatId FactId VarId RoleId EdgeId AidId PromiseTemplateId AffordanceId ItemId"
    " ExitId RuleId SpotId SetPieceId ObjectId".split()
)
EFFECT_OPS = {"set", "inc", "beat", "learn", "relocate", "promise", "improv", "hold"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMA_DOCS: dict[str, dict[str, Any]] = {
    p.name.removesuffix(".schema.json"): load_json(p) for p in sorted(SCHEMAS.glob("*.schema.json"))
}
REGISTRY: Registry[Any] = Registry().with_resources(
    (doc["$id"], Resource.from_contents(doc)) for doc in SCHEMA_DOCS.values()
)


def ref_of(type_name: str) -> str:
    return f"data/{FILE_OF[type_name]}.schema.json#/$defs/{type_name}"


def validator(ref: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": ref}, registry=REGISTRY)


def schema_def(type_name: str) -> dict[str, Any]:
    d: dict[str, Any] = SCHEMA_DOCS[FILE_OF[type_name]]["$defs"][type_name]
    return d


def walk(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}/{i}")


def _explain(e: ValidationError) -> list[ValidationError]:
    """Effect is a oneOf distinguished by op, and jsonschema only says "no branch matches".
    Report the errors in the branch whose op matches instead; if op is unknown, report op.

    Effect は op で区別する oneOf で、jsonschema は「どの分岐にも合わない」としか言わない。
    代わりに op が一致する分岐の中のエラーを報告する。op が未知なら op を報告する。
    """
    if e.validator != "oneOf" or not isinstance(e.instance, dict) or "op" not in e.instance:
        return [e]
    branches = [b.get("properties", {}).get("op", {}).get("const") for b in e.validator_value]
    same_op = [c for c in e.context or [] if branches[c.relative_schema_path[0]] == e.instance["op"]]
    if same_op:
        return same_op
    return [
        ValidationError(
            f"op {e.instance['op']!r} is not one of {branches} / "
            f"op {e.instance['op']!r} は {branches} のいずれでもない",
            validator="enum",
            path=[*e.path, "op"],
        )
    ]


def show(errors: list[ValidationError], where: str, limit: int = 20) -> str:
    shown = [x for e in errors for x in _explain(e)][:limit]
    return "\n".join(f"{where} {e.json_path}: {e.validator} {e.message[:200]}" for e in shown)


# —— 1. The Schemas themselves / Schema そのもの ——


def test_eight_files_with_the_agreed_defs() -> None:
    assert set(SCHEMA_DOCS) == set(TYPES_BY_FILE)
    for name, doc in SCHEMA_DOCS.items():
        assert doc["$id"] == f"data/{name}.schema.json"
        expected = set(TYPES_BY_FILE[name]) | (COMMON_DEFS if name == "common" else set())
        assert set(doc["$defs"]) == expected, name
        if name in MAIN_TYPE:
            assert doc["$ref"] == f"#/$defs/{MAIN_TYPE[name]}"
    assert sum(len(ts) for ts in TYPES_BY_FILE.values()) == 39


@pytest.mark.parametrize("name", sorted(SCHEMA_DOCS))
def test_valid_against_metaschema(name: str) -> None:
    Draft202012Validator.check_schema(SCHEMA_DOCS[name])


@pytest.mark.parametrize("name", sorted(SCHEMA_DOCS))
def test_refs_are_relative_and_resolve(name: str) -> None:
    doc = SCHEMA_DOCS[name]
    resolver = REGISTRY.resolver(base_uri=doc["$id"])
    refs = [(p, n["$ref"]) for p, n in walk(doc) if isinstance(n, dict) and isinstance(n.get("$ref"), str)]
    assert refs
    for path, ref in refs:
        assert "://" not in ref and not ref.startswith("/"), (
            f"{name}{path}: use relative references only / 相対参照のみを使う {ref}"
        )
        resolver.lookup(ref)  # Raises if it cannot be resolved / 解決できなければ例外を投げる


def test_titles_and_descriptions() -> None:
    for name, doc in SCHEMA_DOCS.items():
        for def_name, d in doc["$defs"].items():
            assert d.get("title") == ("StoryPromise" if def_name == "Promise" else def_name), f"{name}#{def_name}"
            assert d.get("description"), f"{name}#{def_name}"


# —— 2. Closed objects / オブジェクトが閉じていること ——


def test_every_object_is_closed() -> None:
    """Plain objects have additionalProperties: false (so the generated types are closed); a Record's
    additionalProperties is the Schema of its values. An intersection type built with allOf may only use
    unevaluatedProperties: false on the outer level (there are none now: sampleLines is written as a plain object).

    普通のオブジェクトには additionalProperties: false を書く（そうすれば生成される型も閉じる）。Record の
    additionalProperties は値の Schema。allOf で組み立てた交差型は外側でだけ unevaluatedProperties: false を使える
    （現在はない：sampleLines は普通のオブジェクトとして書いた）。
    """
    for name, doc in SCHEMA_DOCS.items():
        for path, node in walk(doc):
            # properties and $defs are maps from names to Schemas; if / then add conditional required fields
            # (promiseId in Event.effects, the fields required for Endings written from 1.6 on), not shapes
            # properties と $defs は名前から Schema への表。if / then は条件付きで必須を加えるもの（Event.effects の
            # promiseId、1.6 以降に書き込む Ending の必須フィールド）で、形ではない
            if not isinstance(node, dict) or path.endswith(("/properties", "/$defs", "/if", "/then")):
                continue
            if "allOf" in node:
                assert node.get("unevaluatedProperties") is False, (
                    f"{name}{path}: the outer level of allOf must be closed / allOf の外側は閉じる"
                )
                continue
            assert "unevaluatedProperties" not in node, (
                f"{name}{path}: only the outer level of allOf uses unevaluatedProperties / "
                "unevaluatedProperties は allOf の外側でだけ使う"
            )
            if node.get("type") == "object" or "properties" in node:
                extra = node.get("additionalProperties")
                if "properties" in node:
                    assert extra is False, (
                        f"{name}{path}: plain objects need additionalProperties: false / "
                        "普通のオブジェクトには additionalProperties: false を書く"
                    )
                else:
                    assert isinstance(extra, dict), (
                        f"{name}{path}: a Record needs the Schema of its values / Record には値の Schema を書く"
                    )


def test_sample_lines_keep_cite_fields() -> None:
    """sampleLines is Cite & { since?, until?, when? }, written as a plain object: when Cite gains a field, add it
    here too.

    sampleLines は Cite & { since?, until?, when? } で、普通のオブジェクトとして書いた：Cite にフィールドが増えたら
    ここにも加える。
    """
    item = schema_def("Character")["properties"]["speech"]["properties"]["sampleLines"]["items"]
    cite = schema_def("Cite")
    assert set(item["properties"]) == set(cite["properties"]) | {"since", "until", "when"}
    assert set(item["required"]) == set(cite["required"])
    for field in cite["properties"]:
        assert item["properties"][field] == {"$ref": f"common.schema.json#/$defs/Cite/properties/{field}"}


# —— 3. Comparison with contracts.md / contracts.md との突き合わせ ——


def _end_of_type(src: str, start: int) -> int:
    depth = 0
    for i in range(start, len(src)):
        ch = src[i]
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        elif ch == ";" and depth == 0:
            return i
    raise AssertionError(
        f"Type does not end with a semicolon / 型がセミコロンで終わっていない：{src[start : start + 60]!r}"
    )


def _split_top(src: str, sep: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in src:
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _fields(braced: str) -> dict[str, bool]:
    """'{ a: x; b?: y }' → {'a': required, 'b': optional}. Several fields on one line are also split by semicolons.

    '{ a: x; b?: y }' → {'a': 必須, 'b': 任意}。1 行に複数のフィールドを書いたものもセミコロンで分ける。
    """
    assert braced.startswith("{") and braced.endswith("}"), braced[:60]
    out: dict[str, bool] = {}
    for piece in _split_top(braced[1:-1], ";"):
        m = re.match(r"(\w+)(\?)?\s*:", piece)
        assert m, f"Cannot read the field / フィールドを読み取れない：{piece[:60]!r}"
        out[m.group(1)] = m.group(2) is None
    return out


def doc_types() -> dict[str, Any]:
    """Read every type X = … in the ```ts code blocks of contracts.md: object → {field: required?};
    union of objects (Effect) → {op: {field: required?}}; union of string literals (Activity) → set.

    contracts.md のすべての ```ts コードブロックにある type X = … を読む：オブジェクト → {フィールド: 必須か}。
    オブジェクトのユニオン（Effect）→ {op: {フィールド: 必須か}}。文字列リテラルのユニオン（Activity）→ set。
    """
    text = CONTRACTS_MD.read_text(encoding="utf-8")
    src = "\n".join(re.sub(r"//[^\n]*", "", block) for block in re.findall(r"```ts\n(.*?)```", text, re.S))
    types: dict[str, Any] = {}
    for m in re.finditer(r"\btype\s+(\w+)\s*=", src):
        body = src[m.end() : _end_of_type(src, m.end())].strip()
        name = m.group(1)
        assert name not in types, (
            f"{name} is defined twice in contracts.md / contracts.md で {name} が二重に定義されている"
        )
        if body.startswith("{") and len(_split_top(body, "|")) == 1:
            types[name] = _fields(body)
        elif body.lstrip("| ").startswith("{"):
            branches = {}
            for branch in _split_top(body, "|"):
                op = re.search(r'\bop:\s*"([^"]+)"', branch)
                assert op, branch[:60]
                branches[op.group(1)] = _fields(branch)
            types[name] = branches
        else:
            types[name] = set(re.findall(r'"([^"]+)"', body))
    return types


DOC_TYPES = doc_types()


def test_doc_and_schema_have_the_same_39_types() -> None:
    only_doc, only_schema = sorted(set(DOC_TYPES) - set(FILE_OF)), sorted(set(FILE_OF) - set(DOC_TYPES))
    assert not only_doc and not only_schema, (
        f"In the doc but not the Schema / ドキュメントにあり Schema にない：{only_doc}; "
        f"in the Schema but not the doc / Schema にありドキュメントにない：{only_schema}"
    )
    assert len(DOC_TYPES) == 39


def _compare(where: str, doc_fields: dict[str, bool], schema: dict[str, Any]) -> None:
    props = set(schema["properties"])
    required = set(schema.get("required", []))
    only_doc, only_schema = sorted(set(doc_fields) - props), sorted(props - set(doc_fields))
    assert not only_doc and not only_schema, (
        f"{where}: extra in the doc / ドキュメントに余分 {only_doc}, extra in the Schema / Schema に余分 {only_schema}"
    )
    doc_required = {f for f, req in doc_fields.items() if req}
    assert required == doc_required, (
        f"{where}: required fields differ / 必須が一致しない: doc / ドキュメント {sorted(doc_required)}, "
        f"Schema {sorted(required)}"
    )


@pytest.mark.parametrize("type_name", sorted(FILE_OF))
def test_fields_match_contracts_md(type_name: str) -> None:
    doc = DOC_TYPES[type_name]
    schema = schema_def(type_name)
    if isinstance(doc, set):
        assert set(schema["enum"]) == doc
    elif type_name == "Effect":
        branches = {b["properties"]["op"]["const"]: b for b in schema["oneOf"]}
        assert set(branches) == set(doc) == EFFECT_OPS
        for op, fields in doc.items():
            _compare(f"Effect.{op}", fields, branches[op])
    else:
        _compare(type_name, doc, schema)


# —— 4. Examples / 例 ——

# Why each invalid example fails: (keyword, error location). State it here for each new invalid example, so that it
# does not get rejected for some other reason and miss what it is meant to test.
# 反例が通らない理由：(キーワード, エラーの位置)。反例を追加したらここに明記する。そうしないと別の理由で拒否されて、
# テストしたいことがテストされない。
INVALID_BECAUSE: dict[str, tuple[str, str]] = {
    "Act/plan-with-label.json": ("additionalProperties", "plan"),
    "ActExit/arrival-without-line.json": ("required", "arrival"),
    "ActExit/sub-too-long.json": ("maxLength", "sub"),
    "Affordance/player-spot-uppercase.json": ("pattern", "playerSpot"),
    "Affordance/past-label-with-period.json": ("pattern", "pastLabel"),
    "Affordance/without-past-label.json": ("required", ""),
    "Character/sample-line-extra-field.json": ("additionalProperties", "speech/sampleLines/1"),
    "CheckResult/failed-rule-r8.json": ("enum", "failedRules/0"),
    "Cite/quote-81.json": ("maxLength", "quote"),
    "Effect/beat-to-skipped.json": ("enum", "to"),
    "Effect/op-teleport.json": ("const", "op"),
    "Effect/learn-nobody.json": ("anyOf", "character"),
    "Effect/relocate-spot-uppercase.json": ("pattern", "spot"),
    "Ending/card-title-empty.json": ("minLength", "card/title"),
    "Ending/character-lines-4.json": ("maxItems", "card/characterLines"),
    "Ending/character-lines-empty.json": ("minItems", "card/characterLines"),
    "Ending/v1.6-without-card.json": ("required", ""),
    "Ending/v1.6-without-did-for-you.json": ("required", "player"),
    "Ending/epilogue-empty-cites.json": ("minItems", "player/epilogue/0/cites"),
    "Event/event-id-prefix-evt.json": ("pattern", "eventId"),
    "Event/event-id-ulid-25.json": ("pattern", "eventId"),
    "Event/extra-field.json": ("additionalProperties", ""),
    "Event/idempotency-key-empty.json": ("minLength", "idempotencyKey"),
    "Event/missing-summary.json": ("required", ""),
    "Event/promise-without-id.json": ("required", "effects/0"),
    "Event/schema-version-1.16.json": ("enum", "schemaVersion"),
    "Event/t-fraction.json": ("type", "t"),
    "Event/t-negative.json": ("minimum", "t"),
    "MemoryItem/from-events-empty.json": ("minItems", "fromEvents"),
    "MemoryItem/trust-delta-25.json": ("maximum", "trustDelta"),
    "Relationship/level-6.json": ("enum", "level"),
    "SetPiece/learns-run-fact.json": ("pattern", "learns/0/fact"),
    "SetPiece/line-with-both.json": ("additionalProperties", "lines/0"),
    "SetPiece/lines-empty.json": ("minItems", "lines"),
    "SetPiece/on-act-push.json": ("enum", "on/act"),
    "StateVar/value-requires-without-note.json": ("required", "valueRequires/0"),
    "StateVar/value-requires-empty-when.json": ("minItems", "valueRequires/0/when"),
    "WorldObject/label-empty.json": ("minLength", "label"),
}


def examples(kind: str) -> list[Path]:
    return sorted((EXAMPLES / kind / "data").glob("*/*.json"))


def _all_errors(errors: list[ValidationError]) -> Iterator[ValidationError]:
    for e in errors:
        yield e
        yield from _all_errors(list(e.context or []))


@pytest.mark.parametrize("path", examples("valid"), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_valid_example_passes(path: Path) -> None:
    errors = list(validator(ref_of(path.parent.name)).iter_errors(load_json(path)))
    assert not errors, show(errors, path.name)


@pytest.mark.parametrize("path", examples("invalid"), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_invalid_example_fails_for_the_stated_reason(path: Path) -> None:
    key = f"{path.parent.name}/{path.name}"
    assert key in INVALID_BECAUSE, (
        f"{key}: state in INVALID_BECAUSE why it fails / なぜ通らないかを INVALID_BECAUSE に明記する"
    )
    keyword, where = INVALID_BECAUSE[key]
    errors = list(validator(ref_of(path.parent.name)).iter_errors(load_json(path)))
    assert errors, f"{key} should be rejected / {key} は拒否されるはず"
    found = {(e.validator, "/".join(map(str, e.absolute_path))) for e in _all_errors(errors)}
    assert (keyword, where) in found, (
        f"{key}: no {keyword} reported at {where!r}; got {sorted(found)} / "
        f"{where!r} で {keyword} が報告されていない。実際は {sorted(found)}"
    )


def test_examples_cover_the_card() -> None:
    valid = {p.parent.name for p in examples("valid")}
    invalid_keys = {f"{p.parent.name}/{p.name}" for p in examples("invalid")}
    assert valid | {p.parent.name for p in examples("invalid")} <= set(FILE_OF), (
        "Example directory names must be $defs type names / 例のディレクトリ名は $defs の型名にする"
    )
    # At least one for each main type (WorldModel uses world.json itself, see below);
    # also one each for Promise, RunFact, Relationship and CharacterEnding
    # 主な型ごとに少なくとも 1 つ（WorldModel は world.json そのものを使う。下を参照）。
    # Promise、RunFact、Relationship、CharacterEnding にもそれぞれ 1 つ
    must = (set(MAIN_TYPE.values()) - {"WorldModel"}) | {"Promise", "RunFact", "Relationship", "CharacterEnding"}
    assert must <= valid, sorted(must - valid)
    assert {"Fact", "Beat", "CausalEdge"} <= valid  # contracts.md section 6 / contracts.md 第 6 節
    ops = {load_json(p)["op"] for p in (EXAMPLES / "valid" / "data" / "Effect").glob("*.json")}
    assert ops == EFFECT_OPS
    assert invalid_keys == set(INVALID_BECAUSE)


# —— 5. Data files in the repo / リポジトリ内のデータファイル ——

WORLDS = sorted(REPO.glob("worlds/*/*/world.json"))
SCENARIOS = sorted(REPO.glob("worlds/*/*/scenarios.json"))
SEEDS = sorted(REPO.glob("evals/seeds/E*.jsonl"))
S2_DEV = REPO / "evals" / "s2" / "s2_dev.jsonl"


def test_data_files_exist() -> None:
    assert WORLDS and SCENARIOS and SEEDS and S2_DEV.exists()


@pytest.mark.parametrize("path", WORLDS, ids=lambda p: str(p.relative_to(REPO)))
def test_world_model(path: Path) -> None:
    errors = list(validator(ref_of("WorldModel")).iter_errors(load_json(path)))
    assert not errors, show(errors, path.name)


def _check_effects(effects: list[Any], where: str, problems: list[str]) -> None:
    v = validator(ref_of("Effect"))
    for i, effect in enumerate(effects):
        errors = list(v.iter_errors(effect))
        if errors:
            problems.append(show(errors, f"{where}.effects[{i}]", limit=3))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: str(p.relative_to(REPO)))
def test_scenario_effects(path: Path) -> None:
    problems: list[str] = []
    for sc in load_json(path):
        for j, event in enumerate(sc.get("events", [])):
            _check_effects(event["effects"], f"{sc['id']}.events[{j}]", problems)
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", SEEDS, ids=lambda p: p.name)
def test_seed_events(path: Path) -> None:
    """Events in the seeds are not complete Events (no eventId, seq, check): only check effects, and the character,
    kind and text of seeded memories.

    シードのイベントは完全な Event ではない（eventId、seq、check がない）：effects と、仕込む記憶の character、
    kind、text だけを検査する。
    """
    problems: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        for j, event in enumerate(case.get("setup", {}).get("events") or []):
            where = f"{case['id']}.setup.events[{j}]"
            _check_effects(event["effects"], where, problems)
            memory = event.get("memory")
            if memory is None:
                continue
            if set(memory) != {"character", "kind", "text"}:
                problems.append(
                    f"{where}.memory: fields should be character, kind, text; got {sorted(memory)} / "
                    f"フィールドは character、kind、text であるべきだが、実際は {sorted(memory)}"
                )
            for k in set(memory) & {"character", "kind", "text"}:
                errors = list(validator(f"{ref_of('MemoryItem')}/properties/{k}").iter_errors(memory[k]))
                if errors:
                    problems.append(show(errors, f"{where}.memory.{k}", limit=3))
    assert not problems, "\n".join(problems)


def test_s2_dev_candidates() -> None:
    """Candidate events have no eventId, seq or check yet; the fields they do have are checked against Event's
    fields of the same name, and effects against Effect (a promise effect's promiseId is only assigned at commit, so
    candidates do not have it, evals/s2/README.md).

    候補イベントにはまだ eventId、seq、check がない。あるフィールドは Event の同名フィールドで、effects は Effect で
    検査する（promise エフェクトの promiseId はコミット時に割り当てるので候補にはない。evals/s2/README.md）。
    """
    event_props = set(schema_def("Event")["properties"])
    problems: list[str] = []
    for line in S2_DEV.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        candidate = item["candidate"]
        unknown = set(candidate) - event_props
        if unknown:
            problems.append(
                f"{item['id']}: Event has no such fields / Event にこれらのフィールドはない {sorted(unknown)}"
            )
        for k, value in candidate.items():
            if k == "effects":
                _check_effects(value, item["id"], problems)
            elif k in event_props:
                errors = list(validator(f"{ref_of('Event')}/properties/{k}").iter_errors(value))
                if errors:
                    problems.append(show(errors, f"{item['id']}.{k}", limit=3))
    assert not problems, "\n".join(problems)
