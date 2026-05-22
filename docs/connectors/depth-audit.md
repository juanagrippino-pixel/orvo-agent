# Connector depth audit — Hito 0 / ARTEMEA (Tiendanube + Meta Ads + WhatsApp)

## Scope

This audit is intentionally narrow: the first real ARTEMEA report for Hito 0, delivered at **08:00 Argentina time**, with a **dry/direct tone**, and **WhatsApp as the only customer-facing surface**.

It is based on the current codebase only. No live credentials were required or assumed.

Primary path in scope:

1. **Tiendanube** as the main commercial data source.
2. **Meta Ads** as the ad-spend context source.
3. **WhatsApp delivery** as the critical output path.

WhatsApp analytics as an input source is **not implemented** and can wait for a later milestone.

---

## Executive summary

The codebase already has a usable first-pass path for:

- pulling Tiendanube orders (and optional stock),
- pulling Meta Ads daily account insights,
- merging connector outputs,
- composing a WhatsApp-sized Spanish report,
- dispatching it once via an idempotent send path.

However, for **ARTEMEA Hito 0**, the current path is **not yet robust enough to trust unattended at 08:00**.

### Highest-impact findings

1. **Forced runs only use the first enabled connector**, not all enabled connectors.
   - `scripts/run_orvo_brain_reports.py` uses `_first_enabled_connector_type()` and `run_forced_report()` to select exactly one connector.
   - If ARTEMEA is configured with both **Tiendanube + Meta Ads**, a forced operational check can silently ignore one of them.

2. **Tiendanube metric keys do not line up with the report formatter’s ad section.**
   - Tiendanube emits `revenue_today` and `orders_today`.
   - The WhatsApp ads section in `app/brain/reporting.py` computes "ROAS estimado" from Tiendanube/MercadoLibre namespaced keys such as `revenue_today_tn`, `tiendanube.revenue_today`, etc.
   - Result: with **Tiendanube + Meta Ads only**, the composed report can show **ad spend with a false `ROAS estimado: 0.0x`** because Tiendanube revenue is invisible to that formatter path.

3. **Insight rules for ad-vs-sales are partially disconnected from Tiendanube’s current output.**
   - `app/brain/insights.py` falls back to generic `revenue_today` for one ROAS rule, which helps.
   - But the spend-without-sales and multi-channel rules expect `orders_today_tn`, `revenue_today_tn`, etc., which Tiendanube does not emit.
   - So some ad-related insights will never fire for the current Tiendanube+Meta pairing.

4. **No connector has retries, timeouts, backoff, or degraded-mode behavior yet.**
   - Tiendanube adapter: no timeout, retry, or body-shape guards.
   - Meta Ads adapter: no timeout, retry, rate-limit handling, or pagination handling.
   - WhatsApp send path: no timeout, no retry policy, no delivery receipt reconciliation.

5. **Resolved in code after this audit: the ARTEMEA bootstrap default now targets 08:00 Argentina.**
   - `app/brain/bootstrap.py` defaults to cron `0 8 * * *`.
   - Bootstrap tests now assert that 11:00 UTC fires as 08:00 in `America/Argentina/Buenos_Aires`.
   - The remaining launch step is verifying/updating the live SQLite schedule row after credentials are loaded.

6. **There are two separate WhatsApp send implementations in the repo.**
   - Brain reporting path uses `app/brain/delivery.py` (Graph API `v19.0`).
   - Main server chat/webhook path uses `server.py::_send()` / `app/graph.py` (Graph API `v21.0`).
   - This duplication is a future ops/debugging hotspot once real credentials arrive.

---

## End-to-end path as implemented today

### Scheduled path

Current scheduled Orvo Brain flow:

1. `app/brain/runner.py`
   - resolves due schedules,
   - collects enabled connector types,
   - calls `run_enabled_connectors_daily_report_pipeline(...)`.

2. `app/brain/pipeline.py`
   - builds one `DailyReport` per connector,
   - merges reports with `merge_daily_reports(...)`,
   - generates insights from merged metrics,
   - dispatches once through WhatsApp.

3. `app/brain/dispatch.py`
   - computes idempotency key,
   - composes Spanish report text,
   - truncates to WhatsApp budget,
   - sends via `WhatsAppDeliveryClient.send_text(...)`.

### Forced/manual path

Current forced runtime path:

1. `scripts/run_orvo_brain_reports.py --force`
2. `run_forced_report(...)`
3. selects **only the first enabled connector**
4. runs a single-connector pipeline
5. dispatches that result

For ARTEMEA Hito 0, this means scheduled execution is materially more capable than forced execution.

---

## Shared normalized data model

### `Evidence`

Used to cite source provenance for metrics and insights.

```python
Evidence(
  source: str,
  label: str,
  url: HttpUrl | None = None,
)
```

Current connector usage:

- Tiendanube: `source="tiendanube"`, labels like `"Tiendanube Artemea · orders"`
- Meta Ads: `source="meta_ads"`, label like `"Meta Ads Artemea · insights"`
- WhatsApp delivery does not add message-level evidence back into the report model.

### `Metric`

```python
Metric(
  key: str,
  label: str,
  value: float | int | str,
  unit: str | None,
  evidence: list[Evidence],
)
```

### `DailyReport`

```python
DailyReport(
  business_name: str,
  report_date: date,
  metrics: list[Metric],
  insights: list[Insight],
)
```

### Merge behavior

`merge_daily_reports(...)` in `app/brain/pipeline.py`:

- merges by `metric.key`,
- sums duplicate numeric values when units match,
- unions evidence by `(source, label)`,
- last-wins for non-numeric or unit-mismatched duplicates.

For Hito 0 this matters because:

- Tiendanube + Meta Ads mostly avoid key collision.
- The report/insight layers still depend heavily on **specific canonical key names**, not just semantic meaning.

---

## Connector audit — Tiendanube

### What it currently extracts

Implemented in `app/brain/adapters/tiendanube.py`.

#### Orders path

Calls:

- `GET https://api.tiendanube.com/v1/{store_id}/orders`

With params:

- `created_at_min`
- `created_at_max`
- `per_page=200`

Current logic:

- fetches all pages through `Link` header parsing,
- excludes orders where `status == "cancelled"`,
- sums `total` across remaining orders,
- counts remaining orders.

Current emitted metrics:

- `revenue_today` (`unit="ARS"`)
- `orders_today` (`unit="orders"`)

#### Optional stock path

Calls:

- `GET https://api.tiendanube.com/v1/{store_id}/products`

With params:

- `per_page=200`

Current logic:

- fetches all product pages,
- iterates all product variants,
- sums `variant.stock` when not `None`.

Current emitted metric:

- `stock_units` (`unit="units"`)

### Data shape as currently normalized

Typical current Tiendanube output:

```json
{
  "business_name": "Artemea",
  "report_date": "2026-05-19",
  "metrics": [
    {
      "key": "revenue_today",
      "label": "Ventas del día",
      "value": 8200.5,
      "unit": "ARS",
      "evidence": [{"source": "tiendanube", "label": "Tiendanube Artemea · orders"}]
    },
    {
      "key": "orders_today",
      "label": "Pedidos del día",
      "value": 2,
      "unit": "orders",
      "evidence": [{"source": "tiendanube", "label": "Tiendanube Artemea · orders"}]
    },
    {
      "key": "stock_units",
      "label": "Unidades en stock",
      "value": 18,
      "unit": "units",
      "evidence": [{"source": "tiendanube", "label": "Tiendanube Artemea · products"}]
    }
  ]
}
```

### Known edge cases visible in code/tests

1. **Only `cancelled` is excluded.**
   - Any other non-realized commercial status (depending on Tiendanube semantics) is still counted.
   - This is deliberately simple, but it may overstate real revenue/order count.

2. **Pagination exists, but only through `Link` parsing.**
   - `_parse_next_link(...)` is small and likely sufficient for the current happy path.
   - No guard exists for malformed or unexpected pagination headers.

3. **Date range is hard-coded to `-0300`.**
   - `_date_range_params(...)` formats timestamps as `YYYY-MM-DDTHH:MM:SS-0300`.
   - This fits Argentina today, but it is not tied to business config timezone or actual connector locale.

4. **Stock is total variant stock, not sellable stock.**
   - No filtering by publication status, hidden products, reserved stock, or fulfillment state.

5. **`float(o.get("total", 0))` and `int(v["stock"])` can raise if payloads are malformed.**
   - There is no per-row parse protection.
   - A single malformed order total or stock cell can fail the whole report.

6. **No body-shape validation before `resp.json()` contents are consumed.**
   - The adapter assumes orders/products return list-shaped JSON.

### Failure modes

Current explicit failures:

- `401/403` -> `TiendanubeAuthError`
- any other `>=400` -> `TiendanubeConnectionError`

Current implicit failures:

- network exceptions from `requests` bubble up unwrapped,
- invalid JSON shape can explode at iteration time,
- malformed monetary/stock values can raise `ValueError`/`TypeError`,
- large product catalogs can slow or time out at infrastructure level because no explicit timeout is set.

### Robustness gaps

1. **No explicit request timeout**
2. **No retry/backoff policy**
3. **No rate-limit handling**
4. **No response-body validation**
5. **No partial-success mode**
   - if stock fetch fails, the whole report currently fails instead of delivering orders-only.
6. **No provenance URL or raw request metadata in evidence**
7. **No local audit of raw counts/pages fetched**
8. **No metric namespaced for Tiendanube-specific downstream logic**
   - current output is generic (`revenue_today`, `orders_today`), which causes downstream disconnects for ads/cross-channel logic.

### What could be extracted later

Low-risk expansions after Hito 0:

- average order value,
- paid vs pending vs cancelled split,
- count by payment status,
- top SKUs / top products,
- units sold,
- refunds/chargebacks,
- conversion-relevant order attributes,
- stock by key SKU group rather than total store stock,
- products with zero/low stock only,
- compare vs yesterday / recent baseline from stored history.

### Latency and reliability concerns

Main latency risks:

- orders pagination on high-volume days,
- optional full product crawl for stock,
- lack of timeouts,
- inability to degrade from "orders + stock" to "orders only".

For Hito 0, **optional stock should be treated as non-critical** relative to the morning message. Orders/revenue are the core payload.

### Concrete hardening plan for Tiendanube

Before/around Hito 0:

1. **Add explicit timeout per request**.
2. **Add retry/backoff for transient failures** (5xx, network reset, timeout, 429 if applicable).
3. **Treat stock as optional degraded data**.
   - If orders succeed and stock fails, still send the report with a degraded note.
4. **Add safe numeric parsing**.
   - Bad rows should be counted/logged, not crash the entire run.
5. **Add response shape validation**.
6. **Emit Tiendanube-namespaced companion keys** or align downstream consumers.
   - Example: keep `revenue_today` but also emit `revenue_today_tn` and `orders_today_tn`, or update reporting/insights to understand generic Tiendanube-only outputs.
7. **Log page count + item count fetched** for every run.
8. **Keep `include_stock` off by default for first production send** unless stock is proven fast and reliable.

---

## Connector audit — Meta Ads

### What it currently extracts

Implemented in `app/brain/adapters/meta_ads.py`.

Calls:

- `GET https://graph.facebook.com/v19.0/act_{ad_account_id}/insights`

Params:

- `time_range={"since": "YYYY-MM-DD", "until": "YYYY-MM-DD"}`
- `fields=spend,impressions,clicks,purchase_roas`
- `level=account`
- `access_token=...`

Current emitted metrics:

- `ad_spend_today` (`unit="ARS"`)
- `ad_impressions_today` (`unit="impressions"`)
- `ad_clicks_today` (`unit="clicks"`)
- `ad_roas_today` (`unit="x"`)

### Current aggregation logic

- sums spend across rows,
- sums impressions across rows,
- sums clicks across rows,
- parses `purchase_roas` by summing all action types inside a row,
- then **averages ROAS across rows that reported ROAS**.

With `level="account"`, the API will often return a single row anyway, so this mostly behaves as a simple pass-through today.

### Data shape as currently normalized

Typical current Meta Ads output:

```json
{
  "business_name": "Artemea",
  "report_date": "2026-05-19",
  "metrics": [
    {
      "key": "ad_spend_today",
      "label": "Inversión publicitaria del día",
      "value": 1500.75,
      "unit": "ARS",
      "evidence": [{"source": "meta_ads", "label": "Meta Ads Artemea · insights"}]
    },
    {
      "key": "ad_impressions_today",
      "label": "Impresiones del día",
      "value": 20000,
      "unit": "impressions",
      "evidence": [{"source": "meta_ads", "label": "Meta Ads Artemea · insights"}]
    },
    {
      "key": "ad_clicks_today",
      "label": "Clicks del día",
      "value": 350,
      "unit": "clicks",
      "evidence": [{"source": "meta_ads", "label": "Meta Ads Artemea · insights"}]
    },
    {
      "key": "ad_roas_today",
      "label": "ROAS del día",
      "value": 3.2,
      "unit": "x",
      "evidence": [{"source": "meta_ads", "label": "Meta Ads Artemea · insights"}]
    }
  ]
}
```

### Known edge cases visible in code/tests

1. **Ad account ID prefix handling is covered.**
   - `act_` is added when missing, not doubled when already present.

2. **Empty data returns zeros, not failure.**
   - Good default for awareness/no-spend days.

3. **ROAS is not weighted.**
   - Multi-row ROAS is averaged, not recomputed from attributed revenue / spend.
   - For account-level output this usually matters less, but it is still semantically approximate.

4. **Currency is hard-coded to `ARS` in normalized metrics.**
   - The module docstring itself warns that Meta returns account billing currency.
   - If the account currency is not ARS, the normalized metric becomes misleading.

5. **Token is sent as a query param.**
   - Common in Meta examples, but it increases accidental logging exposure risk in upstream infra.

6. **No pagination/cursor handling.**
   - Fine for the current account-level daily query in many cases, but it is not future-proof if query shape changes.

### Failure modes

Current explicit failures:

- `401/403` -> `MetaAdsAuthError`
- `5xx` -> `MetaAdsAPIError`
- other `4xx` -> `MetaAdsConnectionError`

Current missing/implicit handling:

- no special handling for `429` rate limiting,
- no timeout,
- no retry/backoff,
- no validation of Graph error payloads beyond status code,
- network exceptions from `requests` are not wrapped into domain errors.

### Robustness gaps

1. **No timeout**
2. **No retry/backoff**
3. **No rate-limit strategy**
4. **No cursor/pagination handling**
5. **No response schema validation**
6. **No explicit currency verification against `BusinessConfig.currency`**
7. **No breakdown metrics that are useful for diagnosis**
8. **No degraded mode if Meta is unavailable but Tiendanube is healthy**

### What could be extracted later

High-value later additions:

- purchases / conversions count,
- attributed purchase value,
- CPC / CTR / CPM,
- campaign or ad set breakdown,
- spend by objective,
- creative-level outlier detection,
- yesterday / 7-day benchmark,
- spend pacing vs budget,
- per-campaign ROAS rather than only account aggregate.

### Latency and reliability concerns

Main risks:

- token expiry / revocation,
- 429 and 5xx behavior during early morning batch,
- possible Meta lag in finalizing late-night attributed metrics,
- lack of timeout/retry causing one transient Graph issue to kill the whole message.

For Hito 0, Meta Ads should be treated as **secondary context** behind Tiendanube revenue/orders.

### Concrete hardening plan for Meta Ads

Before/around Hito 0:

1. **Add explicit timeout**.
2. **Retry transient failures** (timeouts, connection resets, 5xx, 429 with backoff).
3. **Introduce degraded mode: Tiendanube-only send if Meta fails**.
4. **Validate/record account currency** before trusting ARS formatting.
5. **Wrap network exceptions into domain errors**.
6. **Add request/response audit metadata** (account id, date, row count, but never raw token).
7. **Decide canonical ROAS meaning**.
   - Either trust Meta’s own returned ROAS for display,
   - or compute one deterministic internal ROAS from revenue/spend and label it clearly.
8. **Align downstream metric keys/reporting logic for Tiendanube+Meta**.

---

## Delivery path audit — WhatsApp

### What it currently sends

Primary reporting send path is in `app/brain/delivery.py`.

Current payload type:

- plain text message only,
- Meta Cloud API `messages` endpoint,
- body shape:

```json
{
  "messaging_product": "whatsapp",
  "to": "+5491112345678",
  "type": "text",
  "text": {
    "preview_url": false,
    "body": "...report text..."
  }
}
```

### Current delivery data model

#### `DeliveryTarget`

```python
DeliveryTarget(
  phone: str,
  business_id: str,
)
```

Validation today:

- only non-empty strings,
- no real E.164 enforcement at this layer.

#### `DeliveryResult`

```python
DeliveryResult(
  success: bool,
  message_id: str | None,
  error: str | None,
)
```

#### Idempotency

`make_idempotency_key(...)` currently returns:

```text
<business_id>/<report_date>/<report_type>
```

Example:

```text
artemea/2026-05-19/daily
```

### Dispatch behavior today

`app/brain/dispatch.py` does the following:

1. compute idempotency key,
2. skip if already sent,
3. compose text with `compose_daily_report_text(...)`,
4. truncate to 1000 chars with `truncate_for_whatsapp(...)`,
5. send with `delivery_client.send_text(...)`,
6. mark idempotency only if send reports success.

### Known edge cases visible in code/tests

1. **Long reports are hard-truncated to 1000 chars.**
   - This is good for readability budget.
   - But truncation is blunt: it can cut sentences, bullets, or evidence context mid-structure.

2. **Success is treated as `HTTP 200` only.**
   - Probably fine for the Cloud API, but the client is strict.

3. **No send timeout is specified.**
   - `requests.Session.post(...)` is called without timeout.

4. **No phone-format validation beyond non-empty at delivery layer.**
   - `BusinessConfig.owner_phone` requires `+`, but `WhatsAppDeliveryClient.send_text(...)` itself does not enforce E.164.

5. **DeliveryTarget.business_id is not actually used in the payload.**
   - It exists for local structure only.

6. **No template-message mode.**
   - Only freeform text is supported.

7. **No delivery-status reconciliation.**
   - Send success means accepted by API, not confirmed delivered/read.

8. **No retry policy.**
   - A transient 500, timeout, or network flap becomes a failed send.

### Failure modes

Current handled failures:

- network exception -> `DeliveryResult(success=False, error=str(exc))`
- non-200 status -> `DeliveryResult(success=False, error="HTTP ...")`

Current missing handling:

- no retry for transient errors,
- no classification for 401 vs 429 vs 5xx,
- no persistence of raw Meta send error codes,
- no recovery after API accepted message but process dies before idempotency mark,
- no reconciliation if API call succeeded but response parsing failed.

### Robustness gaps

1. **No timeout**
2. **No retry/backoff**
3. **No durable outbox state**
4. **No delivery webhook integration for report sends**
5. **No message template fallback**
6. **No post-send observability**
7. **No structured degraded notice in report body**
8. **No shared WhatsApp transport abstraction across repo**
   - `server.py` and `app/graph.py` have separate send logic from `app/brain/delivery.py`.

### What could be sent later

Possible future output upgrades:

- template-based morning report,
- document/PDF attachment,
- compact summary + deep-link to full report,
- explicit degraded-mode footer,
- operator copy to an internal monitoring number,
- resend/fallback policy,
- localization variants if tone evolves.

### Latency and reliability concerns

This is the most operationally sensitive part of Hito 0.

Main concerns:

- no send timeout,
- no delivery confirmation loop,
- no retry queue,
- no automatic fallback if Meta rejects the message,
- idempotency is durable only when using SQLite runtime, not when using in-memory dry-run mode,
- transport implementation is duplicated elsewhere in repo.

### Concrete hardening plan for WhatsApp delivery

Before/around Hito 0:

1. **Add explicit POST timeout**.
2. **Retry transient send failures** with bounded backoff.
3. **Persist send attempt state** (queued / attempted / accepted / failed) separately from final idempotency key.
4. **Capture Graph error code/subcode** in structured logs.
5. **Add a degraded-mode suffix** when upstream connector data is partial.
6. **Keep report text deterministic and compact**; do not rely on manual operator cleanup.
7. **Unify or clearly separate the two WhatsApp send stacks** so debugging credentials is not ambiguous.
8. **Define operational rule for duplicate suppression vs safe resend** if crash occurs after API acceptance.

---

## Cross-connector integration findings that matter for ARTEMEA

### 1) Tiendanube + Meta Ads is not semantically aligned yet

The adapters individually work, but the merged output has downstream inconsistencies.

#### Current mismatch

- Tiendanube emits generic sales keys:
  - `revenue_today`
  - `orders_today`
- Meta emits ad keys:
  - `ad_spend_today`
  - `ad_impressions_today`
  - `ad_clicks_today`
  - `ad_roas_today`

#### Why that matters

`app/brain/reporting.py` ad section computes an estimated ROAS using only:

- `revenue_today_tn`
- `tiendanube.revenue_today`
- `tn_revenue_today`
- `revenue_today_ml`
- `mercadolibre.revenue_today`
- `ml_revenue_today`

So with the actual Hito 0 pair (**Tiendanube + Meta Ads**), the formatter can produce:

- correct ad spend,
- but wrong zero-revenue-derived ROAS text.

#### Impact

This is a **high-priority correctness bug for the first real customer-visible report**.

### 2) Multi-connector scheduled path is better than forced path

- scheduled runner merges all enabled connectors,
- forced runner uses only the first enabled connector.

Operational consequence:

- a manual morning check can disagree with the actual scheduled run behavior,
- or an operator may think Meta Ads is included when it is not.

### 3) Resolved: default schedule is 08:00 Argentina

This is not a connector bug, but it directly affects Hito 0 launch readiness.

### 4) Runtime env checks are out of sync with actual connector config shape

`app/brain/runtime_env.py` currently:

- includes Tiendanube env checks,
- does **not** include Meta Ads env checks,
- expects Tiendanube env names that do not match the connector-config-driven runtime path used by the pipeline.

That means environment readiness diagnostics are not yet a reliable source of truth for the ARTEMEA production path.

---

## Monitoring + degraded mode design for Hito 0 (design only, not implementation)

This section describes the minimum operational design needed before/around the first ARTEMEA production send.

## Monitoring goals

At 08:00 Argentina time, operators should be able to answer four questions quickly:

1. **Did the run start?**
2. **Which connectors succeeded, failed, or degraded?**
3. **Was a WhatsApp message accepted by Meta?**
4. **What exact data was omitted or partial?**

## Minimum event model

For each daily run, record structured events:

### Run-level

- `business_id`
- `report_date`
- `scheduled_at_local`
- `started_at`
- `finished_at`
- `final_status` (`sent`, `sent_degraded`, `failed`, `skipped_duplicate`)
- `idempotency_key`

### Connector-level

For each connector (`tiendanube`, `meta_ads`):

- `connector_status` (`ok`, `degraded`, `failed`, `skipped`)
- `request_count`
- `page_count`
- `row_count` / `item_count`
- `duration_ms`
- `error_class`
- `error_message_sanitized`
- `used_fallback_data` (bool)

### Delivery-level

- `delivery_status` (`accepted`, `failed`, `not_attempted`)
- `phone_id`
- `message_id`
- `status_code`
- `error_code`
- `duration_ms`
- `payload_chars`

## Degraded mode policy for Hito 0

### Principle

**Do not miss the morning send if Tiendanube core commerce data is healthy.**

### Proposed degraded-mode matrix

#### Case A — Tiendanube OK, Meta Ads failed

Action:

- **Send report anyway**.
- Include a short degraded note such as:
  - `Meta Ads no respondió a tiempo; envío ventas de Tiendanube solamente.`

Status:

- `sent_degraded`

This should be the default degraded path for Hito 0.

#### Case B — Tiendanube orders OK, Tiendanube stock failed

Action:

- **Send report anyway**.
- Omit stock metric and stock-based insights.
- Include note:
  - `Stock no disponible en este corte; ventas y pedidos sí confirmados.`

Status:

- `sent_degraded`

#### Case C — Tiendanube failed, Meta Ads OK

Action:

- **Do not send customer report** unless explicitly approved as an ads-only message format.
- For Hito 0, ads-only output is too weak and too easy to misread.

Status:

- `failed`

#### Case D — WhatsApp failed after report build succeeded

Action:

- mark report generation as successful but delivery failed,
- retain sanitized payload preview and connector outputs for operator resend,
- do not mark final idempotency until a send is confirmed accepted.

Status:

- `failed_delivery`

#### Case E — Both connectors failed

Action:

- no customer send,
- operator alert only.

## Suggested operator alert thresholds

Before or at launch, add alerts for:

- no run started by `08:02 ART`,
- Tiendanube failure,
- WhatsApp delivery failure,
- repeated Meta Ads failure for 2+ consecutive days,
- report length truncated on 3+ consecutive days,
- run duration above threshold (example: `>90s`).

## Suggested operator-facing morning checklist

1. Confirm schedule cron is `0 8 * * *` for ARTEMEA.
2. Run forced/dry validation using the same multi-connector path as scheduled runtime.
3. Confirm Tiendanube credential validity.
4. Confirm Meta Ads token validity and account currency.
5. Confirm WhatsApp credentials + phone ID.
6. Confirm last successful send has `message_id` persisted.
7. Confirm degraded note text is acceptable before first production use.

---

## Concrete pre-credential hotspots

These are the files most likely to matter immediately once real ARTEMEA credentials arrive.

### Highest-priority hotspots

1. `/root/orvo-agent/app/brain/reporting.py`
   - ad section expects TN/ML-specific revenue keys,
   - likely incorrect for current Tiendanube + Meta Ads pairing.

2. `/root/orvo-agent/app/brain/insights.py`
   - cross-channel/ad-spend rules expect namespaced TN/ML keys that current Tiendanube adapter does not emit.

3. `/root/orvo-agent/app/brain/adapters/tiendanube.py`
   - no timeout/retry/degraded path,
   - optional stock can currently kill the whole run.

4. `/root/orvo-agent/app/brain/adapters/meta_ads.py`
   - no timeout/retry/429 handling,
   - currency assumption is risky,
   - network exceptions are not normalized.

5. `/root/orvo-agent/app/brain/delivery.py`
   - no timeout/retry/outbox state,
   - only API-acceptance-level success.

6. `/root/orvo-agent/scripts/run_orvo_brain_reports.py`
   - forced path uses only first enabled connector,
   - easy operator trap during launch testing.

### Secondary hotspots

7. `/root/orvo-agent/app/brain/runner.py`
   - scheduled behavior is multi-connector and closer to desired Hito 0 execution.

8. `/root/orvo-agent/app/brain/runtime_env.py`
   - readiness checks drift from actual connector config requirements.

9. `/root/orvo-agent/app/brain/bootstrap.py`
   - default cron now `0 8 * * *` for the ARTEMEA bootstrap path.

10. `/root/orvo-agent/server.py`
    - separate preview endpoints are useful,
    - but there is also a separate WhatsApp send implementation here, which can confuse credential/debug ownership.

---

## Recommended Hito 0 hardening order

If only a few fixes fit before the first live send, do them in this order:

1. **Fix Tiendanube + Meta Ads semantic alignment in reporting/insights**.
2. **Make forced runs use the same multi-connector path as scheduled runs**.
3. **Verify the live ARTEMEA store uses the 08:00 Argentina schedule after credentials are loaded**.
4. **Add request timeouts + bounded retries for Tiendanube, Meta Ads, and WhatsApp**.
5. **Implement degraded send policy: Tiendanube-only send when Meta fails**.
6. **Add minimal structured monitoring for run/connector/delivery status**.
7. **Decide whether stock is in or out for first production morning send**.
8. **Unify or document the WhatsApp transport split across repo**.

---

## Bottom line

For ARTEMEA Hito 0, the codebase already contains the right skeleton, but the path is still **prototype-grade rather than morning-ops-grade**.

The biggest practical blockers are not missing APIs; they are:

- connector-output key alignment,
- degraded behavior,
- transport robustness,
- schedule correctness,
- forced-run behavior mismatch.

If those are tightened, Tiendanube-first + Meta Ads context + WhatsApp delivery is a realistic Hito 0 path without waiting for broader connector expansion.
