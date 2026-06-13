# Branch Readiness Matrix — Architecture Review

**Date:** 2026-06-13  
**Base:** `feat/orvo-brain-control-plane`  
**Review type:** Read-only architecture review. No cron jobs changed. No push, merge, or deploy performed.

## Summary

| Branch | Ahead/behind vs base | Diff shape | Verdict | Why |
|---|---:|---|---|---|
| `N2-Pro/connector-platform` | `+3 / -0` | `2 files, +26, -0` | **Merge-ready** | Small additive projection on top of an already well-separated connector/runtime contract. |
| `N2-Pro/workflow-automation` | `+5 / -62` | `8 files, +663, -19` | **Merge-ready candidate** | Strong fit with ledger-first automation, approval queue, execution queue, and audit projections; needs rebase, not redesign. |
| `N2-Pro/trust-admin-security` | `+5 / -62` | `6 files, +239, -17` | **Merge-ready candidate** | Security hardening is scoped, additive, and aligned with internal operator audit/redaction boundaries; needs rebase. |
| `n2-pro-work-management` | `+5 / -10` | `7 files, +719, -15` | **Merge-ready candidate** | Best Atlassian-pattern improvement: SLA, due date, owner-visible policy, evidence/timeline query fields. |
| `N2-Pro/operator-surfaces` | `+58 / -65` | `55 files, +5646, -277` | **Needs work** | Product direction is right, but the branch is too broad and starts fragmenting the operator API into endpoint-per-transition surfaces. Split before merge. |

## Branch notes

### `N2-Pro/connector-platform`

**Why it aligns**
- Extends the readiness API instead of changing connector execution semantics.
- Preserves the connector registry boundary (`app/brain/connector_registry.py`) and secret-resolution boundary (`app/brain/secret_refs.py`).
- Does not bypass compiled runtime, run ledger, Operational Cases, or audit surfaces.

**Architectural caution**
- Repo-wide semantic enforcement is still not fully blocking outside connector certification; this branch does not worsen that gap.

### `N2-Pro/workflow-automation`

**Why it aligns**
- Builds on the existing workflow action ledger rather than creating a shadow automation store.
- Keeps approval, idempotency, and audit as first-class concepts via approval queue / execution queue / audit projections.
- Uses internal read permission for the new workflow projection routes, so it adds observability before expanding mutation scope.

**Why only a candidate**
- The branch is materially behind the base branch and should be rebased.
- It improves internal workflow visibility, but it does not yet introduce a broader workflow-scheme/project-scheme model.

### `N2-Pro/trust-admin-security`

**Why it aligns**
- Hardens denial semantics in internal API auth.
- Improves audit export redaction and collapses secret-shaped business labels before they enter internal API payloads.
- Reinforces conservative trust boundaries without bypassing current operator auth or audit paths.

**Why only a candidate**
- Needs rebase.
- RBAC remains coarse-grained (`viewer` / `operator` / `admin`) and internal-only; this branch is good hardening, not the final admin model.

### `n2-pro-work-management`

**Why it aligns**
- Strengthens Atlassian/Jira-like semantics already present in `OperationalCase`/`WorkItem`: project key, issue type, workflow status category, JQL-like querying.
- Adds deterministic work-management concepts that operators expect: `sla_target_seconds`, `due_at`, owner visibility, latest evidence, last event, and timeline counts.
- Keeps evidence lineage and case dedupe intact instead of inventing a parallel work-item state machine.

**Why only a candidate**
- Small rebase still needed.
- Project/workflow schemes are still code-defined rather than tenant-configurable.

### `N2-Pro/operator-surfaces`

**Why it aligns**
- Clearly follows the app/operator-console-first product direction.
- Adds useful owner brief, suggested action, runs dashboard, and recent-case projections.
- Expands tests substantially.

**Why it needs work**
- The branch is too wide for safe architectural review.
- It starts to spread the API into many `recently_*` endpoints instead of extending a smaller common activity/query surface.
- The right extraction order is: shared activity projection -> recent case views -> owner brief / suggested actions.

## Cross-branch board call

The safest merge sequence is:
1. `N2-Pro/connector-platform`
2. `N2-Pro/trust-admin-security`
3. `n2-pro-work-management`
4. `N2-Pro/workflow-automation`
5. Split `N2-Pro/operator-surfaces` into smaller branches before reconsidering merge readiness.

## Repo-wide gap still open

Across all reviewed branches, the semantic metric registry is structurally strong but not yet the full blocking source of truth for every ingestion path. The highest-priority follow-up remains tightening unknown/cross-family metric handling outside advisory mode in report/case generation paths.
