from datetime import date

import pytest

from app.brain.models import DailyReport, Evidence, Metric


def _assert_public_error_redacted(response, *raw_values):
    rendered = response.get_data(as_text=True)
    for raw_value in raw_values:
        assert raw_value not in rendered
    assert "[REDACTED]" in rendered


def test_google_sheets_daily_report_endpoint_returns_report(monkeypatch):
    from server import app

    source = Evidence(source="google_sheets", label="Sheet Artemea")

    def fake_build_daily_report_from_sheet(**kwargs):
        assert kwargs["business_name"] == "Artemea"
        assert kwargs["report_date"] == date(2026, 5, 19)
        assert kwargs["spreadsheet_id"] == "abc123"
        return DailyReport(
            business_name="Artemea",
            report_date=kwargs["report_date"],
            metrics=[Metric(key="revenue_today", label="Ventas de hoy", value=70000, unit="ARS", evidence=[source])],
            insights=[],
        )

    monkeypatch.setattr("server.build_daily_report_from_sheet", fake_build_daily_report_from_sheet)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/google-sheets",
        json={
            "business_name": "Artemea",
            "report_date": "2026-05-19",
            "spreadsheet_id": "abc123",
            "range_name": "Daily!A1:F1000",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "Orvo Brain" in body["text"]
    assert body["report"]["business_name"] == "Artemea"


def test_google_sheets_daily_report_endpoint_rejects_missing_required_fields():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily/google-sheets", json={"business_name": "Artemea"})

    assert response.status_code == 400
    assert "spreadsheet_id" in response.get_json()["error"]


@pytest.mark.parametrize(
    ("exception_message", "raw_values"),
    [
        (
            "Sheets auth callback failed refresh_token=raw-refresh-token",
            ("raw-refresh-token",),
        ),
        (
            "Sheets OAuth callback failed Bearer raw-public-bearer-token "
            "https://oauth.example.test/callback?access_token=raw-query-token&state=safe-state "
            "code=raw_oauth_code",
            ("raw-public-bearer-token", "raw-query-token", "raw_oauth_code"),
        ),
    ],
)
def test_google_sheets_daily_report_endpoint_redacts_secret_shaped_value_errors(
    monkeypatch,
    exception_message,
    raw_values,
):
    from server import app

    def raise_secret_error(**kwargs):
        raise ValueError(exception_message)

    monkeypatch.setattr("server.build_daily_report_from_sheet", raise_secret_error)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/google-sheets",
        json={"business_name": "Artemea", "spreadsheet_id": "abc123", "range_name": "Daily!A1:F1000"},
    )

    assert response.status_code == 400
    assert "[REDACTED]" in response.get_json()["error"]
    _assert_public_error_redacted(response, *raw_values)
