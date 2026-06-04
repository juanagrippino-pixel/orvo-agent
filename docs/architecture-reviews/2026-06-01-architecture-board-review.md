# Architecture Review Board — Orvo D2C Control Plane

Date: 2026-06-01  
Repository: `/root/orvo-agent`  
Base reviewed: `feat/orvo-brain-control-plane` @ `4ce7df1` (`codex: expose internal operator session`)  
Mode: read-only architecture review; no code changes, pushes, merges, deploys, or cron changes.

## Executive verdict

Orvo is moving in the right direction for a Jira/Atlassian-like operations control plane: the current code has a canonical `OperationalCase`, evidence snapshots, lifecycle transitions, timeline events, JQL-lite operator views, a connector registry, a metric registry, compiled runtime artifacts, action-key cataloging, redaction, and initial internal RBAC.

However, the current HEAD is **not yet Atlassian-grade as a sellable control plane**. It is closer to a deterministic case queue with operator projections than a full work-management platform. The most important gaps are:

1. **Work management model is not yet project/issue/workflow-scheme based.** `OperationalCase` is strong, but there is no separate `WorkItem` abstraction, project container, issue-type registry, workflow scheme, or explicit status category model.
2. **Semantic registry is advisory in several runtime paths.** Metrics are defined centrally, but adapters and CSV/sheet ingestion can still emit literal/arbitrary keys; pipeline merge behavior can create drift without registry-owned aggregation policy.
3. **Audit/RBAC is incomplete on current HEAD.** Current internal roles exist, but durable operator audit is absent on HEAD; at least one internal route (`/internal/brain/whatsapp/delivery-statuses`) has bearer-token auth but no role permission check. The `codex/trust-admin-security` branch adds important pieces but should be rebased and tightened before merge.
4. **Workflow automation remains projection-only.** This is the right safety posture, but there is no durable approval object, workflow action ledger, executor boundary, or idempotency enforcement for manual case mutations.
5. **Connector platform needs one more consolidation pass.** The registry and compiled runtime are aligned with the platform direction, but current execution still carries legacy inline secret resolution and adapter-specific service bindings at the pipeline boundary.

Recommended integration posture: **merge low-risk operator/query/test/platform-hardening branches after rebase and tests; treat Trust/Admin/Security as a priority hardening branch but not cleanly merge-ready as-is; park broader edge/developer-platform expansion until the D2C wedge contracts are tighter.**

---

## 1. OperationalCase / WorkItem alignment with Atlassian patterns

### What aligns

Current code has several strong Atlassian-like foundations:

- `app/brain/operational_cases.py`
  - Canonical `OperationalCase` model with deterministic `case_id`, `business_id`, `case_type`, `dedupe_key`, severity, priority score, owner/assignee fields, lifecycle timestamps, evidence refs, artifact refs, evidence snapshots, and timeline.
  - Lifecycle invariants enforce timestamp consistency for resolved/dismissed cases and assignee consistency.
  - Store protocol separates case persistence/mutation from operator/API projection.
  - Timelines provide a local issue-history equivalent.
- `app/brain/operator_views.py`
  - JQL-lite parser and built-in views (`status`, `case_type`, `severity`, `source_connector`, `degraded`, ordering, limits).
  - Business scope is enforced outside JQL; attempts to query `business_id` are rejected.
- `app/brain/operator_api.py`
  - Queue, detail, summary, aging, stagnation, throughput, latency, and dashboard projections are all derived from canonical cases rather than WhatsApp/report copy.
- `app/brain/action_catalog.py`
  - Action keys are centralized and projected, with `api_enabled`, approval-required flags, mode, status effect, side effect, and input fields.

### Architectural gaps

The current model still falls short of the Atlassian/Jira pattern in several strategic areas:

- **No `Project` / workspace container.** `business_id` acts as tenant scope, but there is no project key, project metadata, project-level workflow scheme, project-level issue-type scheme, or project-scoped numbering (`D2C-123` style). This limits multi-team operator UX and makes future portfolio/workspace concepts harder.
- **No distinct `WorkItem` abstraction.** Code treats `OperationalCase` as the issue/work-item. That is acceptable for the wedge, but it couples deterministic detection cases to future manually-created work, approvals, tasks, incidents, or connector remediation tickets.
- **Issue type is implicit.** `case_type` is a domain family (`stockout_risk`, `sales_drop`, etc.), not an issue type registry with fields, screens, workflow scheme, SLA policy, and actions. This is fine for first cases but not yet Jira-like.
- **Status categories are not explicit.** Statuses (`open`, `acknowledged`, `in_progress`, `resolved`, `dismissed`) exist, but there is no category map like `to_do`, `in_progress`, `done`, nor a status registry with terminal flags and allowed transitions.
- **Workflow is hardcoded.** `apply_case_action()` maps action keys directly to statuses. Store transition rules enforce safety, but there is no workflow scheme per case family/project/tenant.
- **JQL-lite is useful but not yet platform query.** It is safe and scoped, but it is in-memory/projection oriented and does not yet behave like a canonical indexed query language over all work item fields.

### Recommendation

Introduce a thin platform layer without disrupting D2C cases:

- `Project` / `ControlPlaneProject`: `project_id`, `business_id`, `project_key`, `name`, `issue_type_scheme_id`, `workflow_scheme_id`.
- `IssueType` registry: start by mapping D2C `case_type` families into issue types or subtypes.
- `Status` registry: `status`, `status_category`, `terminal`, `owner_facing`, `allowed_from`.
- `WorkItem` envelope: generic fields (`work_item_id`, `project_key`, `issue_type`, `status`, `status_category`, `priority`, `assignee`, `created_at`, `updated_at`) with `OperationalCase` as a deterministic subtype/source.
- Keep `OperationalCase` as the evidence-backed source for detected cases, but project it into a Jira-like `WorkItem` view.

Verdict for this area: **needs work before calling the product Atlassian/Jira-like**, but the current case engine is a solid wedge foundation.

---

## 2. Semantic registry as canonical source of truth

### What aligns

- `app/brain/semantics/metric_registry.py` is a substantial canonical registry with metric definitions and validation helpers.
- `app/brain/operational_cases.py` imports `default_metric_registry()` and `validate_metrics()` and stores `metric_registry_mode: advisory` metadata on case detection runs.
- `app/brain/connector_registry.py` uses registry validation helpers for emitted metric families and connector metric contracts.
- Tests/branches include drift guards such as `codex/qa-detectable-case-family-contract`.

### Architectural gaps

- **Runtime validation is still advisory for cases.** `_metric_registry_metadata()` records issues but does not stop, quarantine, or downgrade invalid metric emissions.
- **Adapters construct metrics with literal keys.** Tiendanube, MercadoLibre, Meta Ads, sample, Google Sheets, and CSV paths still instantiate `Metric(...)` directly. This is manageable if tests cover every key, but the registry is not yet the only construction path.
- **User-controlled sheet/CSV metrics are a drift vector.** Google Sheets/CSV ingestion can emit arbitrary keys from payload/sheet records. That is acceptable for previews, but sellable control-plane metrics should be registry-resolved or explicitly marked `custom`/non-operational.
- **Merge behavior is not registry-owned.** `merge_daily_reports()` sums numeric duplicate keys with same unit and otherwise last-wins. This is deterministic, but aggregation semantics should live in the metric registry (`sum`, `latest`, `max`, `weighted`, `non_aggregatable`) to prevent silent semantic drift.
- **Currency/unit enforcement is not yet a universal gate.** Registry diagnostics exist, but they need to become pre-dispatch/pre-case gating for operational cases.

### Recommendation

Promote registry validation from advisory to enforced in the runtime path that creates Operational Cases:

1. Add a `metric_registry_enforcement_mode` with at least `preview_advisory`, `runtime_quarantine`, and `runtime_strict`.
2. Reject or quarantine unknown metrics before they can influence deterministic detections.
3. Move duplicate-key aggregation policy into metric definitions.
4. Expose a registry-backed `MetricFactory` or `normalize_metric()` so adapters cannot bypass key/unit/value-kind/evidence requirements.
5. Treat CSV/Sheets unknown metrics as non-operational custom metrics unless mapped to registry definitions.

Verdict for this area: **directionally aligned, but needs enforcement hardening to eliminate metric drift.**

---

## 3. Connector platform separation: adapter / service / storage

### What aligns

- `app/brain/connector_registry.py` defines connector specs, capabilities, factory metadata, required config fields, required secret refs, emitted metric families, rate-limit metadata, lifecycle metadata, and health metadata.
- `app/brain/runtime.py` compiles `BusinessConfig` into a `CompiledBusinessRuntime` with safe connector refs and secret refs instead of raw secrets.
- `app/brain/pipeline.py` now routes daily report execution through registry metadata rather than hardcoding every adapter branch in the core execution path.
- Redaction boundaries are present for public params and runtime metadata.

### Architectural gaps

- **Legacy inline secrets still prove secret availability.** `_missing_required_secret_refs()` still checks legacy connector params, and execution can still pass resolved raw values from `BusinessConfig` at the adapter boundary. This is an accepted transition, but not final platform posture.
- **Service bindings are still adapter-shaped.** Pipeline accepts `sheets_service`, `tiendanube_http_client`, `mercadolibre_http_client`, `meta_ads_http_client`. This is pragmatic, but the platform abstraction should eventually be connector execution context + secret resolver + HTTP/client service factory.
- **Health metadata is declarative only.** `ConnectorHealthMetadata` exists, but readiness checks and degraded connector states are not a first-class runtime output yet.
- **Run ledger is not yet a full connector execution ledger.** Connector outcomes exist in run records, but the platform still needs durable per-connector attempt IDs, retry metadata, secret-ref version/digest, rate-limit state, and normalized error classes.
- **Preview/report endpoints can remain legacy escape hatches.** Public report endpoints still build reports directly from payload/sheets/csv/Tiendanube-style paths. They should either be explicitly preview-only or go through compiled runtime contracts.

### Branch assessment

`codex/connector-platform` is strategically aligned. Its diff indicates:

- registry-driven daily connector discovery,
- safe connector refs in run metadata,
- runtime/runner tests,
- secret redaction invariant tests.

Verdict: **merge-ready after rebase/conflict resolution and full tests; high strategic value.**

---

## 4. Workflow automation: idempotency, approval gates, audit

### What aligns

- `app/brain/workflow_automation.py` is intentionally projection-only and does not mutate cases, dispatch messages, or call external systems.
- Workflow actions are checked against the canonical action registry.
- External/approval-required actions are blocked as `blocked_approval_required`/suggestion-only instead of executing side effects.
- Workflow idempotency keys are deterministic and redacted.
- Workflow plans include an audit-shaped event payload.

### Architectural gaps

- **No durable workflow action ledger.** Idempotency keys are generated, but not enforced against a durable store for workflow action execution.
- **No approval object.** Approval-required actions are represented as blocked projections, but there is no approval request lifecycle (`requested`, `approved`, `rejected`, `expired`, `executed`) or approver policy.
- **Manual operator actions are not idempotent.** `apply_case_action()` mutates case state directly and does not accept or enforce an idempotency key.
- **Audit is split between case timeline and planned event payloads.** Case timeline is valuable, but a platform-grade audit trail should also have an append-only operator/workflow audit store that records authorization decisions, denials, and action requests.
- **Workflow scheme is not case-type/project configurable.** Rules can be evaluated, but allowed transitions/actions remain code-level, not schema-level.

### Branch assessment

`codex/workflow-automation` adds required action parameter gating in the workflow simulation path. This is exactly the right type of hardening: it prevents action plans from being considered executable without required inputs.

Verdict: **merge-ready after rebase and tests.**

---

## 5. Trust / Admin / Security: RBAC, audit trail, secret boundaries

### What aligns on current HEAD

- `app/brain/operator_auth.py` introduces internal operator principals and role permissions:
  - `viewer`: `internal:read`
  - `operator`: `internal:read`, `case:action`
  - `admin`: `internal:read`, `case:action`
- Unknown roles fail closed.
- Blank role defaults to `operator` for legacy bearer-token compatibility.
- Operator session projection redacts actor refs and exposes permission booleans.
- Server routes generally apply bearer token authentication and read permission guards through `_with_internal_stores()`.
- Case action endpoint adds a `case:action` guard inside the handler.
- Secret redaction is used broadly in projections and error paths.

### Critical gaps on current HEAD

- **No durable operator audit store on current HEAD.** There is no `operator_audit_events` table or `operator_audit.py` module in current HEAD. Case timelines are not enough for security audit because they do not capture auth denials, read/export activity, role use, or admin surfaces.
- **Admin is not meaningfully distinct from operator.** Current `admin` and `operator` have the same permission set. That may be acceptable temporarily, but admin-only audit export/config/security actions should require a separate permission.
- **Caller-supplied role headers are trust-on-token.** Anyone with the shared internal bearer token can supply `X-Orvo-Role: admin`. This is fine only if the token terminates behind a trusted internal gateway that injects identity/role headers. The contract should say so explicitly, and routes should eventually use OIDC/mTLS/service identity.
- **RBAC gap: WhatsApp delivery statuses route.** `/internal/brain/whatsapp/delivery-statuses` calls `_authorize_internal_operator()` but does not call `_require_internal_header_permission(..., INTERNAL_READ_PERMISSION)`. That means role semantics are bypassed for that internal route.
- **No audit of failed authorization on HEAD.** Forbidden/unknown role attempts return generic errors but are not appended to a durable audit stream.
- **Secret boundaries are improving but not final.** Runtime artifacts strip secrets, but legacy connector params still hold raw values at execution boundary.

### Branch assessment

`codex/trust-admin-security` is strategically important and should be integrated soon, but it is **not cleanly merge-ready as-is** because it is broad and touches server, storage, operator API, auth, and tests. Its diff indicates it adds:

- `app/brain/operator_audit.py`,
- `operator_audit_events` storage schema,
- scoped audit projection,
- audit of internal case actions and auth denials,
- internal role enforcement tests,
- admin-restricted audit export.

Recommended posture: **needs work before merge, but highest-priority hardening branch.** Rebase it onto `feat/orvo-brain-control-plane`, resolve route/auth duplication, ensure every internal route has the correct permission, and run full tests.

---

## Recent branch merge-readiness matrix

| Branch | Status vs current HEAD | ARB verdict | Rationale |
|---|---:|---|---|
| `codex-build-loop-20260601135119` | merged | No action | Recent workflow endpoints are already in current ancestry. |
| `codex/qa-detectable-case-family-contract` | merged | No action | Drift guard already integrated. |
| `codex/qa-workflow-secret-idempotency` | merged | No action | Secret/idempotency guard already integrated. |
| `codex/action-catalog-service-20260601` | merged | No action | Central action catalog is already present. |
| `codex/recently-acknowledged-endpoint-20260601` | unmerged | Merge-ready after rebase/tests | Read-only operator endpoint; aligns with case queue surfaces. Watch duplication with `codex/operator-surfaces`. |
| `codex/operator-surfaces` | unmerged | Merge-ready after rebase/tests, but dedupe first | Adds action catalog alignment and recently acknowledged endpoint. Some changes overlap with already-merged action catalog and endpoint branches. |
| `codex/search-analytics` | unmerged | Merge-ready after rebase/tests | Adds safe JQL/view analytics such as source connector and unassigned/actionable views; aligns with Jira-like search. |
| `codex/connector-platform` | unmerged | Merge-ready after rebase/tests; high priority | Strengthens registry-driven runtime and safe connector metadata. Strategically aligned with platform core. |
| `codex/workflow-automation` | unmerged | Merge-ready after rebase/tests | Required action-param gating improves approval/idempotency safety. |
| `codex/work-management` | unmerged | Merge-ready after rebase/tests | Adds lifecycle/owner-facing invariants such as non-empty comments, resolved timestamp, and brief policy. Aligns with work-management quality bar. |
| `codex/trust-admin-security` | unmerged | Needs work before merge; high priority | Adds needed durable audit/RBAC, but broad and likely to conflict with current server/auth surfaces. Rebase, tighten route coverage, then merge. |
| `codex/edge-developer-platform` | unmerged | Needs work / park | Gateway policy/service catalog may be directionally useful, but it is broad and risks expanding beyond the D2C wedge before case/workflow/security contracts are fully hardened. |

---

## Strategic recommendations for next architecture slice

1. **Make Trust/Admin/Security durable before adding more surfaces.** Merge a rebased version of operator audit with admin-only audit export and route-complete permission checks.
2. **Add WorkItem envelope and status category registry.** Do this as a projection/schema layer over `OperationalCase`, not a rewrite.
3. **Turn metric registry from advisory to enforced for Operational Cases.** Unknown/invalid metrics should not create owner-facing cases.
4. **Move aggregation semantics into the metric registry.** Replace generic duplicate-key sum/last-wins with registry-defined policies.
5. **Add durable workflow action/approval ledger.** Keep external execution disabled until approvals, idempotency, and audit are enforced.
6. **Consolidate connector execution context.** Replace adapter-shaped pipeline kwargs with a connector execution context, secret resolver, and service factory boundary.
7. **Keep the wedge narrow.** Avoid merging broad edge/developer-platform capabilities until D2C ecommerce case/workflow/admin contracts are stable and demonstrably sellable.

---

## Final ARB classification

- Current `feat/orvo-brain-control-plane` @ `4ce7df1`: **architecturally aligned but needs hardening before sellable-control-plane claim**.
- Low-risk operator/work-management/search/connector hardening branches: **generally merge-ready after rebase and tests**.
- Trust/Admin/Security branch: **needs work before merge, but should be prioritized**.
- Edge/developer-platform branch: **defer or constrain; not part of the immediate D2C control-plane wedge**.

Tests were not run for this read-only review.
