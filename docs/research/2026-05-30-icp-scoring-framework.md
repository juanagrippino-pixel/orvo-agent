# ICP Scoring Framework — Quantitative Qualification for Orvo Pilots

Date: 2026-05-30
Status: Market Research — Sales qualification framework for pilot/beta
Prior research: `docs/research/2026-05-24-tiendanube-latam-d2c-buyer-pain-icp.md`, `docs/research/2026-05-25-ecommerce-ops-buyer-research-tiendanube.md`

## Executive Summary

Not all Tiendanube stores are good Orvo customers. Some lack the operational urgency, some have data too dirty to support deterministic cases, and some want dashboards instead of case queues. This scoring framework gives the sales team a repeatable, quantitative way to qualify pilot candidates before spending concierge time on them.

**Target: score each prospect 0-100. Pilot candidates scoring ≥65 get a sales call. Candidates scoring ≥80 get priority outreach.**

---

## Scoring Dimensions (5 axes, 20 points each)

### Axis 1: Operational Urgency (0-20)

Measures: Does the store have enough daily operational activity that missed exceptions cost real money?

| Score | Criteria |
|-------|----------|
| 0-4 | Hobby store, <50 orders/month, <20 SKUs, no active ads, no fulfillment complexity. |
| 5-9 | Small but growing: 50-150 orders/month, 20-50 SKUs, occasional ads, some fulfillment pain. |
| 10-14 | Active store: 150-500 orders/month, 50-150 SKUs, regular Meta Ads, weekly stockouts or fulfillment delays. |
| 15-17 | High-volume store: 500-2,000 orders/month, 150-500 SKUs, daily ad spend, fulfillment team, WhatsApp-heavy. |
| 18-20 | Intense operation: 2,000+ orders/month, 500+ SKUs, multiple brands/channels, agency + in-house operations. |

**Discovery questions:**
- "¿Cuántos pedidos tenés por mes, aproximadamente?"
- "¿Cuántos productos/SKUs activos tenés?"
- "¿Gastás en publicidad digital? ¿Cuánto por mes?"

### Axis 2: Buyer Pain & Willingness to Pay (0-20)

Measures: Is the buyer feeling operational pain NOW and willing to pay to solve it?

| Score | Criteria |
|-------|----------|
| 0-4 | No recent operational miss. Says "todo está bien." No budget conversation. |
| 5-9 | Aware of problems but not urgent. "A veces pasa pero lo manejamos." Open to free tool, not paid. |
| 10-14 | Had 1-2 operational misses in 30 days (stockout, stuck order, stale data). Open to paid if value is clear. |
| 15-17 | Had 3+ operational misses recently. Can name specific incident that cost money/time. Willing to pay USD 79-149/month. |
| 18-20 | Acute operational pain. Losing customers/revenue weekly. Has budget allocated or can decide quickly. Will pay USD 149+ without hesitation. |

**Discovery questions:**
- "¿Podés nombrar un problema operativo de los últimos 30 días que te costó plata o tiempo?"
- "¿Qué pasaría si ese problema te avisa a las 8 AM en vez de enterarte a las 4 PM?"
- "¿Cuánto te costó el último incidente de stock/despacho/datos?"
- "Si algo así te ahorra uno de estos incidentes por mes, ¿pagarías $149/mes?"

### Axis 3: Data Readiness (0-20)

Measures: Is Tiendanube (or alternative source) maintained well enough for Orvo to produce reliable cases?

| Score | Criteria |
|-------|----------|
| 0-4 | Tiendanube data is known-broken. Stock counts wrong, orders not categorized, no variants configured. Buyer won't fix it. |
| 5-9 | Data is messy. Some products without stock tracking, inconsistent categories, OAuth tokens expire without renewal. Buyer might fix. |
| 10-14 | Mostly clean. Stock tracking enabled on most products, orders categorized, OAuth working. Some cleanup needed. |
| 15-17 | Clean. Stock tracking on all active SKUs, orders well-categorized, Tiendanube admin is source of truth for commerce. |
| 18-20 | Pristine. Full variant/SKU tracking, integrations maintained, data hygiene is a stated priority. Tiendanube API scopes are correct and monitored. |

**Discovery questions:**
- "¿Usás el stock de Tiendanube activamente o tenés un sistema aparte?"
- "¿Cada cuántas horas se actualiza automáticamente tu stock/estado de pedidos en Tiendanube?"
- "¿Alguna vez se te venció el token/integración y no te diste cuenta?"
- "¿Hay productos en Tiendanube que NO deberían estar activos (descatalogados, prueba, etc.)?"

### Axis 4: Operational Champion (0-20)

Measures: Is there an accountable human who will own case follow-up?

| Score | Criteria |
|-------|----------|
| 0-4 | No clear owner. "Lo vemos entre todos." Alerts would become noise because nobody acts. |
| 5-9 | Informal owner but no process. "Generalmente lo mira Juan pero depende del día." |
| 10-14 | Named owner who checks daily. Has some process for follow-up. Will engage with Orvo cases. |
| 15-17 | Dedicated ecommerce operator. Daily routine includes checking operations. Has accountability for results. |
| 18-20 | Owner/founder personally accountable. Checks operations daily, follows up rigorously. Will champion Orvo internally. |

**Discovery questions:**
- "¿Quién mira el estado operativo de la tienda todos los días?"
- "¿Qué pasa cuando ese alguien está de vacaciones o enfermo?"
- "¿Cómo se aseguran de que los problemas no queden abiertos sin resolver?"
- "Si Orvo abre un caso a las 8 AM, ¿quién lo recibe y actúa?"

### Axis 5: Platform & Stack Fit (0-20)

Measures: Does the prospect's technology stack align with Orvo's Tiendanube + WhatsApp model?

| Score | Criteria |
|-------|----------|
| 0-4 | Not on Tiendanube, or Tiendanube is a minor channel. No WhatsApp Business usage. Wants Shopify/BigCommerce solution. |
| 5-9 | Tiendanube is one of many channels. Uses WhatsApp personally but not for business. Stack doesn't include Orvo-connectable tools. |
| 10-14 | Tiendanube is primary storefront. Uses WhatsApp Business (app, not API). Has 1-2 Tiendanube apps in stack. |
| 15-17 | Tiendanube is THE storefront. Active WhatsApp Business usage. Stack includes Tiendanube + ERP + shipping + ads. Good connector coverage. |
| 18-20 | Tiendanube-centric operations. WhatsApp Business API or advanced WhatsApp usage. Full stack: Tiendanube + Dux/Contabilium + shipping + Meta Ads + marketplace sync. |

**Discovery questions:**
- "Tiendanube es tu tienda principal o tenés otros canales igual de importantes?"
- "¿Usás WhatsApp Business o WhatsApp personal para el negocio?"
- "¿Qué herramientas/apps pagás actualmente para manejar la tienda?"
- "¿Cómo se conectan tus herramientas entre sí?"

---

## Scoring Calculator

```
Total Score = Axis 1 + Axis 2 + Axis 3 + Axis 4 + Axis 5

Range: 0 - 100
```

### Score Bands

| Band | Score | Action |
|------|-------|--------|
| **A — Hot Lead** | 80-100 | Priority outreach. Book pilot call within 48 hours. Offer USD 149 pilot with confidence. |
| **B — Qualified** | 65-79 | Standard outreach. Discovery call, qualify further. Offer pilot if pain is validated. |
| **C — Nurture** | 45-64 | Content nurture. Not ready yet — pain may develop or data may improve. Monthly check-in. |
| **D — Disqualified** | 0-44 | Not a fit now. Don't spend sales time. Add to newsletter, revisit in 6 months. |

### Quick Disqualification Rules (bypass scoring)

Even a high-scoring prospect should be disqualified if ANY of these are true:

1. **No Tiendanube commerce data.** Store is service/digital product only.
2. **Buyer wants dashboards/BI, not operational cases.** Category mismatch.
3. **Buyer expects autonomous actions in pilot.** "I want Orvo to pause my ads automatically."
4. **Buyer won't fix dirty data.** "We know our stock is wrong but we won't change it."
5. **No operational champion.** Nobody will act on cases.
6. **Enterprise with mature OMS/WMS.** They need a different product.
7. **Budget ceiling below USD 49/month.** Can't sustain even Starter pricing.

---

## Sales Process by Score Band

### Band A (80-100) — Hot Lead

**Timeline:** 48 hours from identification to pilot offer
**Process:**
1. Inbound lead or referral. Respond within 2 hours.
2. 15-minute qualification call: confirm scoring, validate pain.
3. If confirmed: offer USD 149 pilot immediately. Send pilot agreement.
4. Schedule onboarding within 5 business days.
5. Weekly check-in during pilot.

**Key messaging:** "Basado en lo que me contaste, el caso típico de un cliente como vos paga el piloto solo con 1-2 casos de stockout evitados por mes."

### Band B (65-79) — Qualified

**Timeline:** 1-2 weeks from identification to pilot offer
**Process:**
1. Discovery call (30 min): deep dive into operations, pain, and stack.
2. Adjust scoring based on conversation.
3. If moves to Band A: fast-track to pilot offer.
4. If stays Band B: offer pilot with standard terms, give time to think.
5. Follow up at 3 days and 7 days.

**Key messaging:** "Lo que más les pasa a tiendas como la tuya es que se les escapa un stockout justo cuando corre publicidad. ¿Te pasó?"

### Band C (45-64) — Nurture

**Timeline:** Monthly engagement, revisit quarterly
**Process:**
1. Add to content nurture: weekly Tiendanube operations tips (Spanish).
2. Share "What Your Dashboard Won't Tell You" content series.
3. Every 90 days: re-score based on any changes (growth, new pain, data improvement).
4. If moves to Band B: initiate discovery call.

**Key messaging:** "Seguimos publicando casos concretos de cómo tiendas Tiendanube manejan sus excepciones. Te mantengo al tanto."

### Band D (0-44) — Disqualified

**Timeline:** No active sales effort
**Process:**
1. Thank them for their time.
2. Add to general newsletter if interested.
3. Revisit in 6 months if they reach out again.

**Key messaging:** "Por ahora Orvo está optimizado para tiendas con más volumen operativo. Cuando crezcas, hablemos."

---

## ICP Segments — Prioritized

### Segment Priority 1: Fashion & Apparel D2C

**Why first:**
- Highest SKU complexity (size × color × style) → most stockout/oversell risk.
- Active ad spend (Instagram, Meta) → `spend_without_orders` has strong WTP.
- WhatsApp-heavy for customer inquiries → natural fit for WhatsApp projection.
- Seasonal/flash sales create bursty operations → daily monitoring is urgent.

**Example stores:** Clothing brands, shoe stores, accessory brands, activewear, children's clothing.

**Orvo pitch:** "En moda, un stockout durante una campaña de Instagram es plata que se va y no vuelve. Orvo te avisa antes de que sea tarde."

### Segment Priority 2: Cosmetics & Personal Care D2C

**Why second:**
- High repeat purchase rate → stockout means permanent customer loss.
- Influencer-driven campaigns with short windows → timing sensitivity.
- Product expiration/batch tracking adds operational complexity.
- Strong ad spend efficiency requirements.

**Example stores:** Skincare brands, makeup, hair care, fragrances, wellness products.

**Orvo pitch:** "Si te quedás sin stock de un producto que una influencer está recomendando, esa clienta no vuelve. Orvo vigila."

### Segment Priority 3: Home & Decoration D2C

**Why third:**
- Lower daily order volume but higher ticket → each missed/faulty order is expensive.
- Fulfillment complexity (large items, custom orders, longer lead times).
- ERP usage common → integration opportunity.
- Less ad spend urgency than fashion/cosmetics.

**Example stores:** Furniture, home decor, candles, artisan products, kitchen goods.

**Orvo pitch:** "Un pedido de $80,000 que queda trabado 5 días es un cliente que reclama y un costo de logística que se duplica. Orvo monitorea el despacho."

### Segment Priority 4: Electronics & Accessories D2C

**Why fourth:**
- Fewer SKUs but high-value items.
- Same-day/next-day shipping expectations → fulfillment SLA is tight.
- Heavy competition → ad spend efficiency critical.
- Technical product questions via WhatsApp.

**Example stores:** Phone accessories, gadgets, computer peripherals, smart home devices.

**Orvo pitch:** "En electrónica, el que despacha primero gana. Orvo te dice si tenés pedidos pagados esperando."

### Segment Priority 5: Food & Beverage D2C

**Why fifth:**
- Perishable inventory adds urgency.
- Batch/lot tracking requirements.
- Local delivery complexity.
- Lower Tiendanube adoption (many use custom solutions or MercadoLibre-first).

**Example stores:** Craft food brands, specialty coffee, wine, gourmet snacks.

**Orvo pitch:** "Si un producto se vence en el depósito y seguís vendiéndolo online, es un problema que Orvo puede detectar antes."

---

## Scoring Examples

### Example 1: "Artemea" — Fashion Brand (Hot Lead)

- **Ax1 (Urgency):** 17/20 — 700 orders/month, 400 SKUs, daily Meta Ads spend.
- **Ax2 (Pain/WTP):** 16/20 — Had stockout on promoted product last week. Willing to pay.
- **Ax3 (Data):** 15/20 — Tiendanube stock well-maintained, some legacy products to clean up.
- **Ax4 (Champion):** 18/20 — Founder personally checks daily, follows up rigorously.
- **Ax5 (Stack):** 17/20 — Tiendanube + Dux + Meta Ads + Andreani + WhatsApp Business.

**Total: 83/100 → Band A. Offer pilot immediately.**

### Example 2: "Velas Artesanales" — Candles (Qualified)

- **Ax1 (Urgency):** 10/20 — 200 orders/month, 40 SKUs, monthly campaigns.
- **Ax2 (Pain/WTP):** 12/20 — Had 2 fulfillment delays last month. Interested but price-sensitive.
- **Ax3 (Data):** 14/20 — Tiendanube mostly clean, stock tracking active on most products.
- **Ax4 (Champion):** 15/20 — Owner runs operations daily, part-time help.
- **Ax5 (Stack):** 14/20 — Tiendanube + Correo Argentino + WhatsApp personal (not Business).

**Total: 65/100 → Band B. Discovery call, then pilot offer if pain validates.**

### Example 3: "LibreríaOnline" — Books (Nurture)

- **Ax1 (Urgency):** 8/20 — 100 orders/month, 200 SKUs (books), low ad spend.
- **Ax2 (Pain/WTP):** 6/20 — No recent crisis. "Todo funciona bien." Might try free tool.
- **Ax3 (Data):** 10/20 — Stock is managed but some products have inconsistent data.
- **Ax4 (Champion):** 12/20 — Owner checks when they remember, no daily routine.
- **Ax5 (Stack):** 8/20 — Tiendanube + personal WhatsApp. No other integrations.

**Total: 44/100 → Band D. Not worth sales effort now.**

### Example 4: "GymGear AR" — Fitness Equipment (Hot Lead)

- **Ax1 (Urgency):** 16/20 — 450 orders/month, 120 SKUs, heavy Meta Ads during New Year/summer.
- **Ax2 (Pain/WTP):** 17/20 — Lost ARS 200,000 last summer from stockout during campaign. Very motivated.
- **Ax3 (Data):** 12/20 — Tiendanube stock tracking on, but some variants not configured correctly.
- **Ax4 (Champion):** 17/20 — Operations lead dedicated to store, checks WhatsApp first thing daily.
- **Ax5 (Stack):** 16/20 — Tiendanube + Contabilium + Envia + Meta Ads + WhatsApp Business.

**Total: 78/100 → Band B (near A). Fast-track discovery, likely pilot within 1 week.**
