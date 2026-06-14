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

### 2026-06-13 status checkpoint

The current repository `HEAD` before this reconciliation is `00d7bd8d` (`feat/orvo-brain-control-plane`, `docs: capture 2026-06-13 architecture review findings`). This supersedes the 2026-06-12 checkpoint and incorporates the latest Architecture Review Board review in `docs/architecture-reviews/2026-06-13-arb-cron-review.md` plus `docs/architecture-reviews/2026-06-13-arb-cron-branch-readiness.md`. The latest review keeps `N2-Pro/connector-platform` merge-ready, keeps `N2-Pro/workflow-automation`, `N2-Pro/trust-admin-security`, and `n2-pro-work-management` as merge-ready candidates pending rebase/reconciliation, and keeps `N2-Pro/operator-surfaces` in needs-work mode because it is too broad and route-heavy.

Recent shipped baseline facts, grounded in repo inspection:

- WorkItem remains projection-only: `app/brain/work_items.py` derives project keys, work item IDs, issue types, workflow/status definitions, status categories, priority brackets, and query-field definitions without a separate WorkItem store.
- WorkItem issue-type definitions now expose `release_state` from separate metric-registration and owner-promotion gates: explicitly owner-facing families are `promoted`, registered-but-not-owner-facing families such as `unanswered_conversations` are `readiness_gated`, cataloged-but-unregistered families such as `channel_mix_shift` are `deferred`, and unknown/internal strings resolve as `internal_only`.
- Manual/operator workflow transitions are now separated from deterministic system reopen transitions: `operational_case_status_transitions()` remains the operator-action table while `operational_case_system_status_transitions()` and WorkItem status definitions expose terminal-state reopen metadata for recurring evidence.
- WorkItem query/search vocabulary is centralized near the projection helpers: `work_item_query_field_spec()`, `work_item_query_field_definitions()`, and `allowed_work_item_query_sort_fields()` are the source for JQL-lite/view/sort fields, including `release_state` for readiness-gated issue-type inspection; broad search or dashboard branches must extend this registry instead of adding endpoint-local field semantics.
- Workflow planning/approval/execution queues remain projection-only, but the execution queue no longer trusts ledger state alone: `list_workflow_execution_queue()` requires a catalog-defined approval-required action, `approval_state=approved`, `execution_state=pending_execution`, and a matching approved approval-request object with matching ledger/business/case/action identity and `decided_at`. Queue views still report `execution_enabled = False` and `side_effects_executed = 0`.
- Trust/Admin hardening now includes safe actor refs, safe internal error codes/messages, audit-business scoping for secret-shaped tenant IDs, the Basic-auth audit redaction invariant, non-ASCII internal-auth fail-closed behavior, redacted operator action principals, and an admin plus explicit all-business grant boundary for the global `/internal/brain/whatsapp/delivery-statuses` route. RBAC remains coarse (`viewer`, `operator`, `admin`) and is not external tenant/project-admin launch readiness.
- Manual case actions require idempotency at both the HTTP boundary and the shared helper boundary. `apply_case_action_with_idempotency()` calls `require_case_action_idempotency_key()` before validation, ledger reservation, or mutation, so non-HTTP/internal callers cannot accidentally bypass the ledgered idempotency path.
- Connector secret-boundary hardening is baseline: `app/brain/connector_registry.py` requires secret-backed adapter kwargs to use `resolved_secret_param`, and connector contract tests assert forced/scheduled connector secrets are not satisfied from durable public `connector_param` bindings.
- WorkItem status-category semantics remain canonical in the current branch: `OperationalCaseStatusCategory` is `to_do`, `in_progress`, `done`; branches or docs that use `todo` are non-canonical drift.
- Semantic-registry enforcement is now present on persisted case upserts through `detect_cases_from_report(... metric_registry_mode="enforced")` in `app/brain/operational_cases.py`, but it is not yet uniformly enforced across every non-persistent preview/report/surface path.
- Internal operator analytics continue to use thin route wrappers and shared service helpers. Endpoint count remains the largest Atlassian-pattern risk; future analytics/search/dashboard slices should converge on WorkItem/JQL/view/facet primitives rather than one route per card.

Recommended order from this checkpoint:

1. **Merge connector-platform after normal test pass**
   - Treat `N2-Pro/connector-platform` as the best small merge-ready candidate because it projects connector readiness from registry metadata and preserves the compiled-runtime/ledger path.
   - Gate: full `pytest -q`, diff check, and no regression to connector secret/runtime behavior.

2. **Merge trust/admin hardening after rebase/test verification**
   - Treat `N2-Pro/trust-admin-security` as a merge-ready candidate for internal operator hardening, not external Admin/SaaS launch readiness.
   - Gate: rebase onto the current baseline, run focused audit/operator/security tests, and confirm no semantic-validation or audit-redaction regressions.

3. **Reconcile and rebase work-management before workflow expansion**
   - Treat `n2-pro-work-management` as high-value but not mergeable as-is until it preserves both current audit metadata contracts: severity/priority change tracking already in base plus SLA/due-date/evidence/timeline metadata from the branch.
   - Gate: preserve the forbidden-transition regression, run focused WorkItem/operator-case tests, and avoid merging a branch that overwrites current recurrence metadata.

4. **Merge workflow automation after WorkItem/work-management semantics are clean**
   - Treat `N2-Pro/workflow-automation` as ledger-first and merge-ready in direction, but sequence it after WorkItem/work-management reconciliation because queue projections should build on the canonical case/work-item shape.
   - Gate: rebase first; run focused workflow/audit/operator tests; keep execution paths governed by the workflow action ledger.

5. **Hold or split operator surfaces until projection primitives lead**
   - Keep `N2-Pro/operator-surfaces` in needs-work mode until bespoke endpoints are reduced or backed by shared query/view helpers.
   - Gate: no new surface may duplicate `store.list_cases(...)` projection logic; use built-in views, WorkItem query fields, facets, and canonical case projections instead.

6. **Treat search/analytics as unreviewed in the latest ARB checkpoint**
   - Do not promote `N2-Pro/search-analytics` from the older merge-ready-with-rebase note until a fresh review confirms it stays inside canonical WorkItem/JQL/facet/view primitives.
   - Gate: rebase onto current base; reject local KPI or endpoint-local field semantics; keep registry metadata and shared case-query helpers as the source of truth.

7. **Roll semantic-registry enforcement out across preview/report/surface boundaries**
   - Keep enforced case gating as the baseline, then add explicit validation hooks for report/surface preview paths.
   - Gate: deterministic metric-registry failures must block invalid owner-facing projections without letting report text or WhatsApp become case/source-of-truth state.

8. **Service-management/SLA as nested projections**
   - Integrate `codex/service-management` only as Jira Service Management-style projections over canonical cases and only when the slice is D2C-pilot useful.
   - Gate: `waiting_owner`, `waiting_external`, SLA status, escalation reason, and service record type stay nested service/owner fields; canonical WorkItem status categories remain exactly `to_do`, `in_progress`, and `done`; deferred families such as `channel_mix_shift` remain non-owner-facing until Packet N gates pass.

9. **Edge/developer and external-action toolkits stay contract-first**
   - Keep gateway/service-catalog/external-action toolkits internal unless they include durable idempotency, rate-limit, audit, route-coverage, provider capability, and redacted-response enforcement.
   - Gate: docs and API payloads must not imply production gateway or provider execution when code only reserves capabilities or declares policy metadata.

10. **Pilot-readiness docs after truth gates, not before**
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
