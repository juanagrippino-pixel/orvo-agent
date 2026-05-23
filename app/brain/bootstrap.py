"""Bootstrap helpers for Orvo Brain runtime configuration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule
from app.brain.storage import SQLiteConfigStore, init_schema


def open_brain_sqlite_store(db_path: str) -> tuple[sqlite3.Connection, SQLiteConfigStore]:
    """Open a SQLite-backed config store and ensure the schema exists."""

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    return conn, SQLiteConfigStore(conn)


def upsert_artemea_google_sheets_config(
    store,
    *,
    spreadsheet_id: str,
    range_name: str,
    owner_phone: str,
    cron_expression: str = "0 8 * * *",
) -> tuple[BusinessConfig, ReportSchedule]:
    """Persist Artemea's Google Sheets connector and daily report schedule."""

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone=owner_phone,
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="artemea-google-sheets",
                connector_type="google_sheets",
                label="Orvo Brain - Artemea Control Plane",
                params={"spreadsheet_id": spreadsheet_id, "range_name": range_name},
            )
        ],
    )
    schedule = ReportSchedule(
        schedule_id="artemea-daily-report",
        business_id=business.business_id,
        cron_expression=cron_expression,
        report_type="daily",
        enabled=True,
    )
    store.save_business_config(business)
    store.save_schedule(schedule)
    return business, schedule
