# Architecture Review Board Cron Update — 2026-06-04

Repository: `/root/orvo-agent`

Baseline reviewed: `feat/orvo-brain-control-plane` @ `559c044` (`codex: expose recently in-progress cases`)

Review mode: read-only architecture review. No code edits, merges, pushes, deploys, or cron changes were performed. This markdown report is the only intentional write.

## Executive verdict

The current baseline remains architecturally aligned with the Orvo direction: a sellable Atlassian/Jira-like control plane for LatAm D2C ecommerce, with `OperationalCase` as durable source-of-truth state, WorkItem/JQL/operator surfaces as projections, metric semantics governed by the registry, and workflow/external-action paths guarded by approval, idempotency, run-ledger, and audit contracts.

Since the previous 2026-06-04 review, several good trust/security and operator-surface slices have landed in `feat/orvo-brain-control-plane`:

- external action toolkit/action identifiers are validated before provider execution;
- operator audit denials and auth/business-grant projection have improved;
- recently in-progress cases are exposed from canonical `status_changed` timeline events;
- worker manifest validation was added;
- the full baseline test suite passes in this environment.

Main ARB concerns now are integration discipline rather than foundational misalignment:

1. **Surface branches need consolidation.** `codex/operator-surfaces` and `codex/search-analytics` are useful but continue endpoint/export proliferation and currently have merge-tree conflicts with the new baseline.
2. **Gateway policy must not overstate enforcement.** `codex/edge-developer-platform` is a strong contract slice, but idempotency/rate-limit fields are still policy metadata unless backed by durable enforcement/storage.
3. **Owner WhatsApp preview must remain projection-only.** The owner brief preview correctly avoids dispatch/mutation, but should expose registered action keys alongside text and avoid making legacy `recommended_action` prose the actionable contract.
4. **Unpromoted families must stay explicit.** `channel_mix_shift` still appears in type/projection mappings while intentionally absent from `CASE_FAMILY_METRICS`; this remains acceptable only as an explicit deferred/internal family.

Recommended merge train: merge/rebase clean guard and platform-contract branches first (`connector-platform`, `workflow-automation`, `work-management`, service-management if vocabulary tests hold, test/QA guards), then split/rebase the broad operator/search/edge branches.

## Evidence reviewed

Source-of-truth contracts and code inspected during this pass:

- `docs/README.md`
- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`
- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/connector-registry-contract.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`
- `docs/specs/testing-invariant-matrix.md`
- `app/brain/operational_cases.py`
- `app/brain/work_items.py`
- `app/brain/semantics/metric_registry.py`
- `app/brain/connector_registry.py`
- `app/brain/external_actions.py`
- `app/brain/workflow_automation.py`
- `app/brain/operator_auth.py`
- `app/brain/operator_audit.py`
- `app/brain/operator_api/recent_cases.py`
- branch snapshots/diffs listed below

Git and validation checks:

- Current branch: `feat/orvo-brain-control-plane`
- Current commit: `559c044`
- Pre-report status: clean
- Targeted architecture tests: `149 passed in 7.19s`
- Full suite: `1271 passed in 19.87s`
- Merge-tree scan against active reviewed branches: clean for several branches, conflicts noted explicitly in the branch table.

## Branch disposition summary

| Branch | Tip | Delta vs `feat/orvo-brain-control-plane` | Merge-tree | ARB disposition |
| --- | ---: | ---: | --- | --- |
| `codex/trust-admin-security` | `4d91b02` | no unique diff | clean/absorbed | **Already absorbed / no-op.** Trust/auth improvements are in baseline. |
| `codex/ack-latency-entity-kind-endpoint` | `4de1659` | no unique diff | clean/absorbed | **Already absorbed / no-op.** |
| `codex/resolution-latency-case-type-endpoint-20260604` | `b22b08d` | no unique diff | clean/absorbed | **Already absorbed / no-op.** |
| `codex/eng-factory-test-nodeid-regression-integration-20260604` | `4919b8f` | 2 files | clean | **Merge-ready after routine test.** Engineering guard only; no product architecture risk. |
| `qa/redteam-operator-invalid-payload-audit` | `be2897e` | 2 files | conflict in `tests/test_internal_operator_api.py` | **Merge-ready after rebase.** Strong payload/audit hardening; resolve test conflict. |
| `codex/connector-platform` | `080586c` | 12 files | clean | **Merge-ready after rebase/test.** Event-family metadata and executor policy metadata stay registry/runtime/ledger aligned. |
| `codex/work-management` | `3a1a28e` | 7 files | clean | **Merge-ready with focused core review.** Valuable system-reopen, owner-facing evidence gate, timestamp monotonicity, and WorkItem projection enhancements. Central model changes deserve focused tests. |
| `codex/workflow-automation` | `b7168ef` | 3 files | clean | **Merge-ready with audit-taxonomy check.** Keeps simulation/projection read-only and adds trigger matching; normalize event names before externalizing. |
| `codex/service-management` | `8dd91d8` | 6 files | clean | **Merge-ready after vocabulary contract check.** Read-only JSM projection; ensure owner/service statuses never become canonical `OperationalCase.status`. |
| `docs/roadmap-librarian-integration-train-20260604` | `4624c49` | 1 docs file | clean | **Merge-ready.** Aligns integration train with small trust/security and consolidation slices. |
| `docs/gtm-demo-script-20260604` | `171a96f` | 1 docs file | clean | **Merge-ready if claims remain product-accurate.** GTM docs only; avoid generic chatbot/agent-platform positioning. |
| `codex/eng-factory-manifest-git-guard-20260604` | `87df246` | 4 files | clean | **Merge-ready.** Strengthens worker handoff/git-claim validation. |
| `qa/jql-redaction-echo` | `ff51afd` | 1 test file | clean | **Merge-ready.** Useful redaction regression guard for query echo. |
| `codex/search-analytics` | `a8e1b9e` | 14 files | conflicts in `docs/specs/internal-operator-api-contract.md`, `tests/test_internal_operator_api.py` | **Needs selective merge/rebase.** JQL fields and run-trigger filtering are good; exports/summaries need contract discipline. |
| `codex/operator-surfaces` | `060e680` | 31 files | conflicts in recent cases, cases activity, API contract, tests | **Needs work / split before merge.** Useful read-only projections and owner brief preview, but too broad and conflicts with baseline surface work. |
| `codex/edge-developer-platform` | `dcf17e0` | 13 files | conflicts in auth/common/API contract/tests | **Needs work / rebase.** Strong gateway/service-catalog contract, but idempotency/rate-limit claims must match actual enforcement. |

## 1. OperationalCase / WorkItem vs Atlassian patterns

### Aligned

- `OperationalCase` remains the durable issue-like source of truth. Canonical statuses are still `open`, `acknowledged`, `in_progress`, `resolved`, and `dismissed`; canonical status categories remain Jira-like: `to_do`, `in_progress`, `done`.
- WorkItem remains a projection, not a second persistence model. Project keys, issue types, workflow definitions, status categories, and work item IDs are derived deterministically from canonical case state.
- `recently_in_progress` in baseline is correctly derived from canonical `status_changed` timeline events where `to_status == "in_progress"` rather than a new surface-owned timestamp.
- `codex/work-management` improves Atlassian alignment by exposing:
  - system-only recurrence reopen transitions separately from operator transitions;
  - issue-type definitions with `detectable`, `owner_facing`, `visibility`, and required metric keys;
  - WorkItem priority brackets, comment counts, last-commented timestamps, and acknowledgment SLA fields as projections.
- `codex/service-management` follows a Jira Service Management-style projection model: incident/service-request/problem/change record types, owner-facing status, SLA clocks, escalation reasons, and filters are derived from `OperationalCase` and not written back as lifecycle state.

### Gaps / risks

- There is still no persisted project/issue/workflow scheme registry. This is fine for Phase A, but product/admin language must say these are deterministic default projections, not tenant-configurable Jira projects/workflows.
- `codex/service-management` introduces owner/service status codes such as `waiting_owner` and `waiting_external`. These are acceptable only as nested projection fields with `status_category = "in_progress"`; they must never be promoted into `OperationalCaseStatus` or `OperationalCaseStatusCategory`.
- `codex/operator-surfaces` adds many activity endpoints. They are mostly source-of-truth aligned, but the branch is too broad and conflicts with recently landed baseline endpoints. Merge should be split by surface family or consolidated around shared activity query helpers.
- Wildcard imports across operator API modules continue to spread. This is not a blocker for a small control-plane core, but it becomes a maintainability risk as Jira-like surfaces grow.

### ARB recommendation

Keep the current pattern: `OperationalCase` as durable issue, WorkItem/JQL/board/service/WhatsApp views as projections. Merge `work-management` after focused tests because it strengthens the model. Do not introduce persisted WorkItems or custom workflow admin screens until a first-class project/workflow scheme registry exists.

## 2. Semantic registry as canonical source of truth

### Aligned

- `MetricRegistry` remains the canonical home for metric keys, aliases, units, evidence/source envelopes, value-kind checks, currency checks, case-family eligibility, freshness, and PII classes.
- Detection/owner-facing promotion still gates on `CASE_FAMILY_METRICS` via `DETECTABLE_OPERATIONAL_CASE_TYPES` and `OWNER_FACING_OPERATIONAL_CASE_TYPES`.
- `detect_cases_from_report(...)` attaches registry validation metadata and uses `CASE_FAMILY_METRICS` to suppress unpromoted or unsupported case families.
- Connector emitted metrics are certified through source/family/evidence/value/currency validation. `codex/connector-platform` preserves this and adds connector event-family metadata without inventing business metrics.
- `codex/work-management` strengthens semantic transparency by exposing required metric keys in issue-type definitions and marking unpromoted case families as `internal_deferred`.

### Gaps / risks

- `channel_mix_shift` remains present in operational type literals and projections but absent from `CASE_FAMILY_METRICS`. This is an acceptable deferred-family pattern only if tests keep it hidden from detection/owner-facing surfaces until canonical metrics are registered.
- Runtime/case validation still has advisory paths (`strict=False` metadata) for transitional adapters. Owner-facing promotion should continue to suppress cases when unknown/disallowed metrics are the basis for a claim.
- Workflow analytics such as aging, acknowledgment latency, resolution latency, handling latency, throughput, and SLA clocks are operational analytics over cases/timelines, not D2C semantic business metrics. They should not be mixed into the metric registry unless productized as canonical KPIs with units/evidence policy.
- Owner WhatsApp preview in `codex/operator-surfaces` composes text using `recommended_action` prose from case metadata. This is acceptable as explanatory copy only if the projection also exposes canonical `suggested_action_keys` or action catalog references for any actual action routing.

### ARB recommendation

Keep `CASE_FAMILY_METRICS` as the promotion gate. Add/retain invariant tests that every detectable/owner-facing case family has a metric registry envelope and every deferred family stays hidden. For owner briefs, make registered action keys explicit in the API payload before treating the brief as an actionable operator surface.

## 3. Connector platform separation: adapter / service / storage

### Aligned

- `connector_registry.py` continues to separate static connector metadata/executor policy from adapter implementation.
- Adapter invocation is registry-driven: factories and factory params are allowlisted, and missing required config reports keys rather than values.
- Raw legacy secrets are kept out of registry/runtime/run metadata; required secret refs are modeled as handles while inline secret fields remain transitional execution compatibility.
- `codex/connector-platform` adds:
  - `EVENT_FAMILY_CONNECTOR_EXECUTION` and `EVENT_FAMILY_CONNECTOR_HEALTH`;
  - `emitted_event_families` on `ConnectorSpec`;
  - serializable factory-param and executor policy metadata;
  - propagation through runtime/execution ledger tests.
- Event-family metadata is appropriately limited to connector execution/health. It does not claim domain event families without runtime/ledger records.

### Gaps / risks

- Secret-ref resolution remains transitional: specs model refs, but adapters still need raw tokens supplied by runtime/secret resolution. This bridge must remain inside runtime/secret infrastructure, not operator surfaces or persisted metadata.
- Connector instance/provisioning storage is still absent. Static registry is enough for current runtime, but admin/self-service connector management should not be marketed as complete until connector instances, health history, secret refs, and provisioning audit storage are first-class.
- External provider actions remain sidecar tooling, not core connectors. Baseline `external_actions.py` now correctly validates toolkit/action identifiers, rejects reserved core toolkits, checks run scope, requires approval for writes, and appends pre-side-effect ledger entries.

### ARB recommendation

`codex/connector-platform` is merge-ready after routine rebase/test. Keep the next connector-platform milestone focused on secret-ref resolution, connector instance storage, health history, and provisioning audit; avoid marketplace/generic connector claims.

## 4. Workflow automation: idempotency, approval gates, audit

### Aligned

- Workflow simulation remains projection-first and dry-run: no side effects in planning paths.
- Idempotency keys are deterministic and based on redacted params.
- `WorkflowActionLedgerStore.record_planned_action()` is the durable planning/duplicate-detection boundary.
- Approval-required actions are blocked before execution.
- Baseline `external_actions.py` now validates safe toolkit/action identifiers before any provider call or provider-response ref creation.
- `execute_external_action(...)` checks:
  - request shape;
  - run existence and business scope;
  - duplicate idempotency keys in run outcomes;
  - reserved core toolkit rejection;
  - provider allowlist;
  - approved workflow ledger linkage for writes;
  - pre-side-effect ledger append;
  - redacted payload/response summaries.
- `codex/workflow-automation` adds no-side-effect audit projection and trigger matching that avoids ledger writes when a trigger does not match.

### Gaps / risks

- Approved external action execution is still a narrow sidecar boundary, not a full production workflow executor. Before broader side effects, Orvo needs actor identity linkage, retry/failure semantics, execution-attempt storage, provider idempotency proof, RBAC checks per action, and operator audit correlation.
- `codex/workflow-automation` event names should be normalized against existing operator audit naming before becoming durable external API contract.
- `codex/edge-developer-platform` marks some gateway routes as idempotency-required and rate-limited. Today that is contract/evaluation metadata unless backed by durable idempotency storage and an actual rate-limit mechanism. For case actions, merely requiring an `X-Idempotency-Key` header is not equivalent to enforcing idempotency.

### ARB recommendation

Merge `workflow-automation` after audit taxonomy review. Treat `edge-developer-platform` as a contract draft until it stores/validates idempotency decisions durably and implements or delegates rate limiting.

## 5. Trust / Admin / Security: RBAC, audit trail, secret boundaries

### Aligned

- Internal operator API fails closed when `ORVO_INTERNAL_OPERATOR_TOKEN` is not configured or bearer token is invalid.
- Operator roles and permissions are centralized in `operator_auth.py`; business scoping is explicit through `X-Orvo-Businesses` grants.
- Baseline includes improved audit of denials and redaction of actor/request/target identifiers.
- `operator_audit.py` persists redacted events and enforces bounded audit export retention.
- Baseline external actions validate identifiers and redact request/response metadata.
- `qa/redteam-operator-invalid-payload-audit` is architecturally positive: non-object case-action payloads are rejected, audited, redacted, and do not mutate case state.
- `qa/jql-redaction-echo` is a useful safety guard for query echo redaction.
- `codex/edge-developer-platform` adds a typed gateway policy registry and service catalog, which is a good step toward Atlassian-like platform governance.

### Gaps / risks

- `SQLiteOperatorAuditStore.append_event()` redacts `business_id` before persistence, while `list_events()` queries by the supplied business ID. Normal tenant IDs are unchanged, but secret-shaped business IDs could become unretrievable. Either reject secret-shaped tenant IDs at config time or explicitly test/query the redacted representation.
- RBAC is still header-token based. That is acceptable for internal Phase A but should not be positioned as full user/group/session administration until backed by durable identity provider integration.
- Gateway policy currently audits/returns decisions but does not universally persist allowed/denied gateway events. Denials in specific routes are audited, but a full gateway audit trail should be consistent across routes.
- Edge policy route coverage is partial. Only selected routes are mapped/enforced; do not imply global gateway coverage.

### ARB recommendation

Prioritize small security guard branches (`qa/redteam-operator-invalid-payload-audit`, `qa/jql-redaction-echo`) after rebase. Rebase `edge-developer-platform`, label its gateway/rate-limit/idempotency work as contract-only where enforcement is not durable, and add tests for secret-shaped IDs and idempotency behavior before expanding coverage.

## Branch-specific notes

### `codex/work-management` — merge-ready with focused core review

This branch now looks materially stronger than earlier broad/stale work-management attempts. Positive changes:

- recurrence-driven system reopen is separated from operator transitions;
- detection mutation metadata captures before/after fields;
- mutation timestamps must be monotonic relative to `updated_at`;
- owner-facing eligibility requires promoted family, evidence snapshots, and policy flags;
- WorkItem projection adds priority brackets, comment counts, acknowledgment SLA fields, and issue-type semantic visibility.

Risks to test before merge:

- direct `open -> dismissed/resolved` cases should stop ack SLA clocks correctly;
- system recurrence must clear terminal timestamps without letting operators manually reopen;
- owner-facing evidence gate must not hide intentional `data_stale` owner caveats;
- `channel_mix_shift` must remain `internal_deferred` until metrics are promoted.

### `codex/operator-surfaces` — needs split/rebase

Positive:

- recent opened/acknowledged/in-progress/assigned/commented/reopened/resolved/dismissed views are read-only;
- owner case brief preview avoids dispatch and mutation;
- in-progress/reopened/commented projections use timeline events rather than separate surface state.

Concerns:

- 31-file delta and many endpoints are too broad for one merge;
- merge-tree conflicts exist in recent-cases/activity/API-contract/test files;
- owner brief preview should expose canonical action keys and avoid treating WhatsApp copy as action contract;
- surface modules continue wildcard import coupling.

Recommended salvage order:

1. consolidate recent activity helpers;
2. merge one endpoint family at a time;
3. add contract fields for `suggested_action_keys`/case IDs in owner brief preview;
4. leave dispatch out of this branch.

### `codex/search-analytics` — needs selective merge/rebase

Positive:

- adds useful JQL-lite fields: `work_item_id`, `assigned`, `actionable`, `freshness_state`;
- run history trigger filtering uses ledger API rather than raw SQL;
- summaries are bounded by `parse_limit` and business scope.

Concerns:

- conflicts with API contract and internal operator API tests;
- export rows are built from projection dictionaries, which can make API projection fields an implicit intermediate source of truth;
- saved-view/export-like functionality should remain built-in/read-only until custom view storage/RBAC/audit exists.

Recommendation: merge JQL field additions and run-trigger filtering first; defer or tighten exports behind explicit source-of-truth tests.

### `codex/edge-developer-platform` — needs work/rebase

Positive:

- typed `GatewayPolicyRegistry`, `GatewayRoutePolicy`, `GatewayPrincipal`, and service catalog are strategically aligned with Atlassian platform governance;
- route policies centralize permissions, idempotency requirement metadata, audit event names, and rate-limit buckets;
- `runtime:execute` permission separates runtime execution from case mutation.

Concerns:

- conflicts in auth/common/API-contract/tests;
- idempotency is checked for key presence/shape but not durable duplicate enforcement;
- rate-limit buckets are metadata only;
- route coverage is partial.

Recommendation: rebase after security payload guard, rename enforcement states honestly, and add durable idempotency/rate-limit backing before claiming enforced gateway behavior.

### `codex/service-management` — merge-ready after vocabulary check

Positive:

- pure read-only JSM-style projection over Operational Cases;
- service record type, owner status, SLA clocks, SLA status, escalation reasons, and filters are deterministic;
- waiting states remain nested owner statuses with canonical `status_category = "in_progress"`.

Concerns:

- maps `channel_mix_shift` to `problem`; acceptable only if such cases remain internal/deferred until metric promotion.
- SLA policies are static constants; acceptable for Phase A, but should not be marketed as tenant-configurable SLAs yet.

Recommendation: merge with tests that canonical status categories remain exactly `to_do`, `in_progress`, `done` and service statuses never leak into `OperationalCaseStatus`.

### `qa/redteam-operator-invalid-payload-audit` — merge-ready after rebase

Positive security guard: rejects non-object case action payloads, records a redacted failure audit, and avoids mutation. Rebase conflict is only in test file based on merge-tree output.

### `codex/connector-platform` — merge-ready

Adds connector execution/health event-family metadata and safe executor policy metadata. This is additive and aligned with adapter/service/storage separation.

### `codex/workflow-automation` — merge-ready with taxonomy check

Adds workflow audit projections and trigger-match gates without side effects. Normalize event naming with `operator_audit` before external API/docs commitments.

## Strategic alignment checklist

| ARB question | Current answer |
| --- | --- |
| OperationalCase / WorkItem follows Atlassian patterns? | **Yes, with Phase A limits.** Canonical cases + projected WorkItems/JQL/workflows are right. No tenant-configurable project/workflow scheme yet. |
| Semantic registry canonical; no metric drift? | **Mostly yes.** Registry gates metric/case promotion. Watch `channel_mix_shift` and owner brief action prose. |
| Connector platform separation? | **Yes.** Registry-driven adapter execution is clean; connector instance/secret-ref storage remains next platform gap. |
| Workflow automation idempotency, approval gates, audit? | **Partially yes.** Planning/approval/external-action boundaries are strong. Full executor and gateway idempotency need durable enforcement before broad side effects. |
| Trust/Admin/Security RBAC/audit/secrets? | **Improving.** Header-token RBAC, business grants, redaction, denial audit, and payload guards are good for internal Phase A. Full identity/admin model still future work. |

## Final ARB guidance

1. **Merge clean foundational guards first:** `connector-platform`, `workflow-automation`, `work-management` after focused tests, service-management after vocabulary tests, and small QA/security guards after rebase.
2. **Split broad surface work:** `operator-surfaces` and `search-analytics` should be decomposed by endpoint family/query feature and rebased onto `559c044`.
3. **Keep WhatsApp/operator surfaces projection-only:** expose case IDs, evidence, registered action keys, and source metadata; do not let brief text become workflow state.
4. **Do not promote deferred semantics accidentally:** `channel_mix_shift` stays hidden/deferred until the metric registry receives canonical keys and tests.
5. **Treat edge/gateway work as contract-first:** excellent strategic direction, but durable idempotency/rate-limit/audit enforcement must arrive before product claims.
