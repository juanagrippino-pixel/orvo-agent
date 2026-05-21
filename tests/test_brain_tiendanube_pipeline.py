from datetime import date
from unittest.mock import MagicMock

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore


def make_tiendanube_business(params=None, enabled=True):
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="Tiendanube Artemea",
                params=params or {"store_id": "12345", "access_token": "tn_token", "include_stock": True},
                enabled=enabled,
            )
        ],
    )


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._data


class FakeTiendanubeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/orders"):
            return FakeResponse([
                {"id": 1, "status": "paid", "total": "70000"},
                {"id": 2, "status": "cancelled", "total": "99999"},
            ])
        if url.endswith("/products"):
            return FakeResponse([{"id": 10, "variants": [{"stock": 2}, {"stock": 4}]}])
        raise AssertionError(f"Unexpected Tiendanube URL: {url}")


def test_run_tiendanube_daily_report_pipeline_builds_and_dispatches():
    from app.brain.pipeline import run_tiendanube_daily_report_pipeline

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.tn", error=None)
    http_client = FakeTiendanubeClient()

    result = run_tiendanube_daily_report_pipeline(
        business=make_tiendanube_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=http_client,
    )

    assert result.dispatch.status == "sent"
    assert result.report.business_name == "Artemea"
    assert any(metric.key == "revenue_today" and metric.value == 70000 for metric in result.report.metrics)
    assert any(metric.key == "stock_units" and metric.value == 6 for metric in result.report.metrics)
    delivery_client.send_text.assert_called_once()


def test_tiendanube_pipeline_fails_if_connector_missing():
    from app.brain.pipeline import run_tiendanube_daily_report_pipeline

    business = make_tiendanube_business().model_copy(update={"connectors": []})

    with pytest.raises(ValueError, match="tiendanube connector"):
        run_tiendanube_daily_report_pipeline(
            business=business,
            report_date=date(2026, 5, 19),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            http_client=FakeTiendanubeClient(),
        )


def test_tiendanube_pipeline_fails_if_connector_missing_required_params():
    from app.brain.pipeline import run_tiendanube_daily_report_pipeline

    business = BusinessConfig.model_construct(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig.model_construct(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="Tiendanube Artemea",
                params={"store_id": "12345"},
                enabled=True,
            )
        ],
    )

    with pytest.raises(ValueError, match="store_id and access_token"):
        run_tiendanube_daily_report_pipeline(
            business=business,
            report_date=date(2026, 5, 19),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            http_client=FakeTiendanubeClient(),
        )
