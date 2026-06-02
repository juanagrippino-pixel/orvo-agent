# Composio / integration tooling evaluation for Orvo

Status: Research note / recommendation
Date: 2026-06-02
Owner: Hermes research pass
Scope: Evaluate whether Composio or adjacent integration tooling should be used for Orvo's D2C ecommerce control plane and paid-pilot execution.

## Executive verdict

Composio is useful for Orvo, but only as an **integration accelerator for authenticated third-party actions**, not as the core Orvo platform.

Recommended stance:

1. Orvo should keep owning the control-plane primitives: tenant policy, RBAC, approvals, run ledger, case/evidence store, idempotency, redaction, and audit trails.
2. Composio can be evaluated as a connector/action layer for long-tail SaaS tools such as Google Sheets, Gmail, Slack, HubSpot, Notion, Linear, GitHub, Zendesk/Intercom/Gorgias, Google Ads, Meta Ads, Shopify, and WhatsApp.
3. Composio should **not** replace Orvo-owned Tiendanube/WhatsApp/Meta Cloud API paths until coverage, latency, scopes, delivery-status semantics, and auditability are proven.
4. Because Tiendanube and MercadoLibre were not found in Composio's public toolkit catalog during this pass, Orvo still needs first-party connectors or another provider for those core Latin American ecommerce sources.
5. Pipedream Connect deserves a parallel benchmark because it publicly exposes Tiendanube and WhatsApp Business app pages and may be a better first test for Orvo's immediate paid-pilot wedge.

In short: **yes to a bounded spike, no to delegating core product semantics.**

## What Composio is

Composio describes itself as a tool/integration layer for AI agents. Its public docs state that it powers 1000+ toolkits, tool search, context management, authentication, and a sandboxed workbench for agents that turn user intent into external actions.

Primary integration model:

- Create a runtime session per user, e.g. `composio.create(user_id="user_123")`.
- Use either:
  - native tools via `session.tools()` for supported model/framework packages; or
  - a remote MCP URL via `session.mcp.url` for MCP-compatible clients.
- The session defines whose connected accounts are used, which tools are available, auth behavior, logs, memory/state, MCP state, and workbench files.

Public docs emphasize two modes:

- **Native tools:** more control over schemas, logs, retries, approvals, and provider-specific tool execution.
- **MCP:** easier client compatibility; expose a remote MCP server URL with session-scoped tools.

Relevant sources:

- <https://docs.composio.dev/llms.txt>
- <https://docs.composio.dev/docs/how-composio-works.md>
- <https://docs.composio.dev/docs/native-tools-vs-mcp.md>

## Features relevant to Orvo

### 1. Managed auth and Connect Links

Composio supports hosted auth flows / Connect Links so users can connect external accounts without Orvo implementing every OAuth flow upfront. It also supports managed OAuth apps for many providers and custom auth configs for production use.

Useful for Orvo:

- faster onboarding for non-core SaaS accounts;
- user/tenant-scoped connected accounts;
- multi-account support for operators or agencies;
- less initial work for OAuth refresh/token storage.

Caution:

- customer-facing production probably needs custom OAuth apps, not Composio-branded consent screens;
- scopes must be minimized per action;
- Orvo must support revocation/deletion and not rely only on vendor defaults;
- Composio-managed auth is not a substitute for Orvo's tenant policy model.

Sources:

- <https://docs.composio.dev/docs/authentication.md>
- <https://docs.composio.dev/toolkits/managed-auth.md>
- <https://docs.composio.dev/docs/custom-app-vs-managed-app.md>
- <https://docs.composio.dev/docs/white-labeling-authentication.md>

### 2. Large tool catalog

The public toolkit catalog lists 1000 toolkits. During this pass, relevant entries included:

| Toolkit | Public catalog notes | Orvo relevance |
|---|---:|---|
| Google Sheets | 52 tools / 16 triggers / OAuth2 / managed app yes | Concierge onboarding, customer sheets, pilot ops |
| Gmail | listed with OAuth/managed auth | inbound exceptions, support/customer context, ops summaries |
| Slack | 150 tools / 8 triggers / OAuth2 / managed app yes | internal alerts, agency/operator channels |
| GitHub | large action surface | engineering automation, not customer-facing Orvo core |
| Linear | listed with OAuth/API key | internal issue workflows |
| HubSpot | 233 tools / 2 triggers / OAuth2/API key / managed app yes | CRM/account ops for future GTM |
| Notion | listed with OAuth/API key | customer notes, internal docs |
| WhatsApp | 17 tools / 1 trigger / OAuth2/API key / managed app yes | must verify depth; likely not enough alone for Orvo Meta Cloud delivery semantics |
| Meta Ads | 52 tools / OAuth2/API key / managed app no in catalog | future `spend_without_orders` expansion; verify auth/docs |
| Google Ads | listed | paid media expansion |
| Shopify | 394 tools / API key/OAuth2/S2S OAuth2 / managed app no in catalog | useful outside Tiendanube; not first wedge |
| Zendesk / Intercom / Gorgias | listed | support operations expansion |

Critical gap found:

- No `Tiendanube`, `Nuvemshop`, or `MercadoLibre` matches were found in the public Composio `toolkits.md` during this pass.

Source:

- <https://docs.composio.dev/toolkits.md>

### 3. MCP support

Composio exposes session-scoped remote MCP URLs. This matters because Hermes Agent has native MCP support, so Orvo/Hermes could potentially call Composio tools through MCP after configuring an MCP server URL and headers.

For Hermes specifically, native MCP servers are configured in `~/.hermes/config.yaml` under `mcp_servers`, either as stdio or HTTP/StreamableHTTP. Any Composio MCP use should be configured with tight tool allowlists, timeouts, and credential isolation.

Orvo usage pattern:

```text
Hermes/Orvo worker -> Orvo policy wrapper -> Composio session MCP/native tool -> external SaaS
                 -> Orvo run ledger/evidence/action audit <- normalized result
```

Do not allow agent-selected arbitrary Composio tools in production. Preload/allowlist the exact tools needed per workflow.

Sources:

- <https://docs.composio.dev/docs/native-tools-vs-mcp.md>
- <https://docs.composio.dev/reference/sdk-reference/python/mcp.md>

### 4. Workbench, triggers, proxy execute, observability

Composio also has:

- workbench/sandbox for Python/data manipulation and multi-step workflows;
- triggers/webhooks/polling for supported apps;
- proxy execute for authenticated API calls not covered by a named tool;
- logs/usage APIs for observability.

These are potentially useful for early Orvo operators and internal GTM workflows, but risky as production core unless Orvo wraps them.

Orvo should treat Composio logs as a vendor-side diagnostic stream, not the canonical audit ledger.

Sources:

- <https://docs.composio.dev/docs/workbench.md>
- <https://docs.composio.dev/docs/triggers.md>
- <https://docs.composio.dev/docs/proxy-execute.md>
- <https://docs.composio.dev/docs/observability.md>

## Pricing / limits found

Public pricing page found these tiers at research time:

- Free: 20K tool calls/month.
- Paid low tier: 200K tool calls/month at $29/month, with additional-call pricing.
- Business tier: 2M tool calls/month at $229/month, with additional-call pricing.
- Enterprise: custom, with SLA / compliance / VPC/on-prem claims.

Premium tools may cost more than standard tools. Public docs also mention rate limits and premium-tool limits; plan names differ somewhat across pricing/rate-limit pages, so contractual terms should be verified before production use.

Sources:

- <https://composio.dev/pricing>
- <https://docs.composio.dev/toolkits/premium-tools.md>
- <https://docs.composio.dev/reference/rate-limits.md>

## Security / compliance concerns

Composio would sit on a sensitive boundary: it can hold OAuth credentials and execute external actions. For Orvo, this creates product and compliance requirements.

Before any customer-facing use, ask for or verify:

- DPA and subprocessors;
- SOC 2 / ISO report, not only marketing claims;
- retention and deletion semantics for sessions, logs, workbench files, and connected-account data;
- data residency options;
- how OAuth tokens are stored, encrypted, rotated, revoked, and scoped;
- whether Composio can support per-tenant / per-action allowlists;
- whether enterprise supports VPC/on-prem if Orvo later needs it;
- signed webhook verification;
- guarantees around no use of customer data for model training.

Specific implementation guardrails:

- never use a shared/default user id in production;
- create one Composio session/user mapping per Orvo tenant/operator as appropriate;
- disable broad meta-tools in production unless wrapped by Orvo approvals;
- avoid remote bash/workbench on customer data unless explicitly needed and governed;
- persist a normalized copy of all action attempts/results into Orvo's own ledger;
- redact raw payloads before owner-facing briefs or operator surfaces.

Sources:

- <https://docs.composio.dev/docs/how-composio-works.md>
- <https://docs.composio.dev/docs/webhook-verification.md>
- <https://composio.dev/privacy>
- <https://composio.dev/enterprise>

## Fit by Orvo use case

| Orvo use case | Use Composio? | Reason |
|---|---:|---|
| Tiendanube core ingestion/actions | Not now | Not found in public toolkit catalog; first-party connector remains strategic. |
| MercadoLibre expansion | Not now | Not found in public toolkit catalog; use first-party/API-specific connector or another provider. |
| WhatsApp delivery for Orvo owner briefs | Maybe later, not core now | Public WhatsApp toolkit exists, but Orvo needs Meta Cloud API delivery status, templates, WABA health, inbound/status webhooks, redaction, and 24h-window semantics. Keep current Meta path unless Composio proves full coverage. |
| Google Sheets concierge onboarding | Yes, good candidate | Managed OAuth + Sheets tools/triggers can speed assisted pilots. |
| Gmail/customer inbox scanning | Yes, bounded | Useful for operator workflows if scopes and retention are tight. |
| Slack/Linear/GitHub internal ops | Yes, low-risk internal | Useful for autonomous Orvo team workflows and engineering ops. |
| HubSpot/CRM GTM workflows | Yes, later | Useful once paid-pilot pipeline needs CRM automation. |
| Meta Ads / Google Ads expansion | Maybe | Useful for `spend_without_orders`, but source freshness and evidence policies must stay in Orvo. |
| Shopify/WooCommerce expansion | Maybe | Useful outside the current Tiendanube wedge; do not distract from first pilots. |
| Owner-facing automated actions | Only through Orvo approvals | Composio can execute, but Orvo must own approval, idempotency, audit, and rollback semantics. |

## Alternative/complement matrix

| Tool | Best for | Orvo recommendation |
|---|---|---|
| Pipedream Connect | Managed OAuth, API proxy, workflows, app catalog | Shortlist alongside Composio; especially interesting because public pages exist for Tiendanube and WhatsApp Business. |
| Arcade.dev | Agent authorization, tool calls, MCP, user auth | Compare with Composio for agent-native auth and tool execution. |
| Trigger.dev | Durable tasks, retries, idempotency, queues/concurrency | Strong fit for Orvo's execution backbone; not a connector catalog. |
| LangGraph | In-code agent/workflow state, interruptions, human-in-the-loop | Useful if Orvo formalizes agent workflows in code. Does not solve OAuth/catalog by itself. |
| Retool | Internal operator UI and admin workflows | Good early operator surface for reviewing cases/evidence/approvals before building full UI. |
| Airbyte | Data ingestion/replication | Strong fit for analytical/history ingestion, not side effects. |
| Meltano | Git-versioned open-source data pipelines | Consider if Orvo wants more code-owned ETL than Airbyte. |
| n8n | Self-hosted workflow automation | Useful for one-off/customer-specific workflows; avoid as product core. |
| Zapier AI Actions/MCP | Customer-owned long-tail automation | Useful if customers already use Zapier; not ideal as Orvo core. |
| Apify | Scraping/browser automation/external evidence | Good for public-data extraction where APIs are absent. |
| Workato / Tray.ai | Enterprise iPaaS | Overkill for first SMB pilots; revisit for enterprise customers. |

Relevant sources:

- Pipedream Connect: <https://pipedream.com/docs/connect>
- Pipedream AI Tooling: <https://pipedream.com/docs/ai-tooling>
- Pipedream Tiendanube: <https://pipedream.com/apps/tiendanube>
- Pipedream WhatsApp Business: <https://pipedream.com/apps/whatsapp-business>
- Arcade: <https://docs.arcade.dev/en/get-started/about-arcade>
- Trigger.dev: <https://trigger.dev/docs/introduction>
- LangGraph: <https://docs.langchain.com/oss/python/langgraph/overview>
- Retool Workflows: <https://docs.retool.com/workflows>
- Airbyte: <https://docs.airbyte.com/>
- Meltano: <https://docs.meltano.com/>
- n8n: <https://docs.n8n.io/>
- Zapier AI Actions: <https://actions.zapier.com/docs/platform/gpt/>
- Zapier MCP: <https://mcp.zapier.com/>
- Apify: <https://docs.apify.com/platform/actors>
- Workato MCP/connectors: <https://docs.workato.com/en/mcp>, <https://docs.workato.com/en/connectors>
- Tray docs: <https://tray.ai/documentation>

## Recommended spike for Orvo

Run a 2-provider benchmark, not a big migration.

### Provider A: Composio

Test cases:

1. Connect Google Sheets for a fake tenant/operator.
2. Read a test pilot sheet and normalize a few rows into Orvo evidence records.
3. Execute one safe internal action, e.g. create a Linear/GitHub issue or append an operator note to a Sheet.
4. Persist the action attempt/result in Orvo's run ledger with redacted payloads.
5. Verify allowlist behavior: the agent cannot call tools outside the approved list.
6. Test revocation/expired auth behavior.

### Provider B: Pipedream Connect

Test cases:

1. Verify whether Tiendanube auth/actions are deep enough for Orvo's current connector needs.
2. Verify WhatsApp Business depth, especially templates, message send, inbound/status webhook support, and error semantics.
3. Run the same Sheets/internal-action tests as Composio.
4. Compare OAuth UX, per-tenant account mapping, latency, logs, and API ergonomics.

### Acceptance criteria

Pick a provider only if it can satisfy:

- per-tenant connected-account mapping;
- exact tool/action allowlists;
- predictable OAuth scopes and revocation;
- clear error taxonomy;
- acceptable latency for pilot workflows;
- raw payload redaction before Orvo storage/briefs;
- webhook signature verification;
- vendor logs exportable enough for debugging;
- no bypass of Orvo run ledger, Operational Cases, or approval gates.

### Non-goals

- Do not replace Tiendanube connector during the spike unless Pipedream/another provider demonstrably covers required fields better than Orvo's current code.
- Do not let a generic tool-search agent choose arbitrary tools.
- Do not send real customer WhatsApps through a new provider before Meta delivery semantics are verified.
- Do not move RBAC, approval, or audit source of truth out of Orvo.

## Final recommendation

For Orvo's current priority — first paid Tiendanube/WhatsApp pilots — the best near-term tool stack is:

1. **Keep Orvo-owned Tiendanube + Meta/WhatsApp core** for the first pilot.
2. **Spike Composio** for Google Sheets/Gmail/Slack/Linear/HubSpot-style long-tail authenticated actions.
3. **Spike Pipedream Connect in parallel** because of public Tiendanube and WhatsApp Business app support.
4. **Evaluate Trigger.dev** as execution infrastructure for durable jobs, retries, idempotency, and safe side effects.
5. **Use Retool only if operator/admin UI speed becomes a bottleneck.**
6. **Use Airbyte/Meltano for analytics/history ingestion later, not for transactional actions.**

Decision: Composio is worth testing, but the first production adoption should be narrow and wrapped by Orvo's own control-plane contracts.
