# WISMO + Carrier Visibility Readiness — Post-Dispatch Expansion for Tiendanube

Date: 2026-06-12  
Status: Market Research — bounded pain / ICP / competitor / packaging slice  
Prior research checked: `2026-06-05-fulfillment-backlog-pilot-packaging.md`, `2026-06-10-unanswered-whatsapp-conversations-readiness.md`, `2026-05-30-tiendanube-platform-intelligence.md`, `2026-05-24-orvo-competitor-landscape.md`, `2026-05-26-product-market-intel-tiendanube-control-plane.md`, `docs/specs/d2c-case-family-catalog.md`  
Scope note: this cron environment did not expose live web-search tooling, so this run uses the repo's existing web-sourced research corpus and public links already captured in-repo; refresh source pages before quoting externally.

## Bounded question

Should Orvo sell a WISMO / post-dispatch “shipment not moving” promise for Tiendanube merchants, and how should it be packaged without becoming a tracking app, helpdesk, or customer messaging tool?

## Short answer

Yes — but **only as a post-Starter, carrier-truth-gated expansion**, not as a default Tiendanube claim. WISMO ("¿dónde está mi pedido?") is commercially strong because it is visible to owners, support teams, and customers fast. But Tiendanube-first data is usually enough to detect **pre-dispatch backlog**, not to prove **post-dispatch no-movement** or customer-facing delivery risk. Orvo should package this as a **carrier-visibility readiness lane first**, then a Growth/Scale operational signal only when a trusted movement source exists.

Recommended buyer-facing phrasing:

> “Orvo no reemplaza tu tracking ni responde al cliente. Si existe una fuente confiable de movimiento del envío, Orvo avisa cuando un pedido ya despachado deja de moverse y eso pasa a ser un problema operativo.”

## Evidence base and source links

Public/source links represented in prior corpus:

- Tiendanube seller workflow spans sales, payment methods, shipping/local pickup, Envío Nube management, tracking, and incidents: <https://ayuda.tiendanube.com/es_AR/ventas>, <https://ayuda.tiendanube.com/es_AR/medios-de-pago>, <https://ayuda.tiendanube.com/es_AR/envios-y-locales>, <https://ayuda.tiendanube.com/es_AR/envio-nube-gestion-de-envios>, <https://ayuda.tiendanube.com/es_AR/envio-nube-seguimiento>, <https://ayuda.tiendanube.com/es_AR/envio-nube-incidencias>
- Prior platform intelligence notes that Tiendanube shipping visibility depends on carrier integration quality and does **not** reliably expose granular movement like “in transit” vs “out for delivery” for every store/provider: `2026-05-30-tiendanube-platform-intelligence.md`.
- Tiendanube app categories reinforce fragmented shipping/tracking tooling rather than one case-native control layer: <https://www.tiendanube.com/tienda-aplicaciones-nube>, <https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/envios>, <https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/gestion>
- Adjacent shipping/tracking tools already own label execution and shipment visibility, e.g. AfterShip and ShipStation, while Orvo’s opportunity is the owner/operator case layer above them: <https://apps.shopify.com/aftership>, <https://apps.shopify.com/shipstation>
- Helpdesk and WhatsApp tools already absorb WISMO conversations after the customer asks, but their native object is the chat/ticket rather than the internal operating case: <https://www.gorgias.com/>, <https://www.zoko.io/>, <https://www.wati.io/>, <https://www.kommo.com/>

## Why this slice matters

WISMO is one of the clearest symptoms that a store has moved from “ops inconvenience” to “customer-visible failure.” But it sits at the boundary of three different categories:

- **fulfillment ops**: was the order dispatched at all?
- **carrier/tracking visibility**: is the shipment moving after dispatch?
- **support/inbox**: how many customers are already asking where it is?

That boundary matters because Orvo already has a clean first wedge for the first category (`fulfillment_backlog`) and a possible later wedge for the third (`unanswered_conversations`). The middle category is attractive, but much riskier to claim from Tiendanube alone.

The commercial lesson: WISMO is a **qualification and expansion signal** before it is a default product promise.

## ICP refinement

Add a carrier-visibility overlay to qualification for merchants already showing fulfillment or WhatsApp pain.

| Signal | Fit impact | Sales action |
|---|---:|---|
| Merchant gets frequent “¿dónde está mi pedido?” messages after orders are already marked dispatched | +7 | Strong pain; ask where movement truth actually lives. |
| Uses Envío Nube or a shipping aggregator and reviews tracking/incidents daily | +5 | Candidate for readiness audit. |
| Has one or two dominant carriers with consistent status semantics | +5 | Better fit than mixed long-tail carriers. |
| Support team escalates WISMO to ops every day or every peak week | +6 | Pair with `fulfillment_backlog` and conversation-readiness discovery. |
| Tiendanube marks orders as shipped but real movement only exists in carrier/ERP tools | +4 | Orvo may fit later via second source; do not sell from Tiendanube-only data. |
| Manual deliveries, local pickup, custom products, or highly irregular logistics dominate | -5 | Keep to fulfillment readiness only. |
| No stable shipment ID / tracking number / carrier event history is available | hard disqualifier | No deterministic no-movement claim possible. |
| Buyer wants automatic replies, delivery promises, or proactive customer notifications | -6 | Redirect to tracking/helpdesk tools; Orvo can coexist later. |

## Packaging recommendation

Do not bundle post-dispatch no-movement monitoring into Starter. Treat it as a readiness lane first, then a higher-trust expansion.

| Package | WISMO / carrier-visibility stance | Rationale |
|---|---|---|
| Health Check | Ask WISMO volume and source-of-truth questions only | Qualifies pain without promising shipment intelligence. |
| Activation Sprint — USD 149 / 30 days | Carrier/source audit: where dispatch truth ends and movement truth begins | Prevents false “shipment stuck” claims. |
| Starter — USD 79-99/mo | Not included; use `fulfillment_backlog` and `data_stale` only | Keep Starter on Tiendanube truth, not weak carrier inference. |
| Growth — USD 199/mo | Optional internal/operator-facing no-movement review when one trusted movement source is available | Adds workflow depth without promising support automation. |
| Scale/Agency — USD 399+/mo or custom | Owner-facing multi-carrier movement-risk briefs and escalation views after truth gates pass | Requires stronger source contracts, redaction, and resolver workflows. |

Upsell language:

> “Starter te ayuda antes del despacho. Growth puede sumar riesgo post-despacho, pero solo si el tracking realmente permite demostrar movimiento o falta de movimiento.”

## Carrier-truth gates

Before any owner-facing “shipment not moving” claim, require all gates below.

1. **Dispatch boundary gate:** Orvo can separate “paid but not dispatched” from “already dispatched.” If not, stay in `fulfillment_backlog` only.
2. **Movement-source gate:** a trusted source exists for carrier movement events — Envío Nube detail, shipping aggregator, carrier feed, ERP, or another connector with stable shipment refs.
3. **Shipment-ID gate:** order, shipment, and tracking identifiers can be matched safely enough to compute no-movement without exposing raw customer PII.
4. **Status-semantics gate:** merchant/provider semantics are known: created label, handed to carrier, first scan, in transit, out for delivery, delivered, failed attempt, returned, incident, etc.
5. **Latency gate:** acceptable carrier lag is defined. A missing scan for 6 hours is very different from 48 hours depending on carrier and route.
6. **Exception-SLA gate:** merchant defines what counts as a problem, e.g. “despachado + 48h sin primer movimiento” or “incidencia abierta sin actualización > 24h.”
7. **Exclusion gate:** local pickup, same-day local delivery, manual messenger, preorder, wholesale, and test flows are excluded or separately thresholded.
8. **Resolver gate:** a named person/team can investigate with carrier/support/warehouse and close the follow-up.
9. **Freshness gate:** if carrier/tracking data is stale or partially synced, suppress the claim and create/update `data_stale` or setup-required operator context.
10. **No-customer-message gate:** Orvo does not send delivery promises, apology messages, refund offers, or tracking replies to customers in the first implementation.

If a gate fails, Orvo should say:

> “Podemos ver el despacho, pero todavía no podemos afirmar si el envío dejó de moverse. Primero necesitamos una fuente confiable de tracking y una regla clara de cuándo eso se considera incidente.”

## Competitor gap to position

| Existing category | What buyer already gets | Gap Orvo should own |
|---|---|---|
| Tiendanube admin / Envío Nube views | order state, shipment/tracking screens, incidents | Pull-based inspection; owner/operator must remember to check. |
| AfterShip / ShipStation / shipping tools | labels, tracking pages, carrier notifications, shipment ops | Execution and visibility, but not a cross-tool operational case queue for owner attention. |
| Helpdesks / WhatsApp inboxes | WISMO conversations, macros, support workflows | They react after the customer asks; they do not prove which shipping issue should become today’s ops case. |
| ERP / OMS / sync systems | source-of-record logistics/admin data | They store facts; Orvo should decide when those facts become governed operational follow-up. |
| Manual WhatsApp + screenshot coordination | ad hoc escalation between support and ops | No dedupe, no freshness caveats, no weekly proof, no case memory. |

Positioning line:

> “El tracking te muestra paquetes. Orvo te muestra cuándo un problema de tracking merece seguimiento operativo hasta resolverse.”

## Sales discovery questions

Use these before promising post-dispatch monitoring:

1. “Cuando un cliente pregunta ‘¿dónde está mi pedido?’, ¿el problema suele ser que no salió o que salió y no se mueve?”
2. “¿Dónde vive hoy la verdad del tracking: Tiendanube, Envío Nube, carrier, ERP, planilla, otro?”
3. “¿Qué evento consideran ‘movimiento real’: etiqueta creada, primer escaneo, en tránsito, visita fallida?”
4. “¿Con qué carriers trabajan más y cambian mucho las semánticas entre ellos?”
5. “¿Cuánto tiempo sin actualización consideran normal vs problema?”
6. “¿Quién toma la posta cuando hay una incidencia: soporte, logística, dueño, agencia?”
7. “¿Qué datos nunca deberían aparecer en un brief interno de WhatsApp sobre envíos?”

## Product and governance guardrails

- Do not invent a new owner-facing case family for post-dispatch risk until carrier-source truth, evidence refs, dedupe, and suppression behavior are specified.
- Tiendanube-only shipment fields are sufficient for some fulfillment readiness work, but not for generic “package stuck” or “delivery risk” promises.
- WISMO pressure is a strong ICP signal even when Orvo cannot yet automate the detection.
- Keep customer messaging, refund handling, and delivery promises out of scope; Orvo’s job is internal operational visibility and follow-up.
- When carrier truth is missing, prefer `data_stale`, setup-required context, or internal-only review over false precision.
- Weekly proof should count incidents detected, acknowledged, and resolved — not chats answered or notifications sent.

## Bottom line

WISMO is real buyer pain, but it should **not** be sold as a Tiendanube-only default feature. Orvo should first own the safer categories around it: verified `fulfillment_backlog`, `data_stale`, and later conversation readiness. Then it can expand into post-dispatch shipment-risk monitoring only where a carrier-grade movement source exists. That keeps Orvo positioned as an operations control plane — not a tracking app, helpdesk, or chatbot.