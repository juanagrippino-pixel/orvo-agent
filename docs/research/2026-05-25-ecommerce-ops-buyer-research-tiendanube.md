# Ecommerce ops buyer research — Tiendanube-first operations control plane

Date: 2026-05-25  
Owner: Product & Market Intelligence  
Scope: Buyer research synthesis for Orvo's Tiendanube + WhatsApp-first D2C operations control plane.  
Related: `docs/product/tiendanube-exception-desk-opportunity-spec.md`, `docs/research/2026-05-24-tiendanube-latam-d2c-buyer-pain-icp.md`, `docs/research/2026-05-24-orvo-competitor-landscape.md`, `docs/product/d2c-control-plane-prd.md`, `docs/specs/d2c-case-family-catalog.md`.

> Research note: this environment did not expose live web-search tooling, so this synthesis relies on repo-grounded prior research plus public URLs already captured in repo docs. Treat numeric/public-market claims as cited hypotheses to refresh before publishing externally.

## Executive answer

The highest-probability buyer is the **owner/operator or ecommerce lead of a physical-goods Tiendanube store in Argentina/LatAm whose daily operations happen across Tiendanube, WhatsApp, spreadsheets, shipping/payment apps, agencies, and manual checks**. They do not primarily need another report, chatbot, dashboard, or ERP. They need a **small operating desk** that says what needs action today, why Orvo believes it, what evidence supports it, who is following up, and what is stale/unsafe.

The first sellable wedge should be framed as:

> **Orvo Tiendanube Exception Desk**: Orvo watches Tiendanube and sends a WhatsApp/operator case queue for stock risk and stale/unsafe data. Sales-drop is included only when a safe configured floor/baseline exists. Pending-order/fulfillment cases stay internal or operator-assisted until real Tiendanube payment/fulfillment fields are verified for that store.

This is more buyer-concrete than “control plane,” but preserves the internal Atlassian-like primitives: connector registry, runtime, run ledger, metric registry, Operational Cases, lifecycle, evidence, audit, and operator projections.

## Evidence base and market signals

| Signal | Buyer implication | Evidence / URL |
| --- | --- | --- |
| Argentine ecommerce has material order volume and is now a structural consumption channel. | There is a large enough universe where daily exceptions matter. Prior repo research cites CACE 2025: ARS 34.033.238M, 253M orders, 645M units, ARS 134,519 average ticket. | CACE stats: https://cace.org.ar/estadisticas/ ; CACE 2025 study: https://cace.org.ar/blogs/news/estudio-anual-de-cace-2025-el-ecommerce-como-canal-estructural-del-consumo-argentino |
| Tiendanube sellers are educated around stock, products, orders, payments, shipping, WhatsApp, apps, and operational setup as separate topics. | Seller workflow is fragmented by domain; Orvo can coordinate exceptions above the tools. | Tiendanube help: https://ayuda.tiendanube.com/es_AR/ventas , https://ayuda.tiendanube.com/es_AR/productos , https://ayuda.tiendanube.com/es_AR/medios-de-pago , https://ayuda.tiendanube.com/es_AR/envios-y-locales , Envio Nube docs: https://ayuda.tiendanube.com/es_AR/envio-nube-gestion-de-envios , https://ayuda.tiendanube.com/es_AR/envio-nube-seguimiento , https://ayuda.tiendanube.com/es_AR/envio-nube-incidencias |
| Stock is a recurring Tiendanube seller education theme. | `stockout_risk` is a strong first case family for physical-goods stores. | https://www.tiendanube.com/blog/como-funciona-el-stock-en-el-ecommerce/ ; https://www.tiendanube.com/blog/sistema-de-control-de-stock/ |
| WhatsApp is an operating/sales surface in LatAm. Prior repo research cites Tiendanube/NubeCommerce data that 71.5% of Argentine entrepreneurs used WhatsApp as a sales channel in 2025. | WhatsApp is the right first projection/habit loop, but not the source of truth. | https://site.tiendanube.com/recursos/nubecommerce ; Tiendanube WhatsApp selling: https://www.tiendanube.com/blog/como-vender-por-whatsapp/ ; WhatsApp Business: https://www.tiendanube.com/blog/whatsapp-business/ |
| Tiendanube app ecosystem covers point jobs: ERP, shipping, invoice/accounting, marketplace sync, WhatsApp/chat, reviews, alerts. | Buyers already accept app-based solutions, but suffer app sprawl; Orvo should coordinate across apps, not replace them. | App store: https://www.tiendanube.com/tienda-aplicaciones-nube ; Gestión: https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/gestion ; Envíos: https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/envios ; examples: Dux ERP, Envia, Producteca, BaseLinker, Alerti, Revie in `docs/research/2026-05-24-orvo-competitor-landscape.md` |
| Mature alternatives map to dashboards, helpdesks, ERPs, and iPaaS, not Tiendanube-first operational case management. | Orvo’s differentiation is deterministic cases + evidence + lifecycle + degraded-data honesty. | Competitor/source map: `docs/research/2026-05-24-orvo-competitor-landscape.md` |

## ICP refinement

### Primary ICP

**Business:** Argentine/LatAm physical-goods D2C brand/store where Tiendanube is the main storefront or a major operational source of truth.

**Buyer / champion:**

1. Founder/owner who still checks store health personally.
2. Ecommerce manager or operations lead accountable for daily sales, stock, dispatch, and customer escalation.
3. Small-team operator who coordinates agencies, fulfillment, support, or inventory owners through WhatsApp.

**Operating reality:**

- Daily work starts with “¿qué necesita atención hoy?”
- Tiendanube data is checked alongside WhatsApp, spreadsheets, Meta/agency updates, shipping/payment apps, and sometimes MercadoLibre/ERP-lite tools.
- Follow-up is informal: screenshots, WhatsApp messages, memory, and ad hoc tasks.
- There is at least one accountable human who can resolve cases.

**Minimum fit thresholds for pilot:**

- Physical goods with real stock/fulfillment consequences.
- Tiendanube products/orders/stock/statuses are maintained accurately enough to support deterministic detection, or buyer agrees to fix data hygiene as part of pilot.
- Roughly **100+ monthly orders or 50+ active SKUs** for strong urgency; **500 orders / 300 SKUs** remains a Starter/Growth packaging boundary, not a strict ICP minimum.
- Store has had at least one of these in the last 30-60 days: stockout/oversell, paid orders stuck, owner asking for status screenshots, stale spreadsheet/report, ad spend with weak orders, or support/WISMO escalation.

### Best early segments, ranked

1. **Apparel/accessories/cosmetics/home goods D2C with many SKUs/variants.** High stockout/oversell risk, promotions, seasonal drops, and WhatsApp queries.
2. **Owner-led growth store with agency/ad spend but weak ops instrumentation.** Strong pain around “we spent / did orders happen?” but ads cases should follow Tiendanube-only trust.
3. **Store with manual fulfillment/shipping handoff.** `fulfillment_backlog` is urgent, but only sell it after Tiendanube order/payment/fulfillment/status data passes a field audit.
4. **Multi-channel seller where Tiendanube remains the D2C hub.** Attractive later; first pilot should avoid marketplace/channel-mix sprawl unless Tiendanube is still the clean source.

### Poor fit / disqualifiers

- Very low-volume hobby store where missed exceptions do not cost enough.
- Pure digital products, services, or infoproducts with little stock/fulfillment pain.
- Buyer wants only prettier BI, generic AI chat, or guaranteed revenue lift.
- Tiendanube is not maintained and no reliable alternate source exists.
- No one owns follow-up; alerts would become noise.
- Buyer expects immediate autonomous changes to ads, stock, refunds, prices, or customer messages.
- Enterprise with mature OMS/WMS/BI/incident tooling unless scoped as a custom integration later.

## Top buyer pains / opportunities, ranked

Scoring: 5 = strongest. Fit means suitability for Orvo’s first Tiendanube + WhatsApp product; urgency means buyer pain/WTP; engineering readiness means how close it is to deterministic, evidence-backed implementation.

| Rank | Pain / opportunity | Buyer-language promise | Fit | Urgency | Eng readiness | Recommendation |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | **Manual morning reconciliation / owner attention tax** | “Cada mañana sabés qué necesita atención y por qué.” | 5 | 5 | 4 | Package-level promise. Implement as daily case queue + brief, not one case type. |
| 2 | **Stockout / oversell risk on moving products** | “No te quedes sin stock en productos que se están vendiendo.” | 5 | 5 | 4 | First flagship case: `stockout_risk`. Require stock freshness + recent velocity/important SKU. |
| 3 | **Paid orders aging before fulfillment** | “Revisá pedidos pendientes cuando los estados de pago/despacho estén verificados.” | 5 | 4 | 3 | Conditional/internal. Promote only after Tiendanube order/payment/fulfillment fields are reliable and owner-facing projection gates exclude unverified cases. |
| 4 | **Data stale / unsafe advice trust gap** | “Si una fuente no está confiable, Orvo te lo dice y no inventa.” | 5 | 4 | 5 | First-wave trust moat: `data_stale`. Must suppress/narrow downstream cases. |
| 5 | **Sales/order drop without clear next action** | “Ventas por debajo del piso configurado; revisá tienda/pagos/tráfico.” | 4 | 4 | 3 | Keep conservative. Do not make it flagship unless thresholds/baseline are configured and freshness is safe. |
| 6 | **Ad spend but weak Tiendanube orders** | “Se está gastando y no entran pedidos.” | 4 | 5 | 2 | High WTP Growth expansion after Meta Ads + Tiendanube parity. Avoid attribution war. |
| 7 | **Unanswered WhatsApp/support conversations** | “Chats de venta/soporte esperando demasiado.” | 3 | 4 | 1 | Valuable later, but connector/privacy/provider complexity makes it risky for first Tiendanube-only wedge. |
| 8 | **App/tool sprawl and forgotten follow-up** | “No pierdas el estado de lo que quedó abierto.” | 5 | 3 | 4 | Build as case lifecycle/timeline, not generic task manager. |
| 9 | **Channel mix / MercadoLibre vs Tiendanube changes** | “Cambió dónde se están vendiendo los productos.” | 3 | 3 | 1 | Later multi-channel connector expansion; not first pilot. |

## Urgency and fit signals for sales/discovery

### High-urgency trigger questions

Ask during pilot qualification:

1. “¿Quién mira Tiendanube todos los días y cuánto tarda?”
2. “En los últimos 30 días, ¿se quedaron sin stock o sobrevendieron un producto que se estaba moviendo?”
3. “¿Cuántos pedidos pagos suelen quedar pendientes de despacho al final del día?”
4. “¿Cuál es la edad máxima aceptable de un pedido pago sin despacho?”
5. “¿Cuándo te enterás de que un día viene mal de ventas: a la mañana, a la tarde o al cierre?”
6. “¿Dónde se coordina el seguimiento: WhatsApp, planilla, agencia, sistema de envíos?”
7. “¿Qué dashboards/reportes mirás y cuáles terminás ignorando?”
8. “¿Qué pasa cuando Tiendanube, una planilla o un reporte está desactualizado?”
9. “¿Qué caso detectado por Orvo pagaría el piloto por sí solo?”
10. “¿Qué tendría que pasar en 14 días para cancelar?”

### Strong fit signals

- Owner asks for daily screenshots/status from team or agency.
- Same person manages stock, orders, fulfillment, WhatsApp, and ads with no formal workflow.
- Store has many variants/SKUs and runs promotions.
- Team has suffered stockouts, oversells, stale stock, or paid orders stuck.
- Buyer says “me entero tarde” or “dependo de que alguien se acuerde.”
- Buyer accepts evidence-backed thresholds instead of “AI magic.”
- Buyer wants WhatsApp notification but also asks for history/status.
- They already pay for Tiendanube apps/agencies/ERP-lite/shipping tools.

### Weak fit / churn signals

- Buyer only asks for a dashboard or weekly report PDF.
- No operational owner for resolving cases.
- Stock/order statuses are knowingly inaccurate and buyer will not improve them.
- They demand attribution/ROAS truth before basic source freshness is solved.
- They expect Orvo to handle customer replies, refunds, stock mutations, or ad changes autonomously in pilot.
- They view USD 79-149 as too high because they compare Orvo to a simple alert/report app; likely category mismatch.

## Buyer objections and recommended replies

| Objection | What it means | Reply / positioning |
| --- | --- | --- |
| “Ya tengo dashboards en Tiendanube/Meta/GA.” | They fear another analytics login. | “Perfecto. Orvo no reemplaza dashboards: abre casos operativos con evidencia, prioriza qué atender hoy y guarda seguimiento hasta resolver.” |
| “Esto lo puedo mirar yo.” | They underestimate attention cost. | “Sí, Orvo reemplaza el chequeo manual repetitivo y evita que se escape el caso que importa cuando estás operando.” |
| “¿Es un bot de WhatsApp?” | They may anchor to chatbot/CRM. | “No. WhatsApp es la superficie. El producto es la cola operativa: conectores, evidencia, casos, historial y seguimiento.” |
| “Tenemos ERP/sistema de stock.” | They fear replacement/disruption. | “Mejor. El ERP puede seguir como fuente; Orvo detecta excepciones y coordina seguimiento arriba del ERP/Tiendanube.” |
| “Ya usamos Zapier/Make.” | They have automation literacy. | “Zapier ejecuta reglas que vos definís. Orvo decide qué condición ecommerce merece un caso, deduplica, verifica frescura y audita seguimiento.” |
| “Quiero que pause campañas/cambie stock automáticamente.” | They want automation before governance. | “En piloto Orvo recomienda y registra aprobación. Acciones externas automáticas vienen después de permisos, auditoría e idempotencia.” |
| “Quiero ROI garantizado.” | Risky expectation. | “No prometemos revenue lift. Medimos casos detectados, chequeos manuales reemplazados, datos stale evitados y seguimiento cerrado.” |
| “Nuestra data está desordenada.” | Potentially either pain or blocker. | “Orvo puede abrir `data_stale`, pero no inventa. Si stock/pedidos no son confiables y no hay fuente alternativa, el piloto debe empezar por higiene de datos.” |

## Pilot discovery insights and design

### Best pilot thesis

A paid 30-day pilot should test whether a Tiendanube-first operator will pay for **daily exception monitoring + follow-up memory**, not whether they like AI summaries.

**Pilot promise:**

> “Durante 30 días Orvo monitorea tu Tiendanube y te manda por WhatsApp una cola diaria de excepciones: stock en riesgo y datos no confiables. Los pedidos pendientes/pagos trabados se incluyen solo si validamos que los campos de pago, despacho y antigüedad son confiables para tu tienda. Cada caso tiene evidencia, estado y seguimiento.”

### Pilot package recommendation

- **Name:** Piloto Tiendanube + WhatsApp.
- **Price hypothesis:** USD 149 / 30 days or ARS equivalent at invoice time; creditable if converting.
- **Scope:** 1 Tiendanube store, 1 WhatsApp destination/group, daily scheduled brief, internal/operator-assisted case queue, weekly async review.
- **Case families:**
  1. `stockout_risk` — launch flagship.
  2. `data_stale` — launch trust moat.
  3. `fulfillment_backlog` — conditional/internal-only until Tiendanube fields are verified and the owner-facing brief allowlist marks the case ready.
  4. `sales_drop` — optional only with configured floor/safe baseline.
- **Limits:** no custom connectors, no Meta Ads, no MercadoLibre, no WhatsApp conversation ingestion, no autonomous external actions, no guaranteed revenue lift.

### Pilot success metrics

Convert or continue when at least 2-3 of these happen:

- Owner/operator reads/responds to briefs at least 3 times/week.
- Orvo opens/updates at least 3 cases the buyer agrees were worth knowing.
- At least one case replaces a manual check or prevents a missed follow-up.
- At least one `data_stale`/degraded state prevents false confidence.
- Buyer asks for comments, assignment, multiple recipients, fulfillment depth, or Meta Ads spend/order mismatch.
- Buyer can name one incident where Orvo would have paid for itself.

Kill or reposition when:

- Most days produce no actionable cases and buyer does not miss the brief.
- Data freshness problems dominate and buyer will not fix source data.
- Buyer keeps asking for dashboards/exports instead of cases/actions.
- Manual concierge work exceeds the pilot fee with no path to productization.

## What not to build now

1. **Generic chatbot / “ask your store anything.”** It breaks the deterministic/evidence trust promise.
2. **Dashboard-first UI.** Internal inspection is needed, but buyer value is cases + follow-up, not charts.
3. **Full ERP/accounting/warehouse/payment reconciliation.** Integrate later; do not own fiscal/source-of-record workflows.
4. **Full WhatsApp inbox/helpdesk.** WhatsApp is a projection/habit loop; `unanswered_conversations` can become a case later.
5. **ROAS/attribution suite.** `spend_without_orders` is a simple operational mismatch case after source freshness parity, not attribution truth.
6. **Broad iPaaS/Zapier competitor.** Build registered case actions with approvals/audit, not generic automation plumbing.
7. **Marketplace/channel suite before Tiendanube proof.** MercadoLibre/channel-mix is attractive expansion, but first wedge must be trustworthy.
8. **Autonomous external actions in pilot.** No ad pauses, stock edits, refunds, cancellations, customer promises, or price changes without explicit governance.
9. **LLM-created metrics, detections, priorities, or lifecycle transitions.** LLMs can help explain; the case engine must decide deterministically.
10. **Public developer marketplace/SDK.** Premature until the internal connector/case contracts are stable.

## Engineering-ready implications

### Product architecture guardrails

- The durable object is `OperationalCase`, not alert text, report paragraphs, WhatsApp messages, or dashboard rows.
- WhatsApp is a projection of case state; never the state store.
- Every owner-facing number requires metric/evidence refs and source freshness.
- Missing/stale Tiendanube data must open/update `data_stale` and suppress/narrow downstream advice.
- Case dedupe must update the same issue across days instead of re-alerting as new.
- All actions must use registered action keys; no LLM-invented action names or side effects.

### First case implementation requirements

#### `stockout_risk`

**Detection:** open/update when stock <= configured threshold and recent units sold > 0 or SKU is marked important, with fresh Tiendanube inventory data.

**Suppress:** stale inventory, non-moving SKU without strategic flag, missing SKU/product identity.

**Evidence schema:** product/SKU id, product name, current stock, threshold, recent units sold/window, optional active promotion flag, source freshness, latest run ID.

**Dedupe key:** `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.

**Implemented operator actions today:** `acknowledge_case`, `resolve_case`. **Operator-assisted recommendations/catalog keys, not implemented handlers yet:** `confirm_stock`, `pause_promotion`, `add_comment`. `mark_in_progress` and `dismiss_case` are Growth/workflow roadmap until lifecycle states exist in code.

#### `fulfillment_backlog`

**Detection:** open/update when paid/unfulfilled order count >= threshold or oldest paid/unfulfilled age >= SLA, with fresh/clear order + fulfillment fields.

**Suppress:** ambiguous payment/fulfillment statuses, stale order data, missing timestamps.

**Evidence schema:** paid/unfulfilled count, oldest age, status grouping, safe/redacted sample order refs, source freshness, latest run ID.

**Dedupe key:** `<business_id>/fulfillment_backlog/channel/tiendanube/commerce.fulfillment/daily`.

**Implemented operator actions today:** `acknowledge_case`, `resolve_case`. **Operator-assisted recommendations/catalog keys, not implemented handlers yet:** `inspect_pending_orders`, `assign_owner`, `add_comment`. `mark_in_progress` and `dismiss_case` are Growth/workflow roadmap until lifecycle states exist in code.

#### `data_stale`

**Detection:** open/update when Tiendanube connector is unauthorized, rate-limited, malformed, missing required fields, or last successful run exceeds freshness policy.

**Effect:** downstream case families list `suppressed_by_data_stale` or equivalent, and WhatsApp copy says what Orvo did not use.

**Evidence schema:** connector type/id, failure class, stale duration, last success, affected case families, run ID.

**Dedupe key:** `<business_id>/data_stale/connector/tiendanube/runtime.freshness/daily`.

**Implemented operator actions today:** `acknowledge_case`, `resolve_case` after successful fresh run. **Operator-assisted recommendations/catalog keys, not implemented handlers yet:** `refresh_credentials`, `retry_connector`, `add_comment`.

#### Conservative `sales_drop`

**Detection:** open/update only when current orders/revenue fall below an explicit configured floor or trustworthy baseline with sufficient historical data and fresh source.

**Suppress/downgrade:** insufficient baseline, low-volume noise, stale commerce source, ambiguous current-day partial data.

**Buyer copy:** say “ventas/pedidos por debajo del piso configurado,” not “AI detected cause.”

### Config fields to capture during onboarding

- Business/store timezone and daily check windows.
- WhatsApp recipient/group and escalation contact.
- Stock threshold default and important SKU list.
- Fulfillment SLA: oldest acceptable paid/unfulfilled order age; count threshold.
- Sales floor: minimum orders/revenue by day or time window, only if buyer can set it.
- Freshness policy: max Tiendanube data age, retry behavior, degraded copy.
- Entities to exclude: made-to-order products, preorder SKUs, discontinued products, internal/test orders.
- Case resolution semantics: what counts as resolved for stock and stuck-order cases.

### Internal surface / API requirements

- Case queue filters: open, new today, high priority, stale/degraded, case family, entity scope.
- Case timeline: opened/updated, evidence snapshot, status transition, comments, action request/completion, run refs.
- Run history: runtime/config hash, connector status, errors/degraded state, cases opened/updated/suppressed, dispatch attempts, redaction status.
- Pilot review export: weekly counts of opened/updated/resolved cases, stale-data incidents, and manual follow-ups.

### Tests / invariants

- Deterministic open/update/suppress tests per case family.
- Dedupe tests across preview/forced/scheduled runs for same input.
- Evidence-required test for every owner-facing case field.
- `data_stale` suppresses `stockout_risk`, `fulfillment_backlog`, and `sales_drop` when required source is unsafe.
- Redaction tests for tokens, OAuth values, URLs, order/customer refs where sensitive.
- WhatsApp projection tests verify no unsupported metrics, no hidden state mutation, and degraded-data language.

## Recommended next decisions

1. **Promote `fulfillment_backlog` into first-wave pilot only if Tiendanube adapter exposes reliable payment/fulfillment status + timestamps and owner-facing projection gates exclude unverified cases.** If not, keep it internal/concierge until verified.
2. **Lead sales with stock + stale data + verified pending-order review, not sales anomaly.** Use `sales_drop` as conservative configured-floor detection.
3. **Treat paid pilot as discovery of workflow behavior.** The core question is whether the buyer values durable case follow-up enough to pay and keep using it.
4. **Keep Meta Ads and WhatsApp conversation ingestion as expansion triggers.** They are high-value but would overcomplicate the first Tiendanube-only proof.
5. **Instrument onboarding/support cost.** If pilots require too much manual cleanup, add explicit data-readiness criteria or setup fee.
