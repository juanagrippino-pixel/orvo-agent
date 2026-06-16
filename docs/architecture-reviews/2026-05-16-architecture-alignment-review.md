# Architecture Review — Orvo Brain Control Plane Alignment

- **Date:** 2026-05-16
- **Reviewer role:** Architecture Review Board
- **Scope:** Read-only review of recent branches and current control-plane code. No cron, push, merge, or deploy actions were performed.
- **Current branch:** `feat/orvo-brain-control-plane`
- **Reviewed commit:** `2221c718`
- **Test verification:** `pytest -q` → `1622 passed in 25.10s`

## Executive summary

The recent work is strongly aligned with the accepted Orvo Brain direction: a deterministic, Atlassian-like operations control plane for LatAm D2C commerce, centered on `OperationalCase` as the durable source of truth, a semantic metric registry as canonical evidence vocabulary, connector registry execution, workflow/action ledgers, operator projections, and internal audit/security boundaries.

Most reviewed branches are **merge-ready from an architecture perspective**, with two categories of caveats:

1. **Needs-work before merge:** `claude/case-workflow` has a path/design conflict with the current `app/brain/operator_api/` package shape; `N2-Pro/service-management` needs SLA/state metadata promoted into canonical workflow/timeline semantics before it becomes more than a projection; `N2-Pro/edge-developer-platform` is useful but is currently a gateway contract/catalog layer, not enforcement.
2. **Trivial hygiene / integration caveat:** `N2-Pro/search-analytics` has trailing whitespace in GTM/research docs and should be cleaned before merge. Its code direction is aligned.

The main architectural risk is not strategic misalignment; it is **duplication at the boundary layer**: idempotency, audit, and route-policy concepts exist in several modules, and the gateway branch is not yet wired into enforcement. Keep these as centralized contracts and wire enforcement through one path.

## Branch readiness matrix

| Branch | Readiness | Architectural verdict |
|---|---:|---|
| `N2-Pro/operator-surfaces` | Merge-ready | Strong owner/operator projection branch. Keeps cases as source of truth, uses canonical case/workflow metadata, and avoids mutating workflow state from projections. Needs normal CI and route coverage after merge. |
| `claude/case-workflow` | Needs-work | Good WorkItem/JQL-lite ideas, but the file path `app/brain/operator_api.py` conflicts with the current `app/brain/operator_api/` package and the branch is not integrated into internal routes/auth/audit. Refactor into current package before merge. |
| `n2-pro-work-management` | Merge-ready | Good foundation: project key, issue type, workflow/status category, priority bracket, JQL-lite fields. Superseded/enriched by `N2-Pro/search-analytics`; merge only if still needed independently. |
| `N2-Pro/search-analytics` | Merge-ready after hygiene cleanup | Strong alignment: built-in case views, JQL-lite parser, facets, CSV export, redaction, route auth. Clean trailing whitespace in GTM/research docs before merge. |
| `N2-Pro/connector-platform` | Merge-ready | Good connector platform split: registry contract, readiness, execution ledger, storage path. Keeps connector metadata separate from metric semantics. |
| `N2-Pro/trust-admin-security` | Merge-ready | Good RBAC, audit, and redaction boundaries. Admin provisioning/tenant management remains future work, but the branch does not weaken current security. |
| `N2-Pro/workflow-automation` | Merge-ready / already represented | Workflow/action projection, approval queue, execution queue, and action ledger are aligned with deterministic workflow automation. Route-level idempotency still needs central enforcement. |
| `N2-Pro/service-management` | Needs-work before merge | Service projections are strategically useful, but SLA/waiting-on state is metadata-driven and should be promoted to canonical workflow/timeline semantics if it affects owner-facing commitments. |
| `N2-Pro/edge-developer-platform` | Needs-work for enforcement, merge-ready as contracts | Gateway contracts/catalog are useful for idempotency, auth shape, rate-limit policy, and audit provenance. Not yet integrated as middleware enforcement, so it should not be counted as completed runtime security. |
| `qa/builtin-case-view-contract-20260616` | Merge-ready / already integrated | Good contract tests around built-in case views and action catalog whitelist. |
| `qa/n2-pro-action-key-whitelist-regression` | Merge-ready / already integrated | Good regression coverage for action-key whitelist behavior. |

## 1. OperationalCase / WorkItem Atlassian pattern alignment

### What aligns

- `OperationalCase` remains the durable source of truth. `WorkItem` is a projection, not a parallel task store.
- Work management now has Jira-like concepts:
  - project key/workspace projection,
  - issue type mapped to `OperationalCaseType`,
  - workflow scheme/workflow ID metadata,
  - status category mapping,
  - priority bracket projection,
  - built-in read-only views,
  - JQL-lite query and facet metadata.
- `OperationalCase` exposes explicit manual and system transitions. This supports deterministic workflow behavior without letting UI text or report copy become state.
- JQL-lite is intentionally allowlisted and in-memory over `OperationalCaseStore.list_cases`; it does not generate SQL and does not expose tenant-controlled schema expansion.

### Gaps / risks

- The JQL-lite implementation is not a full JQL grammar. It supports the current product surface, but it should remain explicitly named as JQL-lite to avoid promising Jira parity.
- There is no tenant-customizable workflow concept, which is correct for the deterministic MVP, but the workflow definition should stay in code/contract form and not drift into report copy.
- Board/swimlane abstractions are still implicit. If the product grows toward true Jira-like boards, add a small board/query/view contract rather than scattering sort/group logic across endpoints.
- `claude/case-workflow` needs refactoring into the current operator API package before it can be considered mergeable.

**Verdict:** Strong alignment. The code correctly uses OperationalCase as source of truth and WorkItem as a read-only semantic projection.

## 2. Semantic registry as canonical source of truth

### What aligns

- `MetricRegistry` remains the canonical metric/evidence vocabulary. The reviewed branches did not introduce LLM-driven metrics or ad hoc metric aliases.
- Case families and action keys continue to be validated through contracts.
- WorkItem query fields are explicitly separated from metric semantics: they describe case/workflow projection fields, not business metric definitions.
- Evidence snapshots remain tied to runs/connectors and are projected into case views, not copied into independent truth stores.

### Gaps / risks

- `N2-Pro/service-management` introduces service/SLA-style waiting state based on case metadata. If this becomes owner-facing, it should be represented through canonical case transitions/timeline events rather than implicit metadata.
- Export/facet/query layers expose derived fields such as `degraded`, `source_connector`, `evidence_snapshot_count`, and `latest_evidence_at`. These are acceptable projections, but their definitions should stay centralized in projection helpers to avoid drift.

**Verdict:** Metric registry remains canonical. No material metric drift detected. Guard against future SLA/service metadata becoming a second source of truth.

## 3. Connector platform: adapter/service/storage separation

### What aligns

- Connector registry code separates connector contract metadata, readiness, execution ledger, and SQLite storage.
- Existing adapters remain outside the registry core, which is the right boundary.
- Connector readiness is deterministic and auditable through run/execution ledger paths.
- Internal readiness routes return projections rather than mutating connector state.

### Gaps / risks

- The registry still carries some orchestration responsibilities. This is acceptable for the current slice, but future connector services should have a clearer service-layer interface for execution, health, and storage.
- Connector secret handling is improving through redaction, but secret rotation, per-connector scopes, and admin-facing credential lifecycle are not yet a full product surface.
- Gateway idempotency/rate-limit contracts are not yet enforced at the middleware layer.

**Verdict:** Merge-ready. The connector platform is moving in the right direction without bypassing the compiled runtime or metric registry.

## 4. Workflow automation: idempotency, approval gates, audit

### What aligns

- Action catalog validation prevents arbitrary action-key execution.
- Workflow approval and execution queues provide deterministic approval-gate structure.
- Workflow action ledger provides idempotency-key handling and durable action records.
- Case actions update OperationalCase through explicit transition paths and emit timeline/audit events.
- Operator projections are read-only and do not become workflow state.

### Gaps / risks

- Idempotency exists in action execution and gateway contracts, but route-level idempotency is not yet enforced through one centralized middleware path.
- The gateway branch adds a useful route-policy contract but does not yet enforce it. Until wired, it is documentation/contract hardening, not a security control.
- There is no full durable workflow engine. Current automation is deterministic and sufficient for the MVP, but retry/backoff, compensation, and long-running orchestration should be introduced through the existing ledger/queue contracts.

**Verdict:** Strong alignment. Needs follow-up to centralize gateway enforcement and avoid duplicate idempotency paths.

## 5. Trust/Admin/Security: RBAC, audit trail, secret boundaries

### What aligns

- Internal operator auth now has role/permission concepts: viewer, operator, admin.
- Business scope checks are present for tenant-scoped routes.
- Audit read permission is separated from case mutation permission.
- Operator audit export is bounded by retention and redaction.
- Redaction helpers collapse credential-shaped actor refs, headers, request IDs, idempotency keys, and business IDs where appropriate.
- Internal routes use safe envelopes and permission checks.

### Gaps / risks

- There is no full tenant/admin provisioning UI or organization-level RBAC inheritance model yet.
- Secret boundaries are good for accidental leakage, but not a complete credential lifecycle system: rotation, revocation, per-connector admin scopes, and audit retention policy ownership remain future work.
- Audit logs are durable and redacted, but not tamper-evident. That is acceptable for MVP but should be called out if compliance claims are made.
- Gateway auth/rate-limit policies are not yet enforced.

**Verdict:** Merge-ready for the current MVP security posture, with clear follow-up needed for admin provisioning and middleware enforcement.

## Strategic alignment

The reviewed direction supports the sellable Orvo Brain wedge:

- It feels like an operations control plane, not a generic dashboard or chatbot.
- It keeps the app/operator console as the primary control surface.
- It preserves deterministic evidence-backed cases and workflows.
- It avoids LLM-driven metrics or state transitions.
- It strengthens Jira-like work management while staying bounded to Orvo's D2C commerce domain.

The biggest strategic caution is scope creep: gateway, service management, analytics, and admin surfaces are valuable, but they should remain thin contracts/projections over the core control plane. Do not let them become parallel systems of record.

## Recommended next actions

1. Refactor or retire `claude/case-workflow` into the current `app/brain/operator_api/` package structure before merge.
2. Clean trailing whitespace in `N2-Pro/search-analytics` docs before merge.
3. Promote service/SLA waiting state in `N2-Pro/service-management` to canonical workflow/timeline semantics if it affects owner-facing commitments.
4. Wire `N2-Pro/edge-developer-platform` gateway contracts into actual middleware enforcement, or label the branch as contracts-only.
5. Add a small architecture note defining the single ownership path for idempotency and audit provenance: route gateway → action ledger → operator audit → case timeline.

## Files reviewed

Key files/modules reviewed included:

- `app/brain/operational_cases.py`
- `app/brain/work_items.py`
- `app/brain/operator_views.py`
- `app/brain/operator_api/`
- `app/brain/connector_registry.py`
- `app/brain/run_ledger.py`
- `app/brain/workflow_action_ledger.py`
- `app/brain/workflow_automation.py`
- `app/brain/workflow_approval_queue.py`
- `app/brain/workflow_execution_queue.py`
- `app/brain/action_catalog.py`
- `app/brain/operator_auth.py`
- `app/brain/operator_audit.py`
- `app/brain/audit_scope.py`
- `app/brain/security/redaction.py`
- `app/brain/semantics/metric_registry.py`
- `app/http/internal_brain/`
- `tests/contracts/`
- `tests/invariants/`
- representative operator case, workflow, connector, audit, and auth tests.

## Final ARB decision

**Overall:** merge the aligned control-plane branches after addressing the specific caveats above. The architecture is moving toward a coherent Atlassian-like PyME operating control plane with strong deterministic boundaries, canonical semantic evidence, and credible operator/admin surfaces.
