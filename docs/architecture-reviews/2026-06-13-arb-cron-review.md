# Architecture Review Board — 2026-06-13 (cron)

**Base reviewed:** `feat/orvo-brain-control-plane`  
**Recent branches reviewed:**
- `N2-Pro/connector-platform`
- `N2-Pro/workflow-automation`
- `N2-Pro/trust-admin-security`
- `n2-pro-work-management`
- `N2-Pro/operator-surfaces`
- `n2/metric-registry-source-gate-20260613` *(already absorbed into base)*
- `n2/metric-registry-case-gate-20260613` *(already absorbed into base)*

## Executive summary

The repo is still aligned with the Orvo control-plane direction: `OperationalCase` is the durable issue object, `WorkItem` is the projection layer, workflow automation is ledger-backed, and connector/runtime boundaries remain intact.

The biggest update versus earlier same-day reviews is that **semantic-registry case/source gating is now present on the persisted case-upsert path**. The remaining semantic gap is narrower: report/surface validation helpers exist, but the registry is not yet uniformly enforced across every non-persistent preview/projection path.

## 1) OperationalCase / WorkItem vs Atlassian patterns

### What already aligns
Base branch code already carries the right Atlassian/Jira-like primitives:
- `OperationalCase` as the durable issue record in `app/brain/operational_cases.py`
- project projection, issue type, status category, and query-field registry in `app/brain/work_items.py`
- JQL-lite parsing, built-in views, and faceting in `app/brain/operator_views.py`

That gives Orvo a real issue/work model rather than a report-only alert list.

### Best recent branch in this area
`n2-pro-work-management` is the strongest architectural step forward.

It adds operator-grade work semantics without creating a second source of truth:
- `sla_target_seconds`
- `due_at`
- `owner_visible`
- `latest_evidence_at`
- timeline/comment/event fields
- `sla_status` and richer query/facet surface

This is the right direction: **OperationalCase stays canonical; WorkItem gets richer projections.**

### Remaining Atlassian gap
Still missing for a fuller Atlassian/Jira shape:
- persisted saved filters/shared views
- tenant/project-configurable workflow schemes
- tenant/project-configurable issue-type schemes
- board/rank/backlog configuration
- project-scoped permission schemes

## 2) Semantic registry as canonical source of truth

### What is now strong
The semantic registry remains the canonical definition layer in `app/brain/semantics/metric_registry.py`, and recent metric-registry gate branches appear already absorbed into base.

Important current-state evidence:
- connector certification composes registry validation in `app/brain/connector_registry.py`
- persisted case upserts call `detect_cases_from_report(... metric_registry_mode="enforced")` via `upsert_cases_from_report` in `app/brain/operational_cases.py`
- case detection now refuses case creation when scoped report metrics are unknown or invalid for the case family

### Remaining gap
The registry is **not yet uniformly enforced everywhere**:
- `detect_cases_from_report()` still defaults to `metric_registry_mode="advisory"`
- `_metric_registry_metadata()` still attaches advisory diagnostics to detections
- report/surface helpers such as `validate_report_metric_objects()` / `validate_surface_metric_objects()` exist but are not yet obvious repo-wide enforcement points

**Board call:** no metric-registry drift branch was found, but the next hardening step is repo-wide enforcement consistency, not a new registry design.

## 3) Connector platform separation: adapter / service / storage

The connector architecture remains clean:
- registry contract: `app/brain/connector_registry.py`
- runtime/orchestration: `app/brain/runtime.py`
- secret boundary: `app/brain/secret_refs.py`
- persistence boundary: `app/brain/storage.py`
- operator projection: `app/brain/operator_api/connectors.py`

`N2-Pro/connector-platform` stays on the right side of the boundary. It mostly:
- hardens `secret://` handle validation
- refines connector health-event certification
- exposes executor/runtime metadata in readiness surfaces

It does **not** collapse adapter/service/storage layers together.

## 4) Workflow automation: idempotency, approval gates, audit

This area is architecturally healthy.

Base branch already has the right control-plane model:
- durable idempotency keys in `app/brain/workflow_action_ledger.py`
- approval and execution state as first-class fields
- dry-run planning in `app/brain/workflow_automation.py`
- read-only approval/audit projections in `app/brain/workflow_approval_queue.py` and `app/brain/workflow_action_audit.py`

`N2-Pro/workflow-automation` improves the model correctly by adding internal read surfaces for:
- approval queue
- execution queue
- action audit events
- case/event-type filtering

It adds observability on top of the ledger instead of inventing a shadow automation state machine.

## 5) Trust / Admin / Security

Current trust posture is serviceable but still internal/coarse.

### What is working
- bearer-token internal boundary in `app/http/internal_brain/common.py`
- role/permission model in `app/brain/operator_auth.py`
- durable audit store in `app/brain/operator_audit.py`
- redaction-safe audit scope in `app/brain/audit_scope.py`

### Branch assessment
`N2-Pro/trust-admin-security` is aligned hardening work:
- explicit-global-scope checks become stricter for cross-business/admin surfaces
- nested `business_id` labels get collapsed when secret-shaped
- audit exports redact more aggressively and safely

### Remaining gap
RBAC is still only:
- `viewer`
- `operator`
- `admin`

That is enough for internal tooling, but not for a future tenant-admin / project-admin control plane.

## 6) Operator surfaces and strategic alignment

`N2-Pro/operator-surfaces` is directionally right and operationally too broad.

### Why it aligns
- console-first product surface
- owner brief and suggested actions
- recent activity / top-case projections
- expanded internal operator coverage

### Why it needs work
The branch is too large and starts fragmenting the API into many specialized routes/files:
- `recent_activity`
- `recent_cases`
- `commented_cases`
- `updated_cases`
- multiple `recently_*` endpoint families

That risks drifting from the stronger underlying pattern already present in `operator_views.py`: shared projection + query/facet semantics.

**Board call:** split before merge. Land shared activity primitives first, then smaller surface slices.

## Branch verdicts

| Branch | Verdict | Notes |
|---|---|---|
| `N2-Pro/connector-platform` | **Merge-ready** | Small, additive, boundary-respecting connector/runtime projection work. |
| `N2-Pro/workflow-automation` | **Merge-ready candidate** | Strong ledger-first fit; rebase needed, not redesign. |
| `N2-Pro/trust-admin-security` | **Merge-ready candidate** | Good hardening branch; still sits on coarse RBAC. |
| `n2-pro-work-management` | **Merge-ready candidate** | Best Atlassian-pattern uplift; rebase needed. |
| `N2-Pro/operator-surfaces` | **Needs work** | Too broad; split around shared activity/query primitives. |
| `n2/metric-registry-source-gate-20260613` | **Absorbed into base** | No separate branch decision needed. |
| `n2/metric-registry-case-gate-20260613` | **Absorbed into base** | No separate branch decision needed. |

## Recommended merge sequence

1. `N2-Pro/connector-platform`
2. `N2-Pro/trust-admin-security`
3. `n2-pro-work-management`
4. `N2-Pro/workflow-automation`
5. Split `N2-Pro/operator-surfaces` and re-review in smaller branches

## Highest-priority repo-level follow-ups

1. **Finish semantic-registry enforcement rollout**
   - Keep enforced case gating.
   - Add explicit validation hooks for report/surface preview paths.

2. **Land work-management semantics before UI sprawl**
   - Merge `n2-pro-work-management` before broad operator-surface growth.

3. **Keep workflow ledger canonical**
   - Continue building read surfaces and governed executors on top of `workflow_action_ledger.py` only.

4. **Move from coarse internal roles to scoped admin contracts**
   - Plan project/tenant-scoped permissions before externalizing broader operator/admin surfaces.
