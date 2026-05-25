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

After the 2026-05-25 runtime/ledger/metric/operator-comment integrations, the next safe train should stay inside the existing control-plane path and avoid owner-facing delivery changes until each projection is evidence-backed.

Recommended order:

1. **Metric registry adoption gate**
   - Wire canonical metric validation into case detection/report generation in advisory mode first.
   - Keep legacy aliases accepted and do not change owner-facing wording.
   - Gate: metric registry contract tests, case-family compatibility tests, and full suite.

2. **Evidence snapshot canonicalization**
   - Ensure case timeline events reference canonical persisted evidence snapshot IDs, not ad-hoc refs from transient detection inputs.
   - Keep snapshot payloads redacted before persistence and response projection.
   - Gate: raw SQLite/store reload assertions for snapshot/timeline IDs and secret-shaped refs.

3. **Case-backed owner/operator brief dry projection**
   - Build a dry projection from actionable Operational Cases for owner/operator review, without enabling automatic WhatsApp delivery.
   - Exclude resolved cases, include evidence freshness, and keep total open-case counts truthful when truncating displayed cases.
   - Gate: golden brief tests for healthy, degraded, stale-data, and truncated queues.

4. **Operator search/view hardening**
   - Keep built-in case views read-only before any saved-view persistence.
   - Align docs, route enums, JQL allowlist, business scoping, limits, and redacted error envelopes.
   - Gate: built-in views match equivalent direct queries and SQL-looking input never reaches storage as SQL.

5. **Pilot-readiness runbook refresh**
   - Update the Tiendanube/WhatsApp-first pilot checklist to reflect the real runtime, ledger, case, evidence, and operator-comment capabilities.
   - Keep WhatsApp as a projection/delivery surface, not the source of truth.
   - Gate: docs link validation, secret scan, and one dry-run operator report artifact.

Do not start broad automation, marketplace/extensibility, or Meta Ads/channel-mix expansion until this train can explain every owner-facing claim from runtime, ledger, cases, and evidence.

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
