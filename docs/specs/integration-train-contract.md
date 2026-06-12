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

### 2026-06-12 status checkpoint

The current repository `HEAD` before this reconciliation is `23c115eb` (`feat/orvo-brain-control-plane`). This supersedes the 2026-06-11 checkpoint and incorporates the 2026-06-12 Architecture Review Board review of N2-Pro branches. The 2026-06-12 review found `N2-Pro/connector-platform` to be the best merge-ready candidate, while `n2-pro-work-management`, `N2-Pro/workflow-automation`, `N2-Pro/trust-admin-security`, `N2-Pro/operator-surfaces`, and `N2-Pro/search-analytics` need narrow fixer/split work because they delete tests or regress semantic validation, evidence, or audit behavior. Destructive `claude/*` refactor branches remain not mergeable as reviewed.

Recent shipped baseline facts, grounded in repo inspection:

- WorkItem remains projection-only: `app/brain/work_items.py` derives project keys, work item IDs, issue types, workflow/status definitions, status categories, priority brackets, and query-field definitions without a separate WorkItem store.
- WorkItem issue-type definitions now expose `release_state` from separate metric-registration and owner-promotion gates: explicitly owner-facing families are `promoted`, registered-but-not-owner-facing families such as `unanswered_conversations` are `readiness_gated`, cataloged-but-unregistered families such as `channel_mix_shift` are `deferred`, and unknown/internal strings resolve as `internal_only`.
- Manual/operator workflow transitions are now separated from deterministic system reopen transitions: `operational_case_status_transitions()` remains the operator-action table while `operational_case_system_status_transitions()` and WorkItem status definitions expose terminal-state reopen metadata for recurring evidence.
- WorkItem query/search vocabulary is centralized near the projection helpers: `work_item_query_field_spec()`, `work_item_query_field_definitions()`, and `allowed_work_item_query_sort_fields()` are the source for JQL-lite/view/sort fields, including `release_state` for readiness-gated issue-type inspection; broad search or dashboard branches must extend this registry instead of adding endpoint-local field semantics.
- Workflow planning/approval/execution queues remain projection-only, but the execution queue no longer trusts ledger state alone: `list_workflow_execution_queue()` requires a catalog-defined approval-required action, `approval_state=approved`, `execution_state=pending_execution`, and a matching approved approval-request object with matching ledger/business/case/action identity and `decided_at`. Queue views still report `execution_enabled = False` and `side_effects_executed = 0`.
- Trust/Admin hardening now includes safe actor refs, safe internal error codes/messages, audit-business scoping for secret-shaped tenant IDs, the Basic-auth audit redaction invariant, non-ASCII internal-auth fail-closed behavior, redacted operator action principals, and an admin plus explicit all-business grant boundary for the global `/internal/brain/whatsapp/delivery-statuses` route.
- Manual case actions require idempotency at both the HTTP boundary and the shared helper boundary. `apply_case_action_with_idempotency()` calls `require_case_action_idempotency_key()` before validation, ledger reservation, or mutation, so non-HTTP/internal callers cannot accidentally bypass the ledgered idempotency path.
- Connector secret-boundary hardening is baseline: `app/brain/connector_registry.py` requires secret-backed adapter kwargs to use `resolved_secret_param`, and connector contract tests assert forced/scheduled connector secrets are not satisfied from durable public `connector_param` bindings.
- WorkItem status-category semantics remain canonical in the current branch: `OperationalCaseStatusCategory` is `to_do`, `in_progress`, `done`; branches or docs that use `todo` are non-canonical drift.
- Internal operator analytics continue to use thin route wrappers and shared service helpers. Endpoint count remains the largest Atlassian-pattern risk; future analytics/search/dashboard slices should converge on WorkItem/JQL/view/facet primitives rather than one route per card.

Recommended order from this checkpoint:

1. **Patch-id review and split remaining Work Management value**
   - Treat case-family release-state metadata, system reopen workflow metadata, and owner/worker timeline actor taxonomy as integrated. Do not revive or direct-merge broad `codex/work-management` history just to re-land those pieces.
   - Gate: remaining slices must be narrow and additive, such as evidence-lineage refinements or SLA-compatible metadata. They must preserve `OperationalCase` as lifecycle source of truth and keep manual/operator transitions separate from deterministic system transitions.

2. **Keep workflow automation projection-only until executor foundations exist**
   - Treat approval-request matching as integrated. Future workflow work can improve audit projections and trigger coverage, but broad side-effect execution remains blocked.
   - Gate: any real executor requires provider idempotency proof, an execution-attempt ledger, RBAC/action-scope checks, retry/failure semantics, redacted external response audit, and tests proving no side-effect path can bypass approval/idempotency/audit.

3. **Trust/Admin patch-id review after global delivery-status hardening**
   - Treat safe actor refs, safe internal error codes, Basic-auth redaction, denial audits, non-ASCII auth fail-closed behavior, redacted action principals, and the delivery-status admin/all-business boundary as integrated.
   - Gate: external Admin launch still requires explicit role and explicit business claims everywhere; legacy default role=`operator` and `allowed_businesses=None` remain internal-migration compatibility only.

4. **Connector-platform hardening after resolved-secret bindings**
   - Treat Packet Q's resolved-secret binding work as integrated; the next connector milestone is connector instance/health-history/provisioning audit storage plus typed stale/unauthorized/rate-limit paths.
   - Gate: registry -> compiled runtime -> run ledger -> semantic validation -> cases remains the execution path; runtime hashes and operator metadata never include secret values; raw secret material exists only on execution-scoped resolved copies.

5. **Split broad operator/search surface branches by generic primitives**
   - Decompose `codex/operator-surfaces` and `codex/search-analytics`; do not merge wholesale while they conflict with newer activity/API/test files or invent local query vocabulary.
   - Gate: every endpoint remains read-only, business-scoped, redacted at the API boundary, and backed by shared service/query helpers over `OperationalCase`, WorkItem projections, JQL-lite, facets, or the run ledger. Owner brief previews must expose case IDs, evidence/freshness, and registered action keys; WhatsApp copy is never the action/state contract.

6. **Service-management/SLA as nested projections**
   - Integrate `codex/service-management` only as Jira Service Management-style projections over canonical cases and only when the slice is D2C-pilot useful.
   - Gate: `waiting_owner`, `waiting_external`, SLA status, escalation reason, and service record type stay nested service/owner fields; canonical WorkItem status categories remain exactly `to_do`, `in_progress`, and `done`; deferred families such as `channel_mix_shift` remain non-owner-facing until Packet N gates pass.

7. **Edge/developer and external-action toolkits stay contract-first**
   - Keep gateway/service-catalog/external-action toolkits internal unless they include durable idempotency, rate-limit, audit, route-coverage, provider capability, and redacted-response enforcement.
   - Gate: docs and API payloads must not imply production gateway or provider execution when code only reserves capabilities or declares policy metadata.

8. **Pilot-readiness docs after truth gates, not before**
   - Fulfillment backlog and WhatsApp attention backlog are Growth/readiness-gated modules. Use research packets for qualification, but keep the sellable Starter promise constrained to evidence-backed Tiendanube cases already covered by the PRD and pilot checklist.
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
