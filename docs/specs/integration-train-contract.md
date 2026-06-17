# Integration Train Contract

Status: Draft operating contract
Date: 2026-05-24
Last reconciled: 2026-06-17
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

### 2026-06-17 status checkpoint

The current repository `HEAD` before this reconciliation is `f293c028` (`feat/orvo-brain-control-plane`). This supersedes the 2026-06-15 checkpoint and adopts the 2026-06-17 Architecture Review Board alignment review: `docs/architecture-reviews/2026-06-17-architecture-alignment-review.md` and `docs/architecture-reviews/2026-06-17-branch-readiness-matrix.md`. The reviewed code at `8a0b7c66` passed `pytest -q`; the current HEAD adds those review reports and remains on the same canonical integration branch.

Recent shipped baseline facts, grounded in repo inspection:

- `OperationalCase` remains the durable work-management source of truth; `WorkItem` remains a projection layer with project keys, issue types, workflow/status definitions, status categories, priority brackets, and query-field metadata, not a parallel task store.
- WorkItem issue-type definitions expose `release_state` from metric-registration and owner-promotion gates: `promoted`, `readiness_gated`, `deferred`, and `internal_only`.
- WorkItem query/search vocabulary is centralized through `work_item_query_field_spec()`, `work_item_query_field_definitions()`, and `allowed_work_item_query_sort_fields()`. Broad search/dashboard/operator-surface work must extend this registry instead of adding endpoint-local field semantics.
- Manual/operator workflow transitions are separated from deterministic system reopen transitions: `operational_case_status_transitions()` remains the operator-action table while system transitions expose terminal-state reopen metadata for recurring evidence.
- Workflow planning/approval/execution queues remain projection/governance-first. `list_workflow_execution_queue()` requires a catalog-defined approval-required action, `approval_state=approved`, `execution_state=pending_execution`, and a matching approved approval request with `decided_at`; queue views still report `execution_enabled = False` and `side_effects_executed = 0`.
- Trust/Admin hardening includes safe actor refs, safe internal error codes/messages, audit-business scoping for secret-shaped tenant IDs, the Basic-auth audit redaction invariant, non-ASCII internal-auth fail-closed behavior, redacted operator action principals, and an admin plus explicit all-business grant boundary for the global `/internal/brain/whatsapp/delivery-statuses` route. RBAC remains coarse (`viewer`, `operator`, `admin`) and is not external tenant/project-admin launch readiness.
- Manual case actions require idempotency at the HTTP boundary and shared helper boundary. `apply_case_action_with_idempotency()` calls `require_case_action_idempotency_key()` before validation, ledger reservation, or mutation.
- Connector secret-boundary hardening is baseline: `app/brain/connector_registry.py` requires secret-backed adapter kwargs to use `resolved_secret_param`, and connector contract tests assert forced/scheduled connector secrets are not satisfied from durable public `connector_param` bindings.
- WorkItem status-category semantics remain canonical: `OperationalCaseStatusCategory` is `to_do`, `in_progress`, `done`; branches or docs that use `todo` are non-canonical drift.
- Semantic-registry enforcement defaults to `metric_registry_mode="enforced"` in `detect_cases_from_report(...)`, while persisted case upserts call it explicitly with `metric_registry_mode="enforced"` before writing OperationalCase state.
- Internal operator analytics continue to use thin route wrappers and shared service helpers. Endpoint count remains the largest Atlassian-pattern risk; future analytics/search/dashboard slices should converge on WorkItem/JQL/view/facet primitives rather than one route per card.

Recommended order from this checkpoint:

1. **Document and test the follow-up contracts before the next major merge**
   - Workflow schemes: status transitions, validators, post-functions, and permissions by case type.
   - Semantic manifest: case family → required metrics → allowed actions → built-in views in one audited registry.
   - Connector adapter protocol: typed adapter/service/storage boundaries and runtime certification.
   - Workflow simulation: duplicate request, approval denial, external failure, and replay after success.
   - Trust/admin contract: RBAC matrix, audit retention/export controls, secret rotation, and admin surface boundaries.
   - Gate: these should be docs/spec/test-first unless the implementation already exists and can be verified by focused tests.

2. **Rebase divergent N2 Pro branches before considering promotion**
   - `N2-Pro/operator-surfaces` needs rebase and review for duplicated operator surfaces and projection boundaries.
   - `N2-Pro/trust-admin-security` needs rebase plus the RBAC/audit/secret-rotation contract above.
   - `N2-Pro/edge-developer-platform` needs focused review against connector/service boundaries before integration.
   - `N2-Pro/service-management` needs rebase and case-family/action-catalog alignment.
   - `qa/2026-06-17-control-plane-safety` and `n2/build-loop-20260617035630` should be folded into current tests or rebased if still useful.

3. **Keep work-management/search/operator-surface work on shared projection primitives**
   - Treat WorkItem/JQL-like filtering, facets, built-in views, and case-query helpers as the canonical source for search/analytics/operator surfaces.
   - Reject bespoke recent-case projections, local field vocabularies, or a second query/filter model.
   - Document honestly that the current query layer is a JQL-like subset, not full JQL semantics.

4. **Keep workflow automation ledger-first and projection/governance-first**
   - Planning, idempotency, approval, and audit primitives are aligned, but there is still no real executor, durable approval state machine, or full side-effect audit integration.
   - No external side effect may proceed without approved action-key governance, ledgered idempotency, and failure/replay tests.

5. **Keep semantic-registry enforcement as the baseline**
   - Deterministic metric-registry failures must block invalid owner-facing projections.
   - Reports, WhatsApp text, and operator surfaces remain projections; they must not become case, metric, priority, dedupe, or lifecycle state.

6. **Keep service-management/SLA as nested projections until canonical workflow semantics justify more**
   - `waiting_owner`, `waiting_external`, SLA status, escalation reason, and service record type should remain nested service/owner fields until a workflow-schemes contract makes them first-class.
   - Canonical WorkItem status categories remain exactly `to_do`, `in_progress`, and `done`; deferred families such as `channel_mix_shift` remain non-owner-facing until their gates pass.

7. **Keep edge/developer and external-action toolkits contract-first**
   - Gateway/service-catalog/external-action toolkits stay internal unless they include durable idempotency, rate-limit, audit, route-coverage, provider capability, and redacted-response enforcement.
   - Docs and API payloads must not imply production gateway or provider execution when code only reserves capabilities or declares policy metadata.

8. **Keep pilot-readiness docs after truth gates, not before**
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
