# D2C Control Plane Packaging and Messaging

Status: Draft GTM guide
Date: 2026-05-24
Related: `docs/product/d2c-ecommerce-control-plane.md`, `docs/product/d2c-control-plane-prd.md`

## Positioning

Primary category:

> Ecommerce operations control plane.

Short pitch:

> Orvo watches your ecommerce signals, opens evidence-backed cases, and tells the operator what needs attention today.

Spanish pitch variants:

- "Orvo te arma una cola operativa diaria: qué pasó, qué importa, por qué, y qué sigue."
- "Tiendanube + WhatsApp primero: menos dashboards, más casos accionables."
- "No es otro reporte. Es una lista priorizada de problemas y oportunidades con evidencia."

Avoid:

- "chatbot" as the category;
- "agent platform" as the first buyer story;
- "automatizamos todo" before governance/action safety exists;
- guaranteed revenue-lift claims;
- scammy phrasing or fake familiarity.

## Packages

### Concierge pilot

Goal: validate daily usefulness and willingness to pay.

Included:

- Tiendanube connector setup or assisted import.
- Daily WhatsApp/operator brief.
- Starter-safe case families: sales/stock/data freshness, plus only the case families verified for that merchant.
- Manual operator review/follow-up.
- Weekly improvement notes.
- Optional fulfillment readiness audit: inspect whether Tiendanube payment, shipping/fulfillment statuses, timestamps, exclusions, SLA, and resolver ownership are trustworthy enough for backlog monitoring.

Not included:

- full automation;
- custom dashboards;
- unsupported connectors;
- guaranteed outcomes.

### Control plane starter

Goal: paid first product for a small D2C operator.

Included:

- Tiendanube runtime.
- WhatsApp brief.
- case queue/history.
- run ledger inspection.
- configured thresholds.
- data freshness/degraded alerts.

Default off / setup-required unless verified:

- fulfillment backlog monitoring. If order/payment/shipping statuses are ambiguous, Starter should show a data-quality/setup case rather than “stuck order” alerts.

### Control plane growth

Goal: stores with ads and more operational complexity.

Included:

- verified `fulfillment_backlog` cases after the readiness audit passes;
- Meta Ads + commerce mismatch cases.
- marketplace/channel-mix cases only when connectors, freshness, and semantic-registry promotion gates exist.
- operator workflows/comments/actions.
- weekly case review.
- stronger SLA/freshness monitoring.

Fulfillment backlog positioning:

> “Starter watches stock and data freshness. Growth adds verified dispatch backlog once we confirm your payment/shipping states are reliable.”

Do not sell fulfillment backlog as a generic shipping app replacement. Orvo owns the evidence-backed Operational Case lifecycle and follow-up; shipping apps, ERPs, carrier tools, and Tiendanube admin remain the execution/source systems.

## Demo narrative

1. Start with business pain: owner checks too many tools and still misses operational issues.
2. Show daily brief with one top case.
3. Click/inspect evidence: where the number came from.
4. Show run health/degraded caveat.
5. Show open case timeline, not just a report paragraph.
6. Show what action/follow-up was recorded.
7. Explain architecture briefly only if asked: connectors, runtime, cases, audit.

## Objection handling

### "I already have dashboards"

Orvo is not replacing dashboards. Dashboards show metrics; Orvo opens operational cases, prioritizes them, and keeps follow-up history.

### "Can ChatGPT just summarize my data?"

The risky part is not summarizing. The risky part is knowing which data is fresh, which numbers are valid, what should become a case, and what is still unresolved. Orvo keeps that deterministic and auditable.

### "Can it automate actions?"

Eventually, yes, but first every action needs to be attached to a case with evidence, approval, audit, and rollback/inspection. The first product focuses on trustworthy detection and follow-up.

### "Is this only Tiendanube?"

Tiendanube is the first commerce source of truth. The architecture supports more connectors, but the first product is intentionally focused so it can be reliable.

## Claims allowed before implementation is complete

Allowed:

- Orvo is being built as a D2C ecommerce operations control plane.
- Tiendanube + WhatsApp are the first wedge.
- The product is designed around cases, evidence, run history, and operator follow-up.
- LLMs may help with wording, but business truth is deterministic.
- `fulfillment_backlog` is a readiness-gated module: it can be audited during pilot/Activation Sprint, but owner-facing backlog claims require verified payment, fulfillment, timestamp, SLA, exclusion, resolver, and freshness gates.

Do not claim live support for a connector/case/surface unless it is implemented and verified in the repo.

## Sales copy guardrails

Tone:

- direct;
- operational;
- concrete;
- Argentine Spanish when speaking to Argentine customers;
- no hype without proof.

Good phrases:

- "qué necesita atención hoy";
- "con evidencia de Tiendanube";
- "cuando una fuente está stale, Orvo lo dice y limita la recomendación";
- "casos abiertos y seguimiento".

Bad phrases:

- "te paso las letras";
- "IA mágica";
- "automatización total";
- "aumentá ventas garantizado";
- "conectamos todo en minutos" unless verified.
