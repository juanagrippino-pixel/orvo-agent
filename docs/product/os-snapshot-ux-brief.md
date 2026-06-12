# OS Snapshot UX Brief

Status: Draft implementation brief for Milestone 4C
Date: 2026-06-12
Owner: Product / UX scout
Related: `docs/product/d2c-control-plane-prd.md`, `docs/specs/d2c-operator-surface-contract.md`, `docs/specs/d2c-case-family-catalog.md`, `docs/specs/d2c-action-key-catalog.md`, `docs/specs/internal-operator-api-contract.md`, `docs/roadmap/d2c-control-plane-roadmap.md`

## Product intent

The OS snapshot is the first merchant-facing slice of Orvo's operating-system console. It should answer, in one calm screen:

1. What needs attention now?
2. Which business area is affected?
3. What evidence supports it?
4. What is the next governed action?
5. Which modules are connected, stale, or still setup-required?

The screen is a **projection of runtime, connector, case, and action state**. It is not a dashboard for every metric, not an ERP module grid, not a generic AI interface, and not a place to hide case/workflow truth in chat text.

## One-screen layout

### Screen hierarchy

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Header: store + today + last run + primary next action               │
├─────────────────────────────────────────────────────────────────────┤
│ Priority band: one sentence for the most important open case          │
├───────────────────────────────┬─────────────────────────────────────┤
│ Left: Module health lanes      │ Right: Today's operating queue       │
│ - Ventas / pedidos             │ - Top actionable case                │
│ - Stock / fulfillment          │ - Evidence strip                     │
│ - Atención / WhatsApp          │ - Registered next action             │
│ - ARCA / fiscal readiness      │ - Open / in progress / resolved      │
│ - Caja / reporting readiness   │                                     │
├───────────────────────────────┴─────────────────────────────────────┤
│ Footer: run health + setup path + recently closed / stale caveat     │
└─────────────────────────────────────────────────────────────────────┘
```

### Header card

Purpose: orient the operator without forcing them to read a report.

Required elements:

- business/store label;
- local date and timezone label;
- last successful run timestamp;
- run status: completed, completed degraded, failed, never run, or loading;
- primary next action: the highest-priority registered action from the top actionable case, or a setup action when no evidence-backed case exists;
- small confidence cue: `evidencia actualizada`, `datos parciales`, or `requiere conexión`.

Example copy:

> Hoy: 1 caso prioritario. Riesgo de stock en Campera X. Siguiente acción: confirmar stock físico.

### Priority band

Purpose: make the next action obvious before the operator inspects details.

State rules:

- If a high-priority actionable case exists: show one sentence + case type + action key.
- If only setup-required/degraded connectors exist: show setup as the action.
- If no actionable cases exist and all required modules are healthy: show a calm "todo al día" state with last run context.
- Never show more than one primary action. Secondary actions live in the queue.

### Module health lanes

Purpose: make Orvo feel like a PyME operating system while keeping breadth honest.

Initial modules:

| Module | Owner-facing label | Initial state | Evidence source |
|---|---|---|---|
| Ventas / pedidos | `Ventas` | Connected / degraded / setup-required | Tiendanube connector, `sales_drop` cases, run ledger |
| Stock / fulfillment | `Stock` | Connected / degraded / setup-required / readiness-gated | Tiendanube product/inventory/order data, `stockout_risk`, optional `fulfillment_backlog` when gates pass |
| Atención | `Atención` | Setup-required by default until structured support/WhatsApp source passes gates | Support/WhatsApp connector readiness; `unanswered_conversations` only when promoted |
| Fiscal | `ARCA` | Setup-required / readiness-only | Connector/config readiness; no document issuance in MVP |
| Caja / reportes | `Caja` | Setup-required / readiness-only | Treasury/reporting connector readiness; no reconciliation claims until source gates pass |

Module card fields:

- status pill: `ok`, `atención`, `por conectar`, `datos parciales`, `bloqueado`;
- one-line summary: "Tiendanube actualizado", "Stock requiere confirmación", "Atención pendiente de conexión";
- latest evidence timestamp;
- count of open actionable cases in that lane;
- next action if the module owns the top case;
- "ver casos" link to filtered queue;
- "ver última corrida" link to run detail.

### Today's operating queue

Purpose: replace alert spam with a governed case desk.

Default view: top 3 actionable cases sorted by existing priority projection.

Case row fields:

- case type label: `Riesgo de stock`, `Baja de ventas`, `Datos desactualizados`;
- entity label: SKU/product/channel/connector, redacted/safe only;
- severity and priority score or bracket;
- evidence count and source connector;
- age or last updated time;
- primary registered action key;
- status: open, acknowledged, in progress, resolved recently;
- expand button to open case timeline.

Case detail drawer/side panel fields:

- title and status;
- evidence snapshots with metric label, value, unit/currency, window, observed time, source label;
- source freshness and degraded caveat;
- timeline events;
- registered actions available for that case;
- comment/acknowledge/mark in progress/resolve/dismiss controls using existing action keys;
- "última corrida" and artifact/run refs.

### Footer / run health strip

Purpose: keep evidence honesty visible without turning the screen into logs.

Required elements:

- last run id/date;
- connector health summary;
- cases opened/updated count;
- dispatch status for WhatsApp brief: sent, skipped, failed, not configured, or not run;
- redaction notice when relevant;
- link to full run history.

Example:

> Última corrida: run_123 · Tiendanube ok · 1 caso actualizado · WhatsApp enviado · datos redactados.

## UX rules

1. **Calm, not crowded.** Use whitespace, simple cards, and short Spanish copy. Avoid dense tables unless the operator opens a detail view.
2. **One next action.** The home screen should never ask the owner to choose from ten alerts. Show one primary action and keep secondary work in the queue.
3. **Cases before charts.** Use cards and timelines, not generic charts. Charts may appear only in detail/inspection views and only when tied to a case, run, or module state.
4. **Evidence by default.** Every owner-facing number should expose source, freshness, and evidence refs. Stale or partial data must be visible, not hidden.
5. **Readiness is product.** Unconnected modules should render as honest setup-required lanes. Do not fake ARCA, caja, fulfillment, or atención automation before source gates pass.
6. **No ERP wall.** Do not imitate a full administrative suite. Show operating status and next actions, not every transaction, ledger, report, or menu.
7. **No AI dashboard clutter.** Avoid generic chat panels, floating assistant widgets, speculative explanations, and AI-generated metrics. LLM/copy layers may explain registered cases and actions only.
8. **Governed actions only.** Buttons must map to registered action keys from `d2c-action-key-catalog.md`. Suggestions must not imply external side effects unless approval is explicit.
9. **WhatsApp is a projection.** The console is the canonical control surface. WhatsApp briefs can point back to the OS snapshot and case detail.
10. **Demo-safe.** Videos and screenshots must use demo/synthetic/redacted data. Never show raw tokens, URLs, customer PII, or unimplemented claims.

## Component list and API data needs

### 1. `OSSnapshotPage`

Data needed:

- `GET /internal/brain/businesses/{business_id}/operator-session` for actor/business context.
- `GET /internal/brain/businesses/{business_id}/connectors/readiness` for module readiness and setup-required signals.
- `GET /internal/brain/businesses/{business_id}/cases/summary` for queue counts.
- `GET /internal/brain/businesses/{business_id}/cases/top-by-priority` for the primary action.
- `GET /internal/brain/businesses/{business_id}/runs` for last run and dispatch health.

Derived state:

- module health status;
- primary next action;
- last run status;
- setup-required count;
- actionable/degraded case count.

### 2. `ModuleHealthLane`

Data needed:

- connector readiness projection: `connector_type`, `readiness_state`, `setup_required`, `setup_reason`, `last_health`, `capabilities`, `emitted_metric_families`;
- case summary by case type/source connector;
- latest evidence timestamp from top case or evidence snapshot;
- run status from latest run.

Module mapping should be deterministic and documented in code/config, not hand-written per merchant.

### 3. `PriorityBand`

Data needed:

- top actionable case from `cases/top-by-priority`;
- case detail projection for title, entity scope, severity, priority, evidence count, source connectors;
- suggested actions from case detail;
- setup-required connector if no actionable case exists.

### 4. `OperatingQueue`

Data needed:

- `GET /internal/brain/businesses/{business_id}/cases?status=open` or built-in view/filter;
- `GET /internal/brain/businesses/{business_id}/cases/top-degraded`;
- `GET /internal/brain/businesses/{business_id}/cases/top-stalled`;
- `GET /internal/brain/businesses/{business_id}/cases/facets` for source connector, case type, priority, degraded filters.

Queue filters to support in the first implementation:

- open;
- acknowledged / in progress;
- high priority;
- degraded / stale evidence;
- source connector;
- case type;
- entity scope;
- recently resolved.

### 5. `CaseDetailDrawer`

Data needed:

- `GET /internal/brain/businesses/{business_id}/cases/{case_id}` for evidence snapshots, timeline, suggested action keys, and metadata;
- `GET /internal/brain/businesses/{business_id}/cases/{case_id}/timeline` if timeline is paginated;
- `POST /internal/brain/businesses/{business_id}/cases/{case_id}/actions` for manual actions.

Allowed manual actions:

- `acknowledge_case`;
- `assign_owner`;
- `add_comment`;
- `request_follow_up`;
- `mark_in_progress`;
- `resolve_case`;
- `dismiss_case`;
- `request_external_action` only when explicitly approved and enabled.

### 6. `RunHealthStrip`

Data needed:

- `GET /internal/brain/businesses/{business_id}/runs`;
- `GET /internal/brain/businesses/{business_id}/runs/{run_id}`;
- run fields: `status`, `started_at`, `finished_at`, `connector_outcomes`, `cases_opened`, `cases_updated`, `dispatch_outcomes`, `summary_metadata`.

### 7. `SetupPathCard`

Data needed:

- connectors readiness `setup_required`, `setup_reason`, `operator_next_step`;
- validation issues and safe setup hints;
- disabled/unknown connector state.

Copy rule: setup cards should say what is missing, not imply Orvo can already operate that module.

## First video/demo sequence supported by the UI

Target length: 2–3 minutes for landing/sales walkthrough.

Sequence:

1. Open Orvo console on demo tenant.
2. Show header: today, store, last run, and primary next action.
3. Show module lanes:
   - Ventas: ok / updated from Tiendanube.
   - Stock: attention, with one stock risk.
   - Atención: por conectar, readiness-only.
   - ARCA: por conectar, no fiscal issuance.
   - Caja: por conectar, no reconciliation claim.
4. Open the top case: `stockout_risk`.
5. Show evidence strip: stock units, recent velocity, source label, freshness timestamp.
6. Show registered next action: `confirm_stock` or `pause_promotion` as suggestion/manual action.
7. Acknowledge or mark in progress using the case action API.
8. Open run health strip and show last run + WhatsApp brief sent/skipped status.
9. Show recently resolved or stale caveat to prove follow-up memory and degraded-data honesty.
10. Close with: "No es un dashboard ni un chatbot. Es el centro operativo de la tienda."

Asset rule: record real surfaces only. If a module is not connected, show it as setup-required.

## Acceptance criteria for implementation worker

Functional:

- The OS snapshot is derivable from existing operator API projections: connector readiness, case summaries, top actionable cases, case detail, run history, and action endpoints.
- The screen shows the five initial module lanes: Ventas, Stock, Atención, ARCA, Caja.
- Unconnected or readiness-gated modules render honestly as setup-required or readiness-only.
- The primary next action is unique and comes from a registered action key or setup-required connector.
- Case rows and detail views include evidence source, freshness/degraded caveat, and safe entity labels.
- Manual actions append audit/timeline events through existing case-action APIs.
- Run health shows connector status, cases opened/updated, and dispatch status without exposing raw artifacts or secrets.
- No new source of truth is introduced: cases, metrics, run ledger, connector readiness, and action keys remain canonical.

UX:

- A busy owner can understand the screen in under 10 seconds.
- The interface avoids dense ERP-style menus, spreadsheet-like grids, and generic AI chat widgets.
- Empty, loading, no cases, degraded, and setup-required states are designed explicitly.
- Spanish copy is short, direct, and calm.
- The demo tenant can be recorded without redaction surprises.

Contract/safety:

- No LLM-created metrics, cases, priorities, lifecycle transitions, or action keys.
- No owner-facing claims from stale/missing data.
- No public competitor names in landing, video, metadata, or public copy.
- No raw secrets, OAuth codes, tokens, URLs, or customer PII in screenshots/video.
- Existing Google Sheets, CSV, Tiendanube, dispatch, storage, scheduler, and report behavior remains preserved.
- If implementation changes product code, tests must cover API projections, action keys, redaction, and degraded-state rendering.

## SEO and landing implications

Public positioning should avoid competitor names and avoid "another ERP", "dashboard", or "chatbot" framing.

Recommended public language:

- "centro operativo para ecommerce PyME";
- "casos operativos con evidencia";
- "monitoreo de ventas, stock y datos desde Tiendanube";
- "agentes de gestión que proponen acciones gobernadas";
- "brief diario por WhatsApp, control completo en la app";
- "módulos por conectar con honestidad sobre los datos".

Suggested landing page sequence:

1. Hero: "Tu tienda, operada desde un centro operativo."
2. Problem: owners check Tiendanube, WhatsApp, stock, caja, and fiscal readiness across scattered tabs.
3. Product: Orvo turns evidence-backed cases into a daily queue and WhatsApp brief.
4. Wedge: Tiendanube sales/orders + stock risk + data freshness first.
5. OS feel: module lanes for Ventas, Stock, Atención, ARCA, Caja, with readiness states.
6. Proof: case timeline, evidence refs, run history, follow-up memory.
7. CTA: paid pilot / demo.

SEO page candidates:

- `/centro-operativo-ecommerce-pyme`
- `/tiendanube-control-operativo`
- `/casos-operativos-tiendanube`
- `/riesgo-stock-tiendanube`
- `/ventas-stock-whatsapp-pyme`
- `/brief-operativo-whatsapp`

Landing risk to avoid: do not promise ARCA issuance, money reconciliation, inbox auto-replies, or public API/MCP before the corresponding readiness gates are live.
