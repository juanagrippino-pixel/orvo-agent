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


class FakeMercadoLibreHTTPClient:
    def get(self, url, headers=None, params=None):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {
            "results": [
                {"id": 1, "status": "paid", "total_amount": 5000.0},
                {"id": 2, "status": "cancelled", "total_amount": 999.0},
            ],
            "paging": {"total": 2, "offset": 0, "limit": 50},
        }
        return response


class FakeMetaAdsHTTPClient:
    def get(self, url, params=None):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"spend": "725.25", "impressions": "9000", "clicks": "210", "purchase_roas": []}
            ]
        }
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


def make_mercadolibre_business():
    return BusinessConfig(
        business_id="demo-ml",
        business_name="Demo ML",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-mercadolibre",
                connector_type="mercadolibre",
                label="MercadoLibre Demo",
                params={"seller_id": "123", "access_token": "ml_test_token", "site_id": "MLA"},
            )
        ],
    )


def test_force_report_uses_mercadolibre_pipeline_without_loading_sheets_or_tiendanube():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    sheets_service_factory = MagicMock(side_effect=AssertionError("google sheets should not be loaded for mercadolibre"))

    result = reports_script.run_forced_report(
        business=make_mercadolibre_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service_factory=sheets_service_factory,
        tiendanube_http_client=MagicMock(side_effect=AssertionError("tiendanube must not be called for mercadolibre")),
        mercadolibre_http_client=FakeMercadoLibreHTTPClient(),
    )

    assert result.report.business_name == "Demo ML"
    assert {metric.key: metric.value for metric in result.report.metrics}["revenue_today"] == 5000.0
    assert result.dispatch.status == "sent"
    sheets_service_factory.assert_not_called()


def make_meta_ads_business():
    return BusinessConfig(
        business_id="demo-meta",
        business_name="Demo Meta",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-meta",
                connector_type="meta_ads",
                label="Meta Ads Demo",
                params={"ad_account_id": "act_123", "access_token": "meta_test_token"},
            )
        ],
    )


def test_force_report_uses_meta_ads_pipeline_without_loading_other_clients():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    sheets_service_factory = MagicMock(side_effect=AssertionError("google sheets should not be loaded for meta_ads"))

    result = reports_script.run_forced_report(
        business=make_meta_ads_business(),
        report_date=date(2026, 5, 17),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service_factory=sheets_service_factory,
        tiendanube_http_client=MagicMock(side_effect=AssertionError("tiendanube must not be called for meta_ads")),
        mercadolibre_http_client=MagicMock(side_effect=AssertionError("mercadolibre must not be called for meta_ads")),
        meta_ads_http_client=FakeMetaAdsHTTPClient(),
    )

    metrics = {metric.key: metric.value for metric in result.report.metrics}
    assert result.report.business_name == "Demo Meta"
    assert metrics["ad_spend_today"] == pytest.approx(725.25)
    assert result.dispatch.status == "sent"
    sheets_service_factory.assert_not_called()


def make_artemea_tiendanube_meta_business():
    return BusinessConfig(
        business_id="artemea",
        business_name="ARTEMEA",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="artemea-tn",
                connector_type="tiendanube",
                label="Tiendanube ARTEMEA",
                params={"store_id": "123", "access_token": "tn_test_token", "include_stock": False},
            ),
            ConnectorConfig(
                connector_id="artemea-meta",
                connector_type="meta_ads",
                label="Meta Ads ARTEMEA",
                params={"ad_account_id": "act_123", "access_token": "meta_test_token"},
            ),
        ],
    )


def test_force_report_merges_tiendanube_and_meta_ads_like_scheduled_runtime():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    sheets_service_factory = MagicMock(side_effect=AssertionError("google sheets should not be loaded for ARTEMEA TN+Meta dry run"))

    result = reports_script.run_forced_report(
        business=make_artemea_tiendanube_meta_business(),
        report_date=date(2026, 5, 24),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service_factory=sheets_service_factory,
        tiendanube_http_client=FakeTiendanubeHTTPClient(),
        meta_ads_http_client=FakeMetaAdsHTTPClient(),
    )

    metrics = {metric.key: metric.value for metric in result.report.metrics}
    assert result.report.business_name == "ARTEMEA"
    assert metrics["revenue_today"] == 1000.0
    assert metrics["ad_spend_today"] == pytest.approx(725.25)
    assert result.dispatch.status == "sent"
    delivery.send_text.assert_called_once()
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
