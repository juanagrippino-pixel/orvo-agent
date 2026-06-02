from datetime import date

import pytest

from app.brain.models import DailyReport, Evidence, Metric


def _assert_public_error_redacted(response, *raw_values):
    rendered = response.get_data(as_text=True)
    for raw_value in raw_values:
        assert raw_value not in rendered
    assert "[REDACTED]" in rendered


def test_csv_daily_report_endpoint_returns_report(monkeypatch, tmp_path):
    from server import app

    csv_path = tmp_path / "artemea.csv"
    csv_path.write_text("fecha,ventas\n2026-05-19,70000\n")
    source = Evidence(source="csv", label="CSV Artemea")

    def fake_build_daily_report_from_csv_file(**kwargs):
        assert kwargs["business_name"] == "Artemea"
        assert kwargs["report_date"] == date(2026, 5, 19)
        assert kwargs["csv_path"] == str(csv_path)
        return DailyReport(
            business_name="Artemea",
            report_date=kwargs["report_date"],
            metrics=[Metric(key="revenue_today", label="Ventas de hoy", value=70000, unit="ARS", evidence=[source])],
            insights=[],
        )

    monkeypatch.setattr("server.build_daily_report_from_csv_file", fake_build_daily_report_from_csv_file)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/csv",
        json={"business_name": "Artemea", "report_date": "2026-05-19", "csv_path": str(csv_path)},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "Orvo Brain" in body["text"]
    assert body["report"]["business_name"] == "Artemea"


def test_csv_daily_report_endpoint_rejects_missing_required_fields():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily/csv", json={"business_name": "Artemea"})

    assert response.status_code == 400
    assert "csv_path" in response.get_json()["error"]


@pytest.mark.parametrize(
    ("exception", "raw_values"),
    [
        (
            FileNotFoundError("CSV missing access_token=raw-public-token"),
            ("raw-public-token",),
        ),
        (
            ValueError("CSV invalid Authorization: Basic dXNlcjpzdXBlcl9zZWNyZXQ="),
            ("dXNlcjpzdXBlcl9zZWNyZXQ=",),
        ),
    ],
)
def test_csv_daily_report_endpoint_redacts_secret_shaped_errors(monkeypatch, exception, raw_values):
    from server import app

    def raise_secret_error(**kwargs):
        raise exception

    monkeypatch.setattr("server.build_daily_report_from_csv_file", raise_secret_error)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/csv",
        json={"business_name": "Artemea", "csv_path": "/tmp/orders.csv"},
    )

    assert response.status_code == 400
    assert "[REDACTED]" in response.get_json()["error"]
    _assert_public_error_redacted(response, *raw_values)
