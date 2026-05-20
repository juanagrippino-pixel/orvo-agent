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
