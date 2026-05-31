# Integration Train — 2026-05-31

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

## Current branch inventory

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

## Parent/worktree hygiene

- Parent repo dirty state from the Architecture Review Board report was converted into commit `72dd737` (`docs: refresh architecture review board report`).
- The failed implementation merge was rolled back; `feat/orvo-brain-control-plane` does not contain the failing `codex/work-management` merge.
- Dirty worker worktrees observed and not touched:
  - `/root/orvo-agent-worktrees/claude-case-workflow` — modified `app/brain/operator_api.py`, untracked `tests/test_operator_case_queue_aging_by_severity.py`.
  - `/root/orvo-agent-worktrees/claude-runtime-semantics` — modified `app/brain/connector_registry.py`, `tests/contracts/test_connector_registry_contract.py`.
