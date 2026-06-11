# La Pyme benchmark for Orvo

Source checked: https://www.lapyme.com.ar/ and pricing/API docs on 2026-06-11.

## What La Pyme is positioning as

La Pyme is not a chatbot. It is positioned as **"el sistema operativo de tu pyme"** for Argentine SMBs.

Core promise:
- one system for sales, stock, ARCA invoicing, treasury, accounting, purchases, reports, and ecommerce integrations;
- simple day-to-day operation with depth as the business grows;
- AI/assistant layer over real operational data.

## Product surface observed

- Ecommerce/POS channels: Mercado Libre, Tiendanube, Shopify, WooCommerce, local POS.
- Sales become real operational records: invoice, stock sync, payment/treasury record.
- Purchases: upload supplier invoice PDF; AI extracts lines/taxes/totals; user approves; stock/cost/accounting evidence updated.
- Operations: workflows advance from state derived from reality, not manual stage clicks.
- Reports: drill-down numbers by channel/vendor/product, exportable.
- AI assistants: Claude/ChatGPT/Grok connector can query real data and create drafts/actions under permissions.
- API: customers, suppliers, products, inventory, purchases, sales, collections, payments, reports, config.

## Public stack signal from Tomas Malamud / La Pyme repost

Reported stack from 2025:
- Next.js: frontend + backend.
- Supabase: Auth, DB, storage.
- Trigger.dev: background jobs.
- Vercel: hosting, observability, firewall, DNS, infra.
- Resend: transactional + marketing email.
- Ultracite: linter/formatter.
- afipsdk: ARCA integration.
- AI SDK: upcoming AI features.

Technical interpretation for Orvo:
- The stack is solid for a web-first SaaS ERP/control panel.
- It validates that La Pyme is a real SaaS product with modern infra, not a simple no-code/bot wrapper.
- Orvo should copy the **product operating-system direction**, not immediately migrate the current Python/Hermes control-plane core.
- Keep Orvo's deterministic runtime in Python for now; introducing a full Next/Supabase/Vercel rewrite before MVP would slow execution.
- Consider borrowing selectively:
  - Next.js/Vercel for future operator/admin surface.
  - Resend for lifecycle/customer emails.
  - afipsdk for ARCA once the wedge reaches invoicing/accounting.
  - Trigger.dev only if current scheduler/job orchestration becomes a bottleneck.
  - AI SDK only for UI assistant surfaces, not for metric/state generation.

## Pricing signal

Public monthly plans:
- Starter: ARS 81,900/mo list, 50% off first 3 months.
- Pro: ARS 163,900/mo list, 50% off first 3 months.
- Max: ARS 269,900/mo list, 50% off first 3 months.

This is evidence that Argentine SMBs can be sold an operating-system category if it bundles painful local workflows: ARCA, stock, ecommerce, treasury/accounting, support/migration.

## Implications for Orvo

The user explicitly said Orvo should be closer to what La Pyme does.

Recommended interpretation:
- Keep Orvo's long-term thesis as an **operating system / control plane for Argentine PyMEs**, not a generic chatbot.
- La Pyme validates the category language and operational breadth.
- Orvo should not blindly build a full ERP first. The fastest MVP wedge remains a narrower operational control plane for D2C/Tiendanube/WhatsApp-first stores, but it should look and feel like an operating system, not a report bot.

## Orvo differentiation to preserve

- Operational Cases / exception desk: detect stale data, missed revenue, stock/action issues, WhatsApp follow-up needs.
- Deterministic runtime/ledger/evidence: reports and assistant copy are projections, not source of truth.
- WhatsApp/operator-first workflow: daily concise actions for owners/operators.
- AI as an interface over real data and governed actions, not the owner of metrics or state transitions.

## Product direction adjustment

Use La Pyme as the product benchmark:

1. **North star:** Orvo is an AI-native operating/control plane for Argentine commerce PyMEs.
2. **Initial wedge:** D2C ecommerce operators using Tiendanube/WhatsApp/Mercado Pago-like workflows.
3. **MVP must show:** sales/orders, stock/data freshness, cases, actions, report projection, and governed assistant-style querying.
4. **Later expansion:** ARCA invoicing, supplier purchases, treasury/accounting, multi-channel POS/ecommerce.
5. **Do not frame as:** chatbot, generic agent platform, dashboard-only analytics, or report generator.

## Worker guidance

Autonomous workers should use La Pyme as a product/positioning benchmark, but should still respect Orvo platform contracts:
- connector registry;
- compiled runtime;
- run ledger;
- metric registry/evidence;
- Operational Cases;
- audited actions;
- tenant secret redaction.

If a feature can be copied only by bypassing those contracts, do not copy it yet. Build the platform-safe slice.
