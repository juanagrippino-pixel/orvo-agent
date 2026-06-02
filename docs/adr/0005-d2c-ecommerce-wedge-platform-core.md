# ADR-0005: D2C ecommerce wedge with platform/control-plane core

Status: Accepted
Date: 2026-05-24

## Context

Orvo has two directions that must not be confused:

1. The **first sellable product** needs a narrow, urgent buyer story.
2. The **internal architecture** needs to become a durable control plane, not a pile of bespoke report scripts.

The strongest product wedge is D2C ecommerce in Argentina/LatAm, starting with Tiendanube + WhatsApp and expanding to ads, marketplaces, fulfillment, inventory, and support conversations. The strongest architecture is the Atlassian-style platform/control-plane model already captured in the Phase A contract: brokered configuration, compiled runtime, connector registry, run ledger, semantic registry, Operational Cases, governance, and operator surfaces.

This ADR records the product decision requested by the business owner: sell the focused D2C ecommerce control plane first, while building the internals as a general platform/control-plane foundation.

## Decision

Orvo's first sellable product is:

> A control plane for D2C ecommerce operators that detects, prioritizes, and coordinates operational cases across commerce, ads, inventory, fulfillment, and customer conversations — delivered first through WhatsApp/operator workflows, not as a generic chatbot.

Internally, Orvo must still be built as a platform/control plane:

- `OperationalCase` remains the native issue/workflow object.
- `CompiledBusinessRuntime` remains the execution contract for preview, forced, scheduled, and future API/UI runs.
- Connector/metric/run-ledger/secret/operator API boundaries stay platform-grade.
- D2C/Tiendanube/WhatsApp is the first vertical packaging and prioritization lens, not a reason to hard-code tenant-specific shortcuts.

Short version:

```text
Sell: "Orvo operates your ecommerce with evidence-backed cases and WhatsApp/operator workflows."
Build: "Orvo is a governed control plane for cases, workflows, connectors, runtime policy, audit, and automations."
```

## Product wedge boundaries

### In scope for first sellable wedge

- D2C ecommerce businesses, initially Argentine/LatAm SMBs.
- Tiendanube as the first commerce source of truth.
- WhatsApp as the first owner/operator surface.
- Operational cases for revenue/order deviations, stock risk, stale data, fulfillment/backlog signals, spend/order mismatches, and unanswered conversations where data exists.
- Daily and forced operational summaries sourced from deterministic metrics/cases.
- Internal operator API/surfaces for configuration, run history, cases, degraded states, and manual follow-up.
- Evidence-backed recommendations with explicit source/degraded-mode honesty.

### Out of scope for the first wedge

- Generic agent platform positioning.
- Developer-facing SDK/API as the primary buyer story.
- Horizontal Jira/Linear replacement for all teams.
- Mini-ERP scope: accounting, HR, full inventory master, payment reconciliation, or customer support suite replacement.
- LLM-created metrics, hidden case state in chat text, or irreversible automations without case/action governance.

## Architecture implications

1. Product copy, sales demos, onboarding, and first roadmap should speak D2C ecommerce language.
2. Code must preserve platform abstractions even when only Tiendanube/WhatsApp are active.
3. New connector work should ask: does it improve the D2C operational picture or unlock a case family?
4. New UI/API work should ask: does it help an operator inspect, prioritize, or resolve cases?
5. Reports are a wedge/projection. They are not the system of record.
6. Autonomous worker lanes should prioritize the platform primitives that make the D2C wedge real: runtime, registry, ledger, semantic registry, case engine, operator API, and trusted projections.

## First case families to prioritize

The first D2C wedge should bias toward cases a store owner immediately understands:

1. `sales_drop`: orders/revenue below baseline or expected range.
2. `stockout_risk`: high-selling SKU/product near zero stock.
3. `spend_without_orders`: ad spend continues while commerce orders underperform.
4. `data_stale`: Tiendanube/ads/support data missing or stale enough to narrow advice.
5. `fulfillment_backlog`: paid/unfulfilled orders or aging fulfillment queue when connector support exists.
6. `unanswered_conversations`: sales/support conversations waiting too long when WhatsApp/support data exists.
7. `channel_mix_shift`: marketplace/storefront/ad channel diverges from normal mix once multi-channel inputs exist.

Each case family must be deterministic, evidence-backed, deduped, and auditable before it becomes owner-facing.

## Consequences

### Positive

- Sales positioning becomes concrete: D2C ecommerce operators buy operational outcomes, not abstract infrastructure.
- Architecture stays ambitious enough to avoid rebuilding when Orvo expands beyond the first wedge.
- Worker lanes get a clear priority filter: platform primitives that make D2C cases real beat broad horizontal features.
- WhatsApp remains a strong adoption surface without becoming the source of truth.

### Negative / costs

- Some generic platform capabilities must wait until they support the D2C wedge.
- We must resist demo-only shortcuts that would help Tiendanube quickly but damage platform contracts.
- Product docs must maintain two layers of language: buyer-facing ecommerce outcomes and implementation-facing control-plane primitives.

## Invariants for future workers

1. Do not position the first product as a generic chatbot or generic agent platform.
2. Do not build Tiendanube/WhatsApp shortcuts that bypass connector registry, compiled runtime, run ledger, metric registry, case engine, or audit contracts.
3. Do not add workflow-like objects that compete with `OperationalCase`.
4. Do not make reports or WhatsApp text the source of truth for state.
5. Do not broaden product scope unless it strengthens the D2C control-plane wedge or is explicitly accepted in a later ADR.
6. Do not let LLMs create metrics, cases, priorities, or lifecycle transitions.
