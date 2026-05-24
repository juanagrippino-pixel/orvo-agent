"""Run Orvo Brain reports from the SQLite runtime config."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain.adapters.google_sheets import get_sheets_service
from app.brain.delivery import DeliveryResult, WhatsAppDeliveryClient
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.pipeline import run_enabled_connectors_daily_report_pipeline
from app.brain.runner import run_due_daily_reports
from app.brain.storage import SQLiteConfigStore, SQLiteIdempotencyStore, init_schema


class DryRunDeliveryClient(WhatsAppDeliveryClient):
    def __init__(self) -> None:
        super().__init__(phone_id="dry-run", token="dry-run")
        self.messages: list[dict[str, str]] = []

    def send_text(self, phone: str, text: str) -> DeliveryResult:
        self.messages.append({"phone": phone, "text": text})
        return DeliveryResult(success=True, message_id="dry-run", error=None)


def open_runtime(db_path: str):
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    return conn, SQLiteConfigStore(conn), SQLiteIdempotencyStore(conn)


def _enabled_supported_connector_types(business) -> list[str]:
    supported = {"csv", "google_sheets", "mercadolibre", "meta_ads", "tiendanube"}
    connector_types: list[str] = []
    for connector in business.connectors:
        if not connector.enabled or connector.connector_type not in supported:
            continue
        if connector.connector_type not in connector_types:
            connector_types.append(connector.connector_type)
    return connector_types


def run_forced_report(
    *,
    business,
    report_date: date,
    delivery_client,
    idempotency_store,
    sheets_service_factory=get_sheets_service,
    tiendanube_http_client=None,
    mercadolibre_http_client=None,
    meta_ads_http_client=None,
):
    connector_types = _enabled_supported_connector_types(business)
    if not connector_types:
        raise ValueError(f"Business {business.business_id} has no supported enabled connector")

    return run_enabled_connectors_daily_report_pipeline(
        business=business,
        report_date=report_date,
        connector_types=connector_types,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        sheets_service=sheets_service_factory() if "google_sheets" in connector_types else None,
        tiendanube_http_client=tiendanube_http_client,
        mercadolibre_http_client=mercadolibre_http_client,
        meta_ads_http_client=meta_ads_http_client,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Orvo Brain report pipelines")
    parser.add_argument("--db", default=os.environ.get("ORVO_BRAIN_DB_PATH", "orvo_brain.sqlite3"))
    parser.add_argument("--business-id", default="artemea")
    parser.add_argument("--report-date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true", help="Generate report without calling WhatsApp API")
    parser.add_argument("--force", action="store_true", help="Run the selected business now instead of only due schedules")
    args = parser.parse_args()

    conn, config_store, idempotency_store = open_runtime(args.db)
    try:
        delivery_client = DryRunDeliveryClient() if args.dry_run else WhatsAppDeliveryClient.from_env()
        runtime_idempotency_store = InMemoryIdempotencyStore() if args.dry_run else idempotency_store
        if args.force:
            business = config_store.load_business_config(args.business_id)
            if business is None:
                raise SystemExit(f"Business not found: {args.business_id}")
            result = run_forced_report(
                business=business,
                report_date=date.fromisoformat(args.report_date),
                delivery_client=delivery_client,
                idempotency_store=runtime_idempotency_store,
            )
            output = [{"business_id": business.business_id, "dispatch": result.dispatch.model_dump(mode="json"), "report": result.report.model_dump(mode="json")}]
        else:
            results = run_due_daily_reports(
                config_store=config_store,
                idempotency_store=runtime_idempotency_store,
                delivery_client=delivery_client,
                sheets_service=get_sheets_service(),
                now=datetime.now(tz=timezone.utc),
            )
            output = [
                {
                    "business_id": result.business_id,
                    "schedule_id": result.schedule_id,
                    "dispatch": result.pipeline.dispatch.model_dump(mode="json"),
                    "report": result.pipeline.report.model_dump(mode="json"),
                }
                for result in results
            ]
        print(json.dumps({"dry_run": args.dry_run, "results": output}, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
