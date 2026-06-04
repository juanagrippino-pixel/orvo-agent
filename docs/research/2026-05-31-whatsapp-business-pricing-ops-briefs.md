# WhatsApp Business Pricing Implications for Orvo Ops Briefs

Date: 2026-05-31  
Status: Market Research — bounded pricing/packaging slice  
Prior research checked: `2026-05-30-whatsapp-first-operations.md`, `2026-05-30-pricing-intelligence.md`, `2026-05-30-competitor-gap-analysis.md`

## Why this slice matters

Orvo's first customer-facing surface is a proactive WhatsApp operations brief. Meta's current WhatsApp Business Platform model makes this commercially viable, but only if Orvo treats WhatsApp as a governed projection layer: approved utility templates for scheduled/outbound briefs, free-form service messages only inside the 24-hour customer service window, and strict volume controls to avoid alert spam.

## Evidence from current WhatsApp Business Platform pricing

Sources checked 2026-05-31:

- Meta WhatsApp pricing documentation, updated May 21, 2026: <https://developers.facebook.com/docs/whatsapp/pricing/>
- Meta service messages / customer service window documentation, updated May 21, 2026: <https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages/>
- Meta rate cards linked from the pricing page, effective April 1, 2026.

Key rules from Meta docs:

1. Since July 1, 2025, Meta charges WhatsApp Business Platform on a **per-delivered-template-message** basis.
2. Non-template messages are free, but can only be sent inside an open **24-hour customer service window** after the user messages or calls the business.
3. To message users outside that window, businesses must use pre-approved templates.
4. Template categories are **Marketing**, **Utility**, and **Authentication**; rates vary by recipient country.
5. Utility templates delivered inside an open customer service window are free.
6. All messages are free for 72 hours if sent within an eligible free entry point window.

## Rate snapshot relevant to Orvo

Meta USD rate card effective April 1, 2026:

| Recipient market | Marketing | Utility | Authentication | Orvo relevance |
|---|---:|---:|---:|---|
| Argentina | USD 0.0618 | USD 0.0260 | USD 0.0260 | Primary wedge market; utility brief is materially cheaper than marketing. |
| Mexico | USD 0.0305 | USD 0.0085 | USD 0.0085 | Expansion market has lower WhatsApp COGS than AR. |
| Colombia | USD 0.0125 | USD 0.0008 | USD 0.0008 | Very low COGS; pricing should not be message-cost anchored. |
| Brazil | USD 0.0625 | USD 0.0068 | USD 0.0068 | Nuvemshop path has low utility COGS despite high marketing rate. |
| Rest of Latin America | USD 0.0740 | USD 0.0113 | USD 0.0113 | Still low enough for included daily briefs. |

Meta ARS rate card effective April 1, 2026:

| Recipient market | Marketing | Utility | Authentication |
|---|---:|---:|---:|
| Argentina | ARS 89.5620 | ARS 37.6798 | ARS 37.6798 |

## Orvo unit-economics estimate for Argentina

Assumption: one scheduled daily Orvo operations brief, sent as a utility template outside the 24-hour customer service window.

| Usage pattern | Monthly Meta utility COGS | % of USD 79 Starter |
|---|---:|---:|
| 1 recipient × 30 days | USD 0.78 | 0.99% |
| 3 recipients × 30 days | USD 2.34 | 2.96% |
| 5 recipients × 30 days | USD 3.90 | 4.94% |
| 1 recipient × 2 daily sends × 30 days | USD 1.56 | 1.97% |

If incorrectly classified/implemented as marketing, the same daily brief costs USD 1.854/month per Argentina recipient, or USD 9.27/month for 5 recipients. That is still not fatal, but it weakens margin and may create policy/category risk.

## Product and packaging implications

### 1. Classify the Orvo brief as Utility, not Marketing

The scheduled brief should be framed and templated as an operational/account update: open cases, data freshness, stock risk, fulfillment backlog, and required actions. Avoid promo language, upsells, or engagement bait inside the operational template.

**Action:** create a small template taxonomy before launch:

| Template | Category target | Purpose |
|---|---|---|
| `daily_ops_brief` | Utility | Morning operational cases and evidence summary. |
| `case_action_confirmation` | Utility or service message when CSW open | Confirm ack/resolved/follow-up actions. |
| `data_stale_urgent` | Utility | Connector/source-health incident. |
| `billing_or_trial_notice` | Utility | Account/payment/trial status. |
| `feature_announcement` | Marketing | Only for explicit marketing opt-in; not part of core ops loop. |

### 2. Include daily WhatsApp delivery in Starter; do not nickel-and-dime per message

At Argentina utility rates, a one-recipient daily brief is under USD 1/month. Even 3 recipients remain around USD 2.34/month. Charging per message would add friction without meaningful margin benefit.

**Packaging recommendation:**

- Starter: include 1 store, 1 daily brief, up to 3 WhatsApp recipients, and reply-based actions.
- Growth: include more recipients/check frequencies, but still cap alert volume.
- Custom: charge for high-frequency, multi-store, or agency fan-out where WhatsApp COGS and support load become real.

### 3. Batch cases into one daily template; avoid per-case alert spam

Because every outbound template delivery can incur a charge, Orvo should not send one WhatsApp template per case by default. The best unit is a consolidated daily or exception digest with top cases, stale-data state, and a link to the operator surface.

**Product guardrail:** default max one scheduled template/day/store, plus narrowly scoped urgent templates for source-health or severe cases. More detail should be pulled by user reply or opened in the operator surface.

### 4. Use the 24-hour service window for low-cost interaction, not proactive chatter

When a merchant replies `OK`, `Ver 1`, `Resuelto`, or asks for details, that opens/resets the 24-hour customer service window. Orvo can then use free-form service messages for confirmations, detail drilldowns, and follow-up prompts.

**Workflow implication:**

- Outbound morning brief: utility template.
- Merchant reply: registered action, audit event, opens CSW.
- Orvo confirmation/detail: service message when CSW is open.
- If no CSW is open: send only approved utility templates or deep-link to operator surface.

### 5. Build pricing safety into platform contracts

WhatsApp costs are low enough for GTM, but category, country, and delivery outcomes must be auditable. Do not hide WhatsApp delivery behind ad hoc dispatcher behavior.

**Required internal state:**

- recipient country / phone prefix for rate estimation;
- template name and intended category;
- delivery status and provider message id;
- whether the message used template vs service mode;
- whether a customer service window was open;
- current rate-card version used for COGS estimation.

## ICP signal

WhatsApp COGS does **not** constrain the Tiendanube merchant ICP. The stronger segmentation signals remain operational complexity: multiple daily manual checks, SKU/variant risk, fulfillment or stale-data incidents, and owner/team coordination over WhatsApp. A store that cannot justify USD 79/month will not be saved by cheaper messaging; a store with real operational pain should accept WhatsApp delivery as included table stakes.

## Open risks

- Meta can reclassify or reject templates; Orvo needs backup email/operator-surface delivery during template approval incidents.
- Utility-vs-marketing boundaries depend on template content; keep sales, upgrade prompts, and generic engagement out of ops templates.
- BSPs/Twilio/360dialog may add markup or monthly phone fees beyond Meta's rate card; validate before final COGS model.
- User opt-in, quiet hours, and unsubscribe handling must be treated as launch requirements, not later compliance polish.
