from datetime import date, datetime, timezone

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.dispatch import ReportDispatchResult
from app.brain.execution_ledger import record_pipeline_failure, record_pipeline_success
from app.brain.models import DailyReport
from app.brain.operational_cases import InMemoryOperationalCaseStore
from app.brain.pipeline import PipelineResult
from app.brain.run_ledger import InMemoryRunLedger


def utc_dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 24, hour, minute, tzinfo=timezone.utc)


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
    assert outcome.metadata["emitted_event_families"] == ["connector.execution", "connector.health"]
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
