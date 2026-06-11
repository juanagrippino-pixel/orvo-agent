# ARCA + Treasury Readiness Lanes — OS-Style MVP Packaging

Date: 2026-06-11  
Status: Market Research — bounded ICP / competitor / packaging slice  
Prior research checked: `2026-06-11-lapyme-deep-research.md`, `2026-06-11-lapyme-benchmark.md`, `2026-05-24-orvo-competitor-landscape.md`, `2026-05-25-ecommerce-ops-buyer-research-tiendanube.md`, `2026-06-05-fulfillment-backlog-pilot-packaging.md`, `docs/product/2026-06-11-lapyme-category-mvp-scope.md`, `docs/roadmap/d2c-control-plane-roadmap.md`  
Scope note: this cron environment did not expose live web-search tooling, so this run uses the repo's existing web-sourced research corpus and public links already captured in-repo; refresh source pages before quoting externally.

## Bounded question

Should Orvo show ARCA/facturación and Mercado Pago/treasury in the first sellable Tiendanube OS-style MVP, and how should they be packaged without drifting into ERP, accounting, invoice issuance, or reconciliation scope?

## Short answer

Yes — but as **readiness lanes**, not automated finance modules. La Pyme validates that Argentine PyMEs expect an operating-system category to acknowledge ARCA, treasury, Mercado Pago, reports, and accounting-adjacent workflows. Orvo should use that expectation to make the MVP feel like a serious PyME control plane, while staying honest: Tiendanube sales/orders are the first source of operational truth; ARCA and treasury start as setup/readiness status, source-health checks, and next-step guidance.

Recommended buyer-facing phrasing:

> “Orvo no emite facturas ni concilia tu contabilidad en el piloto. Sí te muestra si la tienda está lista para conectar facturación/tesorería, qué fuente falta, y qué señales no podemos afirmar todavía.”

## Evidence base and source links

Public/source links represented in prior corpus:

- La Pyme positions as “el sistema operativo de tu pyme” and publicly bundles sales, stock, ARCA invoicing, purchases, treasury, accounting, reports, Tiendanube, Mercado Pago, API, and AI/MCP assistants: <https://www.lapyme.com.ar/>.
- Tiendanube seller workflow is already fragmented across ventas, productos, medios de pago, envíos/locales, Envío Nube, WhatsApp, and apps: <https://ayuda.tiendanube.com/es_AR/ventas>, <https://ayuda.tiendanube.com/es_AR/medios-de-pago>, <https://ayuda.tiendanube.com/es_AR/envios-y-locales>, <https://www.tiendanube.com/tienda-aplicaciones-nube>.
- Tiendanube app/store categories include fiscal/accounting/ERP-like point tools, e.g. Dux ERP, Contagram, TFactura/Tango Factura, and Facturante, reinforcing that merchants buy specialized admin/fiscal tools around Tiendanube: <https://www.tiendanube.com/tienda-aplicaciones-nube/dux-software-erp>, <https://www.tiendanube.com/tienda-aplicaciones-nube/contagram>, <https://www.tiendanube.com/tienda-aplicaciones-nube/tango-factura>, <https://www.tiendanube.com/tienda-aplicaciones-nube/facturante>.
- Prior competitor research maps ERPs/accounting/fiscal tools as systems of record and warns Orvo should integrate with them rather than replace them (`2026-05-24-orvo-competitor-landscape.md`).
- The accepted La Pyme-category MVP scope explicitly calls for a fiscal/admin readiness lane and a treasury/reporting lane, with no full ARCA invoice issuance or payment reconciliation in MVP (`docs/product/2026-06-11-lapyme-category-mvp-scope.md`).

## Why this slice matters

Without ARCA/treasury visibility, Orvo risks looking like a narrow ecommerce alert bot while La Pyme/Tango-like alternatives look like real operating systems. But if Orvo promises invoice issuance, accounting, taxes, or reconciliation too early, it creates source-of-record, liability, support, and implementation burden that will slow the Tiendanube wedge.

The right MVP move is a **visible but gated lane**:

- visible enough that buyers see a path from ecommerce operations to PyME OS;
- constrained enough that Orvo does not become an ERP clone;
- deterministic enough that every status comes from connector/runtime/case state, not marketing copy;
- useful in sales discovery because it exposes what the merchant already uses for fiscal/admin work.

## ICP refinement

Add an ARCA/treasury-readiness overlay to qualification, but do not make it a hard requirement for the first pilot.

| Signal | Fit impact | Sales action |
|---|---:|---|
| Merchant already asks “qué vendimos, qué cobré, qué falta facturar” daily | +7 | Position OS snapshot, not just WhatsApp report. |
| Uses Tiendanube plus Mercado Pago/bank transfer/manual payment methods | +5 | Add payment-source readiness questions. |
| Has accountant/admin person who chases invoices or reports weekly | +5 | Include them in setup/readiness review; do not sell accounting replacement. |
| Uses Dux, Contagram, Tango/TFactura, Facturante, La Pyme, Alegra, Contabilium, or similar | +4 | Treat as future source connector/system-of-record; Orvo sits above it. |
| Owner manually compares Tiendanube orders vs payments/invoices | +6 | Strong pain, but package as readiness audit first. |
| Buyer wants Orvo to issue invoices or keep books immediately | -6 | Redirect scope: Orvo can monitor readiness now, integrate later. |
| No fiscal/admin workflow owner or accountant contact | -3 | Lane can be informational only. |
| Finance source is offline spreadsheets with no stable export | -4 | Activation Sprint may document gaps; no automated claims. |

## Packaging recommendation

Do not bundle ARCA issuance or payment reconciliation into Starter. Use readiness lanes to raise perceived product seriousness and create expansion paths.

| Package | ARCA/fiscal stance | Treasury/reporting stance | Rationale |
|---|---|---|---|
| Health Check | Ask what tool issues invoices and whether Tiendanube order data matches it | Ask how payments are confirmed and where Mercado Pago/bank records live | Qualifies pain without connecting sensitive finance systems. |
| Activation Sprint — USD 149 / 30 days | Readiness checklist + setup-required lane; no invoice issuance | Payment-source map + freshness/readiness lane; no reconciliation claims | Makes the product feel OS-like while keeping implementation bounded. |
| Starter — USD 79-99/mo | Visible “Fiscal/admin: not connected / setup required / source stale” status | Visible “Treasury/reporting: not connected / setup required / source stale” status | Differentiates from report bot; avoids ERP support burden. |
| Growth — USD 199/mo | Optional connector to existing fiscal/admin source after truth gates | Optional Mercado Pago/payment export connector after truth gates | Expansion based on source evidence, not generic finance automation. |
| Scale/Custom | Multi-source fiscal/payment evidence, accountant/operator views, audit exports | Multi-account payment freshness and exception review | Requires roles, redaction, audit, and customer-specific rules. |

Upsell language:

> “Starter te da control operativo sobre Tiendanube. Growth puede sumar señales fiscales o de cobro cuando tengamos una fuente confiable; si no, Orvo te muestra exactamente qué falta conectar.”

## Readiness truth gates

Before any owner-facing ARCA or treasury claim, require these gates.

### ARCA / fiscal lane gates

1. **Source-of-record gate:** define the current invoice/admin system: ARCA portal, accountant, ERP, fiscal app, La Pyme, Tango/TFactura, Facturante, Contagram, Dux, spreadsheet, or none.
2. **Scope gate:** define whether Orvo is checking readiness, invoice presence, invoice-status freshness, report export freshness, or only setup status.
3. **Identifier gate:** determine whether Tiendanube orders can be safely matched to fiscal/admin records without exposing full customer PII in owner-facing briefs.
4. **Permission gate:** confirm who can connect/read fiscal/admin data and who is allowed to see summaries.
5. **Freshness gate:** if the fiscal source is stale/missing, show setup-required or `data_stale`; do not claim missing invoices.
6. **No-issuance gate:** MVP does not create, cancel, resend, or mutate invoices.
7. **No-tax-advice gate:** Orvo does not interpret tax law, calculate obligations, or tell the merchant what category/tax treatment applies.

### Treasury / payment lane gates

1. **Payment-source gate:** define whether payment truth is Tiendanube payment status, Mercado Pago, bank transfer spreadsheet, ERP, accountant export, or another source.
2. **Settlement semantics gate:** distinguish paid/authorized, refunded, cancelled, chargeback, pending transfer, and payout-settled states before making claims.
3. **Timestamp gate:** ensure order/payment/settlement timestamps exist for aging or mismatch checks.
4. **Tolerance gate:** define acceptable timing differences between order creation, payment approval, payout, manual transfer confirmation, and admin booking.
5. **Redaction gate:** owner-facing WhatsApp summaries must not expose full payment IDs, customer names, bank details, tax IDs, or raw statements.
6. **No-reconciliation gate:** MVP does not book accounting entries, reconcile ledgers, or close cash/bank balances.
7. **Freshness gate:** stale payment sources suppress mismatch claims and create/update `data_stale` or setup-required operator context.

If a gate fails, Orvo should say:

> “Esta parte todavía está en modo preparación: sabemos qué fuente falta o está vieja, pero no podemos afirmar facturación/cobros sin evidencia confiable.”

## Competitor gap to position

| Existing category | What buyer already gets | Gap Orvo should own |
|---|---|---|
| La Pyme / Tango-like PyME OS | Deep admin/fiscal/stock/treasury workflows and source-of-record objects | Orvo can be lighter and case-first: operating queue, evidence, follow-up, readiness, and WhatsApp/app projection. |
| Tiendanube fiscal/accounting apps | Invoice/accounting-specific execution | They solve the admin job; Orvo coordinates when admin/fiscal readiness affects daily operations. |
| ERP/accounting tools | Invoices, ledgers, purchases, inventory, reports | They are systems of record, not a cross-tool operational case queue for owner/operator attention. |
| Mercado Pago / payment dashboards | Payment and settlement views | Pull-based finance views; Orvo should show readiness/freshness and later exception cases when safe. |
| Manual accountant/admin workflow | Human review and compliance judgment | No daily operational status, no cross-source evidence, no follow-up memory inside ecommerce operations. |

Positioning line:

> “Tu sistema fiscal o contable registra. Orvo te muestra si esa parte de la operación está conectada, fresca y lista para usarse como evidencia operativa.”

## Sales discovery questions

Use these in Activation Sprint discovery before promising any fiscal/treasury automation:

1. “¿Dónde se emiten hoy las facturas: ARCA, contador, Tango/La Pyme/Dux/Facturante/Contagram, o manual?”
2. “¿Quién revisa si los pedidos de Tiendanube quedaron facturados o pendientes?”
3. “¿Qué medios de pago usan y cuál consideran fuente de verdad para cobros?”
4. “¿Mercado Pago/banco/transferencias se revisan todos los días o al cierre semanal/mensual?”
5. “¿Qué diferencia de tiempo es normal entre pedido, pago aprobado, despacho, factura y cobro disponible?”
6. “¿Qué datos fiscales o de clientes no deberían aparecer nunca en un brief interno de WhatsApp?”
7. “¿El objetivo ahora es emitir/conciliar, o primero tener visibilidad de qué fuente falta y qué está atrasado?”

## Product and governance guardrails

- ARCA and treasury lanes should be product-visible as module readiness/status, not fabricated operational claims.
- Do not add owner-facing case families like `missing_invoice` or `payment_reconciliation_gap` until metric registry entries, source contracts, evidence refs, redaction, and suppression tests exist.
- Use `data_stale` or setup-required context when finance/admin sources are absent, stale, or ambiguous.
- Do not issue invoices, mutate fiscal records, move money, refund customers, book accounting entries, or reconcile ledgers in MVP.
- Do not let WhatsApp become the control surface for finance actions; use the app/operator console for inspection and permissions.
- Treat accountant/admin users as stakeholders, not as workflows Orvo replaces.

## Bottom line

ARCA and treasury should appear in the MVP because they make Orvo feel like the first slice of a real Argentine PyME operating system. They should start as **readiness lanes**: source map, setup-required status, freshness, redacted evidence policy, and next-step guidance. This creates a credible expansion path against La Pyme/Tango-like competitors without compromising the Tiendanube-first control-plane wedge or drifting into ERP/accounting obligations too early.
