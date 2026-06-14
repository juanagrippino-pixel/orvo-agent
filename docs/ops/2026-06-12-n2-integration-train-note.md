# N2 Pro Integration Train Note — 2026-06-12

## Release integration update — 2026-06-14

**Integration branch:** `feat/orvo-brain-control-plane`
**Current integration HEAD before update:** `bd28c57c` (`codex: expose recently reopened cases endpoint`)
**Worker root inspected:** `/root/orvo-agent-worktrees`
**Run mode:** safe integration review; no destructive branch cleanup.

### Inventory summary

- `git fetch --all --prune`: completed.
- Canonical worktree: clean on `feat/orvo-brain-control-plane`.
- Local unmerged branches against integration branch: **122**.
- Git worktrees total: **211**.
- Worker worktrees under `/root/orvo-agent-worktrees`: **210**.
- Dirty worker worktrees: **0**.
- Missing worker worktrees: **0**.

### Candidate review

#### `N2-Pro/connector-platform` at `4fb4f4dd`

This branch was still the first branch in the latest ARB merge sequence, but it is **not merge-safe against the current integration HEAD** without rebasing/splitting.

Observed diff against `feat/orvo-brain-control-plane`:

- `15` commits ahead and `12` commits behind current integration HEAD.
- `20` files changed, `105` insertions and `1,657` deletions.
- Deletes accepted regression coverage:
  - `tests/test_operator_case_recently_reopened.py`
  - `tests/test_operator_case_top_reopened.py`
- Rewrites/deletes substantial current test coverage in:
  - `tests/contracts/test_metric_validation_contract.py`
  - `tests/test_brain_operational_cases.py`
  - `tests/test_brain_reporting.py`
  - `tests/test_server_internal_brain_recently_opened.py`
- Touches semantic registry and reporting paths in a stale/drift-prone shape:
  - `app/brain/semantics/metric_registry.py`
  - `app/brain/reporting.py`
  - `app/brain/operator_api/recent_cases.py`
  - `app/brain/operator_api/top_cases.py`

Blocker: the branch appears to be based on an older integration baseline and removes accepted current tests instead of adding a narrow additive connector/runtime slice. The current guardrail is to preserve the integration baseline until a connector-platform slice is rebased with additive tests and no deletion of accepted coverage.

#### Broader recent N2 Pro lane branches

Recent lane branches were also not selected for direct merge because their diffs against current HEAD are stale, broad, or delete accepted regression coverage:

- `N2-Pro/workflow-automation` — `89` files changed, `1,290` insertions, `9,116` deletions.
- `N2-Pro/trust-admin-security` — `87` files changed, `910` insertions, `9,110` deletions.
- `n2-pro-work-management` — `34` files changed, `990` insertions, `1,951` deletions.
- `N2-Pro/operator-surfaces` — `129` files changed, `7,044` insertions, `9,468` deletions.
- `n2/report-surface-registry-gate-integration-20260614` — `12` files changed, `1` insertion, `1,451` deletions.
- `n2/report-surface-registry-gate` — `26` files changed, `32` insertions, `1,759` deletions.
- `n2/success-recording-terminal-20260613` — `45` files changed, `188` insertions, `4,436` deletions.
- `n2/query-layer-recent-cases-20260613` — `65` files changed, `665` insertions, `6,178` deletions.

Blocker: these branches are not safe as whole-branch merges because they are stale relative to current integration HEAD and remove accepted tests/docs or introduce broad architecture changes. They need lane-owner rebases and additive slicing.

### Decision

**No branch merged this run.**

The integration branch remains the clean source of truth. The safest action is to keep the current baseline and ask lane owners to rebase/split around the current integration HEAD, preserving accepted regression tests and durable docs.

### Next integration order

1. Rebase/split `N2-Pro/connector-platform` into an additive connector/runtime metadata slice with no deletion of accepted regression tests.
2. Rebase/split `N2-Pro/trust-admin-security` around audit/redaction hardening only, preserving existing operator audit tests.
3. Rebase/split `n2-pro-work-management` around WorkItem/SLA projection primitives, preserving accepted OperationalCase and metric-registry tests.
4. Rebase/split `N2-Pro/workflow-automation` around ledger-derived read surfaces and approval/action-key filters only.
5. Defer `N2-Pro/operator-surfaces` until it is split into smaller projection-led slices that use shared query/activity primitives.
6. Preserve current integration branch as the clean source of truth until a narrow branch passes focused tests without deleting accepted coverage or durable docs.

### Verification performed

- `git fetch --all --prune`: completed.
- `git status --short`: clean before this note.
- `git branch --show-current`: `feat/orvo-brain-control-plane`.
- `git rev-parse --short HEAD`: `bd28c57c`.
- `git branch --no-merged feat/orvo-brain-control-plane`: **122** unmerged branches.
- `git worktree list --porcelain`: **211** worktrees, **210** worker worktrees, **0** dirty, **0** missing.
- Candidate diff inspected with `git diff --stat`, `git diff --name-status`, and commit ancestry checks.
- Focused guard suite: `pytest tests/test_worker_handoff_manifest_guard.py tests/test_brain_connector_registry.py tests/test_brain_execution_ledger.py tests/test_internal_connector_readiness_api.py tests/test_brain_run_ledger.py tests/test_operator_case_views.py -q` -> **71 passed**.
- Broader regression suite: `pytest -q` -> **1553 passed**.
- No merge, push, deploy, or cron mutation performed.


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

## Release integration update — 2026-06-12 08:45 UTC

Status: **No safe merge; preserve current integration baseline**.

Preflight notes:

- `git fetch --all --prune` completed successfully.
- Canonical worktree was clean on `feat/orvo-brain-control-plane` at `9eb52b6d` before review.
- Worker root inspected: `/root/orvo-agent-worktrees`.
- Git worktrees under worker root: **182**; dirty worker worktrees: **0**; missing worktrees: **0**.
- Local branches with unique commits against `feat/orvo-brain-control-plane`: **99**.
- Recent candidate diffs were inspected with `git diff --stat`, `git diff --name-status`, and commit logs against `feat/orvo-brain-control-plane`.

## Candidate review

### `n2/case-family-readiness-policy-20260612-v2` at `8c4d6467`

This remains the closest product-priority candidate, but it is **not merge-safe** in its current form.

Observed diff against the integration branch:

- Adds `app/brain/case_family_policy.py`.
- Modifies `app/brain/connector_registry.py`, `app/brain/operational_cases.py`, `app/brain/semantics/metric_registry.py`, `app/brain/work_items.py`, and `tests/test_case_family_policy.py`.
- Rewrites/weakens accepted regression coverage in `tests/contracts/test_connector_registry_contract.py`, `tests/contracts/test_metric_validation_contract.py`, `tests/test_brain_operational_cases.py`, `tests/test_brain_reporting.py`, and `tests/test_brain_run_ledger.py`.

Blocker: the branch duplicates case-family readiness semantics already represented in the current integration baseline and does not preserve the accepted regression suite. It should be rebased/split so it either becomes a narrow policy service with additive tests or is parked until product ownership confirms the refactor.

### Recent N2 Pro lane branches

The recent `N2-Pro/*` and `n2-pro-work-management` branches are strategically useful but not merge-safe as whole branches:

- `N2-Pro/connector-platform` (`4cb2994a`) touches connector registry, execution ledger, semantic registry, operational cases, docs, and 778 lines of accepted test changes.
- `N2-Pro/trust-admin-security` (`2b6ea41e`) touches audit scope, connector registry, operational cases, semantic registry, docs, and accepted regression tests.
- `N2-Pro/workflow-automation` (`0c701f3f`) adds connector allowlist workflow conditions but also rewrites connector/metric/operational-case tests.
- `N2-Pro/search-analytics` (`aa1fe1ae`) adds a redacted case queue CSV export while touching operator views, connector registry, metric registry, and accepted regression tests.
- `n2-pro-work-management` (`cd8bc74b`) audits priority/severity timeline changes but rewrites central operational-case and registry tests.
- `N2-Pro/operator-surfaces` (`dbd59990`) is broad endpoint proliferation: 53 commits, 60 files, 5,410 insertions, and deletion of the current integration train note.

Blocker: these branches are based behind the current integration baseline and remove/rewrite accepted coverage instead of adding narrow, rebased slices.

### Recent QA / dispatch / case-view branches

- `codex/qa-case-timeline-dedupe-scope-20260612` (`28fdaff3`) deletes `docs/ops/2026-06-12-n2-integration-train-note.md` and rewrites accepted tests/docs.
- `codex/dispatch-idempotency-redaction-integration-20260611231456` (`80abe686`) and `codex/qa-dispatch-idempotency-redaction-20260611` (`174fb67f`) remove the current integration note and accepted regression tests; the latter also deletes `tests/test_server_webhook_message_extraction.py`.
- `codex/lapyme-os-snapshot-20260611` (`28f96224`) is product-valuable but deletes four accepted regression test files and touches 43 files.

Blocker: do not merge broad stale branches that delete durable docs or accepted tests. Rebase/split them into additive slices.

## Decision

**No branch merged this run.**

The current integration branch is clean, green on the focused guard suite, and already contains the latest connector-registry redaction boundary commit. Merging any currently unmerged branch would either regress accepted tests/docs, duplicate already-integrated readiness semantics, or introduce broad operator/search/work-management changes that need lane-owner rebases.

## Verification performed

- `git status --short`: clean before this update.
- `git branch --show-current`: `feat/orvo-brain-control-plane`.
- `git rev-parse --short HEAD`: `9eb52b6d`.
- `git worktree list --porcelain`: 182 worker worktrees, none dirty, none missing.
- `git rev-list --count feat/orvo-brain-control-plane..branch`: 99 branches with unique commits.
- Focused guard suite before this docs update: `pytest tests/test_worker_handoff_manifest_guard.py tests/test_brain_run_ledger.py tests/test_operator_case_views.py -q` -> `41 passed in 4.28s`.
- No merge, deploy, or cron mutation performed.

## Next integration order

1. Rebase/split `n2/case-family-readiness-policy-20260612-v2` into a narrow case-family policy service with additive tests and no removal of accepted regression coverage.
2. Rebase/split `N2-Pro/*` connector/workflow/search/work-management branches around current HEAD; merge only additive registry/runtime/ledger slices that preserve existing tests.
3. Keep `N2-Pro/operator-surfaces`, `codex/operator-surfaces`, `codex/search-analytics`, `codex/work-management`, and `codex/edge-developer-platform` behind WorkItem/JQL/facet/SLA primitive gates rather than wholesale endpoint bundles.
4. Preserve `docs/ops/2026-06-12-n2-integration-train-note.md` as durable integration history; future branches must not delete it.
5. Preserve the current integration branch as the clean source of truth until a narrow branch passes focused tests without deleting accepted coverage or durable docs.
