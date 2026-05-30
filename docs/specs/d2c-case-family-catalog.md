# D2C Case Family Catalog

Status: Draft contract
Date: 2026-05-24
Related: `docs/adr/0002-operational-case-native-issue-object.md`, `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`

## Purpose

This catalog defines the first ecommerce case families Orvo should support. A case family is allowed into owner-facing output only when it is deterministic, evidence-backed, deduped, auditable, and registered in the metric/semantic layer.

## Universal case requirements

Every `OperationalCase` produced from these families must include:

- `business_id`
- stable `case_type`
- deterministic `dedupe_key`
- `entity_scope`
- severity/priority computed by policy
- evidence snapshots
- source connector/run/artifact refs where available
- lifecycle transition history
- degraded-data caveats when relevant

Forbidden:

- LLM-created case existence.
- LLM-created priority.
- owner-facing numbers without metric/evidence refs.
- a new case for the same issue every day when the dedupe key is unchanged.
- hiding multiple distinct SKU/channel/order-flow issues under one broad case.

## Case families

### 1. `sales_drop`

**Buyer language:** Sales are materially below normal or expected range.

**Initial sources:** Tiendanube, CSV/manual onboarding, later MercadoLibre.

**Required metrics:**

- `commerce.orders.count` with daily time grain; legacy aliases: `commerce.orders.today`, `orders_today`
- `commerce.revenue.total` with daily time grain; legacy aliases: `commerce.revenue.today`, `revenue_today`
- baseline/comparison metric when available
- freshness/data-quality metric

**Detection policy:**

Open when orders/revenue fall below a configured threshold against baseline or expected minimum, and data freshness is sufficient. If baseline is missing, downgrade to informational or suppress unless an explicit configured threshold exists.

**Dedupe key shape:**

```text
<business_id>/sales_drop/channel/<channel_id>/commerce.revenue/daily
```

**Evidence:** current orders/revenue, comparison window, connector freshness, source labels.

**Initial actions:** check storefront/checkout, review traffic/ad changes, inspect payment/fulfillment blockers.

### 2. `stockout_risk`

**Buyer language:** A product that sells is at risk of running out.

**Initial sources:** Tiendanube product/inventory/order data.

**Required metrics:**

- SKU/product identifier
- stock units available
- recent units sold or sales velocity
- product/source freshness

**Detection policy:**

Open when stock is below threshold and recent sales velocity or strategic product flag indicates business relevance. Suppress if stock data is stale unless reporting a `data_stale` case.

**Dedupe key shape:**

```text
<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily
```

**Evidence:** stock snapshot, recent sales, product label, connector freshness.

**Initial actions:** pause promotion, restock, substitute product, confirm inventory sync.

### 3. `spend_without_orders`

**Buyer language:** Ads spent money but orders did not follow.

**Initial sources:** Meta Ads + Tiendanube.

**Required metrics:**

- ad spend today/window
- orders/revenue today/window
- channel/source freshness for both connectors
- configured minimum spend threshold

**Detection policy:**

Open only when ad spend passes a minimum threshold and commerce orders/revenue are below expected range. If either connector is stale, create/update `data_stale` instead of claiming spend/order mismatch.

**Dedupe key shape:**

```text
<business_id>/spend_without_orders/channel/meta_ads/ads.spend/daily
```

**Evidence:** spend, orders, revenue, source freshness, comparison window.

**Initial actions:** review campaigns, check checkout/storefront, inspect tracking freshness.

### 4. `data_stale`

**Buyer language:** Orvo cannot safely advise because a data source is stale or missing.

**Initial sources:** runtime/connector health for Tiendanube, Meta Ads, Sheets/CSV, WhatsApp/support.

**Required metrics/events:**

- connector type
- last successful sync/run timestamp
- failure class or stale duration
- affected surfaces/case families

**Detection policy:**

Open/update when required data for a scheduled/forced run is missing, stale, unauthorized, rate-limited, or malformed beyond policy. This case must narrow or suppress downstream advice.

**Dedupe key shape:**

```text
<business_id>/data_stale/connector/<connector_type>/runtime.freshness/daily
```

**Evidence:** connector run result, error class, stale duration, affected advice.

**Initial actions:** refresh token, check credentials, inspect API status, retry after rate limit, update config.

### 5. `fulfillment_backlog`

**Buyer language:** Orders are aging or stuck before delivery.

**Initial sources:** Tiendanube order/fulfillment data when available.

**Required metrics:**

- paid/unfulfilled order count
- oldest unfulfilled age
- fulfillment status grouping
- freshness

**Detection policy:**

Open when count or age exceeds configured threshold and source freshness is sufficient.

**Dedupe key shape:**

```text
<business_id>/fulfillment_backlog/channel/<channel_id>/commerce.fulfillment/daily
```

**Evidence:** count, oldest age, sample order refs redacted/safe, source freshness.

**Initial actions:** inspect pending orders, contact fulfillment provider, notify customer if needed.

### 6. `unanswered_conversations`

**Buyer language:** Sales/support chats are waiting too long.

**Initial sources:** WhatsApp/support connector when available.

**Required metrics:**

- unanswered conversation count
- age of oldest unanswered conversation
- channel/team scope
- freshness

**Detection policy:**

Open when unanswered count/age exceeds threshold and source freshness is sufficient.

**Dedupe key shape:**

```text
<business_id>/unanswered_conversations/channel/whatsapp/support.conversations/daily
```

**Evidence:** count, oldest age, source freshness, safe conversation refs.

**Initial actions:** reply to pending chats, route owner/operator, mark follow-up.

### 7. `channel_mix_shift`

**Current promotion state (2026-05-30): internal/deferred.** The shipped semantic registry does **not** include `channel_mix_shift` in `CASE_FAMILY_METRICS`, and the contract test intentionally covers only the currently registered owner-facing case families. Keep this family in the catalog as a post-pilot design target, but do not project it into owner-facing briefs until the metric-registry promotion packet lands.

**Buyer language:** Sales mix changed abnormally across storefront/marketplace/ad channels.

**Initial sources:** Tiendanube + MercadoLibre + ads once multi-channel confidence is high.

**Required metrics:**

- channel revenue/orders
- historical channel share
- freshness for all included sources

**Detection policy:**

Open when a channel share shift crosses configured threshold and all included source states are trustworthy. Suppress or degrade if a source is missing.

**Dedupe key shape:**

```text
<business_id>/channel_mix_shift/business/all_channels/commerce.revenue/daily
```

**Evidence:** current mix, comparison mix, connector freshness.

**Initial actions:** inspect channel health, review promotions, rebalance attention/spend.

**Promotion prerequisites specific to this family:**

- define canonical channel-share metrics or an approved deterministic composition over `commerce.orders.count` / `commerce.revenue.total` scoped by channel;
- add `channel_mix_shift` to `CASE_FAMILY_METRICS` only after those metrics are registered with `case_allowed=true`;
- add contract tests proving the family cannot emit owner-facing cases when any included channel source is stale or missing;
- add dedupe tests that keep broad all-channel alerts from hiding distinct channel-specific issues.

## Promotion gates

A case family can move from internal-only to owner-facing only after:

1. metric registry entries exist;
2. deterministic tests cover open/update/suppress paths;
3. dedupe tests cover repeated runs;
4. evidence/redaction tests pass;
5. degraded-state behavior is explicit;
6. WhatsApp/operator projection is reviewed for unsupported claims;
7. full suite remains green.
