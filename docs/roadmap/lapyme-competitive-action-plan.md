# Competitive action plan: 2 weeks (2026-06-12 → 2026-06-26)

Source: `docs/research/2026-06-12-lapyme-orvo-strategy-deep-dive.md`
Internal benchmark plan. No public mention of La Pyme/Tango in any output.

## Goal

Make Orvo demo-able and sellable as an operating-control-plane slice
(Milestone 4C feel) with honest module readiness, a working case follow-up
loop, and the first real product videos — without ERP scope creep.

## Week 1 (06-12 → 06-18)

### Build

1. **OS snapshot / operator home** (top priority, unblocks video V2):
   module health for Ventas / Stock / Atención / ARCA / Caja derived from
   connector/runtime/case state; setup-required cases for unconnected lanes.
2. **Console case queue + timeline polish** for `sales_drop`,
   `stockout_risk`, `data_stale`: acknowledge / comment / resolve from the
   console; next brief reflects open/resolved state.
3. **Demo tenant** with synthetic/redacted data passing redaction tests —
   the recording substrate for all videos and sales calls.

### GTM/content

4. Update pilot copy from "reporte/brief" to "centro operativo de tu tienda"
   (close kit + onboarding checklist), claims mapped to implemented or
   explicitly readiness-labeled capabilities.
5. Script + record **V2 product walkthrough** (console/OS snapshot, 2–3 min)
   on the demo tenant; frame-check for secrets before sharing.

## Week 2 (06-19 → 06-26)

### Build

6. **Pilot activation hardening:** Tiendanube connect → first run → first OS
   snapshot → first WhatsApp brief; document the path in the pilot runbook.
7. **Internal MCP read-only spike** over the operator API (case queue, run
   history, OS snapshot projections; evidence refs; no writes). Internal use
   only; informs the later "ask your assistant" upsell.
8. Quiet prep (no shipping): Tiendanube partner/dev account + app-scope
   mapping to the connector registry entry; draft listing copy as "centro
   operativo / monitoreo", category Gestión.

### GTM/content

9. Record **V3 case demo** (stockout, 60s) and **V1 founder explainer**
   (60–90s); publish V1/V2 on landing when site work is approved (landing
   edits are out of scope for this task's branch).
10. First 3 SEO pages drafted from product contracts: centro operativo para
    ecommerce PyME; Tiendanube + stock + ventas; qué es un caso operativo.

## Explicitly deferred (do not start)

- ARCA invoicing issuance (readiness lane only).
- Accounting/treasury ledgers or reconciliation writes.
- Public API/MCP, public Tiendanube listing, Mercado Libre connector.
- POS, multicurrency, custom report builder.
- Any stack migration (Next/Supabase/etc.).

## Exit criteria (06-26)

- A merchant-facing demo: console with module health + case follow-up loop +
  WhatsApp brief, all evidence-backed, degraded states honest.
- V1/V2/V3 recorded from real product surfaces on the demo tenant.
- Pilot activation path documented and rehearsed once end-to-end.
- USD 149 pilot kit updated to centro-operativo language.
- No new owner-facing claims without evidence/readiness gates; full suite green.
