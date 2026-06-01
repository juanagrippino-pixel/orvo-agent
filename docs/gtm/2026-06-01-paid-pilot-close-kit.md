# Orvo Paid Pilot Close Kit — Qualification, ROI Worksheet, and Offer Sheet

Status: GTM execution asset
Date: 2026-06-01
Owner: Codex GTM / Pricing / Packaging
Scope: Tiendanube-first D2C operations control plane; paid pilot selling motion only.

## Purpose

Move the current pricing/ICP research into a close-ready asset for the first 3-5 paid pilots. Use this when a prospect is a Tiendanube-first D2C merchant and the sales goal is to decide, in one conversation, whether to offer the **Piloto Exception Desk Tiendanube + WhatsApp — USD 149 / 30 días**.

This is not a generic chatbot, BI dashboard, WhatsApp CRM, or automation pitch. The sellable job is:

> Orvo watches one Tiendanube operation, opens evidence-backed operational cases, sends a concise WhatsApp exception brief, and keeps follow-up state/history so the owner knows what needs attention today.

## Sources used

Repo/product sources:

- `docs/product/d2c-control-plane-prd.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`
- `docs/research/2026-05-30-icp-scoring-framework.md`
- `docs/research/2026-05-30-latam-d2c-pain-points.md`
- `docs/research/2026-05-30-pricing-intelligence.md`
- `docs/research/2026-05-30-buyer-journey-objection-playbook.md`
- `docs/research/2026-05-30-whatsapp-first-operations.md`
- `docs/research/2026-05-31-whatsapp-business-pricing-ops-briefs.md`

Assumptions and limits:

- Exact competitor prices should be re-verified before publishing externally; this document uses internal Orvo pricing and source docs as sales guidance.
- ROI examples are illustrative worksheets. Do not promise revenue lift or guaranteed savings.
- `fulfillment_backlog`, Meta Ads, WhatsApp inbox, and autonomous external actions must be sold only behind implementation/source-truth gates.
- Daily WhatsApp delivery should be packaged as included value, not per-message billing, because Meta utility-template COGS are low relative to Starter pricing in the current research.

## 1. Fast qualification gate

Use this before doing a full demo. If the prospect fails any hard gate, do not offer the paid pilot yet.

### Hard gates

| Gate | Pass condition | If not passed |
|---|---|---|
| Platform fit | Tiendanube is the primary commerce source of truth. | Nurture or route to future connector list. |
| Physical-goods operation | Store sells physical products where stock/order/fulfillment cases matter. | Disqualify for now; Orvo is not first selling digital/service commerce. |
| Operational champion | A named owner/operator will receive and act on cases. | Do not pilot; daily briefs become noise. |
| Data willingness | Merchant is willing to fix obvious Tiendanube data hygiene issues. | Do not pilot; bad data creates false positives and churn. |
| Paid intent | Buyer accepts that the 30-day pilot is paid. | Nurture; free users are not validating willingness to pay. |
| Scope agreement | Buyer accepts “human decides; Orvo detects/recommends” for pilot. | Disqualify if they require autonomous ad/stock/order actions now. |

### Target pilot profile

Best-fit first pilots look like this:

- Argentina/LatAm Tiendanube merchant on a serious paid plan or with equivalent operational activity.
- Fashion/apparel, cosmetics/personal care, home/deco, electronics/accessories, or another physical-goods category with SKU/order pressure.
- Roughly **150-1,000 orders/month** or enough SKU/ad/fulfillment complexity that missed exceptions cost money.
- Uses WhatsApp operationally and checks it early in the day.
- Has a concrete recent incident: stockout, stale data, delayed fulfillment, ad spend without orders, or missed follow-up.
- Can decide on a USD 149 pilot without procurement.

## 2. Discovery script with scoring shortcuts

The goal is to expose one quantified pain and one named operator. Keep it under 15 minutes.

### Opening

```text
Antes de mostrarte Orvo, quiero entender si tiene sentido para tu operación.
Orvo no es otro dashboard ni un bot: es una cola diaria de casos operativos
con evidencia para Tiendanube. Si no hay suficiente dolor operativo, te lo digo.
```

### Five questions that decide the deal

| Question | What to listen for | Strong answer |
|---|---|---|
| “¿Cómo es tu primera media hora del día con la tienda?” | Manual checking tax across tools. | Checks Tiendanube, WhatsApp, shipping, stock, ads, sheets every morning. |
| “¿Qué problema operativo de los últimos 30 días te costó plata o tiempo?” | Current pain and urgency. | Names stockout, delayed orders, stale data, broken sync, wasted ad spend. |
| “¿Cuántos pedidos/mes y SKUs activos tenés?” | Operational volume. | 150+ orders/month or SKU complexity that creates real stock risk. |
| “¿Usás el stock y estado de pedidos de Tiendanube como dato confiable?” | Data readiness. | Mostly yes; knows where cleanup is needed. |
| “Si Orvo abre un caso a las 8 AM, ¿quién lo recibe y quién lo resuelve?” | Champion/accountability. | Named owner/operator, not “lo ve el equipo”. |

### Close-or-nurture rule

Offer the paid pilot only if:

1. one hard-money/time pain is named;
2. Tiendanube data is usable or fixable;
3. a responsible operator is named;
4. the buyer says a USD 149 pilot is within decision range.

Otherwise, place into nurture with the relevant pain content rather than creating a high-touch low-fit pilot.

## 3. ROI worksheet for the sales call

Use prospect inputs. If a value is unknown, leave it blank instead of inventing it.

### A. Manual checking time saved

| Input | Prospect value |
|---|---:|
| Minutes/day checking Tiendanube + WhatsApp + shipping + ads + sheets | `[minutes]` |
| Business days/month | `22` |
| Operator hourly cost or owner value/hour | `[USD/hour]` |

Formula:

```text
Monthly time value = (minutes/day ÷ 60) × 22 × USD/hour
```

Example, clearly labeled as illustrative:

```text
30 min/day × 22 days × USD 12/hour = USD 132/month of attention reclaimed
```

Sales line:

```text
Si Orvo reemplaza aunque sea media hora diaria de chequeos, el Starter se acerca
a pagarse solo antes de contar stockouts, despachos o publicidad.
```

### B. Stockout risk avoided

| Input | Prospect value |
|---|---:|
| Stockouts/month on products that were selling | `[count]` |
| Estimated missed orders per stockout | `[orders]` |
| Average order value | `[USD or ARS]` |
| Gross margin % if known | `[margin]` |

Formula:

```text
Monthly gross loss = stockouts × missed orders × AOV × gross margin %
```

If margin is unknown, present revenue-at-risk, not profit saved.

Spanish line:

```text
No prometo que Orvo recupera ventas. Lo que sí mide el piloto es si detectamos
a tiempo los productos que se están quedando sin stock con evidencia de Tiendanube.
```

### C. Fulfillment / WISMO cost avoided

Only use if Tiendanube order/payment/fulfillment fields are reliable for this prospect.

| Input | Prospect value |
|---|---:|
| Paid orders aging beyond SLA per week | `[count]` |
| Refund/claim rate caused by delays | `[rate]` |
| Average order value | `[USD or ARS]` |
| Support minutes per WISMO message | `[minutes]` |

Formula options:

```text
Revenue at risk = aging orders × refund/claim rate × AOV
Support cost = WISMO messages × support minutes ÷ 60 × USD/hour
```

Guardrail:

```text
Pedimos validar primero cómo Tiendanube marca pago, despacho y cancelación en tu tienda.
Si el dato no es confiable, Orvo abre un caso de dato stale/no confiable en vez de inventar.
```

### D. Ad spend without orders

Use as Growth expansion trigger unless the Meta Ads connector and freshness parity are verified.

| Input | Prospect value |
|---|---:|
| Meta Ads spend/day | `[USD or ARS]` |
| Longest recent undetected bad-spend window | `[hours or days]` |
| Orders/revenue floor that should have triggered concern | `[floor]` |

Formula:

```text
Spend at risk = daily ad spend × bad-spend days before detection
```

Sales line:

```text
No vendemos atribución ni ROAS perfecto. El caso simple es operativo:
si hay gasto significativo y no entran pedidos, alguien tiene que mirar rápido.
```

## 4. Buyer-facing one-page offer

Use this as the proposal text after a qualified call.

```text
Piloto Exception Desk Tiendanube + WhatsApp — USD 149 / 30 días

Durante 30 días, Orvo mira tu Tiendanube y te manda por WhatsApp qué necesita
atención hoy: stock en riesgo, datos stale/no confiables y ventas bajo piso
configurado cuando aplique. Cada caso viene con evidencia y seguimiento.

Incluye:
- 1 tienda Tiendanube / 1 control plane operativo.
- Setup asistido de Tiendanube y umbrales.
- 1 brief operativo diario por WhatsApp.
- Hasta 2-3 destinatarios operativos, según el canal acordado.
- Casos con evidencia para `data_stale` y `stockout_risk` cuando el dato esté fresco.
- `sales_drop` solo como piso configurado o baseline confiable.
- Auditoría inicial de salud de datos.
- Revisión semanal de casos y ajustes del piloto.

No incluye en el piloto:
- Acciones automáticas sobre Tiendanube, stock, campañas o pedidos.
- Meta Ads / `spend_without_orders` salvo acuerdo explícito y conector verificado.
- WhatsApp inbox/chatbot para clientes.
- Dashboard BI a medida.
- Conectores custom, ERP/warehouse/accounting, MercadoLibre o multi-store.
- Garantía de aumento de ventas.

Criterio de éxito:
- Orvo abre/actualiza casos útiles con evidencia, o demuestra que el dato no es confiable.
- El brief reemplaza chequeos manuales diarios o reduce follow-up perdido.
- Al día 25-28 decidimos si seguir como Starter o Growth según volumen y workflow.
```

Recommended verbal close:

```text
Si Orvo no te abre al menos un caso accionable o no te muestra claramente
un problema de datos durante el piloto, no tiene sentido que sigamos. La idea
es validar valor real, no venderte otro reporte.
```

## 5. Pricing guardrails for the first 3-5 pilots

| Situation | Offer |
|---|---|
| Clean Band A lead with acute pain | USD 149 / 30-day pilot. No discount. |
| Strategic design partner with strong learning value but price friction | USD 149 pilot; optionally credit USD 79-99 to first paid month if they convert within 14 days. |
| Low-volume but high-learning store | Pilot only if data/vertical learning is exceptional; otherwise nurture. |
| Store wants ongoing concierge review | Do not force Starter; continue as Growth or scoped managed-service add-on. |
| Store asks for multi-store/agency | Custom waitlist or scoped Custom; do not bundle many stores into Starter. |
| Store asks for Meta Ads first | Position as Growth expansion after Tiendanube source truth is stable. |
| Store asks for free pilot | Decline; offer a short data-health check or nurture content if useful. |

Do not offer permanent USD 49/mo grandfathering. If a design-partner discount is needed, time-box it to 3 months and trade it for weekly feedback plus permission to use anonymized learnings.

## 6. Post-pilot conversion decision

Run this on days 25-28.

### Convert to Starter when

- 1 Tiendanube store is enough.
- 1 daily WhatsApp brief is enough.
- The buyer values `data_stale`, `stockout_risk`, and conservative `sales_drop`/data-health cases.
- Basic open/acknowledged/resolved lifecycle is enough.
- Onboarding/support load is trending toward productized SaaS, not manual analyst work.

### Convert to Growth when

- They need more recipients, multiple brief windows, comments/assignment/timeline depth, weekly review, more history, higher order/SKU limits, fulfillment workflow, or Meta Ads spend/order monitoring after connector truth gates.
- One bad operational day can exceed the Growth price.
- There is an agency/operator accountability angle.

### Do not convert when

- Data hygiene is too poor and the buyer will not fix it.
- The buyer only wants dashboards/exports or a chatbot.
- Most briefs are empty because the store lacks operational urgency.
- Concierge labor exceeds willingness to pay and does not create reusable product learning.
- The buyer requires autonomous external actions before governance and audit are implemented.

## 7. First outbound segments for the next commercial action

Prioritize lead list building in this order:

| Priority | Segment | Why now | First outreach hook |
|---:|---|---|---|
| 1 | Fashion/apparel Tiendanube stores with size/color variants | Highest SKU/stockout complexity and Meta/Instagram dependence. | “¿Te enterás antes de quedarte sin stock en el talle que está vendiendo por Instagram?” |
| 2 | Cosmetics/personal care brands with repeat purchases | Stockout can permanently lose repeat customers; campaign windows are short. | “Cuando una influencer mueve un producto, ¿quién vigila stock y pedidos esa mañana?” |
| 3 | Home/deco stores with higher-ticket orders | Fulfillment delays and custom/large-item logistics create expensive exceptions. | “Un pedido pago trabado 3 días puede valer más que un mes de Orvo.” |
| 4 | Electronics/accessories stores with same/next-day delivery pressure | Fulfillment speed and ad spend mismatch are commercially visible. | “Si gastás en tráfico y no entran pedidos, ¿cuántas horas tardás en enterarte?” |
| 5 | Tiendanube stores using Dux/Contabilium + shipping apps | App-sprawl monitoring is easy to explain. | “No reemplazamos tus apps; te avisamos cuando algo entre ellas necesita atención.” |
| 6 | Agencies managing 3-10 Tiendanube stores | Referral/Custom channel, but not first self-serve SKU. | “Una cola de excepciones por cliente para demostrar valor operativo.” |
| 7 | Stores with known Producteca/BaseLinker marketplace sync | Future sync-health value; watch but avoid widening too early. | “Cuando se rompe el sync, ¿quién se entera primero: ustedes o el cliente?” |
| 8 | Paid-ad-heavy stores already asking about ROAS | Strong WTP, but must avoid attribution trap until Meta connector is truth-gated. | “No hacemos atribución; detectamos gasto sin pedidos como incidente operativo.” |
| 9 | High-WhatsApp sales stores | Future `unanswered_conversations`; good for projection habit. | “El brief operativo llega al canal que ya abrís cada mañana.” |
| 10 | Low-volume but fast-growing founders | Nurture now, pilot later when urgency appears. | “Te paso un checklist de salud operativa para cuando superes el volumen actual.” |

## 8. Sales collateral snippets

### LinkedIn / community post seed

```text
La mayoría de las tiendas Tiendanube no necesitan otro dashboard.
Necesitan que alguien les diga a las 8 AM:

1. qué necesita atención,
2. por qué importa,
3. con qué evidencia,
4. quién lo sigue hasta resolverlo.

Eso es lo que estamos probando con Orvo: un Exception Desk para Tiendanube + WhatsApp.
No chatbot. No promesas mágicas. Casos operativos con evidencia.
```

### Cold WhatsApp / DM opener

```text
Hola [nombre], vi que operan Tiendanube en [categoría]. Estamos abriendo 3-5 pilotos pagos de Orvo: un brief diario por WhatsApp con casos operativos de Tiendanube (stock en riesgo, datos stale, ventas bajo piso), siempre con evidencia. ¿Te pasó en el último mes enterarte tarde de un stockout, pedido trabado o dato que no era confiable?
```

### Follow-up after discovery

```text
Resumen de lo que entendí:
- Hoy revisan [herramientas] cada mañana.
- El problema más caro reciente fue [incidente].
- Si eso se detecta antes de [hora], cambia [impacto].

Mi recomendación: piloto de 30 días, USD 149. Orvo abre casos con evidencia y medimos si reemplaza chequeos manuales / evita follow-up perdido. Si no aparece valor real, no seguimos.
```

## 9. What to track from day one

The pilot must produce commercial evidence, not only product feedback.

| Metric | Why it matters |
|---|---|
| Onboarding minutes | Detect whether USD 149 pilot is underpriced. |
| Tiendanube data-health findings | Qualifies ICP and product readiness. |
| Number of cases opened/updated | Core value proof. |
| Number of accepted/useful cases | Avoid vanity alerts. |
| False positives / suppressed cases | Trust and threshold tuning. |
| Manual checks replaced | Time-value proof. |
| WhatsApp read/reply/forward behavior | Habit and surface fit. |
| Support touches | COGS and scalability. |
| Requested expansions | Starter vs Growth signal. |
| Day 25 conversion decision | Pricing validation. |

## 10. Next commercial action

Build a list of **30 Fashion/Apparel and Cosmetics Tiendanube stores** in Argentina that appear to have:

1. active product variants/SKUs;
2. Instagram/Meta-driven demand;
3. visible WhatsApp Business usage;
4. enough catalog/order activity to plausibly score ≥65 in the ICP framework;
5. a founder/operator contact reachable through WhatsApp, Instagram, LinkedIn, or referral.

Run the five-question discovery script with the first 10 reachable leads, ask for the USD 149 pilot when the hard gates pass, and record every objection against the pricing/ICP docs.
