"""数据契约的 JSON Schema（C-2）：元 Schema、例子、和 contracts.md 对照、对象关死、校验仓库里的数据文件。

不联网：8 个 Schema 之间只用相对 $ref，全部从本地文件装进 registry。
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

# 8 个文件和各自的 $defs（C-2 卡的表）。common 另有公共定义（ID、时间等），不是 contracts.md 的类型，不参加对照。
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
    """Effect 是按 op 区分的 oneOf，jsonschema 只说「哪个分支都不合」。
    改报 op 对上的那个分支里的错；op 不认识就报 op。"""
    if e.validator != "oneOf" or not isinstance(e.instance, dict) or "op" not in e.instance:
        return [e]
    branches = [b.get("properties", {}).get("op", {}).get("const") for b in e.validator_value]
    same_op = [c for c in e.context or [] if branches[c.relative_schema_path[0]] == e.instance["op"]]
    if same_op:
        return same_op
    return [ValidationError(f"op {e.instance['op']!r} 不是 {branches} 之一", validator="enum", path=[*e.path, "op"])]


def show(errors: list[ValidationError], where: str, limit: int = 20) -> str:
    shown = [x for e in errors for x in _explain(e)][:limit]
    return "\n".join(f"{where} {e.json_path}: {e.validator} {e.message[:200]}" for e in shown)


# —— 1. Schema 本身 ——


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
        assert "://" not in ref and not ref.startswith("/"), f"{name}{path}: 只用相对引用 {ref}"
        resolver.lookup(ref)  # 解析不了会抛异常


def test_titles_and_descriptions() -> None:
    for name, doc in SCHEMA_DOCS.items():
        for def_name, d in doc["$defs"].items():
            assert d.get("title") == ("StoryPromise" if def_name == "Promise" else def_name), f"{name}#{def_name}"
            assert d.get("description"), f"{name}#{def_name}"


# —— 2. 对象关死 ——


def test_every_object_is_closed() -> None:
    """普通对象写 additionalProperties: false（生成的类型才是关死的）；Record 的 additionalProperties 是值的 Schema。
    allOf 拼出来的交叉类型只能在外层用 unevaluatedProperties: false（现在没有：sampleLines 写成了普通对象）。"""
    for name, doc in SCHEMA_DOCS.items():
        for path, node in walk(doc):
            # properties、$defs 是名字到 Schema 的表；if / then 是按条件加的必填（Event.effects 的 promiseId、
            # 1.6 起写入的 Ending 必写的字段），不是形状
            if not isinstance(node, dict) or path.endswith(("/properties", "/$defs", "/if", "/then")):
                continue
            if "allOf" in node:
                assert node.get("unevaluatedProperties") is False, f"{name}{path}: allOf 的外层要关死"
                continue
            assert "unevaluatedProperties" not in node, f"{name}{path}: 只有 allOf 的外层用 unevaluatedProperties"
            if node.get("type") == "object" or "properties" in node:
                extra = node.get("additionalProperties")
                if "properties" in node:
                    assert extra is False, f"{name}{path}: 普通对象要写 additionalProperties: false"
                else:
                    assert isinstance(extra, dict), f"{name}{path}: Record 要写值的 Schema"


def test_sample_lines_keep_cite_fields() -> None:
    """sampleLines 是 Cite & { since?, until?, when? }，写成了普通对象：Cite 加字段时这里要跟着加。"""
    item = schema_def("Character")["properties"]["speech"]["properties"]["sampleLines"]["items"]
    cite = schema_def("Cite")
    assert set(item["properties"]) == set(cite["properties"]) | {"since", "until", "when"}
    assert set(item["required"]) == set(cite["required"])
    for field in cite["properties"]:
        assert item["properties"][field] == {"$ref": f"common.schema.json#/$defs/Cite/properties/{field}"}


# —— 3. 和 contracts.md 对照 ——


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
    raise AssertionError(f"类型没有以分号结束：{src[start : start + 60]!r}")


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
    """'{ a: x; b?: y }' → {'a': 必填, 'b': 可选}。一行写几个字段的也按分号拆开。"""
    assert braced.startswith("{") and braced.endswith("}"), braced[:60]
    out: dict[str, bool] = {}
    for piece in _split_top(braced[1:-1], ";"):
        m = re.match(r"(\w+)(\?)?\s*:", piece)
        assert m, f"读不出字段：{piece[:60]!r}"
        out[m.group(1)] = m.group(2) is None
    return out


def doc_types() -> dict[str, Any]:
    """读 contracts.md 里全部 ```ts 代码块的 type X = …：对象 → {字段: 是否必填}；
    对象的联合（Effect）→ {op: {字段: 是否必填}}；字符串字面量的联合（Activity）→ set。"""
    text = CONTRACTS_MD.read_text(encoding="utf-8")
    src = "\n".join(re.sub(r"//[^\n]*", "", block) for block in re.findall(r"```ts\n(.*?)```", text, re.S))
    types: dict[str, Any] = {}
    for m in re.finditer(r"\btype\s+(\w+)\s*=", src):
        body = src[m.end() : _end_of_type(src, m.end())].strip()
        name = m.group(1)
        assert name not in types, f"contracts.md 里 {name} 定义了两次"
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
    assert not only_doc and not only_schema, f"文档有、Schema 没有：{only_doc}；Schema 有、文档没有：{only_schema}"
    assert len(DOC_TYPES) == 39


def _compare(where: str, doc_fields: dict[str, bool], schema: dict[str, Any]) -> None:
    props = set(schema["properties"])
    required = set(schema.get("required", []))
    only_doc, only_schema = sorted(set(doc_fields) - props), sorted(props - set(doc_fields))
    assert not only_doc and not only_schema, f"{where}：文档多 {only_doc}，Schema 多 {only_schema}"
    doc_required = {f for f, req in doc_fields.items() if req}
    assert required == doc_required, f"{where}：必填对不上，文档 {sorted(doc_required)}，Schema {sorted(required)}"


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


# —— 4. 例子 ——

# 反例为什么不过：(关键字, 出错位置)。新加反例要在这里写明，免得它因为别的原因被拒、测不到想测的东西。
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
    "Event/schema-version-1.10.json": ("enum", "schemaVersion"),
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
    assert key in INVALID_BECAUSE, f"{key}：在 INVALID_BECAUSE 里写明它为什么不过"
    keyword, where = INVALID_BECAUSE[key]
    errors = list(validator(ref_of(path.parent.name)).iter_errors(load_json(path)))
    assert errors, f"{key} 应该被拒"
    found = {(e.validator, "/".join(map(str, e.absolute_path))) for e in _all_errors(errors)}
    assert (keyword, where) in found, f"{key}：没有在 {where!r} 报 {keyword}，实际 {sorted(found)}"


def test_examples_cover_the_card() -> None:
    valid = {p.parent.name for p in examples("valid")}
    invalid_keys = {f"{p.parent.name}/{p.name}" for p in examples("invalid")}
    assert valid | {p.parent.name for p in examples("invalid")} <= set(FILE_OF), "例子目录名要是 $defs 的类型名"
    # 每个主类型至少一个（WorldModel 用 world.json 本身，见下面）；
    # Promise、RunFact、Relationship、CharacterEnding 也各一个
    must = (set(MAIN_TYPE.values()) - {"WorldModel"}) | {"Promise", "RunFact", "Relationship", "CharacterEnding"}
    assert must <= valid, sorted(must - valid)
    assert {"Fact", "Beat", "CausalEdge"} <= valid  # contracts.md 第 6 节
    ops = {load_json(p)["op"] for p in (EXAMPLES / "valid" / "data" / "Effect").glob("*.json")}
    assert ops == EFFECT_OPS
    assert invalid_keys == set(INVALID_BECAUSE)


# —— 5. 仓库里的数据文件 ——

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
    """种子里的事件不是完整的 Event（没有 eventId、seq、check）：只查 effects，和种的记忆的 character、kind、text。"""
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
                problems.append(f"{where}.memory：字段应是 character、kind、text，实际 {sorted(memory)}")
            for k in set(memory) & {"character", "kind", "text"}:
                errors = list(validator(f"{ref_of('MemoryItem')}/properties/{k}").iter_errors(memory[k]))
                if errors:
                    problems.append(show(errors, f"{where}.memory.{k}", limit=3))
    assert not problems, "\n".join(problems)


def test_s2_dev_candidates() -> None:
    """候选事件还没有 eventId、seq、check；有的字段按 Event 的同名字段查，effects 按 Effect 查
    （promise 效果的 promiseId 提交时才分配，候选里没有，evals/s2/README.md）。"""
    event_props = set(schema_def("Event")["properties"])
    problems: list[str] = []
    for line in S2_DEV.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        candidate = item["candidate"]
        unknown = set(candidate) - event_props
        if unknown:
            problems.append(f"{item['id']}：Event 没有这些字段 {sorted(unknown)}")
        for k, value in candidate.items():
            if k == "effects":
                _check_effects(value, item["id"], problems)
            elif k in event_props:
                errors = list(validator(f"{ref_of('Event')}/properties/{k}").iter_errors(value))
                if errors:
                    problems.append(show(errors, f"{item['id']}.{k}", limit=3))
    assert not problems, "\n".join(problems)
