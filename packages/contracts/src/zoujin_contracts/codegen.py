"""`uv run contracts-gen`：从 schemas/ 重新生成全部 TypeScript 和 Python 类型（C-1）。

- 数据（schemas/data/）和接口（schemas/api/）各拼成一个只有 `$defs` 的 bundle，再交给生成器：
  TypeScript 用 json-schema-to-typescript（gen/json2ts.mjs），Python 用 datamodel-code-generator（pydantic v2）。
- 接口整个引用数据类型的地方，生成的代码直接用数据那边的类型（TS 里是 `Data.X`，Python 从 generated.data 导入）；
  指到数据类型里某个字段的 JSON 指针，就地展开成那个字段的 Schema。
- 生成物提交进仓库，CI 重新生成后 `git diff --exit-code`；不要手改。

需要 node 和 `pnpm install` 装好的 json-schema-to-typescript。
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

TS_HEADER = "// 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。"
PY_HEADER = "# 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。"

# Python 里按 type / name / kind 一次解析到对的类（pydantic 的 discriminated union）。
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
            raise SystemExit(f"{rel}: $id 应该是 {rel!r}，现在是 {doc.get('$id')!r}")
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
    """生成器给一个 $defs 条目起的名字：有 title 用 title（例：Promise 的 title 是 StoryPromise）。"""
    title = doc["$defs"][name].get("title")
    return title if isinstance(title, str) else name


def is_ws_root(doc: dict[str, Json]) -> bool:
    return "oneOf" in doc and "$defs" in doc


# 值是 JSON 数据、不是 Schema 的关键字；但 properties 里同名的字段（例：StateVar.default）还是 Schema。
DATA_KEYWORDS = ("const", "enum", "default", "examples")


def map_schema(node: dict[str, Json], f: Callable[[Json], Json]) -> dict[str, Json]:
    """对一个 Schema 对象的子 Schema 逐个调用 f（DATA_KEYWORDS 的值原样留着）。"""
    out: dict[str, Json] = {}
    for k, v in node.items():
        if k in DATA_KEYWORDS:
            out[k] = v
        elif k in ("properties", "patternProperties", "$defs", "dependentSchemas") and isinstance(v, dict):
            out[k] = {name: f(sub) for name, sub in v.items()}
        else:
            out[k] = f(v)
    return out


# external(doc_id, def_name) -> 替换成的 Schema；返回 None = 不是外部类型
External = Callable[[str, str], dict[str, Json] | None]


def bundle(
    docs: dict[str, dict[str, Json]], prefix: str, title: str, external: External, wrap_refs: bool = False
) -> dict[str, Json]:
    """把 prefix 下全部文件的 $defs 拼成一个 bundle。

    wrap_refs：带说明的内部 $ref 改写成 allOf 包一层（json-schema-to-typescript 遇到 $ref 旁边有别的键会复制出
    `X1` 这样的重复类型）。
    """
    members = [k for k in docs if k.startswith(prefix)]
    defs: dict[str, Json] = {}
    owner: dict[str, str] = {}

    def add(name: str, schema: Json, doc_id: str) -> None:
        if name in defs:
            raise SystemExit(f"$defs 重名：{name}（{owner[name]} 和 {doc_id}）")
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
            return None  # 生成器把它折进了用到它的地方（简单类型），这里也就地展开
        return {"customTypePath": f"{PY_MODULE}.data.{py_name}"}

    return ext


def py_names(path: Path) -> set[str]:
    """生成的模块顶层定义了哪些类型。"""
    return set(re.findall(r"^(?:class|type) (\w+)", path.read_text(encoding="utf-8"), re.M))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"失败：{' '.join(cmd[:3])} …")


SHAPE_KEYWORDS = {"type", "$ref", "enum", "const", "properties", "items", "oneOf", "anyOf", "allOf", "tsType"}


def ts_unknown_for_any(node: Json) -> Json:
    """不限类型的字段（只有说明，例：StateVar.default）写明 `unknown`。

    json-schema-to-typescript 遇到名叫 `default` 的这种字段会生成成 `{[k: string]: unknown}`。
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
        raise SystemExit("找不到 node：先装 Node（.nvmrc）并在仓库根目录 pnpm install")
    TS_OUT.mkdir(parents=True, exist_ok=True)
    for name, b in bundles.items():
        src = tmp / f"{name}.ts.json"
        src.write_text(json.dumps(ts_unknown_for_any(b), ensure_ascii=False), encoding="utf-8")
        header = TS_HEADER
        if name == "api":
            header += '\nimport type * as Data from "./data";\n'
        run([node, str(PKG / "gen" / "json2ts.mjs"), str(src), str(TS_OUT / f"{name}.ts"), header], cwd=PKG)


def with_discriminators(b: dict[str, Json]) -> dict[str, Json]:
    """给 DISCRIMINATORS 里的联合加 discriminator。

    就地写的分支（数据的 Effect）提出来按区分字段的值起名（EffectSet、EffectBeat…），
    不然生成器起成 Effect1…Effect8，也不保留联合本身的名字。
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
                raise SystemExit(f"$defs 重名：{branch_name}（{name} 的 {prop}={value!r} 分支）")
            defs[branch_name] = branch
            union["oneOf"][n] = {"$ref": f"#/$defs/{branch_name}"}
        union["discriminator"] = {"propertyName": prop}
    b["$defs"] = dict(sorted(defs.items()))
    return b


def pascal(s: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w)


def name_inline_objects(b: dict[str, Json]) -> dict[str, Json]:
    """就地写的对象按位置起名（例：Ending 里 player.relationships 的元素 → EndingPlayerRelationshipsItem）。

    不然生成器按字段名起名，和 $defs 重名时给 $defs 那个加数字（数据的 Relationship 会变成 Relationship1），
    哪个带数字还随 Schema 变。if / then / else / not 里的只是条件，生成器不看，不起名。
    """
    taken = set(b["$defs"])

    def visit(node: Json, name: str, top: bool) -> None:
        if not isinstance(node, dict) or "$ref" in node:
            return
        if not top and "properties" in node and "title" not in node:
            if name in taken:
                raise SystemExit(f"就地对象的名字和别的类型重名：{name}")
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
        src.write_text(json.dumps(name_inline_objects(with_discriminators(b)), ensure_ascii=False), encoding="utf-8")
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
        f'{PY_HEADER}\n"""从 schemas/ 生成的 pydantic 模型：data（数据契约）、api（接口）、binary（帧格式）。"""\n'
    )


def strip_py_root(path: Path, root: str) -> None:
    """bundle 的根只是个容器，生成的根类型删掉。"""
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [n for n, line in enumerate(lines) if line.startswith((f"type {root} =", f"class {root}("))]
    if len(starts) != 1:
        raise SystemExit(f"{path.name}：没找到根类型 {root}")
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
    print(f"已生成：{TS_OUT.relative_to(PKG)}/、{PY_OUT.relative_to(PKG)}/")


if __name__ == "__main__":
    main()
