from datetime import date
from unittest.mock import MagicMock

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
import scripts.run_orvo_brain_reports as reports_script


class FakeTiendanubeHTTPClient:
    def get(self, url, headers=None, params=None):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        if url.endswith("/orders"):
            response.json.return_value = [
                {"id": 1, "status": "paid", "total": "1000.00"},
                {"id": 2, "status": "cancelled", "total": "999.00"},
            ]
        elif url.endswith("/products"):
            response.json.return_value = []
        else:
            response.json.return_value = []
        return response


def make_tiendanube_business():
    return BusinessConfig(
        business_id="demo-shop",
        business_name="Demo Shop",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-tiendanube",
                connector_type="tiendanube",
                label="Tiendanube Demo",
                params={"store_id": "123", "access_token": "tn_test_token", "include_stock": False},
            )
        ],
    )


def test_force_report_uses_tiendanube_pipeline_without_loading_sheets():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    sheets_service_factory = MagicMock(side_effect=AssertionError("google sheets should not be loaded for tiendanube"))

    result = reports_script.run_forced_report(
        business=make_tiendanube_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service_factory=sheets_service_factory,
        tiendanube_http_client=FakeTiendanubeHTTPClient(),
    )

    assert result.report.business_name == "Demo Shop"
    assert {metric.key: metric.value for metric in result.report.metrics}["revenue_today"] == 1000.0
    assert result.dispatch.status == "sent"
    sheets_service_factory.assert_not_called()


def test_force_report_rejects_unsupported_connector_type():
    business = BusinessConfig(
        business_id="unknown",
        business_name="Unknown",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="unknown-conn",
                connector_type="shopify",
                label="Shopify",
                params={},
            )
        ],
    )

    with pytest.raises(ValueError, match="no supported enabled connector"):
        reports_script.run_forced_report(
            business=business,
            report_date=date(2026, 5, 19),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            sheets_service_factory=MagicMock(),
        )


def make_csv_business(csv_path: str, *, label: str = "CSV Demo") -> BusinessConfig:
    return BusinessConfig(
        business_id="demo-csv",
        business_name="Demo CSV",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-csv-conn",
                connector_type="csv",
                label=label,
                params={"csv_path": csv_path},
            )
        ],
    )


def test_force_report_uses_csv_pipeline_without_loading_sheets():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    sheets_service_factory = MagicMock(side_effect=AssertionError("google sheets should not be loaded for csv"))

    result = reports_script.run_forced_report(
        business=make_csv_business("examples/artemea_daily.csv"),
        report_date=date(2026, 5, 19),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service_factory=sheets_service_factory,
        tiendanube_http_client=MagicMock(side_effect=AssertionError("tiendanube must not be called for csv")),
    )

    metrics = {metric.key: metric.value for metric in result.report.metrics}
    assert result.report.business_name == "Demo CSV"
    assert metrics["revenue_today"] == 260000.0
    assert result.dispatch.status == "sent"
    sheets_service_factory.assert_not_called()
    delivery.send_text.assert_called_once()
    assert any(
        ev.source == "csv" and "CSV Demo" in ev.label
        for metric in result.report.metrics
        for ev in metric.evidence
    )


def test_force_report_csv_requires_csv_path():
    business = BusinessConfig(
        business_id="bad-csv",
        business_name="Bad CSV",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="bad-csv-conn",
                connector_type="csv",
                label="Bad CSV",
                params={},
            )
        ],
    )

    with pytest.raises(ValueError, match="csv_path"):
        reports_script.run_forced_report(
            business=business,
            report_date=date(2026, 5, 19),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            sheets_service_factory=MagicMock(),
        )
