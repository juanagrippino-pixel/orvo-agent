# Unanswered WhatsApp Conversations — Readiness-Gated Case for Tiendanube Stores

Date: 2026-06-10  
Status: Market Research — bounded WhatsApp-first workflow / competitor / ICP / packaging slice  
Prior research checked: `2026-05-30-whatsapp-first-operations.md`, `2026-05-31-whatsapp-business-pricing-ops-briefs.md`, `2026-05-30-competitor-gap-analysis.md`, `2026-05-30-pricing-intelligence.md`, `2026-06-03-whatsapp-recipient-topology-governance.md`, `docs/specs/d2c-case-family-catalog.md`  
Scope note: this cron environment did not expose live web-search tooling, so this run uses the repo's existing web-sourced research corpus and public links already captured in-repo; refresh source pages before quoting externally.

## Bounded question

Should Orvo sell `unanswered_conversations` for WhatsApp-heavy Tiendanube merchants, and how should it be positioned without becoming a WhatsApp inbox, helpdesk, chatbot, or message-sending product?

## Short answer

Yes, but **not as a first-pilot default and not as a Starter promise**. `unanswered_conversations` is commercially attractive because slow WhatsApp replies leak sales and trigger post-purchase complaints, but it is integration- and privacy-sensitive. Orvo should package it as a **Growth readiness-gated case** only for merchants already using a structured WhatsApp inbox/API source, or as an Activation Sprint audit when the merchant still operates from personal phones.

Recommended buyer-facing phrasing:

> “Orvo no reemplaza tu WhatsApp ni responde por vos. Si tu inbox permite medirlo, Orvo avisa cuando se acumulan conversaciones sin respuesta y quién debería revisarlas, con evidencia mínima y sin exponer datos del cliente.”

## Evidence base and source links

Public/source links represented in prior corpus:

- Tiendanube/NubeCommerce and Tiendanube WhatsApp education validate WhatsApp as a normal Argentine/LatAm seller channel; prior research cites 71.5% of Argentine entrepreneurs using WhatsApp as a sales channel in 2025: <https://site.tiendanube.com/recursos/nubecommerce>, <https://www.tiendanube.com/blog/como-vender-por-whatsapp/>, <https://www.tiendanube.com/blog/whatsapp-business/>
- Tiendanube offers Chat Nube / chat-oriented selling surfaces, reinforcing that merchants already expect WhatsApp/chat tooling but not necessarily operational case governance: <https://www.tiendanube.com/soluciones/chat-nube>, <https://www.tiendanube.com/tienda-aplicaciones-nube>
- Meta WhatsApp Business Platform rules matter because business-initiated messages need approved templates outside the 24-hour service window and utility messaging must avoid marketing content: <https://developers.facebook.com/docs/whatsapp/pricing/>, <https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages/>
- Adjacent WhatsApp/inbox competitors in prior corpus include Zoko, WATI, Kommo, Manychat, Zenvia, and Tiendanube-native chatbots; they manage conversations or messaging infrastructure, not Tiendanube operational case state: <https://www.zoko.io/>, <https://www.wati.io/>, <https://www.kommo.com/>, <https://manychat.com/>, <https://www.zenvia.com/>
- The D2C case catalog defines `unanswered_conversations` with required metrics: unanswered count, oldest unanswered age, channel/team scope, freshness, safe conversation refs, and deterministic dedupe (`docs/specs/d2c-case-family-catalog.md`).

## Why this slice matters

WhatsApp response backlog is one of the most intuitive buyer pains in LatAm D2C: every merchant understands that a question left unanswered can become a lost order or angry customer. It is also one of the easiest places for Orvo to be miscategorized.

If sold incorrectly, buyers will expect:

- a shared inbox;
- automated AI replies;
- broadcast/campaign tooling;
- sentiment classification;
- customer service macros;
- order-level customer support history.

Those are not Orvo’s category. Orvo’s category is an **operations control plane**: detect that the team has an attention backlog, create/update a governed case, show minimal evidence, and keep follow-up state outside WhatsApp.

## ICP refinement

Add a conversation-readiness overlay only after the core Tiendanube ICP is strong.

| Signal | Fit impact | Sales action |
|---|---:|---|
| WhatsApp is a meaningful sales/support channel, not just a contact link | +6 | Ask volume and response-time questions early. |
| Merchant receives 20+ WhatsApp conversations/day or clear rush-hour backlogs | +6 | Position as Growth case after source audit. |
| Uses structured inbox/API tool such as WATI, Zoko, Zenvia, Kommo, Manychat, respond.io, or similar | +7 | Candidate for deterministic backlog metrics. |
| Owner/operator already reviews “pendientes” each morning | +5 | Tie Orvo to replacing manual inbox scan. |
| Post-purchase WISMO / “¿dónde está mi pedido?” messages create pressure | +4 | Pair with `fulfillment_backlog`; do not inspect message content unless scoped. |
| Personal WhatsApp phone only, no export/API, no shared inbox | -7 | Sell readiness audit or defer; do not promise monitoring. |
| Buyer mainly wants a chatbot to answer customers | -6 | Redirect to chatbot/inbox tools; Orvo can coexist later. |
| No SLA threshold for what counts as “unanswered too long” | -4 | Require setup before owner-facing alerts. |
| No named resolver for pending conversations | hard disqualifier | Alerts will become guilt/noise, not action. |

## Packaging recommendation

Do not bundle `unanswered_conversations` into the first Starter package. The variability of WhatsApp sources, permissions, PII, and response-state semantics makes it a poor low-touch feature.

| Package | Conversation-backlog stance | Rationale |
|---|---|---|
| Health Check | Ask about WhatsApp workflow; no monitoring claim | Qualifies pain without needing customer-message access. |
| Activation Sprint — USD 149 / 30 days | Optional inbox/source readiness audit and manual baseline | Useful discovery if WhatsApp pain is high. |
| Starter — USD 79-99/mo | Not included; daily Orvo brief still delivered through WhatsApp | Keep Starter focused on Tiendanube truth and avoid helpdesk expectations. |
| Growth — USD 199/mo | Include one approved conversation source only after truth gates pass | Justifies workflow depth and second-source integration. |
| Scale/Agency — USD 399+/mo or custom | Multi-inbox, team scopes, SLA variants, agency/owner proof views | Requires roles, permissions, privacy review, and support scope. |

Upsell language:

> “Starter te avisa qué pasa en Tiendanube. Growth puede sumar si tu WhatsApp/inbox se está acumulando sin respuesta, siempre que la fuente permita medirlo bien.”

## Activation truth gates

Before projecting `unanswered_conversations` to WhatsApp or owner-facing surfaces, require all gates below.

1. **Source gate:** a structured inbox/API/export can provide conversation status, last inbound timestamp, last outbound timestamp, assignment/team scope, and stable conversation refs.
2. **Freshness gate:** the conversation source sync is fresh; otherwise create/update `data_stale` and suppress backlog claims.
3. **Scope gate:** define which channels count: sales, post-purchase support, Instagram/WhatsApp combined inbox, bot handoff, etc.
4. **SLA gate:** merchant defines thresholds, e.g. “oldest unanswered > 2h during business hours” or “more than 10 unanswered chats by 10:00.”
5. **Business-hours gate:** silence or adjust alerts outside configured hours/weekends unless merchant explicitly wants after-hours visibility.
6. **PII/redaction gate:** owner-facing brief uses counts, age, channel/team, and safe refs only; no raw message text, phone numbers, names, addresses, or sensitive customer data in WhatsApp briefs.
7. **Resolver gate:** named human/team can act on the backlog and mark follow-up.
8. **No-auto-reply gate:** Orvo does not answer customers, send macros, promise delivery status, or mutate support tickets in first implementation.
9. **No-LLM-classification gate:** do not use an LLM to decide whether a conversation is unanswered, urgent, angry, or sales-related unless deterministic source labels already exist and are evidenced.

If any gate fails, Orvo should say:

> “Todavía no podemos medir conversaciones sin responder con seguridad. Primero necesitamos una fuente/inbox confiable, horarios y una regla clara de qué cuenta como pendiente.”

## Competitor gap to position

| Existing category | What buyer already gets | Gap Orvo should own |
|---|---|---|
| WhatsApp Business app | phone-based messaging, labels, basic small-team workflow | No governed operational case lifecycle, source freshness, or cross-Tiendanube evidence. |
| Zoko / WATI / Kommo / respond.io / similar inbox tools | shared inbox, automation, assignments, broadcasts, sometimes analytics | They manage the conversation; Orvo decides when backlog is an operational case and links it to store context. |
| Manychat / chatbot tools | flows, FAQs, lead capture, automations | Conversation automation, not deterministic operations control. |
| Helpdesks like Zendesk/Gorgias | ticket SLAs, macros, agent workflows | Support-ticket lifecycle, not Tiendanube-first operations cases. |
| Manual owner review | screenshots and “¿quién responde?” follow-up | No dedupe, no evidence, no weekly proof, no history of unresolved ops cases. |

Positioning line:

> “No somos tu inbox. Orvo mira si el inbox se convirtió en un problema operativo y lo mantiene como caso hasta que alguien lo atienda.”

## Sales discovery questions

Use these before promising conversation-backlog monitoring:

1. “¿Cuántas conversaciones de WhatsApp entran por día en promedio y en picos?”
2. “¿Qué cuenta como ‘sin responder’: cliente nuevo, post-compra, bot derivado a humano, mensaje fuera de horario?”
3. “¿Hoy usan WhatsApp Business en un teléfono, un inbox compartido o una plataforma con API?”
4. “¿Quién revisa pendientes cada mañana y qué pasa si nadie responde?”
5. “¿Cuánto tiempo puede pasar una consulta sin respuesta antes de que sea problema?”
6. “¿Quieren medir ventas perdidas por demora o solo asegurar que no queden chats colgados?”
7. “¿Qué datos de clientes NO quieren que aparezcan en un brief de WhatsApp interno?”

## Product and governance guardrails

- `unanswered_conversations` must remain a deterministic Operational Case with evidence, dedupe, lifecycle, redacted refs, and freshness caveats.
- WhatsApp delivery of the Orvo brief is separate from WhatsApp conversation ingestion; do not mix the two concepts in sales copy.
- Do not store raw message bodies unless a future privacy-reviewed connector scope explicitly requires it; counts/ages/status metadata are enough for the first case.
- Do not send customer replies, delivery promises, refunds, coupons, or macros from Orvo in the first implementation.
- Do not let the WhatsApp/inbox tool become the system of record for Orvo case state; Orvo cases remain authoritative.
- Weekly proof should count backlog cases opened/acknowledged/resolved and average oldest-age improvement, not “messages automated.”

## Bottom line

`unanswered_conversations` is a strong **Growth-level expansion case** for WhatsApp-heavy Tiendanube merchants, but only when a structured inbox source can prove unanswered count and age safely. Sell it as attention-backlog monitoring, not inbox management or chatbot automation. For the first paid pilots, qualify the pain and readiness, but keep owner-facing alerts gated behind source, freshness, SLA, business-hours, PII/redaction, resolver, no-auto-reply, and no-LLM-classification gates.
