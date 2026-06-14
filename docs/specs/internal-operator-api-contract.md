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
GET /internal/brain/businesses/{business_id}/runs/{run_id}/delivery-statuses
GET /internal/brain/businesses/{business_id}/runs/dispatch-status-summary
```

Returns run status, connector outcomes, artifacts, dispatch status, cases opened/updated. Run list and dispatch-status summary support allowlisted projection filters for `dispatch_status` (`sent`, `failed`, `skipped_duplicate`, `skipped`, `queued`, `none`) and `dispatch_message_type` (`daily_report`, `owner_case_brief`, `unknown`) so operators can inspect primary report delivery separately from secondary owner-brief delivery without treating WhatsApp text as workflow state.
Run-history rows and run detail include a redacted `dispatch_summary` derived from
run-ledger dispatch outcomes so operators can distinguish the primary daily
report from the secondary owner-case-brief delivery without using WhatsApp/report
text as source of truth. The run-scoped `delivery-statuses` route correlates the
run ledger's safe dispatch `message_id` values with business-scoped WhatsApp
delivery-status events, redacts provider metadata, excludes unrelated message IDs
and other businesses, and remains a read-only observability projection.

### WhatsApp delivery status inspection

```http
GET /internal/brain/businesses/{business_id}/whatsapp/delivery-statuses
GET /internal/brain/whatsapp/delivery-statuses
```

The business-scoped route is the preferred operator surface. It returns only
delivery events whose durable `business_id` matches the route business, enforces
standard internal read permission plus explicit `X-Orvo-Businesses` grants,
supports the allowlisted `status` query filter (`sent`, `delivered`, `read`,
`failed`) within that tenant scope, rejects unsupported filter values with a
safe redacted `400` envelope, and redacts provider error metadata at the API
boundary.

The global route is for cross-business internal administration only. It uses the
legacy envelope `business_id = "whatsapp"`, but must require an admin-only
permission before returning unscoped recent events; viewer/operator callers
should use the business route instead.

### Cases

```http
GET /internal/brain/businesses/{business_id}/cases
GET /internal/brain/businesses/{business_id}/cases/recent?activity_type=updated
GET /internal/brain/businesses/{business_id}/cases/recently-opened
GET /internal/brain/businesses/{business_id}/cases/recently-acknowledged
GET /internal/brain/businesses/{business_id}/cases/recently-in-progress
GET /internal/brain/businesses/{business_id}/cases/recently-assigned
GET /internal/brain/businesses/{business_id}/cases/recently-commented
GET /internal/brain/businesses/{business_id}/cases/recently-updated
GET /internal/brain/businesses/{business_id}/cases/recently-reopened
GET /internal/brain/businesses/{business_id}/cases/recently-resolved
GET /internal/brain/businesses/{business_id}/cases/recently-dismissed
GET /internal/brain/businesses/{business_id}/cases/suggested-actions?action_key=confirm_stock
GET /internal/brain/businesses/{business_id}/cases/stagnation
GET /internal/brain/businesses/{business_id}/cases/stagnation/by-source-connector
GET /internal/brain/businesses/{business_id}/cases/stagnation/by-priority-bracket
GET /internal/brain/businesses/{business_id}/cases/{case_id}
GET /internal/brain/businesses/{business_id}/case-actions
GET /internal/brain/businesses/{business_id}/cases/facets
POST /internal/brain/businesses/{business_id}/cases/{case_id}/actions
GET /internal/brain/businesses/{business_id}/owner-case-brief/preview
```

Case queue and detail projections include WorkItem envelope fields derived from
`OperationalCase`, including `project_key`, `issue_type`, `release_state`,
`status_category`, and `work_item_id`. JQL-lite and case facets are read-only,
route-scoped projections over the canonical WorkItem field registry; supported
fields include `project`, `issue_type`, `release_state`, `status_category`,
`assignee_ref`, `priority_bracket`, `source_connector`, and `degraded`. The
API must reject unsupported fields/operators/values instead of translating user
input into SQL or allowing query text to own business scope.

Actions must use registered action keys and append timeline events. Manual case-action
requests must include a safe `X-Idempotency-Key`; missing/blank keys fail before
mutation with a stable error envelope and redacted audit event. Valid keys are
reserved in the durable workflow action ledger before the case mutation, duplicate
completed requests replay the current case with `data.action.status = "skipped_duplicate"`,
and duplicate pending/failed keys are rejected with a safe `409` envelope. The
`cases/recent` endpoint is the shared recent-activity query model for operator
surfaces: it accepts allowlisted `activity_type` values (`opened`,
`acknowledged`, `in_progress`, `assigned`, `commented`, `updated`, `reopened`,
`resolved`, `dismissed`), defaults to `updated`, and also accepts legacy
`recently-*` aliases such as `recently-opened` during migration. It returns a
normalized top-level envelope (`projection_type`, `activity_type`, `total`,
`count`, `limit`, `cases`) and keeps the underlying case rows as projections
over canonical `OperationalCase` state. Legacy `recently-*` endpoints remain
supported for compatibility, but new operator clients should prefer the shared
route instead of multiplying specialized HTTP paths. The
`recently-assigned` endpoint is a read-only projection over actionable cases with
`assigned_at`/`assignee_ref`; it does not mutate lifecycle state or treat
assignment as a source of truth. The `recently-commented` endpoint is a
read-only collaboration projection over canonical `operator_comment` timeline
events; rows include redacted title and entity scope for queue context, order by
latest comment timestamp, and do not mutate lifecycle state. The
`recently-updated` endpoint is a read-only operator activity projection over the
canonical case timeline; it orders by latest timeline event timestamp, includes
redacted latest-event summary/actor context, and does not infer workflow state
from API output. The
`suggested-actions` endpoint is a read-only,
actionable-case projection that filters `suggested_action_keys` through the
registered action catalog, suppresses invented keys, optionally narrows the
queue by a registered `action_key`, rejects unknown action-key filters with a
safe redacted `400` envelope, and redacts case titles and entity scope at the
API boundary. The `stagnation` endpoints are read-only,
business-scoped queue-health projections over canonical actionable cases; the
`by-source-connector` split groups each idle bucket by the deterministic source
connector derived from evidence snapshots so operators can spot connector-skewed
backlogs without treating API output as workflow state. The action catalog
endpoint is an authenticated, business-scoped projection of registered case
action keys; it must mark which catalog actions are actually enabled by the
current internal API (including `assign_owner` once the scoped assignment path is
wired) so clients do not infer executable capabilities from docs or owner-facing
copy. Enabled assignment entries must advertise required input fields without
exposing unredacted assignee values. The owner-case-brief preview endpoint is a
read-only WhatsApp projection over canonical actionable cases; it returns the
composed, redacted text plus projection metadata (`total_actionable_cases`,
`displayed_case_count`, `truncated`, displayed `case_ids`, displayed
`evidence_snapshot_ids` for each shown case, truthful freshness totals, and
registered `suggested_action_keys`/action catalog projections for the displayed
cases only). Unknown, wrong-family, duplicate, or secret-shaped action keys from
case metadata must be dropped at the service layer before the API envelope is
returned; when registered displayed action keys exist, brief text must render
those catalog-backed action labels instead of raw `recommended_action` metadata.
The endpoint must not dispatch, mutate cases, or treat brief text as state.

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
- run-scoped delivery-status projection is authenticated, grant-scoped, redacted, and only returns business-scoped events for dispatch message IDs from the selected run;
- WhatsApp delivery-status inspection prefers the business-scoped route, filters by durable event `business_id`, supports allowlisted tenant-scoped status filtering, rejects unsupported status filters without echoing caller input, rejects excluded business grants, and keeps the global route admin-only;
- internal business endpoints deny operators whose explicit business grant header excludes the route business and audit the denial without persisting raw grant/header secrets;
- case action rejects unknown action keys;
- case action catalog is authenticated, tenant-scoped, redacted, and marks disabled catalog actions as not executable;
- owner-case-brief preview is authenticated, tenant-scoped, read-only, excludes resolved/dismissed cases, redacts composed text and metadata, and reports truthful truncation counts;
- responses include `redaction_applied=true`.
