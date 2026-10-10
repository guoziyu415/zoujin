"""契约测试共用的东西（C-1）：读全部 Schema，按 $id 建 referencing 的 Registry，按目录找例子要对哪个 Schema。"""

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
    """深度优先走遍一个 Schema，给出（JSON 指针, 子节点）。"""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for n, v in enumerate(node):
            yield from walk(v, f"{path}/{n}")


@dataclass
class Contracts:
    """测试通过 fixture `contracts` 拿到它（--import-mode=importlib 下测试文件不能 import conftest）。"""

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
        """对 base 文件里的 ref（相对引用）校验的 validator。"""
        return Draft202012Validator({"$ref": urljoin(base, ref)}, registry=self.registry)

    def resolve(self, base: str, ref: str) -> Json:
        return self.registry.resolver(base_uri=base).lookup(ref).contents

    def api(self) -> dict[str, dict[str, Json]]:
        return {k: v for k, v in self.docs.items() if k.startswith("api/")}

    def data(self) -> dict[str, dict[str, Json]]:
        return {k: v for k, v in self.docs.items() if k.startswith("data/")}

    def endpoints(self) -> dict[str, dict[str, Json]]:
        """rest/ 下每个文件的 x-endpoint，键是文件名（不含 .schema.json）。"""
        out = {}
        for k, v in self.docs.items():
            if k.startswith("api/rest/"):
                out[k.removeprefix("api/rest/").removesuffix(".schema.json")] = v["x-endpoint"]
        return out

    def ws_types(self, side: str) -> dict[str, str]:
        """client / server 里每种消息的 type → $defs 名。"""
        doc = self.docs[f"api/ws/{side}.schema.json"]
        return {d["properties"]["type"]["const"]: name for name, d in doc["$defs"].items()}

    def example_target(self, rel: Path) -> tuple[str, str, str]:
        """接口例子相对 examples/valid/api/、examples/invalid/api/ 的路径 → （base 文件, ref, 名字）。

        - ws/client/<type>/x.json、ws/server/<type>/x.json：对整个联合校验；
        - rest/<endpoint>/<request|query|params|状态码>/x.json：对 x-endpoint 里写的那个 Schema 校验；
        - <文件>/<$defs 名>/x.json：对那个文件的 $defs 条目校验（例 error/ErrorResponse）。
        """
        parts = rel.parts
        if parts[0] == "ws":
            return f"api/ws/{parts[1]}.schema.json", "#", parts[2]
        if parts[0] == "rest":
            base = f"api/rest/{parts[1]}.schema.json"
            ep = self.docs[base]["x-endpoint"]
            ref = ep[parts[2]] if parts[2] in ("request", "query", "params") else ep["responses"][parts[2]]
            assert isinstance(ref, str), f"{rel}：{parts[2]} 没有响应体"
            return base, ref, parts[2]
        base = f"api/{'/'.join(parts[:-2])}.schema.json"
        return base, f"#/$defs/{parts[-2]}", parts[-2]


@pytest.fixture(scope="session")
def contracts() -> Contracts:
    return Contracts.load()
