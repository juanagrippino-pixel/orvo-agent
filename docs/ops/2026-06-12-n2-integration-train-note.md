# N2 Pro Integration Train Note — 2026-06-12

**Integration branch:** `feat/orvo-brain-control-plane`  
**Current integration HEAD:** `cb49a64c` (`test: workflow ledger approval redaction boundary`)  
**Worker root inspected:** `/root/orvo-agent-worktrees`  
**Run mode:** safe integration review only; no destructive branch cleanup.

## Inventory summary

- Unmerged local branches against `feat/orvo-brain-control-plane`: **92**
- Git worktrees under `/root/orvo-agent-worktrees`: **175**
- Dirty worker worktrees found: **0**
- Recent branch set inspected: 2026-06-11 and newer candidates.

## Candidate review

### `n2/case-family-readiness-policy-20260612` at `a86a1bb8`

This was the closest N2 product candidate, but it is **not merge-safe** in its current form.

Observed diff against the integration branch:

- Adds `app/brain/case_family_policy.py` and moves case-family release-state ownership there.
- Updates `app/brain/operational_cases.py`, `app/brain/work_items.py`, and `docs/specs/metric-registry-contract.md`.
- Adds `tests/test_case_family_policy.py`.
- Removes existing regression tests from:
  - `tests/test_internal_operator_api.py`
  - `tests/test_workflow_automation_simulation.py`

Blocker: the branch deletes already-accepted regression coverage for top-priority case ordering and workflow-action ledger redaction/approval-boundary scoping. The new test does not replace those deleted tests. It also duplicates case-family release-state behavior that is already represented in the current integration baseline, so the merge would regress coverage without adding a clearly net-positive product slice.

### Broader recent branches

Recent `codex/*` and `docs/*` branches were also not selected for direct merge because they are stale or scope-sprawling relative to the current integration train:

- `codex/operator-surfaces`, `codex/search-analytics`, `codex/work-management`, `codex/connector-platform`, `codex/workflow-automation`, `codex/trust-admin-security`, and `codex/service-management` touch multiple architecture layers and/or remove current tests/docs.
- Several branches delete historical docs such as `docs/ops/2026-05-31-integration-train.md`, `docs/architecture-reviews/2026-06-11-arb-update-6457695.md`, or connector/operator API tests that the current baseline intentionally preserves.
- `codex/qa-case-timeline-dedupe-scope-20260612` and `codex/dispatch-idempotency-redaction-integration-20260611231456` are small in file count but still remove 307 lines of current regression tests.

## Decision

**No branch merged this run.**

The integration branch is clean and already includes the latest verified workflow ledger redaction commit. Merging any currently unmerged branch would either regress tests, duplicate already-integrated behavior, or introduce broad architecture changes that should be split and rebased by their lane owners.

## Next integration order

1. Ask lane owners to rebase/split `n2/case-family-readiness-policy-20260612` so it preserves current regression tests and becomes a narrow case-family policy refactor.
2. Rebase/split broad operator/search/work-management branches around generic WorkItem/JQL/view primitives instead of wholesale merge.
3. Keep workflow automation projection-only until a real executor has idempotency, approval, audit, RBAC, retry/failure, and redacted-response tests.
4. Keep connector-platform hardening on the contract-first path: connector registry → compiled runtime → run ledger → semantic validation → Operational Cases.
5. Preserve the current integration branch as the clean source of truth until a narrow branch passes focused tests without deleting accepted coverage.

## Verification performed

- `git status --short`: clean before this note.
- `git branch --show-current`: `feat/orvo-brain-control-plane`.
- `git rev-parse --short HEAD`: `cb49a64c`.
- `git worktree list --porcelain`: 175 worktrees, none dirty.
- `git branch --no-merged feat/orvo-brain-control-plane`: 92 unmerged branches.
- Candidate diff inspected with `git diff --find-renames feat/orvo-brain-control-plane..n2/case-family-readiness-policy-20260612`.
- No merge, push, deploy, or cron mutation performed.
