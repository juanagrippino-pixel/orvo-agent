from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig, InMemoryConfigStore, ReportSchedule
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.operational_cases import InMemoryOperationalCaseStore
from app.brain.run_ledger import InMemoryRunLedger


class FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class CapturingTiendanubeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeResponse([])


def _delivery():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.secret-ref", error=None)
    return delivery


def _tiendanube_business_with_secret_ref() -> BusinessConfig:
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN principal",
                params={"store_id": "12345", "include_stock": False},
                secret_refs={"access_token": "secret://businesses/artemea/connectors/tn-main/access_token"},
            )
        ],
    )


def test_tiendanube_pipeline_resolves_secret_ref_at_execution_boundary_without_persisting_raw_token():
    from app.brain.pipeline import run_tiendanube_daily_report_pipeline
    from app.brain.runtime import compile_business_runtime
    from app.brain.secret_refs import MappingSecretResolver

    business = _tiendanube_business_with_secret_ref()
    resolver = MappingSecretResolver(
        {"secret://businesses/artemea/connectors/tn-main/access_token": "tn_resolved_runtime_token"}
    )
    client = CapturingTiendanubeClient()

    result = run_tiendanube_daily_report_pipeline(
        business=business,
        report_date=date(2026, 5, 19),
        delivery_client=_delivery(),
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=client,
        secret_resolver=resolver,
    )

    assert client.calls[0]["headers"]["Authentication"] == "bearer tn_resolved_runtime_token"
    assert result.dispatch.status == "sent"
    compiled = compile_business_runtime(business, run_mode="forced")
    serialized_runtime = compiled.model_dump_json()
    assert "tn_resolved_runtime_token" not in serialized_runtime
    assert "tn_resolved_runtime_token" not in business.model_dump_json()
    assert compiled.connectors[0].params == {"store_id": "12345", "include_stock": False}
    assert compiled.connectors[0].secret_refs == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
    }


def test_unresolved_secret_ref_records_redacted_data_stale_case_and_failed_run():
    from app.brain.runner import run_due_daily_reports
    from app.brain.secret_refs import MappingSecretResolver, SecretResolutionError

    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="ml-shop",
            business_name="ML Shop",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="ml-main",
                    connector_type="mercadolibre",
                    label="ML principal",
                    params={"seller_id": "123", "site_id": "MLA"},
                    secret_refs={"access_token": "secret://businesses/ml-shop/connectors/ml-main/access_token"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="ml-daily",
            business_id="ml-shop",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    run_ledger = InMemoryRunLedger()
    case_store = InMemoryOperationalCaseStore()

    with pytest.raises(SecretResolutionError) as raised:
        run_due_daily_reports(
            config_store=store,
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=_delivery(),
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
            run_ledger=run_ledger,
            case_store=case_store,
            secret_resolver=MappingSecretResolver({}),
        )

    assert raised.value.connector_id == "ml-main"
    assert raised.value.connector_type == "mercadolibre"
    assert raised.value.secret_name == "access_token"
    [run] = run_ledger.list_runs(business_id="ml-shop")
    assert run.status == "failed"
    assert run.connector_outcomes[0].connector_id == "ml-main"
    assert run.connector_outcomes[0].connector_type == "mercadolibre"
    assert run.connector_outcomes[0].status == "failed"
    assert "secret://businesses/ml-shop" not in run.model_dump_json()
    cases = case_store.list_cases(business_id="ml-shop")
    assert len(cases) == 1
    assert cases[0].case_type == "data_stale"
    assert cases[0].entity_scope["id"] == "mercadolibre"
    assert "secret://businesses/ml-shop" not in cases[0].model_dump_json()
