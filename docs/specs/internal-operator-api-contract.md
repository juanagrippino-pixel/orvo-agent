# Internal Operator API Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `docs/specs/d2c-operator-surface-contract.md`, `docs/specs/tenant-secret-redaction-contract.md`

## Purpose

The internal operator API is the controlled surface for inspecting runtimes, connector readiness, run history, cases, and manual follow-up actions. It is not a public customer API in the first wave.

## Design rules

1. Internal APIs are projections over control-plane/runtime/case state.
2. Mutations must be tenant/business-scoped and audited.
3. Responses must be redacted and safe for operator inspection.
4. API endpoints must not become alternate sources of truth.
5. Existing public/preview report endpoints must remain compatible.

## Initial endpoints

### Operator session

```http
GET /internal/brain/businesses/{business_id}/operator-session
```

Returns the authenticated operator's redacted actor ref, normalized role,
permission flags, and redacted business-grant projection. Legacy callers without
`X-Orvo-Businesses` are marked `legacy_token_scoped=true`; explicit grants return
only safe business labels or `[REDACTED]`, never raw pasted header material.

### Compile preview

```http
POST /internal/brain/businesses/{business_id}/runtime/compile-preview
```

Returns redacted `CompiledBusinessRuntime` summary and validation errors. Does not execute connectors.

### Connector readiness

```http
GET /internal/brain/businesses/{business_id}/connectors/readiness
```

Returns registry validation, secret-ref presence, required scopes/capabilities,
and last health state. Last-health projections include connector timestamps,
derived `duration_ms` when a finished timestamp is available, and a compact
certification summary derived from the latest connector outcome metadata
(`event_certification` / `metric_certification`) with only `status` and
`issue_count` fields projected for operator-safe inspection.

### Force dry run

```http
POST /internal/brain/businesses/{business_id}/runs/dry-run
```

Executes with dry-run delivery policy. Must create run ledger record and artifacts.

### Force dispatch run

```http
POST /internal/brain/businesses/{business_id}/runs/force-dispatch
```

Allowed only after idempotency and approval rules are explicit. For early implementation, keep disabled or admin-only.

### Run history

```http
GET /internal/brain/businesses/{business_id}/runs
GET /internal/brain/businesses/{business_id}/runs/{run_id}
```

Returns run status, connector outcomes, artifacts, dispatch status, cases opened/updated.

### Cases

```http
GET /internal/brain/businesses/{business_id}/cases
GET /internal/brain/businesses/{business_id}/cases/export
GET /internal/brain/businesses/{business_id}/cases/{case_id}
GET /internal/brain/businesses/{business_id}/cases/facets
GET /internal/brain/businesses/{business_id}/case-query-fields
GET /internal/brain/businesses/{business_id}/case-query-fields?field={field}
POST /internal/brain/businesses/{business_id}/cases/{case_id}/actions
```

`/cases` accepts allowlisted `status`, `jql`, `limit`, and a read-only built-in
`view_id` selector that reuses the canonical case-view registry instead of
creating endpoint-local filters. `view_id`, `jql`, and `status` are mutually
exclusive; the API rejects unsupported query syntax or unknown views with
stable redacted errors and does not persist custom views or translate query
text into SQL.

`/cases/export` returns a read-only CSV projection of the same route-scoped
case queue. It accepts the same allowlisted `jql`, `status`, and `limit` guards
as `/cases`, plus a read-only built-in `view_id` selector that reuses the
canonical case-view registry rather than creating endpoint-local filters.
`view_id`, `jql`, and `status` are mutually exclusive; the API rejects
unsupported query syntax or unknown views with stable redacted errors and does
not persist custom views or translate query text into SQL. The export is a
projection over `OperationalCase`/WorkItem state, not an alternate source of
truth; raw response bodies are redacted at the HTTP boundary.

`status_category`, and `work_item_id`. JQL-lite and case facets are read-only,
route-scoped projections over the canonical WorkItem field registry; supported
fields include `project`, `issue_type`, `release_state`, `status_category`,
`assignee_ref`, `priority_bracket`, `source_connector`, and `degraded`. Case
facets may be scoped either by allowlisted `jql` or by a built-in read-only
`view_id`, but never both at once. The API must reject unsupported
fields/operators/values instead of translating user input into SQL or allowing
query text to own business scope.

`/case-query-fields` is a read-only metadata projection over the same canonical
WorkItem field registry. Without `field`, it returns allowlisted fields, value
types, operators, sortability, and facetability for UI/query builders. With
`field={field}`, it returns one allowlisted field definition or a stable redacted
`unsupported_jql_field` error; unsupported values never become source-of-truth
state or SQL fragments.

`/case-query-fields` is a read-only metadata projection over the same canonical
WorkItem field registry. Without `field`, it returns allowlisted fields, value
types, operators, sortability, and facetability for UI/query builders. With
`field={field}`, it returns one allowlisted field definition or a stable redacted
`unsupported_jql_field` error; unsupported values never become source-of-truth
state or SQL fragments.

`/case-query-fields` is a read-only metadata projection over the same canonical
WorkItem field registry. Without `field`, it returns allowlisted fields, value
types, operators, sortability, and facetability for UI/query builders. With
`field={field}`, it returns one allowlisted field definition or a stable redacted
`unsupported_jql_field` error; unsupported values never become source-of-truth
state or SQL fragments.

Actions must use registered action keys and append timeline events. Manual case-action
requests must include a safe `X-Idempotency-Key`; missing/blank keys fail before
mutation with a stable error envelope and redacted audit event. Valid keys are
reserved in the durable workflow action ledger before the case mutation, duplicate
completed requests replay the current case with `data.action.status = "skipped_duplicate"`,
and duplicate pending/failed keys are rejected with a safe `409` envelope.

### Operator audit events

```http
GET /internal/brain/businesses/{business_id}/operator-audit-events
GET /internal/brain/businesses/{business_id}/operator-audit-events?limit=50&retention_days=90
```

Admin-only projection over durable operator audit events. Returns redacted events
scoped to the route `business_id`; viewer/operator roles must receive a safe
`403` envelope. Exports default to a 90-day retention window and reject
`retention_days` values above the configured maximum instead of allowing
unbounded historical export.

## Response envelope

`request_id` mirrors `X-Request-ID` only when it is a safe operational
identifier; secret-shaped request IDs are collapsed to `[REDACTED]` in responses
and durable audit events.

```json
{
  "ok": true,
  "business_id": "artemea",
  "request_id": "req_...",
  "data": {},
  "warnings": [],
  "redaction_applied": true
}
```

Error envelope:

```json
{
  "ok": false,
  "business_id": "artemea",
  "request_id": "req_...",
  "error": {
    "code": "connector_unauthorized",
    "message": "Tiendanube credentials need refresh.",
    "safe_to_show_owner": true
  },
  "redaction_applied": true
}
```

## Authorization minimum before live use

Before exposing beyond local/dev:

- authenticate operator identity;
- scope access to business/tenant;
- enforce explicit `X-Orvo-Businesses` operator grants when present: comma-separated business IDs grant only those businesses, `*` grants all businesses, and an empty/present header fails closed while legacy callers without the header remain token-scoped during migration;
- audit failed internal bearer-token authentication attempts without persisting raw `Authorization` header values or token tails;
- log mutating actions with actor ref;
- rate-limit force-run endpoints;
- require approval for external side effects;
- keep raw artifacts behind explicit privileged inspection.

## Required tests

- compile preview does not execute connectors;
- readiness endpoint redacts secret refs;
- invalid internal bearer-token attempts create redacted operator audit events without persisting raw `Authorization` headers;
- internal envelopes and durable audit events redact secret-shaped `X-Request-ID` values;
- dry run creates ledger entries but does not dispatch externally;
- run detail cannot cross business scope;
- internal business endpoints deny operators whose explicit business grant header excludes the route business and audit the denial without persisting raw grant/header secrets;
- case action rejects unknown action keys;
- responses include `redaction_applied=true`.
