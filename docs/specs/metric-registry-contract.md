# Metric Registry Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `docs/specs/d2c-case-family-catalog.md`, `docs/specs/connector-registry-contract.md`

## Purpose

The metric registry defines the semantic meaning of metrics used by reports, detections, cases, and operator surfaces. It prevents connector drift, hidden aliases, and owner-facing claims that cannot be traced to evidence.

## Registry entry shape

```python
class MetricSpec(BaseModel):
    key: str
    family: str
    label: str
    unit: Literal["count", "money", "percent", "duration", "boolean", "timestamp"]
    allowed_sources: set[str]
    aliases: set[str] = set()
    aggregation: Literal["sum", "latest", "average", "min", "max", "ratio", "none"]
    freshness_required: bool = True
    report_allowed: bool
    case_allowed: bool
    evidence_required: bool = True
    pii_class: Literal["none", "low", "sensitive"] = "none"
```

## Initial D2C metric families

### Commerce

- `commerce.orders.count`
- `commerce.revenue.total`
- `commerce.inventory.available_units`
- `commerce.fulfillment.pending_count`
- `commerce.fulfillment.oldest_pending_age_hours`

### Ads

Post-pilot unless already implemented and tested.

- `ads.spend.total`
- `ads.delivery.impressions`
- `ads.delivery.clicks`
- `ads.roas.estimated`

### Support / conversations

- `support.conversations.unanswered_count`
- `support.conversations.oldest_unanswered_age_minutes`

### Runtime / data quality

- `runtime.freshness.last_success_at`
- `runtime.freshness.age_seconds`
- `runtime.data_quality.completeness_ratio`
- `runtime.connector.status`

## Legacy alias policy

Existing metric keys may remain during migration. Every legacy key that participates in new case/report behavior must be mapped explicitly.

Example:

```text
revenue_today -> commerce.revenue.total
orders_today -> commerce.orders.count
commerce.revenue.today -> commerce.revenue.total
commerce.orders.today -> commerce.orders.count
stock_units -> commerce.inventory.available_units
```

Rules:

- New case logic reads canonical keys.
- Report compatibility may render legacy labels temporarily.
- Alias removal requires migration note and tests.
- Workers must not add new unregistered aliases in templates or adapters.

## Evidence requirements

Every metric used in an owner-facing claim must carry:

- source connector type;
- source artifact/run ref where possible;
- observation timestamp;
- freshness state;
- unit and currency when relevant;
- redaction-safe entity labels.

## Case participation

Case families may only depend on metrics marked `case_allowed=true`.

Initial mapping:

| Case family | Required canonical metrics |
| --- | --- |
| `sales_drop` | `commerce.orders.count`, `commerce.revenue.total`, `runtime.freshness.age_seconds` |
| `stockout_risk` | `commerce.inventory.available_units`, `commerce.orders.count`, `runtime.freshness.age_seconds` |
| `data_stale` | `runtime.freshness.last_success_at`, `runtime.freshness.age_seconds`, `runtime.connector.status` |
| `fulfillment_backlog` | `commerce.fulfillment.pending_count`, `commerce.fulfillment.oldest_pending_age_hours` |
| `unanswered_conversations` | `support.conversations.unanswered_count`, `support.conversations.oldest_unanswered_age_minutes` |
| `spend_without_orders` | `ads.spend.total`, `commerce.orders.count`, `commerce.revenue.total`, freshness metrics for both sources |

## Required tests

- every metric emitted by enabled connector wrappers validates or is explicitly ignored;
- every case family references registered metrics;
- owner-facing report renderer rejects unknown metrics when strict mode is on;
- alias resolution is deterministic;
- currency/money metrics cannot be rendered without currency context;
- stale metrics suppress dependent cases or create `data_stale`.
