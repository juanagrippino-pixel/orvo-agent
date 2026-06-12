# Architecture Board Review — Orvo Brain Control Plane

**Date:** 2026-06-12  
**Reviewer:** Architecture Review Board  
**Current branch:** `feat/orvo-brain-control-plane`  
**Scope:** Read-only architectural review of recent local branches and current control-plane code. No cron jobs were created, updated, paused, resumed, or removed. No push, merge, or deploy was performed.

## Executive verdict

- **Merge-ready candidate:** `N2-Pro/connector-platform`
  - Additive connector/event metadata work that aligns with the compiled runtime and run-ledger contracts.
  - `git diff --check feat/orvo-brain-control-plane N2-Pro/connector-platform` passed.
  - Recommendation: treat as the best candidate for merge after a normal test pass.
- **Needs work:** `n2-pro-work-management`, `N2-Pro/workflow-automation`, `N2-Pro/trust-admin-security`, `N2-Pro/operator-surfaces`, `N2-Pro/search-analytics`
  - These branches contain useful partial ideas, but they also delete core tests, remove semantic validation, or regress evidence/audit behavior.
- **Not mergeable as reviewed:** `claude/qa-review`, `claude/runtime-semantics`, `claude/case-workflow`
  - These are broad destructive refactor branches that delete core control-plane modules, docs, and tests.

## Mission findings

### 1. OperationalCase / WorkItem alignment with Atlassian patterns

**Current branch alignment: strong.**

`app/brain/operational_cases.py` already models the core Jira/Atlassian concepts:

- Project identity via `project_key`.
- Issue type via `issue_type`.
- Workflow/status lifecycle via deterministic status transitions.
- Status categories remain canonical: `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done`, with projection metadata also exposing higher-level categories such as `review`, `blocked`, `ready`, and `skipped` where appropriate.
- Workflow definitions and deterministic transition validation are projection metadata, not tenant-custom workflow schemes.
- JQL-lite query support is centralized through WorkItem projection fields rather than endpoint-local vocabulary, covering fields such as `project_key`, `issue_type`, `status`, `priority`, `owner`, `source`, `run_id`, `case_key`, `created_at`, and `updated_at`.

**Good pattern:** `app/brain/work_items.py` remains an additive projection derived from cases, metrics, and workflow actions. It does not become a second source of truth.

**Gap:** The base branch does not yet model explicit SLA fields such as `due_at` / `sla_target_seconds`. The `n2-pro-work-management` branch adds this, but it also removes evidence attachment and deletes large test coverage, so it is not mergeable as-is.

### 2. Semantic registry as canonical source of truth

**Current branch alignment: strong.**

`app/brain/semantics/metric_registry.py` is the canonical semantic gate for emitted metrics. It validates:

- Metric keys and source/family envelopes.
- Evidence presence and source alignment.
- Value kind, money currency, and numeric/money boundaries.
- Case/report/surface/freshness metadata.
- Strict-mode validation for connector contracts.

**Regression risk in recent branches:** Several branches remove or weaken duplicate-canonical validation and delete metric validation tests. That directly threatens the “no metric drift” requirement. Any merge must preserve the registry as the only canonical source for metric semantics.

### 3. Connector platform separation: adapter / service / storage

**Current branch alignment: strong.**

`app/brain/connector_registry.py` and `app/brain/runtime.py` keep connector identity, executor metadata, required params, scopes, secret refs, rate limits, lifecycle, and emitted metric families in registry/runtime contracts rather than in adapters.

**Best recent branch:** `N2-Pro/connector-platform` extends this cleanly by adding emitted event families and execution-ledger event certification metadata. This is additive and platform-aligned.

**Regression risk:** Branches that delete connector registry tests, connector health, secret refs, or runtime tests should not be merged until those contracts are restored.

### 4. Workflow automation: idempotency, approval gates, audit

**Current branch alignment: strong.**

The current control-plane workflow layer has the right shape:

- `app/brain/workflow_action_ledger.py` records deterministic workflow action projections before side effects.
- Durable idempotency keys prevent duplicate action planning.
- Approval-required actions create approval requests and block execution.
- `app/brain/workflow_approval_queue.py` is a read-only projection with no side effects.
- `app/brain/workflow_action_audit.py` projects deterministic audit events with redaction.
- `app/brain/workflow_execution_queue.py` exposes ready/executed/failed workflow actions without mutating state.

**Regression risk:** `N2-Pro/workflow-automation` adds a useful `source_connector` list condition, but it also removes metric validation and deletes workflow/operator tests. It is not mergeable until those regressions are fixed.

### 5. Trust / Admin / Security: RBAC, audit trail, secret boundaries

**Current branch alignment: good, with room to mature.**

Current files establish the right boundaries:

- `app/brain/operator_auth.py` defines operator roles and permissions.
- `app/brain/operator_audit.py` records operator actions.
- `app/brain/audit_scope.py` scopes audit visibility.
- `app/brain/secret_refs.py` keeps secret references separate from raw values.
- `app/brain/security/redaction.py` redacts at service boundaries.

**Best recent branch:** `N2-Pro/trust-admin-security` includes a useful hardening of `audit_scope` for secret-shaped business IDs. However, it also deletes tests and weakens metric validation, so it needs cleanup before merge.

## Strategic alignment

The current branch remains aligned with the product direction: deterministic control plane, not chatbot/agent/ERP clone; connector -> normalizer -> metric registry -> cases -> workflow/audit/dispatch.

The branches that best preserve this architecture are small, additive, and contract-preserving. The branches that most threaten the product direction are broad refactor branches that delete tests and core modules instead of extending the platform.

## Merge recommendations

| Branch | Verdict | Recommendation |
|---|---:|---|
| `N2-Pro/connector-platform` | **Merge-ready candidate** | Best recent branch. Additive connector/event metadata and run-ledger work. Run full tests before merge. |
| `N2-Pro/trust-admin-security` | Needs work | Useful audit redaction hardening, but restore deleted tests and avoid metric-validation regressions. |
| `N2-Pro/operator-surfaces` | Needs work | Useful operator API additions, but deletes core tests and weakens semantic validation. |
| `N2-Pro/search-analytics` | Needs work | Useful search surfaces, but deletes tests and core modules. |
| `N2-Pro/workflow-automation` | Needs work | Useful workflow condition work, but deletes tests and weakens metric validation. |
| `n2-pro-work-management` | Needs work | Useful SLA idea, but removes evidence attachment and deletes tests. |
| `claude/qa-review` | Not mergeable | Destructive refactor; deletes core control-plane files and docs. |
| `claude/runtime-semantics` | Not mergeable | Destructive refactor; deletes metric/runtime/test coverage. |
| `claude/case-workflow` | Not mergeable | Destructive refactor; deletes cases/workflow/operator surfaces. |

## Required fixes before merge

1. Restore all deleted tests in branches that remove coverage.
2. Preserve `app/brain/semantics/metric_registry.py` as the canonical metric source of truth.
3. Keep `WorkItem` as a projection, not a workflow state source.
4. Preserve evidence attachment and metric validation paths.
5. Preserve zero-side-effect approval queue and audit projection behavior.
6. Preserve secret reference and redaction boundaries.
7. Avoid deleting operator API modules wholesale; split by responsibility rather than collapsing.
8. If adding SLA fields, update cases, work items, query fields, and tests together.

## Notes / risks

- The most dangerous pattern in recent branches is “feature work + wholesale deletion of tests/core modules.”
- The safest architectural direction is small additive branches that extend contracts and projections without removing existing control-plane guarantees.
- `N2-Pro/connector-platform` is the only reviewed branch that appears to follow that pattern consistently.
