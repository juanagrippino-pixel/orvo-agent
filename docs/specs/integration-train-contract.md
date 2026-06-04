# Integration Train Contract

Status: Draft operating contract
Date: 2026-05-24
Related: `docs/organization/d2c-autonomous-worker-addendum.md`, `docs/specs/testing-invariant-matrix.md`

## Purpose

This contract defines how autonomous worker branches are integrated without contaminating the parent repo or breaking the product direction.

## Integration order

For the D2C control-plane build, integrate in this sequence unless a later ADR changes it:

1. docs/spec contracts;
2. contract/invariant test scaffolds;
3. compiled runtime model/compiler shim;
4. connector registry wrapper for current connectors;
5. run ledger writes around existing execution;
6. metric registry aliases;
7. case engine basics;
8. operator API/read-only surfaces;
9. WhatsApp projection migration;
10. controlled actions/automation.

## Current next recommendations train

### 2026-06-03 status checkpoint

The 2026-06-03 integration cycle absorbed the highest-priority Architecture Review Board recommendations from `docs/architecture-reviews/2026-06-03-review.md` into the canonical branch:

- `b1ab601` landed WorkItem project-key hashing: `app/brain/work_items.py` now keeps project keys capped at 32 characters and appends an 8-character deterministic SHA-1 suffix for long normalized `business_id` values, closing the project-key collision risk without adding a WorkItem store.
- `ab486b6` landed the run operator projection hardening: run-ledger/operator metadata remains a projection boundary and must continue redacting raw secret-ref URI values.
- `71d334f` landed connector health taxonomy: `connector_registry.py` exposes connector health policy metadata and `run_ledger.py` records/defaults connector `health_state` through the shared connector-health taxonomy.
- `b97a10a` plus `67bf08b` landed and hardened the workflow approval queue projection: workflow approval and execution queues remain read-only, declare execution disabled, and report `side_effects_executed = 0`.

Evidence checked for this checkpoint:

- `app/brain/work_items.py` defines `project_key_for_business()`, `project_projection()`, `case_work_item_projection()`, issue-type/status definitions, workflow definition, and canonical status categories via `OperationalCaseStatusCategory`.
- `app/brain/operator_views.py` resolves JQL-lite fields `project`, `issue_type`, `status_category`, and `assignee_ref` through WorkItem/OperationalCase helpers, not duplicated status literals.
- `app/brain/connector_registry.py` defines `ConnectorHealthMetadata.health_policy_metadata()`, and `app/brain/run_ledger.py` stores connector `health_state` while recursively redacting `secret_refs` values.
- `app/brain/workflow_approval_queue.py` and `app/brain/workflow_execution_queue.py` expose queue projections with execution disabled and zero side effects.
- Tests present for the shipped slices include `tests/test_work_items.py`, `tests/test_operator_case_views.py`, `tests/test_brain_connector_registry.py`, `tests/test_brain_run_ledger.py`, and `tests/test_workflow_automation_simulation.py`.

Recommended order:

1. **Operator surfaces and search analytics on top of canonical WorkItem fields**
   - Integrate or rebase `codex/operator-surfaces` and `codex/search-analytics` only as read-only projections over `OperationalCase`, WorkItem helpers, and JQL-lite.
   - Gate: recently-in-progress derives from `status_changed` timeline events; recently-dismissed derives from terminal/dismissal timestamps; built-in view totals/export run through the same allowlisted parser and remain redacted/business-scoped.

2. **Service-management/SLA projection slice**
   - Integrate `codex/service-management` only if owner/service statuses remain nested projection fields such as `owner_status_category` or `service_status_category`.
   - Gate: service/SLA tests prove `waiting_owner` / `waiting_external` never become canonical WorkItem `status_category` values; canonical categories remain only `to_do`, `in_progress`, and `done`.

3. **Work-management lifecycle/metadata salvage**
   - Re-evaluate `codex/work-management` for unique lifecycle/audit/issue-type metadata improvements after the project-key hash and approval-queue merges.
   - Gate: no duplicate WorkItem persistence table, no alternate status-category vocabulary, no owner-facing copy changes, and tests prove mutation timestamps, first acknowledgement preservation, and metric-backed issue-type metadata without bypassing `OperationalCase`.

4. **Edge/developer platform as manifest first**
   - Reframe `codex/edge-developer-platform` as gateway policy/service-catalog contract metadata unless and until it is wired into actual route enforcement, rate limiting, and audit.
   - Gate: docs and API responses must not imply production gateway enforcement when the code is still manifest-only.

5. **Connector registry runtime secret-ref hardening**
   - Keep registry execution on the platform path: registry -> compiled runtime -> run ledger -> semantic validation -> cases.
   - Move from transitional inline secret params toward runtime secret-ref resolution for Tiendanube/MercadoLibre/Meta Ads before promoting registry execution as compiled-runtime complete.
   - Gate: connector registry/runtime tests proving required secret refs resolve at runtime, runtime hashes do not include secret values, persisted/operator metadata redacts secret-ref URI values, and redacted failures open/update `data_stale` rather than leaking credentials.

6. **Governed workflow executor preconditions, not execution yet**
   - Do not turn approved workflow actions into side effects until executor actor identity, provider idempotency, execution-attempt ledger, RBAC, retry/failure semantics, and redacted audit linkage exist.
   - Gate: approval queues may remain visible, but execution projections must keep `execution_enabled = False` and `side_effects_executed = 0` until a separate executor contract and tests land.

7. **Pilot-readiness runbook refresh**
   - Update the Tiendanube/WhatsApp-first pilot checklist to reflect the real merged runtime, ledger, case, evidence, WorkItem, operator-action, connector-health, and workflow-approval surfaces.
   - Keep WhatsApp as a projection/delivery surface, not the source of truth.
   - Gate: docs link validation, secret scan, and one dry-run operator report artifact.

Do not start broad automation, marketplace/extensibility, or Meta Ads/channel-mix expansion until this train can explain every owner-facing claim from runtime, ledger, cases, evidence, and WorkItem projections and until workflow execution and gateway enforcement are explicitly implemented rather than manifest/projection-only.

## Branch rules

- One bounded context per branch.
- External worktrees only: `/root/orvo-agent-worktrees/<task-slug>`.
- Parent repo must be clean before and after merge.
- Do not merge two branches that edit the same central file without a sequencing note.
- Integration manager resolves conflicts, not random lane workers.

## Merge gate

Before merge:

- worker summary includes branch, commit, files, tests, product impact, platform impact, risks;
- `git diff --check` passes;
- focused tests pass;
- no secret patterns in diff;
- docs links validate if docs changed;
- reviewer approves spec compliance for non-trivial code.

After merge:

- run focused tests for affected area;
- run broader tests when code changed;
- verify parent `git status --short` is empty;
- record any deferred risk in docs/worker packet or board report.

## Conflict policy

When conflicts arise:

- preserve ADR-0005 and Phase A architecture contract unless deliberately superseded;
- preserve existing working runtime/report behavior;
- prefer additive contracts/shims over rewrites;
- if unsure, stop and write an integration note instead of guessing.

## No-go merges

Do not merge if:

- raw secrets are present;
- a new path bypasses runtime/registry/ledger/cases/audit;
- tests fail and are waived without explicit user instruction;
- a branch changes product positioning away from D2C control plane;
- LLMs become source of business truth.
