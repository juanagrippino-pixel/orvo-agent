# Orvo OS Activation Sprint Offer — Paid Pilot Repositioning

Status: GTM execution asset  
Date: 2026-06-11  
Owner: Codex GTM / Pricing / Packaging  
Scope: Reposition the first paid pilot from a narrow Tiendanube exception brief into an OS-style Activation Sprint for one Argentine/LatAm D2C merchant, without promising ERP, ARCA issuance, reconciliation, or autonomous actions.

## Purpose

Recent product direction raises the commercial bar: Orvo should sell as the first slice of an Argentine PyME operating control plane, not as a WhatsApp report bot. This document turns the existing USD 149 / 30-day paid pilot into a tighter **OS Activation Sprint** offer that still preserves the deterministic Tiendanube wedge.

The offer should make the buyer feel:

> “Esto es el centro operativo de mi tienda: me dice qué pasó, qué está roto, qué falta conectar y qué hago ahora.”

It must not imply that Orvo already replaces Tiendanube, La Pyme/Tango, fiscal/accounting tools, shipping tools, agencies, or human operators.

## Sources used

Repo/product sources:

- `docs/organization/2026-05-30-codex-24-7-autonomous-operating-system.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/product/2026-06-11-lapyme-category-mvp-scope.md`
- `docs/gtm/d2c-packaging-and-messaging.md`
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`
- `docs/gtm/2026-06-01-paid-pilot-close-kit.md`
- `docs/gtm/2026-06-02-paid-pilot-onboarding-checklist.md`
- `docs/gtm/2026-06-05-first-10-paid-pilot-lead-build-packet.md`
- `docs/research/2026-05-30-icp-scoring-framework.md`
- `docs/research/2026-05-30-pricing-intelligence.md`
- `docs/research/2026-05-30-buyer-journey-objection-playbook.md`
- `docs/research/2026-06-11-arca-treasury-readiness-lanes.md`

Assumptions and limits:

- No live web search/browser tool was available in this cron environment; no new external pricing claims are introduced.
- Any exact competitor/Tiendanube pricing should be refreshed before public marketing use.
- The USD 149 / 30-day pilot price remains the current sellable hypothesis.
- Orvo’s source of truth remains Operational Cases, evidence, run ledger, metric registry, and operator surfaces. WhatsApp is a projection channel.
- ARCA/fiscal and treasury/payment features are readiness lanes only until source, freshness, identifier, permission, redaction, and no-issuance/no-reconciliation gates exist.

## 1. Recommended offer name and positioning

### Replace the narrow pilot headline

Old working headline:

> Piloto Exception Desk Tiendanube + WhatsApp — USD 149 / 30 días

Recommended external headline:

> **Orvo OS Activation Sprint — Centro operativo para tu Tiendanube en 30 días**

Short Spanish pitch:

```text
En 30 días armamos el centro operativo de una tienda Tiendanube: ventas, stock,
datos stale, próximos pasos y módulos que faltan conectar, con casos y evidencia.
WhatsApp te avisa; la cola de casos y el historial quedan en Orvo.
```

Plain-English internal meaning:

- Keep Tiendanube as the first source of operational truth.
- Show an app/operator-console-first control plane, even if early.
- Use WhatsApp as the owner’s daily alert surface.
- Add visible readiness lanes for fiscal/admin, treasury/reporting, customer attention, and fulfillment without making unsafe claims.

### Category anchor

Use:

> “control operativo para PyMEs ecommerce”

Avoid:

- “chatbot de WhatsApp”;
- “dashboard de Tiendanube”;
- “agente que automatiza todo”;
- “ERP/facturación/contabilidad”;
- “BI con IA”.

## 2. One-page buyer-facing offer

```text
Orvo OS Activation Sprint — USD 149 / 30 días

Para una tienda Tiendanube, Orvo arma un centro operativo inicial: qué necesita
atención hoy, por qué, con qué evidencia, qué queda abierto y qué fuente todavía
falta conectar.

Incluye:
- 1 tienda Tiendanube como control plane operativo.
- Setup asistido de Tiendanube y umbrales.
- Vista/cola operativa de casos: abiertos, reconocidos, resueltos y datos stale.
- 1 brief diario por WhatsApp para el dueño/equipo operativo.
- Casos con evidencia para datos stale/no confiables y stock en riesgo cuando el dato esté fresco.
- Ventas bajo piso configurado cuando exista baseline o piso acordado.
- Revisión de preparación para módulos: fulfillment, atención al cliente, ARCA/fiscal y tesorería/cobros.
- Revisión semanal de casos, ruido, umbrales y próximos pasos.

No incluye:
- Emisión de facturas, interpretación fiscal, conciliación contable o movimiento de dinero.
- Acciones automáticas sobre Tiendanube, stock, pedidos, campañas, cobros o clientes.
- WhatsApp inbox/chatbot para clientes.
- Meta Ads, MercadoLibre, ERP, warehouse, fiscal apps o conectores custom salvo acuerdo explícito.
- Garantía de aumento de ventas.

Criterio de éxito:
- Orvo abre o actualiza casos útiles con evidencia, o demuestra honestamente qué dato/fuente no es confiable.
- El brief reduce chequeos manuales o evita que seguimientos abiertos se pierdan.
- Al día 25-28 decidimos si seguir como Starter, Growth, Custom, limpieza de datos o stop.
```

## 3. Activation Sprint deliverables

Use this as the internal delivery checklist promised in sales. Do not promise a deliverable unless the implementation/runtime can support it or the item is explicitly a readiness assessment.

| Deliverable | Buyer-visible promise | Source-of-truth guardrail |
|---|---|---|
| OS snapshot | “Una vista de qué está fresco, qué está abierto y qué falta conectar.” | Must project from run health, cases, connector/source state, or explicit setup checklist. |
| Tiendanube data-health audit | “Sabemos si stock/pedidos/ventas sirven para abrir casos.” | If data is stale or ambiguous, create/note `data_stale` or setup-required state; do not invent certainty. |
| Daily case brief | “Un WhatsApp breve con lo que necesita atención.” | Derived from canonical cases/evidence; WhatsApp never owns lifecycle state. |
| Stock risk setup | “Monitoreamos productos/SKUs mapeados cuando el stock es confiable.” | Enable only for mapped fresh stock evidence. |
| Sales floor setup | “Si no se cumple el piso acordado, Orvo lo marca.” | Use configured floor/baseline only; do not claim root cause. |
| Fulfillment readiness | “Vemos si los estados de pago/envío permiten mirar pedidos trabados.” | Owner-facing backlog only after payment/shipping/timestamp/SLA gates pass. |
| Customer attention readiness | “Definimos si hay fuente confiable para chats pendientes.” | No raw message bodies/phone numbers or chatbot promises in MVP. |
| ARCA/fiscal readiness | “Mapeamos dónde se factura y qué falta conectar.” | No invoice issuance, tax advice, or missing-invoice claims. |
| Treasury/reporting readiness | “Mapeamos cómo se confirma cobro y qué fuente falta.” | No reconciliation, payout certainty, or bank/payment detail exposure. |
| Weekly value note | “Mostramos casos, ajustes y aprendizaje.” | Quantify only evidence-backed cases and manual-check inputs provided by merchant. |

## 4. Discovery script additions for the OS repositioning

Keep the existing five qualification questions from the close kit. Add this OS block only after basic Tiendanube fit and a named pain are confirmed.

### Opening category line

```text
La idea no es sumarte otro dashboard. La idea es que Orvo sea la cola operativa
de la tienda: ventas, stock, datos caídos, qué falta conectar y qué queda abierto.
WhatsApp es el aviso; el historial queda en Orvo.
```

### OS-readiness questions

| Question | What it qualifies | Commercial use |
|---|---|---|
| “Además de Tiendanube, ¿qué mirás cada mañana para saber si el negocio está bien?” | Breadth of manual-check tax. | If they mention payments, invoices, WhatsApp, shipping, ads, use OS framing. |
| “¿Quién mira si lo vendido se cobró/facturó o queda pendiente?” | Fiscal/treasury stakeholder. | Add accountant/admin/ops recipient to readiness review, not to daily alert by default. |
| “¿Qué fuente te da más miedo que esté vieja o mal: stock, pedidos, cobros, factura, envíos o chats?” | First trust wedge. | Demo `data_stale` honesty as a value, not a limitation. |
| “Si Orvo te muestra ‘esto todavía no puedo afirmarlo porque falta conectar fuente’, ¿eso te sirve o solo querés alertas perfectas?” | Buyer maturity. | Good buyers value readiness/status; bad buyers want fabricated certainty. |
| “¿Querés resolver ahora emitir/conciliar, o primero tener visibilidad diaria de qué está abierto y qué fuente falta?” | ERP-scope risk. | If they require issuance/reconciliation, route to nurture/custom later. |

### Revised close line

```text
Si lo que necesitás es facturar o conciliar, Orvo todavía no es ese sistema.
Si necesitás un centro operativo que te diga qué pasó, qué está abierto, qué dato
no es confiable y qué hacer primero cada mañana, el Sprint de USD 149 sí encaja.
```

## 5. Demo narrative for paid pilot calls

Use this sequence for a 12-15 minute sales demo. The goal is to show seriousness without over-explaining architecture.

1. **Start with the morning chaos.**
   - “Hoy mirás Tiendanube, WhatsApp, envíos, pagos y quizás planillas. Orvo convierte eso en una cola.”
2. **Show the OS snapshot.**
   - Sales/orders: fresh or stale.
   - Stock/fulfillment: active cases or setup-required.
   - Customer attention: setup-required unless source exists.
   - Fiscal/admin: readiness lane.
   - Treasury/reporting: readiness lane.
3. **Open one real-style case.**
   - Title, why it matters, evidence, suggested human action, current state.
4. **Show degraded honesty.**
   - “Acá Orvo no afirma ventas/stock porque la fuente está stale.”
5. **Show WhatsApp projection.**
   - Keep it short; it is the alert, not the product.
6. **Show follow-up memory.**
   - Acknowledge/resolve/comment where implemented; otherwise explain planned lifecycle honestly.
7. **Close with the Activation Sprint.**
   - “En 30 días vemos si esto reemplaza chequeos manuales y qué módulos están listos para Starter/Growth.”

Do not demo fictional autonomous actions, invoice issuance, reconciliation, customer auto-replies, or connectors that are not implemented/verified.

## 6. Objection handling updates

### “Entonces, ¿esto compite con La Pyme / Tango / mi ERP?”

```text
No. Esos sistemas registran o ejecutan: factura, stock, compras, contabilidad.
Orvo está arriba como control operativo: qué necesita atención, qué fuente está
fresca, qué caso queda abierto y quién tiene que actuar. Si tu ERP/fiscal app es
la fuente correcta, Orvo debería integrarse o marcar su estado, no reemplazarla.
```

### “¿Puede emitir facturas o decirme qué falta facturar?”

```text
En el Sprint no emitimos facturas ni damos asesoramiento fiscal. Primero mapeamos
la fuente: ARCA, contador, Tango/La Pyme/Dux/Facturante/Contagram u otra. Si más
adelante hay una fuente confiable y permisos claros, puede convertirse en caso.
Hasta entonces, Orvo muestra preparación/fuente faltante, no inventa faltantes.
```

### “¿Puede conciliar Mercado Pago o banco?”

```text
No en el primer Sprint. Sí podemos mapear qué fuente usan para cobros, qué estados
son confiables y qué sería necesario para monitorear excepciones después. El MVP
no mueve dinero, no reconcilia libros y no expone datos sensibles en WhatsApp.
```

### “Solo quiero que me mande un WhatsApp, no otra app.”

```text
El WhatsApp te sirve para enterarte rápido, pero si todo vive en un mensaje se
pierde historial, estado y responsabilidad. Orvo guarda la cola de casos y el
seguimiento; WhatsApp es el resumen accionable.
```

### “¿Por qué pagar USD 149 si todavía hay cosas en preparación?”

```text
Porque parte del valor es saber con evidencia qué se puede afirmar y qué no.
El Sprint no vende una promesa perfecta: valida Tiendanube, abre los primeros
casos útiles y te deja un mapa claro de qué fuentes faltan conectar para crecer.
Si no aparece un caso útil ni un hallazgo de datos que te sirva, no seguimos.
```

## 7. Pricing and packaging implication

Keep the current ladder, but change the buyer-facing names toward OS/control-plane language.

| Tier | Existing hypothesis | Recommended buyer-facing name | Packaging note |
|---|---:|---|---|
| Pilot | USD 149 / 30 days | Orvo OS Activation Sprint | Concierge setup, data-health, first cases, readiness lanes, weekly review. |
| Starter | USD 79-99/mo | Orvo Control Plane Starter | One Tiendanube store, daily brief, basic cases, readiness statuses, limited recipients/history. |
| Growth | USD 199/mo | Orvo Control Plane Growth | More workflow depth, more recipients/checks/history, verified fulfillment/Meta/fiscal/payment expansion only when gates pass. |
| Custom | USD 399+/mo scoped | Orvo Operations Control Plane Custom | Multi-store, custom connectors, agency/accountant views, SLA/security, deeper governance. |

Do not price by AI message, WhatsApp conversation, alert count, or seat. The primary value unit remains **one monitored store / operational control plane**.

## 8. First 10 lead segment adjustment

The first 10 lead packet remains valid, but OS positioning should change how leads are prioritized inside equal scores.

Add priority when a merchant has at least one of these visible/discovery signals:

- The owner/admin asks daily: “qué vendimos, qué cobré, qué falta facturar, qué está trabado.”
- They use Tiendanube plus Mercado Pago/bank transfers/manual payment review.
- They mention accountant/admin/fiscal tool coordination as a recurring task.
- They have enough SKU/order complexity that stock and sales cases are credible, plus enough admin complexity that OS breadth matters.
- They explicitly dislike “another dashboard” but want a morning operating answer.

Do not over-prioritize merchants who only want ARCA/facturación, payment reconciliation, or a chatbot. Those are not the first product.

## 9. Next commercial action

For the next GTM run, produce a one-page sales asset or landing-page wireframe using this headline:

> “El centro operativo diario para tu Tiendanube: casos, evidencia y próximos pasos.”

It should include:

1. the OS snapshot promise;
2. the USD 149 Activation Sprint box;
3. three case examples (`data_stale`, `stockout_risk`, configured `sales_drop`);
4. four readiness lanes (fulfillment, customer attention, ARCA/fiscal, treasury/reporting);
5. “WhatsApp te avisa; Orvo guarda el historial”;
6. clear exclusions: no chatbot, no ERP, no automatic actions, no tax advice.

## Bottom line

The commercial move is not to abandon the Tiendanube exception desk. It is to sell the same wedge as the first visible slice of a PyME operating system. The Activation Sprint should give buyers a credible control-plane experience — cases, evidence, freshness, readiness, follow-up — while staying honest about what is not yet automated or integrated.
