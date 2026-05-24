# Orvo D2C Ecommerce Control Plane

Status: Product direction accepted
Date: 2026-05-24
Related ADR: `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`

Companion docs:

- `docs/product/d2c-control-plane-prd.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`
- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/connector-registry-contract.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`
- `docs/gtm/d2c-packaging-and-messaging.md`
- `docs/ops/d2c-pilot-readiness-checklist.md`

## One-line thesis

Orvo is the operational control plane for D2C ecommerce: it turns Tiendanube/commerce, ads, inventory, fulfillment, and conversation signals into evidence-backed cases, priorities, workflows, and owner/operator actions.

## What we sell first

Sell this as a focused ecommerce operations product, not as infrastructure:

> Orvo watches the business, detects what needs attention, explains the evidence, and helps the operator act before issues become revenue loss.

Initial buyer-facing promise:

- Know what changed today.
- Know which issues matter most.
- Know why Orvo believes it.
- Know what action or follow-up is next.
- Keep a history of open/resolved operational cases.

## What we build internally

Build it as a platform/control plane:

```text
D2C systems
  -> connector registry + adapter execution
  -> canonical metric/semantic registry
  -> compiled business runtime
  -> deterministic detections
  -> Operational Cases
  -> projections: WhatsApp, operator API, future UI
  -> actions/workflows with audit and run ledger
```

The vertical wedge is D2C ecommerce. The internal architecture remains reusable across future verticals.

## First ICP

Primary ICP:

- Argentine/LatAm D2C brands or physical-goods ecommerce stores.
- Tiendanube-first or Tiendanube-heavy operations.
- Owner/operator still manages business through WhatsApp, spreadsheets, dashboards, or agency reports.
- Pain is not lack of dashboards; pain is deciding what to do every day across sales, stock, ads, fulfillment, and messages.

Best early customers:

- Have enough daily activity for deviations to matter.
- Feel operational chaos across tools.
- Already trust WhatsApp as an operating surface.
- Prefer a concrete operator/copilot outcome over a generic analytics dashboard.

## First surfaces

1. **WhatsApp owner/operator brief**
   - Short, evidence-backed summary.
   - New/open/resolved case highlights.
   - Degraded-data honesty.
   - Suggested next actions, never unsupported claims.

2. **Internal operator API/surface**
   - Business config and connector status.
   - Run history and artifacts.
   - Open cases and timelines.
   - Manual follow-up/action records.

3. **Future web UI**
   - Case queue.
   - Timeline.
   - Connector health.
   - Playbooks and approvals.

## First case families

| Case family | Buyer language | Sources |
| --- | --- | --- |
| `sales_drop` | Sales dropped versus normal/expected range | Tiendanube, marketplaces, manual/CSV during onboarding |
| `stockout_risk` | A product that sells is about to run out | Tiendanube inventory/product data |
| `spend_without_orders` | Ads spent but orders did not follow | Meta Ads + Tiendanube |
| `data_stale` | Orvo cannot safely advise because a source is stale/missing | Runtime/connector health |
| `fulfillment_backlog` | Orders are aging or stuck before delivery | Tiendanube/order/fulfillment data when available |
| `unanswered_conversations` | Sales/support chats are waiting too long | WhatsApp/support data when available |
| `channel_mix_shift` | Sales/channel mix moved abnormally | Tiendanube + MercadoLibre + ads, once multi-channel inputs exist |

## Messaging guardrails

Use language like:

- "Orvo operates your ecommerce from cases, evidence, and next actions."
- "A daily operating brief backed by your store data."
- "Tiendanube + WhatsApp first; control-plane architecture underneath."
- "Not another dashboard: a prioritized operating queue."

Avoid language like:

- "generic AI agent platform" for the first product.
- "chatbot" as the product category.
- "we automate everything" before case/action governance exists.
- unsupported promises around revenue lift, inventory accuracy, or root-cause certainty.

## Product priority filter

A task is first-wave priority only if it satisfies at least one of these:

1. Makes Tiendanube/commerce data more trustworthy.
2. Creates or improves an evidence-backed D2C case family.
3. Improves compiled runtime parity across preview, forced, and scheduled runs.
4. Improves run ledger/audit/degraded-mode inspection.
5. Helps an operator inspect, prioritize, resolve, or follow up on cases.
6. Preserves deterministic, cited WhatsApp/operator projections.

Otherwise it is backlog, even if it is interesting platform work.
