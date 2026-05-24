import logging
from datetime import datetime, timezone
import json
from unittest.mock import MagicMock

from app.brain.config import BusinessConfig, ConnectorConfig, InMemoryConfigStore, ReportSchedule
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore


def make_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="sheet",
                    connector_type="google_sheets",
                    label="Sheet Artemea",
                    params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-daily-report",
            business_id="artemea",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def fake_sheets_service():
    class FakeExecute:
        def execute(self):
            return {
                "values": [
                    ["fecha", "ventas", "ordenes", "stock", "conversaciones_sin_responder"],
                    ["2026-05-19", "70000", "12", "3", "8"],
                    ["2026-05-18", "100000", "10", "10", "1"],
                ]
            }

    class FakeValues:
        def get(self, spreadsheetId, range):
            return FakeExecute()

    class FakeSpreadsheets:
        def values(self):
            return FakeValues()

    class FakeService:
        def spreadsheets(self):
            return FakeSpreadsheets()

    return FakeService()


def test_run_due_daily_reports_dispatches_due_google_sheet_report():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),  # 09:00 Buenos Aires
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea"
    assert results[0].dispatch.status == "sent"
    assert results[0].runtime_metadata["run_mode"] == "scheduled"
    assert results[0].runtime_metadata == results[0].pipeline.runtime_metadata
    assert results[0].runtime_metadata["config_digest"].startswith("sha256:")
    delivery.send_text.assert_called_once()


def test_run_due_daily_reports_skips_when_not_due():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()

    results = run_due_daily_reports(
        config_store=make_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),  # 10:00 Buenos Aires
    )

    assert results == []
    delivery.send_text.assert_not_called()


def make_tiendanube_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn",
                    connector_type="tiendanube",
                    label="Tiendanube Artemea",
                    params={"store_id": "12345", "access_token": "tn_token", "include_stock": False},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-tiendanube-daily-report",
            business_id="artemea",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


class FakeTiendanubeResponse:
    status_code = 200
    headers = {}

    def json(self):
        return [{"id": 1, "status": "paid", "total": "42000"}]


class FakeTiendanubeClient:
    def get(self, url, **kwargs):
        return FakeTiendanubeResponse()


def test_run_due_daily_reports_dispatches_due_tiendanube_report():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.tn", error=None)

    results = run_due_daily_reports(
        config_store=make_tiendanube_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        tiendanube_http_client=FakeTiendanubeClient(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "revenue_today" and metric.value == 42000 for metric in results[0].pipeline.report.metrics)
    delivery.send_text.assert_called_once()


def make_mercadolibre_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-ml",
            business_name="Artemea ML",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="ml",
                    connector_type="mercadolibre",
                    label="MercadoLibre Artemea",
                    params={"seller_id": "12345", "access_token": "ml_token", "site_id": "MLA"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-mercadolibre-daily-report",
            business_id="artemea-ml",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


class FakeMercadoLibreClient:
    def get(self, url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {
            "results": [{"id": 1, "status": "paid", "total_amount": 99000.0}],
            "paging": {"total": 1, "offset": 0, "limit": 50},
        }
        return response


def test_run_due_daily_reports_dispatches_due_mercadolibre_report():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.ml", error=None)

    results = run_due_daily_reports(
        config_store=make_mercadolibre_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        mercadolibre_http_client=FakeMercadoLibreClient(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea-ml"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "revenue_today" and metric.value == 99000 for metric in results[0].pipeline.report.metrics)
    delivery.send_text.assert_called_once()


def make_tiendanube_mercadolibre_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-multi",
            business_name="Artemea Multi",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn",
                    connector_type="tiendanube",
                    label="Tiendanube Artemea",
                    params={"store_id": "12345", "access_token": "tn_token", "include_stock": False},
                ),
                ConnectorConfig(
                    connector_id="ml",
                    connector_type="mercadolibre",
                    label="MercadoLibre Artemea",
                    params={"seller_id": "12345", "access_token": "ml_token", "site_id": "MLA"},
                ),
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-multi-daily-report",
            business_id="artemea-multi",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def test_run_due_daily_reports_merges_tiendanube_and_mercadolibre_metrics_once():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.multi", error=None)

    results = run_due_daily_reports(
        config_store=make_tiendanube_mercadolibre_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        tiendanube_http_client=FakeTiendanubeClient(),
        mercadolibre_http_client=FakeMercadoLibreClient(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea-multi"
    assert results[0].dispatch.status == "sent"

    metrics_by_key = {metric.key: metric for metric in results[0].pipeline.report.metrics}
    assert len(metrics_by_key) == len(results[0].pipeline.report.metrics)
    assert metrics_by_key["revenue_today"].value == 141000
    assert metrics_by_key["orders_today"].value == 2
    assert metrics_by_key["avg_order_value"].value == 99000
    assert {item.source for item in metrics_by_key["revenue_today"].evidence} == {"tiendanube", "mercadolibre"}
    delivery.send_text.assert_called_once()


def make_meta_ads_store():
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-meta",
            business_name="Artemea Meta",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="meta",
                    connector_type="meta_ads",
                    label="Meta Ads Artemea",
                    params={"ad_account_id": "act_12345", "access_token": "meta_test_token"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-meta-ads-daily-report",
            business_id="artemea-meta",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


class FakeMetaAdsClient:
    def __init__(self):
        self.params = None

    def get(self, url, params=None):
        self.params = params
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": [{"spend": "12000", "impressions": "5000", "clicks": "120", "purchase_roas": []}]
        }
        return response


def test_run_due_daily_reports_dispatches_due_meta_ads_report_with_scheduled_date():
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.meta", error=None)
    http_client = FakeMetaAdsClient()

    results = run_due_daily_reports(
        config_store=make_meta_ads_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        meta_ads_http_client=http_client,
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "artemea-meta"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "ad_spend_today" and metric.value == 12000 for metric in results[0].pipeline.report.metrics)
    assert http_client.params is not None
    assert json.loads(http_client.params["time_range"]) == {"since": "2026-05-19", "until": "2026-05-19"}
    delivery.send_text.assert_called_once()


def make_artemea_08h00_store():
    """ARTEMEA production store: 08:00 Buenos Aires schedule = 11:00 UTC."""
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="sheet",
                    connector_type="google_sheets",
                    label="Sheet Artemea",
                    params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-daily-report",
            business_id="artemea",
            cron_expression="0 8 * * *",
            report_type="daily",
        )
    )
    return store


def test_artemea_08h00_schedule_dispatches_at_11h00_utc():
    """08:00 Buenos Aires = 11:00 UTC: runner must fire at exactly that tick."""
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.art", error=None)

    # 11:00 UTC == 08:00 Buenos Aires: should fire
    results = run_due_daily_reports(
        config_store=make_artemea_08h00_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc),
    )
    assert len(results) == 1
    assert results[0].schedule_id == "artemea-daily-report"
    assert results[0].dispatch.status == "sent"
    delivery.send_text.assert_called_once()


def test_artemea_08h00_schedule_does_not_dispatch_at_12h00_utc():
    """12:00 UTC == 09:00 Buenos Aires: must NOT fire for 08:00 schedule."""
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()

    results = run_due_daily_reports(
        config_store=make_artemea_08h00_store(),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        sheets_service=fake_sheets_service(),
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )
    assert results == []
    delivery.send_text.assert_not_called()


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


def make_no_connector_store():
    """Business with a due schedule but no enabled connectors."""
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="artemea-empty",
            business_name="Artemea Empty",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="artemea-empty-daily-report",
            business_id="artemea-empty",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def test_run_due_daily_reports_logs_no_connectors_skip(caplog):
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()

    with caplog.at_level(logging.INFO, logger="app.brain.runner"):
        results = run_due_daily_reports(
            config_store=make_no_connector_store(),
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=delivery,
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        )

    assert results == []
    messages = [r.getMessage() for r in caplog.records]
    assert any("no_connectors" in m and "artemea-empty" in m for m in messages)


def test_run_due_daily_reports_logs_pipeline_start(caplog):
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.log", error=None)

    with caplog.at_level(logging.INFO, logger="app.brain.runner"):
        run_due_daily_reports(
            config_store=make_store(),
            idempotency_store=InMemoryIdempotencyStore(),
            delivery_client=delivery,
            sheets_service=fake_sheets_service(),
            now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        )

    messages = [r.getMessage() for r in caplog.records]
    assert any("starting" in m and "artemea" in m for m in messages)
