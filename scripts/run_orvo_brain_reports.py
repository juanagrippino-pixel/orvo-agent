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
from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief
from app.brain.execution_ledger import begin_pipeline_run, record_pipeline_failure, record_pipeline_success
from app.brain.operational_cases import OperationalCaseStore
from app.brain.pipeline import (
    run_csv_daily_report_pipeline,
    run_google_sheets_daily_report_pipeline,
    run_mercadolibre_daily_report_pipeline,
    run_meta_ads_daily_report_pipeline,
    run_tiendanube_daily_report_pipeline,
    run_woocommerce_daily_report_pipeline,
)
from app.brain.runner import run_due_daily_reports
from app.brain.run_ledger import RunLedger
from app.brain.runtime import RuntimeCompileError, compile_business_runtime, runtime_run_metadata
from app.brain.storage import (
    SQLiteConfigStore,
    SQLiteIdempotencyStore,
    SQLiteOperationalCaseStore,
    SQLiteRunLedger,
    init_schema,
)


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
    return (
        conn,
        SQLiteConfigStore(conn),
        SQLiteIdempotencyStore(conn),
        SQLiteRunLedger(conn),
        SQLiteOperationalCaseStore(conn),
    )


def _with_runtime_metadata(result, metadata: dict):
    return result.model_copy(update={"runtime_metadata": metadata}, deep=True)


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
    woocommerce_http_client=None,
    run_ledger: RunLedger | None = None,
    case_store: OperationalCaseStore | None = None,
):
    try:
        runtime = compile_business_runtime(business, run_mode="forced")
    except RuntimeCompileError as exc:
        if any("unsupported connector_type" in error or "no enabled connectors" in error for error in exc.errors):
            raise ValueError(f"Business {business.business_id} has no supported enabled connector") from exc
        raise

    connector_type = runtime.execution_plan.daily_connector_types[0] if runtime.execution_plan.daily_connector_types else None
    executed_connector_types = [connector_type] if connector_type else []
    runtime_metadata = runtime_run_metadata(runtime)
    runtime_metadata = {**runtime_metadata, "connector_types": executed_connector_types}
    runtime_metadata = begin_pipeline_run(
        run_ledger=run_ledger,
        business_id=business.business_id,
        trigger_type="forced",
        runtime_metadata=runtime_metadata,
        summary_metadata={"report_type": "daily", "connector_types": executed_connector_types},
    )
    run_id = runtime_metadata.get("run_id")

    try:
        if connector_type == "google_sheets":
            result = run_google_sheets_daily_report_pipeline(
                business=business,
                report_date=report_date,
                delivery_client=delivery_client,
                idempotency_store=idempotency_store,
                sheets_service=sheets_service_factory(),
            )
        elif connector_type == "tiendanube":
            result = run_tiendanube_daily_report_pipeline(
                business=business,
                report_date=report_date,
                delivery_client=delivery_client,
                idempotency_store=idempotency_store,
                http_client=tiendanube_http_client,
            )
        elif connector_type == "mercadolibre":
            result = run_mercadolibre_daily_report_pipeline(
                business=business,
                report_date=report_date,
                delivery_client=delivery_client,
                idempotency_store=idempotency_store,
                http_client=mercadolibre_http_client,
            )
        elif connector_type == "meta_ads":
            result = run_meta_ads_daily_report_pipeline(
                business=business,
                report_date=report_date,
                delivery_client=delivery_client,
                idempotency_store=idempotency_store,
                http_client=meta_ads_http_client,
            )
        elif connector_type == "woocommerce":
            result = run_woocommerce_daily_report_pipeline(
                business=business,
                report_date=report_date,
                delivery_client=delivery_client,
                idempotency_store=idempotency_store,
                http_client=woocommerce_http_client,
            )
        elif connector_type == "csv":
            result = run_csv_daily_report_pipeline(
                business=business,
                report_date=report_date,
                delivery_client=delivery_client,
                idempotency_store=idempotency_store,
            )
        else:
            raise ValueError(f"Business {business.business_id} has no supported enabled connector")
    except Exception as exc:
        record_pipeline_failure(
            run_ledger=run_ledger,
            case_store=case_store,
            run_id=run_id,
            error=exc,
            business=business,
            business_id=business.business_id,
            connector_types=executed_connector_types,
            summary_metadata={"report_type": "daily"},
        )
        raise

    result = _with_runtime_metadata(result, runtime_metadata)
    case_brief_dispatch = record_pipeline_success(
        run_ledger=run_ledger,
        case_store=case_store,
        run_id=run_id,
        business=business,
        connector_types=executed_connector_types,
        pipeline=result,
        summary_metadata={"report_type": "daily"},
        case_brief_dispatcher=lambda cases: dispatch_owner_case_brief(
            cases,
            business,
            report_date,
            delivery_client,
            idempotency_store,
        ),
    )
    if case_brief_dispatch is not None:
        result = result.model_copy(update={"case_brief_dispatch": case_brief_dispatch}, deep=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Orvo Brain report pipelines")
    parser.add_argument("--db", default=os.environ.get("ORVO_BRAIN_DB_PATH", "orvo_brain.sqlite3"))
    parser.add_argument("--business-id", default="artemea")
    parser.add_argument("--report-date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true", help="Generate report without calling WhatsApp API")
    parser.add_argument("--force", action="store_true", help="Run the selected business now instead of only due schedules")
    args = parser.parse_args()

    conn, config_store, idempotency_store, run_ledger, case_store = open_runtime(args.db)
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
                run_ledger=run_ledger,
                case_store=case_store,
            )
            output = [
                {
                    "business_id": business.business_id,
                    "runtime_metadata": result.runtime_metadata,
                    "dispatch": result.dispatch.model_dump(mode="json"),
                    "report": result.report.model_dump(mode="json"),
                }
            ]
        else:
            results = run_due_daily_reports(
                config_store=config_store,
                idempotency_store=runtime_idempotency_store,
                delivery_client=delivery_client,
                sheets_service=get_sheets_service(),
                now=datetime.now(tz=timezone.utc),
                run_ledger=run_ledger,
                case_store=case_store,
            )
            output = [
                {
                    "business_id": result.business_id,
                    "schedule_id": result.schedule_id,
                    "runtime_metadata": result.runtime_metadata,
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
