"""TDD tests for app/brain/adapters/tiendanube.py

Uses a fake HTTP client — no real network calls.
"""
from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.brain.adapters.tiendanube import (
    TiendanubeAuthError,
    TiendanubeConnectionError,
    build_daily_report_from_tiendanube,
)
from app.brain.models import DailyReport, Evidence, Metric


# ---------------------------------------------------------------------------
# Fake HTTP client helpers
# ---------------------------------------------------------------------------

def _response(data: Any, status: int = 200, link: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.headers = {"Link": link} if link else {}
    return r


def _client(responses: dict[str, MagicMock]) -> MagicMock:
    """Fake session: matches URL fragments to canned responses."""
    session = MagicMock()

    def fake_get(url, **kwargs):
        for fragment, resp in responses.items():
            if fragment in url:
                return resp
        raise ValueError(f"Unexpected URL in test: {url}")

    session.get.side_effect = fake_get
    return session


TWO_ORDERS = [
    {"id": 1, "status": "paid", "total": "5000.00"},
    {"id": 2, "status": "open", "total": "3200.50"},
]

ONE_CANCELLED = [{"id": 3, "status": "cancelled", "total": "999.00"}]

PRODUCTS_WITH_STOCK = [
    {"id": 10, "variants": [{"stock": 5}, {"stock": 3}]},
    {"id": 11, "variants": [{"stock": None}, {"stock": 10}]},
]


# ---------------------------------------------------------------------------
# Return type and shape
# ---------------------------------------------------------------------------

def test_returns_daily_report():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube(
        business_name="Test Store", store_id="123", access_token="tok", http_client=client
    )
    assert isinstance(result, DailyReport)


def test_business_name_preserved():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube(
        business_name="Mi Tienda", store_id="123", access_token="tok", http_client=client
    )
    assert result.business_name == "Mi Tienda"


def test_report_date_defaults_to_today():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube(
        business_name="T", store_id="1", access_token="tok", http_client=client
    )
    assert result.report_date == date.today()


def test_report_date_custom():
    client = _client({"orders": _response(TWO_ORDERS)})
    d = date(2026, 5, 19)
    result = build_daily_report_from_tiendanube(
        business_name="T", store_id="1", access_token="tok", report_date=d, http_client=client
    )
    assert result.report_date == d


# ---------------------------------------------------------------------------
# revenue_today
# ---------------------------------------------------------------------------

def test_revenue_today_key_present():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    assert any(m.key == "revenue_today" for m in result.metrics)


def test_revenue_today_sums_non_cancelled():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == pytest.approx(8200.50)


def test_revenue_today_excludes_cancelled():
    client = _client({"orders": _response(TWO_ORDERS + ONE_CANCELLED)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == pytest.approx(8200.50)


def test_revenue_today_zero_when_no_orders():
    client = _client({"orders": _response([])})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    m = next(m for m in result.metrics if m.key == "revenue_today")
    assert m.value == 0.0


# ---------------------------------------------------------------------------
# orders_today
# ---------------------------------------------------------------------------

def test_orders_today_key_present():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    assert any(m.key == "orders_today" for m in result.metrics)


def test_orders_today_counts_non_cancelled():
    client = _client({"orders": _response(TWO_ORDERS + ONE_CANCELLED)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    m = next(m for m in result.metrics if m.key == "orders_today")
    assert m.value == 2


def test_orders_today_zero_when_no_orders():
    client = _client({"orders": _response([])})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    m = next(m for m in result.metrics if m.key == "orders_today")
    assert m.value == 0


# ---------------------------------------------------------------------------
# Evidence on every metric
# ---------------------------------------------------------------------------

def test_every_metric_has_evidence():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    for m in result.metrics:
        assert len(m.evidence) >= 1, f"Metric {m.key} has no evidence"


def test_evidence_source_is_tiendanube():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    for m in result.metrics:
        sources = {e.source for e in m.evidence}
        assert "tiendanube" in sources, f"Metric {m.key} missing tiendanube source"


def test_evidence_instances_are_evidence_type():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)
    for m in result.metrics:
        for e in m.evidence:
            assert isinstance(e, Evidence)


# ---------------------------------------------------------------------------
# stock_units (optional)
# ---------------------------------------------------------------------------

def test_stock_units_absent_when_include_stock_false():
    client = _client({"orders": _response(TWO_ORDERS)})
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client, include_stock=False)
    assert not any(m.key == "stock_units" for m in result.metrics)


def test_stock_units_present_when_include_stock_true():
    client = _client({
        "orders": _response(TWO_ORDERS),
        "products": _response(PRODUCTS_WITH_STOCK),
    })
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client, include_stock=True)
    assert any(m.key == "stock_units" for m in result.metrics)


def test_stock_units_sums_non_null_variants():
    client = _client({
        "orders": _response(TWO_ORDERS),
        "products": _response(PRODUCTS_WITH_STOCK),
    })
    result = build_daily_report_from_tiendanube("T", "1", "tok", http_client=client, include_stock=True)
    m = next(m for m in result.metrics if m.key == "stock_units")
    # 5+3 (product 10) + None (skip)+10 (product 11) = 18
    assert m.value == 18


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_auth_error_on_401():
    client = _client({"orders": _response(None, status=401)})
    with pytest.raises(TiendanubeAuthError):
        build_daily_report_from_tiendanube("T", "1", "bad", http_client=client)


def test_server_error_on_500():
    client = _client({"orders": _response(None, status=500)})
    with pytest.raises(TiendanubeConnectionError):
        build_daily_report_from_tiendanube("T", "1", "tok", http_client=client)


# ---------------------------------------------------------------------------
# HTTP call details
# ---------------------------------------------------------------------------

def test_store_id_in_orders_url():
    client = _client({"orders": _response(TWO_ORDERS)})
    build_daily_report_from_tiendanube("T", "42", "tok", http_client=client)
    call_url = client.get.call_args_list[0][0][0]
    assert "42" in call_url


def test_auth_header_sent():
    client = _client({"orders": _response(TWO_ORDERS)})
    build_daily_report_from_tiendanube("T", "1", "mytoken", http_client=client)
    call_kwargs = client.get.call_args_list[0][1]
    headers = call_kwargs.get("headers", {})
    assert "mytoken" in headers.get("Authentication", "")
