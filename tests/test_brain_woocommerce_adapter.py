from datetime import date

import pytest

from app.brain.adapters.woocommerce import (
    WooCommerceAuthError,
    build_daily_report_from_woocommerce,
)


class FakeResponse:
    def __init__(self, data, status_code=200, headers=None):
        self._data = data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeWooCommerceClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError(f"Unexpected WooCommerce URL: {url}")
        return self.responses.pop(0)


def test_woocommerce_adapter_builds_read_only_commerce_metrics_with_evidence():
    client = FakeWooCommerceClient(
        [
            FakeResponse(
                [
                    {"id": 1, "status": "processing", "total": "1200.50", "currency": "ARS"},
                    {"id": 2, "status": "completed", "total": "800.00", "currency": "ARS"},
                    {"id": 3, "status": "cancelled", "total": "9999.00", "currency": "ARS"},
                ]
            ),
            FakeResponse([
                {"id": 10, "stock_quantity": 4},
                {"id": 11, "stock_quantity": None},
                {"id": 12, "stock_quantity": 7},
            ]),
        ]
    )

    report = build_daily_report_from_woocommerce(
        business_name="Demo Woo",
        store_url="https://demo.example.com/",
        consumer_key="ck_test_key",
        consumer_secret="cs_test_secret",
        report_date=date(2026, 6, 2),
        http_client=client,
        include_stock=True,
        source_label="Woo demo",
    )

    metrics = {metric.key: metric for metric in report.metrics}
    assert report.business_name == "Demo Woo"
    assert metrics["revenue_today"].value == 2000.50
    assert metrics["orders_today"].value == 2
    assert metrics["stock_units"].value == 11
    assert all(metric.evidence[0].source == "woocommerce" for metric in report.metrics)

    order_url, order_kwargs = client.calls[0]
    product_url, product_kwargs = client.calls[1]
    assert order_url == "https://demo.example.com/wp-json/wc/v3/orders"
    assert product_url == "https://demo.example.com/wp-json/wc/v3/products"
    assert order_kwargs["auth"] == ("ck_test_key", "cs_test_secret")
    assert product_kwargs["auth"] == ("ck_test_key", "cs_test_secret")
    assert order_kwargs["params"] == {
        "after": "2026-06-02T00:00:00",
        "before": "2026-06-02T23:59:59",
        "per_page": "100",
        "status": "any",
        "page": "1",
    }


def test_woocommerce_adapter_emits_only_declared_metric_envelope():
    from app.brain.connector_registry import get_connector_spec

    client = FakeWooCommerceClient([FakeResponse([{"id": 1, "status": "completed", "total": "42", "currency": "ARS"}])])

    report = build_daily_report_from_woocommerce(
        business_name="Demo Woo",
        store_url="demo.example.com",
        consumer_key="ck_test_key",
        consumer_secret="cs_test_secret",
        report_date=date(2026, 6, 2),
        http_client=client,
        include_stock=False,
    )

    assert get_connector_spec("woocommerce").validate_emitted_metric_objects(report.metrics) == []


def test_woocommerce_auth_errors_are_typed_and_redacted():
    raw_key = "ck_super_secret_key"
    raw_secret = "cs_super_secret_secret"
    client = FakeWooCommerceClient([FakeResponse({"message": "invalid credentials"}, status_code=401)])

    with pytest.raises(WooCommerceAuthError) as exc_info:
        build_daily_report_from_woocommerce(
            business_name="Demo Woo",
            store_url="https://demo.example.com",
            consumer_key=raw_key,
            consumer_secret=raw_secret,
            report_date=date(2026, 6, 2),
            http_client=client,
        )

    message = str(exc_info.value)
    assert message == "WooCommerce auth failed: HTTP 401"
    assert raw_key not in message
    assert raw_secret not in message
