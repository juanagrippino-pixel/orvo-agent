# 2026-06-17 Branch Readiness Matrix

**Reviewer:** Architecture Review Board  
**Date:** 2026-06-17  
**Purpose:** Read-only branch readiness matrix for Orvo Brain control-plane architecture. This report does not modify code, cron jobs, deployments, or remote refs.

## Review method

- Reviewed current integration branch `feat/orvo-brain-control-plane` at `8a0b7c66`.
- Compared recent local/remote branches against `main` and current HEAD using `git diff --stat`.
- Reviewed current code paths for OperationalCase/WorkItem, semantic registry, connector registry, workflow automation, RBAC/audit/redaction.
- Ran `pytest -q` on the reviewed worktree; it passed.

## Branch matrix

| Branch | HEAD | Architecture verdict | Merge recommendation | Notes |
|---|---:|---|---|---|
| `feat/orvo-brain-control-plane` | `8a0b7c66` | Strong alignment with control-plane direction. Work management, JQL-like views, metric gating, workflow automation, and trust boundaries are integrated. | **Merge-ready for next integration train** | Matches remote. Tests passed. Needs follow-up contracts for workflow schemes, semantic manifest, connector adapter protocols, and RBAC matrix. |
| `N2-Pro/connector-platform` | `ad816955` | Good connector registry/platform alignment. | **Already integrated / merge-ready** | Current HEAD includes this direction. Follow-up: concrete adapter/service/storage split and typed adapter protocol. |
| `N2-Pro/workflow-automation` | `bbb9808e` | Good workflow automation alignment. | **Already integrated / merge-ready** | Current HEAD includes this direction. Follow-up: external side-effect simulation, ledger atomicity, approval policy depth. |
| `n2-pro-work-management` | `60dd6679` | Strong Atlassian-like work-management alignment. | **Already integrated / merge-ready** | Current HEAD includes this direction. Follow-up: first-class workflow schemes and JQL-subset documentation. |
| `N2-Pro/search-analytics` | `bb5d105e` | Useful case query metadata, aligned with operator surfaces. | **Already integrated / merge-ready** | Current HEAD includes this direction. Follow-up: semantic manifest governance. |
| `N2-Pro/operator-surfaces` | `53219815` | Valuable direction but diverged from current HEAD. | **Needs rebase before merge** | Large diff vs current HEAD; review for duplicated operator surfaces and owner/operator projection boundaries. |
| `N2-Pro/trust-admin-security` | `39c1ca95` | Important trust/admin direction but diverged. | **Needs rebase before merge** | Large diff vs current HEAD; needs RBAC matrix, audit retention/export controls, secret rotation contract. |
| `N2-Pro/edge-developer-platform` | `dac56f3e` | Adds gateway contracts; potential platform value. | **Needs focused review/rebase** | Large new `gateway_contracts.py`; not integrated into current HEAD. Review against connector/service boundaries before merge. |
| `N2-Pro/service-management` | `ae497d68` | Service-management queue summary is strategically plausible but not integrated. | **Needs rebase and case-family alignment** | Large new service-management module; must align with case-family catalog and action catalog. |
| `qa/2026-06-17-control-plane-safety` | `5df5d34e` | Test-only safety work. | **Rebase or retire** | Diverged from current HEAD; likely superseded by current tests or needs rebase. |
| `n2/build-loop-20260617035630` | `f8ad5f48` | Redaction safety follow-up. | **Rebase or fold into current branch** | Diverged from current HEAD; useful but should not be merged as stale standalone branch. |
| `claude/qa-review` | `13f1dc48` | Architectural regression. | **Do not merge** | Destructive diff from `main`: deletes many platform modules and adds monolithic operator API. Breaks connector registry, metric registry, operational cases, audit separation. |
| `claude/runtime-semantics` | `36e55806` | Architectural regression. | **Do not merge** | Same destructive pattern as `claude/qa-review`; collapses platform responsibilities. |
| `claude/case-workflow` | `47ef9226` | Architectural regression. | **Do not merge** | Adds very large monolithic `operator_api.py` while deleting modular platform contracts. Opposite of Atlassian-like control plane. |

## Readiness categories

### Merge-ready / already integrated

- `feat/orvo-brain-control-plane`
- `N2-Pro/connector-platform`
- `N2-Pro/workflow-automation`
- `n2-pro-work-management`
- `N2-Pro/search-analytics`

### Needs rebase or focused review

- `N2-Pro/operator-surfaces`
- `N2-Pro/trust-admin-security`
- `N2-Pro/edge-developer-platform`
- `N2-Pro/service-management`
- `qa/2026-06-17-control-plane-safety`
- `n2/build-loop-20260617035630`

### Needs-work / reject as-is

- `claude/qa-review`
- `claude/runtime-semantics`
- `claude/case-workflow`

## Required follow-up contracts before next major merge

1. Workflow schemes: status transitions, validators, post-functions, permissions by case type.
2. Semantic manifest: case family → metrics → actions → built-in views in one audited registry.
3. Connector adapter protocol: typed adapter/service/storage boundaries and runtime certification.
4. Workflow simulation: duplicate request, approval denial, external failure, replay after success.
5. Trust/admin contract: RBAC matrix, audit retention/export controls, secret rotation, admin surface boundaries.

## Test result

`pytest -q` passed on `feat/orvo-brain-control-plane` at `8a0b7c66`.
