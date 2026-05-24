"""SQLite-backed config, idempotency, and run ledger stores for Orvo Brain.

Provides:
- init_schema(conn)          — creates all tables (idempotent)
- SQLiteConfigStore          — drop-in replacement for InMemoryConfigStore
- SQLiteIdempotencyStore     — satisfies IdempotencyStore Protocol
- SQLiteRunLedger            — durable RunLedger implementation
- SQLiteOperationalCaseStore — durable OperationalCase store

Only stdlib sqlite3 is used — no external dependencies.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.brain.operational_cases import SQLiteOperationalCaseStore
from app.brain.run_ledger import SQLiteRunLedger
from app.brain.config import (
    BusinessConfig,
    ReportSchedule,
    config_from_json,
    config_to_json,
    schedule_from_json,
    schedule_to_json,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables if they do not already exist (idempotent)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS business_configs (
            business_id TEXT PRIMARY KEY,
            data        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS report_schedules (
            schedule_id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            data        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS idempotency_keys (
            key        TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_ledger (
            run_id       TEXT PRIMARY KEY,
            business_id  TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            status       TEXT NOT NULL,
            started_at   TEXT NOT NULL,
            finished_at  TEXT,
            data         TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_run_ledger_business_started
            ON run_ledger (business_id, started_at DESC);

        CREATE INDEX IF NOT EXISTS idx_run_ledger_status_started
            ON run_ledger (status, started_at DESC);

        CREATE TABLE IF NOT EXISTS operational_cases (
            case_id        TEXT PRIMARY KEY,
            business_id    TEXT NOT NULL,
            dedupe_key     TEXT NOT NULL,
            status         TEXT NOT NULL,
            case_type      TEXT NOT NULL,
            priority_score INTEGER NOT NULL,
            opened_at      TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            data           TEXT NOT NULL,
            UNIQUE (business_id, dedupe_key)
        );

        CREATE INDEX IF NOT EXISTS idx_operational_cases_business_status
            ON operational_cases (business_id, status, priority_score DESC, opened_at ASC);

        CREATE INDEX IF NOT EXISTS idx_operational_cases_updated
            ON operational_cases (updated_at DESC);
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# SQLiteConfigStore
# ---------------------------------------------------------------------------


class SQLiteConfigStore:
    """Persistent config store backed by a SQLite connection.

    The caller is responsible for creating/closing the connection.
    In tests, pass ``sqlite3.connect(':memory:')`` with ``init_schema`` called.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # -- BusinessConfig CRUD -------------------------------------------------

    def save_business_config(self, cfg: BusinessConfig) -> None:
        """Insert or replace a BusinessConfig record."""
        self._conn.execute(
            "INSERT OR REPLACE INTO business_configs (business_id, data) VALUES (?, ?)",
            (cfg.business_id, config_to_json(cfg)),
        )
        self._conn.commit()

    def load_business_config(self, business_id: str) -> BusinessConfig | None:
        """Return the BusinessConfig for *business_id* or None if not found."""
        cursor = self._conn.execute(
            "SELECT data FROM business_configs WHERE business_id = ?",
            (business_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return config_from_json(row[0])

    def delete_business_config(self, business_id: str) -> None:
        """Delete a BusinessConfig (no-op if it does not exist)."""
        self._conn.execute(
            "DELETE FROM business_configs WHERE business_id = ?",
            (business_id,),
        )
        self._conn.commit()

    def list_business_configs(self) -> list[BusinessConfig]:
        """Return all stored BusinessConfig records."""
        cursor = self._conn.execute("SELECT data FROM business_configs")
        return [config_from_json(row[0]) for row in cursor.fetchall()]

    # -- ReportSchedule CRUD -------------------------------------------------

    def save_schedule(self, sched: ReportSchedule) -> None:
        """Insert or replace a ReportSchedule record."""
        self._conn.execute(
            "INSERT OR REPLACE INTO report_schedules (schedule_id, business_id, data) VALUES (?, ?, ?)",
            (sched.schedule_id, sched.business_id, schedule_to_json(sched)),
        )
        self._conn.commit()

    def load_schedule(self, schedule_id: str) -> ReportSchedule | None:
        """Return the ReportSchedule for *schedule_id* or None if not found."""
        cursor = self._conn.execute(
            "SELECT data FROM report_schedules WHERE schedule_id = ?",
            (schedule_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return schedule_from_json(row[0])

    def delete_schedule(self, schedule_id: str) -> None:
        """Delete a ReportSchedule (no-op if it does not exist)."""
        self._conn.execute(
            "DELETE FROM report_schedules WHERE schedule_id = ?",
            (schedule_id,),
        )
        self._conn.commit()

    def list_schedules(self, business_id: str) -> list[ReportSchedule]:
        """Return all schedules belonging to *business_id*."""
        cursor = self._conn.execute(
            "SELECT data FROM report_schedules WHERE business_id = ?",
            (business_id,),
        )
        return [schedule_from_json(row[0]) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# SQLiteIdempotencyStore
# ---------------------------------------------------------------------------


class SQLiteIdempotencyStore:
    """Persistent idempotency store satisfying the IdempotencyStore Protocol.

    Keys are stored with a UTC ``created_at`` timestamp for auditability.
    Marking the same key twice is safe (INSERT OR IGNORE).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def has(self, key: str) -> bool:
        """Return True if *key* has already been marked."""
        cursor = self._conn.execute(
            "SELECT 1 FROM idempotency_keys WHERE key = ?",
            (key,),
        )
        return cursor.fetchone() is not None

    def mark(self, key: str) -> None:
        """Persist *key* as processed (idempotent — duplicate marks are ignored)."""
        created_at = datetime.now(tz=timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys (key, created_at) VALUES (?, ?)",
            (key, created_at),
        )
        self._conn.commit()
