from datetime import date

from app.brain.models import DailyReport, Evidence, Metric


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
    assert "Prioridad:" in body["text"]
    assert body["report"]["business_name"] == "Artemea"


def test_google_sheets_daily_report_endpoint_rejects_missing_required_fields():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily/google-sheets", json={"business_name": "Artemea"})

    assert response.status_code == 400
    assert "spreadsheet_id" in response.get_json()["error"]
