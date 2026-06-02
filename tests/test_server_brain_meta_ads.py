from datetime import date

import pytest

from app.brain.adapters.meta_ads import MetaAdsAPIError, MetaAdsAuthError, MetaAdsConnectionError
from app.brain.models import DailyReport, Evidence, Metric


def _assert_public_error_redacted(response, *raw_values):
    rendered = response.get_data(as_text=True)
    for raw_value in raw_values:
        assert raw_value not in rendered
    assert "[REDACTED]" in rendered


def test_meta_ads_daily_report_endpoint_returns_text_and_report(monkeypatch):
    from server import app

    client = app.test_client()
    captured = {}

    def fake_build_daily_report_from_meta_ads(**kwargs):
        captured.update(kwargs)
        return DailyReport(
            business_name=kwargs["business_name"],
            report_date=kwargs["report_date"],
            metrics=[
                Metric(
                    key="ad_spend_today",
                    label="Inversión publicitaria del día",
                    value=12500.0,
                    unit="ARS",
                    evidence=[Evidence(source="meta_ads", label="Meta Ads")],
                )
            ],
        )

    monkeypatch.setattr("server.build_daily_report_from_meta_ads", fake_build_daily_report_from_meta_ads)

    response = client.post(
        "/brain/reports/daily/meta-ads",
        json={
            "business_name": "Demo Meta",
            "ad_account_id": "act_12345",
            "access_token": "meta_test_token",
            "report_date": "2026-05-17",
            "source_label": "Meta Ads Demo",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["report"]["business_name"] == "Demo Meta"
    assert payload["report"]["report_date"] == "2026-05-17"
    assert "Demo Meta" in payload["text"]
    assert captured["business_name"] == "Demo Meta"
    assert captured["report_date"] == date(2026, 5, 17)
    assert captured["ad_account_id"] == "act_12345"
    assert captured["access_token"] == "meta_test_token"
    assert captured["source_label"] == "Meta Ads Demo"


def test_meta_ads_daily_report_endpoint_requires_fields():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily/meta-ads", json={"business_name": "Demo"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "missing_fields"
    assert payload["missing"] == ["ad_account_id", "access_token"]


def test_meta_ads_daily_report_endpoint_rejects_bad_date():
    from server import app

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily/meta-ads",
        json={"business_name": "Demo", "ad_account_id": "act_123", "access_token": "tok", "report_date": "bad-date"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_report_date"


def test_meta_ads_daily_report_endpoint_maps_auth_errors(monkeypatch):
    from server import app

    client = app.test_client()

    def raise_auth(**kwargs):
        raise MetaAdsAuthError("bad token")

    monkeypatch.setattr("server.build_daily_report_from_meta_ads", raise_auth)

    response = client.post(
        "/brain/reports/daily/meta-ads",
        json={"business_name": "Demo", "ad_account_id": "act_123", "access_token": "bad"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "meta_ads_auth_error"


def test_meta_ads_daily_report_endpoint_maps_api_errors(monkeypatch):
    from server import app

    client = app.test_client()

    def raise_api(**kwargs):
        raise MetaAdsAPIError("down")

    monkeypatch.setattr("server.build_daily_report_from_meta_ads", raise_api)

    response = client.post(
        "/brain/reports/daily/meta-ads",
        json={"business_name": "Demo", "ad_account_id": "act_123", "access_token": "tok"},
    )

    assert response.status_code == 502
    assert response.get_json()["error"] == "meta_ads_api_error"


@pytest.mark.parametrize(
    ("exception", "expected_status", "expected_error", "raw_values"),
    [
        (
            MetaAdsAuthError("Meta Ads auth failed access_token=raw-public-token"),
            401,
            "meta_ads_auth_error",
            ("raw-public-token",),
        ),
        (
            MetaAdsAPIError("Meta Ads API failed Authorization: Basic dXNlcjpzdXBlcl9zZWNyZXQ="),
            502,
            "meta_ads_api_error",
            ("dXNlcjpzdXBlcl9zZWNyZXQ=",),
        ),
        (
            MetaAdsConnectionError("Meta Ads connection failed refresh_token=raw-refresh-token"),
            502,
            "meta_ads_api_error",
            ("raw-refresh-token",),
        ),
        (
            ValueError("Meta Ads payload invalid refresh_token=raw-refresh-token"),
            400,
            None,
            ("raw-refresh-token",),
        ),
    ],
)
def test_meta_ads_daily_report_endpoint_redacts_secret_shaped_errors(
    monkeypatch,
    exception,
    expected_status,
    expected_error,
    raw_values,
):
    from server import app

    client = app.test_client()

    def raise_secret_error(**kwargs):
        raise exception

    monkeypatch.setattr("server.build_daily_report_from_meta_ads", raise_secret_error)

    response = client.post(
        "/brain/reports/daily/meta-ads",
        json={"business_name": "Demo", "ad_account_id": "act_123", "access_token": "tok"},
    )

    assert response.status_code == expected_status
    payload = response.get_json()
    if expected_error is not None:
        assert payload["error"] == expected_error
        assert "[REDACTED]" in payload["message"]
    else:
        assert "[REDACTED]" in payload["error"]
    _assert_public_error_redacted(response, *raw_values)
