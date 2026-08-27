from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from core.database import Database


@dataclass(frozen=True)
class AuditEntry:
    id: int
    event_type: str
    action: str
    entity_type: str
    entity_id: str
    summary: str
    details: dict
    created_at: str


class AuditService:
    def __init__(self, database: Database):
        self.database = database

    def record(
        self,
        *,
        event_type: str,
        action: str,
        summary: str,
        entity_type: str = "",
        entity_id: str | int | None = None,
        details: dict | None = None,
        created_at: str | None = None,
    ) -> int:
        timestamp = created_at or datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_log(
                    event_type,
                    action,
                    entity_type,
                    entity_id,
                    summary,
                    details_json,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event_type).strip().upper(),
                    str(action).strip().upper(),
                    str(entity_type or "").strip(),
                    "" if entity_id is None else str(entity_id),
                    str(summary).strip(),
                    payload,
                    timestamp,
                ),
            )
            return int(cursor.lastrowid)

    def recent(self, limit: int = 20) -> list[AuditEntry]:
        safe_limit = max(1, min(int(limit), 200))
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_type,
                    action,
                    entity_type,
                    entity_id,
                    summary,
                    details_json,
                    created_at
                FROM audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        result: list[AuditEntry] = []
        for row in rows:
            try:
                details = json.loads(str(row["details_json"] or "{}"))
            except json.JSONDecodeError:
                details = {}

            result.append(
                AuditEntry(
                    id=int(row["id"]),
                    event_type=str(row["event_type"]),
                    action=str(row["action"]),
                    entity_type=str(row["entity_type"] or ""),
                    entity_id=str(row["entity_id"] or ""),
                    summary=str(row["summary"]),
                    details=details if isinstance(details, dict) else {},
                    created_at=str(row["created_at"]),
                )
            )
        return result
