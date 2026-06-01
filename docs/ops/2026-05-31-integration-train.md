# Integration Train — 2026-05-31

## Supersession update — 2026-06-01 03:39 UTC

Status: **superseded by shipped canonical integration state**.

Canonical branch: `feat/orvo-brain-control-plane`<br>
Current head reviewed: `394344a` (`docs: refresh autonomous board report`)<br>
Last pushed product head in the local log: `166545e` (`codex: expose stalled actionable cases endpoint`)

This file originally recorded failed 2026-05-31 merge attempts and a blocker around terminal transition reasons. That blocker is no longer the active integration state. The canonical branch now contains the Work Management terminal-reason invariant and the follow-on platform slices listed below.

### Shipped since the blocked 2026-05-31 train

Grounded in `git log --oneline` from the canonical branch:

| Commit | Status | What changed | Notes for future workers |
|---:|---|---|---|
| `b59bcc3` | shipped | Integrated Work Management terminal reasons. | Manual terminal case actions must keep non-empty reasons; do not weaken this invariant for fixtures. |
| `ba0ff58` | shipped | Integrated Connector Platform runtime metadata/execution routing. | Still treat secret-ref execution hardening as follow-up; compiled metadata is not the whole connector platform. |
| `8493451` | shipped | Integrated Workflow Automation simulation. | Dry-run only: no external side effects, no durable executor, no approval workflow yet. |
| `194e4d3` | shipped | Integrated Search/Analytics case query/view slices. | JQL-lite/read-only views remain scoped projections over canonical cases. |
| `61543de` | shipped | Exposed top actionable cases by age endpoint. | Operator surface only; does not own case state. |
| `9fa1dce` / `ff24e81` | shipped | Pinned action actor identity and action whitelist-before-lookup behavior. | Keep actor identity from authenticated/internal context, not client payload. |
| `28119f5` | shipped | Centralized case action catalog in `app/brain/action_catalog.py`. | API and workflow projections should reuse this service-layer catalog instead of duplicating action metadata. |
| `166545e` | shipped | Exposed stalled actionable cases endpoint. | Operator surface projection over actionable cases. |
| `394344a` | docs-only | Refreshed autonomous board report with the current train state. | This integration-train update reconciles the stale train doc with that report and local branch inspection. |

Code inspection confirms the action catalog is now service-layer source of truth: `app/brain/action_catalog.py` defines registered action metadata, marks `resolve_case`/`dismiss_case` as `requires_reason=True`, exposes `API_ENABLED_CASE_ACTION_KEYS`, and provides `workflow_action_registry()` for workflow dry-run validation. `app/brain/workflow_automation.py` imports that catalog instead of maintaining an independent workflow action registry.

### Branch inventory as of this update

Checked with `git merge-base --is-ancestor <branch> HEAD` from `/root/orvo-agent`:

| Branch | Head | Canonical status | Recommended handling |
|---|---:|---|---|
| `codex/connector-platform` | `6c544fb` | merged | Candidate for safe cleanup only after normal branch-retention review. |
| `codex/workflow-automation` | `8c6260d` | merged | Candidate for safe cleanup; keep dry-run-only labeling in docs/release notes. |
| `codex/search-analytics` | `087a081` | merged | Candidate for safe cleanup. |
| `codex/action-catalog-service-20260601` | `28119f5` | merged | Candidate for safe cleanup; this is now the canonical action-catalog service slice. |
| `docs/gtm-paid-pilot-roi-20260601` | `93c582e` | unmerged | Low-risk docs-only candidate; integrate before more feature branches if the diff is still clean. |
| `codex/work-management` | `2a68aca` | unmerged follow-up | Contains owner-facing case brief policy beyond already-shipped terminal reasons; rebase and run full suite before merge. |
| `codex/operator-surfaces` | `118aff8` | unmerged/rework | Must reconcile with shipped `action_catalog.py`; do not reintroduce duplicated action metadata. |
| `codex/trust-admin-security` | `a90e276` | unmerged/review | Still needs security review for scoped principals, least privilege, failed-attempt audit, and append-only audit guarantees. |
| `codex/service-management` | `b7793fc` | unmerged/dependent | Wait until Work Management/Operator API follow-ups stabilize. |
| `codex/edge-developer-platform` | `ba37d0b` | unmerged/dependent | Wait for current operator/runtime contracts to settle. |
| `codex/coverage-regression-guard-20260531-0330` | `d2d171d` | unmerged QA | Good hardening candidate; merge one at a time with full tests. |
| `codex/qa-owner-brief-actionable` | `c3f0954` | unmerged QA | Re-evaluate after the owner-facing case brief policy branch is rebased. |
| `codex/channel-mix-case-gate` | `4f366cb` | unmerged QA/product gate | Keep aligned with Packet N; channel mix remains deferred/internal until gates pass. |
| `codex/qa-redteam-run-ledger-redaction-20260531` | `b2aa861` | unmerged QA | Review carefully because the branch subject overlaps channel-mix gating despite the name. |
| `qa/case-family-registry-drift` | `b78e65e` | unmerged QA | Useful registry drift test candidate; sequence after current semantic/connector tests are green. |

### Current next integration order

1. **Docs-only first:** `docs/gtm-paid-pilot-roi-20260601` if its diff still contains only GTM/ROI docs and passes conflict-marker/secret checks.
2. **Work Management follow-up:** rebase `codex/work-management` @ `2a68aca` onto `feat/orvo-brain-control-plane`; verify owner-facing brief policy does not conflict with current actionable-case projections.
3. **QA hardening:** integrate `coverage-regression-guard`, `qa-owner-brief-actionable`, and `qa/case-family-registry-drift` one at a time, with focused tests plus `pytest -q` after each merge.
4. **Operator/Trust branches:** only after action-catalog and Work Management follow-ups are stable, reconcile `codex/operator-surfaces` and `codex/trust-admin-security` against the shipped catalog, actor identity, whitelist ordering, and operator endpoint surfaces.
5. **Platform expansion:** service-management and edge/developer branches should remain behind the above stabilization work.

### Superseded blocker notes

The earlier sections below are kept as historical integration evidence. Do not use their branch order as current guidance. In particular:

- `codex/work-management-fixture-reasons-20260531` / severity fixture repair are no longer the top-level integration blocker on the canonical branch; Work Management terminal reasons are already present.
- Connector Platform, Workflow Automation simulation, Search/Analytics, and Action Catalog are no longer pending train items; they are merged into `feat/orvo-brain-control-plane`.
- Any future cleanup must use safe deletion (`git branch -d`) and/or explicit `merge-base --is-ancestor` checks; do not force-delete unmerged branches.

---

## Historical update — 2026-05-31 20:35 UTC

Integration branch: `feat/orvo-brain-control-plane`
Base before attempted merge: `01da568` (`merge: consolidate runtime semantics diagnostics`)
Candidate attempted: `codex/work-management-fixture-reasons-20260531` @ `641db72`
Temporary merge head: `fa2afd0`

### Result

No implementation worker branch was promoted in this run.

The integration manager attempted the packaged Work Management Core repair branch after verifying the worker worktree was clean and the focused Work Management + queue-summary blocker suite passed. The branch merged cleanly into the current integration branch, but the required post-merge full regression suite failed because two newer severity-split projection fixtures still resolve operator-owned cases without explicit terminal reasons. The merge was rolled back locally to `01da568` and was not pushed.

Verification performed:

- Worker worktree: `/root/orvo-agent-worktrees/codex-work-management-fixture-reasons-20260531`
- Worker status: clean before test.
- Focused test on worker branch: `pytest tests/test_brain_operational_cases.py tests/test_operator_case_actions.py tests/test_operator_case_queue_summary_by_case_type.py tests/test_operator_case_queue_summary_by_entity_kind.py tests/test_operator_case_queue_summary_by_priority_bracket.py tests/test_operator_case_queue_summary_by_source_connector.py -q` → 95 passed.
- Merge attempt into `feat/orvo-brain-control-plane`: clean merge, temporary merge head `fa2afd0`.
- Post-merge focused test: same command → 95 passed.
- Post-merge full suite: `pytest -q` → 2 failed, 1096 passed.
- Rollback: local integration branch reset to `01da568`; source branch preserved.

New blocker introduced by integration-branch drift after the worker base:

- `tests/test_operator_case_queue_aging_by_severity.py::test_summarize_case_queue_aging_by_severity_excludes_resolved_cases`
- `tests/test_operator_case_queue_stagnation_by_severity.py::test_summarize_case_queue_stagnation_by_severity_excludes_resolved_cases`

Representative error:

```text
OperationalCaseStatusError: operator transition to resolved requires a non-empty reason
```

Required fix before retry:

- Rebase or extend `codex/work-management-fixture-reasons-20260531` on current `feat/orvo-brain-control-plane` and add explicit `reason=` values to the two severity-split resolved-case fixtures above.
- Keep the production invariant that operator terminal transitions require non-empty reasons; do not weaken the invariant to satisfy fixtures.
- Re-run the severity-split aging/stagnation tests, the existing focused Work Management suite, and `pytest -q` after the fixture repair.

### Historical next integration order from that run

1. `codex/work-management-fixture-reasons-20260531` @ `641db72` — first priority, but blocked by the two severity fixture failures above.
2. `codex/connector-platform` @ `6c544fb` — ARB merge-ready incremental; retry only after Work Management terminal-reason semantics land or are intentionally deferred.
3. `codex/workflow-automation` @ `8c6260d` — merge-ready only as dry-run/simulation after Work Management dependency clears.
4. `codex/search-analytics` @ `087a081` — merge-ready incremental after overlap with `operator_api.py` and projections is checked against prior merges.

## Earlier run — 2026-05-31 16:21 UTC

Run time: 2026-05-31 16:21 UTC
Integration branch: `feat/orvo-brain-control-plane`
Base before attempted merge: `72dd737` (`docs: refresh architecture review board report`)

## Result

No implementation worker branch was promoted in this run.

The integration manager attempted the ARB-recommended first branch, `codex/work-management` at `f8fd2f8`, after verifying the worker worktree was clean and its focused suite passed. The branch merged cleanly, but the required full regression suite failed, so the merge was rolled back locally and was not pushed.

## Verified candidate

### `codex/work-management` @ `f8fd2f8`

Disposition: **blocked by full-suite fixture fallout; source branch preserved**.

Verification performed:

- Worker worktree: `/root/orvo-agent-worktrees/codex-work-management`
- Worker status: clean before test.
- Focused test on worker branch: `pytest tests/test_brain_operational_cases.py tests/test_operator_case_actions.py -q` → 74 passed.
- Merge attempt into `feat/orvo-brain-control-plane`: clean merge, temporary merge head `68fef14`.
- Post-merge focused test: `pytest tests/test_brain_operational_cases.py tests/test_operator_case_actions.py -q` → 74 passed.
- Post-merge full suite: `pytest -q` → 12 failed, 1066 passed.
- Rollback: local integration branch reset to `72dd737`; no failing merge pushed.

Failure pattern:

The branch adds a deterministic invariant: operator-driven terminal transitions to `resolved` or `dismissed` require a non-empty reason. Full-suite failures are test fixture calls that resolve cases with `actor_type="operator"` but no reason.

Failing files/tests:

- `tests/test_operator_case_queue_summary_by_case_type.py`
  - `test_summarize_case_queue_by_case_type_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_case_type_is_scoped_per_business`
  - `test_summarize_case_queue_by_case_type_excludes_resolved_from_actionable`
- `tests/test_operator_case_queue_summary_by_entity_kind.py`
  - `test_summarize_case_queue_by_entity_kind_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_entity_kind_is_scoped_per_business`
  - `test_summarize_case_queue_by_entity_kind_excludes_resolved_from_actionable`
- `tests/test_operator_case_queue_summary_by_priority_bracket.py`
  - `test_summarize_case_queue_by_priority_bracket_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_priority_bracket_is_scoped_per_business`
  - `test_summarize_case_queue_by_priority_bracket_excludes_resolved_from_actionable`
- `tests/test_operator_case_queue_summary_by_source_connector.py`
  - `test_summarize_case_queue_by_source_connector_groups_lifecycle_counts`
  - `test_summarize_case_queue_by_source_connector_is_scoped_per_business`
  - `test_summarize_case_queue_by_source_connector_excludes_resolved_from_actionable`

Representative error:

```text
OperationalCaseStatusError: operator transition to resolved requires a non-empty reason
```

Required fix before retry:

- Update the queue-summary test fixtures to include explicit operator resolution reasons, or use a non-operator deterministic/system actor only if the test is truly modeling system automation.
- Keep the new production invariant; do not weaken it to make fixtures pass.
- Re-run the focused queue-summary slices plus `pytest -q` after the fixture fix.

## Historical branch inventory from that run

### Merge-ready after blocker fix / dependency order

1. `codex/work-management` @ `f8fd2f8` — first priority, but blocked by the full-suite fixture failures above.
2. `codex/connector-platform` @ `239861e` — ARB marked merge-ready incremental; retry after work-management or if work-management is repaired/rebased.
3. `codex/workflow-automation` @ `2fb942c` — merge-ready only as dry-run/simulation, not an executor.
4. `codex/search-analytics` @ `1585e5a` — merge-ready incremental after overlap with operator API/projection files is checked against prior merges.

### Needs work / do not promote yet

- `codex/operator-surfaces` @ `a85e28b` — needs rebase/alignment with terminal-action reason requirements and action catalog ownership.
- `codex/trust-admin-security` @ `83513da` — useful RBAC/audit scaffolding but not Trust/Admin/Security-complete; needs failed-attempt audit, scoped principals, least-privilege defaults, and stronger append-only audit guarantees.

### Additional unmerged branches needing separate review or rebase

- `codex/service-management` @ `b7793fc`
- `codex/edge-developer-platform` @ `ba37d0b`
- `codex/qa-redteam-run-ledger-redaction-20260531` @ `b2aa861`
- `codex/contract-resolve-reason-20260531` @ `0440c80`
- `codex/require-resolve-reason-20260531` @ `47310bc`
- `codex/coverage-regression-guard-20260531-0330` @ `d2d171d`
- `codex/channel-mix-case-gate` @ `4f366cb`
- `codex/qa-action-key-whitelist-before-lookup` @ `2d0826d`
- `codex/qa-owner-brief-actionable` @ `c3f0954`
- `qa/case-family-registry-drift` @ `b78e65e`
- `docs/roadmap-librarian-2026-05-31` @ `6c4db5e`

Already merged into the integration branch:

- `codex/qa-cross-tenant-case-action`
- `codex/qa-invariant-20260531072626`
- `claude/runtime-semantics`
- `claude/qa-review`
- `claude/case-workflow`

## Parent/worktree hygiene recorded in earlier run

- Parent repo dirty state from the Architecture Review Board report was converted into commit `72dd737` (`docs: refresh architecture review board report`).
- The failed implementation merge was rolled back; `feat/orvo-brain-control-plane` does not contain the failing `codex/work-management` merge.
- Dirty worker worktrees observed and not touched:
  - `/root/orvo-agent-worktrees/claude-case-workflow` — modified `app/brain/operator_api.py`, untracked `tests/test_operator_case_queue_aging_by_severity.py`.
  - `/root/orvo-agent-worktrees/claude-runtime-semantics` — modified `app/brain/connector_registry.py`, `tests/contracts/test_connector_registry_contract.py`.
