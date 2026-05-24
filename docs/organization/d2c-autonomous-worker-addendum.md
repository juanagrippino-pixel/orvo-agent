# D2C Control Plane Autonomous Worker Addendum

Status: Binding addendum for Orvo workers
Date: 2026-05-24
Related: `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`, `docs/roadmap/d2c-control-plane-roadmap.md`

## North star

First sellable product:

> D2C ecommerce control plane for Tiendanube/WhatsApp-first operators.

Internal architecture:

> Atlassian-like platform/control plane with compiled runtime, connector registry, run ledger, metric registry, Operational Cases, governance, and operator surfaces.

## Required prompt preamble for new workers

Use this in future autonomous worker prompts:

```text
STRATEGY
Orvo's first sellable product is a D2C ecommerce control plane for Tiendanube/WhatsApp-first operators. Build internally as a platform/control-plane core: compiled runtime, connector registry, run ledger, metric registry, Operational Cases, audit/governance, and operator surfaces.

PRIORITY FILTER
First-wave work must strengthen the D2C ecommerce wedge without bypassing platform contracts. Do not build a generic chatbot, generic agent platform, or Tiendanube/WhatsApp shortcut that bypasses runtime/registry/ledger/cases/audit.

SOURCE OF TRUTH
Read ADR-0005, the D2C PRD, the case family catalog, the operator surface contract, and the roadmap before changing product/architecture direction.
```

## Source-of-truth docs

Workers must prefer these docs over older milestone-first or generic-platform wording:

- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-ecommerce-control-plane.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`
- `docs/plans/2026-05-24-d2c-control-plane-first-product.md`
- `docs/architecture/phase-a-control-plane-contract.md`

## Lane priorities

### Runtime / Registry lane

Priority:

1. compiled runtime parity;
2. Tiendanube registry definition;
3. connector degraded-state semantics;
4. secret refs/redaction;
5. execution shim for preview/forced/scheduled.

### Metric / Semantics lane

Priority:

1. D2C metric families;
2. aliases for legacy metrics;
3. evidence rules;
4. detection contracts for first case families.

### Operational Case lane

Priority:

1. models/storage;
2. deterministic creation from insights/runtime events;
3. dedupe/reopen;
4. evidence snapshots;
5. case timeline events.

### Operator Surface lane

Priority:

1. internal run inspection;
2. case queue;
3. case timeline;
4. WhatsApp brief as projection;
5. manual comments/actions.

### QA / Red-team lane

Priority:

1. unsupported claims in owner-facing text;
2. stale-data honesty;
3. duplicate case spam;
4. secret leakage;
5. runtime parity regressions;
6. report compatibility breakage.

### GTM / Product lane

Priority:

1. buyer language for D2C operators;
2. demo narratives grounded in implemented capabilities;
3. pilot onboarding checklist;
4. objections and pricing/package hypotheses;
5. avoid generic agent-platform positioning.

## Stop rules

Stop and report instead of continuing if:

- a task requires storing or exposing raw credentials;
- code would bypass compiled runtime/registry/ledger/cases for speed;
- two workers need to edit the same core file without sequencing;
- tests reveal current Hito0/runtime behavior would break;
- a surface would make a claim without evidence;
- the only path forward is broad rewrite.

## Output requirements

Every autonomous worker summary must include:

- branch/worktree;
- commit SHA or explicit no-commit reason;
- files changed;
- tests/checks run;
- product impact in D2C terms;
- platform contract impact;
- risks/blockers;
- whether parent repo remained clean.

## Cron safety

Recurring agents must not create, update, pause, resume, remove, or schedule cron jobs unless their explicit charter is scheduler/orchestration management. They may recommend job changes in their summary.
