# Orvo Paid Pilot Onboarding Checklist — Tiendanube Exception Desk

Status: GTM execution asset
Date: 2026-06-02
Owner: Codex GTM / Pricing / Packaging
Scope: First 3-5 paid pilots for one Tiendanube store/control plane; docs-only commercial runbook.

## Purpose

This checklist turns the USD 149 / 30-day pilot offer into a repeatable operating motion. Use it after a prospect passes qualification and before Orvo claims it can deliver a daily WhatsApp exception brief.

The onboarding promise is narrow:

> In 30 days, Orvo will validate whether one Tiendanube operation can produce useful evidence-backed cases, a daily WhatsApp exception brief, and enough follow-up habit to justify Starter or Growth.

This is not a chatbot launch, BI onboarding, generic automation setup, agency management rollout, or multi-store implementation.

## Sources used

Repo/product sources:

- `docs/organization/2026-05-30-codex-24-7-autonomous-operating-system.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/gtm/2026-06-01-paid-pilot-close-kit.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/research/2026-05-30-icp-scoring-framework.md`
- `docs/research/2026-05-30-latam-d2c-pain-points.md`
- `docs/research/2026-05-30-buyer-journey-objection-playbook.md`
- `docs/research/2026-05-30-whatsapp-first-operations.md`
- `docs/research/2026-06-01-agency-assisted-icp-partner-wedge.md`

Assumptions and limits:

- No current competitor pricing is quoted here; existing pricing docs remain the pricing source of truth.
- The pilot is merchant-led and per-store, even when an agency/freelancer is a recipient or resolver.
- `fulfillment_backlog`, Meta Ads, WhatsApp inbox ingestion, and autonomous actions stay out of the default pilot unless implementation and truth gates are explicitly passed.
- WhatsApp is a projection surface. Operational Cases, run ledger, evidence, and lifecycle state remain the source of truth.

## 1. Pre-onboarding acceptance gate

Do not start setup until each hard gate is answered with a clear **yes**.

| Gate | Required answer | Evidence to capture | If not true |
|---|---|---|---|
| Paid pilot accepted | Buyer agrees to USD 149 / 30 days or approved ARS equivalent at invoice time. | Payment/invoice note and start date. | Do not provide ongoing monitoring; offer nurture or one-time data-health content. |
| One store selected | Exactly one Tiendanube store is the pilot control plane. | Store URL, admin owner, business name, timezone/currency. | Route multi-store/agency requests to Custom waitlist. |
| Named operator | A named owner/operator will read and act on cases. | Name, WhatsApp number, role, backup contact. | Do not pilot; alerts will become noise. |
| Tiendanube is source of truth | Stock/orders are maintained in Tiendanube or a clear upstream sync is understood. | Merchant statement plus first data-health audit result. | Open a data-health-only path; do not sell stock/sales confidence. |
| Pilot scope accepted | Buyer accepts “Orvo detects/recommends; human decides.” | Written scope acknowledgement. | Disqualify if autonomous changes are required now. |
| WhatsApp channel fit | Buyer wants the morning brief in WhatsApp or an agreed backup channel. | Destination/group/contact and preferred send window. | Keep as internal/operator pilot only or defer. |

### Recommended acceptance message

```text
Confirmo el alcance del piloto Orvo:
- 1 tienda Tiendanube durante 30 días.
- Brief operativo diario por WhatsApp.
- Casos con evidencia para datos stale/no confiables, stock en riesgo y ventas bajo piso configurado cuando aplique.
- Orvo no hace acciones automáticas: abre casos y recomienda; una persona decide.
- Si el dato de Tiendanube no es confiable, Orvo lo marca como dato stale en vez de inventar.
```

## 2. Day 0 commercial setup packet

Capture these fields before engineering/operator setup begins.

| Field | Value |
|---|---|
| Merchant/legal name | `[merchant]` |
| Store URL | `[store_url]` |
| Tiendanube admin owner | `[name/email]` |
| Pilot start date | `[date]` |
| Pilot end / renewal decision date | `[date]` |
| Buyer | `[name/role]` |
| Daily operator | `[name/role]` |
| Backup operator | `[name/role]` |
| Agency/freelancer recipient, if any | `[name/role/company]` |
| WhatsApp destination | `[number/group]` |
| Preferred brief window | `[time/timezone]` |
| Main pain named in discovery | `[stockout/data stale/sales floor/fulfillment/manual checks]` |
| Monthly order estimate | `[count]` |
| Active SKU/product estimate | `[count]` |
| Current tools/apps | `[Tiendanube + ...]` |
| Current manual-check minutes/day | `[minutes]` |
| Paid pilot amount | `USD 149 / ARS equivalent` |
| Invoice/payment status | `[paid/pending]` |

Minimum rule: if the “main pain named in discovery” field is blank, do not proceed. A pilot without a named pain is not validating willingness to pay.

## 3. Tiendanube data-health intake

The first operator task is not “send alerts.” It is to decide which owner-facing claims are safe.

### Source-health checks

| Check | Pass condition | Pilot action |
|---|---|---|
| Authorization / token | Tiendanube access works through approved secret handling. | Proceed; log connector health. |
| Store identity | Store ID/name/timezone/currency are known and match merchant. | Proceed; include in run config. |
| Product/SKU mapping | Products and variants needed for stock cases can be identified consistently. | Enable `stockout_risk` only for mapped entities. |
| Stock tracking | Active products have usable stock values or a known upstream sync. | Enable stock cases only where fresh/mapped. |
| Order/revenue visibility | Recent orders and timestamps are readable enough for configured sales floor. | Enable conservative `sales_drop` only if floor/baseline is agreed. |
| Freshness policy | Last-successful source timestamp is inspectable. | Enable `data_stale`; suppress/narrow downstream advice when stale. |
| Fulfillment fields | Paid/unfulfilled/aging semantics are verified for this store. | Keep owner-facing fulfillment out unless this passes. |
| Redaction | Tokens, URLs, secrets, personal data, and evidence snippets are safe for owner/operator projection. | Block external brief until safe. |

### Data-health outcomes

Use one of three outcomes after the first audit:

| Outcome | Meaning | Commercial handling |
|---|---|---|
| Green | Tiendanube data supports `data_stale`, mapped `stockout_risk`, and conservative sales-floor monitoring. | Continue normal pilot. |
| Yellow | Some data is usable, but limits must be explicit. | Continue pilot with a written caveat and narrower case families. |
| Red | Data is too unreliable for owner-facing claims. | Pause normal pilot; offer cleanup plan or refund/credit decision. |

Buyer-facing data-health copy:

```text
Primer diagnóstico de datos:
- Lo que Orvo puede mirar con confianza: [items]
- Lo que queda limitado o bloqueado: [items]
- Qué pasa si el dato se vuelve stale: Orvo abre un caso de datos no confiables y no inventa stock/ventas.
```

## 4. Threshold and case-family configuration

Configure only what maps to deterministic evidence and accepted product readiness.

| Case family | Pilot default | Required setup question | Owner-facing rule |
|---|---|---|---|
| `data_stale` | Always enabled. | “¿Cuánto tiempo sin datos frescos ya te preocupa?” | Always allowed when source health/freshness is inspectable. |
| `stockout_risk` | Enabled for mapped SKUs/products with fresh stock. | “¿Qué stock mínimo te preocupa para tus SKUs que venden?” | Include product/SKU, current stock, recent movement or strategic flag, evidence source. |
| `sales_drop` | Optional, configured floor only. | “¿Cuál es el piso de pedidos/ventas que si no se cumple a las 12/18 hs querés mirar?” | Do not claim root cause; use floor/baseline language only. |
| `fulfillment_backlog` | Internal/conditional. | “¿Cómo marca Tiendanube pagado, enviado, cancelado y reembolsado en tu tienda?” | Owner-facing only after field audit passes. |
| `spend_without_orders` | Out of default pilot. | “¿Cuánto gastás en Meta y quién lo mira?” | Sell as Growth expansion only after Meta connector/truth gate. |

### Minimum threshold record

```text
Freshness threshold: [hours]
Stock threshold: [units or category-specific thresholds]
Important SKUs/products: [list]
Sales floor window: [optional: time + orders/revenue floor]
Fulfillment SLA: [internal only unless field audit passed]
```

## 5. WhatsApp brief readiness gate

Before sending the first daily brief to the merchant, confirm:

- [ ] The brief is generated from canonical cases/evidence, not from ad hoc report text.
- [ ] Every owner-facing number has an evidence/source line.
- [ ] Stale/degraded data is explicit.
- [ ] Resolved cases are not shown as actionable.
- [ ] The total open-case count remains truthful when the message truncates top cases.
- [ ] The message is concise enough to be read on a phone and forwarded to an operator.
- [ ] Any action shown to the buyer maps to an implemented, audited action key.
- [ ] Secrets, tokens, private URLs, and sensitive payload values are redacted at the text boundary.

First-brief template:

```text
📋 Orvo — [día/fecha] — Tienda: [store]

Estado de datos: [fresco / limitado / stale]

[🔴/🟡] Caso 1: [case title]
→ por qué importa: [short reason]
→ evidencia: [source + id/timestamp]
→ acción sugerida: [human action]

Abiertos totales: [count]
Ver detalle/historial: [link or operator note]
```

Do not send a “perfect-looking” brief if source data is stale. The correct first value can be: “tu dato no es confiable y por eso no voy a inventar.”

## 6. 30-day pilot operating cadence

| Day | Milestone | Owner/operator action | Orvo proof to capture |
|---:|---|---|---|
| 0 | Paid pilot accepted | Pay/approve scope and provide contacts. | Signed scope, payment state, pilot dates. |
| 1 | Connector/data-health setup | Grant Tiendanube access or provide assisted import path. | Source-health outcome: Green/Yellow/Red. |
| 2 | Threshold calibration | Confirm stock/freshness/sales-floor thresholds. | Config record and accepted case families. |
| 3 | First daily brief | Read/forward/reply. | Delivery result, cases shown/skipped, evidence freshness. |
| 5 | Noise check | Mark any case as useful/noisy/missing. | False positive notes and threshold adjustments. |
| 7 | Week 1 review | Decide whether pilot is producing useful cases or only data-health work. | Cases opened/updated/resolved, manual-check minutes replaced. |
| 14 | Habit check | Confirm whether WhatsApp brief is part of morning routine. | Read/reply/forward behavior; unresolved case count. |
| 21 | Expansion signal check | Surface requests for more recipients/workflow/ads/fulfillment/history. | Starter vs Growth indicators. |
| 25-28 | Renewal decision | Choose Starter, Growth, Custom waitlist, cleanup path, or stop. | Value summary and conversion recommendation. |
| 30 | Pilot close | Confirm next plan or offboarding. | Final commercial outcome. |

## 7. Weekly value statement

Send one concise weekly proof note. It should quantify value without guaranteeing revenue lift.

```text
Resumen semanal Orvo — [store]

- Casos abiertos/actualizados: [count]
- Casos resueltos o reconocidos: [count]
- Casos de datos stale/no confiables: [count]
- Stock en riesgo detectado: [count]
- Chequeos manuales potencialmente reemplazados: [minutes/day × days]
- Caso más útil según tu feedback: [case]
- Ajustes hechos: [thresholds/case scope]

Recomendación de Orvo para la semana próxima: [continue / adjust thresholds / fix data / evaluate Growth]
```

Rules:

- Say “revenue at risk” when margin or avoided-loss proof is unknown.
- Do not say “stockout avoided” unless the merchant acted and the case evidence supports that claim.
- Do not imply Meta/fulfillment monitoring unless those connectors/case gates were actually active.

## 8. Conversion decision tree

### Convert to Starter when

- One Tiendanube store remains the right unit.
- Daily brief plus basic open/acknowledged/resolved lifecycle is enough.
- The merchant values `data_stale`, mapped `stockout_risk`, and conservative configured sales-floor cases.
- Setup/support load is trending toward repeatable SaaS, not ongoing analyst labor.
- At least one useful case or data-health finding created a clear operational action.

Recommended close:

```text
El piloto ya validó que Orvo te sirve como desk diario para una tienda.
Mi recomendación es pasar a Starter: mismo brief, mismos casos base, menos concierge.
```

### Convert to Growth when

- The buyer asks for more recipients, brief windows, weekly proof review, more history, assignment/comments, agency accountability, or higher order/SKU limits.
- Fulfillment backlog is commercially important and that store passed the fulfillment truth gate.
- Meta Ads monitoring is the strongest ROI path, but must wait for verified connector/truth gates.
- Ongoing human review is desired and should be priced, not hidden inside Starter.

Recommended close:

```text
Lo que estás pidiendo ya no es solo un brief diario: es workflow operativo.
Eso corresponde a Growth porque incluye más límites, más seguimiento y revisión semanal.
```

### Stop or pause when

- Tiendanube data is unreliable and the buyer will not fix it.
- Most days have no actionable cases and the store lacks operational urgency.
- The buyer wants dashboards, chatbot flows, or autonomous external actions instead of cases.
- The owner/operator does not read or act on the brief.
- Concierge time exceeds willingness to pay and produces no reusable learning.

## 9. Offboarding / pause checklist

If the pilot stops, leave the relationship clean:

- [ ] Revoke or confirm revocation path for Tiendanube access.
- [ ] Stop WhatsApp/operator delivery.
- [ ] Preserve redacted case/run summary internally for learning.
- [ ] Send a concise reason: converted, paused for data cleanup, no fit, no champion, or scope mismatch.
- [ ] If appropriate, set a 60-90 day revisit trigger tied to volume growth, data cleanup, or new connector readiness.

## 10. Next commercial action

For the next qualified lead, use this onboarding checklist as the internal pilot setup form. The immediate sales motion should be:

1. Build or select 10 Fashion/Apparel and Cosmetics Tiendanube leads that match the close-kit ICP.
2. Run the five-question discovery script.
3. Offer the USD 149 pilot only after a named pain, named operator, and Tiendanube data willingness are confirmed.
4. Start onboarding with the Day 0 packet above within 2 business days of payment.
5. Track the first three pilots in one shared table using: source-health outcome, cases opened, useful cases, false positives, manual-check minutes replaced, support minutes, and conversion recommendation.
