"""TDD tests for app/brain/adapters/meta_ads.py

Uses a fake HTTP client — no real network calls.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.brain.adapters.meta_ads import (
    MetaAdsAPIError,
    MetaAdsAuthError,
    MetaAdsConnectionError,
    build_daily_report_from_meta_ads,
)
from app.brain.models import DailyReport, Evidence


# ---------------------------------------------------------------------------
# Fake HTTP client helpers
# ---------------------------------------------------------------------------

def _response(data: Any, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    return r


def _client(resp: MagicMock) -> MagicMock:
    session = MagicMock()
    session.get.return_value = resp
    return session


REPORT_DATE = date(2026, 5, 19)

# Sample API response bodies
SINGLE_ROW = {
    "data": [
        {
            "spend": "1500.75",
            "impressions": "20000",
            "clicks": "350",
            "purchase_roas": [{"action_type": "omni_purchase", "value": "3.20"}],
            "date_start": "2026-05-19",
            "date_stop": "2026-05-19",
        }
    ]
}

MULTI_ROW = {
    "data": [
        {
            "spend": "1000.00",
            "impressions": "10000",
            "clicks": "200",
            "purchase_roas": [{"action_type": "omni_purchase", "value": "2.50"}],
        },
        {
            "spend": "500.75",
            "impressions": "8000",
            "clicks": "90",
            "purchase_roas": [{"action_type": "omni_purchase", "value": "4.10"}],
        },
    ]
}

ZERO_SPEND = {
    "data": [
        {
            "spend": "0",
            "impressions": "0",
            "clicks": "0",
            "purchase_roas": [],
        }
    ]
}

EMPTY_DATA = {"data": []}


# ---------------------------------------------------------------------------
# Return type and shape
# ---------------------------------------------------------------------------

def test_returns_daily_report():
    result = build_daily_report_from_meta_ads(
        "Mi Tienda", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert isinstance(result, DailyReport)


def test_business_name_preserved():
    result = build_daily_report_from_meta_ads(
        "Mi Tienda", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert result.business_name == "Mi Tienda"


def test_report_date_preserved():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert result.report_date == REPORT_DATE


# ---------------------------------------------------------------------------
# ad_spend_today
# ---------------------------------------------------------------------------

def test_ad_spend_today_present():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert any(m.key == "ad_spend_today" for m in result.metrics)


def test_ad_spend_single_row():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_spend_today")
    assert m.value == pytest.approx(1500.75)


def test_ad_spend_aggregates_multiple_rows():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(MULTI_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_spend_today")
    assert m.value == pytest.approx(1500.75)


def test_ad_spend_zero_on_empty_data():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(EMPTY_DATA)),
    )
    m = next(m for m in result.metrics if m.key == "ad_spend_today")
    assert m.value == 0.0


def test_ad_spend_zero_on_zero_spend_day():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(ZERO_SPEND)),
    )
    m = next(m for m in result.metrics if m.key == "ad_spend_today")
    assert m.value == 0.0


def test_ad_spend_unit_is_ars():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_spend_today")
    assert m.unit == "ARS"


# ---------------------------------------------------------------------------
# ad_impressions_today
# ---------------------------------------------------------------------------

def test_ad_impressions_today_present():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert any(m.key == "ad_impressions_today" for m in result.metrics)


def test_ad_impressions_single_row():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_impressions_today")
    assert m.value == 20000


def test_ad_impressions_aggregates_multiple_rows():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(MULTI_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_impressions_today")
    assert m.value == 18000


def test_ad_impressions_zero_on_zero_spend_day():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(ZERO_SPEND)),
    )
    m = next(m for m in result.metrics if m.key == "ad_impressions_today")
    assert m.value == 0


# ---------------------------------------------------------------------------
# ad_clicks_today
# ---------------------------------------------------------------------------

def test_ad_clicks_today_present():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert any(m.key == "ad_clicks_today" for m in result.metrics)


def test_ad_clicks_single_row():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_clicks_today")
    assert m.value == 350


def test_ad_clicks_aggregates_multiple_rows():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(MULTI_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_clicks_today")
    assert m.value == 290


def test_ad_clicks_zero_on_zero_spend_day():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(ZERO_SPEND)),
    )
    m = next(m for m in result.metrics if m.key == "ad_clicks_today")
    assert m.value == 0


# ---------------------------------------------------------------------------
# ad_roas_today
# ---------------------------------------------------------------------------

def test_ad_roas_today_present():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    assert any(m.key == "ad_roas_today" for m in result.metrics)


def test_ad_roas_single_row():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_roas_today")
    assert m.value == pytest.approx(3.20)


def test_ad_roas_averages_multiple_rows():
    """ROAS is averaged across campaigns that reported it."""
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(MULTI_ROW)),
    )
    m = next(m for m in result.metrics if m.key == "ad_roas_today")
    # (2.50 + 4.10) / 2
    assert m.value == pytest.approx(3.30)


def test_ad_roas_zero_when_no_purchase_roas():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(ZERO_SPEND)),
    )
    m = next(m for m in result.metrics if m.key == "ad_roas_today")
    assert m.value == 0.0


def test_ad_roas_zero_on_empty_data():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(EMPTY_DATA)),
    )
    m = next(m for m in result.metrics if m.key == "ad_roas_today")
    assert m.value == 0.0


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_every_metric_has_evidence():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    for m in result.metrics:
        assert len(m.evidence) >= 1, f"Metric {m.key} has no evidence"
        for e in m.evidence:
            assert isinstance(e, Evidence)


def test_evidence_source_is_meta_ads():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=_client(_response(SINGLE_ROW)),
    )
    for m in result.metrics:
        sources = {e.source for e in m.evidence}
        assert "meta_ads" in sources


def test_evidence_label_uses_source_label():
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        source_label="Meta Ads MiNegocio",
        http_client=_client(_response(SINGLE_ROW)),
    )
    labels = {e.label for m in result.metrics for e in m.evidence}
    assert any("Meta Ads MiNegocio" in lab for lab in labels)


def test_evidence_does_not_expose_access_token():
    secret = "SUPER_SECRET_META_TOKEN_zzz"
    result = build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", secret,
        http_client=_client(_response(SINGLE_ROW)),
    )
    serialized = json.dumps(result.model_dump(mode="json"))
    assert secret not in serialized


# ---------------------------------------------------------------------------
# ad_account_id prefix handling
# ---------------------------------------------------------------------------

def test_act_prefix_not_doubled():
    """If ad_account_id already has 'act_' prefix, URL should not double it."""
    client = _client(_response(SINGLE_ROW))
    build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "act_123456789", "tok",
        http_client=client,
    )
    call_url = client.get.call_args_list[0].args[0]
    assert "act_act_" not in call_url
    assert "act_123456789" in call_url


def test_act_prefix_added_when_missing():
    client = _client(_response(SINGLE_ROW))
    build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=client,
    )
    call_url = client.get.call_args_list[0].args[0]
    assert "act_123456789" in call_url


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_auth_error_on_401():
    with pytest.raises(MetaAdsAuthError):
        build_daily_report_from_meta_ads(
            "T", REPORT_DATE, "123456789", "bad",
            http_client=_client(_response(None, status=401)),
        )


def test_auth_error_on_403():
    with pytest.raises(MetaAdsAuthError):
        build_daily_report_from_meta_ads(
            "T", REPORT_DATE, "123456789", "bad",
            http_client=_client(_response(None, status=403)),
        )


def test_api_error_on_500():
    with pytest.raises(MetaAdsAPIError):
        build_daily_report_from_meta_ads(
            "T", REPORT_DATE, "123456789", "tok",
            http_client=_client(_response(None, status=500)),
        )


def test_api_error_on_503():
    with pytest.raises(MetaAdsAPIError):
        build_daily_report_from_meta_ads(
            "T", REPORT_DATE, "123456789", "tok",
            http_client=_client(_response(None, status=503)),
        )


def test_connection_error_on_unexpected_4xx():
    with pytest.raises(MetaAdsConnectionError):
        build_daily_report_from_meta_ads(
            "T", REPORT_DATE, "123456789", "tok",
            http_client=_client(_response(None, status=400)),
        )


# ---------------------------------------------------------------------------
# HTTP call details
# ---------------------------------------------------------------------------

def test_access_token_in_request_params():
    client = _client(_response(SINGLE_ROW))
    build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "mytoken",
        http_client=client,
    )
    params = client.get.call_args_list[0].kwargs.get("params", {})
    assert params.get("access_token") == "mytoken"


def test_request_uses_report_date_time_range_not_today_preset():
    requested_date = date(2026, 5, 17)
    client = _client(_response(SINGLE_ROW))
    build_daily_report_from_meta_ads(
        "T", requested_date, "123456789", "tok",
        http_client=client,
    )
    params = client.get.call_args_list[0].kwargs.get("params", {})
    assert json.loads(params.get("time_range")) == {"since": "2026-05-17", "until": "2026-05-17"}
    assert "date_preset" not in params


def test_required_fields_in_params():
    client = _client(_response(SINGLE_ROW))
    build_daily_report_from_meta_ads(
        "T", REPORT_DATE, "123456789", "tok",
        http_client=client,
    )
    params = client.get.call_args_list[0].kwargs.get("params", {})
    fields = params.get("fields", "")
    for f in ("spend", "impressions", "clicks", "purchase_roas"):
        assert f in fields, f"Expected field '{f}' not in API request fields"
