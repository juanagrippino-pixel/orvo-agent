# Orvo organization documents

This directory is the durable source of truth for the autonomous product organization building Orvo Brain as a sellable Atlassian-like ecommerce operations control plane.

## Precedence

1. Architecture decisions in `docs/adr/` and the Phase A architecture contract are binding for code ownership and invariants.
2. `orvo-operating-toolchain-blueprint.md` is the canonical operating/toolchain contract for how the autonomous organization turns capacity into product artifacts.
3. `autonomous-org-operating-plan.md` is the current department map and execution model.
4. Research notes are inputs, not binding strategy. Anything that still frames Orvo as Hito/report-first is superseded by the product pivot.

## Current files

- [Orvo operating toolchain blueprint](orvo-operating-toolchain-blueprint.md)
- [Autonomous organization operating plan](autonomous-org-operating-plan.md)
- [Autonomous org research v2](autonomous-org-research-v2.md)
- [Product pivot correction](product-pivot-correction.md)

## Product north star

Orvo is not a chatbot, dashboard, or daily-report service. Orvo is a control plane for D2C ecommerce operations where `OperationalCase` / `WorkItem` is the native product object and WhatsApp, reports, queues, timelines, APIs, automations, and playbooks are projections/actions around that object.
