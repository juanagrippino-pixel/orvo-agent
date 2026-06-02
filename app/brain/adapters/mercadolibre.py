"""MercadoLibre adapter for Orvo Brain.

Fetches sold orders for a given date from the MercadoLibre orders/search API
and returns a DailyReport with normalized Metric objects, each backed by an
Evidence record.

No env vars are read here — callers supply seller_id and access_token directly.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.brain.models import DailyReport, Evidence, Metric


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MercadoLibreAuthError(Exception):
    """Raised on HTTP 401/403 from MercadoLibre."""


class MercadoLibreAPIError(Exception):
    """Raised on HTTP 5xx from MercadoLibre."""


class MercadoLibreConnectionError(Exception):
    """Raised on unexpected non-success HTTP responses from MercadoLibre."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = "https://api.mercadolibre.com"
_PAID_STATUSES = {"paid", "confirmed"}
_CANCELLED_STATUSES = {"cancelled"}
_DEFAULT_PAGE_LIMIT = 50


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def _check_response(resp: Any) -> None:
    status = resp.status_code
    if status in (401, 403):
        raise MercadoLibreAuthError(f"MercadoLibre auth failed: HTTP {status}")
    if 500 <= status < 600:
        raise MercadoLibreAPIError(f"MercadoLibre server error: HTTP {status}")
    if status >= 400:
        raise MercadoLibreConnectionError(f"MercadoLibre error: HTTP {status}")


def _date_range_params(report_date: date) -> dict[str, str]:
    fmt = "%Y-%m-%dT%H:%M:%S.000-03:00"
    start = datetime(report_date.year, report_date.month, report_date.day, 0, 0, 0)
    end = datetime(report_date.year, report_date.month, report_date.day, 23, 59, 59)
    return {
        "order.date_created.from": start.strftime(fmt),
        "order.date_created.to": end.strftime(fmt),
    }


def _fetch_all_pages(
    session: Any,
    url: str,
    headers: dict,
    base_params: dict,
) -> list[dict]:
    results: list[dict] = []
    offset = 0
    limit = _DEFAULT_PAGE_LIMIT
    while True:
        params = {**base_params, "offset": offset, "limit": limit}
        resp = session.get(url, headers=headers, params=params)
        _check_response(resp)
        body = resp.json() or {}
        page = body.get("results") or []
        results.extend(page)

        paging = body.get("paging") or {}
        total = paging.get("total")
        if total is None:
            break

        page_limit = paging.get("limit") or limit
        page_offset = paging.get("offset")
        if page_offset is None:
            page_offset = offset
        offset = page_offset + page_limit
        limit = page_limit
        if offset >= total or not page:
            break
    return results


def _is_active_paid(order: dict) -> bool:
    status = (order.get("status") or "").lower()
    if status in _CANCELLED_STATUSES:
        return False
    return status in _PAID_STATUSES


def _order_total(order: dict) -> float:
    raw = order.get("total_amount", 0)
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_daily_report_from_mercadolibre(
    business_name: str,
    report_date: date,
    seller_id: str,
    access_token: str,
    site_id: str = "MLA",
    source_label: str = "MercadoLibre",
    http_client: Optional[Any] = None,
) -> DailyReport:
    """Return a DailyReport populated from MercadoLibre orders/search.

    Args:
        business_name: Human-readable store name.
        report_date: Date to report on (no default — be explicit).
        seller_id: MercadoLibre numeric seller user ID.
        access_token: OAuth bearer token.
        site_id: MercadoLibre site code (default "MLA" = Argentina).
        source_label: Human-readable label for Evidence records.
        http_client: Injectable session (must support .get(url, **kw)).
                     Defaults to a new requests.Session() if None.
    """
    if http_client is None:
        import requests
        http_client = requests.Session()

    hdrs = _headers(access_token)
    base_params = {
        "seller": seller_id,
        "site_id": site_id,
        **_date_range_params(report_date),
    }

    orders = _fetch_all_pages(
        http_client,
        f"{_BASE}/orders/search",
        hdrs,
        base_params,
    )

    active = [o for o in orders if _is_active_paid(o)]
    revenue = float(sum(_order_total(o) for o in active))
    order_count = len(active)
    aov = (revenue / order_count) if order_count else 0.0

    summary = {
        "seller_id": seller_id,
        "site_id": site_id,
        "report_date": report_date.isoformat(),
        "orders_fetched": len(orders),
        "orders_active": order_count,
    }

    evidence = Evidence(
        source="mercadolibre",
        label=f"{source_label} · orders",
        summary=summary,
    )

    metrics: list[Metric] = [
        Metric(
            key="revenue_today",
            label="Ventas del día",
            value=revenue,
            unit="ARS",
            evidence=[evidence],
        ),
        Metric(
            key="orders_today",
            label="Pedidos del día",
            value=order_count,
            unit="orders",
            evidence=[evidence],
        ),
        Metric(
            key="avg_order_value",
            label="Ticket promedio",
            value=aov,
            unit="ARS",
            evidence=[evidence],
        ),
    ]

    return DailyReport(
        business_name=business_name,
        report_date=report_date,
        metrics=metrics,
    )
