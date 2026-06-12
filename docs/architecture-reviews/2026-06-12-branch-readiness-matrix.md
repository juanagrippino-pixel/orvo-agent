# Branch Readiness Matrix — Architecture Review

**Date:** 2026-06-12  
**Base:** `feat/orvo-brain-control-plane`  
**Review type:** Read-only architecture review. No cron jobs changed. No push, merge, or deploy performed.

## Summary

| Branch | Diff shape | Architectural alignment | Readiness | Key reason |
|---|---:|---|---|---|
| `N2-Pro/connector-platform` | `5 files, +209, -3` | Strong | **Merge-ready candidate** | Additive connector event families and run-ledger event certification; clean diff check. |
| `N2-Pro/trust-admin-security` | Small security/audit change plus deletions | Partial | Needs work | Useful audit redaction hardening, but deletes tests and weakens metric validation. |
| `N2-Pro/operator-surfaces` | Adds operator API surfaces plus deletions | Partial | Needs work | Useful console-first surfaces, but deletes core tests and weakens semantic validation. |
| `N2-Pro/search-analytics` | Adds search surfaces plus deletions | Partial | Needs work | Useful operator search work, but deletes tests and core modules. |
| `N2-Pro/workflow-automation` | Adds workflow condition plus deletions | Partial | Needs work | Useful `source_connector` list matching, but deletes workflow/operator tests and metric validation. |
| `n2-pro-work-management` | Adds SLA/work-item projection plus deletions | Partial | Needs work | Useful SLA direction, but removes evidence attachment and deletes tests. |
| `claude/qa-review` | Large destructive refactor | Poor | Not mergeable | Deletes core control-plane modules, docs, and tests. |
| `claude/runtime-semantics` | Large destructive refactor | Poor | Not mergeable | Deletes runtime/semantic coverage and core files. |
| `claude/case-workflow` | Large destructive refactor | Poor | Not mergeable | Deletes case/workflow/operator surfaces and tests. |

## Branch notes

### `N2-Pro/connector-platform`

**Verdict:** Merge-ready candidate.

**Why it aligns:**

- Extends connector runtime metadata with `emitted_event_families`.
- Adds execution-ledger event certification for connector success/skipped/failed paths.
- Keeps connector registry, runtime, and ledger contracts intact.
- Does not bypass the compiled runtime, metric registry, Operational Cases, workflow ledger, or audit path.

**Caution:** Run full tests before merge.

### `n2-pro-work-management`

**Verdict:** Needs work.

**Positive signal:**

- Adds SLA-style fields such as `sla_target_seconds` / `due_at`.
- Adds `WorkItem` projection concepts that can support Atlassian-like work views.

**Blockers:**

- Removes evidence attachment behavior.
- Deletes large test coverage.
- Weakens semantic metric validation.
- Needs a follow-up branch to restore evidence and tests before merge consideration.

### `N2-Pro/workflow-automation`

**Verdict:** Needs work.

**Positive signal:**

- Adds workflow action filtering for `source_connector`.
- Adds workflow simulation tests.

**Blockers:**

- Deletes workflow/operator tests.
- Weakens semantic metric validation.
- Should be split into a smaller branch that only adds the workflow condition and preserves existing contracts.

### `N2-Pro/trust-admin-security`

**Verdict:** Needs work.

**Positive signal:**

- Improves `audit_scope` redaction for secret-shaped business IDs.
- Aligns with the principle that audit/visibility boundaries should be conservative.

**Blockers:**

- Deletes tests.
- Weakens metric validation.
- Should be rebased as a small security-only patch.

### `N2-Pro/operator-surfaces`

**Verdict:** Needs work.

**Positive signal:**

- Adds operator-facing API surfaces for cases, approvals, audit, and views.
- Aligns with the app/operator-console-first product direction.

**Blockers:**

- Deletes core tests.
- Weakens semantic validation.
- Deletes or collapses existing modules rather than extending them.

### `N2-Pro/search-analytics`

**Verdict:** Needs work.

**Positive signal:**

- Adds search/analytics surfaces that could support operator discovery.

**Blockers:**

- Deletes tests and core modules.
- Needs to be split into a narrow search-surface branch that preserves control-plane contracts.

### `claude/qa-review`

**Verdict:** Not mergeable.

**Reason:** Broad destructive refactor. It deletes large parts of the control plane, docs, and tests instead of incrementally extending the platform.

### `claude/runtime-semantics`

**Verdict:** Not mergeable.

**Reason:** Broad destructive refactor. It removes runtime/semantic modules and tests, threatening the semantic registry as the source of truth.

### `claude/case-workflow`

**Verdict:** Not mergeable.

**Reason:** Broad destructive refactor. It deletes case/workflow/operator modules and tests, regressing the Atlassian-like operating control plane.

## Recommended next actions

1. Merge `N2-Pro/connector-platform` only after a full test pass.
2. Split the useful pieces of `n2-pro-work-management`, `N2-Pro/workflow-automation`, `N2-Pro/operator-surfaces`, and `N2-Pro/search-analytics` into narrow additive branches.
3. Restore deleted tests and semantic validation before any merge.
4. Keep `WorkItem` projection-only and keep the semantic registry as the canonical metric source of truth.
5. Do not merge destructive refactor branches without a full reimplementation and migration plan.
