"""Contract Event ↔ one row of the events table.

契約の Event ↔ events テーブルの 1 行。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

Json = Any

# Optional fields that are rarely queried go in the extra column.
# あまり検索しない任意フィールドは extra 列に入れる。
EXTRA = ("beneficiary", "confirmed", "utteranceRefs", "plan")


def recorded_at(now: datetime | None = None) -> str:
    """RecordedAt: UTC, ending in Z (isoformat gives +00:00, so we format it ourselves).

    RecordedAt：UTC で Z で終わる（isoformat は +00:00 を返すので自前で書く）。
    """
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
    """Events written by the same submission all have idempotency key "<task key>/<index>"; those sharing the first
    part belong to the same commit.

    同じ送信で書いたイベントの冪等キーはどれも「タスクのキー/連番」。前半が同じものは同じ commit に属する。
    """
    return idempotency_key.rsplit("/", 1)[0]
