# D2C Control Plane Roadmap

Status: Working roadmap
Date: 2026-05-24
Related: `docs/plans/2026-05-24-d2c-control-plane-first-product.md`

## Priority rule

First-wave work must strengthen the D2C ecommerce wedge without bypassing platform contracts.

```text
Tiendanube/WhatsApp use case wins prioritization.
Runtime/registry/ledger/cases/audit wins implementation shape.
```

## Milestone 1 — Trustworthy runtime foundation

Outcome: every report/run can be explained from a compiled runtime and run ledger.

Deliverables:

- compiled runtime parity across preview/forced/scheduled paths;
- Tiendanube connector registry entry with capabilities and degraded behavior;
- run ledger records connector results, artifacts, dispatch attempts, and typed errors;
- secret redaction invariant tests;
- existing report paths and docs examples remain green.

Exit criteria:

- A forced and scheduled run use the same executable runtime shape or compatibility shim.
- Operator can inspect what ran and why advice was narrowed/skipped.
- No raw secrets in run artifacts/logs/docs.

## Milestone 2 — D2C metric and case foundation

Outcome: Orvo opens durable ecommerce cases instead of only producing report paragraphs.

Deliverables:

- metric registry entries/aliases for first D2C families;
- `OperationalCase` models/storage/engine basics;
- deterministic case creation from current insights/runtime events;
- stable dedupe/reopen behavior;
- case evidence snapshots;
- tests for `sales_drop`, `stockout_risk`, `data_stale`.

Exit criteria:

- Repeated runs update existing cases rather than spam duplicates.
- Every case has evidence.
- Existing `DailyReport` compatibility remains green.

## Milestone 3 — Operator surfaces and WhatsApp projection

Outcome: owner/operator sees case-backed summaries and internal inspection surfaces.

Deliverables:

- case queue projection;
- case timeline projection;
- run history endpoint/surface contract;
- WhatsApp brief sourced from cases where available;
- manual follow-up comments/actions;
- degraded-data language in briefs.

Exit criteria:

- Owner-facing brief can cite case/evidence refs.
- Operator can inspect open cases and run health.
- Missing/stale sources suppress/narrow advice.

## Milestone 4 — Sellable Tiendanube/WhatsApp pilot operations

Outcome: Orvo can run a paid/concierge Tiendanube/WhatsApp pilot safely.

Meta Ads, `spend_without_orders`, and channel-mix cases are not prerequisites for the first Tiendanube/WhatsApp pilot; the first pilot gates are the PRD launch checklist and `docs/ops/d2c-pilot-readiness-checklist.md`.

Deliverables:

- onboarding checklist;
- threshold configuration guide;
- pilot SLA/freshness policy;
- support/runbook for connector failures;
- GTM packet aligned with actual capabilities;
- board-report loop tracking pilot usefulness and blockers.

Exit criteria:

- One real business can receive a daily useful brief.
- Operator can explain every claim.
- Failures degrade honestly.
- Follow-up history exists for open/resolved cases.

## Milestone 5 — Post-pilot revenue/ads wedge expansion

Outcome: Orvo identifies spend/order mismatch and higher-value cross-system cases after the Tiendanube/WhatsApp wedge is trustworthy.

Deliverables:

- Meta Ads + Tiendanube runtime freshness parity;
- `spend_without_orders` family;
- channel/source health surfaced in operator view;
- demo/sales examples using redacted data.

Exit criteria:

- Orvo never claims ad/commerce mismatch when either source is stale.
- Cross-source evidence is inspectable in run ledger/case timeline.

## Backlog until wedge is real

- generic app marketplace;
- developer-first SDK;
- broad horizontal team workflows;
- complex automations;
- dashboards not tied to case/action workflows;
- LLM explainer beyond validated projections.
