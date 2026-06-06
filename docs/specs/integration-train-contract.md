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

### 2026-06-06 status checkpoint

The current repository `HEAD` before this reconciliation is `be03342` (`docs: record 2026-06-06 integration blocker`). This supersedes the 2026-06-05 checkpoint and the 2026-06-06 Architecture Review Board recommendation that still treated connector resolved-secret bindings and WorkItem priority brackets as pending.

Recent shipped baseline facts, grounded in repo inspection:

- WorkItem remains projection-only: `app/brain/work_items.py` derives project keys, work item IDs, issue types, workflow/status definitions, status categories, and priority brackets without a separate WorkItem store.
- WorkItem priority semantics are now centralized: `priority_bracket_for_score()`, `case_priority_bracket()`, `allowed_priority_brackets()`, and `operational_case_priority_definitions()` define the `low` / `medium` / `high` cutoffs; `app/brain/operator_api/common.py` delegates `_classify_priority_bracket()` to that registry.
- WorkItem query-field semantics are now centralized near the projection helpers: `app/brain/work_items.py` exposes `WorkItemQueryFieldDefinition`, `work_item_query_field_spec()`, `work_item_query_field_definitions()`, and `allowed_work_item_query_sort_fields()`; `app/brain/operator_views.py` imports that registry instead of owning a local `_FIELD_SPECS` allowlist.
- Connector secret-boundary hardening is now baseline: `app/brain/connector_registry.py` requires secret-backed adapter kwargs to use `resolved_secret_param`, and `tests/contracts/test_connector_registry_contract.py` asserts forced/scheduled connector secrets are not satisfied from durable public `connector_param` bindings.
- Internal operator analytics continue to use thin route wrappers and shared service helpers; the current branch adds another resolution-latency severity endpoint while preserving route-level delegation.
- Manual case actions reserve a workflow/action ledger row before mutation at the internal HTTP boundary; missing `X-Idempotency-Key` headers fail before case mutation with a stable envelope and redacted audit event. The transport-agnostic helper still exposes a direct-mutation fallback for non-HTTP/internal callers.
- Workflow planning/approval/execution queues remain projection-only: queue views still report execution disabled / `side_effects_executed = 0`; broad workflow execution remains blocked until durable audit, RBAC, provider idempotency, retry/failure semantics, and approval gates are all enforced.
- `channel_mix_shift` is still present in type/projection mappings but absent from `CASE_FAMILY_METRICS`; `DETECTABLE_OPERATIONAL_CASE_TYPES` and `OWNER_FACING_OPERATIONAL_CASE_TYPES` continue deriving from `CASE_FAMILY_METRICS`, so the family remains deferred/internal until Packet N promotes it.

Recommended order:

1. **Keep manual case-action idempotency enforced while continuing workflow hardening**
   - Guard the `POST /internal/brain/businesses/<business_id>/cases/<case_id>/actions` route-boundary requirement: every successful mutation request carries a safe `X-Idempotency-Key`, reserves before mutation, and replays/skips duplicates without a second side effect.
   - Gate: missing/blank/secret-shaped keys fail before mutation with redacted stable envelopes/audit events; duplicate or racing keyed requests cannot apply the same side effect twice.

2. **Keep WorkItem query-field registry as the only JQL/search vocabulary source**
   - Future JQL-lite/view/facet fields must be added through the canonical WorkItem/OperationalCase query-field registry near the projection helpers, while keeping metric keys in the semantic metric registry.
   - Gate: built-in views and the JQL parser continue importing the same allowlisted field definitions; future dashboard/search filters must either reuse existing WorkItem helpers (for example priority brackets) or extend the registry first. No SQL translation, persisted saved views, or tenant-custom schemas are introduced.

3. **Connector-platform hardening after resolved-secret bindings**
   - Treat Packet Q's resolved-secret binding work as integrated; the next connector milestone is connector instance/health-history/provisioning audit storage plus typed stale/unauthorized/rate-limit paths.
   - Gate: registry -> compiled runtime -> run ledger -> semantic validation -> cases remains the execution path; runtime hashes and operator metadata never include secret values; raw secret material exists only on execution-scoped resolved copies.

4. **Workflow automation projections and trigger matching, not broad execution**
   - Merge workflow trigger/audit projection work only if event names are normalized against existing operator-audit taxonomy and approval decisions are durably auditable.
   - Gate: approval/execution queues keep `execution_enabled = False` and `side_effects_executed = 0`; approved actions must not become broad side effects until actor identity, provider idempotency proof, execution-attempt ledger, RBAC, retries, and redacted audit linkage exist.

5. **Service-management/SLA as nested projections**
   - Integrate `codex/service-management` only as Jira Service Management-style projections over canonical cases.
   - Gate: `waiting_owner`, `waiting_external`, SLA status, escalation reason, and service record type stay nested service/owner fields; canonical WorkItem status categories remain exactly `to_do`, `in_progress`, and `done`.

6. **Split broad operator/search surface branches by endpoint family**
   - Decompose `codex/operator-surfaces` and `codex/search-analytics`; do not merge wholesale while they conflict with newer activity/API/test files or invent local query vocabulary.
   - Gate: every endpoint remains read-only, business-scoped, redacted at the API boundary, and backed by shared service/query helpers over `OperationalCase`, WorkItem projections, JQL-lite, or the run ledger. Owner brief previews must expose case IDs, evidence/freshness, and registered action keys; WhatsApp copy is never the action/state contract.

7. **Edge/developer platform as contract-first until enforcement exists**
   - Reframe `codex/edge-developer-platform` as gateway policy/service-catalog metadata unless it lands durable idempotency, rate-limit, audit, and route-coverage enforcement.
   - Gate: docs and API payloads must not imply production gateway enforcement when code only checks idempotency-key presence or declares rate-limit buckets.

8. **Pilot lead execution and pilot-readiness docs after core gates**
   - Use the first-10 lead-build and fulfillment-backlog research packets for outbound learning, but keep the sellable promise constrained to Tiendanube-backed cases/evidence already covered by the PRD and pilot checklist.
   - Update the Tiendanube/WhatsApp-first pilot checklist only after required manual idempotency, WorkItem query-field registry, connector-platform hardening, and operator-surface deltas are integrated.
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
