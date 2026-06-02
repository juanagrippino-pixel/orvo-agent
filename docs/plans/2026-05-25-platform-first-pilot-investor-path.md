# Platform-First Pilot + Investor Path

## Decision

Orvo should be built primarily as the **long-term mature/scalable platform** because that is where the meaningful upside is: high-ticket product potential, investor interest, defensibility, and a much larger company outcome.

The Tiendanube/WhatsApp pilot is not the destination. It is the first proof loop for the platform.

## Core thesis

Orvo is not a cheap alerting plugin.

Orvo is an operational control plane for LatAm PyMEs: it connects fragmented business tools, understands operational state, turns problems into actionable cases, and coordinates execution through WhatsApp, dashboards, and APIs.

## Priority rule

When a short-term pilot decision conflicts with the long-term platform direction, choose the path that keeps the platform intact, unless the shortcut is explicitly temporary and isolated.

Build the wedge only through reusable platform primitives:

- connector registry,
- compiled runtime,
- metric registry,
- run ledger,
- operational cases,
- audit trail,
- operator surfaces,
- WhatsApp delivery/reply channels.

Do not build one-off Tiendanube scripts that cannot become part of the platform.

## Why still do the pilot

The pilot exists to avoid building a beautiful platform in a vacuum.

It should generate:

1. real merchant workflows,
2. painful operational cases,
3. evidence for product decisions,
4. screenshots and demo material,
5. proof that owners will use WhatsApp/operator workflows,
6. early testimonials or design partners,
7. investor credibility.

The pilot is a validation loop, not a downgrade in ambition.

## Time horizon

### 4–8 weeks: private proof loop

Goal: make one Tiendanube/WhatsApp merchant workflow useful enough that Juan would not feel embarrassed showing it.

Must prove:

- Orvo can ingest real store data.
- Orvo can detect a few real operational cases.
- Orvo can send an actionable WhatsApp brief through the real Meta Cloud API path.
- Orvo can maintain run/case history.
- Orvo feels like the beginning of an operator, not just a generic report.

### 2–4 months: investor-ready demo

Goal: demo the platform direction with a concrete wedge.

Must show:

- connected merchant data,
- deterministic case creation,
- case lifecycle or action loop,
- WhatsApp as owner/operator interface,
- internal operator/API surface,
- platform architecture that can expand beyond Tiendanube.

This is the point where Juan can start investor conversations if the demo is solid.

### 6–12+ months: scalable platform foundation

Goal: move from private pilot to productized platform.

Needs:

- multi-tenant onboarding,
- production secret management,
- stronger operator UI,
- more case families,
- richer connector set,
- billing/auth/permissions,
- observability/SLOs,
- support/runbooks,
- investor/product metrics.

## Product posture

For customers/design partners:

> “We are opening a small private pilot for Tiendanube stores. Orvo connects to your operation, detects operational issues, and helps you manage them through WhatsApp. The goal is to build the operating layer for ecommerce teams, starting with a few serious stores.”

For investors:

> “LatAm PyMEs run on WhatsApp and disconnected SaaS tools. Orvo is building the operational control plane that connects those tools, creates a live model of the business, and coordinates execution through cases and operator workflows. We are starting with D2C ecommerce because Tiendanube/WhatsApp creates a concentrated wedge with urgent operational pain.”

## Near-term execution emphasis

1. Fix/verify Meta Cloud API WhatsApp end-to-end.
2. Make Tiendanube ingestion reliable for real merchant data.
3. Upgrade reports into operational cases with lifecycle and evidence.
4. Build minimal operator surface/demo path.
5. Preserve platform contracts in every implementation.
6. Use Claude Code workers for code/review tasks to conserve Hermes tokens.
7. Keep the main repo clean and commit green docs/code promptly.

## Anti-goals

- Do not position Orvo as a cheap Tiendanube alert app.
- Do not optimize for low-ticket micro-SaaS pricing.
- Do not overbuild a generic platform before the wedge proves real pain.
- Do not let LLM-generated summaries become the source of truth.
- Do not promise full automation before the case/action loop is reliable.

## Success definition

The strategy is working if, within 2–4 months, Orvo can show a credible demo where:

1. a merchant connects operational data,
2. Orvo detects real cases,
3. the owner receives useful WhatsApp guidance,
4. an operator can inspect/follow cases,
5. the architecture clearly supports expansion,
6. investors can understand why this becomes a platform, not a feature.
