# La Pyme-Category MVP Scope

Status: Accepted product-direction adjustment
Date: 2026-06-11
Related: `docs/research/2026-06-11-lapyme-benchmark.md`, `docs/product/d2c-control-plane-prd.md`, `docs/roadmap/d2c-control-plane-roadmap.md`

## Decision

Orvo's MVP should look and sell like the first slice of an Argentine PyME operating system, not like a narrow report bot.

La Pyme validates that Argentine SMBs understand and pay for an operational system that joins commerce, stock, fiscal/admin workflows, reports, and AI over real data. Orvo should compete at that category level while preserving its current deterministic control-plane architecture.

## Product positioning

```text
Orvo is the AI-native operating control plane for Argentine commerce PyMEs.
The first wedge is Tiendanube/WhatsApp-first D2C operations.
```

Avoid these framings:

- WhatsApp bot;
- dashboard;
- generic agent platform;
- loose AI analyst;
- ERP clone.

## MVP category slice

The MVP should expose five visible capabilities even if some begin as readiness-gated/projection-only modules:

1. **Sales/orders operating truth**
   - Tiendanube orders, sales metrics, evidence refs, sales-drop cases.
   - This remains the core wedge.

2. **Stock/fulfillment attention**
   - `stockout_risk` and readiness-gated `fulfillment_backlog`.
   - Suppress owner-facing claims when order/status evidence is ambiguous.

3. **WhatsApp/customer attention**
   - readiness-gated `unanswered_conversations`.
   - No raw message bodies, phone numbers, or auto-reply promises in MVP.

4. **Fiscal/admin readiness lane**
   - ARCA/facturación is not a full MVP integration yet.
   - MVP should include an operator-visible readiness checklist and source/credential status so the product feels like an OS path, not a report-only tool.

5. **Treasury/reporting lane**
   - Start with payment/collection/freshness placeholders and redacted evidence policy.
   - Do not promise accounting automation until the source and reconciliation gates exist.

## Build rule

Use La Pyme's breadth as the buyer-facing category, but build only platform-safe slices:

- connector registry;
- compiled runtime;
- run ledger;
- metric registry/evidence;
- Operational Cases;
- audited actions;
- redacted operator/WhatsApp projections.

If a capability cannot pass those contracts, ship it as:

- readiness checklist;
- setup-required case;
- data-stale case;
- operator-only projection;
- or post-MVP backlog.

Do not bypass the platform to fake ERP breadth.

## Recommended MVP package

### Activation Sprint

For one merchant:

- connect Tiendanube;
- run deterministic daily brief;
- show open cases and run health;
- configure stock/fulfillment thresholds;
- qualify WhatsApp source readiness;
- qualify ARCA/payment source readiness;
- produce a concise OS-style operator screen and WhatsApp projection.

### Owner-facing promise

```text
En una semana te damos el centro operativo de tu tienda: ventas, stock, chats pendientes, fuentes caídas y próximos pasos, con evidencia y seguimiento por WhatsApp.
```

### What must be real for pilot

- At least Tiendanube sales/order truth.
- At least 3 deterministic case families.
- Case queue + run health inspection.
- Redacted degraded-state handling.
- WhatsApp projection from cases.

### What can be readiness-gated

- ARCA/facturación;
- payments/treasury;
- fulfillment backlog;
- unanswered conversations;
- AI assistant over operational data.

Readiness-gated means visible in product as setup/status/next-step, but not owner-facing automated claims until source truth is verified.

## Worker priority changes

Autonomous workers should now prioritize MVP work that makes Orvo feel like a PyME OS without broad rewrites:

1. operator home / OS snapshot;
2. module readiness statuses for sales, stock, WhatsApp, ARCA, treasury;
3. setup-required / data-stale cases;
4. case-backed WhatsApp projection;
5. pilot activation checklist and demo data;
6. only then deeper integrations.

## Not now

- Full accounting ledger.
- Full ARCA invoice issuance.
- Full POS/ecommerce omnichannel sync.
- Auto-answering customers.
- Generic app marketplace.
- LLM-created metrics or lifecycle transitions.

## Success criteria

The MVP is good enough when a merchant can say:

> "Esto es el centro operativo de mi tienda; me dice qué pasó, qué está roto, qué falta conectar y qué hago ahora."

Not when Orvo has feature parity with La Pyme.
