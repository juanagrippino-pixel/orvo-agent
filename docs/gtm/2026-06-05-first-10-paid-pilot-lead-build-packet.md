# First 10 Paid Pilot Lead Build Packet — Tiendanube Exception Desk

Status: GTM execution asset
Date: 2026-06-05
Owner: Codex GTM / Pricing / Packaging
Scope: Build the first qualified outreach batch for the USD 149 / 30-day Orvo paid pilot without drifting into chatbot, BI, or generic automation positioning.

## Purpose

This packet turns the existing ICP, pricing, close-kit, and onboarding docs into a concrete lead-building workflow for the first 10 commercial conversations.

The goal is not to create a huge lead database. The goal is to find **10 reachable Tiendanube-first D2C stores** where Orvo can credibly sell:

> a daily evidence-backed operations exception desk for one Tiendanube store, projected to WhatsApp, with cases for stale data, stock risk, and conservative sales-floor monitoring when the source data supports it.

Do not sell this as a chatbot, WhatsApp inbox, dashboard, agency report, or autonomous action tool.

## Sources used

Repo/product sources:

- `docs/organization/2026-05-30-codex-24-7-autonomous-operating-system.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/gtm/2026-06-01-paid-pilot-close-kit.md`
- `docs/gtm/2026-06-02-paid-pilot-onboarding-checklist.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`
- `docs/research/2026-05-30-icp-scoring-framework.md`
- `docs/research/2026-05-30-latam-d2c-pain-points.md`
- `docs/research/2026-05-30-buyer-journey-objection-playbook.md`
- `docs/research/2026-05-30-whatsapp-first-operations.md`
- `docs/research/2026-05-30-competitor-gap-analysis.md`
- `docs/research/2026-05-30-tiendanube-platform-intelligence.md`
- `docs/research/2026-05-30-pricing-intelligence.md`

Assumptions and limits:

- No current competitor pricing is quoted or invented here.
- This document does not name real merchants; it defines the repeatable lead-selection workflow.
- A lead is only pilot-eligible after discovery confirms a named pain, named operator, Tiendanube data willingness, and paid intent.
- WhatsApp remains a projection surface. Operational Cases, run ledger, evidence, and lifecycle state remain the source of truth.
- `fulfillment_backlog`, Meta Ads, WhatsApp inbox ingestion, and autonomous actions are expansion/conditional claims only behind implementation and truth gates.

## 1. Lead batch objective

Build a batch of **30 researched stores**, score them, and contact the **first 10** that clear a minimum pre-call threshold.

Batch targets:

| Target | Count | Why |
|---|---:|---|
| Total researched stores | 30 | Enough to avoid overfitting to one vertical or weak evidence. |
| Pre-qualified outreach-ready stores | 10 | First live commercial conversations. |
| Expected discovery calls | 3-5 | Early response rates will be uneven. |
| Expected paid pilots | 1-2 | Good first validation if qualification is strict. |

Do not chase volume before the first 10 conversations produce objection data.

## 2. First 30 sourcing mix

Use this mix to prevent the first list from becoming too broad:

| Priority | Segment | Count in first 30 | Why now | Strong visible signals |
|---:|---|---:|---|---|
| 1 | Fashion / apparel Tiendanube stores | 12 | Best launch fit for `stockout_risk`: variants, sizes, colors, campaign bursts. | Size/color variants, Instagram selling, “consultar por WhatsApp”, frequent new drops. |
| 2 | Cosmetics / personal care | 8 | Repeat purchase + campaign timing makes stockouts expensive. | Product collections, influencer/Instagram activity, bundles, visible WhatsApp. |
| 3 | Home / deco / higher-ticket goods | 5 | Higher ticket means one fulfillment or stock miss can justify pilot, but daily velocity may be lower. | Shipping complexity, custom/large items, explicit delivery promises. |
| 4 | Electronics / accessories | 3 | Useful for ad-spend and fulfillment urgency, but stronger Growth pull than Starter. | Same/next-day shipping, Meta/Instagram presence, WhatsApp product questions. |
| 5 | Agency/freelancer-managed Tiendanube clients | 2 | Referral/Custom signal; do not make first SKU multi-store. | Agency names in footer/social bio, multiple Tiendanube clients, ops/reporting offer. |

Rule: if the first 30 cannot produce at least 10 stores with visible WhatsApp + physical goods + plausible SKU/order pressure, stop and improve sourcing quality instead of lowering the ICP bar.

## 3. Pre-call scoring shortcut

Use public/visible evidence only before the discovery call. This is a fast 50-point screen, not the full 100-point ICP score.

| Axis | Max | What to look for before outreach |
|---|---:|---|
| Tiendanube/platform fit | 10 | Store appears to run on Tiendanube or is clearly a Tiendanube merchant. |
| Physical-goods SKU complexity | 10 | Variants, bundles, catalog depth, high-stock-risk category. |
| Operational urgency signal | 10 | Active drops, promos, delivery promises, campaign/social activity, high-ticket products. |
| WhatsApp operating fit | 10 | WhatsApp Business/contact is visible and likely used for sales/support. |
| Reachable decision-maker/operator | 10 | Founder/operator/contact is reachable through WhatsApp, Instagram, LinkedIn, email, referral, or agency. |

Pre-call bands:

| Score | Action |
|---:|---|
| 40-50 | Contact in first 10. Likely Band A/B if discovery confirms pain and data readiness. |
| 32-39 | Contact after the top 10 or when segment learning is useful. |
| 20-31 | Nurture/research only; do not spend live sales time yet. |
| <20 | Disqualify for now. |

Hard pre-call exclusions:

- Digital/service-only store.
- No visible way to contact a human operator.
- Marketplace-only or non-Tiendanube-first operation.
- Looks like a hobby/micro-store with no operational urgency.
- Public positioning suggests they want chatbot/support automation rather than operations monitoring.

## 4. Lead worksheet fields

Create one shared sheet/table with these exact fields so GTM and onboarding can reuse the same evidence.

| Field | Required? | Notes |
|---|---|---|
| Store / brand name | Yes | Public name. |
| Store URL | Yes | Tiendanube or ecommerce URL. |
| Segment | Yes | Fashion, cosmetics, home/deco, electronics, agency, other. |
| Country / province | Yes | Start with Argentina unless a high-fit LatAm lead appears. |
| Contact channel | Yes | WhatsApp, Instagram, LinkedIn, email, referral. |
| Contact person | Preferred | Founder/operator/agency contact if known. |
| Visible WhatsApp? | Yes | Yes/no + link/location. |
| Physical goods? | Yes | Must be yes. |
| Visible SKU/variant complexity | Yes | Low/medium/high + evidence. |
| Campaign/social activity | Yes | Low/medium/high + recent signal. |
| Likely pain hypothesis | Yes | `stockout_risk`, `data_stale`, `sales_drop`, `fulfillment_backlog`, `manual_check_tax`, other. |
| Pre-call score /50 | Yes | Use section 3. |
| ICP band after discovery | Later | Use full 100-point framework after call. |
| Discovery pain named | Later | One concrete recent pain or blank. |
| Named operator | Later | Person who receives/acts on cases. |
| Tiendanube data willingness | Later | Yes/no/unknown. |
| Paid pilot status | Later | Not offered / offered / accepted / declined / nurture. |
| Objection | Later | Exact buyer words. |
| Next step/date | Yes | Prevents ghosted leads from lingering forever. |

## 5. Pain hypothesis by segment

Use the pain hypothesis to personalize the first line. Do not assert that the store has the pain; ask whether it happened.

| Segment | First pain to test | Why | Safe first question |
|---|---|---|---|
| Fashion/apparel | `stockout_risk` on active variants | Size/color variants make manual monitoring brittle. | “¿Te pasó quedarte sin stock en un talle/color justo cuando estaba vendiendo por Instagram?” |
| Cosmetics/personal care | `stockout_risk` + campaign timing | Repeat purchase and influencer windows punish slow detection. | “Cuando una promo o influencer mueve un producto, ¿quién mira stock y pedidos esa mañana?” |
| Home/deco | `fulfillment_backlog` only as discovery, not default pilot claim | Higher ticket and logistics create expensive exceptions. | “¿Cómo detectan pedidos pagos que quedan trabados más de lo esperado?” |
| Electronics/accessories | ad spend / checkout / fulfillment urgency | Competitive category; one bad day can be expensive. | “Si gastan en tráfico y no entran pedidos, ¿cuánto tardan en enterarse?” |
| Agency-managed store | accountability / proof of daily follow-up | Agency can use Orvo as evidence, but first SKU is per store. | “¿Cómo le muestran al cliente qué excepciones operativas detectaron y siguieron esta semana?” |

Guardrail: for home/deco/electronics, do not sell owner-facing fulfillment or ads monitoring as included unless the actual pilot truth gates pass. Use those pains to qualify urgency and Growth potential.

## 6. Outreach sequence for the first 10

Keep the sequence short. The ask is a discovery conversation, not an immediate demo to everyone.

### Touch 1 — WhatsApp/Instagram DM opener

```text
Hola [nombre], vi que operan Tiendanube en [categoría]. Estoy abriendo pocos pilotos pagos de Orvo: un desk operativo para Tiendanube que te manda por WhatsApp qué necesita atención hoy (stock en riesgo, datos stale/no confiables y ventas bajo piso cuando aplique), siempre con evidencia.

Pregunta rápida: en el último mes, ¿te pasó enterarte tarde de un stockout, pedido trabado o dato de Tiendanube que no era confiable?
```

### Touch 2 — segment-specific follow-up after 2-3 days

Fashion/apparel:

```text
Lo pregunto porque en moda suele doler cuando se vende un talle/color por Instagram y el stock queda mal o se agota sin que nadie lo vea temprano.
Orvo no cambia stock ni pausa campañas: abre un caso con evidencia para que una persona decida.
```

Cosmetics/personal care:

```text
En cosmética el caso típico es campaña/promoción + stock que se mueve rápido. Orvo busca que el primer aviso sea un caso operativo, no un reclamo de una clienta.
```

Home/deco:

```text
En deco/hogar suele doler menos por volumen y más por ticket: un pedido pago trabado varios días puede costar más que el piloto. En Orvo primero validamos si el dato de Tiendanube permite mirar eso con confianza.
```

### Touch 3 — close or nurture after 7-10 days

```text
Cierro el seguimiento para no molestarte. Si hoy revisan Tiendanube/WhatsApp/envíos manualmente cada mañana y querés probar un brief operativo con evidencia, tengo lugar para conversar esta semana. Si no es prioridad, te puedo dejar un checklist de salud operativa para Tiendanube y retomamos más adelante.
```

Rules:

- Maximum 3 touches before moving to nurture.
- Every touch must reference an operational exception, not “AI,” “chatbot,” or “dashboard.”
- If they ask for a free ongoing pilot, decline and offer a one-time data-health/checklist conversation instead.
- If they ask for autonomous actions, say Orvo recommends and tracks; a human decides in the pilot.

## 7. Discovery call pass/fail gate

Offer the USD 149 pilot only if all hard gates pass:

| Gate | Pass signal | Fail handling |
|---|---|---|
| One store | One Tiendanube store is selected as the pilot control plane. | Multi-store goes to Custom waitlist or one-store pilot only. |
| Named pain | Buyer names a recent stock, stale data, fulfillment, sales-floor, or manual-check problem. | Nurture; no pain means no paid urgency. |
| Named operator | A person will receive and act on cases. | Do not pilot; case briefs become noise. |
| Data willingness | Buyer accepts that bad data may limit case families and must be fixed. | Disqualify if they want Orvo to invent certainty. |
| Paid intent | USD 149 / 30 days or approved ARS equivalent is acceptable. | Nurture; free pilot does not validate WTP. |
| Scope fit | Buyer accepts “Orvo detects/recommends; human decides.” | Disqualify if they require autonomous external actions now. |

If the buyer passes the gates, use the close-kit offer text and immediately start the onboarding checklist. Do not invent a custom plan during the call.

## 8. What to learn from the first 10 conversations

The first batch should produce learning even if few pilots close.

Track these questions:

| Learning question | Decision it informs |
|---|---|
| Which vertical most quickly names a painful recent incident? | First repeatable outbound segment. |
| Which pain gets the fastest “yes, that happened” response? | Demo and outreach opening hook. |
| How often is Tiendanube stock/order data trusted? | Pilot feasibility and onboarding risk. |
| Does USD 149 feel easy, acceptable, or blocked? | Pilot price validation. |
| Do buyers ask for WhatsApp, dashboard, email, or agency recipient? | Surface packaging. |
| Do buyers request Meta/fulfillment before stock/stale data? | Growth roadmap pressure. |
| How often do buyers confuse Orvo with chatbot/helpdesk/BI? | Messaging clarity. |
| How much manual-check time do they report? | ROI model calibration. |

Success for this batch is not only “closed pilots.” Success is a clean answer to: **which exact merchant segment, pain, and objection should the next 30 leads target?**

## 9. Weekly commercial review format

After the first 10 outreach attempts or at the end of the week, summarize:

```text
First 10 lead review — [date]

Lead outcomes:
- Contacted: [count]
- Replies: [count]
- Discovery calls booked: [count]
- Paid pilots offered: [count]
- Paid pilots accepted: [count]

Best segment signal:
- [segment + evidence]

Strongest pain signal:
- [pain + buyer words]

Main objection:
- [exact words]

Pricing signal:
- [easy / acceptable / blocked / unknown]

Product truth-gate issue:
- [data stale / fulfillment fields / Meta pull / WhatsApp delivery / none]

Next action:
- [build next 30 in same segment / shift segment / improve collateral / pause until product gate]
```

## 10. Next commercial action

Within the next GTM run:

1. Build the first 30-store worksheet using the sourcing mix above.
2. Select the 10 highest pre-call scores.
3. Send Touch 1 to those 10 only.
4. For every reply, run the discovery gate before offering the USD 149 pilot.
5. Feed exact buyer objections back into `docs/gtm/2026-06-01-paid-pilot-close-kit.md` or a future objection-update doc.
