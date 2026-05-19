from datetime import date

from app.brain.adapters.mercadolibre import MercadoLibreAPIError, MercadoLibreAuthError
from app.brain.models import DailyReport, Evidence, Metric


def test_mercadolibre_daily_report_endpoint_returns_text_and_report(monkeypatch):
    from server import app

    client = app.test_client()
    captured = {}

    def fake_build_daily_report_from_mercadolibre(**kwargs):
        captured.update(kwargs)
        return DailyReport(
            business_name=kwargs["business_name"],
            report_date=kwargs["report_date"],
            metrics=[
                Metric(
                    key="revenue_today",
                    label="Ventas del día",
                    value=12500.0,
                    unit="ARS",
                    evidence=[Evidence(source="mercadolibre", label="ML")],
                )
            ],
        )

    monkeypatch.setattr(
        "server.build_daily_report_from_mercadolibre",
        fake_build_daily_report_from_mercadolibre,
    )

    response = client.post(
        "/brain/reports/daily/mercadolibre",
        json={
            "business_name": "Demo ML",
            "seller_id": "12345",
            "access_token": "ml_test_token",
            "report_date": "2026-05-19",
            "site_id": "MLA",
            "source_label": "MercadoLibre Demo",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["report"]["business_name"] == "Demo ML"
    assert payload["report"]["report_date"] == "2026-05-19"
    assert "Demo ML" in payload["text"]
    assert captured["business_name"] == "Demo ML"
    assert captured["report_date"] == date(2026, 5, 19)
    assert captured["seller_id"] == "12345"
    assert captured["access_token"] == "ml_test_token"
    assert captured["site_id"] == "MLA"
    assert captured["source_label"] == "MercadoLibre Demo"


def test_mercadolibre_daily_report_endpoint_requires_fields():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily/mercadolibre", json={"business_name": "Demo"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "missing_fields"
    assert payload["missing"] == ["seller_id", "access_token"]


def test_mercadolibre_daily_report_endpoint_rejects_bad_date():
    from server import app

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/mercadolibre",
        json={"business_name": "Demo", "seller_id": "123", "access_token": "tok", "report_date": "bad-date"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_report_date"


def test_mercadolibre_daily_report_endpoint_maps_auth_errors(monkeypatch):
    from server import app

    client = app.test_client()
    def raise_auth(**kwargs):
        raise MercadoLibreAuthError("bad token")

    monkeypatch.setattr("server.build_daily_report_from_mercadolibre", raise_auth)

    response = client.post(
        "/brain/reports/daily/mercadolibre",
        json={"business_name": "Demo", "seller_id": "123", "access_token": "bad"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "mercadolibre_auth_error"


def test_mercadolibre_daily_report_endpoint_maps_api_errors(monkeypatch):
    from server import app

    client = app.test_client()
    def raise_api(**kwargs):
        raise MercadoLibreAPIError("down")

    monkeypatch.setattr("server.build_daily_report_from_mercadolibre", raise_api)

    response = client.post(
        "/brain/reports/daily/mercadolibre",
        json={"business_name": "Demo", "seller_id": "123", "access_token": "tok"},
    )

    assert response.status_code == 502
    assert response.get_json()["error"] == "mercadolibre_api_error"
