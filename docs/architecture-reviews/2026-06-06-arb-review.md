# Architecture Review Board Review — 2026-06-06

**Repository:** `/root/orvo-agent`
**Baseline branch reviewed:** `feat/orvo-brain-control-plane`
**Baseline HEAD:** `c0660eb` (`docs: gate fulfillment backlog roadmap`)
**Review mode:** read-only architecture review; no code changes, merges, pushes, deployments, or cron changes performed. This markdown report is the only written artifact.
**Verification:** `pytest -q` on `feat/orvo-brain-control-plane` returned `1315 passed in 20.05s`.

## Executive decision

**Current control-plane branch is architecturally aligned enough to continue building on, with several important gaps remaining before calling the platform Atlassian/Jira-grade.** The mainline code now has the right directional seams: OperationalCase is the durable source of truth, WorkItem is a projection, JQL-lite is a bounded in-memory query layer, the semantic metric registry is canonical, connector execution is moving toward registry-driven factories, and internal operator APIs have token + RBAC + tenant-scope + audit/redaction controls.

**Merge-ready / low-risk candidates**

| Branch | ARB disposition | Reason |
|---|---:|---|
| `codex/eng-factory-secret-ref-runtime-20260606` (`b093178`) | **Merge-ready after normal CI/rebase** | Small focused change (2 files) that strengthens connector secret boundaries by requiring secret-bearing adapter kwargs to be sourced as resolved execution secrets, not durable public connector params. This directly closes a connector-platform gap. |
| `qa/case-stale-suppression-snapshot-contract` (`36ac5ff`) | **Already integrated / no unique delta vs current baseline** | `ahead=0`; no active architecture concern. |
| `codex/stagnation-case-type-endpoint-20260606023129` (`0dc7327`) | **Already integrated / no unique delta vs current baseline** | Stagnation-by-case-type route exists on current baseline. |
| `codex/qa-invalid-idempotency-redaction-20260605` (`e43cbdc`) | **Already integrated / no unique delta vs current baseline** | Idempotency-key redaction guard is present in current action API. |
| `codex/stagnation-severity-endpoint-20260605232428` (`c5d56a3`) | **Already integrated / no unique delta vs current baseline** | Stagnation-by-severity route exists on current baseline. |
| `codex/run-artifact-route-validation-20260605170229` (`e67fa3a`) | **Already integrated / no unique delta vs current baseline** | Resolution-latency source endpoint is present on current baseline. |

**Needs-work / do not merge without reconciliation**

| Branch | ARB disposition | Reason |
|---|---:|---|
| `codex/work-management` (`15e0575`) | **Needs rebase + focused split** | Architecturally strong Atlassian additions (timeline chronological invariants, actor taxonomy, reopen semantics, owner-facing policy) but branch is behind current baseline and touches central OperationalCase/WorkItem semantics. Merge only after rebasing and isolating central-model changes into a narrow packet with invariant tests. |
| `codex/connector-platform` (`3ee379a`) | **Needs rebase + secret-boundary reconciliation** | Direction is correct for adapter/service/storage separation and registry execution, but the current baseline still lacks the `resolved_secret_param` seam unless `codex/eng-factory-secret-ref-runtime-20260606` lands. Reconcile with that branch first. |
| `codex/trust-admin-security` (`da8be95`) | **Needs rebase / partial integration check** | The current baseline already contains strong internal envelope redaction and audit changes. Remaining branch commits should be patch-id reviewed to avoid duplicating already-integrated security behavior. |
| `codex/operator-surfaces` (`a0ff67b`) | **Needs decomposition** | Adds many read surfaces and owner/operator projections. Directionally useful, but high duplication risk across recent/stagnation/owner-brief endpoints. Split into contracts + one surface family at a time. |
| `codex/search-analytics` (`f21a8f9`) | **Needs canonical field review** | Adds JQL/view facets and run analytics. Good for Jira-like discoverability, but every new filter/facet must be tied to WorkItem/OperationalCase or metric-registry canonical fields; avoid ad hoc projection vocabulary. |
| `codex/workflow-automation` (`7ba53f6`) | **Needs strict gate/audit review before merge** | Contains important approval/audit work, but broad and repetitive commit stack. Ensure executor cannot run side effects unless action catalog + approval gate + ledger state all agree. |
| `codex/edge-developer-platform` (`2dea33f`) | **Needs scope control** | Gateway policy/service catalog are plausible platform primitives, but risk pulling Orvo toward a generic developer platform. Keep behind internal API/control-plane contract, not first-product surface. |
| `codex/service-management` (`0751910`) | **Needs product-scope validation** | Service-management projection may be useful internally but risks broadening beyond D2C ecommerce wedge. Merge only if tied to D2C operator workflows and existing case/workflow contracts. |

## 1. OperationalCase / WorkItem vs Atlassian patterns

### What is aligned

- **OperationalCase remains canonical state.** `app/brain/work_items.py` explicitly frames WorkItem as an additive projection layer over OperationalCase, not a second durable task store.
- **Project projection exists.** `project_projection()` derives a stable project/workspace from `business_id` with `project_key`, `case_type_scheme_id`, and `workflow_scheme_id`.
- **Issue-type mapping exists.** `case_issue_type()` maps OperationalCase `case_type` to issue type; `operational_case_issue_type_definitions()` exposes current D2C case families as scheme-bound definitions.
- **Workflow/status categories exist.** `operational_case_status_definitions()` exposes statuses, transitions, actionable/terminal flags, and Jira-like `status_category` metadata.
- **JQL-lite exists and is safely bounded.** `operator_views.py` supports a limited field/operator set, max length, max clause count, max `IN` values, explicit syntax rejection, and in-memory filtering rather than SQL translation.
- **Built-in views are readonly.** This fits Atlassian patterns where saved/built-in filters sit on top of canonical issue state.

### Gaps / concerns

1. **WorkItem is still projection-only, not yet a full Jira-grade work-management contract.** It has project key, issue type, status category, and workflow definition, but lacks canonical priority scheme definitions, SLA fields, reopen policy, workflow transition metadata, and permission/role linkage at the workflow level.
2. **Priority bracket logic is duplicated outside WorkItem.** Multiple operator API modules classify `priority_score` into brackets via helper logic in `operator_api.common`, while `work_items.py` does not own the priority scheme. This creates drift risk for dashboards vs WorkItem/JQL semantics.
3. **JQL fields are locally registered in `operator_views.py`.** The field list is controlled and safe, but not yet exported from a canonical WorkItem query-field registry. As search analytics expands, this could become a second semantic registry.
4. **Branch `codex/work-management` contains important missing invariants.** Its unique changes add timeline chronological validation, actor types (`owner`, `worker`), recurrence reopen semantics, redacted assignment, and owner-facing policy checks. These are architecturally good, but central-model changes should be rebased and merged narrowly.

### ARB recommendation

- Create a canonical **WorkItem field registry** in/near `work_items.py` and have JQL/views/facets import from it.
- Move priority bracket definitions into WorkItem semantics and reuse everywhere (`cases`, `aging`, `stagnation`, `workflow`, `histograms_*`).
- Rebase `codex/work-management`; split central invariants from surface additions. Merge the timeline/timestamp/owner-facing-policy invariants first if tests stay green.

## 2. Semantic registry as canonical source of truth / metric drift

### What is aligned

- `app/brain/semantics/metric_registry.py` defines immutable `MetricDefinition` records and a `MetricRegistry` with deterministic alias resolution.
- `CASE_FAMILY_METRICS` is a `MappingProxyType` and is used by OperationalCase to derive detectable and owner-facing case families.
- OperationalCase evidence extraction resolves metric aliases through `default_metric_registry()` and stores canonical `metric_key`, preserving source alias only in metadata when different.
- Connector metric validation exists (`validate_emitted_metrics`, `find_source_envelope_violations`, case metric validators) and tests cover connector-registry contracts.
- Owner-facing reporting checks the metric registry before displaying case evidence metrics.

### Gaps / concerns

1. **Case family membership is still encoded in both type literals and `CASE_FAMILY_METRICS`.** Current `OperationalCaseType` is a literal union, while detectable/owner-facing sets derive from the registry. The accepted direction is fine, but new case families must not be added to one without the other.
2. **Projection-level analytics may create vocabulary drift.** New dashboard facets (`priority_bracket`, `source_connector`, `entity_kind`, `degraded`, evidence summaries) are useful, but some are not metric-registry concepts. They need a separate canonical WorkItem/Case field registry to avoid masquerading as metrics.
3. **Metric registry remains Python-code canonical, not data-backed.** This is acceptable for the current deterministic wedge, but future tenant/config overrides must not bypass registry validation.

### ARB recommendation

- Add an invariant test that `OperationalCaseType`, `CASE_FAMILY_METRICS`, docs case-family catalog, and action-key catalog stay in lockstep.
- Keep all actual business measurements in `MetricRegistry`; keep WorkItem/search fields in a separate canonical query-field registry.
- Do not let dashboard route names or WhatsApp/report text introduce new metric keys.

## 3. Connector platform separation: adapter / service / storage

### What is aligned

- `ConnectorSpec`, `ConnectorExecutorMetadata`, `ConnectorFactoryParam`, health/rate-limit/scope/lifecycle metadata, and `build_report_factory_kwargs()` form a real connector registry seam.
- Factory loading is declarative and adapter callables are validated through `validate_daily_report_adapter()`.
- Service bindings (`source == "service_binding"`) are separated from connector public params.
- `validate_control_plane_config()` distinguishes public `params` from `secret_refs` and warns on legacy inline secrets.
- Current capabilities preserve existing adapters while introducing registry-driven execution.

### Gaps / concerns

1. **Current baseline still lets secret-bearing factory params be represented as `connector_param`.** The small `codex/eng-factory-secret-ref-runtime-20260606` branch fixes this by adding a `resolved_secret_param` source and updating Tiendanube/MercadoLibre/WooCommerce secret kwargs.
2. **Legacy adapter signatures still accept raw token kwargs.** This is acceptable only if raw values exist exclusively in an execution-scoped compiled runtime copy, never in durable control-plane config.
3. **Storage remains SQLite-bound in several operator/internal helper paths.** The separation is adequate for the current product stage, but connector execution/state should continue to flow through run ledger + connector registry rather than endpoint-local persistence shortcuts.

### ARB recommendation

- Merge `codex/eng-factory-secret-ref-runtime-20260606` after CI/rebase.
- Add contract language/tests that durable connector config may contain `secret_refs` only, and raw secret material may only be present in a runtime-resolved ephemeral object.
- Keep adding service bindings instead of importing services directly into route handlers.

## 4. Workflow automation: idempotency, approval gates, audit

### What is aligned

- Manual operator case actions validate action keys against the registered case action catalog and disabled-boundary list.
- `normalize_case_action_idempotency_key()` rejects non-string, empty, oversized, unsupported-character, and secret-shaped idempotency keys.
- `apply_case_action_with_idempotency()` pre-ledgers manual mutations with `execution_state="pending_execution"`, marks `executed` after mutation, marks `failed` on exception, and replays duplicates only if the existing ledger record matches source/case/action and was executed.
- `WorkflowActionLedgerStore` has durable uniqueness on `(business_id, idempotency_key)` and tracks approval state, execution state, source, actor, rule, params, and approval request ID.
- Approval decision handling updates approval request and ledger state and returns a redacted audit event with `side_effects_executed=0`.

### Gaps / concerns

1. **Manual actions can execute without idempotency key.** Current code falls back to direct mutation when no key is supplied. This may be acceptable for internal MVP but is not Atlassian-grade for auditable operator workflows. The internal HTTP boundary should require an idempotency key for mutating endpoints.
2. **Workflow approval decision audit is returned, not durably appended to operator audit.** The ledger returns an `audit_event`, but ARB should require durable audit storage or explicit run-ledger linkage before automation is considered production-ready.
3. **Approval execution gate must remain fail-closed.** Branch `codex/workflow-automation` appears to address approved gates, but it is broad. Ensure side effects cannot execute from `pending`, `rejected`, `cancelled`, `blocked_approval_required`, or mismatched action catalog states.
4. **Idempotency key is stored raw in workflow ledger.** It is validated to avoid secret-shaped values, which reduces risk. Still, if external clients generate business-sensitive keys, consider storing a deterministic hash lookup key plus redacted display value later.

### ARB recommendation

- Require `X-Idempotency-Key` on all mutating internal case-action endpoints.
- Persist approval decision audit events to `operator_audit_events` or a workflow audit table before any executor consumes approved actions.
- Rebase/decompose `codex/workflow-automation`; merge only the approval-gate invariant and tests first.

## 5. Trust / Admin / Security: RBAC, audit trail, secret boundaries

### What is aligned

- Internal API authenticates with `ORVO_INTERNAL_OPERATOR_TOKEN` via constant-time bearer comparison.
- Internal authorization builds an operator principal from headers and enforces both business scope (`X-Orvo-Businesses`) and required permission (`internal:read` for read routes).
- Failed authentication and authorization paths append best-effort redacted audit events without persisting raw Authorization values.
- `audit_scope.py` separates redacted business display ID from deterministic SHA-256 business scope key, preventing secret-shaped tenant IDs from leaking while preserving queryability.
- `SQLiteOperatorAuditStore` redacts event payloads, actor refs, target IDs, request IDs, and enforces bounded retention exports.
- Internal success/error envelopes redact secret-shaped `business_id` and request IDs and set `redaction_applied=True`.

### Gaps / concerns

1. **RBAC currently appears coarse-grained.** Read routes use `internal:read`; mutating routes must require distinct permissions (`case:write`, `workflow:approve`, `audit:read`, etc.) and tests should enforce this boundary.
2. **Audit append failures are swallowed for auth denial.** This is acceptable to fail closed on auth, but production posture should emit a safe operational signal/counter for audit sink failures.
3. **Audit retention is bounded for export, but deletion/compaction policy is not visible here.** Add explicit retention enforcement or document that retention currently applies only to exports.
4. **Secret boundary depends on connector registry branch not yet in baseline.** Until `resolved_secret_param` lands, secret-bearing adapter kwargs can still look like normal connector params.

### ARB recommendation

- Add route-level permission matrix tests for every internal read/write/admin endpoint.
- Treat audit read/export as admin-only and test tenant scope using the hashed `business_scope_key` path.
- Land connector secret-boundary branch before exposing self-service connector config.

## Strategic alignment notes

- The product is still properly positioned as a D2C ecommerce operations control plane, not a generic chatbot or generic agent platform.
- The strongest platform pattern is **canonical state + deterministic projection**. Preserve this: OperationalCase, metric registry, connector registry, run ledger, action ledger, and audit log must remain source-of-truth layers; WhatsApp/report/operator text must remain projections.
- The main architectural risk is **surface proliferation**: many recent branches add dashboard endpoints/facets. Useful, but every new surface should prove it is a projection over canonical WorkItem/Case/Metric/Run fields.
- The second risk is **branch breadth**: several branches are behind and broad. Merge smaller invariants first, especially in central model and workflow automation areas.

## Concrete next actions for engineering

1. Merge or cherry-pick `codex/eng-factory-secret-ref-runtime-20260606` after CI; it is the highest-value small security/platform alignment patch.
2. Rebase `codex/work-management` and split into:
   - timeline chronological invariant + timestamp guards,
   - owner/worker actor taxonomy,
   - recurrence reopen semantics,
   - owner-facing policy projection.
3. Create a WorkItem query-field/priority registry and route `operator_views.py`, dashboard facets, and histogram priority brackets through it.
4. Require idempotency keys on mutating internal HTTP actions.
5. Persist workflow approval-decision audit events durably before introducing any workflow executor with external side effects.

## Review artifact / status

- Report written to: `docs/architecture-reviews/2026-06-06-arb-review.md`
- Tests run on baseline: `pytest -q` → `1315 passed in 20.05s`
- No code edits, merges, pushes, deploys, or cron changes were performed.
