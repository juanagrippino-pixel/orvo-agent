# 2026-06-17 Architecture Alignment Review

**Reviewer:** Architecture Review Board  
**Date:** 2026-06-17  
**Scope:** Read-only architecture review of recent Orvo Brain branches and current control-plane code. No code was edited by this review except this report. No cron jobs were created, updated, paused, resumed, or removed. No push, merge, or deploy was performed.  
**Primary reviewed HEAD:** `8a0b7c66` / `feat/orvo-brain-control-plane` — `fix: apply as_of clock to SLA status JQL filters`.  
**Test signal used:** `pytest -q` passed on the reviewed worktree.

## Executive verdict

| Area | Alignment verdict | Status |
|---|---:|---|
| OperationalCase / WorkItem as Atlassian-like work management | Strong alignment, but workflow schemes are still implicit rather than first-class. | **Merge-ready with follow-ups** |
| Semantic registry as canonical source of truth | Good canonical gating in runtime/case/report paths; drift risk remains across case-family/action/report metadata. | **Needs follow-up, not blocker** |
| Connector platform separation | Registry-level separation exists; concrete adapters still have mixed adapter/service/storage responsibilities. | **Needs follow-up** |
| Workflow automation idempotency/approval/audit | Core pieces exist and are integrated; external side-effect atomicity and approval policy depth need tests. | **Merge-ready with follow-ups** |
| Trust/Admin/Security RBAC/audit/secret boundaries | Business scoping, RBAC, redaction, and secret-ref boundaries exist; admin role matrix and audit retention are incomplete. | **Needs follow-up** |
| Destructive Claude branches | Diverge by deleting platform modules and adding large monoliths. | **Needs-work / no merge** |

## 1. OperationalCase / WorkItem: Atlassian/Jira pattern alignment

### What is aligned

The current code has moved meaningfully toward an Atlassian-like operating model:

- `OperationalCase` carries project/work-management semantics: `project_key`, `case_type`, `status`, `status_category`, `priority`, `severity`, `assignee`, owner-visible policy, and timeline events.
- `WorkItem` supports issue-like fields: project key, issue type, status category, assignee, assignment activity, comment activity, evidence lineage, SLA due/as-of fields, owner-visible policy, and security level.
- Built-in case views now use a JQL-style allowlist registry with `order_by` validation and route-owned project scope checks.
- The recent `as_of` clock fix makes SLA status classification deterministic instead of relying on wall-clock evaluation at render time.
- Timeline events preserve actor taxonomy and evidence lineage, which is important for auditability and owner/operator trust.

### Remaining gaps

1. **Workflow schemes are not yet first-class.**  
   Status categories and SLA fields exist, but there is no explicit workflow scheme object that defines valid transitions, validators, post-functions, and permissions by case type.

2. **JQL is an allowlist parser, not a full query language.**  
   This is acceptable for MVP safety, but it should be named honestly in docs/contracts: “JQL-like filtering” or “JQL subset.” Full JQL semantics, functions, and nested clauses are not present.

3. **Project hierarchy is shallow.**  
   The current model has `project_key`, but not full Atlassian hierarchy such as epic/link/issue relationships, versions, components, or custom fields.

4. **Transition audit is partial.**  
   Priority/severity changes are audited in timeline, but full transition history should be enforced by the workflow engine rather than by ad hoc case actions.

### Recommendation

Treat the current work-management branch as aligned with the sellable Atlassian-like direction, but require a follow-up `workflow-schemes-contract` before claiming full Jira parity.

## 2. Semantic registry as canonical source of truth

### What is aligned

The current architecture uses semantic registries as gating surfaces:

- `MetricRegistry` is used to validate report metrics and case detections.
- Case upserts validate case-family metric metadata.
- Built-in case view JQL is guarded by a registry contract.
- Action catalog gating prevents workflow mutations from using uncataloged action keys.
- The runtime path still routes through connector registry, metric registry, run ledger, cases, and projections rather than letting reports become state.

### Remaining gaps

1. **Case-family, action, and metric registries are related but not unified.**  
   The semantic layer is canonical in practice, but there is no single registry manifest that cross-references case family → metric → action → operator view.

2. **Source-scope metadata is still easy to drift.**  
   Several branches repeatedly hardened “case metric registry metadata by source,” which indicates the risk is understood but not fully eliminated by design.

3. **Docs should distinguish canonical metric from derived projection.**  
   Operator views and WhatsApp projections must continue to be treated as derived, not as state.

### Recommendation

Add a semantic registry manifest contract that lists case family, required metrics, allowed actions, and built-in views in one audited artifact. This is not a blocker for merge, but it is the next architectural control to prevent drift.

## 3. Connector platform: adapter/service/storage separation

### What is aligned

The connector registry now centralizes:

- Connector identity and readiness.
- Adapter factory paths.
- Service/storage references.
- Secret references.
- Runtime execution metadata.

This is the right platform direction and avoids connector-specific shortcuts in reports or dispatch.

### Remaining gaps

1. **Concrete adapters are not consistently split.**  
   Tiendanube and Google Sheets adapters still mix HTTP extraction, normalization, and persistence responsibilities in adapter files. The registry supports separation, but the concrete implementations do not fully demonstrate it.

2. **No formal adapter interface/base class.**  
   The registry validates factory paths but does not enforce a typed adapter contract through a base class or protocol.

3. **Connector certification is mostly docs/tests, not runtime enforcement.**  
   The design has connector certification snapshots, but runtime should fail closed if a connector does not implement the expected adapter/service/storage boundaries.

### Recommendation

Keep the registry design, but add a connector platform follow-up that introduces an explicit adapter protocol/base class and splits at least one production adapter into adapter/service/storage modules.

## 4. Workflow automation: idempotency, approval gates, audit

### What is aligned

The current workflow surface includes the required control-plane pieces:

- Approval queue scoped by case/action.
- Execution queue with action-key filters.
- Workflow action ledger.
- Workflow action audit projections.
- Action catalog whitelist.
- Approval-gated action boundaries.
- Idempotency fields on manual case actions.

This is aligned with the requirement that workflow automation should be deterministic and auditable.

### Remaining gaps

1. **External side-effect atomicity is not proven.**  
   The ledger/queue/audit model exists, but the system still needs tests or a simulator showing that a failed external side effect does not leave the workflow in an inconsistent state.

2. **Approval policy depth is limited.**  
   Approval gates exist, but per-role approval requirements, escalation, and multi-approver policy are not yet first-class.

3. **Ledger uniqueness/atomicity should be stronger.**  
   Idempotency is present, but the persistence layer should enforce uniqueness constraints for idempotency keys and execution records.

### Recommendation

Merge the current workflow automation direction, but require a follow-up workflow simulation test covering: duplicate request, approval denial, external failure, and replay after success.

## 5. Trust/Admin/Security: RBAC, audit trail, secret boundaries

### What is aligned

The current code includes important trust boundaries:

- Operator auth and permission checks.
- Business-scoped operator routes.
- Audit exports scoped by business.
- Redaction for secret-shaped ids, auth headers, URL userinfo, and public payloads.
- Secret-ref handling in connector execution.
- Admin/operator distinctions in audit/action surfaces.

### Remaining gaps

1. **RBAC matrix is implicit.**  
   Permissions exist in code, but there is no single admin-facing RBAC matrix tying roles to routes, actions, approvals, and audit exports.

2. **Audit retention and export controls are incomplete.**  
   Audit records exist, but retention, tamper-evidence, export approval, and legal hold are not yet specified.

3. **Secret rotation boundaries need documentation.**  
   Secret refs and redaction are present, but the admin workflow for rotation, revocation, and connector credential replacement is not yet explicit.

### Recommendation

Add a trust/admin security contract that defines role matrix, audit retention, export approval, secret rotation, and admin surface boundaries.

## Branch-level observations

### Merge-ready / already integrated

- `feat/orvo-brain-control-plane` / `8a0b7c66`  
  Current integration branch is aligned with the product direction. It is ahead of `main` and matches its remote. Tests passed.
- `N2-Pro/connector-platform`  
  Good registry-level platform work; integrated into current branch. Follow-up needed on concrete adapter separation.
- `N2-Pro/workflow-automation`  
  Good workflow control-plane work; integrated into current branch. Follow-up needed on external side-effect simulation and ledger atomicity.
- `n2-pro-work-management`  
  Strong Atlassian-like work-management alignment; integrated into current branch. Follow-up needed on workflow schemes.
- `N2-Pro/search-analytics`  
  Useful case query metadata; integrated into current branch. Follow-up needed on semantic manifest governance.

### Needs rebase or integration

- `N2-Pro/operator-surfaces`  
  Diverged from current HEAD and contains large surface changes. Needs rebase and conflict review before merge.
- `N2-Pro/trust-admin-security`  
  Diverged from current HEAD. Needs rebase and RBAC/audit contract follow-up.
- `N2-Pro/edge-developer-platform`  
  Large gateway contract addition; not integrated into current HEAD. Needs a focused review against connector/service boundaries.
- `N2-Pro/service-management`  
  Large new service-management module; needs rebase and case-family/action-catalog alignment.
- `qa/2026-06-17-control-plane-safety`  
  Test-only safety work, but diverged from current HEAD. Likely superseded or needs rebase.
- `n2/build-loop-20260617035630`  
  Redaction test follow-up; diverged from current HEAD. Needs rebase or should be folded into current branch.

### Needs-work / do not merge as-is

- `claude/qa-review`  
  Destructive diff from `main`: many platform modules deleted, large monolithic operator surface added. Does not preserve connector registry, metric registry, operational cases, or audit contracts.
- `claude/runtime-semantics`  
  Same destructive pattern as `claude/qa-review`; deletes core platform structure and collapses responsibilities.
- `claude/case-workflow`  
  Adds a very large monolithic `operator_api.py` while deleting the modular operator API and platform contracts. This is the opposite of the desired Atlassian-like control plane.

## Final ARB recommendation

Proceed with the current `feat/orvo-brain-control-plane` integration train, but only after documenting the follow-up contracts above. Do not merge the destructive Claude branches. Rebase or retire the divergent N2-Pro branches before they are considered merge-ready.
