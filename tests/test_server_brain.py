from app.brain.models import DailyReport, Evidence, Metric


def test_daily_brain_report_endpoint_returns_text_metrics_and_insights():
    from server import app

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily",
        json={
            "business_name": "Artemea",
            "report_date": "2026-05-19",
            "source_label": "Sheet Artemea mayo",
            "metrics": {
                "revenue_today": 70000,
                "revenue_baseline": 100000,
                "stock_units": 3,
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "Orvo Brain" in body["text"]
    assert body["report"]["business_name"] == "Artemea"
    assert len(body["report"]["metrics"]) == 3
    assert len(body["report"]["insights"]) == 2


def test_daily_brain_report_endpoint_rejects_report_not_allowed_metrics():
    from server import app

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily",
        json={
            "business_name": "Artemea",
            "report_date": "2026-05-19",
            "metrics": {
                "runtime.connector.status": True,
            },
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"]
    assert "report_not_allowed" in payload["error"]
    assert "runtime.connector.status" in payload["error"]


def test_google_sheets_daily_report_endpoint_rejects_report_not_allowed_metrics(monkeypatch):
    from server import app

    source = Evidence(source="google_sheets", label="Sheet Artemea")

    def fake_build_daily_report_from_sheet(**kwargs):
        return DailyReport(
            business_name=kwargs["business_name"],
            report_date=kwargs["report_date"],
            metrics=[
                Metric(
                    key="runtime.connector.status",
                    label="Estado del conector",
                    value=True,
                    evidence=[source],
                )
            ],
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

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"]
    assert "report_not_allowed" in payload["error"]
    assert "runtime.connector.status" in payload["error"]


def test_daily_brain_report_endpoint_rejects_empty_payload():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily", json={})

    assert response.status_code == 400
    assert "error" in response.get_json()
