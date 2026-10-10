"""契约 Event ↔ events 表的一行。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

Json = Any

EXTRA = ("beneficiary", "confirmed", "utteranceRefs", "plan")  # 不常查的可选字段放 extra 列


def recorded_at(now: datetime | None = None) -> str:
    """RecordedAt：UTC、以 Z 结尾（isoformat 给的是 +00:00，自己写）。"""
    now = now or datetime.now(UTC)
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def parse_recorded_at(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def to_row(ev: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": ev["eventId"],
        "playthrough_id": ev["playthroughId"],
        "seq": ev["seq"],
        "turn_id": ev.get("turnId"),
        "idempotency_key": ev["idempotencyKey"],
        "schema_version": ev["schemaVersion"],
        "t": ev["t"],
        "dt": ev["dt"],
        "actor": ev["actor"],
        "type": ev["type"],
        "origin": ev.get("origin"),
        "place": ev["place"],
        "summary": ev["summary"],
        "causes": list(ev["causes"]),
        "effects": list(ev["effects"]),
        "key_moment": ev["keyMoment"],
        "check_result": dict(ev["check"]),
        "supersedes": ev.get("supersedes"),
        "exit_id": ev.get("exitId"),
        "extra": {k: ev[k] for k in EXTRA if k in ev},
        "recorded_at": parse_recorded_at(ev["recordedAt"]),
    }


def from_row(row: Mapping[str, Any], world_model_version: str) -> Json:
    ev: Json = {
        "schemaVersion": row["schema_version"],
        "eventId": row["event_id"],
        "playthroughId": row["playthrough_id"],
        "seq": row["seq"],
        "idempotencyKey": row["idempotency_key"],
        "worldModelVersion": world_model_version,
        "t": row["t"],
        "dt": row["dt"],
        "recordedAt": recorded_at(row["recorded_at"]),
        "actor": row["actor"],
        "type": row["type"],
        "place": row["place"],
        "summary": row["summary"],
        "causes": row["causes"],
        "effects": row["effects"],
        "keyMoment": row["key_moment"],
        "check": row["check_result"],
    }
    for k, col in (("turnId", "turn_id"), ("origin", "origin"), ("supersedes", "supersedes"), ("exitId", "exit_id")):
        if row[col] is not None:
            ev[k] = row[col]
    ev.update(row["extra"] or {})
    return ev


def commit_key(idempotency_key: str) -> str:
    """同一次提交写的事件，幂等键都是「任务的键/序号」；前一段相同的属于同一条 commit。"""
    return idempotency_key.rsplit("/", 1)[0]
