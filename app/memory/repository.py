from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.db.database import Database


@dataclass
class Vehicle:
    id: int
    vehicle_name: str
    ip: str
    mcp_endpoint: str | None
    auth_type: str
    auth_secret_ref: str | None
    status: str
    is_configured: bool
    last_seen_at: str | None


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

    def set_last_vehicle_ip(self, session_id: str, ip: str | None) -> None:
        self.ensure_session(session_id)
        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET last_vehicle_ip=?, updated_at=CURRENT_TIMESTAMP
                WHERE session_id=?
                """,
                (ip, session_id),
            )

    def get_last_vehicle_ip(self, session_id: str) -> str | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT last_vehicle_ip FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return row["last_vehicle_ip"]

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

    def get_recent_messages(self, session_id: str, limit: int = 8) -> list[dict[str, Any]]:
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

    def list_vehicles(self) -> list[Vehicle]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, vehicle_name, ip, mcp_endpoint, auth_type, auth_secret_ref, status, is_configured, last_seen_at
                FROM vehicles
                ORDER BY vehicle_name ASC
                """
            ).fetchall()
        return [self._row_to_vehicle(r) for r in rows]

    def get_vehicle_by_ip(self, ip: str) -> Vehicle | None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT id, vehicle_name, ip, mcp_endpoint, auth_type, auth_secret_ref, status, is_configured, last_seen_at
                FROM vehicles
                WHERE ip=?
                """,
                (ip,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_vehicle(row)

    def upsert_vehicle(
        self,
        vehicle_name: str,
        ip: str,
        mcp_endpoint: str | None,
        status: str = "offline",
        is_configured: bool = False,
        auth_type: str = "none",
        auth_secret_ref: str | None = None,
    ) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO vehicles (vehicle_name, ip, mcp_endpoint, status, is_configured, auth_type, auth_secret_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    vehicle_name=excluded.vehicle_name,
                    mcp_endpoint=excluded.mcp_endpoint,
                    status=excluded.status,
                    is_configured=excluded.is_configured,
                    auth_type=excluded.auth_type,
                    auth_secret_ref=excluded.auth_secret_ref,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    vehicle_name,
                    ip,
                    mcp_endpoint,
                    status,
                    1 if is_configured else 0,
                    auth_type,
                    auth_secret_ref,
                ),
            )

    def _row_to_vehicle(self, row: Any) -> Vehicle:
        return Vehicle(
            id=row["id"],
            vehicle_name=row["vehicle_name"],
            ip=row["ip"],
            mcp_endpoint=row["mcp_endpoint"],
            auth_type=row["auth_type"],
            auth_secret_ref=row["auth_secret_ref"],
            status=row["status"],
            is_configured=bool(row["is_configured"]),
            last_seen_at=row["last_seen_at"],
        )
