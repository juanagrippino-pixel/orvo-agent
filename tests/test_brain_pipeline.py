from datetime import date
from unittest.mock import MagicMock

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.models import InsightThresholds


def make_business():
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="sheets-main",
                connector_type="google_sheets",
                label="Sheet Artemea",
                params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:F1000"},
            )
        ],
    )


def test_run_google_sheets_daily_report_pipeline_builds_and_dispatches(monkeypatch):
    from app.brain.pipeline import run_google_sheets_daily_report_pipeline

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

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)

    result = run_google_sheets_daily_report_pipeline(
        business=make_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service=FakeService(),
    )

    assert result.dispatch.status == "sent"
    assert result.report.business_name == "Artemea"
    assert len(result.report.insights) == 3
    delivery_client.send_text.assert_called_once()


def test_google_sheets_pipeline_uses_business_insight_thresholds():
    from app.brain.pipeline import run_google_sheets_daily_report_pipeline

    class FakeExecute:
        def execute(self):
            return {
                "values": [
                    ["fecha", "ventas"],
                    ["2026-05-19", "90000"],
                    ["2026-05-18", "100000"],
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

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)
    business = make_business().model_copy(
        update={"insight_thresholds": InsightThresholds(revenue_drop_threshold=0.05)}
    )

    result = run_google_sheets_daily_report_pipeline(
        business=business,
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service=FakeService(),
    )

    assert len(result.report.insights) == 1
    assert "ventas" in result.report.insights[0].title.lower()


def test_pipeline_fails_if_google_sheets_connector_missing():
    import pytest
    from app.brain.pipeline import run_google_sheets_daily_report_pipeline

    business = make_business().model_copy(update={"connectors": []})

    with pytest.raises(ValueError, match="google_sheets connector"):
        run_google_sheets_daily_report_pipeline(
            business=business,
            report_date=date(2026, 5, 19),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            sheets_service=MagicMock(),
        )


def test_pipeline_fails_if_connector_missing_sheet_params():
    import pytest
    from app.brain.pipeline import run_google_sheets_daily_report_pipeline

    business = make_business().model_copy(
        update={
            "connectors": [
                ConnectorConfig(
                    connector_id="bad",
                    connector_type="google_sheets",
                    label="Bad Sheet",
                    params={},
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="spreadsheet_id and range_name"):
        run_google_sheets_daily_report_pipeline(
            business=business,
            report_date=date(2026, 5, 19),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            sheets_service=MagicMock(),
        )


def test_registry_driven_builder_uses_executor_factory_metadata(monkeypatch):
    from app.brain.models import DailyReport, Evidence, Metric
    from app.brain.pipeline import _build_daily_report_for_connector_type

    captured = {}

    def fake_csv_report_factory(**kwargs):
        captured.update(kwargs)
        return DailyReport(
            business_name=kwargs["business_name"],
            report_date=kwargs["report_date"],
            metrics=[
                Metric(
                    key="orders_today",
                    label="Pedidos",
                    value=1,
                    unit="orders",
                    evidence=[Evidence(source="csv", label="Daily CSV")],
                )
            ],
            insights=[],
        )

    monkeypatch.setattr(
        "app.brain.adapters.csv_file.build_daily_report_from_csv_file",
        fake_csv_report_factory,
    )
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="csv-main",
                connector_type="csv",
                label="CSV Artemea",
                params={"csv_path": "/tmp/orders.csv", "source_label": "Daily CSV"},
            )
        ],
    )

    report = _build_daily_report_for_connector_type(
        connector_type="csv",
        business=business,
        report_date=date(2026, 5, 19),
    )

    assert report.business_name == "Artemea"
    assert captured == {
        "business_name": "Artemea",
        "report_date": date(2026, 5, 19),
        "csv_path": "/tmp/orders.csv",
        "source_label": "Daily CSV",
        "insight_thresholds": business.insight_thresholds,
    }


def test_registry_driven_builder_rejects_non_daily_report_connector():
    import pytest
    from app.brain.pipeline import _build_daily_report_for_connector_type

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="sample-main",
                connector_type="sample",
                label="Sample payload",
                params={},
            )
        ],
    )

    with pytest.raises(ValueError, match="Unsupported connector type for daily report: sample"):
        _build_daily_report_for_connector_type(
            connector_type="sample",
            business=business,
            report_date=date(2026, 5, 19),
        )


def test_run_connector_daily_report_pipeline_dispatches_registry_built_report(monkeypatch):
    from app.brain.models import DailyReport, Evidence, Metric
    from app.brain.pipeline import run_connector_daily_report_pipeline

    captured = {}

    def fake_csv_report_factory(**kwargs):
        captured.update(kwargs)
        return DailyReport(
            business_name=kwargs["business_name"],
            report_date=kwargs["report_date"],
            metrics=[
                Metric(
                    key="orders_today",
                    label="Pedidos",
                    value=2,
                    unit="orders",
                    evidence=[Evidence(source="csv", label="Daily CSV")],
                )
            ],
            insights=[],
        )

    monkeypatch.setattr(
        "app.brain.adapters.csv_file.build_daily_report_from_csv_file",
        fake_csv_report_factory,
    )
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="csv-main",
                connector_type="csv",
                label="CSV Artemea",
                params={"csv_path": "/tmp/orders.csv", "source_label": "Daily CSV"},
            )
        ],
    )
    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)

    result = run_connector_daily_report_pipeline(
        connector_type="csv",
        business=business,
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
    )

    assert result.dispatch.status == "sent"
    assert result.report.metrics[0].key == "orders_today"
    assert captured["csv_path"] == "/tmp/orders.csv"
    delivery_client.send_text.assert_called_once()


def test_connector_specific_pipeline_wrappers_reload_registry_factory_metadata(monkeypatch):
    import app.brain.pipeline as pipeline
    from app.brain.models import DailyReport, Evidence, Metric

    captured = {}

    def fake_tiendanube_report_factory(**kwargs):
        captured.update(kwargs)
        return DailyReport(
            business_name=kwargs["business_name"],
            report_date=kwargs["report_date"],
            metrics=[
                Metric(
                    key="orders_today",
                    label="Pedidos",
                    value=1,
                    unit="orders",
                    evidence=[Evidence(source="tiendanube", label="TN Artemea")],
                )
            ],
            insights=[],
        )

    monkeypatch.setattr(
        "app.brain.adapters.tiendanube.build_daily_report_from_tiendanube",
        fake_tiendanube_report_factory,
    )
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="TN Artemea",
                params={"store_id": "123", "access_token": "tn_test_token", "include_stock": True},
            )
        ],
    )
    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.2", error=None)

    result = pipeline.run_tiendanube_daily_report_pipeline(
        business=business,
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=object(),
    )

    assert result.dispatch.status == "sent"
    assert captured["store_id"] == "123"
    assert captured["access_token"] == "tn_test_token"
    assert captured["include_stock"] is True
