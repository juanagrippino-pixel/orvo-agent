# Tiendanube Data Health Check — Acquisition + Qualification Wedge

Date: 2026-06-02  
Status: Market Research — bounded GTM/pricing slice  
Prior research checked: `2026-05-25-ecommerce-ops-buyer-research-tiendanube.md`, `2026-05-30-pricing-intelligence.md`, `2026-05-30-buyer-journey-objection-playbook.md`, `2026-05-30-tiendanube-platform-intelligence.md`, `2026-06-01-agency-assisted-icp-partner-wedge.md`  
Scope note: this cron environment did not expose live web-search tooling, so this run uses the repo's existing web-sourced research corpus and public links already captured in-repo; refresh source pages before quoting externally.

## Bounded question

Should Orvo offer a free/low-friction Tiendanube “data health check” before the paid Activation Sprint, and how can it qualify buyers without creating a support-heavy free tier?

## Short answer

Yes — but only as a **one-time diagnostic artifact**, not ongoing monitoring. The health check should convert a vague “interesting tool” conversation into a concrete paid-sprint decision by showing whether the store has enough operational complexity, data hygiene, and follow-up ownership for Orvo to work.

Recommended buyer-facing promise:

> “Conectamos Tiendanube una vez y te mostramos qué puede vigilar Orvo: datos desactualizados, productos con riesgo de stock y pedidos que podrían necesitar seguimiento. Si la data no sirve, también te lo decimos.”

## Evidence base and source links

Public/source links represented in prior corpus:

- Tiendanube seller workflow is fragmented across ventas, productos, medios de pago, envíos/locales, Envío Nube tracking/incidents, WhatsApp, and apps: <https://ayuda.tiendanube.com/es_AR/ventas>, <https://ayuda.tiendanube.com/es_AR/productos>, <https://ayuda.tiendanube.com/es_AR/medios-de-pago>, <https://ayuda.tiendanube.com/es_AR/envios-y-locales>, <https://ayuda.tiendanube.com/es_AR/envio-nube-gestion-de-envios>, <https://ayuda.tiendanube.com/es_AR/envio-nube-seguimiento>, <https://ayuda.tiendanube.com/es_AR/envio-nube-incidencias>
- Stock/stock-control education is a recurring Tiendanube theme, supporting `stockout_risk` as a diagnostic slice: <https://www.tiendanube.com/blog/como-funciona-el-stock-en-el-ecommerce/>, <https://www.tiendanube.com/blog/sistema-de-control-de-stock/>
- WhatsApp is already a seller surface in LatAm; prior corpus cites Tiendanube/NubeCommerce data that 71.5% of Argentine entrepreneurs used WhatsApp as a sales channel in 2025: <https://site.tiendanube.com/recursos/nubecommerce>, <https://www.tiendanube.com/blog/como-vender-por-whatsapp/>, <https://www.tiendanube.com/blog/whatsapp-business/>
- Tiendanube app ecosystem shows buyers already install point tools, but no app owns cross-source operational case state: <https://www.tiendanube.com/tienda-aplicaciones-nube>, <https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/gestion>, <https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/envios>
- Prior pricing research already recommends no free tier, with one exception: a one-time data health check for lead generation, not ongoing monitoring (`2026-05-30-pricing-intelligence.md`).

## Why this wedge matters

The buyer often does not yet know whether Orvo is an “app,” “dashboard,” “AI bot,” “agency replacement,” or “alert tool.” A one-time health check demonstrates the category by producing a small evidence-backed operating assessment.

It also solves three GTM problems:

1. **Reduces trust friction.** Merchants can see Orvo’s degraded-data honesty before paying.
2. **Prevents bad pilots.** If Tiendanube stock/order data is not maintained, Orvo can disqualify or require cleanup before Activation Sprint.
3. **Creates urgency from the buyer’s own facts.** “12 products with stock = 0 and recent sales” is stronger than generic ROI claims.

## Recommended diagnostic scope

Keep the health check narrow and deterministic. Do not promise the full control plane.

### Include

| Diagnostic area | Output | Why it qualifies |
|---|---|---|
| Connector/source freshness | last successful read, missing scopes, stale/failed state | Proves whether Orvo can safely operate |
| Catalog/stock coverage | products/variants counted, missing/negative/zero stock summary | Detects data hygiene and `stockout_risk` viability |
| Recent sales/order volume | last 7/30 day orders and revenue if safely available | Confirms operational urgency and plan fit |
| Candidate stock cases | top 3-5 low/zero stock products with recent movement | Shows concrete value without full monitoring |
| Fulfillment readiness, not claims | whether payment/shipping fields are interpretable | Gates future `fulfillment_backlog`; avoids false positives |
| WhatsApp/operator fit | recommended recipients and brief cadence based on team workflow | Confirms there is a human resolver |

### Exclude

- No ongoing daily alerts.
- No WhatsApp automation beyond sending the diagnostic/report sample if opt-in exists.
- No Meta Ads claims unless a paid Growth/Activation scope includes a connector.
- No autonomous actions: no pausing ads, changing stock, refunding, or messaging customers.
- No “AI found insights” language; every finding must cite source/evidence.

## Suggested artifact

Deliver a concise PDF/Markdown/WhatsApp-friendly summary with this structure:

```text
Diagnóstico Orvo — Tienda [nombre]

1) ¿La data está confiable?
- Tiendanube: OK / STALE / FALTA PERMISO
- Productos: X leídos; Y sin SKU; Z con stock negativo/cero
- Pedidos: X últimos 30 días; estado de despacho: verificable / no verificable

2) Qué vigilaría Orvo primero
- Stock: [3 candidatos con evidencia]
- Datos stale: [riesgos de fuente]
- Fulfillment: apto / requiere auditoría de estados

3) Fit comercial
- Plan sugerido: Activation Sprint / Starter / Growth / no fit todavía
- Motivo: volumen, SKUs, WhatsApp workflow, datos confiables

4) Próximo paso
- Si querés monitoreo diario por WhatsApp + casos con historial: Activation Sprint 30 días.
```

## Qualification rules

| Result | Action |
|---|---|
| Fresh data + 100+ orders/month or 50+ active SKUs + human resolver | Offer Activation Sprint immediately |
| Fresh data but lower volume | Nurture or Starter waitlist; do not oversell ROI |
| Stock/order fields inconsistent but buyer is motivated | Offer paid setup/readiness cleanup before monitoring |
| Tiendanube not source of truth | Require alternate connector scope; otherwise no fit |
| Buyer wants only “AI advice” or generic dashboard | Disqualify; Orvo is an operations control plane |
| No one owns follow-up | Disqualify or require named operator/agency recipient |

## Packaging recommendation

Use the health check as **lead generation**, not a free product tier:

- Public offer: “Free Tiendanube Data Health Check” for qualified stores only.
- Internal eligibility: require physical goods, active Tiendanube, and at least one urgency signal before doing the work.
- Output expiry: valid for 7 days; ongoing monitoring requires paid plan.
- Conversion CTA: USD 149 / 30-day Activation Sprint or USD 79-99/mo Starter where self-serve readiness is already strong.
- Limit free operational cost: cap at one run, one summary, one 20-minute review call.

If inbound quality is poor, reframe as **credited paid diagnostic**: USD 49-99 one-time, credited toward Activation Sprint.

## Sales copy to test

Spanish short version:

> “Antes de venderte Orvo, revisamos si tu Tiendanube tiene data suficiente para que valga la pena. Te damos un diagnóstico simple: fuentes confiables, productos en riesgo, pedidos/estados que se pueden monitorear y qué recibirías por WhatsApp. Si no hay fit, te lo decimos.”

Objection handler:

> “No es una auditoría de marketing ni un reporte de BI. Es una prueba de si podemos convertir tu operación diaria en casos accionables con evidencia.”

## Product and governance guardrails

- Run the diagnostic through the same runtime/registry/ledger/evidence path used by paid monitoring; do not create a shortcut script that later diverges.
- Mark all findings as diagnostic candidates, not persistent customer case state, unless the merchant is already onboarded to Orvo.
- Redact tokens, customer PII, exact URLs, and raw order identifiers in shared artifacts.
- Suppress downstream recommendations when source freshness fails; make `data_stale` the hero if needed.
- Do not let the sample WhatsApp brief become the source of truth for workflow state.

## Bottom line

A Tiendanube Data Health Check is a strong acquisition wedge because it demonstrates Orvo’s category — evidence-backed operational control — while filtering out bad-fit stores before the paid sprint. The key is to keep it one-time, truth-gated, and conversion-oriented: diagnose readiness, show 2-5 concrete candidate cases, then move the buyer to a paid Activation Sprint or disqualify.
