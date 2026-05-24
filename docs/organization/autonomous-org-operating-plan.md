# Orvo Autonomous Organization Operating Plan

> Pivot: Orvo is no longer being managed as a sequence of milestones or a WhatsApp-report project. The organization is now oriented toward building a **sellable Atlassian-like operations control plane** for LatAm ecommerce.

## Product thesis

Orvo should become the operating system for D2C physical-goods ecommerce operations in Argentina/LatAm.

The right analogy is **Atlassian/Jira for ecommerce operations**, not a chatbot, not a dashboard, not a daily-report bot, and not a mini ERP.

```text
Connectors + events + metrics
        ↓
Semantic registry + evidence model
        ↓
OperationalCase / WorkItem native object
        ↓
Workflow states, comments, decisions, ownership, SLA, audit
        ↓
Operator surfaces: WhatsApp, API, timeline, queue, admin
        ↓
Rules, approvals, playbooks, controlled automations
        ↓
Sellable team/product platform
```

WhatsApp is a surface. Reports are a wedge/projection. The product is the **case/workflow control plane**.

## Operating principles

1. **Product-first, not milestone-first.** Stop optimizing around isolated Hitos. Optimize for the sellable product: cases, workflows, governance, connectors, operator experience, and trust.
2. **Native object first.** `OperationalCase`/`WorkItem` is the equivalent of a Jira Issue. Everything else is a projection, event, action, automation, or surface around it.
3. **Atlassian-like primitives.** Workspaces, projects/businesses, issue types, statuses, transitions, comments, assignees, labels, evidence, audit log, rules, integrations, permissions, admin APIs.
4. **External systems remain source of truth.** Tiendanube/MercadoLibre/Meta/Sheets own commerce facts. Orvo owns coordination, exceptions, decisions, operational state, and evidence-backed workflow.
5. **Connector platform, not one-off adapters.** Connectors must become registry-driven, contract-tested, health-scored, permissioned, and auditable.
6. **LLMs explain; deterministic core decides.** Calculations, detections, state transitions, dedupe, reopen, and automation gates are deterministic and testable.
7. **Capacity becomes product artifacts.** Tokens should yield specs, ADRs, code, tests, evals, review findings, integration plans, and sellable packaging.
8. **Autonomous organization, not swarm.** Departments own domains, gates, and outputs. No overlapping random edits.
9. **Human-controlled integration.** Branches, commits, tests, and merge plans are prepared autonomously; push/deploy/major merge remains controlled unless explicitly delegated.

## Departments and live jobs

| Department | Job ID | Role |
|---|---:|---|
| Chief of Staff / COO | `661036933588` | Runs the product organization, allocates capacity, resolves overlap, enforces product-first strategy. |
| Product & Market Intelligence | `11d230a06306` | ICP, packaging, sellable use cases, competitor/primitives research, pricing/GTM implications. |
| Architecture Review Board | `156fc69339e5` | Atlassian-like platform architecture, bounded contexts, ADRs, source-of-truth boundaries. |
| Engineering Factory Manager | `19a7934d892f` | Converts product/platform strategy into non-overlapping implementation worktrees. |
| QA / Red Team Director | `be285bc8f107` | Platform invariants, contract tests, workflow/case lifecycle tests, trust/security regression gates. |
| Release / Integration Manager | `9273c4bc5131` | Verifies branches/commits/tests and prepares product integration trains. |
| SRE / Operations Director | `d62555476c05` | Keeps cron/gateway/worktrees/repo/runtime healthy and observable. |
| Knowledge / Roadmap Librarian | `c155ea848ddb` | Keeps product docs, ADRs, specs, roadmap, and operating map coherent. |
| Board Report | `61c5bd141ea2` | Executive synthesis for Juan: product progress, shipped artifacts, risks, decisions. |
| Work Management Platform | `NEW` | Owns OperationalCase/WorkItem, lifecycle, comments, evidence, audit, transitions. |
| Workflow Automation Platform | `NEW` | Owns rules, triggers, approvals, playbooks, controlled automations. |
| Connector Platform | existing `daad02bc0620` + product expansion | Owns connector registry, contracts, health, scopes, secrets, emitted events/metrics. |
| Semantic Intelligence Platform | existing `fe5814e07377` | Owns metric/event definitions, aliases, evidence semantics, cross-connector correctness. |
| Operator Experience / Surfaces | existing `20fe2125e513` + surface lane | Owns API/timeline/queue/WhatsApp/web surfaces as projections around cases. |
| Platform Trust / Security / Admin | `NEW` | Owns tenants/workspaces, RBAC, audit log, secret indirection, compliance boundaries. |

## Bounded contexts

### 1. Work Management Core

Equivalent to Jira Issue core.

Owns:
- `OperationalCase` / `WorkItem`
- issue types: stockout, fulfillment delay, payment risk, revenue anomaly, campaign inefficiency, data freshness, connector failure
- status model: open, triaged, waiting_owner, waiting_external, snoozed, resolved, dismissed, reopened
- transitions with deterministic guards
- comments, events, labels, priority, assignee, due/SLA
- evidence links and run references
- dedupe/reopen semantics

Likely paths:
- `app/brain/cases/models.py`
- `app/brain/cases/engine.py`
- `app/brain/cases/store.py`
- `tests/contracts/test_case_engine_contract.py`

### 2. Workflow Automation Core

Equivalent to Jira Automation/Atlassian rules.

Owns:
- triggers: case_created, case_reopened, connector_failed, metric_threshold_crossed, owner_replied, scheduled_check
- conditions: business, connector, metric, priority, stale evidence, SLA
- actions: comment, assign, notify surface, request approval, create follow-up, suppress, escalate
- human-in-the-loop approvals before external side effects

Likely paths:
- `app/brain/workflows/rules.py`
- `app/brain/workflows/engine.py`
- `app/brain/workflows/actions.py`
- `tests/contracts/test_workflow_rules_contract.py`

### 3. Connector Platform

Equivalent to Atlassian app/connectors + Zapier-style integration runtime.

Owns:
- connector registry as source of truth
- connector capabilities, scopes, rate limits, health checks
- public config vs secret references
- emitted event/metric contracts
- connector outcome logging

Likely paths:
- `app/brain/connector_registry.py`
- `app/brain/runtime.py`
- `app/brain/adapters/*`
- `tests/contracts/test_connector_contracts.py`

### 4. Semantic Intelligence

Owns:
- metric definitions
- event definitions
- aliases and namespace policy
- evidence types
- deterministic insight-to-case mapping

Likely paths:
- `app/brain/semantics/*`
- `app/brain/insights.py`
- `tests/contracts/test_metric_registry_contract.py`

### 5. Operator Experience / Surfaces

Surfaces are projections, not the system of record.

Owns:
- case queue
- case timeline
- operator API
- WhatsApp commands/replies
- digest/report projections
- future lightweight web/admin UI

Likely paths:
- `app/brain/operator_api.py`
- `app/brain/surfaces/*`
- `app/brain/reporting.py`
- `app/brain/dispatch.py`

### 6. Trust, Admin, Security

Owns:
- workspaces/businesses/users
- RBAC and permissions
- audit log
- run ledger integration
- secret indirection
- data retention and export boundaries

Likely paths:
- `app/brain/admin/*`
- `app/brain/run_ledger.py`
- `app/brain/storage.py`
- `tests/contracts/test_audit_log_contract.py`

## First product wave

This replaces milestone-first work.

1. **Product object spec:** canonical `OperationalCase`/`WorkItem` spec with lifecycle and Atlassian analogy.
2. **Case model/store/engine:** pure deterministic core with tests.
3. **Metric/event registry:** semantic definitions before cross-connector logic expands.
4. **Connector emitted-event contracts:** adapters emit typed metrics/events with source/evidence.
5. **Insight-to-case mapper:** deterministic mapping from current insights to work items.
6. **Case timeline/queue API skeleton:** sellable operator surface.
7. **Run ledger/audit integration:** every case has evidence lineage.
8. **Workflow rules MVP:** trigger/condition/action DSL for controlled internal actions.
9. **Tenant/admin/security skeleton:** business/workspace boundaries, secret references, audit.
10. **GTM packaging:** define the first sellable SKU: “ops control plane for Tiendanube brands”, not “daily WhatsApp report”.

## What to stop doing

- Stop calling the operating strategy Hito-first.
- Stop making WhatsApp report tone the center of the product.
- Stop building one-off report rules when the real product object should be a case/work item.
- Stop treating adapters as isolated scripts instead of a connector platform.
- Stop adding scaffolds that are not wired to cases, workflows, audit, or sellable operator surfaces.

## Organization interaction graph

```text
Product/GTM ─────────────┐
Architecture Board ──────┼──> Knowledge/Roadmap ───────┐
Deep Research ───────────┘                              │
                                                        ↓
Semantic Intelligence ──> Work Management Core ──> Workflow Automation
Connector Platform ─────┘             │                    │
                                      ↓                    ↓
                         Operator Surfaces/API/WhatsApp/Digest
                                      │
                                      ↓
QA/Red Team ───────────────> Release Integration ─────────> Board Report
SRE/Ops ────────────────────────────────────────┘
COO monitors and reallocates across all departments.
```

## Success metric

A good autonomous-org day ends with:

- one or more product-platform branches or specs closer to a sellable Atlassian-like control plane;
- concrete movement on native cases/workflows/connectors/semantics/operator surfaces;
- tests/contracts proving invariants;
- a clear integration queue;
- product/GTM clarity about the first sellable package;
- no regression to “just make the report nicer” as the strategic center.
