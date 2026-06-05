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

### 2026-06-05 status checkpoint

The current repository `HEAD` is `06d7c2d` (`docs: refresh autonomous board report`). The latest code checkpoint called out by the board report is `8f69b94` (`codex: expose resolution latency priority endpoint`), with subsequent `HEAD` movement docs-only. This supersedes the 2026-06-03 train ordering and folds in `docs/architecture-reviews/2026-06-04-arb-cron-update.md` plus `docs/ops/latest-autonomous-board-report.md`.

Recent shipped baseline facts, grounded in repo inspection:

- WorkItem remains a projection: `app/brain/work_items.py` still derives project keys, issue types, workflow/status definitions, and work item IDs without a separate WorkItem store.
- Internal operator surfaces have expanded through thin route/service projections: `app/http/internal_brain/cases_activity.py` now includes `resolution-latency/by-priority-bracket` and `top-by-priority`; histogram/priority logic lives under `app/brain/operator_api/`, not the route body.
- Wrong-token internal-route auth is guarded by `tests/invariants/test_internal_operator_route_auth.py`; business grants remain enforced through `app/brain/operator_auth.py` before route logic.
- Connector failure health now classifies rate limits through `app/brain/connector_health.py` and records typed health state from `app/brain/execution_ledger.py`.
- Workflow planning/approval/execution queues remain projection-only: `app/brain/workflow_automation.py`, `workflow_approval_queue.py`, and `workflow_execution_queue.py` continue reporting `side_effects_executed = 0` / execution disabled for queue views.
- `channel_mix_shift` is still present in type/projection mappings but absent from `CASE_FAMILY_METRICS`; `DETECTABLE_OPERATIONAL_CASE_TYPES` and `OWNER_FACING_OPERATIONAL_CASE_TYPES` continue deriving from `CASE_FAMILY_METRICS`, so the family remains deferred/internal until Packet N promotes it.

Recommended order:

1. **Small Trust/Security guard merges first**
   - Integrate `codex/operator-audit-business-scope-redaction-20260604` before broader product surfaces.
   - Then take the remaining narrow trust/admin/security follow-up if it is still a one-slice diff.
   - Gate: audit lookup still works after redaction, secret-shaped tenant IDs cannot leak/collide, wrong-token and business-scope denial tests stay green, and public response envelopes remain unchanged.

2. **Work-management core, from the verified rebased branch/worktree**
   - Integrate the green local `codex/work-management` slice only after resolving the stale remote/rebase ownership issue described in the board report.
   - Gate: no duplicate WorkItem persistence table, no alternate status-category vocabulary, no manual operator reopen shortcut, and tests prove system recurrence, mutation timestamps, first acknowledgment preservation, owner-facing evidence gates, and metric-backed issue-type metadata without bypassing `OperationalCase`.

3. **Connector-platform hardening on the platform path**
   - Merge connector event/health/executor metadata only as registry/runtime/ledger metadata; keep adapter factories static/allowlisted.
   - Next connector milestone remains secret-ref runtime resolution plus connector instance/health-history/provisioning audit storage.
   - Gate: registry -> compiled runtime -> run ledger -> semantic validation -> cases remains the execution path; runtime hashes and operator metadata never include secret values; rate-limit/auth/stale failures are typed and redacted.

4. **Workflow automation projections and trigger matching, not broad execution**
   - Merge workflow trigger/audit projection work only if event names are normalized against existing operator-audit taxonomy.
   - Gate: approval/execution queues keep `execution_enabled = False` and `side_effects_executed = 0`; approved actions must not become broad side effects until actor identity, provider idempotency proof, execution-attempt ledger, RBAC, retries, and redacted audit linkage exist.

5. **Service-management/SLA as nested projections**
   - Integrate `codex/service-management` only as Jira Service Management-style projections over canonical cases.
   - Gate: `waiting_owner`, `waiting_external`, SLA status, escalation reason, and service record type stay nested service/owner fields; canonical WorkItem status categories remain exactly `to_do`, `in_progress`, and `done`.

6. **Split broad operator/search surface branches by endpoint family**
   - Decompose `codex/operator-surfaces` and `codex/search-analytics`; do not merge wholesale while they conflict with newer activity/API/test files.
   - Gate: every endpoint remains read-only, business-scoped, redacted at the API boundary, and backed by shared service/query helpers over `OperationalCase`, WorkItem projections, JQL-lite, or the run ledger. Owner brief previews must expose case IDs, evidence/freshness, and registered action keys; WhatsApp copy is never the action/state contract.

7. **Edge/developer platform as contract-first until enforcement exists**
   - Reframe `codex/edge-developer-platform` as gateway policy/service-catalog metadata unless it lands durable idempotency, rate-limit, audit, and route-coverage enforcement.
   - Gate: docs and API payloads must not imply production gateway enforcement when code only checks idempotency-key presence or declares rate-limit buckets.

8. **Pilot-readiness runbook refresh after the core merge train**
   - Update the Tiendanube/WhatsApp-first pilot checklist after trust/security, work-management, connector health, and operator-surface deltas are integrated.
   - Gate: docs link validation, secret scan, and one dry-run/operator-report artifact; keep WhatsApp as projection/delivery, not source of truth.

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
