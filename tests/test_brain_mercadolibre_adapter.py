"""TDD tests for app/brain/adapters/mercadolibre.py

Uses a fake HTTP client — no real network calls.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.brain.adapters.mercadolibre import (
    MercadoLibreAPIError,
    MercadoLibreAuthError,
    MercadoLibreConnectionError,
    build_daily_report_from_mercadolibre,
)
from app.brain.models import DailyReport, Evidence


# ---------------------------------------------------------------------------
# Fake HTTP client helpers
# ---------------------------------------------------------------------------

def _response(data: Any, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.headers = {}
    return r


def _single_response_client(resp: MagicMock) -> MagicMock:
    session = MagicMock()
    session.get.return_value = resp
    return session


def _paged_client(pages: list[dict]) -> MagicMock:
    """Fake session that returns successive pages by call order."""
    session = MagicMock()
    responses = [_response(p) for p in pages]
    session.get.side_effect = responses
    return session


REPORT_DATE = date(2026, 5, 19)


def _orders_body(results: list[dict], total: int | None = None, offset: int = 0, limit: int = 50) -> dict:
    body = {"results": results}
    if total is not None:
        body["paging"] = {"total": total, "offset": offset, "limit": limit}
    return body


PAID_ORDERS = [
    {"id": 1001, "status": "paid", "total_amount": 5000.0},
    {"id": 1002, "status": "paid", "total_amount": 3200.5},
]

CANCELLED_ORDER = {"id": 1003, "status": "cancelled", "total_amount": 999.0}

CONFIRMED_ORDER = {"id": 1004, "status": "confirmed", "total_amount": 1800.0}


# ---------------------------------------------------------------------------
# Return type and shape
# ---------------------------------------------------------------------------

def test_returns_daily_report():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        business_name="Mi Tienda",
        report_date=REPORT_DATE,
        seller_id="42",
        access_token="tok",
        http_client=client,
    )
    assert isinstance(result, DailyReport)


def test_business_name_preserved():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        business_name="Mi Tienda",
        report_date=REPORT_DATE,
        seller_id="42",
        access_token="tok",
        http_client=client,
    )
    assert result.business_name == "Mi Tienda"


def test_report_date_preserved():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        business_name="T",
        report_date=REPORT_DATE,
        seller_id="42",
        access_token="tok",
        http_client=client,
    )
    assert result.report_date == REPORT_DATE


# ---------------------------------------------------------------------------
# revenue_today
# ---------------------------------------------------------------------------

def test_revenue_today_present():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    assert any(m.key == "revenue_today" for m in result.metrics)


def test_revenue_sums_paid_orders():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == pytest.approx(8200.5)


def test_revenue_includes_confirmed_orders():
    client = _single_response_client(
        _response(_orders_body(PAID_ORDERS + [CONFIRMED_ORDER]))
    )
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == pytest.approx(10000.5)


def test_revenue_excludes_cancelled_orders():
    client = _single_response_client(
        _response(_orders_body(PAID_ORDERS + [CANCELLED_ORDER]))
    )
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == pytest.approx(8200.5)


def test_revenue_zero_when_no_orders():
    client = _single_response_client(_response(_orders_body([])))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == 0.0


# ---------------------------------------------------------------------------
# orders_today
# ---------------------------------------------------------------------------

def test_orders_today_counts_active_orders():
    client = _single_response_client(
        _response(_orders_body(PAID_ORDERS + [CANCELLED_ORDER]))
    )
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "orders_today")
    assert m.value == 2


def test_orders_today_zero_when_empty():
    client = _single_response_client(_response(_orders_body([])))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "orders_today")
    assert m.value == 0


# ---------------------------------------------------------------------------
# avg_order_value
# ---------------------------------------------------------------------------

def test_avg_order_value_present():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    assert any(m.key == "avg_order_value" for m in result.metrics)


def test_avg_order_value_revenue_over_orders():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "avg_order_value")
    assert m.value == pytest.approx(8200.5 / 2)


def test_avg_order_value_zero_when_no_orders():
    client = _single_response_client(_response(_orders_body([])))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "avg_order_value")
    assert m.value == 0


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_every_metric_has_evidence():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    for m in result.metrics:
        assert len(m.evidence) >= 1, f"Metric {m.key} has no evidence"
        for e in m.evidence:
            assert isinstance(e, Evidence)


def test_evidence_source_is_mercadolibre():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    for m in result.metrics:
        sources = {e.source for e in m.evidence}
        assert "mercadolibre" in sources


def test_evidence_label_uses_source_label():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    result = build_daily_report_from_mercadolibre(
        "T",
        REPORT_DATE,
        "42",
        "tok",
        http_client=client,
        source_label="ML Argentina",
    )
    labels = {e.label for m in result.metrics for e in m.evidence}
    assert any("ML Argentina" in lab for lab in labels)


def test_evidence_does_not_expose_access_token():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    secret = "SUPER_SECRET_ML_TOKEN_zzz"
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", secret, http_client=client
    )
    serialized = json.dumps(result.model_dump(mode="json"))
    assert secret not in serialized


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_pagination_fetches_multiple_pages():
    page1 = _orders_body(
        [{"id": i, "status": "paid", "total_amount": 100.0} for i in range(50)],
        total=120,
        offset=0,
        limit=50,
    )
    page2 = _orders_body(
        [{"id": 50 + i, "status": "paid", "total_amount": 100.0} for i in range(50)],
        total=120,
        offset=50,
        limit=50,
    )
    page3 = _orders_body(
        [{"id": 100 + i, "status": "paid", "total_amount": 100.0} for i in range(20)],
        total=120,
        offset=100,
        limit=50,
    )
    client = _paged_client([page1, page2, page3])

    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    m = next(m for m in result.metrics if m.key == "orders_today")
    assert m.value == 120
    assert client.get.call_count == 3


def test_pagination_advances_offset():
    page1 = _orders_body(
        [{"id": 1, "status": "paid", "total_amount": 10.0}],
        total=2,
        offset=0,
        limit=1,
    )
    page2 = _orders_body(
        [{"id": 2, "status": "paid", "total_amount": 20.0}],
        total=2,
        offset=1,
        limit=1,
    )
    client = _paged_client([page1, page2])

    build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    offsets = [call.kwargs.get("params", {}).get("offset") for call in client.get.call_args_list]
    assert offsets[0] == 0
    assert offsets[1] >= 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_auth_error_on_401():
    client = _single_response_client(_response(None, status=401))
    with pytest.raises(MercadoLibreAuthError):
        build_daily_report_from_mercadolibre(
            "T", REPORT_DATE, "42", "bad", http_client=client
        )


def test_auth_error_on_403():
    client = _single_response_client(_response(None, status=403))
    with pytest.raises(MercadoLibreAuthError):
        build_daily_report_from_mercadolibre(
            "T", REPORT_DATE, "42", "bad", http_client=client
        )


def test_api_error_on_500():
    client = _single_response_client(_response(None, status=500))
    with pytest.raises(MercadoLibreAPIError):
        build_daily_report_from_mercadolibre(
            "T", REPORT_DATE, "42", "tok", http_client=client
        )


def test_api_error_on_503():
    client = _single_response_client(_response(None, status=503))
    with pytest.raises(MercadoLibreAPIError):
        build_daily_report_from_mercadolibre(
            "T", REPORT_DATE, "42", "tok", http_client=client
        )


def test_connection_error_on_unexpected_4xx():
    client = _single_response_client(_response(None, status=418))
    with pytest.raises(MercadoLibreConnectionError):
        build_daily_report_from_mercadolibre(
            "T", REPORT_DATE, "42", "tok", http_client=client
        )


# ---------------------------------------------------------------------------
# HTTP call details
# ---------------------------------------------------------------------------

def test_seller_id_passed_in_request():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "777", "tok", http_client=client
    )
    call = client.get.call_args_list[0]
    params = call.kwargs.get("params", {})
    flat = " ".join(str(v) for v in params.values()) + " " + call.args[0]
    assert "777" in flat


def test_access_token_in_authorization_header():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "mytoken", http_client=client
    )
    headers = client.get.call_args_list[0].kwargs.get("headers", {})
    assert "mytoken" in headers.get("Authorization", "")


def test_default_site_id_is_mla():
    client = _single_response_client(_response(_orders_body(PAID_ORDERS)))
    # Should not raise with default site_id
    result = build_daily_report_from_mercadolibre(
        "T", REPORT_DATE, "42", "tok", http_client=client
    )
    assert isinstance(result, DailyReport)
