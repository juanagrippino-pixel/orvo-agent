# Orvo Brain + Atlassian control-plane 24/7 operating system

Status: Active operating mode
Date: 2026-05-30
Codex provider: `openai-codex`
Model: `gpt-5.5`
Canonical branch: `feat/orvo-brain-control-plane`
Canonical repo: `/root/orvo-agent`
Worker root: `/root/orvo-agent-worktrees`

## Operating decision

The Codex plan is renewed and becomes the primary execution path again. OpenRouter is not the normal route for Orvo work; it remains an emergency fallback only when explicitly requested or when Codex is hard-blocked.

The autonomous system must now run as a real product organization building an Atlassian-like D2C ecommerce operations control plane, not as a report bot or generic agent demo.

## North-star product

Orvo Brain is the operating system for LatAm/Tiendanube/WhatsApp-first D2C operations:

```text
External commerce systems
  -> connector registry + emitted metric/event contracts
  -> semantic registry + evidence model
  -> compiled runtime + run ledger + audit
  -> OperationalCase / WorkItem native object
  -> workflow states, comments, owners, SLAs, approvals
  -> operator surfaces: API, queue, timeline, WhatsApp, reports
  -> controlled automations, playbooks, governance, marketplace/connectors
```

WhatsApp and daily reports are surfaces. The product is the case/workflow/control-plane platform.

## Active department model

The organization is split by bounded ownership, not by random feature generation.

| Department | Ownership | Output |
|---|---|---|
| COO / Chief of Staff | priority arbitration, overlap detection, capacity allocation | operating memo, next bets, blockers |
| Product & Market Intelligence | ICP, buyer pains, Tiendanube packaging, pricing, GTM | research docs, offer specs, demo narrative |
| Architecture Review Board | source-of-truth boundaries, ADRs, platform invariants | review docs, ADR/spec changes |
| Engineering Factory | bounded implementation slices in external worktrees | commits with tests, worker manifests |
| QA / Red Team | invariant tests, adversarial scenarios, regression gates | tests/review findings/fix packets |
| Release / Integration | branch/worktree inventory, sequential merge plan, test gates | integration train, verified merge notes |
| SRE / Operations | cron/gateway/worktree health, repo hygiene, runtime/report dry-runs | health reports, incident notes, scripts |
| Knowledge / Roadmap | source-of-truth docs, roadmap, packet cleanup | committed docs/README/spec updates |
| Work Management Core | OperationalCase/WorkItem lifecycle | code/tests/specs around case object |
| Workflow Automation Platform | triggers, conditions, actions, approvals, audit | rule-engine code/tests/specs |
| Connector / Ecosystem Platform | connector registry, scopes, health, emitted events | contracts/tests/developer docs |
| Semantic Intelligence Platform | metrics/events/evidence semantics | registry code/tests/contract docs |
| Operator Surfaces | internal API, queue, timeline, WhatsApp/report projections | endpoints/tests/projection docs |
| Trust/Admin/Security | tenants, RBAC, audit, secrets, redaction | security tests/contracts/runbooks |
| Search/Query/Analytics | JQL-lite, saved views, dashboards, exports | query primitives/tests/specs |
| Service Management/SLA | incidents, escalations, request/change/problem records | SLA/case extensions/tests/specs |
| Edge/Developer Platform | broker/API, compiled runtime specs, gateway/auth/rate-limit/telemetry conventions | ADRs/specs/code slices for platform hardening |
| Board Reporter | concise executive synthesis for Juan | daily/periodic status and decisions |

## 24/7 execution rules

1. **Codex-first**: recurring LLM-driven jobs should run on `openai-codex` / `gpt-5.5` unless explicitly overridden.
2. **No stale OpenRouter mode**: do not route normal Orvo work to qwen/OpenRouter.
3. **No recursive cron changes**: cron-run agents must not create/update/pause/resume/remove/schedule cron jobs unless their explicit charter is Orvo ops under controller supervision.
4. **External worktrees only**: implementation jobs create/edit `/root/orvo-agent-worktrees/<lane>`; parent repo stays clean unless an integration controller is explicitly committing verified docs/integrations.
5. **One bounded slice per implementation run**: TDD first, focused tests, then broader `pytest -q` when feasible.
6. **No overlapping central edits**: central files like `app/brain/models.py`, `operator_api.py`, registry modules, and stores require explicit ownership and review before parallel edits.
7. **Worker handoff manifest required**: every implementation branch reports branch, worktree, commit SHA, files, tests, risks, secret check, and integration recommendation.
8. **Integration is sequential**: one branch at a time, tests after each merge, stop on first failure.
9. **Surfaces never become source of truth**: WhatsApp/reports/API/timeline project canonical cases/workflows; they do not own lifecycle state.
10. **LLMs explain; deterministic core decides**: no LLM-driven metric values, case transitions, priority, dedupe, or external side effects.

## First-wave Codex lanes

The first wave is designed to cover unfinished Atlassian-platform work without broad feature sprawl:

1. **Work Management Core** — close case-family consistency gaps, lifecycle invariants, case evidence lineage.
2. **Workflow Automation Platform** — rule dry-run, approval boundaries, idempotent action keys.
3. **Connector/Ecosystem Platform** — registry-driven execution gap, connector health/scopes/certification tests.
4. **Search/Query/Analytics** — safe built-in saved views/JQL-lite over cases/runs.
5. **Service Management/SLA** — SLA timers, escalation/request/incident mapping over OperationalCase.
6. **Edge/Developer Platform** — broker/API and gateway conventions inside current Python runtime before external infra.
7. **QA/Red Team** — regression tests for stale data, redaction, tenant scoping, action whitelists, case hidden/published policy.
8. **Release/Integration** — reconcile all autonomous worker branches and keep integration train current.
9. **Knowledge/Roadmap** — keep docs/specs/ADRs aligned with actual shipped surfaces.
10. **SRE/Ops** — keep Hermes/cron/watchdogs/gateway/daily-report and repo hygiene green.

## Immediate known action queue

These came from current code/doc audits and should be prioritized by lanes:

- Keep `channel_mix_shift` deferred/internal until Packet N promotes it with channel-scoped `CASE_FAMILY_METRICS`, stale-source suppression, and dedupe/entity-scope tests.
- Reduce connector-specific branching by making runtime execution consume registry metadata where safe.
- Keep operator API endpoints thin: auth, tenant/business scoping, response envelope, action-key whitelist, redaction at boundary.
- Add coverage-regression guard: workers must not make green suites by deleting tests.
- Keep docs/architecture-reviews and docs/research as durable inputs to implementation packets.
- Move from report-first prompts toward product surfaces: cases, workflows, connector contracts, search, SLA, admin, governance.

## Verification handles

A controller should verify each day:

```bash
cd /root/orvo-agent
git status --short
python -m pytest -q
git worktree list
hermes --version
```

Cron state should show all Orvo agent-driven jobs with `workdir=/root/orvo-agent`; script workers should use absolute paths.
