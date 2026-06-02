from datetime import date
from unittest.mock import MagicMock

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.secret_refs import MappingSecretResolver, SecretResolutionError


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._data


class FakeWooCommerceHTTPClient:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/orders"):
            return FakeResponse([
                {"id": 1, "status": "completed", "total": "1500.00", "currency": "ARS"},
                {"id": 2, "status": "refunded", "total": "999.00", "currency": "ARS"},
            ])
        if url.endswith("/products"):
            return FakeResponse([{"id": 10, "stock_quantity": 3}])
        raise AssertionError(f"Unexpected WooCommerce URL: {url}")


def make_woocommerce_business(params=None, secret_refs=None, enabled=True):
    return BusinessConfig(
        business_id="demo-woo",
        business_name="Demo Woo",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-woo-conn",
                connector_type="woocommerce",
                label="WooCommerce Demo",
                params={
                    "store_url": "https://demo.example.com",
                    "consumer_key": "ck_test_key",
                    "consumer_secret": "cs_test_secret",
                    "include_stock": True,
                }
                if params is None
                else params,
                secret_refs=secret_refs or {},
                enabled=enabled,
            )
        ],
    )


def test_woocommerce_pipeline_resolves_secret_refs_builds_and_dispatches_report():
    from app.brain.pipeline import run_woocommerce_daily_report_pipeline

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    http_client = FakeWooCommerceHTTPClient()
    resolved = {
        "secret://demo-woo/woocommerce/consumer-key": "ck_resolved_key",
        "secret://demo-woo/woocommerce/consumer-secret": "cs_resolved_secret",
    }

    result = run_woocommerce_daily_report_pipeline(
        business=make_woocommerce_business(
            params={"store_url": "https://demo.example.com", "include_stock": True},
            secret_refs={
                "consumer_key": "secret://demo-woo/woocommerce/consumer-key",
                "consumer_secret": "secret://demo-woo/woocommerce/consumer-secret",
            },
        ),
        report_date=date(2026, 6, 2),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=http_client,
        secret_resolver=MappingSecretResolver(resolved),
    )

    metrics = {metric.key: metric.value for metric in result.report.metrics}
    assert result.report.business_name == "Demo Woo"
    assert metrics["revenue_today"] == 1500.0
    assert metrics["orders_today"] == 1
    assert metrics["stock_units"] == 3
    assert result.dispatch.status == "sent"
    assert http_client.calls[0][1]["auth"] == ("ck_resolved_key", "cs_resolved_secret")
    delivery.send_text.assert_called_once()


def test_woocommerce_pipeline_missing_secrets_reports_redacted_required_keys():
    from app.brain.pipeline import run_woocommerce_daily_report_pipeline

    with pytest.raises(SecretResolutionError) as exc_info:
        run_woocommerce_daily_report_pipeline(
            business=make_woocommerce_business(params={"store_url": "https://demo.example.com"}),
            report_date=date(2026, 6, 2),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            http_client=FakeWooCommerceHTTPClient(),
        )

    message = str(exc_info.value)
    assert message == (
        "credential resolution failed for connector_type=woocommerce "
        "connector_id=demo-woo-conn secret_name=consumer_key reason=secret_ref_missing"
    )
    assert "ck_test_key" not in message
    assert "cs_test_secret" not in message


def test_woocommerce_runtime_compiler_keeps_public_params_and_secret_refs_only():
    from app.brain.runtime import compile_business_runtime

    runtime = compile_business_runtime(
        make_woocommerce_business(
            params={"store_url": "https://demo.example.com", "include_stock": True},
            secret_refs={
                "consumer_key": "secret://demo-woo/woocommerce/consumer-key",
                "consumer_secret": "secret://demo-woo/woocommerce/consumer-secret",
            },
        )
    )

    connector = runtime.connectors[0]
    assert connector.connector_type == "woocommerce"
    assert connector.params == {"store_url": "https://demo.example.com", "include_stock": True}
    assert connector.secret_refs == {
        "consumer_key": "secret://demo-woo/woocommerce/consumer-key",
        "consumer_secret": "secret://demo-woo/woocommerce/consumer-secret",
    }
    assert connector.secret_param_names == ["consumer_key", "consumer_secret"]
    assert connector.required_scopes == ["orders.read", "products.read"]
