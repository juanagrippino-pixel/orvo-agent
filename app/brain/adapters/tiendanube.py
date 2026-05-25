"""Tiendanube adapter for Orvo Brain.

Fetches orders (and optionally product stock) for a given date and returns a
DailyReport with normalized Metric objects, each backed by an Evidence record.

No env vars are read here — callers supply store_id and access_token directly.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.brain.models import DailyReport, Evidence, Metric


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TiendanubeAuthError(Exception):
    """Raised on HTTP 401/403 from Tiendanube."""


class TiendanubeConnectionError(Exception):
    """Raised on HTTP 5xx or unexpected 4xx from Tiendanube."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BASE = "https://api.tiendanube.com/v1"


def _headers(access_token: str, store_id: str) -> dict[str, str]:
    return {
        "Authentication": f"bearer {access_token}",
        "User-Agent": f"Orvo Brain/1.0 ({store_id}@orvo.ai)",
    }


def _is_empty_last_page_response(resp: Any) -> bool:
    if resp.status_code != 404:
        return False
    try:
        body = resp.json()
    except Exception:
        return False
    if not isinstance(body, dict):
        return False
    description = str(body.get("description") or "")
    return "Last page is 0" in description


def _check_response(resp: Any) -> None:
    status = resp.status_code
    if status in (401, 403):
        raise TiendanubeAuthError(f"Tiendanube auth failed: HTTP {status}")
    if status >= 400:
        raise TiendanubeConnectionError(f"Tiendanube error: HTTP {status}")


def _parse_next_link(link_header: str) -> str:
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return ""


def _fetch_all_pages(session: Any, url: str, headers: dict, params: dict) -> list[dict]:
    items: list[dict] = []
    resp = session.get(url, headers=headers, params=params)
    if _is_empty_last_page_response(resp):
        return items
    _check_response(resp)
    items.extend(resp.json())
    while True:
        next_url = _parse_next_link(resp.headers.get("Link", ""))
        if not next_url:
            break
        resp = session.get(next_url, headers=headers)
        if _is_empty_last_page_response(resp):
            break
        _check_response(resp)
        items.extend(resp.json())
    return items


def _date_range_params(report_date: date) -> dict[str, str]:
    fmt = "%Y-%m-%dT%H:%M:%S-0300"
    start = datetime(report_date.year, report_date.month, report_date.day, 0, 0, 0)
    end = datetime(report_date.year, report_date.month, report_date.day, 23, 59, 59)
    return {
        "created_at_min": start.strftime(fmt),
        "created_at_max": end.strftime(fmt),
        "per_page": "200",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_daily_report_from_tiendanube(
    business_name: str,
    store_id: str,
    access_token: str,
    report_date: Optional[date] = None,
    http_client: Any = None,
    include_stock: bool = False,
    source_label: str = "Tiendanube",
) -> DailyReport:
    """Return a DailyReport populated from Tiendanube API data.

    Args:
        business_name: Human-readable store name.
        store_id: Tiendanube numeric store ID.
        access_token: OAuth bearer token.
        report_date: Date to report on; defaults to today.
        http_client: Injectable session (must support .get(url, **kw)).
                     Defaults to a new requests.Session() if None.
        include_stock: When True, also fetch product stock.
        source_label: Human-readable label for Evidence records.
    """
    if http_client is None:
        import requests
        http_client = requests.Session()

    report_date = report_date or date.today()
    hdrs = _headers(access_token, store_id)

    # -- Orders -----------------------------------------------------------
    orders = _fetch_all_pages(
        http_client,
        f"{_BASE}/{store_id}/orders",
        hdrs,
        _date_range_params(report_date),
    )

    active = [o for o in orders if o.get("status") != "cancelled"]
    revenue = sum(float(o.get("total", 0)) for o in active)
    order_count = len(active)

    orders_evidence = Evidence(
        source="tiendanube",
        label=f"{source_label} · orders",
    )

    metrics: list[Metric] = [
        Metric(
            key="revenue_today",
            label="Ventas del día",
            value=revenue,
            unit="ARS",
            evidence=[orders_evidence],
        ),
        Metric(
            key="orders_today",
            label="Pedidos del día",
            value=order_count,
            unit="orders",
            evidence=[orders_evidence],
        ),
    ]

    # -- Stock (optional) -------------------------------------------------
    if include_stock:
        products = _fetch_all_pages(
            http_client,
            f"{_BASE}/{store_id}/products",
            hdrs,
            {"per_page": "200"},
        )
        stock_total = sum(
            int(v["stock"])
            for p in products
            for v in p.get("variants", [])
            if v.get("stock") is not None
        )
        metrics.append(
            Metric(
                key="stock_units",
                label="Unidades en stock",
                value=stock_total,
                unit="units",
                evidence=[Evidence(source="tiendanube", label=f"{source_label} · products")],
            )
        )

    return DailyReport(
        business_name=business_name,
        report_date=report_date,
        metrics=metrics,
    )
