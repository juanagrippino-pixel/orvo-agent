# Orvo N2 Pro autonomous operating system

Status: Active operating mode for current N2 Pro cron jobs
Date: 2026-06-13
Last reconciled: 2026-06-15
Provider/model: OpenRouter `nex-agi/nex-n2-pro:free`
Canonical branch: `feat/orvo-brain-control-plane`
Canonical repo: `/root/orvo-agent`
Worker root: `/root/orvo-agent-worktrees`

## Relationship to the May 30 operating model

The May 30 document [`2026-05-30-codex-24-7-autonomous-operating-system.md`](2026-05-30-codex-24-7-autonomous-operating-system.md) remains useful for the product/control-plane operating model: Orvo is a sellable Atlassian-like D2C operations control plane, not a report bot or generic agent demo.

This N2 Pro note supersedes only the provider-specific rule that normal Orvo work must be Codex-first. Current scheduled jobs may run on N2 Pro free through OpenRouter when the job charter explicitly says so, while preserving the same repo, worktree, test, and integration guardrails.

## Product/control-plane invariants

- Orvo Brain is the operating system for LatAm/Tiendanube/WhatsApp-first D2C operations.
- `OperationalCase` / `WorkItem` is the native product object.
- WhatsApp, reports, queues, timelines, APIs, automations, and playbooks are projections or actions around cases/workflows.
- LLMs may explain, draft, and synthesize; deterministic runtime, registries, ledgers, cases, and tests decide state.
- Surfaces never become the source of truth for lifecycle state, metric values, case priority, dedupe, or automation side effects.

## Current N2 Pro job boundaries

- Keep implementation work in isolated external worktrees under `/root/orvo-agent-worktrees`.
- Keep the parent repo clean except for verified docs/integration commits.
- Do not create, update, pause, resume, or remove cron jobs from cron-run agents unless the explicit job charter is Orvo ops under controller supervision.
- Do not push to GitHub from autonomous jobs unless the job charter explicitly delegates push/deploy.
- Prefer docs, review, and narrow verification work when running under the free N2 Pro lane.
- For coding work, require TDD, focused tests, broader regression tests when feasible, diff review, and secret checks before commit.

## Integration posture after latest ARB review

Latest source: [`docs/architecture-reviews/2026-06-15-arb-architecture-alignment-review.md`](../architecture-reviews/2026-06-15-arb-architecture-alignment-review.md), [`docs/architecture-reviews/2026-06-15-work-management-jql-review.md`](../architecture-reviews/2026-06-15-work-management-jql-review.md), [`docs/architecture-reviews/2026-06-15-semantic-connector-review.md`](../architecture-reviews/2026-06-15-semantic-connector-review.md), and [`docs/architecture-reviews/2026-06-15-workflow-trust-security-review.md`](../architecture-reviews/2026-06-15-workflow-trust-security-review.md). The older branch-readiness matrix is now historical context; the consolidated alignment review is the current branch-sequencing note.

- Current HEAD (`3fd74eed`) remains aligned enough for the MVP control plane: `OperationalCase` is still the durable state owner, WorkItem/JQL/query metadata stay projection primitives, and the semantic registry remains the canonical metric source.
- Connector-platform hardening is already on the canonical branch, so keep the connector-health/runtime path green rather than treating the old branch as the next merge target.
- Preferred next merge lane after rebase/order: `n2-pro-work-management`, `N2-Pro/workflow-automation`, `N2-Pro/trust-admin-security`, then `N2-Pro/search-analytics` on top of the work-management field/query model.
- Needs re-scope before promotion: `N2-Pro/operator-surfaces` and `N2-Pro/service-management`.
- Workflow automation stays projection/governance-first for now: planning/idempotency/approval primitives are acceptable, but there is still no real executor, durable approval state machine, or full side-effect audit integration.
- Search, operator-surface, and service-management work must consume WorkItem/JQL/built-in-view/query-field primitives; reject bespoke recent-case projections or a second search/filter model.
- Not mergeable: destructive `claude/*` refactor branches.

The integration train should continue to merge narrow, additive slices that strengthen registries, audit, readiness, deterministic workflow plumbing, and shared query/view primitives. It should reject wholesale merges that duplicate projection logic, weaken semantic validation, delete accepted tests, or let bespoke operator endpoints become source of truth.

## Verification handles

A controller should verify each run:

```bash
cd /root/orvo-agent
git status --short
pytest -q
git worktree list
```

For code changes, run focused tests first, then the broader suite, then review the diff for architecture duplication, misplaced business logic, and security/secret risks.
