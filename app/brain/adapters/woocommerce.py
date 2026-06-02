"""WooCommerce adapter for Orvo Brain.

Fetches read-only orders (and optionally product stock) from the WooCommerce REST
API and returns a DailyReport with normalized Metric objects, each backed by an
Evidence record.

No env vars are read here — callers supply store_url, consumer_key, and
consumer_secret directly. Credentials are passed via HTTP Basic auth kwargs so
they never enter URLs, query params, or error messages.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from urllib.parse import urlparse

from app.brain.models import DailyReport, Evidence, Metric


class WooCommerceAuthError(Exception):
    """Raised on HTTP 401/403 from WooCommerce."""


class WooCommerceAPIError(Exception):
    """Raised on HTTP 5xx from WooCommerce."""


class WooCommerceConnectionError(Exception):
    """Raised on unexpected non-success HTTP responses from WooCommerce."""


_ACTIVE_ORDER_STATUSES = {"processing", "completed"}
_DEFAULT_PAGE_LIMIT = 100


def _normalize_store_url(store_url: str) -> str:
    raw = str(store_url or "").strip()
    if not raw:
        raise WooCommerceConnectionError("WooCommerce store_url is required")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise WooCommerceConnectionError("WooCommerce store_url must include a host")
    return raw.rstrip("/")


def _endpoint(store_url: str, resource: str) -> str:
    return f"{_normalize_store_url(store_url)}/wp-json/wc/v3/{resource.lstrip('/')}"


def _check_response(resp: Any) -> None:
    status = resp.status_code
    if status in (401, 403):
        raise WooCommerceAuthError(f"WooCommerce auth failed: HTTP {status}")
    if 500 <= status < 600:
        raise WooCommerceAPIError(f"WooCommerce server error: HTTP {status}")
    if status >= 400:
        raise WooCommerceConnectionError(f"WooCommerce error: HTTP {status}")


def _date_range_params(report_date: date) -> dict[str, str]:
    start = datetime(report_date.year, report_date.month, report_date.day, 0, 0, 0)
    end = datetime(report_date.year, report_date.month, report_date.day, 23, 59, 59)
    return {
        "after": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "before": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "per_page": str(_DEFAULT_PAGE_LIMIT),
        "status": "any",
    }


def _fetch_all_pages(
    session: Any,
    url: str,
    *,
    auth: tuple[str, str],
    base_params: dict[str, str],
) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        params = {**base_params, "page": str(page)}
        resp = session.get(url, auth=auth, params=params)
        _check_response(resp)
        body = resp.json() or []
        if not isinstance(body, list):
            raise WooCommerceConnectionError("WooCommerce response body must be a list")
        items.extend(body)

        total_pages = _header_int(resp, "X-WP-TotalPages")
        if total_pages is not None:
            if page >= total_pages:
                break
        elif len(body) < _DEFAULT_PAGE_LIMIT:
            break
        page += 1
    return items


def _header_int(resp: Any, key: str) -> int | None:
    raw = (getattr(resp, "headers", {}) or {}).get(key)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _is_active_order(order: dict) -> bool:
    return str(order.get("status") or "").lower() in _ACTIVE_ORDER_STATUSES


def _money_value(raw: Any) -> float:
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _stock_quantity(raw: Any) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _currency_from_orders(orders: list[dict]) -> str | None:
    for order in orders:
        currency = order.get("currency")
        if isinstance(currency, str) and currency:
            return currency
    return None


def build_daily_report_from_woocommerce(
    business_name: str,
    store_url: str,
    consumer_key: str,
    consumer_secret: str,
    report_date: Optional[date] = None,
    http_client: Any = None,
    include_stock: bool = False,
    source_label: str = "WooCommerce",
) -> DailyReport:
    """Return a DailyReport populated from WooCommerce read-only API data.

    Args:
        business_name: Human-readable store name.
        store_url: Store base URL, e.g. ``https://store.example.com``.
        consumer_key: WooCommerce REST API consumer key.
        consumer_secret: WooCommerce REST API consumer secret.
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
    auth = (consumer_key, consumer_secret)

    orders = _fetch_all_pages(
        http_client,
        _endpoint(store_url, "orders"),
        auth=auth,
        base_params=_date_range_params(report_date),
    )
    active_orders = [order for order in orders if _is_active_order(order)]
    revenue = float(sum(_money_value(order.get("total")) for order in active_orders))
    order_count = len(active_orders)
    currency = _currency_from_orders(orders)

    orders_evidence = Evidence(source="woocommerce", label=f"{source_label} · orders")
    metrics: list[Metric] = [
        Metric(
            key="revenue_today",
            label="Ventas del día",
            value=revenue,
            unit=currency,
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

    if include_stock:
        products = _fetch_all_pages(
            http_client,
            _endpoint(store_url, "products"),
            auth=auth,
            base_params={"per_page": str(_DEFAULT_PAGE_LIMIT)},
        )
        stock_total = sum(_stock_quantity(product.get("stock_quantity")) for product in products)
        metrics.append(
            Metric(
                key="stock_units",
                label="Unidades en stock",
                value=stock_total,
                unit="units",
                evidence=[Evidence(source="woocommerce", label=f"{source_label} · products")],
            )
        )

    return DailyReport(
        business_name=business_name,
        report_date=report_date,
        metrics=metrics,
    )
