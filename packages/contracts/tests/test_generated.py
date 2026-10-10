"""生成物（C-1 第 3、5 条）：TypeScript 里没有放开的索引签名；帧格式常量自洽；
Python 的类型名就是 $defs 的名字；能按 type 一次解析。"""

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


def test_api_ts_has_no_index_signature() -> None:
    """关死检查的 TS 一侧：接口类型里没有 `[k: string]: unknown`。"""
    text = (TS / "api.ts").read_text(encoding="utf-8")
    assert "[k: string]" not in text


def test_data_ts_index_signatures_only_for_records(contracts: Contracts) -> None:
    """数据类型里只有 Record（additionalProperties 是一个 Schema）生成索引签名。"""
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
    """每个 $defs 条目都按自己的名字（有 title 用 title）生成，对象的字段对得上。

    防的是生成器遇到重名时给 $defs 那个加数字（例：数据的 Relationship 变成 Relationship1，
    Relationship 却是别处就地写的对象），见 codegen.name_inline_objects。
    """
    wrong = []
    for module, docs in ((data, contracts.data()), (api, contracts.api())):
        for doc in docs.values():
            for name, schema in doc.get("$defs", {}).items():
                py_name = schema.get("title", name)
                py = getattr(module, py_name, None)
                if py is None:
                    wrong.append(f"{module.__name__}.{py_name}：没生成")
                elif "properties" in schema:
                    fields = {f.alias or n for n, f in py.model_fields.items()}
                    if fields != set(schema["properties"]):
                        wrong.append(f"{module.__name__}.{py_name}：字段 {sorted(fields)}")
    assert not wrong, "\n".join(wrong)


def test_effect_parses_by_op() -> None:
    effect = TypeAdapter(data.Effect)
    parsed = effect.validate_python({"op": "inc", "var": "var.trust.king", "by": -1})
    assert type(parsed).__name__ == "EffectInc"


def test_aliased_fields_accept_the_python_name() -> None:
    """叫 `from` 的字段生成成 `from_` 加别名；按 Python 的名字也能构造，导出时用回 `from`。"""
    effect = data.EffectSet(op="set", var="var.trust.king", value=1, from_=0)
    assert effect.model_dump(by_alias=True) == {"op": "set", "var": "var.trust.king", "value": 1, "from": 0}
