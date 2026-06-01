import logging
from datetime import datetime, timezone
import json
from unittest.mock import MagicMock

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig, InMemoryConfigStore, ReportSchedule
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.run_ledger import InMemoryRunLedger
from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection


def make_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="sheet",
                    connector_type="google_sheets",
                    label="Sheet Artemea",
                    params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-daily-report",
            business_id="artemea",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def fake_sheets_service():
    class FakeExecute:
        def execute(self):
            return {
                "values": [
                    ["fecha", "ventas", "ordenes", "stock", "conversaciones_sin_responder"],
                    ["2026-05-19", "70000", "12", "3", "8"],
                    ["2026-05-18", "100000", "10", "10", "1"],
                ]
            }

    class FakeValues:
        def get(self, spreadsheetId, range):
            return FakeExecute()

    class FakeSpreadsheets:
        def values(self):
            return FakeValues()

    class FakeService:
        def spreadsheets(self):
            return FakeSpreadsheets()

    return FakeService()


def test_enabled_daily_connector_types_are_discovered_from_registry_metadata(monkeypatch):
    from app.brain.connector_registry import (
        CAPABILITY_DAILY_REPORT,
        ConnectorRegistry,
        ConnectorSpec,
        get_connector_spec,
    )
    from app.brain.runner import _enabled_daily_connector_types

    registry = ConnectorRegistry(
        (
            get_connector_spec("google_sheets"),
            ConnectorSpec(
                connector_type="shopify",
                display_name="Shopify",
                adapter_module="app.brain.adapters.csv_file",
                report_factory="build_daily_report_from_csv_file",
                capabilities=(CAPABILITY_DAILY_REPORT,),
                required_config_fields=("shop_id",),
            ),
            ConnectorSpec(
                connector_type="sample_payload",
                display_name="Sample payload",
                adapter_module="app.brain.adapters.sample",
                report_factory="build_daily_report_from_payload",
                capabilities=("manual_payload",),
            ),
        )
    )
    monkeypatch.setattr("app.brain.runner.default_connector_registry", lambda: registry)
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="manual",
                connector_type="sample_payload",
                label="Manual sample",
                params={},
            ),
            ConnectorConfig(
                connector_id="shopify-main",
                connector_type="shopify",
                label="Shopify main",
                params={"shop_id": "ar-shop"},
            ),
            ConnectorConfig(
                connector_id="sheet",
                connector_type="google_sheets",
                label="Sheet Artemea",
                params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
            ),
            ConnectorConfig(
                connector_id="shopify-disabled",
                connector_type="shopify",
                label="Shopify disabled",
                params={"shop_id": "disabled"},
                enabled=False,
            ),
        ],
    )

    assert _enabled_daily_connector_types(business) == ["shopify", "google_sheets"]


def test_run_due_daily_reports_dispatches_due_google_sheet_report():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),  # 09:00 Buenos Aires
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea"
    assert results[0].dispatch.status == "sent"
    assert results[0].runtime_metadata["run_mode"] == "scheduled"
    assert results[0].runtime_metadata == results[0].pipeline.runtime_metadata
    assert results[0].runtime_metadata["config_digest"].startswith("sha256:")
    delivery.send_text.assert_called_once()


def test_run_due_daily_reports_records_scheduled_run_in_ledger():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.ledger", error=None)
    ledger = InMemoryRunLedger()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        run_ledger=ledger,
    )

    assert len(results) == 1
    assert results[0].runtime_metadata["run_id"]
    [record] = ledger.list_runs(business_id="artemea")
    assert record.run_id == results[0].runtime_metadata["run_id"]
    assert record.trigger_type == "scheduled"
    assert record.status == "succeeded"
    assert record.config_digest == results[0].runtime_metadata["config_digest"]
    assert record.summary_metadata["schedule_id"] == "artemea-daily-report"
    assert record.summary_metadata["report_type"] == "daily"
    assert record.summary_metadata["connector_refs"] == [
        {
            "connector_id": "sheet",
            "connector_type": "google_sheets",
            "label": "Sheet Artemea",
            "secret_refs": {},
            "required_params": ["spreadsheet_id", "range_name"],
            "secret_param_names": [],
            "legacy_secret_param_names": [],
            "capabilities": ["daily_report", "sheet_import"],
            "emitted_metric_families": [
                "commerce.orders",
                "commerce.revenue",
                "commerce.inventory",
                "runtime.freshness",
                "runtime.data_quality",
            ],
            "supported_runtime_modes": ["preview", "forced", "scheduled", "operator_triggered"],
            "executor_factory_path": "app.brain.adapters.google_sheets.build_daily_report_from_sheet",
            "health_policy": {
                "readiness_check": "metadata_only",
                "supports_health_check": False,
                "degraded_state": "degraded",
            },
            "required_scopes": ["spreadsheets.readonly"],
            "rate_limit_policy": {
                "default_timeout_seconds": 30,
                "requests_per_minute": None,
                "retry_policy": "adapter_default",
            },
        }
    ]
    assert "abc123" not in json.dumps(record.summary_metadata)
    assert record.connector_outcomes[0].connector_id == "sheet"
    assert record.connector_outcomes[0].connector_type == "google_sheets"
    assert record.connector_outcomes[0].status == "succeeded"
    assert record.connector_outcomes[0].metadata == {
        "label": "Sheet Artemea",
        "executor_factory_path": "app.brain.adapters.google_sheets.build_daily_report_from_sheet",
        "capabilities": ["daily_report", "sheet_import"],
        "emitted_metric_families": [
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ],
        "required_scopes": ["spreadsheets.readonly"],
        "metric_certification": {
            "status": "warning",
            "issue_count": 1,
            "issues": [
                {
                    "code": "undeclared_family",
                    "key": "unanswered_conversations",
                    "index": 4,
                }
            ],
        },
    }
    assert "abc123" not in json.dumps(record.connector_outcomes[0].metadata)
    assert record.dispatch_outcomes[0].status == "sent"
    assert record.dispatch_outcomes[0].message_id == "wamid.ledger"
    assert record.artifacts[0].artifact_type == "daily_report"


def test_run_due_daily_reports_records_failed_connector_outcome_on_scheduled_failure():
    from app.brain.runner import run_due_daily_reports

    class FailingExecute:
        def execute(self):
            raise RuntimeError("sheets 500 access_token=raw_failure_secret")

    class FailingValues:
        def get(self, spreadsheetId, range):
            return FailingExecute()

    class FailingSpreadsheets:
        def values(self):
            return FailingValues()

    class FailingSheetsService:
        def spreadsheets(self):
            return FailingSpreadsheets()

    delivery = MagicMock()
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    with pytest.raises(RuntimeError, match="raw_failure_secret"):
        run_due_daily_reports(
            config_store=make_store(),
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=delivery,
            sheets_service=FailingSheetsService(),
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
            run_ledger=run_ledger,
            case_store=case_store,
        )

    [run] = run_ledger.list_runs(business_id="artemea")
    assert run.status == "failed"
    assert run.finished_at is not None
    assert len(run.connector_outcomes) == 1
    failed_connector = run.connector_outcomes[0]
    assert failed_connector.connector_id == "sheet"
    assert failed_connector.connector_type == "google_sheets"
    assert failed_connector.status == "failed"
    assert failed_connector.finished_at is not None
    assert failed_connector.error_summary is not None
    assert "raw_failure_secret" not in failed_connector.error_summary
    assert failed_connector.metadata == {
        "failure_stage": "pre_dispatch",
        "label": "Sheet Artemea",
        "executor_factory_path": "app.brain.adapters.google_sheets.build_daily_report_from_sheet",
        "capabilities": ["daily_report", "sheet_import"],
        "emitted_metric_families": [
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ],
        "required_scopes": ["spreadsheets.readonly"],
    }
    assert run.artifacts == []
    assert run.dispatch_outcomes == []
    assert run.summary_metadata["schedule_id"] == "artemea-daily-report"
    assert run.summary_metadata["report_type"] == "daily"
    assert "raw_failure_secret" not in run.model_dump_json()
    delivery.send_text.assert_not_called()


def test_run_due_daily_reports_records_exact_failed_connector_for_multi_connector_scheduled_failure(tmp_path):
    from app.brain.pipeline import PipelineConnectorError
    from app.brain.runner import run_due_daily_reports

    store = InMemoryConfigStore()
    missing_csv_path = tmp_path / "missing.csv"
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-multi-source",
            business_name="Artemea Multi Source",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="sheet",
                    connector_type="google_sheets",
                    label="Sheet Artemea",
                    params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
                ),
                ConnectorConfig(
                    connector_id="csv-orders",
                    connector_type="csv",
                    label="CSV Orders",
                    params={"csv_path": str(missing_csv_path)},
                ),
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-multi-source-daily-report",
            business_id="artemea-multi-source",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    delivery = MagicMock()
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    with pytest.raises(PipelineConnectorError) as raised:
        run_due_daily_reports(
            config_store=store,
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=delivery,
            sheets_service=fake_sheets_service(),
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
            run_ledger=run_ledger,
            case_store=case_store,
        )
    assert raised.value.connector_type == "csv"
    assert raised.value.connector_id == "csv-orders"
    assert isinstance(raised.value.original_exception, FileNotFoundError)

    [run] = run_ledger.list_runs(business_id="artemea-multi-source")
    assert run.status == "failed"
    assert [(out.connector_id, out.connector_type, out.status) for out in run.connector_outcomes] == [
        ("csv-orders", "csv", "failed")
    ]
    failed_connector = run.connector_outcomes[0]
    assert failed_connector.error_summary is not None
    assert "missing.csv" in failed_connector.error_summary
    assert failed_connector.metadata["label"] == "CSV Orders"
    assert failed_connector.metadata["failure_stage"] == "pre_dispatch"
    assert run.artifacts == []
    assert run.dispatch_outcomes == []
    assert run.summary_metadata["schedule_id"] == "artemea-multi-source-daily-report"
    assert run.summary_metadata["report_type"] == "daily"
    assert run.summary_metadata["cases_opened"] == 2
    assert {case.entity_scope["id"] for case in case_store.list_cases(business_id="artemea-multi-source")} == {
        "google_sheets",
        "csv",
    }
    delivery.send_text.assert_not_called()


def test_run_due_daily_reports_persists_operational_cases_and_links_ledger_artifact():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.cases", error=None)
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        run_ledger=run_ledger,
        case_store=case_store,
    )

    assert len(results) == 1
    cases = case_store.list_cases(business_id="artemea")
    assert {case.case_type for case in cases} == {"sales_drop", "stockout_risk", "unanswered_conversations"}
    assert all(case.status == "open" for case in cases)
    assert all(case.latest_run_id == results[0].runtime_metadata["run_id"] for case in cases)

    [run] = run_ledger.list_runs(business_id="artemea")
    assert set(run.artifacts[0].operational_case_ids) == {case.case_id for case in cases}
    assert run.summary_metadata["cases_opened"] == 3
    assert run.summary_metadata["cases_updated"] == 0


def test_run_due_daily_reports_sends_owner_case_brief_after_cases_are_persisted():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.side_effect = [
        DeliveryResult(success=True, message_id="wamid.daily", error=None),
        DeliveryResult(success=True, message_id="wamid.case-brief", error=None),
    ]
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        run_ledger=run_ledger,
        case_store=case_store,
    )

    assert len(results) == 1
    assert results[0].pipeline.case_brief_dispatch is not None
    assert results[0].pipeline.case_brief_dispatch.status == "sent"
    assert results[0].pipeline.case_brief_dispatch.idempotency_key == "artemea/2026-05-19/owner_case_brief"
    assert delivery.send_text.call_count == 2
    _daily_phone, daily_text = delivery.send_text.call_args_list[0].args
    brief_phone, brief_text = delivery.send_text.call_args_list[1].args
    assert brief_phone == "+5491149724933"
    assert "Brief operativo" in brief_text
    assert "Caso:" in brief_text
    assert "Orvo Brain" in daily_text

    [run] = run_ledger.list_runs(business_id="artemea")
    assert [out.metadata.get("message_type") for out in run.dispatch_outcomes] == ["daily_report", "owner_case_brief"]
    assert [out.message_id for out in run.dispatch_outcomes] == ["wamid.daily", "wamid.case-brief"]
    assert run.summary_metadata["case_brief_dispatch_status"] == "sent"


def test_run_due_daily_reports_owner_brief_includes_in_progress_actionable_cases():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.side_effect = [
        DeliveryResult(success=True, message_id="wamid.daily", error=None),
        DeliveryResult(success=True, message_id="wamid.case-brief", error=None),
    ]
    case_store = InMemoryOperationalCaseStore()
    preexisting = case_store.upsert_detection(
        OperationalCaseDetection(
            business_id="artemea",
            case_type="stockout_risk",
            dedupe_key="artemea/stockout_risk/business/monitored/commerce.inventory/daily",
            title="Stock crítico",
            severity="critical",
            priority_score=100,
            entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
            evidence_refs=["evidence://tiendanube/stock/preexisting"],
            run_id="run-preexisting",
            artifact_refs=["ledger://runs/run-preexisting/daily-report"],
        ),
        detected_at=datetime(2026, 5, 18, 12, tzinfo=timezone.utc),
    )
    case_store.transition_case(
        preexisting.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Owner is restocking now",
        transitioned_at=datetime(2026, 5, 18, 13, tzinfo=timezone.utc),
    )

    run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        run_ledger=InMemoryRunLedger(),
        case_store=case_store,
    )

    assert delivery.send_text.call_count == 2
    _brief_phone, brief_text = delivery.send_text.call_args_list[1].args
    assert "Stock crítico" in brief_text
    assert preexisting.case_id in brief_text


def test_run_due_daily_reports_records_partial_when_owner_case_brief_raises():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.side_effect = [
        DeliveryResult(success=True, message_id="wamid.daily", error=None),
        RuntimeError("brief provider exploded access_token=raw_runtime_secret"),
    ]
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        run_ledger=run_ledger,
        case_store=case_store,
    )

    assert len(results) == 1
    assert results[0].pipeline.case_brief_dispatch is not None
    assert results[0].pipeline.case_brief_dispatch.status == "failed"
    assert results[0].pipeline.case_brief_dispatch.idempotency_key == "artemea/2026-05-19/owner_case_brief"
    assert "raw_runtime_secret" not in (results[0].pipeline.case_brief_dispatch.error or "")

    [run] = run_ledger.list_runs(business_id="artemea")
    assert run.status == "partial"
    assert run.finished_at is not None
    assert [out.metadata.get("message_type") for out in run.dispatch_outcomes] == ["daily_report", "owner_case_brief"]
    assert run.dispatch_outcomes[1].status == "failed"
    assert "raw_runtime_secret" not in (run.dispatch_outcomes[1].error_summary or "")
    assert run.summary_metadata["case_brief_dispatch_status"] == "failed"


def test_run_due_daily_reports_records_partial_when_daily_dispatch_fails_and_skips_owner_brief():
    """A transient WhatsApp 5xx on the daily report dispatch must:
      - record the run as ``partial`` (data and cases are valid; only delivery failed),
      - leave the daily idempotency key UNMARKED so the next runner tick can retry,
      - NOT attempt the owner case brief (its idempotency would otherwise be lost
        if the daily report is later re-sent on retry — the brief belongs after a
        successful daily report),
      - still persist operational cases and the artifact, since the report data is
        valid even when delivery transiently fails.

    Locks the runtime contract that a delivery transient downgrades the run to
    ``partial`` without silently dropping the daily report or sending the brief
    out of order.
    """
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(
        success=False, message_id=None, error="HTTP 502"
    )
    idempotency = InMemoryIdempotencyStore()
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=idempotency,
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        run_ledger=run_ledger,
        case_store=case_store,
    )

    assert len(results) == 1
    pipeline = results[0].pipeline
    assert pipeline.dispatch.status == "failed"
    assert pipeline.dispatch.error == "HTTP 502"
    assert pipeline.dispatch.idempotency_key == "artemea/2026-05-19/daily"
    assert pipeline.case_brief_dispatch is None

    # Idempotency must remain unmarked on both keys so retry works end-to-end.
    assert not idempotency.has("artemea/2026-05-19/daily")
    assert not idempotency.has("artemea/2026-05-19/owner_case_brief")
    # Owner case brief must NOT have been attempted yet.
    assert delivery.send_text.call_count == 1

    [run] = run_ledger.list_runs(business_id="artemea")
    assert run.status == "partial"
    assert run.finished_at is not None
    # Connector ran successfully — only the delivery transient downgrades the run.
    assert [out.status for out in run.connector_outcomes] == ["succeeded"]
    # The artifact is still produced from the valid report data.
    assert len(run.artifacts) == 1
    assert run.artifacts[0].artifact_type == "daily_report"
    # Only the daily_report dispatch outcome is recorded (owner brief was skipped).
    assert [out.metadata.get("message_type") for out in run.dispatch_outcomes] == ["daily_report"]
    assert run.dispatch_outcomes[0].status == "failed"
    assert run.dispatch_outcomes[0].error_summary == "HTTP 502"
    # case_brief_dispatch_status must NOT be present since the brief was never attempted.
    assert "case_brief_dispatch_status" not in run.summary_metadata
    # Cases derived from the report data are still upserted.
    assert run.summary_metadata["cases_opened"] == 3
    assert run.summary_metadata["report_type"] == "daily"
    assert run.summary_metadata["schedule_id"] == "artemea-daily-report"
    cases = case_store.list_cases(business_id="artemea")
    assert {case.case_type for case in cases} == {
        "sales_drop",
        "stockout_risk",
        "unanswered_conversations",
    }


def test_run_due_daily_reports_skips_when_not_due():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),  # 10:00 Buenos Aires
    )

    assert results == []
    delivery.send_text.assert_not_called()


def make_tiendanube_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn",
                    connector_type="tiendanube",
                    label="Tiendanube Artemea",
                    params={"store_id": "12345", "access_token": "tn_token", "include_stock": False},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-tiendanube-daily-report",
            business_id="artemea",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


class FakeTiendanubeResponse:
    status_code = 200
    headers = {}

    def json(self):
        return [{"id": 1, "status": "paid", "total": "42000"}]


class FakeTiendanubeClient:
    def get(self, url, **kwargs):
        return FakeTiendanubeResponse()


def test_run_due_daily_reports_dispatches_due_tiendanube_report():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.tn", error=None)

    results = run_due_daily_reports(
        config_store=make_tiendanube_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        tiendanube_http_client=FakeTiendanubeClient(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "revenue_today" and metric.value == 42000 for metric in results[0].pipeline.report.metrics)
    delivery.send_text.assert_called_once()


def make_mercadolibre_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-ml",
            business_name="Artemea ML",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="ml",
                    connector_type="mercadolibre",
                    label="MercadoLibre Artemea",
                    params={"seller_id": "12345", "access_token": "ml_token", "site_id": "MLA"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-mercadolibre-daily-report",
            business_id="artemea-ml",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


class FakeMercadoLibreClient:
    def get(self, url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {
            "results": [{"id": 1, "status": "paid", "total_amount": 99000.0}],
            "paging": {"total": 1, "offset": 0, "limit": 50},
        }
        return response


def test_run_due_daily_reports_dispatches_due_mercadolibre_report():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.ml", error=None)

    results = run_due_daily_reports(
        config_store=make_mercadolibre_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        mercadolibre_http_client=FakeMercadoLibreClient(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea-ml"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "revenue_today" and metric.value == 99000 for metric in results[0].pipeline.report.metrics)
    delivery.send_text.assert_called_once()


def make_tiendanube_mercadolibre_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-multi",
            business_name="Artemea Multi",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn",
                    connector_type="tiendanube",
                    label="Tiendanube Artemea",
                    params={"store_id": "12345", "access_token": "tn_token", "include_stock": False},
                ),
                ConnectorConfig(
                    connector_id="ml",
                    connector_type="mercadolibre",
                    label="MercadoLibre Artemea",
                    params={"seller_id": "12345", "access_token": "ml_token", "site_id": "MLA"},
                ),
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-multi-daily-report",
            business_id="artemea-multi",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def test_run_due_daily_reports_merges_tiendanube_and_mercadolibre_metrics_once():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.multi", error=None)

    results = run_due_daily_reports(
        config_store=make_tiendanube_mercadolibre_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        tiendanube_http_client=FakeTiendanubeClient(),
        mercadolibre_http_client=FakeMercadoLibreClient(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea-multi"
    assert results[0].dispatch.status == "sent"

    metrics_by_key = {metric.key: metric for metric in results[0].pipeline.report.metrics}
    assert len(metrics_by_key) == len(results[0].pipeline.report.metrics)
    assert metrics_by_key["revenue_today"].value == 141000
    assert metrics_by_key["orders_today"].value == 2
    assert metrics_by_key["avg_order_value"].value == 99000
    assert {item.source for item in metrics_by_key["revenue_today"].evidence} == {"tiendanube", "mercadolibre"}
    delivery.send_text.assert_called_once()


def make_meta_ads_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-meta",
            business_name="Artemea Meta",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="meta",
                    connector_type="meta_ads",
                    label="Meta Ads Artemea",
                    params={"ad_account_id": "act_12345", "access_token": "meta_test_token"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-meta-ads-daily-report",
            business_id="artemea-meta",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


class FakeMetaAdsClient:
    def __init__(self):
        self.params = None

    def get(self, url, params=None):
        self.params = params
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": [{"spend": "12000", "impressions": "5000", "clicks": "120", "purchase_roas": []}]
        }
        return response


def test_run_due_daily_reports_dispatches_due_meta_ads_report_with_scheduled_date():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.meta", error=None)
    http_client = FakeMetaAdsClient()

    results = run_due_daily_reports(
        config_store=make_meta_ads_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        meta_ads_http_client=http_client,
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea-meta"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "ad_spend_today" and metric.value == 12000 for metric in results[0].pipeline.report.metrics)
    assert http_client.params is not None
    assert json.loads(http_client.params["time_range"]) == {"since": "2026-05-19", "until": "2026-05-19"}
    delivery.send_text.assert_called_once()


def make_artemea_22h00_meta_store():
    """Late-night schedule: 22:00 Buenos Aires = 01:00 UTC the next calendar day."""
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-late",
            business_name="Artemea Late",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="meta",
                    connector_type="meta_ads",
                    label="Meta Ads Artemea Late",
                    params={"ad_account_id": "act_12345", "access_token": "meta_test_token"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-late-daily-report",
            business_id="artemea-late",
            cron_expression="0 22 * * *",
            report_type="daily",
        )
    )
    return store


def test_run_due_daily_reports_report_date_follows_business_local_calendar_for_late_night_schedule():
    """A 22:00 Buenos Aires schedule fires at 01:00 UTC the next UTC day. The owner's
    local calendar date is still May 19, so the report header, idempotency key, and
    Meta Ads time_range must all be stamped May 19 — not May 20 (UTC).

    Locks the runtime contract that ``report_date`` reflects the business owner's
    local calendar day, not the UTC instant of the scheduler tick. Without this,
    end-of-day reports get duplicate or wrong-day idempotency keys and ad metrics
    are pulled for a day the owner has not yet lived.
    """
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.late", error=None)
    http_client = FakeMetaAdsClient()

    # 01:00 UTC on 2026-05-20 == 22:00 Buenos Aires on 2026-05-19.
    now = datetime(2026, 5, 20, 1, 0, tzinfo=timezone.utc)

    results = run_due_daily_reports(
        config_store=make_artemea_22h00_meta_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        meta_ads_http_client=http_client,
        now=now,
    )

    assert len(results) == 1
    pipeline = results[0].pipeline
    assert pipeline.report.report_date.isoformat() == "2026-05-19"
    assert pipeline.dispatch.idempotency_key == "artemea-late/2026-05-19/daily"
    assert http_client.params is not None
    assert json.loads(http_client.params["time_range"]) == {"since": "2026-05-19", "until": "2026-05-19"}


def make_artemea_08h00_store():
    """ARTEMEA production store: 08:00 Buenos Aires schedule = 11:00 UTC."""
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="sheet",
                    connector_type="google_sheets",
                    label="Sheet Artemea",
                    params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-daily-report",
            business_id="artemea",
            cron_expression="0 8 * * *",
            report_type="daily",
        )
    )
    return store


def test_artemea_08h00_schedule_dispatches_at_11h00_utc():
    """08:00 Buenos Aires = 11:00 UTC: runner must fire at exactly that tick."""
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.art", error=None)

    # 11:00 UTC == 08:00 Buenos Aires: should fire
    results = run_due_daily_reports(
        config_store=make_artemea_08h00_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc),
    )
    assert len(results) == 1
    assert results[0].schedule_id == "artemea-daily-report"
    assert results[0].dispatch.status == "sent"
    delivery.send_text.assert_called_once()


def test_artemea_08h00_schedule_does_not_dispatch_at_12h00_utc():
    """12:00 UTC == 09:00 Buenos Aires: must NOT fire for 08:00 schedule."""
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()

    results = run_due_daily_reports(
        config_store=make_artemea_08h00_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )
    assert results == []
    delivery.send_text.assert_not_called()


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


def make_no_connector_store():
    """Business with a due schedule but no enabled connectors."""
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-empty",
            business_name="Artemea Empty",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-empty-daily-report",
            business_id="artemea-empty",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def test_run_due_daily_reports_logs_no_connectors_skip(caplog):
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()

    with caplog.at_level(logging.INFO, logger="app.brain.runner"):
        results = run_due_daily_reports(
            config_store=make_no_connector_store(),
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=delivery,
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        )

    assert results == []
    messages = [r.getMessage() for r in caplog.records]
    assert any("no_connectors" in m and "artemea-empty" in m for m in messages)


def test_run_due_daily_reports_logs_pipeline_start(caplog):
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.log", error=None)

    with caplog.at_level(logging.INFO, logger="app.brain.runner"):
        run_due_daily_reports(
            config_store=make_store(),
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=delivery,
            sheets_service=fake_sheets_service(),
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        )

    messages = [r.getMessage() for r in caplog.records]
    assert any("starting" in m and "artemea" in m for m in messages)
