from datetime import date

from app.brain.models import DailyReport, Evidence, Metric
from app.brain.adapters.tiendanube import TiendanubeAuthError, TiendanubeConnectionError


def test_tiendanube_daily_report_endpoint_returns_report(monkeypatch):
    from server import app

    source = Evidence(source="tiendanube", label="Tiendanube Artemea")

    def fake_build_daily_report_from_tiendanube(**kwargs):
        assert kwargs["business_name"] == "Artemea"
        assert kwargs["report_date"] == date(2026, 5, 19)
        assert kwargs["store_id"] == "12345"
        assert kwargs["access_token"] == "tn_token"
        assert kwargs["include_stock"] is True
        assert kwargs["source_label"] == "Tienda Artemea"
        return DailyReport(
            business_name="Artemea",
            report_date=kwargs["report_date"],
            metrics=[Metric(key="revenue_today", label="Ventas de hoy", value=70000, unit="ARS", evidence=[source])],
            insights=[],
        )

    monkeypatch.setattr("server.build_daily_report_from_tiendanube", fake_build_daily_report_from_tiendanube)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/tiendanube",
        json={
            "business_name": "Artemea",
            "report_date": "2026-05-19",
            "store_id": "12345",
            "access_token": "tn_token",
            "include_stock": True,
            "source_label": "Tienda Artemea",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "Prioridad:" in body["text"]
    assert body["report"]["business_name"] == "Artemea"
    assert body["report"]["metrics"][0]["evidence"][0]["source"] == "tiendanube"


def test_tiendanube_daily_report_endpoint_rejects_missing_required_fields():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily/tiendanube", json={"business_name": "Artemea"})

    assert response.status_code == 400
    assert "store_id" in response.get_json()["error"]
    assert "access_token" in response.get_json()["error"]


def test_tiendanube_daily_report_endpoint_rejects_bad_report_date():
    from server import app

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/tiendanube",
        json={
            "business_name": "Artemea",
            "store_id": "12345",
            "access_token": "tn_token",
            "report_date": "19/05/2026",
        },
    )

    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.get_json()["error"]


def test_tiendanube_daily_report_endpoint_maps_auth_errors(monkeypatch):
    from server import app

    def fake_build_daily_report_from_tiendanube(**kwargs):
        raise TiendanubeAuthError("bad token")

    monkeypatch.setattr("server.build_daily_report_from_tiendanube", fake_build_daily_report_from_tiendanube)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/tiendanube",
        json={"business_name": "Artemea", "store_id": "12345", "access_token": "bad"},
    )

    assert response.status_code == 401
    assert "bad token" in response.get_json()["error"]


def test_tiendanube_daily_report_endpoint_maps_connection_errors(monkeypatch):
    from server import app

    def fake_build_daily_report_from_tiendanube(**kwargs):
        raise TiendanubeConnectionError("api down")

    monkeypatch.setattr("server.build_daily_report_from_tiendanube", fake_build_daily_report_from_tiendanube)

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/tiendanube",
        json={"business_name": "Artemea", "store_id": "12345", "access_token": "tok"},
    )

    assert response.status_code == 502
    assert "api down" in response.get_json()["error"]
