# Tiendanube Connector — Orvo Brain

## Overview

Pulls daily sales/order/stock data from a Tiendanube store and returns a `DailyReport`
with normalized `Metric` objects, each backed by an `Evidence` record pointing to the
Tiendanube API as its source.

---

## Endpoints Used

| Purpose | Method | Path |
|---------|--------|------|
| Orders for a date range | GET | `/v1/{store_id}/orders` |
| Product list (for stock) | GET | `/v1/{store_id}/products` |

### Orders endpoint

```
GET https://api.tiendanube.com/v1/{store_id}/orders
    ?created_at_min=2026-05-19T00:00:00-0300
    &created_at_max=2026-05-19T23:59:59-0300
    &per_page=200
```

Pagination: response header `Link: <url>; rel="next"` — follow until absent.
Only orders with `status != "cancelled"` are counted toward revenue and order count.

### Products endpoint (optional, for stock)

```
GET https://api.tiendanube.com/v1/{store_id}/products?per_page=200
```

Each product has `variants[].stock` (integer or `null` for unlimited).
`stock_units` = sum of all non-null variant stocks across all products.

---

## Auth

Header (note lowercase `bearer`, per Tiendanube docs):

```
Authentication: bearer {TIENDANUBE_ACCESS_TOKEN}
User-Agent: Orvo Brain/1.0 ({store_id}@orvo.ai)
```

### Required env vars (caller's responsibility)

| Var | Description |
|-----|-------------|
| `TIENDANUBE_USER_ID` | Numeric store ID (path parameter) |
| `TIENDANUBE_ACCESS_TOKEN` | OAuth access token |

The adapter does **not** read env vars directly — callers must pass `store_id` and
`access_token`. This keeps the adapter fully testable without environment patching.

---

## Normalized Fields → Metrics

| Metric key | Formula | Unit | Label |
|-----------|---------|------|-------|
| `revenue_today` | Sum of `total` for non-cancelled orders | ARS | Ventas del día |
| `orders_today` | Count of non-cancelled orders | orders | Pedidos del día |
| `stock_units` | Sum of non-null variant stocks (if `include_stock=True`) | units | Unidades en stock |

Each `Metric` carries:

```python
evidence=[Evidence(source="tiendanube", label="Tiendanube · orders")]
```

---

## Failure Modes

| Scenario | Behaviour |
|----------|-----------|
| HTTP 401/403 | Raise `TiendanubeAuthError` |
| HTTP 4xx/5xx other | Raise `TiendanubeConnectionError` |
| Empty orders (200) | `revenue_today=0`, `orders_today=0` |
| `stock` is `null` on variant | Treated as unlimited — skipped from sum |
| `include_stock=False` (default) | Products endpoint never called |

---

## Public API

```python
def build_daily_report_from_tiendanube(
    business_name: str,
    store_id: str,
    access_token: str,
    report_date: date | None = None,
    http_client=None,           # injectable for tests; defaults to requests.Session
    include_stock: bool = False,
    source_label: str = "Tiendanube",
) -> DailyReport
```

---

## Pagination

The Tiendanube API paginates via a `Link` header. The adapter follows `rel="next"` links
until the header is absent, preventing silent data truncation on days with >200 orders.

---

## Not in Scope (this iteration)

- Abandoned cart data
- Product-level revenue breakdown
- Multi-currency stores
- Webhook-based real-time sync
