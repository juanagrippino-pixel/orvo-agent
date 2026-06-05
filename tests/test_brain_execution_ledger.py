from datetime import datetime, timezone

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.execution_ledger import record_pipeline_failure
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
    assert outcome.metadata["required_secret_refs"] == [
        {
            "name": "access_token",
            "provider": "tiendanube_oauth",
            "description": "Tiendanube API access token reference.",
            "scopes": ["orders.read", "products.read"],
            "legacy_config_field": "access_token",
        }
    ]
    assert outcome.metadata["emitted_event_families"] == ["connector.execution", "connector.health"]
    assert outcome.metadata["event_certification"] == {
        "status": "passed",
        "issue_count": 0,
        "issues": [],
        "events": ["connector.execution.failed", "connector.health.unauthorized"],
    }
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
