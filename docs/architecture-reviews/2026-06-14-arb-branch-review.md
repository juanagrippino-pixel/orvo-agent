# Architecture Review Board — branch alignment review

**Date:** 2026-06-14  
**Base branch:** `feat/orvo-brain-control-plane`  
**Review type:** Read-only code/branch review. No merge, push, deploy, or cron changes performed.

## Executive summary

| Branch | Commit | Verdict | Board call |
|---|---:|---|---|
| `N2-Pro/connector-platform` | `4adfc5137011` | **Merge-ready** | Small, additive, and respects connector/runtime boundaries. |
| `N2-Pro/trust-admin-security` | `dafa91ebbe77` | **Merge-ready** | Good trust-boundary hardening with no new shadow auth path. |
| `n2-pro-work-management` | `0b6382f4d358` | **Merge-ready with sequencing** | Strongest Atlassian-style WorkItem improvement; merge before search/service layers. |
| `N2-Pro/workflow-automation` | `4dc140da032f` | **Needs work** | Good ledger-first model, but route overlap/conflict and one surface inconsistency remain. |
| `N2-Pro/search-analytics` | `6d6f7a53ba24` | **Needs work** | Useful exports/query metadata, but overlaps heavily with work-management and operator-surface changes. |
| `N2-Pro/service-management` | `872d816991d3` | **Needs work** | Good JSM-style projection, but policy/mapping literals risk drift outside the canonical registry/catalog path. |
| `N2-Pro/operator-surfaces` | `6064b83ecfc5` | **Needs work** | Directionally right, but too broad and now collides with other branches on route/module ownership. |

## Board findings by architecture theme

### 1) OperationalCase / WorkItem vs Atlassian patterns

**What aligns**
- `n2-pro-work-management` is the best fit with the Atlassian/Jira target. It expands `app/brain/work_items.py` and `app/brain/operator_views.py` with canonical WorkItem fields such as `owner_visible`, `sla_target_seconds`, `due_at`, `sla_status`, evidence/timeline counts, last-event metadata, and owner-facing visibility.
- The branch keeps `OperationalCase` as the durable issue object and projects Jira-like semantics from it instead of creating a second task system, which matches `docs/specs/operational-case-engine-contract.md`.
- `N2-Pro/search-analytics` reinforces the same direction by exposing query-field metadata and CSV export on top of the allowlisted JQL-like parser in `app/brain/operator_views.py` / `app/brain/operator_api/views.py`.
- `N2-Pro/service-management` is directionally correct as a Jira Service Management-style projection over the existing case object, not a replacement lifecycle.

**Gaps / risks**
- Atlassian-like patterns are still mostly code-defined, not scheme-defined. Projects, issue-type schemes, workflow schemes, and SLA policies are still hardcoded projections rather than compiled tenant-configured policy.
- `N2-Pro/operator-surfaces` adds many endpoint-per-transition surfaces (`recently_opened`, `recently_acknowledged`, `recently_in_progress`, etc.). That is usable, but it pushes the API toward endpoint proliferation instead of a smaller query/activity surface plus stable projection families.
- `N2-Pro/search-analytics` and `n2-pro-work-management` both modify `app/brain/work_items.py` and `app/brain/operator_views.py`. The overlap is architectural, not just git noise: both are trying to become the canonical WorkItem/query surface. Merge sequencing matters.

### 2) Semantic registry as source of truth

**What aligns**
- `N2-Pro/connector-platform` is disciplined: it only exposes a narrow certification summary in `app/brain/operator_api/connectors.py` (`status` + integer `issue_count` from `event_certification` / `metric_certification`) and documents/tests that operator-safe boundary.
- None of the reviewed branches create LLM-defined metrics or a parallel metric computation plane.

**Gaps / risks**
- The repo-wide gap from the 2026-06-13 review remains open: the semantic/metric registry is structurally strong, but still not obviously the blocking source of truth for every ingestion/report/case path.
- `N2-Pro/service-management` introduces hardcoded case-type→service-record-type mappings and hardcoded SLA policy tables in `app/brain/service_management.py`. That is acceptable as an initial projection, but it will drift unless those mappings are anchored to the case-family catalog or a compiled policy registry.
- `N2-Pro/search-analytics` broadens exports and query metadata, but does not itself tighten metric-registry enforcement. It should land after—not before—the underlying canonical WorkItem field set is settled.

### 3) Connector platform separation (adapter / service / storage)

**What aligns**
- `N2-Pro/connector-platform` is the cleanest branch in the set. It changes only:
  - `app/brain/operator_api/connectors.py`
  - `docs/specs/internal-operator-api-contract.md`
  - `tests/test_internal_connector_readiness_api.py`
- It does not couple connector readiness UI data to adapter internals, raw secret material, or runtime mutation.
- The projection remains operator-safe and additive to the existing connector registry/run ledger boundary.

**Board call**
- This branch is ready to merge independently and first.

### 4) Workflow automation: idempotency, approvals, audit

**What aligns**
- `N2-Pro/workflow-automation` is well aligned with the control-plane pattern: approval queue, execution queue, and audit are all projections over the workflow action ledger rather than a new automation store.
- `app/brain/workflow_approval_queue.py`, `app/brain/workflow_execution_queue.py`, and `app/brain/workflow_action_audit.py` add scoped filtering by `case_id` / `action_key`, validate action keys against the catalog, and keep approval-required actions governed.
- The HTTP layer in `app/http/internal_brain/workflow_actions.py` is read-focused and permissioned, which is the right order: visibility before more mutation power.

**Gaps / risks**
- There is a concrete branch conflict with `N2-Pro/operator-surfaces`: both branches define `app/http/internal_brain/workflow_actions.py`, but for different responsibilities. In `N2-Pro/workflow-automation` it serves workflow approval/execution/audit reads; in `N2-Pro/operator-surfaces` it serves case action POSTs. That needs a route/module ownership split before merge.
- The approval queue projection supports `case_id`, but the HTTP route in `N2-Pro/workflow-automation` does not pass `case_id` through for `/workflow/approval-queue`, while execution/audit routes do. That is a surface inconsistency.
- Execution is still explicitly non-implemented (`execution_enabled: False` / `executor_state: not_implemented`). That is acceptable for a read surface, but the branch is not yet a complete workflow automation slice.

### 5) Trust / admin / security

**What aligns**
- `N2-Pro/trust-admin-security` materially improves secret-boundary handling:
  - `app/brain/audit_scope.py` collapses secret-shaped `business_id` labels to `[REDACTED]`.
  - `app/brain/operator_audit.py` redacts secret-key payloads and legacy identifiers during export.
  - `app/http/internal_brain/common.py` collapses nested `business_id` fields after redaction so partial secret-bearing labels do not survive in operator payloads.
- `app/brain/operator_auth.py` now canonicalizes wildcard business grants to `("*",)`, reducing accidental retention of redundant or pasted grant fragments.
- `app/http/internal_brain/operator_audit.py` now returns a controlled 503 on store failure instead of leaking lower-level behavior.

**Gaps / risks**
- RBAC is still coarse and internal-header/token based. This branch hardens the boundary; it does not complete the long-term admin/RBAC model.
- Approval/mutation permissions remain route-level and coarse; there is still no richer project/workflow/case-scope permission scheme.

## Branch-by-branch detail

### `N2-Pro/connector-platform` — **Merge-ready**
- Good change shape: operator projection only.
- Best evidence: `app/brain/operator_api/connectors.py` adds `_certification_summary_projection(...)` and threads it into `last_health` without exposing raw certification payloads.
- No architectural duplication found.

### `N2-Pro/trust-admin-security` — **Merge-ready**
- Good change shape: auth/audit/redaction hardening only.
- Best evidence: `app/brain/operator_audit.py`, `app/http/internal_brain/common.py`, `app/brain/audit_scope.py`.
- Recommended to merge early, before wider operator-surface/export branches.

### `n2-pro-work-management` — **Merge-ready with sequencing**
- Strongest Atlassian-pattern branch.
- Best evidence: `app/brain/work_items.py` and `app/brain/operator_views.py` expand canonical field vocabulary instead of inventing a second queue model.
- Merge this before `N2-Pro/search-analytics` and `N2-Pro/service-management`, because those branches assume or extend the same query/projection surface.

### `N2-Pro/workflow-automation` — **Needs work**
- Keep the ledger-first design.
- Fix before merge:
  1. split/rename the HTTP module ownership so it does not collide with operator-surfaces,
  2. make `/workflow/approval-queue` accept/pass `case_id` consistently,
  3. rebase after the route split.

### `N2-Pro/search-analytics` — **Needs work**
- Good pieces:
  - `app/brain/operator_api/views.py` exposes canonical query-field metadata,
  - `app/brain/operator_views.py` adds CSV export over the same allowlisted filters,
  - `app/http/internal_brain/runs_delivery.py` adds run-history export.
- Main issue: it overlaps the same WorkItem/query ownership already expanded by `n2-pro-work-management`, so merging it first would lock in a second round of canonical-surface churn.

### `N2-Pro/service-management` — **Needs work**
- Good direction: `app/brain/service_management.py` is explicitly read-only and projects JSM-style concepts from canonical case state.
- Main issue: record types, waiting states, escalation reasons, and SLA policy are currently literal tables in code. Those should be tied more directly to case-family/spec/compiled policy so the projection does not become a second policy source of truth.

### `N2-Pro/operator-surfaces` — **Needs work**
- Good product direction: modular operator routes, owner brief, recent activity, suggested actions, richer top/recent projections.
- Main issues:
  1. too broad for safe merge as one unit,
  2. endpoint proliferation across many `recently_*` routes,
  3. direct conflict with `N2-Pro/workflow-automation` on `app/http/internal_brain/workflow_actions.py`.
- Split recommendation: recent activity surface, owner brief, suggested actions, and case-action mutation routes should be separate branches.

## Recommended merge order

1. `N2-Pro/connector-platform`
2. `N2-Pro/trust-admin-security`
3. `n2-pro-work-management`
4. Rework/split route ownership between `N2-Pro/workflow-automation` and `N2-Pro/operator-surfaces`
5. Rebase `N2-Pro/search-analytics` on top of merged work-management surface
6. Revisit `N2-Pro/service-management` after policy-source tightening
7. Reconsider smaller `N2-Pro/operator-surfaces` slices

## Highest-priority open architectural gaps

1. Make the semantic/metric registry the clearly enforced source of truth across all case/report/export paths, not just selected readiness/certification surfaces.
2. Move project / issue-type / workflow / SLA policy from code literals toward compiled registry/scheme objects.
3. Resolve route/module ownership for workflow surfaces vs case-action mutation surfaces before merging broader operator-console work.
4. Avoid letting search/export surfaces become a second canonical query model; `WorkItem` field/query definitions should stay singular.
