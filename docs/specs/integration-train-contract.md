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

### 2026-05-31 status checkpoint

The 2026-05-31 integration cycle merged the two architecture-review branches that were marked merge-ready:

- `codex/work-management` landed richer OperationalCase workflow/status/action behavior, including `in_progress`, assignment, source-connector-aware case projections, and queue/workflow summary endpoints.
- `codex/connector-platform` landed registry-driven daily-report factory metadata and the registry path used by `run_enabled_connectors_daily_report_pipeline`.
- Follow-on runtime/semantics and case-workflow commits added money/currency metric diagnostics and source/priority split operator summaries.

The same review explicitly did **not** clear `codex/trust-admin-security` as Trust/Admin/Security-complete. Treat its gaps as the next integration train's first blocking item, not as a completed platform capability.

Evidence checked for this checkpoint:

- Git history on `feat/orvo-brain-control-plane`: `4d979c9` merged `codex/connector-platform`; `9ad3c8b` and `f3576c9` merged `codex/work-management`; later `claude/runtime-semantics` and `claude/case-workflow` merges landed through `4456d0e`; head was `4ffcc02` during this docs sync.
- `app/brain/operational_cases.py` defines `open`, `acknowledged`, `in_progress`, `resolved`, `dismissed`, deterministic transition rules, `case_assigned`, and actionable statuses.
- `app/brain/operator_api.py` exposes whitelisted case action keys including `assign_owner` and `mark_in_progress`, plus source connector projections derived from evidence snapshots.
- `app/brain/connector_registry.py` defines allowlisted `ConnectorFactoryParam` / `ConnectorExecutorMetadata`; `app/brain/pipeline.py` routes multi-connector daily report execution through `_build_daily_report_for_connector_type`.

Recommended order:

1. **Trust/Admin/Security audit and authorization closure**
   - Convert the 2026-05-31 architecture-review blockers into implementation packets before claiming Trust/Admin/Security readiness.
   - Audit failed/denied case actions and auth failures, not only successful mutations.
   - Add a minimal action-scope/RBAC boundary or explicitly document the branch as audit-foundation-only.
   - Gate: internal operator API tests for rejected action keys, invalid transitions, scope failures, and auth failures proving redacted audit events are written where an actor/business can be derived.

2. **Work-management contract cleanup after merge**
   - Reconcile the merged workflow with the written Operational Case contract: manual `resolve_case` must require a reason, and the removal of direct `open -> resolved` needs an explicit release/contract note.
   - Keep Jira-like follow-ups tracked but scoped: project abstraction, issue-type registry/versioning, and status categories should be separate packets rather than opportunistic central-model edits.
   - Gate: lifecycle/action tests around resolve reasons and transition-table contract assertions.

3. **Connector registry runtime hardening**
   - Move from transitional inline secret params toward runtime secret-ref resolution for Tiendanube/MercadoLibre/Meta Ads before promoting registry execution as compiled-runtime complete.
   - Keep registry executor metadata allowlisted and avoid tenant-controlled import paths.
   - Gate: connector registry tests proving required secret refs resolve at runtime, runtime hashes do not include secret values, and redacted failures open/update `data_stale` rather than leaking credentials.

4. **Semantic registry / connector family alignment**
   - Replace typo-prone string drift in connector `emitted_metric_families` with shared semantic registry family identifiers or equivalent contract tests.
   - Keep `channel_mix_shift` deferred/internal until channel-scoped metrics, stale-source suppression, and dedupe/entity-scope tests are green.
   - Gate: tests fail when a connector declares a family absent from the semantic registry or emits a report/case metric outside its declared families.

5. **Pilot-readiness runbook refresh**
   - Update the Tiendanube/WhatsApp-first pilot checklist to reflect the real merged runtime, ledger, case, evidence, operator-action, and source-split summary surfaces.
   - Keep WhatsApp as a projection/delivery surface, not the source of truth.
   - Gate: docs link validation, secret scan, and one dry-run operator report artifact.

Do not start broad automation, marketplace/extensibility, or Meta Ads/channel-mix expansion until this train can explain every owner-facing claim from runtime, ledger, cases, and evidence and until Trust/Admin/Security blockers are either fixed or explicitly scoped out of live use.

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
