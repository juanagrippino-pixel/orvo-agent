from datetime import datetime, timezone
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


def make_csv_store(tmp_path):
    csv_path = tmp_path / "daily.csv"
    csv_path.write_text(
        "fecha,ventas,ordenes,stock,conversaciones_sin_responder\n"
        "2026-05-19,70000,12,3,8\n"
        "2026-05-18,100000,10,10,1\n",
        encoding="utf-8",
    )
    store = InMemoryConfigStore()
    store.save_business_config(
        BusinessConfig(
            business_id="csv-biz",
            business_name="CSV Biz",
            owner_phone="+5491149724933",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="csv-main",
                    connector_type="csv",
                    label="CSV Daily",
                    params={"csv_path": str(csv_path), "source_label": "CSV Biz"},
                )
            ],
        )
    )
    store.save_schedule(
        ReportSchedule(
            schedule_id="csv-biz-daily-report",
            business_id="csv-biz",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
    )
    return store


def test_run_due_daily_reports_dispatches_due_csv_report(tmp_path):
    from app.brain.runner import run_due_daily_reports

    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="wamid.csv", error=None)

    results = run_due_daily_reports(
        config_store=make_csv_store(tmp_path),
        idempotency_store=InMemoryIdempotencyStore(),
        delivery_client=delivery,
        now=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].business_id == "csv-biz"
    assert results[0].dispatch.status == "sent"
    assert any(metric.key == "revenue_today" and metric.value == 70000 for metric in results[0].pipeline.report.metrics)
    delivery.send_text.assert_called_once()
