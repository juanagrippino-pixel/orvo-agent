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

### 2026-06-02 status checkpoint

The 2026-06-02 integration cycle absorbed two Architecture Review Board recommendations into the canonical branch:

- `8267bd2` landed the preferred canonical WorkItem/status-category direction from `codex/eng-factory-work-item-status-category-20260602`: `app/brain/work_items.py` exposes read-only project, issue-type, workflow/status-definition, work item ID, and `to_do`/`in_progress`/`done` status-category semantics over `OperationalCase`.
- `f09aa7f` landed the connector-platform metadata branch: connector health/rate-limit/lifecycle metadata, registry-driven enabled daily connector discovery, runtime connector refs, and run-ledger redaction of raw `secret_refs` values.
- `5181dd7` committed the ARB branch review that marked `codex/status-category-jql-20260602` as a consolidation risk (`todo` vs `to_do`) and `codex/service-management` as blocked until service/customer statuses are namespaced away from canonical WorkItem `status_category`.

Evidence checked for this checkpoint:

- `app/brain/work_items.py` defines `project_projection()`, `case_work_item_projection()`, issue-type/status definitions, workflow definition, and allowed status categories.
- `app/brain/operator_views.py` resolves JQL-lite fields `project`, `issue_type`, `status_category`, and `assignee_ref` through the WorkItem/OperationalCase helpers, not duplicated status literals.
- `app/brain/runtime.py` emits connector runtime metadata, and `app/brain/run_ledger.py` redacts persisted `secret_refs` values while preserving parameter names.
- Tests present for the shipped slices include `tests/test_work_items.py`, `tests/test_operator_case_views.py`, `tests/test_brain_connector_registry.py`, `tests/test_brain_runtime.py`, `tests/test_brain_run_ledger.py`, and `tests/invariants/test_secret_redaction.py`.

Recommended order:

1. **Trust/Admin/Security audit and authorization closure**
   - Convert remaining ARB blockers into implementation packets before claiming Trust/Admin/Security readiness.
   - Merge/test retention-bounded audit export (`codex/trust-admin-security`) and URL userinfo redaction (`qa/redaction-url-userinfo-20260602131915`) only after focused security/invariant tests are green.
   - Gate: internal operator API/security tests for rejected action keys, invalid transitions, scope failures, auth failures, export retention limits, and redacted audit/error payloads.

2. **WorkItem semantic consolidation**
   - Mark `codex/status-category-jql-20260602` as superseded unless it is rebased onto canonical `to_do`/`in_progress`/`done` helpers.
   - Keep all new queue/export/dashboard predicates deriving from `app/brain/work_items.py` / `operational_case_status_category()`.
   - Gate: `tests/test_work_items.py`, `tests/test_operator_case_views.py`, and any internal API projection tests proving no `todo`/`waiting` category drift leaks into canonical `status_category`.

3. **Operator surfaces and search analytics on top of WorkItem fields**
   - Integrate `codex/operator-surfaces` and `codex/search-analytics` as read-only projections after confirming they consume canonical WorkItem fields and do not persist duplicate state.
   - Gate: recently-in-progress derives from `status_changed` timeline events; recently-dismissed derives from `dismissed_at`; built-in view totals/export run through the same JQL-lite parser and remain redacted/business-scoped.

4. **Service-management/SLA namespace fix**
   - Rebase `codex/service-management` after WorkItem consolidation and rename customer/service categories to `owner_status_category` or `service_status_category`; reserve `status_category` for canonical WorkItem values.
   - Gate: service/SLA tests prove `waiting_owner` / `waiting_external` never become canonical WorkItem status categories.

5. **Connector registry runtime hardening**
   - Keep registry execution on the platform path: registry -> compiled runtime -> run ledger -> semantic validation -> cases.
   - Move from transitional inline secret params toward runtime secret-ref resolution for Tiendanube/MercadoLibre/Meta Ads before promoting registry execution as compiled-runtime complete.
   - Gate: connector registry/runtime tests proving required secret refs resolve at runtime, runtime hashes do not include secret values, persisted/operator metadata redacts secret-ref URI values, and redacted failures open/update `data_stale` rather than leaking credentials.

6. **Pilot-readiness runbook refresh**
   - Update the Tiendanube/WhatsApp-first pilot checklist to reflect the real merged runtime, ledger, case, evidence, WorkItem, operator-action, and connector-metadata surfaces.
   - Keep WhatsApp as a projection/delivery surface, not the source of truth.
   - Gate: docs link validation, secret scan, and one dry-run operator report artifact.

Do not start broad automation, marketplace/extensibility, or Meta Ads/channel-mix expansion until this train can explain every owner-facing claim from runtime, ledger, cases, evidence, and WorkItem projections and until Trust/Admin/Security blockers are either fixed or explicitly scoped out of live use.

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
