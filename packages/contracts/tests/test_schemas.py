"""Schema 本身（C-1 第 5 条）：元 Schema 合法、引用都能解析、对象都关死、和 api-contract 的消息表一一对应。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from jsonschema import Draft202012Validator

if TYPE_CHECKING:
    from conftest import Contracts

PKG = Path(__file__).resolve().parents[1]
SCHEMAS = PKG / "schemas"
API_CONTRACT = PKG.parents[1] / "docs" / "backend" / "api-contract.md"

# C-1 卡「验收」列的 16 个 REST 接口（2.10 分享是 P1，不在 v1.0）。
REST_ENDPOINTS = {
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/auth/logout"),
    ("GET", "/v1/me"),
    ("GET", "/v1/books/{bookId}/manifest"),
    ("POST", "/v1/playthroughs"),
    ("GET", "/v1/playthroughs/{id}/snapshot"),
    ("GET", "/v1/playthroughs/{id}/events"),
    ("GET", "/v1/playthroughs/{id}/timeline"),
    ("GET", "/v1/playthroughs/{id}/why"),
    ("GET", "/v1/playthroughs/{id}/memories"),
    ("GET", "/v1/playthroughs/{id}/memories/{memoryId}/impact"),
    ("DELETE", "/v1/playthroughs/{id}/memories/{memoryId}"),
    ("GET", "/v1/playthroughs/{id}/ending"),
    ("DELETE", "/v1/playthroughs/{id}"),
    ("POST", "/v1/telemetry"),
    ("POST", "/v1/test/playthroughs/{id}/advance"),
}


def test_ids_match_paths_and_metaschema(contracts: Contracts) -> None:
    assert contracts.api(), "没有读到 api/ 的 Schema"
    for doc_id, doc in contracts.docs.items():
        assert doc["$id"] == doc_id
        assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema", doc_id
        Draft202012Validator.check_schema(doc)


def test_every_ref_is_relative_and_resolves(contracts: Contracts) -> None:
    count = 0
    for doc_id, doc in contracts.docs.items():
        for path, node in contracts.walk(doc):
            if isinstance(node, dict) and isinstance(node.get("$ref"), str):
                ref = node["$ref"]
                assert "://" not in ref and not ref.startswith("/"), f"{doc_id}{path}：只用相对引用，{ref}"
                contracts.resolve(doc_id, ref)
                count += 1
    assert count > 0


def test_x_endpoint_pointers_resolve(contracts: Contracts) -> None:
    for name, ep in contracts.endpoints().items():
        base = f"api/rest/{name}.schema.json"
        for key in ("request", "query", "params"):
            if key in ep:
                contracts.resolve(base, ep[key])
        assert ep["responses"], f"{name}：没有响应"
        for status, ref in ep["responses"].items():
            assert re.fullmatch(r"[1-5]\d\d", status), f"{name}：{status}"
            if ref is not None:
                contracts.resolve(base, ref)


def test_api_objects_are_closed(contracts: Contracts) -> None:
    """关死检查：api/ 里每个对象都写 additionalProperties: false（Record 的值是 Schema，不算）。"""
    open_objects = []
    for doc_id, doc in contracts.api().items():
        for path, node in contracts.walk(doc):
            if not isinstance(node, dict) or "/x-endpoint" in path:
                continue
            if node.get("type") == "object" or "properties" in node and "type" in node:
                ap = node.get("additionalProperties")
                if ap is not False and not isinstance(ap, dict):
                    open_objects.append(f"{doc_id}{path}")
            assert "unevaluatedProperties" not in node or "allOf" in node, f"{doc_id}{path}"
            assert "allOf" not in node, f"{doc_id}{path}：接口 Schema 不用 allOf（C-1 卡 2）"
    assert not open_objects, "这些对象没关死：\n" + "\n".join(open_objects)


def doc_table_types(section: str) -> list[str]:
    """从 api-contract 的 3.2 / 3.3 表格里读出全部消息 type（第一列反引号里的名字，二进制帧那行不算）。"""
    text = API_CONTRACT.read_text(encoding="utf-8")
    start = text.index(f"\n### {section} ")
    end = text.index("\n### ", start + 1)
    types = []
    for line in text[start:end].splitlines():
        m = re.match(r"^\| `([a-z_]+)` \|", line)
        if m:
            types.append(m.group(1))
    return types


def test_ws_messages_match_api_contract_tables(contracts: Contracts) -> None:
    """覆盖检查：文档 3.2、3.3 表格里的 type 和 Schema 的 const 一一对应，少一个、多一个都红。"""
    for section, side, expected in (("3.2", "client", 17), ("3.3", "server", 30)):
        in_doc = doc_table_types(section)
        assert len(in_doc) == len(set(in_doc)), f"{section} 表里有重复的 type"
        in_schema = contracts.ws_types(side)
        assert set(in_doc) == set(in_schema), (
            f"{section}：文档有、Schema 没有 {sorted(set(in_doc) - set(in_schema))}；"
            f"Schema 有、文档没有 {sorted(set(in_schema) - set(in_doc))}"
        )
        assert len(in_doc) == expected


def test_ws_unions_list_every_message(contracts: Contracts) -> None:
    for side in ("client", "server"):
        doc = contracts.docs[f"api/ws/{side}.schema.json"]
        assert [r["$ref"] for r in doc["oneOf"]] == [f"#/$defs/{n}" for n in doc["$defs"]]


def test_rest_endpoints_match_card_and_doc(contracts: Contracts) -> None:
    in_schema = {(ep["method"], ep["path"]) for ep in contracts.endpoints().values()}
    assert in_schema == REST_ENDPOINTS
    text = API_CONTRACT.read_text(encoding="utf-8")
    for _method, path in REST_ENDPOINTS:
        doc_path = path.removeprefix("/v1/")
        assert doc_path.split("{")[0].rstrip("/") in text, f"文档里找不到 {path}"


def test_def_names_unique_across_api_and_data(contracts: Contracts) -> None:
    """生成的 TS 和 Python 用 $defs 名（或 title）当类型名：接口和数据不能重名，接口内部也不能。"""
    seen: dict[str, str] = {}
    for doc_id, doc in contracts.docs.items():
        names = [d.get("title", n) for n, d in doc.get("$defs", {}).items()]
        if "oneOf" in doc and doc_id.startswith("api/ws/"):
            names.append(doc["title"])
        for n in names:
            assert n not in seen, f"{n} 重名：{seen[n]} 和 {doc_id}"
            seen[n] = doc_id


def test_schema_files_are_where_the_card_says() -> None:
    api = sorted(p.relative_to(SCHEMAS / "api").as_posix() for p in (SCHEMAS / "api").rglob("*.json"))
    assert "ws/client.schema.json" in api and "ws/server.schema.json" in api
    assert {"binary.json", "error.schema.json", "telemetry.schema.json", "common.schema.json"} <= set(api)
    assert len([p for p in api if p.startswith("rest/")]) == len(REST_ENDPOINTS)
