"""`uv run contracts-gen`: regenerate all TypeScript and Python types from schemas/ (C-1).

- Data (schemas/data/) and API (schemas/api/) are each merged into one bundle holding only `$defs`, then handed to
  the generators: json-schema-to-typescript for TypeScript (gen/json2ts.mjs), datamodel-code-generator (pydantic v2)
  for Python.
- Where the API references a whole data type, the generated code uses the data-side type directly (`Data.X` in TS,
  imported from generated.data in Python); a JSON pointer into a field of a data type is expanded in place into that
  field's Schema.
- The generated files are committed; CI regenerates them and runs `git diff --exit-code`. Do not edit them by hand.

Needs node and json-schema-to-typescript installed by `pnpm install`.

`uv run contracts-gen`：schemas/ からすべての TypeScript と Python の型を再生成する（C-1）。

- データ（schemas/data/）と API（schemas/api/）をそれぞれ `$defs` だけを持つ 1 つの bundle にまとめ、生成器に渡す：
  TypeScript は json-schema-to-typescript（gen/json2ts.mjs）、Python は datamodel-code-generator（pydantic v2）。
- API がデータ型を丸ごと参照する箇所では、生成コードはデータ側の型をそのまま使う（TS では `Data.X`、Python では
  generated.data から import）。データ型の中のフィールドを指す JSON ポインタは、その場でそのフィールドの
  Schema に展開する。
- 生成物はリポジトリにコミットし、CI が再生成して `git diff --exit-code` を実行する。手で編集しないこと。

node と、`pnpm install` でインストールした json-schema-to-typescript が必要。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

PKG = Path(__file__).resolve().parents[2]  # packages/contracts
SCHEMAS = PKG / "schemas"
TS_OUT = PKG / "src" / "generated"
PY_OUT = PKG / "src" / "zoujin_contracts" / "generated"
PY_MODULE = "zoujin_contracts.generated"

TS_HEADER = (
    "// Generated file, do not edit by hand: change packages/contracts/schemas/ and run `uv run contracts-gen`.\n"
    "// 生成ファイル。手で編集しないこと：packages/contracts/schemas/ を変更して `uv run contracts-gen` を実行する。"
)
PY_HEADER = (
    "# Generated file, do not edit by hand: change packages/contracts/schemas/ and run `uv run contracts-gen`.\n"
    "# 生成ファイル。手で編集しないこと：packages/contracts/schemas/ を変更して `uv run contracts-gen` を実行する。"
)

# In Python, parse straight to the right class by type / name / kind (pydantic discriminated unions).
# Python では type / name / kind で一度に正しいクラスへ解析する（pydantic の discriminated union）。
DISCRIMINATORS = {
    "Effect": "op",
    "ClientMessage": "type",
    "ServerMessage": "type",
    "TelemetryEvent": "name",
    "VisibleEffect": "kind",
    "TimelineItem": "kind",
}

Json = Any
DEF_PTR = re.compile(r"^/\$defs/([A-Za-z0-9_]+)$")


def load_docs() -> dict[str, dict[str, Json]]:
    docs: dict[str, dict[str, Json]] = {}
    for path in sorted(SCHEMAS.rglob("*.schema.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        rel = path.relative_to(SCHEMAS).as_posix()
        if doc.get("$id") != rel:
            raise SystemExit(
                f"{rel}: $id should be {rel!r}, but is {doc.get('$id')!r} / "
                f"$id は {rel!r} であるべきだが、現在は {doc.get('$id')!r}"
            )
        docs[rel] = doc
    return docs


def split_ref(ref: str, base: str) -> tuple[str, str]:
    url, _, frag = ref.partition("#")
    return (urljoin(base, url) if url else base), frag


def get_pointer(doc: Json, pointer: str) -> Json:
    node = doc
    for part in pointer.lstrip("/").split("/") if pointer else []:
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def type_name(doc: dict[str, Json], name: str) -> str:
    """The name the generator gives a $defs entry: the title if there is one (e.g. Promise's title is StoryPromise).

    生成器が $defs の項目に付ける名前：title があれば title を使う（例：Promise の title は StoryPromise）。
    """
    title = doc["$defs"][name].get("title")
    return title if isinstance(title, str) else name


def is_ws_root(doc: dict[str, Json]) -> bool:
    return "oneOf" in doc and "$defs" in doc


# Keywords whose values are JSON data, not Schemas; but a field of the same name under properties (e.g.
# StateVar.default) is still a Schema.
# 値が Schema ではなく JSON データであるキーワード。ただし properties 内の同名のフィールド（例：StateVar.default）は
# Schema のまま。
DATA_KEYWORDS = ("const", "enum", "default", "examples")


def map_schema(node: dict[str, Json], f: Callable[[Json], Json]) -> dict[str, Json]:
    """Call f on each sub-Schema of a Schema object (values of DATA_KEYWORDS are kept as is).

    Schema オブジェクトの各サブ Schema に f を呼ぶ（DATA_KEYWORDS の値はそのまま残す）。
    """
    out: dict[str, Json] = {}
    for k, v in node.items():
        if k in DATA_KEYWORDS:
            out[k] = v
        elif k in ("properties", "patternProperties", "$defs", "dependentSchemas") and isinstance(v, dict):
            out[k] = {name: f(sub) for name, sub in v.items()}
        else:
            out[k] = f(v)
    return out


# external(doc_id, def_name) -> the Schema to substitute; returning None = not an external type
# external(doc_id, def_name) -> 置き換え先の Schema。None を返す = 外部の型ではない
External = Callable[[str, str], dict[str, Json] | None]


def bundle(
    docs: dict[str, dict[str, Json]], prefix: str, title: str, external: External, wrap_refs: bool = False
) -> dict[str, Json]:
    """Merge the $defs of all files under prefix into one bundle.

    wrap_refs: rewrite internal $refs that carry a description into a one-element allOf (when a $ref has other keys
    next to it, json-schema-to-typescript copies it into a duplicate type such as `X1`).

    prefix 配下のすべてのファイルの $defs を 1 つの bundle にまとめる。

    wrap_refs：説明付きの内部 $ref を allOf で 1 層包む形に書き換える（json-schema-to-typescript は $ref の横に
    別のキーがあると `X1` のような重複した型を作ってしまう）。
    """
    members = [k for k in docs if k.startswith(prefix)]
    defs: dict[str, Json] = {}
    owner: dict[str, str] = {}

    def add(name: str, schema: Json, doc_id: str) -> None:
        if name in defs:
            raise SystemExit(
                f"Duplicate $defs name: {name} ({owner[name]} and {doc_id}) / "
                f"$defs の名前が重複：{name}（{owner[name]} と {doc_id}）"
            )
        defs[name] = schema
        owner[name] = doc_id

    def rewrite(node: Json, base: str) -> Json:
        if isinstance(node, list):
            return [rewrite(v, base) for v in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            siblings = {k: rewrite(v, base) for k, v in node.items() if k != "$ref"}
            doc_id, pointer = split_ref(node["$ref"], base)
            m = DEF_PTR.match(pointer)
            local = None
            if doc_id in members and m:
                local = f"#/$defs/{type_name(docs[doc_id], m.group(1))}"
            elif doc_id in members and pointer == "" and is_ws_root(docs[doc_id]):
                local = f"#/$defs/{docs[doc_id]['title']}"
            if local is not None:
                if wrap_refs and siblings:
                    return {**siblings, "allOf": [{"$ref": local}]}
                return {"$ref": local, **siblings}
            if m and (ext := external(doc_id, m.group(1))) is not None:
                return {**siblings, **ext}
            target = rewrite(get_pointer(docs[doc_id], pointer), doc_id)
            target.pop("title", None)
            return {**target, **siblings}
        return map_schema(node, lambda v: rewrite(v, base))

    for doc_id in members:
        doc = docs[doc_id]
        for name, schema in doc.get("$defs", {}).items():
            add(type_name(doc, name), rewrite(schema, doc_id), doc_id)
        if is_ws_root(doc):
            add(
                doc["title"],
                {"title": doc["title"], "description": doc["description"], "oneOf": rewrite(doc["oneOf"], doc_id)},
                doc_id,
            )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "$defs": dict(sorted(defs.items())),
    }


def ts_external(docs: dict[str, dict[str, Json]]) -> External:
    def ext(doc_id: str, name: str) -> dict[str, Json] | None:
        if not doc_id.startswith("data/"):
            return None
        return {"tsType": f"Data.{type_name(docs[doc_id], name)}"}

    return ext


def py_external(docs: dict[str, dict[str, Json]], defined: set[str]) -> External:
    def ext(doc_id: str, name: str) -> dict[str, Json] | None:
        if not doc_id.startswith("data/"):
            return None
        py_name = type_name(docs[doc_id], name)
        if py_name not in defined:
            # The generator folded it into the places that use it (a simple type), so expand it in place here too
            # 生成器が使用箇所に畳み込んだ（単純な型）ので、ここでもその場で展開する
            return None
        return {"customTypePath": f"{PY_MODULE}.data.{py_name}"}

    return ext


def py_names(path: Path) -> set[str]:
    """Which types the generated module defines at top level.

    生成されたモジュールのトップレベルで定義されている型。
    """
    return set(re.findall(r"^(?:class|type) (\w+)", path.read_text(encoding="utf-8"), re.M))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"Failed / 失敗：{' '.join(cmd[:3])} …")


def closed_tuples(node: Json) -> Json:
    """Rewrite fixed-length tuples (`prefixItems` plus `items: false`, e.g. the data's Clock.labels.bands) into a
    draft-07 `items` array.

    Neither generator understands `prefixItems`: json-schema-to-typescript emits `never[]`, and
    datamodel-code-generator emits an unbounded array of the union. After the rewrite TS gets `[number, string]` and
    Python an array of fixed length 2. Only the bundle fed to the generators changes; the Schema stays as is.

    固定長のタプル（`prefixItems` と `items: false`。例：データの Clock.labels.bands）を draft-07 の `items` 配列に
    書き換える。

    どちらの生成器も `prefixItems` を理解しない：json-schema-to-typescript は `never[]` を、
    datamodel-code-generator は長さ無制限のユニオンの配列を生成する。書き換え後は TS が `[number, string]`、
    Python が長さ 2 固定の配列になる。変えるのは生成器に渡す bundle だけで、Schema はそのまま。
    """
    if isinstance(node, list):
        return [closed_tuples(v) for v in node]
    if not isinstance(node, dict):
        return node
    out = map_schema(node, closed_tuples)
    if "prefixItems" in out:
        items = out.pop("prefixItems")
        assert isinstance(items, list)
        if out.get("items") is not False or out.get("minItems") != len(items):
            raise SystemExit(
                "Only fixed-length tuples are handled: prefixItems needs items: false and minItems equal to the "
                "number of elements / 固定長のタプルのみ扱う：prefixItems には items: false が必要で、"
                "minItems は要素数と等しくなければならない"
            )
        out.update(items=items, additionalItems=False, maxItems=len(items))
    return out


SHAPE_KEYWORDS = {"type", "$ref", "enum", "const", "properties", "items", "oneOf", "anyOf", "allOf", "tsType"}


def ts_unknown_for_any(node: Json) -> Json:
    """Mark untyped fields (description only, e.g. StateVar.default) explicitly as `unknown`.

    For such a field named `default`, json-schema-to-typescript would emit `{[k: string]: unknown}`.

    型の制約がないフィールド（説明のみ。例：StateVar.default）を明示的に `unknown` にする。

    json-schema-to-typescript は `default` という名前のこうしたフィールドを `{[k: string]: unknown}` として
    生成してしまう。
    """
    if isinstance(node, list):
        return [ts_unknown_for_any(v) for v in node]
    if not isinstance(node, dict):
        return node
    out = map_schema(node, ts_unknown_for_any)
    if isinstance(out.get("properties"), dict):
        for key, sub in out["properties"].items():
            if isinstance(sub, dict) and not SHAPE_KEYWORDS & sub.keys():
                out["properties"][key] = {**sub, "tsType": "unknown"}
    return out


def gen_ts(bundles: dict[str, dict[str, Json]], tmp: Path) -> None:
    node = shutil.which("node")
    if node is None:
        raise SystemExit(
            "node not found: install Node (.nvmrc) first and run pnpm install at the repo root / "
            "node が見つからない：先に Node（.nvmrc）をインストールし、リポジトリのルートで pnpm install を実行する"
        )
    TS_OUT.mkdir(parents=True, exist_ok=True)
    for name, b in bundles.items():
        src = tmp / f"{name}.ts.json"
        src.write_text(json.dumps(ts_unknown_for_any(closed_tuples(b)), ensure_ascii=False), encoding="utf-8")
        header = TS_HEADER
        if name == "api":
            header += '\nimport type * as Data from "./data";\n'
        run([node, str(PKG / "gen" / "json2ts.mjs"), str(src), str(TS_OUT / f"{name}.ts"), header], cwd=PKG)


def with_discriminators(b: dict[str, Json]) -> dict[str, Json]:
    """Add a discriminator to the unions in DISCRIMINATORS.

    Inline branches (the data's Effect) are pulled out and named after the discriminating field's value
    (EffectSet, EffectBeat…); otherwise the generator names them Effect1…Effect8 and drops the union's own name.

    DISCRIMINATORS にあるユニオンに discriminator を付ける。

    その場で書かれた分岐（データの Effect）は取り出して、判別フィールドの値で名前を付ける（EffectSet、EffectBeat…）。
    そうしないと生成器は Effect1…Effect8 と名付け、ユニオン自体の名前も残さない。
    """
    defs = b["$defs"]
    for name, prop in DISCRIMINATORS.items():
        if name not in defs:
            continue
        union = defs[name]
        for n, branch in enumerate(union["oneOf"]):
            if "$ref" in branch:
                continue
            value = branch["properties"][prop]["const"]
            branch_name = name + "".join(w.capitalize() for w in re.split(r"[^A-Za-z0-9]+", value))
            if branch_name in defs:
                raise SystemExit(
                    f"Duplicate $defs name: {branch_name} (the {prop}={value!r} branch of {name}) / "
                    f"$defs の名前が重複：{branch_name}（{name} の {prop}={value!r} の分岐）"
                )
            defs[branch_name] = branch
            union["oneOf"][n] = {"$ref": f"#/$defs/{branch_name}"}
        union["discriminator"] = {"propertyName": prop}
    b["$defs"] = dict(sorted(defs.items()))
    return b


def pascal(s: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w)


def name_inline_objects(b: dict[str, Json]) -> dict[str, Json]:
    """Name inline objects by position (e.g. the items of player.relationships in Ending →
    EndingPlayerRelationshipsItem).

    Otherwise the generator names them by field name, and on a clash with $defs it appends a number to the $defs one
    (the data's Relationship would become Relationship1), and which one gets the number shifts as the Schema changes.
    Objects inside if / then / else / not are only conditions; the generator ignores them, so they are not named.

    その場で書かれたオブジェクトに位置で名前を付ける（例：Ending の player.relationships の要素 →
    EndingPlayerRelationshipsItem）。

    そうしないと生成器はフィールド名で名前を付け、$defs と重複したときは $defs 側に番号を付けてしまう（データの
    Relationship が Relationship1 になる）。しかもどちらに番号が付くかは Schema によって変わる。if / then / else / not
    の中は条件にすぎず、生成器は見ないので名前を付けない。
    """
    taken = set(b["$defs"])

    def visit(node: Json, name: str, top: bool) -> None:
        if not isinstance(node, dict) or "$ref" in node:
            return
        if not top and "properties" in node and "title" not in node:
            if name in taken:
                raise SystemExit(
                    f"The name of an inline object clashes with another type: {name} / "
                    f"その場のオブジェクトの名前がほかの型と重複：{name}"
                )
            node["title"] = name
            taken.add(name)
        for key, sub in node.get("properties", {}).items():
            visit(sub, name + pascal(key), False)
        visit(node.get("items"), name + "Item", False)
        visit(node.get("additionalProperties"), name + "Value", False)
        for key in ("oneOf", "anyOf", "allOf"):
            for n, sub in enumerate(node.get(key, [])):
                visit(sub, f"{name}Option{n + 1}", False)

    for def_name, schema in b["$defs"].items():
        visit(schema, def_name, True)
    return b


def gen_py(docs: dict[str, dict[str, Json]], tmp: Path) -> None:
    exe = Path(sys.executable).with_name("datamodel-codegen")
    PY_OUT.mkdir(parents=True, exist_ok=True)
    for name in ("data", "api"):
        if name == "data":
            b = bundle(docs, "data/", "DataBundle", lambda _d, _n: None)
        else:
            b = bundle(docs, "api/", "ApiBundle", py_external(docs, py_names(PY_OUT / "data.py")))
        src = tmp / f"{name}.py.json"
        b = name_inline_objects(with_discriminators(b))
        src.write_text(json.dumps(closed_tuples(b), ensure_ascii=False), encoding="utf-8")
        out = PY_OUT / f"{name}.py"
        run(
            [
                str(exe),
                "--input",
                str(src),
                "--input-file-type",
                "jsonschema",
                "--output",
                str(out),
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--target-python-version",
                "3.13",
                "--use-annotated",
                "--field-constraints",
                "--use-standard-collections",
                "--use-union-operator",
                "--disable-timestamp",
                "--use-title-as-name",
                "--use-schema-description",
                "--use-field-description",
                "--use-type-alias",
                "--allow-population-by-field-name",
                "--target-pydantic-version",
                "2.11",
                "--naming-strategy",
                "primary-first",
                "--enum-field-as-literal",
                "all",
                "--use-one-literal-as-default",
                "--formatters",
                "builtin",
                "--custom-file-header",
                PY_HEADER,
            ]
        )
        strip_py_root(out, b["title"])
    (PY_OUT / "__init__.py").write_text(
        f'{PY_HEADER}\n"""Pydantic models generated from schemas/: data (data contracts), api (API),\n'
        "binary (frame format).\n\n"
        'schemas/ から生成した pydantic モデル：data（データ契約）、api（API）、binary（フレーム形式）。\n"""\n'
    )


def strip_py_root(path: Path, root: str) -> None:
    """The bundle's root is only a container, so delete the generated root type.

    bundle のルートは入れ物にすぎないので、生成されたルートの型を削除する。
    """
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [n for n, line in enumerate(lines) if line.startswith((f"type {root} =", f"class {root}("))]
    if len(starts) != 1:
        raise SystemExit(f"{path.name}: root type {root} not found / ルートの型 {root} が見つからない")
    end = starts[0] + 1
    while end < len(lines) and (not lines[end] or lines[end][0] in " ])"):
        end += 1
    path.write_text("\n".join(lines[: starts[0]] + lines[end:]), encoding="utf-8")


def gen_binary() -> None:
    spec = json.loads((SCHEMAS / "api" / "binary.json").read_text(encoding="utf-8"))
    consts = {
        "HEADER_BYTES": spec["headerBytes"],
        "MIC_UP": spec["types"]["micUp"]["byte"],
        "MIC_UP_SAMPLE_RATE_HZ": spec["types"]["micUp"]["sampleRateHz"],
        "MIC_UP_FRAME_MS": spec["types"]["micUp"]["frameMs"],
        "MIC_UP_FRAME_BYTES": spec["types"]["micUp"]["frameBytes"],
        "CHARACTER_DOWN": spec["types"]["characterDown"]["byte"],
        "CHARACTER_DOWN_SAMPLE_RATE_HZ": spec["types"]["characterDown"]["sampleRateHz"],
        "CLIENT_TURN_SEQ_MAX": spec["clientTurnSeqMax"],
        "SERVER_TURN_SEQ_MIN": spec["serverTurnSeqMin"],
    }
    doc = spec["description"]
    py = [PY_HEADER, f'"""{doc}"""', ""] + [f"{k} = {v}" for k, v in consts.items()]
    (PY_OUT / "binary.py").write_text("\n".join(py) + "\n", encoding="utf-8")
    ts = [TS_HEADER, f"// {doc}", ""] + [f"export const {k} = {v};" for k, v in consts.items()]
    (TS_OUT / "binary.ts").write_text("\n".join(ts) + "\n", encoding="utf-8")


def ruff(paths: list[Path]) -> None:
    exe = Path(sys.executable).with_name("ruff")
    args = [str(p) for p in paths]
    run([str(exe), "format", "--quiet", *args], cwd=PKG.parents[1])
    run([str(exe), "check", "--fix", "--quiet", *args], cwd=PKG.parents[1])
    run([str(exe), "format", "--quiet", *args], cwd=PKG.parents[1])


def main() -> None:
    docs = load_docs()
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        gen_ts(
            {
                "data": bundle(docs, "data/", "DataBundle", lambda _d, _n: None, wrap_refs=True),
                "api": bundle(docs, "api/", "ApiBundle", ts_external(docs), wrap_refs=True),
            },
            tmp,
        )
        gen_py(docs, tmp)
    gen_binary()
    ruff([PY_OUT])
    print(f"Generated / 生成済み：{TS_OUT.relative_to(PKG)}/, {PY_OUT.relative_to(PKG)}/")


if __name__ == "__main__":
    main()
