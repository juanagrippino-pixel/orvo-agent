# D2C Control Plane Roadmap

Status: Working roadmap
Date: 2026-05-24
Last reconciled: 2026-06-10
Related: `docs/plans/2026-05-24-d2c-control-plane-first-product.md`

## Priority rule

First-wave work must strengthen the D2C ecommerce wedge without bypassing platform contracts.

```text
Tiendanube/WhatsApp use case wins prioritization.
Runtime/registry/ledger/cases/audit wins implementation shape.
```

## Milestone 1 — Trustworthy runtime foundation

Outcome: every report/run can be explained from a compiled runtime and run ledger.

Deliverables:

- compiled runtime parity across preview/forced/scheduled paths;
- Tiendanube connector registry entry with capabilities and degraded behavior;
- run ledger records connector results, artifacts, dispatch attempts, and typed errors;
- secret redaction invariant tests;
- existing report paths and docs examples remain green.

Exit criteria:

- A forced and scheduled run use the same executable runtime shape or compatibility shim.
- Operator can inspect what ran and why advice was narrowed/skipped.
- No raw secrets in run artifacts/logs/docs.

## Milestone 2 — D2C metric and case foundation

Outcome: Orvo opens durable ecommerce cases instead of only producing report paragraphs.

Deliverables:

- metric registry entries/aliases for first D2C families;
- `OperationalCase` models/storage/engine basics;
- deterministic case creation from current insights/runtime events;
- stable dedupe/reopen behavior;
- case evidence snapshots;
- tests for `sales_drop`, `stockout_risk`, `data_stale`.

Exit criteria:

- Repeated runs update existing cases rather than spam duplicates.
- Every case has evidence.
- Existing `DailyReport` compatibility remains green.

## Milestone 3 — Operator surfaces and WhatsApp projection

Outcome: owner/operator sees case-backed summaries and internal inspection surfaces.

Deliverables:

- case queue projection;
- case timeline projection;
- run history endpoint/surface contract;
- WhatsApp brief sourced from cases where available;
- manual follow-up comments/actions;
- degraded-data language in briefs.

Exit criteria:

- Owner-facing brief can cite case/evidence refs.
- Operator can inspect open cases and run health.
- Missing/stale sources suppress/narrow advice.

## Milestone 3A — Work-management registry stabilization

Outcome: Orvo's Jira-like `OperationalCase` / WorkItem surface gains stable project, issue-type, workflow, and status-category semantics before saved filters, SLA queues, or multi-operator expansion depend on derived status sets.

Current shipped checkpoint, grounded in `app/brain/operational_cases.py`, `app/brain/work_items.py`, `app/brain/operator_views.py`, and `app/brain/operator_api/projections.py`:

- `OperationalCase` is still the durable work item source of truth with tenant scope via `business_id`, deterministic case types, timeline/evidence snapshots, and hardcoded lifecycle transitions.
- A read-only WorkItem projection layer now exposes project keys, work item IDs, issue types, workflow/status definitions, and canonical status categories (`to_do`, `in_progress`, `done`) without creating a parallel task store.
- JQL-lite and built-in operator views now support WorkItem projection fields including `project`, `issue_type`, `release_state`, `status_category`, and `assignee_ref`; they remain route/business-scoped projections and do not translate user input to SQL or persist custom saved views.
- There is still no separate persisted `Project`/`WorkItem` table, tenant-custom workflow scheme, or writable saved-view layer; treat those as post-v1 platform work until a concrete operator workflow requires them.

Delivered / keep green:

- additive project/work-item envelope over `business_id`, with stable project keys and no tenant-crossing leakage;
- internal status-category mapping for existing statuses: `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done`;
- explicit issue-type/case-type registry wrapper for current D2C case families, without introducing tenant-custom workflows yet;
- workflow definition registry that documents current allowed transitions before any executor/SLA layer consumes them;
- JQL-lite additions for canonical fields (`project`, `status_category`, `release_state`, `assignee_ref`, and `issue_type`), with route-owned business scope.

Next hardening deliverables:

- retire or rebase any branch/doc that uses the non-canonical `todo` category spelling;
- namespace service-management/customer-visible categories separately from canonical WorkItem `status_category` before merging SLA/service queues;
- preserve the projection-only boundary in operator/API docs and tests whenever queue, analytics, export, or WhatsApp surfaces include WorkItem fields.

Exit criteria:

- Operator/API projections can return WorkItem-shaped output while `OperationalCase` remains the source of truth.
- Built-in views and any new JQL fields derive from canonical registry/mapping helpers, not duplicated status literals.
- No new lifecycle transitions, LLM decisions, manual work creation, or owner-facing WhatsApp/report copy changes are introduced.
- Full suite and focused operator-case/query tests remain green.

## Milestone 4 — Sellable Tiendanube/WhatsApp pilot operations

Outcome: Orvo can run a paid/concierge Tiendanube/WhatsApp pilot safely.

Meta Ads, `spend_without_orders`, and channel-mix cases are not prerequisites for the first Tiendanube/WhatsApp pilot; the first pilot gates are the PRD launch checklist and `docs/ops/d2c-pilot-readiness-checklist.md`.

Deliverables:

- onboarding checklist;
- threshold configuration guide;
- pilot SLA/freshness policy;
- support/runbook for connector failures;
- GTM packet aligned with actual capabilities;
- board-report loop tracking pilot usefulness and blockers.

Fulfillment backlog is a conditional pilot/Growth module, not a blanket Starter promise. Current code and contracts already recognize `fulfillment_backlog` as a registered case family (`CASE_FAMILY_METRICS`, `OperationalCaseType`, dedupe/entity/action catalog alignment), but commercial enablement must wait for merchant-specific payment, fulfillment-status, timestamp, SLA, exclusion, resolver, and freshness gates. If those gates fail, the pilot should surface `data_stale` / setup-required state instead of owner-facing stuck-order claims. See `docs/research/2026-06-05-fulfillment-backlog-pilot-packaging.md`.

Exit criteria:

- One real business can receive a daily useful brief.
- Operator can explain every claim.
- Failures degrade honestly.
- Follow-up history exists for open/resolved cases.

### Milestone 4A — Readiness-gated fulfillment backlog module

Outcome: Orvo can safely decide whether a Tiendanube merchant is eligible for owner-facing `fulfillment_backlog` cases, and can explain when fulfillment data is not trustworthy enough.

Source-of-truth checkpoint:

- `app/brain/semantics/metric_registry.py` registers `fulfillment_backlog` metrics (`commerce.fulfillment.pending_count`, `commerce.fulfillment.oldest_pending_age_hours`).
- `app/brain/operational_cases.py` defines the case type, dedupe shape, and Tiendanube entity scope, while `tests/contracts/test_metric_registry_contract.py` keeps registered case families aligned with Operational Cases/actions.
- Detection still needs merchant-specific truth gates before this becomes a sellable owner-facing workflow; do not infer fulfillment backlog from generic report copy or ambiguous order statuses.

Deliverables:

- fulfillment readiness audit checklist for Tiendanube order/payment/shipping statuses;
- deterministic suppression path that opens/updates `data_stale` or setup-required context when fulfillment status cannot be trusted;
- redacted order-sample evidence policy for backlog cases;
- operator/resolver assignment requirement before WhatsApp projection;
- package copy that places verified backlog monitoring in Growth/upsell unless the Activation Sprint proves the gates are green.

Exit criteria:

- Payment, fulfillment, timestamp, SLA, exclusion, resolver, and freshness gates are represented in docs/tests before owner-facing backlog copy is enabled.
- Backlog cases cite registered fulfillment metrics and redacted evidence refs only.
- Stale Tiendanube data suppresses backlog and updates `data_stale`.
- The Starter package can still launch without promising fulfillment monitoring.

## Milestone 4B — Readiness-gated WhatsApp attention-backlog module

Outcome: Orvo can safely decide whether a WhatsApp-heavy Tiendanube merchant is eligible for owner-facing `unanswered_conversations` cases, without being mistaken for an inbox, chatbot, or auto-reply product.

Source-of-truth checkpoint:

- `app/brain/semantics/metric_registry.py` registers `unanswered_conversations` metrics (`support.conversations.unanswered_count`, `support.conversations.oldest_unanswered_age_minutes`) with low-PII semantics and source restrictions.
- `app/brain/operational_cases.py` includes `unanswered_conversations` in the registered owner-facing/detectable family set because it derives from `CASE_FAMILY_METRICS`.
- The legacy report/Sheets/sample path can still emit a “Conversaciones sin responder” insight from `unanswered_conversations`; that compatibility path is not enough to sell a live WhatsApp backlog workflow. The Growth module requires the activation gates in `docs/research/2026-06-10-unanswered-whatsapp-conversations-readiness.md`.

Deliverables:

- structured inbox/API/source readiness checklist covering status, last inbound/outbound timestamps, assignment/team scope, and stable conversation refs;
- deterministic suppression path that opens/updates `data_stale` or setup-required context when the WhatsApp/support source is missing, stale, or cannot prove unanswered state;
- business-hours and SLA threshold policy before any owner-facing alert;
- PII-safe evidence policy: counts, oldest age, channel/team, and safe refs only; no raw message bodies, phone numbers, customer names, addresses, or sensitive support text in WhatsApp briefs;
- explicit resolver/team ownership and no-auto-reply/no-LLM-classification guardrails;
- packaging copy that keeps Starter focused on Tiendanube truth and places conversation backlog monitoring in Growth only after the source gates pass.

Exit criteria:

- Backlog cases cite registered support-conversation metrics and redacted evidence refs only.
- Stale or ambiguous WhatsApp/support evidence suppresses `unanswered_conversations` and updates `data_stale` or setup-required operator context.
- Owner-facing briefs never expose raw customer-message content or imply Orvo will answer customers.
- The first paid pilot can qualify WhatsApp pain without promising backlog monitoring until the approved source is live.

## Milestone 5 — Post-pilot revenue/ads wedge expansion

Outcome: Orvo identifies spend/order mismatch and higher-value cross-system cases after the Tiendanube/WhatsApp wedge is trustworthy.

Deliverables:

- Meta Ads + Tiendanube runtime freshness parity;
- `spend_without_orders` family;
- channel/source health surfaced in operator view;
- `channel_mix_shift` promotion only after channel-scoped metrics, cross-source freshness policy, and owner-facing suppression tests exist;
- demo/sales examples using redacted data.

Exit criteria:

- Orvo never claims ad/commerce mismatch when either source is stale.
- Cross-source evidence is inspectable in run ledger/case timeline.
- `channel_mix_shift`, if enabled, cites channel-scoped evidence and cannot collapse distinct channel issues into one broad all-channel case.

## Backlog until wedge is real

- generic app marketplace;
- developer-first SDK;
- broad horizontal team workflows;
- complex automations;
- dashboards not tied to case/action workflows;
- LLM explainer beyond validated projections.
