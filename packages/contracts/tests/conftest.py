"""Shared pieces of the contract tests (C-1): read every Schema, build a referencing Registry by $id, and map each
example's directory to the Schema it is validated against.

契約テストの共通部分（C-1）：すべての Schema を読み込み、$id ごとに referencing の Registry を作り、ディレクトリから
各例を検証する Schema を決める。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

PKG = Path(__file__).resolve().parents[1]
SCHEMAS = PKG / "schemas"
EXAMPLES = PKG / "examples"
REPO = PKG.parents[1]

Json = Any


def load(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def walk(node: Json, path: str = "") -> Iterator[tuple[str, Json]]:
    """Walk a Schema depth-first, yielding (JSON pointer, child node).

    Schema を深さ優先でたどり、（JSON ポインタ, 子ノード）を返す。
    """
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for n, v in enumerate(node):
            yield from walk(v, f"{path}/{n}")


@dataclass
class Contracts:
    """Tests get this through the `contracts` fixture (test files cannot import conftest under
    --import-mode=importlib).

    テストは fixture `contracts` でこれを受け取る（--import-mode=importlib ではテストファイルから conftest を import
    できない）。
    """

    docs: dict[str, dict[str, Json]] = field(default_factory=dict)
    walk = staticmethod(walk)
    load_json = staticmethod(load)
    repo = REPO
    schemas_dir = SCHEMAS
    examples_dir = EXAMPLES

    @classmethod
    def load(cls) -> Contracts:
        c = cls()
        for p in sorted(SCHEMAS.rglob("*.schema.json")):
            c.docs[p.relative_to(SCHEMAS).as_posix()] = load(p)
        return c

    @cached_property
    def registry(self) -> Registry[Json]:
        return Registry().with_resources((k, DRAFT202012.create_resource(v)) for k, v in self.docs.items())

    def validator(self, base: str, ref: str) -> Draft202012Validator:
        """A validator for ref (a relative reference) in the base file.

        base ファイル内の ref（相対参照）に対して検証する validator。
        """
        return Draft202012Validator({"$ref": urljoin(base, ref)}, registry=self.registry)

    def resolve(self, base: str, ref: str) -> Json:
        return self.registry.resolver(base_uri=base).lookup(ref).contents

    def api(self) -> dict[str, dict[str, Json]]:
        return {k: v for k, v in self.docs.items() if k.startswith("api/")}

    def data(self) -> dict[str, dict[str, Json]]:
        return {k: v for k, v in self.docs.items() if k.startswith("data/")}

    def endpoints(self) -> dict[str, dict[str, Json]]:
        """The x-endpoint of each file under rest/, keyed by file name (without .schema.json).

        rest/ 配下の各ファイルの x-endpoint。キーはファイル名（.schema.json を除く）。
        """
        out = {}
        for k, v in self.docs.items():
            if k.startswith("api/rest/"):
                out[k.removeprefix("api/rest/").removesuffix(".schema.json")] = v["x-endpoint"]
        return out

    def ws_types(self, side: str) -> dict[str, str]:
        """For client / server, each message's type → its $defs name.

        client / server の各メッセージの type → $defs の名前。
        """
        doc = self.docs[f"api/ws/{side}.schema.json"]
        return {d["properties"]["type"]["const"]: name for name, d in doc["$defs"].items()}

    def example_target(self, rel: Path) -> tuple[str, str, str]:
        """Path of an API example relative to examples/valid/api/ or examples/invalid/api/ → (base file, ref, name).

        - ws/client/<type>/x.json, ws/server/<type>/x.json: validated against the whole union;
        - rest/<endpoint>/<request|query|params|status code>/x.json: validated against the Schema named in x-endpoint;
        - <file>/<$defs name>/x.json: validated against that file's $defs entry (e.g. error/ErrorResponse).

        examples/valid/api/、examples/invalid/api/ からの API の例の相対パス → （base ファイル, ref, 名前）。

        - ws/client/<type>/x.json、ws/server/<type>/x.json：ユニオン全体に対して検証する。
        - rest/<endpoint>/<request|query|params|ステータスコード>/x.json：x-endpoint に書かれた Schema に対して
          検証する。
        - <ファイル>/<$defs 名>/x.json：そのファイルの $defs の項目に対して検証する（例：error/ErrorResponse）。
        """
        parts = rel.parts
        if parts[0] == "ws":
            return f"api/ws/{parts[1]}.schema.json", "#", parts[2]
        if parts[0] == "rest":
            base = f"api/rest/{parts[1]}.schema.json"
            ep = self.docs[base]["x-endpoint"]
            ref = ep[parts[2]] if parts[2] in ("request", "query", "params") else ep["responses"][parts[2]]
            assert isinstance(ref, str), f"{rel}: {parts[2]} has no response body / {parts[2]} にレスポンスボディがない"
            return base, ref, parts[2]
        base = f"api/{'/'.join(parts[:-2])}.schema.json"
        return base, f"#/$defs/{parts[-2]}", parts[-2]


@pytest.fixture(scope="session")
def contracts() -> Contracts:
    return Contracts.load()
