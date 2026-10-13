"""Generated files (C-1 items 3 and 5): no open index signatures in TypeScript; the frame-format constants are
consistent; Python type names are the $defs names; parsing by type works in one step.

生成物（C-1 第 3、5 項）：TypeScript に開いたインデックスシグネチャがない。フレーム形式の定数が整合している。
Python の型名は $defs の名前そのもの。type で一度に解析できる。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter
from zoujin_contracts.generated import api, binary, data

if TYPE_CHECKING:
    from conftest import Contracts

PKG = Path(__file__).resolve().parents[1]
TS = PKG / "src" / "generated"


def test_api_ts_index_signatures_only_for_records(contracts: Contracts) -> None:
    """The TS side of the closed-object check: no `[k: string]: unknown` in the API types; index signatures come only
    from Records (additionalProperties is a Schema, manifest.setPieceVoices in v1.0.4).

    閉じているかの検査の TS 側：API の型に `[k: string]: unknown` がない。インデックスシグネチャは Record
    （additionalProperties が Schema であるもの。v1.0.4 の manifest.setPieceVoices）からだけ生じる。
    """
    records = sum(
        1
        for doc in contracts.api().values()
        for _, node in contracts.walk(doc)
        if isinstance(node, dict)
        and node.get("type") == "object"
        and isinstance(node.get("additionalProperties"), dict)
    )
    text = (TS / "api.ts").read_text(encoding="utf-8")
    assert "[k: string]: unknown" not in text
    assert len(re.findall(r"\[k: string\]", text)) == records


def test_data_ts_index_signatures_only_for_records(contracts: Contracts) -> None:
    """In the data types, only Records (additionalProperties is a Schema) produce index signatures.

    データの型では Record（additionalProperties が Schema であるもの）だけがインデックスシグネチャを生成する。
    """
    records = sum(
        1
        for doc in contracts.data().values()
        for _, node in contracts.walk(doc)
        if isinstance(node, dict)
        and node.get("type") == "object"
        and isinstance(node.get("additionalProperties"), dict)
    )
    text = (TS / "data.ts").read_text(encoding="utf-8")
    assert len(re.findall(r"\[k: string\]", text)) == records


def test_ts_has_no_never() -> None:
    """Constructs the generator does not understand produce `never` (e.g. `prefixItems` tuples, which codegen rewrites
    into `items` arrays).

    生成器が理解しない書き方は `never` を生成する（例：`prefixItems` のタプル。codegen で `items` 配列に
    書き換えている）。
    """
    for name in ("api.ts", "data.ts"):
        assert not re.search(r"\bnever\b", (TS / name).read_text(encoding="utf-8")), name


def test_binary_constants_consistent() -> None:
    spec = json.loads((PKG / "schemas" / "api" / "binary.json").read_text(encoding="utf-8"))
    up = spec["types"]["micUp"]
    assert up["frameBytes"] == up["sampleRateHz"] * up["frameMs"] // 1000 * spec["pcmSampleBits"] // 8
    assert binary.MIC_UP_FRAME_BYTES == 1280
    assert binary.SERVER_TURN_SEQ_MIN == binary.CLIENT_TURN_SEQ_MAX + 2 == 0x80000001
    assert (binary.MIC_UP, binary.CHARACTER_DOWN, binary.HEADER_BYTES) == (1, 2, 5)


def test_discriminated_unions_pick_the_right_class() -> None:
    client = TypeAdapter(api.ClientMessage)
    server = TypeAdapter(api.ServerMessage)
    assert type(client.validate_python({"type": "ping"})).__name__ == "PingMessage"
    assert type(server.validate_json('{"type": "pong"}')).__name__ == "PongMessage"
    batch = api.TelemetryBatch.model_validate(
        {
            "common": {"deviceClass": "ios-390x844@3", "os": "iOS 26", "browser": "Safari", "appVersion": "web-0.1.0"},
            "events": [{"name": "gl_context_lost", "clientTs": "2026-10-10T07:00:00Z", "props": {"restored": True}}],
        }
    )
    assert type(batch.events[0]).__name__ == "TelemetryGlContextLost"


def test_python_names_are_the_defs(contracts: Contracts) -> None:
    """Every $defs entry is generated under its own name (the title if there is one), and objects' fields match.

    Guards against the generator appending a number to the $defs entry on a name clash (e.g. the data's Relationship
    becoming Relationship1 while Relationship is an inline object from elsewhere); see codegen.name_inline_objects.

    $defs の各項目は自分の名前（title があれば title）で生成され、オブジェクトのフィールドが一致する。

    名前が重複したときに生成器が $defs 側に番号を付けてしまうこと（例：データの Relationship が Relationship1 になり、
    Relationship がよそでその場に書いたオブジェクトになる）を防ぐ。codegen.name_inline_objects を参照。
    """
    wrong = []
    for module, docs in ((data, contracts.data()), (api, contracts.api())):
        for doc in docs.values():
            for name, schema in doc.get("$defs", {}).items():
                py_name = schema.get("title", name)
                py = getattr(module, py_name, None)
                if py is None:
                    wrong.append(f"{module.__name__}.{py_name}: not generated / 生成されていない")
                elif "properties" in schema:
                    fields = {f.alias or n for n, f in py.model_fields.items()}
                    if fields != set(schema["properties"]):
                        wrong.append(f"{module.__name__}.{py_name}: fields / フィールド {sorted(fields)}")
    assert not wrong, "\n".join(wrong)


def test_effect_parses_by_op() -> None:
    effect = TypeAdapter(data.Effect)
    parsed = effect.validate_python({"op": "inc", "var": "var.trust.king", "by": -1})
    assert type(parsed).__name__ == "EffectInc"


def test_aliased_fields_accept_the_python_name() -> None:
    """A field named `from` is generated as `from_` with an alias; it can be constructed by the Python name and is
    dumped back as `from`.

    `from` という名前のフィールドは `from_` とエイリアスとして生成される。Python の名前でも構築でき、出力時には
    `from` に戻る。
    """
    effect = data.EffectSet(op="set", var="var.trust.king", value=1, from_=0)
    assert effect.model_dump(by_alias=True) == {"op": "set", "var": "var.trust.king", "value": 1, "from": 0}
