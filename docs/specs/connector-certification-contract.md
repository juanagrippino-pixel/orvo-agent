# Connector certification contract

Status: draft for the Orvo developer platform lane.

This contract defines the safe metadata that connector owners expose to self-service provisioning, gateway planning, and runtime compilation. It intentionally describes *references* and policy envelopes, not raw credentials or channel-specific transport behavior.

## Rules

1. `ConnectorSpec` remains the source of truth for connector metadata.
2. Certification output may include secret-reference names such as `access_token`, `consumer_key`, or `consumer_secret`; it must never include raw secret values, OAuth codes, access tokens, refresh tokens, bearer tokens, or `.env` contents.
3. Required scopes must come from `ConnectorScopeMetadata.required`.
4. Runtime modes must come from executor metadata. The `sample` connector remains limited to `preview` and `operator_triggered` because it has no scheduled daily-report executor.
5. Health states must use the shared connector health taxonomy: `ok`, `degraded`, `stale`, `unauthorized`, `rate_limited`, `failed`.
6. Rate-limit metadata is planning guidance for connector execution, not a global gateway enforcement point. Gateway route policies live in `app.brain.gateway_contracts`.
7. Connector capabilities must map to existing adapter/report-factory paths registered in the connector registry.

## Certification snapshot

Generated from `render_connector_certification_markdown(default_connector_registry().specs())`.

# Connector certification snapshot

Status: generated from `app.brain.connector_registry.default_connector_registry()`.

This snapshot is the developer-facing connector onboarding reference. Keep connector metadata in `ConnectorSpec` first, then refresh this document from the renderer.

| Connector type | Display name | Status | Owner | Version | Capabilities | Scopes | Secret refs | Rate limit | Health states | Runtime modes | Config fields | Metric families |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `csv` | CSV file | active | orvo-brain | phase-a | daily_report, file_import | none | none | retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, forced, scheduled, operator_triggered | required: csv_path; optional: source_label | commerce.orders, commerce.revenue, commerce.inventory, runtime.freshness, runtime.data_quality |
| `google_sheets` | Google Sheets | active | orvo-brain | phase-a | daily_report, sheet_import | spreadsheets.readonly | none | retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, forced, scheduled, operator_triggered | spreadsheet_id, range_name | commerce.orders, commerce.revenue, commerce.inventory, runtime.freshness, runtime.data_quality |
| `mercadolibre` | MercadoLibre | active | orvo-brain | phase-a | daily_report, commerce_metrics | orders.read, items.read | access_token | 60 rpm / retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, forced, scheduled, operator_triggered | required: seller_id; optional: site_id, source_label | commerce.orders, commerce.revenue, commerce.average_order_value, runtime.freshness, runtime.data_quality |
| `meta_ads` | Meta Ads | active | orvo-brain | phase-a | daily_report, ad_metrics | ads_read, read_insights | access_token | 200 rpm / retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, forced, scheduled, operator_triggered | required: ad_account_id; optional: source_label | ads.spend, ads.delivery, ads.roas, runtime.freshness, runtime.data_quality |
| `sample` | Manual sample payload | active | orvo-brain | phase-a | manual_payload | none | none | retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, operator_triggered | none | manual.payload, runtime.freshness, runtime.data_quality |
| `tiendanube` | Tiendanube | active | orvo-brain | phase-a | daily_report, commerce_metrics, inventory_metrics | orders.read, products.read | access_token | 120 rpm / retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, forced, scheduled, operator_triggered | required: store_id; optional: include_stock | commerce.orders, commerce.revenue, commerce.inventory, runtime.freshness, runtime.data_quality |
| `woocommerce` | WooCommerce | active | orvo-brain | phase-a | daily_report, commerce_metrics, inventory_metrics | orders.read, products.read | consumer_key, consumer_secret | 120 rpm / retry adapter_default | ok, degraded, stale, unauthorized, rate_limited, failed | preview, forced, scheduled, operator_triggered | required: store_url; optional: include_stock, source_label | commerce.orders, commerce.revenue, commerce.inventory, runtime.freshness, runtime.data_quality |

## Certification checks

The companion contract tests verify:

- every registered connector appears in the certification markdown;
- secret-reference names are present only as safe handles;
- raw fixture-like secret values are absent;
- rendered markdown is deterministic for the default catalog;
- Tiendanube exposes the expected commerce scopes, rate-limit plan, health taxonomy, and runtime modes.
