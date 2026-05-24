# Orvo Autonomous Organization Operating Plan

> Created to move from a "mini organization" of agents to an actual autonomous operating system for Orvo Brain.

## Objective

Run Orvo as a layered autonomous organization that continuously converts model capacity into verified product, research, architecture, implementation, QA, integration, and operations progress.

The organization's first hard trust milestone remains **Hito 0**: a real 08:00 Argentina WhatsApp report for ARTEMEA/client-zero with dry, non-AI tone. Platform work is allowed and encouraged, but it must be additive and must not regress Hito 0.

## Operating principles

1. **Capacity becomes artifacts, not noise.** Extra gpt-5.5/openai-codex usage must show up as research outputs, specs, commits, tests, evals, review findings, or integration plans.
2. **Layered organization, not flat swarm.** Departments have ownership and gates; they do not all edit the same files.
3. **Parent repo stays clean.** `/root/orvo-agent` is the integration checkout. Workers use external worktrees under `/root/orvo-agent-worktrees`.
4. **Research feeds implementation.** Research and architecture outputs are wired into implementation/review/integration lanes through cron `context_from` and repo docs.
5. **Human-controlled integration.** Autonomous workers may prepare branches, commits, tests, and merge plans; push/deploy/major merge decisions remain human-controlled unless explicitly delegated.
6. **Verification beats self-report.** Worker summaries are untrusted until checked by git status, diffs, tests, commits, and file inspection.
7. **Hito 0 wins conflicts.** If architecture/platform work conflicts with first customer trust, Hito 0 gets priority.

## Departments and live jobs

| Department | Job ID | Cadence | Role |
|---|---:|---|---|
| Chief of Staff / COO | `661036933588` | every 60m | Coordinates the org, audits lanes, makes operating decisions, launches bounded workers. |
| Product & Market Intelligence | `11d230a06306` | every 3h | LatAm/Tiendanube/WhatsApp ecommerce research, product wedge, specs. |
| Architecture Review Board | `156fc69339e5` | every 3h | Control-plane architecture, ADRs, invariants, module boundaries. |
| Engineering Factory Manager | `19a7934d892f` | every 90m | Selects implementation slices, prevents overlap, launches bounded coding workers. |
| QA / Red Team Director | `be285bc8f107` | every 75m | Evals, golden tests, regression gates, failure scenarios. |
| Release / Integration Manager | `9273c4bc5131` | every 90m | Reviews branches, verifies tests, prepares safe integration order. |
| SRE / Operations Director | `d62555476c05` | every 60m | Cron/gateway/watchdog health, repo hygiene, logs, delivery risks. |
| Knowledge / Roadmap Librarian | `c155ea848ddb` | every 3h | Keeps docs, ADRs, roadmap, specs coherent and current. |
| Board Report | `61c5bd141ea2` | every 4h | Executive synthesis for Juan. |

## Existing specialist lanes absorbed into the org

These existing lanes remain active as specialist production units:

- Hito0 runtime lane: `70e0189b04a2`
- Hito0 reliability lane: `ebb43bdc7fe5`
- Hito0 reporting lane: `1af3dff762ac`
- Hito0 evals lane: `ef61ae4b51c6`
- Hito0 observability lane: `69bec26899b0`
- Deep research architect: `51ef44f54957`
- Research-to-implementation worker: `24de093511bf`
- Research market lane: `bcd31561788e`
- Research architecture lane: `ba3aeb852f40`
- Implementation runtime lane: `6dca27f31a95`
- Implementation review lane: `6ab866a6acaf`
- Integration controller lane: `1a14a8ed4d5e`
- Metric semantics lane: `fe5814e07377`
- Operational case lane: `88c926969f63`
- Connector contract lane: `daad02bc0620`
- Operator API/timeline lane: `20fe2125e513`
- Platform evals/redteam lane: `411d6caf9cd1`
- Platform docs/roadmap curator: `adb1536b4199`

## Department interaction graph

```text
Product & Market ─┐
Deep Research ────┤
Architecture Board ├──> Knowledge/Roadmap ───┐
                  │                           │
                  └──> Engineering Factory ───┼──> QA/Red Team ───> Release Integration
                                              │                         │
SRE/Ops ──────────────────────────────────────┘                         │
                                                                        ↓
Chief of Staff / COO <──────────────────────── Board Report <───────────┘
```

## Weekly operating model

The system runs continuously, but decisions should be interpreted in this rhythm:

- **Every hour:** Chief of Staff and SRE check health, blockers, and whether capacity is being used productively.
- **Every 75-90 minutes:** Engineering/QA/Release loops select, test, review, and prepare code branches.
- **Every 3 hours:** Product, Architecture, and Knowledge update the strategic source of truth.
- **Every 4 hours:** Board Report gives Juan a concise executive view.

## Gate taxonomy

### Pre-flight gates

- Parent repo `/root/orvo-agent` must be clean before long implementation workers start.
- Worker must have exact allowed files, tests, branch/worktree path, and commit/report schema.
- No worker may touch secrets or `.env` values.

### Revision gates

- Spec review before quality review.
- QA can request failing tests or golden fixtures before integration.
- Architecture Board can block broad changes that violate bounded contexts or Hito 0 compatibility.

### Escalation gates

Escalate to Juan only when:

- a merge/deploy/push decision is required;
- product direction has a real trade-off;
- a credential/customer account/action is needed;
- Hito 0 cannot proceed without external information.

### Abort gates

Stop or pause a worker if:

- parent repo is dirty and cause is unknown;
- worker edits outside scope;
- tests fail and root cause is not understood;
- secrets are exposed;
- multiple workers collide on same files.

## Immediate first-wave mandate

The first wave after creating the org should produce:

1. Current org state audit from Chief of Staff.
2. Product/market ranked opportunities tied to Hito 0 and OperationalCase.
3. Architecture Board invariants for metric registry, connector contracts, run ledger, and OperationalCase.
4. Engineering Factory implementation queue with non-overlapping worktrees.
5. QA/Red Team high-risk regression list and at least one new test/eval path if safe.
6. Release Integration inventory of existing worktrees/branches.
7. SRE health report for cron/gateway/repo hygiene.
8. Knowledge Librarian source-of-truth index.

## Success metric

A good autonomous-org day ends with:

- Hito 0 closer to a real customer report;
- at least one verified green branch/commit or test/eval improvement;
- clearer product/architecture decisions;
- fewer unknowns in integration and ops;
- concise report to Juan with evidence, not vibes.
