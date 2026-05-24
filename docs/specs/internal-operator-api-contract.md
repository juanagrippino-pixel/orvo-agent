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

### Compile preview

```http
POST /internal/brain/businesses/{business_id}/runtime/compile-preview
```

Returns redacted `CompiledBusinessRuntime` summary and validation errors. Does not execute connectors.

### Connector readiness

```http
GET /internal/brain/businesses/{business_id}/connectors/readiness
```

Returns registry validation, secret-ref presence, and last health state.

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
GET /internal/brain/businesses/{business_id}/cases/{case_id}
POST /internal/brain/businesses/{business_id}/cases/{case_id}/actions
```

Actions must use registered action keys and append timeline events.

## Response envelope

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
- log mutating actions with actor ref;
- rate-limit force-run endpoints;
- require approval for external side effects;
- keep raw artifacts behind explicit privileged inspection.

## Required tests

- compile preview does not execute connectors;
- readiness endpoint redacts secret refs;
- dry run creates ledger entries but does not dispatch externally;
- run detail cannot cross business scope;
- case action rejects unknown action keys;
- responses include `redaction_applied=true`.
