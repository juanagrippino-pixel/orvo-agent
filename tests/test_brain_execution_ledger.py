from datetime import date, datetime, timezone

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.dispatch import ReportDispatchResult
from app.brain.execution_ledger import (
    _event_certification_metadata,
    _metric_certification_metadata,
    record_pipeline_failure,
    record_pipeline_success,
)
from app.brain.models import DailyReport, Evidence, Metric
from app.brain.operational_cases import InMemoryOperationalCaseStore
from app.brain.pipeline import PipelineResult
from app.brain.run_ledger import InMemoryRunLedger


def utc_dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 24, hour, minute, tzinfo=timezone.utc)


def test_event_certification_metadata_includes_issue_messages_for_connector_logging():
    certification = _event_certification_metadata(
        "google_sheets",
        ["connector.execution.succeeded", "connector.health.paused"],
    )

    assert certification == {
        "status": "warning",
        "issue_count": 1,
        "events": [
            "connector.execution.succeeded",
            "connector.health.paused",
        ],
        "issues": [
            {
                "code": "undeclared_health_state",
                "event_type": "connector.health.paused",
                "index": 1,
                "message": (
                    "google_sheets connector emitted health state paused outside declared "
                    "health states: ok, degraded, stale, unauthorized, rate_limited, failed"
                ),
            }
        ],
    }


def test_event_certification_metadata_accepts_connector_specific_health_states():
    certification = _event_certification_metadata(
        "tiendanube",
        [
            "connector.execution.succeeded",
            "connector.health.partial_inventory_unavailable",
        ],
    )

    assert certification == {
        "status": "passed",
        "issue_count": 0,
        "events": [
            "connector.execution.succeeded",
            "connector.health.partial_inventory_unavailable",
        ],
        "issues": [],
    }


def test_metric_certification_metadata_includes_issue_messages_for_connector_logging():
    certification = _metric_certification_metadata(
        "google_sheets",
        [
            Metric(
                key="unanswered_conversations",
                label="Chats sin responder",
                value=5,
                unit="count",
                evidence=[Evidence(source="google_sheets", label="Sheet Artemea")],
            )
        ],
    )

    assert certification == {
        "status": "warning",
        "issue_count": 1,
        "issues": [
            {
                "code": "undeclared_family",
                "key": "unanswered_conversations",
                "index": 0,
                "message": (
                    "Metric key 'unanswered_conversations' (canonical "
                    "'support.conversations.unanswered_count') has family "
                    "'support.conversations' which is not declared in connector "
                    "'google_sheets' emitted_metric_families=['commerce.orders', "
                    "'commerce.revenue', 'commerce.inventory', 'runtime.freshness', "
                    "'runtime.data_quality']"
                ),
            }
        ],
    }


def test_event_certification_metadata_degrades_to_warning_for_unknown_connector_type():
    certification = _event_certification_metadata(
        "legacy_connector",
        ["connector.execution.succeeded", "connector.health.ok"],
    )

    assert certification == {
        "status": "warning",
        "issue_count": 1,
        "events": [
            "connector.execution.succeeded",
            "connector.health.ok",
        ],
        "issues": [
            {
                "code": "unknown_connector_type",
                "event_type": "connector_type",
                "index": None,
                "message": "Unknown connector type: legacy_connector",
            }
        ],
    }


def test_metric_certification_metadata_degrades_to_warning_for_unknown_connector_type():
    certification = _metric_certification_metadata(
        "legacy_connector",
        [
            Metric(
                key="orders_today",
                label="Pedidos",
                value=3,
                unit="count",
                evidence=[Evidence(source="legacy_connector", label="Legacy")],
            )
        ],
    )

    assert certification == {
        "status": "warning",
        "issue_count": 1,
        "issues": [
            {
                "code": "unknown_connector_type",
                "key": "connector_type",
                "index": None,
                "message": "Unknown connector type: legacy_connector",
            }
        ],
    }


def test_record_pipeline_failure_maps_connector_auth_errors_to_typed_health_state():
    class UnauthorizedConnectorError(RuntimeError):
        connector_type = "tiendanube"
        connector_id = "tn-main"

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "123", "access_token": "tn_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        run_id="run-auth-failure",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )

    record_pipeline_failure(
        run_ledger=ledger,
        run_id=run.run_id,
        error=UnauthorizedConnectorError("HTTP 401 Unauthorized access_token=raw_secret"),
        business=business,
        business_id=business.business_id,
        connector_types=["tiendanube"],
    )

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    [outcome] = reloaded.connector_outcomes
    assert outcome.status == "failed"
    assert outcome.health_state == "unauthorized"
    assert outcome.metadata["health_policy"]["allowed_states"] == [
        "ok",
        "degraded",
        "stale",
        "unauthorized",
        "rate_limited",
        "failed",
    ]
    assert outcome.error_summary is not None
    assert "raw_secret" not in outcome.error_summary


def test_record_pipeline_success_records_event_certification_for_connector_outcomes():
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "123", "access_token": "tn_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        run_id="run-success-events",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )
    pipeline = PipelineResult(
        report=DailyReport(
            business_name=business.business_name,
            report_date=date(2026, 5, 24),
            metrics=[
                Metric(
                    key="orders_today",
                    label="Pedidos",
                    value=3,
                    unit="count",
                    evidence=[Evidence(source="tiendanube", label="TN principal")],
                )
            ],
            insights=[],
        ),
        dispatch=ReportDispatchResult(
            status="sent",
            idempotency_key="artemea:2026-05-24:daily",
        ),
    )

    record_pipeline_success(
        run_ledger=ledger,
        run_id=run.run_id,
        business=business,
        connector_types=["tiendanube"],
        pipeline=pipeline,
    )

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    [outcome] = reloaded.connector_outcomes
    assert outcome.metadata["emitted_events"] == [
        "connector.execution.succeeded",
        "connector.health.ok",
    ]
    assert outcome.metadata["event_certification"] == {
        "status": "passed",
        "issue_count": 0,
        "events": [
            "connector.execution.succeeded",
            "connector.health.ok",
        ],
        "issues": [],
    }
    assert outcome.metadata["emitted_event_families"] == ["connector.execution", "connector.health"]


def test_record_pipeline_success_marks_run_failed_when_case_projection_crashes(monkeypatch):
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "123", "access_token": "tn_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        run_id="run-success-post-processing-failure",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )
    pipeline = PipelineResult(
        report=DailyReport(
            business_name=business.business_name,
            report_date=date(2026, 5, 24),
            metrics=[
                Metric(
                    key="orders_today",
                    label="Pedidos",
                    value=3,
                    unit="count",
                    evidence=[Evidence(source="tiendanube", label="TN principal")],
                )
            ],
            insights=[],
        ),
        dispatch=ReportDispatchResult(
            status="sent",
            idempotency_key="artemea:2026-05-24:daily",
        ),
    )

    def explode(**_kwargs):
        raise RuntimeError("case projection exploded access_token=raw_runtime_secret")

    monkeypatch.setattr("app.brain.execution_ledger.upsert_cases_from_report", explode)

    with pytest.raises(RuntimeError, match="case projection exploded"):
        record_pipeline_success(
            run_ledger=ledger,
            run_id=run.run_id,
            business=business,
            connector_types=["tiendanube"],
            pipeline=pipeline,
            summary_metadata={"schedule_id": "sched-1"},
        )

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    assert reloaded.status == "failed"
    assert reloaded.finished_at is not None
    assert reloaded.summary_metadata["report_type"] == "daily"
    assert reloaded.summary_metadata["schedule_id"] == "sched-1"
    assert reloaded.summary_metadata["failure_stage"] == "post_connector_success_recording"
    assert reloaded.error_summary == "RuntimeError: case projection exploded access_token=[REDACTED]"
    assert len(reloaded.connector_outcomes) == 1
    assert reloaded.artifacts == []
    assert reloaded.dispatch_outcomes == []


def test_record_pipeline_failure_maps_rate_limit_errors_to_typed_health_state():
    class RateLimitedConnectorError(RuntimeError):
        connector_type = "meta_ads"
        connector_id = "meta-main"

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="meta-main",
                connector_type="meta_ads",
                label="Meta principal",
                params={"ad_account_id": "act_123", "access_token": "meta_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        run_id="run-rate-failure",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )

    record_pipeline_failure(
        run_ledger=ledger,
        run_id=run.run_id,
        error=RateLimitedConnectorError("HTTP 429 rate limit exceeded"),
        business=business,
        business_id=business.business_id,
        connector_types=["meta_ads"],
    )

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    [outcome] = reloaded.connector_outcomes
    assert outcome.status == "failed"
    assert outcome.health_state == "rate_limited"


def test_record_pipeline_failure_records_event_certification_for_connector_outcomes():
    class UnauthorizedConnectorError(RuntimeError):
        connector_type = "tiendanube"
        connector_id = "tn-main"

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "123", "access_token": "tn_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        run_id="run-failure-events",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )

    record_pipeline_failure(
        run_ledger=ledger,
        run_id=run.run_id,
        error=UnauthorizedConnectorError("HTTP 401 Unauthorized access_token=raw_secret"),
        business=business,
        business_id=business.business_id,
        connector_types=["tiendanube"],
    )

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    [outcome] = reloaded.connector_outcomes
    assert outcome.metadata["emitted_events"] == [
        "connector.execution.failed",
        "connector.health.unauthorized",
    ]
    assert outcome.metadata["event_certification"] == {
        "status": "passed",
        "issue_count": 0,
        "events": [
            "connector.execution.failed",
            "connector.health.unauthorized",
        ],
        "issues": [],
    }
    assert outcome.metadata["emitted_event_families"] == ["connector.execution", "connector.health"]


def test_record_pipeline_failure_records_detailed_health_event_and_metadata_when_declared():
    class TimeoutConnectorError(RuntimeError):
        connector_type = "tiendanube"
        connector_id = "tn-main"

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "123", "access_token": "tn_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        run_id="run-failure-detailed-events",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )

    record_pipeline_failure(
        run_ledger=ledger,
        run_id=run.run_id,
        error=TimeoutConnectorError("request timed out while fetching orders access_token=raw_secret"),
        business=business,
        business_id=business.business_id,
        connector_types=["tiendanube"],
    )

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    [outcome] = reloaded.connector_outcomes
    assert outcome.health_state == "failed"
    assert outcome.metadata["health_detail"] == "network_error"
    assert outcome.metadata["emitted_events"] == [
        "connector.execution.failed",
        "connector.health.failed",
        "connector.health.network_error",
    ]
    assert outcome.metadata["event_certification"] == {
        "status": "passed",
        "issue_count": 0,
        "events": [
            "connector.execution.failed",
            "connector.health.failed",
            "connector.health.network_error",
        ],
        "issues": [],
    }


def test_record_pipeline_success_finalizes_partial_when_secondary_owner_brief_dispatcher_raises():
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "123", "access_token": "tn_test_token"},
            )
        ],
    )
    ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()
    run = ledger.create_run(
        run_id="run-owner-brief-secondary-failure",
        business_id=business.business_id,
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )
    pipeline = PipelineResult(
        report=DailyReport(
            business_name=business.business_name,
            report_date=date(2026, 5, 24),
            metrics=[],
            insights=[],
        ),
        dispatch=ReportDispatchResult(
            status="sent",
            idempotency_key="artemea:2026-05-24:daily",
        ),
    )

    def broken_owner_brief_dispatcher(_owner_cases):
        raise RuntimeError("owner brief failed access_token=raw_dispatch_secret")

    secondary_dispatch = record_pipeline_success(
        run_ledger=ledger,
        case_store=case_store,
        run_id=run.run_id,
        business=business,
        connector_types=["tiendanube"],
        pipeline=pipeline,
        case_brief_dispatcher=broken_owner_brief_dispatcher,
    )

    assert secondary_dispatch is not None
    assert secondary_dispatch.status == "failed"
    assert secondary_dispatch.error == "RuntimeError: owner brief failed access_token=[REDACTED]"

    reloaded = ledger.get_run(run.run_id)
    assert reloaded is not None
    assert reloaded.status == "partial"
    assert reloaded.finished_at is not None
    assert reloaded.summary_metadata["case_brief_dispatch_status"] == "failed"
    assert reloaded.error_summary is None
    assert [outcome.status for outcome in reloaded.dispatch_outcomes] == ["sent", "failed"]
    assert [outcome.metadata["message_type"] for outcome in reloaded.dispatch_outcomes] == [
        "daily_report",
        "owner_case_brief",
    ]
    owner_brief_outcome = reloaded.dispatch_outcomes[-1]
    assert owner_brief_outcome.metadata["case_count"] == 0
    assert owner_brief_outcome.error_summary == "RuntimeError: owner brief failed access_token=[REDACTED]"
    assert "raw_dispatch_secret" not in repr(reloaded)
