# Orvo Brain — Runtime Operations Guide

This document describes how to operate the Orvo Brain control plane in
development and production: bootstrapping the SQLite store, configuring
connectors (Google Sheets, CSV, Tiendanube), running dry-run reports, dispatching
real WhatsApp messages, and recovering from common failures.

> Scope: this is **operational** documentation. Internal design decisions live
> in `docs/plans/2026-05-19-orvo-brain-control-plane.md`.

---

## 1. Components at a glance

| Layer | Module | Purpose |
|-------|--------|---------|
| Config models | `app.brain.config` | `BusinessConfig`, `ConnectorConfig`, `ReportSchedule` (Pydantic v2) |
| Storage | `app.brain.storage` | `SQLiteConfigStore`, `SQLiteIdempotencyStore`, `init_schema` |
| Bootstrap | `app.brain.bootstrap` | `open_brain_sqlite_store`, `upsert_artemea_google_sheets_config` |
| Adapters | `app.brain.adapters.google_sheets` | Pull Sheet rows → `DailyReport` |
| Adapters | `app.brain.adapters.csv_file` | Read local CSV → `DailyReport` |
| Adapters | `app.brain.adapters.tiendanube` | Call Tiendanube API → `DailyReport` |
| Pipeline | `app.brain.pipeline` | Build report + dispatch end-to-end |
| Dispatch | `app.brain.dispatch` | Idempotent delivery via `WhatsAppDeliveryClient` |
| Runner | `app.brain.runner` | Execute every *due* schedule from config store |
| HTTP API | `server.py` | `POST /brain/reports/daily{,/google-sheets,/csv}` |
| CLI scripts | `scripts/` | Bootstrap, dry-run, scheduled run |

All metrics carry `Evidence` records so downstream summaries can cite their
source (`google_sheets`, `csv`, `tiendanube`, …).

---

## 2. Required environment variables

Only set what you actually need — adapters can be invoked independently.

### Core runtime

| Variable | Required for | Notes |
|----------|--------------|-------|
| `ORVO_BRAIN_DB_PATH` | All CLI scripts | SQLite path. Defaults to `orvo_brain.sqlite3` in CWD. |
| `ORVO_BRAIN_OWNER_PHONE` | `bootstrap_orvo_brain.py` | E.164 phone (must start with `+`). |

### WhatsApp delivery (real dispatch)

| Variable | Required | Notes |
|----------|----------|-------|
| `WHATSAPP_PHONE_ID` | yes | From Meta dashboard. |
| `WHATSAPP_TOKEN` | yes | Permanent or temporary access token. Treat as a secret. |

`WhatsAppDeliveryClient.from_env()` raises `EnvironmentError` if either is empty.

### Google Sheets (one of two auth modes)

**Service account (recommended for production):**

| Variable | Notes |
|----------|-------|
| `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE` | Path to service-account JSON. The sheet must be shared with the service-account email. |
| `GOOGLE_SHEETS_SCOPES` | Optional. Defaults to `https://www.googleapis.com/auth/spreadsheets.readonly`. |

**User OAuth (recommended for local dry-runs):**

| Variable | Notes |
|----------|-------|
| `GOOGLE_CLIENT_SECRET_FILE` | Path to `google_client_secret.json`. Defaults to `~/.hermes/google_client_secret.json`. |
| `GOOGLE_OAUTH_TOKEN_FILE` | Path to a refreshable user-token JSON. Defaults to `~/.hermes/google_token.json`. |

If neither set of credentials is found, `get_sheets_service()` raises
`ValueError` with the missing-vars message.

### Tiendanube

The Tiendanube adapter does **not** read env vars itself — callers pass
`store_id` and `access_token` directly. In practice the values come from your
business config (`ConnectorConfig.params`) or from these env vars wired in by
the caller:

| Variable | Notes |
|----------|-------|
| `TIENDANUBE_USER_ID` | Numeric Tiendanube store ID (e.g. `4828037`). |
| `TIENDANUBE_ACCESS_TOKEN` | OAuth bearer. Scope needed: `read_orders` (plus `read_products` for stock). |

> Do **not** commit real tokens. Examples in this repo use `[REDACTED]` /
> `tn_test_token`.

---

## 3. Bootstrap the SQLite database

The control-plane state lives in a single SQLite file. The schema is created
on first connection.

```bash
# Default: orvo_brain.sqlite3 in current working directory
python scripts/bootstrap_orvo_brain.py

# Custom path + values
ORVO_BRAIN_DB_PATH=/data/orvo_brain.sqlite3 \
ORVO_BRAIN_OWNER_PHONE=+5491149724933 \
python scripts/bootstrap_orvo_brain.py \
    --spreadsheet-id 1OO5fEVKraXKkiofZ0EtHpEOUPgHMxym-Y82VPwtRtG0 \
    --range-name 'Daily!A1:G1000'
```

This seeds Artemea's `BusinessConfig` + a `ReportSchedule` (daily, cron
`0 9 * * *`) using `upsert_artemea_google_sheets_config()`. The script prints
the persisted records as JSON to stdout.

To bootstrap from Python directly:

```python
from app.brain.bootstrap import open_brain_sqlite_store, upsert_artemea_google_sheets_config

conn, store = open_brain_sqlite_store("orvo_brain.sqlite3")
try:
    business, schedule = upsert_artemea_google_sheets_config(
        store,
        spreadsheet_id="...",
        range_name="Daily!A1:G1000",
        owner_phone="+54...",
    )
finally:
    conn.close()
```

---

## 4. Configure a Google Sheets connector

A `BusinessConfig` may carry one or more `ConnectorConfig` entries. For Google
Sheets the `params` block must contain `spreadsheet_id` and `range_name`.

A complete example lives at
[`examples/google_sheets_business_config.json`](../examples/google_sheets_business_config.json).
Minimal shape:

```json
{
  "business_id": "artemea",
  "business_name": "Artemea",
  "owner_phone": "+5491149724933",
  "timezone": "America/Argentina/Buenos_Aires",
  "currency": "ARS",
  "connectors": [
    {
      "connector_id": "artemea-google-sheets",
      "connector_type": "google_sheets",
      "label": "Orvo Brain - Artemea Control Plane",
      "params": {
        "spreadsheet_id": "1OO5fEVKraXKkiofZ0EtHpEOUPgHMxym-Y82VPwtRtG0",
        "range_name": "Daily!A1:G1000"
      },
      "enabled": true
    }
  ]
}
```

Load it into the store:

```python
import json
from app.brain.config import BusinessConfig
from app.brain.bootstrap import open_brain_sqlite_store

conn, store = open_brain_sqlite_store("orvo_brain.sqlite3")
business = BusinessConfig.model_validate_json(
    open("examples/google_sheets_business_config.json").read()
)
store.save_business_config(business)
conn.close()
```

### Sheet column layout

`google_sheets.normalize_header` accepts these aliases (case-insensitive,
accents OK):

| Canonical key | Accepted headers |
|---------------|------------------|
| `date` | `fecha`, `date` |
| `revenue` | `ventas`, `venta`, `facturacion`, `facturación`, `revenue` |
| `orders` | `pedidos`, `ordenes`, `órdenes`, `orders` |
| `stock_units` | `stock`, `stock_units`, `unidades_stock` |
| `unanswered_conversations` | `conversaciones_sin_responder`, `sin_responder`, `mensajes_pendientes` |
| `ad_spend` | `gasto_ads`, `ads`, `meta_ads`, `ad_spend` |

A `date` column is mandatory. Other columns are optional — a metric is only
emitted when at least one row provides a value for it.

---

## 5. Configure a Tiendanube connector

Example: [`examples/tiendanube_business_config.json`](../examples/tiendanube_business_config.json).

```json
{
  "business_id": "demo-shop",
  "business_name": "Demo Shop",
  "owner_phone": "+5491150380097",
  "timezone": "America/Argentina/Buenos_Aires",
  "currency": "ARS",
  "connectors": [
    {
      "connector_id": "demo-tiendanube",
      "connector_type": "tiendanube",
      "label": "Tiendanube - Demo Shop",
      "params": {
        "store_id": "4828037",
        "access_token": "[REDACTED]",
        "include_stock": false
      },
      "enabled": true
    }
  ]
}
```

The adapter is called directly:

```python
from datetime import date
from app.brain.adapters.tiendanube import build_daily_report_from_tiendanube

report = build_daily_report_from_tiendanube(
    business_name="Demo Shop",
    store_id="4828037",
    access_token="tn_test_token",
    report_date=date(2026, 5, 19),
    include_stock=False,
)
```

Tiendanube is wired in the runtime layer:

- HTTP preview endpoint: `POST /brain/reports/daily/tiendanube` returns the composed text and report payload without dispatching.
- Pipeline: `run_tiendanube_daily_report_pipeline(...)` builds the report and dispatches through the idempotent dispatcher.
- Scheduled runner: `run_due_daily_reports(...)` chooses the Tiendanube pipeline when a business config has an enabled `tiendanube` connector.

HTTP preview example:

```bash
curl -s -X POST http://localhost:5000/brain/reports/daily/tiendanube \
  -H 'Content-Type: application/json' \
  -d '{
    "business_name": "Demo Shop",
    "store_id": "4828037",
    "access_token": "tn_test_token",
    "report_date": "2026-05-19",
    "include_stock": false
  }'
```

---

## 6. Configure a Meta Ads connector

Example: [`examples/meta_ads_business_config.json`](../examples/meta_ads_business_config.json).

`connector_type` must be `meta_ads`. Required connector params:

- `ad_account_id`: Meta ad account ID, with or without the `act_` prefix.
- `access_token`: Meta Marketing API user/system-user access token.

Use placeholders in docs and examples; never commit a real ad account token.

```json
{
  "business_id": "demo-meta",
  "business_name": "Demo Meta",
  "owner_phone": "+5491150380097",
  "timezone": "America/Argentina/Buenos_Aires",
  "currency": "ARS",
  "connectors": [
    {
      "connector_id": "demo-meta-ads",
      "connector_type": "meta_ads",
      "label": "Meta Ads - Demo Meta",
      "params": {
        "ad_account_id": "act_1234567890",
        "access_token": "[REDACTED]"
      },
      "enabled": true
    }
  ]
}
```

Meta Ads is wired in the runtime layer:

- HTTP preview endpoint: `POST /brain/reports/daily/meta-ads` returns composed text and report payload without dispatching.
- Pipeline: `run_meta_ads_daily_report_pipeline(...)` builds the report and dispatches through the idempotent dispatcher.
- Scheduled runner: `run_due_daily_reports(...)` chooses the Meta Ads pipeline when a business config has an enabled `meta_ads` connector.
- Forced runner: `scripts/run_orvo_brain_reports.py --force` selects it for businesses whose first enabled connector is `meta_ads`.

HTTP preview example:

```bash
curl -s -X POST http://localhost:5000/brain/reports/daily/meta-ads \
  -H 'Content-Type: application/json' \
  -d '{
    "business_name": "Demo Meta",
    "ad_account_id": "act_1234567890",
    "access_token": "meta_test_token",
    "report_date": "2026-05-19"
  }'
```

---

## 7. Configure a CSV connector


The CSV adapter is the simplest path — useful for back-fills or when a client
exports their POS data daily.

Example: [`examples/artemea_daily.csv`](../examples/artemea_daily.csv).

```csv
fecha,ventas,pedidos,stock_units,conversaciones_sin_responder,gasto_ads
2026-05-12,180000,11,420,1,12000
2026-05-13,165000,9,415,2,11500
2026-05-14,195000,12,408,0,13000
2026-05-15,210000,14,400,1,12500
2026-05-16,230000,16,388,0,14000
2026-05-17,205000,13,376,1,12000
2026-05-18,220000,15,360,0,13500
2026-05-19,260000,18,342,0,15000
```

Header parsing is the same as Google Sheets (aliases + accent folding). The
last row (`report_date`) is the row used to populate today's metrics; the
seven preceding rows become the rolling baseline.

Drive it via HTTP:

```bash
curl -s -X POST http://localhost:5000/brain/reports/daily/csv \
  -H 'Content-Type: application/json' \
  -d '{
    "business_name": "Artemea",
    "report_date": "2026-05-19",
    "csv_path": "examples/artemea_daily.csv"
  }'
```

Or from Python:

```python
from datetime import date
from app.brain.adapters.csv_file import build_daily_report_from_csv_file

report = build_daily_report_from_csv_file(
    business_name="Artemea",
    report_date=date(2026, 5, 19),
    csv_path="examples/artemea_daily.csv",
)
```

---

## 8. Run the one-command sales demo

Use the seeded demo when selling Orvo Brain to Argentine/LatAm PyMEs. It needs
no database, no API keys, and prints WhatsApp-ready examples for a normal day,
a stock crisis, and a multi-channel Tiendanube + MercadoLibre + Meta Ads shop.

```bash
python scripts/demo_report.py

# Focus the strongest urgency demo for a prospect call
python scripts/demo_report.py --scenario pyme-stock-crisis

# Save copy/pasteable WhatsApp samples + JSON payloads
python scripts/demo_report.py --save-dir examples/demo_output/
```

The ads block uses available sales metrics for estimated ROAS, so single-channel
demos show a prospect-friendly value (for example `ARS 95.000 / ARS 25.000 =
3.8x`) instead of a misleading zero when channel-specific revenue is absent.

---

## 9. Run a dry-run report

A dry-run builds the report and composes the WhatsApp text *without* sending
anything to Meta — safe to run repeatedly in CI or on a laptop.

### Dry-run via the runner script

```bash
python scripts/run_orvo_brain_reports.py \
    --db orvo_brain.sqlite3 \
    --business-id artemea \
    --report-date 2026-05-19 \
    --dry-run --force
```

`--dry-run` substitutes a no-op delivery client and an in-memory idempotency
store, so re-running it never marks the day as "sent".

### Dry-run against a live Sheet (OAuth)

`scripts/run_orvo_brain_sheet_dry_run.py` reads OAuth credentials from
`~/.hermes/google_client_secret.json` + `~/.hermes/google_token.json` and
prints the composed text + raw metrics. Useful for sanity-checking real
production data without touching WhatsApp.

### Dry-run via HTTP

```bash
curl -s -X POST http://localhost:5000/brain/reports/daily/google-sheets \
  -H 'Content-Type: application/json' \
  -d '{
    "business_name": "Artemea",
    "report_date": "2026-05-19",
    "spreadsheet_id": "1OO5fEVKraXKkiofZ0EtHpEOUPgHMxym-Y82VPwtRtG0",
    "range_name": "Daily!A1:G1000"
  }'
```

This endpoint never dispatches — it only returns the composed text and the
report payload.

---

## 10. Run a real WhatsApp dispatch

```bash
export WHATSAPP_PHONE_ID="..."
export WHATSAPP_TOKEN="..."

python scripts/run_orvo_brain_reports.py \
    --db orvo_brain.sqlite3 \
    --business-id artemea \
    --report-date 2026-05-19 \
    --force
```

When `--dry-run` is **omitted** the script:

1. Builds the daily report from the configured connector.
2. Computes the idempotency key `<business_id>/<date>/daily`.
3. Skips if already marked, else POSTs to Meta and stores the key in the
   `idempotency_keys` SQLite table.

### Scheduled execution (cron / scheduler)

Drop the script in cron / a Railway scheduled job. Without `--force` the
script consults `ReportSchedule.cron_expression` and only runs schedules
whose UTC time matches. Typical cron entry:

```cron
*/5 * * * * cd /app && python scripts/run_orvo_brain_reports.py >> /var/log/orvo_brain.log 2>&1
```

The runner is safe to invoke every five minutes — `due_schedules()` filters
to schedules whose `next_daily_run()` falls inside the polling window, and
idempotency keys ensure no duplicate messages.

---

## 11. Troubleshooting

### 11.1 Google OAuth expired or revoked

Symptoms:

- `get_sheets_service()` raises `ValueError("Google Sheets credentials are required …")`.
- Sheets API calls return `401`.
- Dry-run script fails inside `load_credentials()` reading
  `~/.hermes/google_token.json`.

Fix:

1. Confirm both files exist:
   - `~/.hermes/google_client_secret.json`
   - `~/.hermes/google_token.json`
2. If the access token expired and there is a `refresh_token` in
   `google_token.json`, regenerate by re-running the OAuth flow (any
   one-off script that calls `InstalledAppFlow.from_client_secrets_file(...)`
   and `flow.run_local_server(...)` then writes the new token).
3. If the user revoked access in Google Account → Security → Third-party
   access, redo the OAuth flow from scratch.
4. For production prefer a **service account** + share the sheet with the
   service-account email — refresh tokens cannot be revoked behind your
   back. Point `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE` at the JSON.

### 11.2 Tiendanube returns 401 / 403

Symptoms:

- `TiendanubeAuthError: Tiendanube auth failed: HTTP 401`
- or HTTP 403 on the orders endpoint.

Fix:

1. Verify the request header uses **`Authentication: bearer <token>`** —
   note the spelling (`Authentication`, not `Authorization`) and the
   lower-case `bearer`. This is encoded in `_headers()`; if you have
   patched it, restore it.
2. Verify the OAuth token has the `read_orders` scope (and `read_products`
   if you set `include_stock=True`).
3. Verify the `store_id` matches the token — Tiendanube tokens are
   per-store. A token for store `4828037` cannot read store `1234567`.
4. Regenerate the token from the Tiendanube partner dashboard and update
   `ConnectorConfig.params.access_token`.

### 11.3 WhatsApp credentials missing or wrong

Symptoms:

- `EnvironmentError: Missing required environment variable(s): WHATSAPP_PHONE_ID, WHATSAPP_TOKEN`
- or `DeliveryResult(success=False, error="HTTP 401: …")` from
  `send_text()`.

Fix:

1. Set `WHATSAPP_PHONE_ID` and `WHATSAPP_TOKEN` in the runtime environment
   (Railway variables, `.env`, …).
2. Confirm the phone ID and token belong to the **same WhatsApp Business
   Account**.
3. If the token is temporary (24h), replace with a permanent system-user
   token before relying on the scheduled runner.
4. For development, use `--dry-run` on `run_orvo_brain_reports.py` to skip
   the WhatsApp call entirely.

### 11.4 Duplicate dispatch / idempotency

Symptoms:

- The same report was delivered twice in a single day.
- `dispatch.status == "skipped_duplicate"` and you expected a real send.

How dedup works:

- `make_idempotency_key(business_id, report_date, "daily")` →
  `"<business_id>/<YYYY-MM-DD>/daily"`.
- `SQLiteIdempotencyStore` persists the key in the `idempotency_keys`
  table.

Recovery / behaviour rules:

1. **Want to re-send today's report** (e.g. after fixing a bad source row):
   delete that key — it is the *only* gate.
   ```sql
   DELETE FROM idempotency_keys WHERE key = 'artemea/2026-05-19/daily';
   ```
2. **Two pods sharing the same SQLite file**: SQLite locks the file, so
   double-dispatch is structurally prevented. Make sure both pods share
   the same `ORVO_BRAIN_DB_PATH` (a Railway Volume mount, not a local
   ephemeral disk).
3. **Two separate SQLite files**: each file has its own idempotency state,
   so the same `(business, date)` can be sent twice. Consolidate onto a
   single shared store before enabling the runner cron.
4. **Dry-runs do not mark keys**: `--dry-run` uses
   `InMemoryIdempotencyStore`, so a dry-run will never block a later real
   send.

---

## 12. Examples bundled with this repo

| File | Purpose |
|------|---------|
| [`examples/artemea_daily.csv`](../examples/artemea_daily.csv) | 8-day Artemea sample (works with the CSV adapter and `/brain/reports/daily/csv`). |
| [`examples/google_sheets_business_config.json`](../examples/google_sheets_business_config.json) | Full `BusinessConfig` JSON for a Google Sheets connector. |
| [`examples/tiendanube_business_config.json`](../examples/tiendanube_business_config.json) | Full `BusinessConfig` JSON for a Tiendanube connector. Uses `[REDACTED]` in place of a real token. |
| [`examples/meta_ads_business_config.json`](../examples/meta_ads_business_config.json) | Full `BusinessConfig` JSON for a Meta Ads connector. Uses `[REDACTED]` in place of a real token. |
| `scripts/demo_report.py` | One-command sales demo that prints WhatsApp samples from deterministic PyME scenarios. |

All examples are validated by
[`tests/test_runtime_docs_examples.py`](../tests/test_runtime_docs_examples.py):

- JSON files parse as `BusinessConfig`.
- The CSV file is readable by `build_daily_report_from_csv_file` and yields
  at least one cited metric.

> **Never commit real access tokens, phone numbers, or service-account
> private keys.** Replace with `[REDACTED]` or `tn_test_token` placeholders
> when sharing.
