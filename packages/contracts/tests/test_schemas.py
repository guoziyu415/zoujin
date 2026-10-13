"""The Schemas themselves (C-1 item 5): valid against the meta-Schema, every reference resolves, every object is
closed, and one-to-one with the message tables of api-contract.

Schema そのもの（C-1 第 5 項）：メタ Schema に適合し、参照がすべて解決でき、オブジェクトがすべて閉じていて、
api-contract のメッセージ表と 1 対 1 で対応する。
"""

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

# The 16 REST endpoints in the "acceptance check" column of the C-1 card (2.10 sharing is P1, not in v1.0).
# C-1 カードの「受け入れ確認」欄にある 16 の REST エンドポイント（2.10 の共有は P1 で、v1.0 には含まれない）。
REST_ENDPOINTS = {
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/auth/logout"),
    ("GET", "/v1/me"),
    ("GET", "/v1/books"),
    ("GET", "/v1/library"),
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
    assert contracts.api(), "No Schemas under api/ were read / api/ の Schema が読み込まれていない"
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
                assert "://" not in ref and not ref.startswith("/"), (
                    f"{doc_id}{path}: use relative references only / 相対参照のみを使う：{ref}"
                )
                contracts.resolve(doc_id, ref)
                count += 1
    assert count > 0


def test_x_endpoint_pointers_resolve(contracts: Contracts) -> None:
    for name, ep in contracts.endpoints().items():
        base = f"api/rest/{name}.schema.json"
        for key in ("request", "query", "params"):
            if key in ep:
                contracts.resolve(base, ep[key])
        assert ep["responses"], f"{name}: no responses / レスポンスがない"
        for status, ref in ep["responses"].items():
            assert re.fullmatch(r"[1-5]\d\d", status), f"{name}：{status}"
            if ref is not None:
                contracts.resolve(base, ref)


def test_api_objects_are_closed(contracts: Contracts) -> None:
    """Closed-object check: every object in api/ has additionalProperties: false (a Record, whose value is a Schema,
    does not count).

    閉じているかの検査：api/ のすべてのオブジェクトに additionalProperties: false がある（値が Schema の Record は
    数えない）。
    """
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
            assert "allOf" not in node, (
                f"{doc_id}{path}: API Schemas do not use allOf (C-1 card 2) / "
                "API の Schema は allOf を使わない（C-1 カード 2）"
            )
    assert not open_objects, "These objects are not closed / これらのオブジェクトが閉じていない：\n" + "\n".join(
        open_objects
    )


def doc_table_types(section: str) -> list[str]:
    """Read every message type from the 3.2 / 3.3 tables of api-contract (the backquoted name in the first column;
    the binary frame row does not count).

    api-contract の 3.2 / 3.3 の表からすべてのメッセージの type を読み取る（1 列目のバッククォート内の名前。
    バイナリフレームの行は数えない）。
    """
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
    """Coverage check: the types in the doc's 3.2 and 3.3 tables map one-to-one to the Schema consts; one missing or
    one extra fails.

    網羅の検査：ドキュメントの 3.2、3.3 の表にある type と Schema の const が 1 対 1 で対応する。1 つでも
    足りなかったり多かったりすれば失敗する。
    """
    for section, side, expected in (("3.2", "client", 18), ("3.3", "server", 31)):
        in_doc = doc_table_types(section)
        assert len(in_doc) == len(set(in_doc)), f"{section}: duplicate types in the table / 表に重複した type がある"
        in_schema = contracts.ws_types(side)
        assert set(in_doc) == set(in_schema), (
            f"{section}: in the doc but not the Schema / ドキュメントにあり Schema にない "
            f"{sorted(set(in_doc) - set(in_schema))}; "
            f"in the Schema but not the doc / Schema にありドキュメントにない {sorted(set(in_schema) - set(in_doc))}"
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
        assert doc_path.split("{")[0].rstrip("/") in text, (
            f"{path} not found in the doc / ドキュメントに {path} が見つからない"
        )


def test_def_names_unique_across_api_and_data(contracts: Contracts) -> None:
    """The generated TS and Python use the $defs name (or title) as the type name: API and data must not share names,
    nor may names repeat within the API.

    生成される TS と Python は $defs の名前（または title）を型名にする：API とデータで名前が重複してはならず、
    API の中でも重複してはならない。
    """
    seen: dict[str, str] = {}
    for doc_id, doc in contracts.docs.items():
        names = [d.get("title", n) for n, d in doc.get("$defs", {}).items()]
        if "oneOf" in doc and doc_id.startswith("api/ws/"):
            names.append(doc["title"])
        for n in names:
            assert n not in seen, f"Duplicate name / 名前が重複：{n} ({seen[n]}, {doc_id})"
            seen[n] = doc_id


def test_schema_files_are_where_the_card_says() -> None:
    api = sorted(p.relative_to(SCHEMAS / "api").as_posix() for p in (SCHEMAS / "api").rglob("*.json"))
    assert "ws/client.schema.json" in api and "ws/server.schema.json" in api
    assert {"binary.json", "error.schema.json", "telemetry.schema.json", "common.schema.json"} <= set(api)
    assert len([p for p in api if p.startswith("rest/")]) == len(REST_ENDPOINTS)
