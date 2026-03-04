from __future__ import annotations

import json
from typing import Any

from app.db.database import Database


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def ensure_session(self, session_id: str) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id)
                VALUES (?)
                ON CONFLICT(session_id) DO UPDATE SET updated_at=CURRENT_TIMESTAMP
                """,
                (session_id,),
            )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_payload: dict[str, Any] | None = None,
    ) -> None:
        self.ensure_session(session_id)
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, tool_json)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, json.dumps(tool_payload or {})),
            )

    def get_recent_messages(self, session_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT role, content, ts, tool_json
                FROM messages
                WHERE session_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def upsert_summary(self, session_id: str, summary: str) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_snapshots (session_id, summary, version)
                VALUES (?, ?, COALESCE((SELECT MAX(version)+1 FROM memory_snapshots WHERE session_id=?), 1))
                """,
                (session_id, summary, session_id),
            )

    def get_latest_summary(self, session_id: str) -> str | None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT summary FROM memory_snapshots
                WHERE session_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return row["summary"]

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT session_id, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
