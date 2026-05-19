from datetime import date
from unittest.mock import MagicMock

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.pipeline import run_mercadolibre_daily_report_pipeline


class FakeMercadoLibreHTTPClient:
    def get(self, url, headers=None, params=None):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {
            "results": [
                {"id": 1, "status": "paid", "total_amount": 1500.0},
                {"id": 2, "status": "cancelled", "total_amount": 999.0},
            ],
            "paging": {"total": 2, "offset": 0, "limit": 50},
        }
        return response


def make_mercadolibre_business(params=None):
    return BusinessConfig(
        business_id="demo-ml",
        business_name="Demo ML",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-ml-conn",
                connector_type="mercadolibre",
                label="MercadoLibre Demo",
                params={"seller_id": "123", "access_token": "ml_test_token", "site_id": "MLA"} if params is None else params,
            )
        ],
    )


def test_mercadolibre_pipeline_builds_and_dispatches_report():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)

    result = run_mercadolibre_daily_report_pipeline(
        business=make_mercadolibre_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=FakeMercadoLibreHTTPClient(),
    )

    metrics = {metric.key: metric.value for metric in result.report.metrics}
    assert result.report.business_name == "Demo ML"
    assert metrics["revenue_today"] == 1500.0
    assert metrics["orders_today"] == 1
    assert result.dispatch.status == "sent"
    delivery.send_text.assert_called_once()


def test_mercadolibre_pipeline_requires_seller_id_and_access_token():
    delivery = MagicMock()

    import pytest

    with pytest.raises(ValueError, match="seller_id and access_token"):
        run_mercadolibre_daily_report_pipeline(
            business=make_mercadolibre_business(params={}),
            report_date=date(2026, 5, 19),
            delivery_client=delivery,
            idempotency_store=InMemoryIdempotencyStore(),
            http_client=FakeMercadoLibreHTTPClient(),
        )
