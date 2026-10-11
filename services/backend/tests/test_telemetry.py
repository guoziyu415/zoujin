"""2.11 `POST /v1/telemetry`：不要会话，合 Schema 回 204、每条记一行日志，不合回 400。不联网。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from zoujin_backend.gateway import app as gateway_app

from .conftest import Env

EXAMPLES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "examples"
REQ = "api/rest/telemetry/request"


def test_telemetry_is_accepted_without_a_session_and_logged(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    app = gateway_app.create_app(env.settings)
    with (
        TestClient(app, headers={"Origin": "http://testserver"}) as c,
        caplog.at_level(logging.INFO, "zoujin.telemetry"),
    ):
        for f in sorted((EXAMPLES / "valid" / REQ).glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            caplog.clear()
            r = c.post("/v1/telemetry", json=doc)
            assert r.status_code == 204 and r.content == b"", f.name
            rows = [json.loads(m.split(" ", 1)[1]) for m in caplog.messages if m.startswith("telemetry ")]
            assert len(rows) == len(doc["events"]), f.name
            assert all(row["common"] == doc["common"] for row in rows)
        for f in sorted((EXAMPLES / "invalid" / REQ).glob("*.json")):
            r = c.post("/v1/telemetry", json=json.loads(f.read_text(encoding="utf-8")))
            assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request", f.name
