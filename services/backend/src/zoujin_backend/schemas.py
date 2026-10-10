"""发出前的自检：先用 packages/contracts 生成的 pydantic 类型构造，再按 JSON Schema 校验。

mock（B-1）发的每条消息和响应、网关（B-0）发的每条消息和响应、叙事者写库前的每个事件都过这里。
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

from jsonschema import Draft202012Validator, ValidationError
from pydantic import TypeAdapter
from referencing import Registry
from referencing.jsonschema import DRAFT202012
from zoujin_contracts.generated import api, data

Json = Any

SERVER = "api/ws/server.schema.json"
CLIENT = "api/ws/client.schema.json"
EVENT = "data/event.schema.json"


class SchemaError(Exception):
    """一条消息或响应不合契约。"""


class SchemaBook:
    def __init__(self, root: Path) -> None:
        self.docs: dict[str, Json] = {}
        for p in sorted(root.rglob("*.schema.json")):
            self.docs[p.relative_to(root).as_posix()] = json.loads(p.read_text(encoding="utf-8"))
        if SERVER not in self.docs:
            raise FileNotFoundError(f"{root} 下没有 {SERVER}")
        self.registry: Registry[Json] = Registry().with_resources(
            (k, DRAFT202012.create_resource(v)) for k, v in self.docs.items()
        )
        self._validators: dict[tuple[str, str], Draft202012Validator] = {}

    def endpoint(self, name: str) -> dict[str, Json]:
        """rest/<name>.schema.json 的 x-endpoint。"""
        return cast(dict[str, Json], self.docs[f"api/rest/{name}.schema.json"]["x-endpoint"])

    def endpoints(self) -> dict[str, dict[str, Json]]:
        return {
            k.removeprefix("api/rest/").removesuffix(".schema.json"): v["x-endpoint"]
            for k, v in self.docs.items()
            if k.startswith("api/rest/")
        }

    def ws_types(self, side: str) -> list[str]:
        doc = self.docs[f"api/ws/{side}.schema.json"]
        return [d["properties"]["type"]["const"] for d in doc["$defs"].values() if "type" in d.get("properties", {})]

    def validator(self, base: str, ref: str) -> Draft202012Validator:
        key = (base, ref)
        if key not in self._validators:
            self._validators[key] = Draft202012Validator({"$ref": urljoin(base, ref)}, registry=self.registry)
        return self._validators[key]

    def errors(self, base: str, ref: str, doc: Json) -> list[str]:
        """服务端自己构造的文档：带 jsonschema 的原句（可能含值），只进 SchemaError 和测试。"""
        out = []
        for e in self.validator(base, ref).iter_errors(doc):
            out.append(f"/{'/'.join(map(str, e.absolute_path))}: {e.message}")
        return out

    def spots(self, base: str, ref: str, doc: Json) -> list[str]:
        """客户端发来的文档：只给出错的字段路径和规则名，不带值（可能是玩家的原话），可以直接写日志。"""
        return [s for e in self.validator(base, ref).iter_errors(doc) for s in _spots(e)]

    def title(self, base: str, ref: str) -> str:
        """ref 指向的定义的 title：生成的 pydantic 类型就叫这个名字。"""
        contents = self.registry.resolver(base_uri=base).lookup(ref).contents
        return cast(str, contents.get("title", ref.rsplit("/", 1)[-1]))

    def build(self, base: str, ref: str, doc: Json, adapter: TypeAdapter[Any] | None = None) -> Json:
        """用生成的类型构造（解析再导出），再按 Schema 校验；不过就抛 SchemaError。"""
        ta = adapter or (data_adapter if base.startswith("data/") else rest_adapter)(self.title(base, ref))
        try:
            out = ta.dump_python(ta.validate_python(doc), mode="json", by_alias=True, exclude_unset=True)
        except ValueError as e:
            raise SchemaError(f"{base}{ref}：生成的类型不收：{e}") from e
        errs = self.errors(base, ref, out)
        if errs:
            raise SchemaError(f"{base}{ref}：\n" + "\n".join(errs))
        return out

    def server_message(self, doc: Json) -> Json:
        return self.build(SERVER, "#", doc, server_adapter())

    def event(self, doc: Json) -> Json:
        """数据契约的 Event（叙事者写库前）。"""
        return self.build(EVENT, "#/$defs/Event", doc)

    def client_errors(self, doc: Json) -> list[str]:
        return self.spots(CLIENT, "#", doc)

    def response(self, endpoint: str, status: int, doc: Json) -> Json:
        name = f"api/rest/{endpoint}.schema.json"
        ref = self.endpoint(endpoint)["responses"][str(status)]
        if ref is None:
            raise SchemaError(f"{endpoint} {status} 没有响应体")
        return self.build(name, ref, doc)

    def request_errors(self, endpoint: str, part: str, doc: Json) -> list[str]:
        """part = request / query / params。"""
        return self.spots(f"api/rest/{endpoint}.schema.json", self.endpoint(endpoint)[part], doc)


def _spots(e: ValidationError) -> list[str]:
    """「/字段路径: 规则名」。客户端消息是按 type 分的 oneOf：只看 type 对上的那个分支，都对不上就是「/: oneOf」。"""
    if e.validator in ("oneOf", "anyOf") and e.context:
        branches: dict[Any, list[ValidationError]] = {}
        for c in e.context:
            branches.setdefault(c.relative_schema_path[0], []).append(c)
        hit = [errs for errs in branches.values() if not any(list(c.absolute_path) == ["type"] for c in errs)]
        if len(hit) == 1:
            return [s for c in hit[0] for s in _spots(c)]
    return [f"/{'/'.join(map(str, e.absolute_path))}: {e.validator}"]


@cache
def server_adapter() -> TypeAdapter[Any]:
    return TypeAdapter(api.ServerMessage)


@cache
def rest_adapter(title: str) -> TypeAdapter[Any]:
    return TypeAdapter(getattr(api, title))


@cache
def data_adapter(title: str) -> TypeAdapter[Any]:
    return TypeAdapter(getattr(data, title))
