# Orvo operating toolchain blueprint

Status: Proposed  
Date: 2026-05-24  
Related ADR: `docs/adr/0004-autonomous-operating-toolchain.md`

## Purpose

This document defines how Orvo's autonomous organization should work and which Atlassian/Vasilios-inspired platform tools and practices it should translate into Orvo.

The goal is not to imitate Atlassian's UI or deploy heavyweight infrastructure too early. The goal is to copy the durable operating mechanics:

- one native work object;
- self-service provisioning through a broker/control plane;
- compiled, validated runtime configuration;
- centralized gateway concerns;
- evidence, audit, permissions, rate limits, and observability as platform primitives;
- product work represented as durable artifacts, not chat memory.

## Public source note on Vasilios Syrakis references

The current public/source evidence found for the “Vasilios/Atlassian platform” thread is:

- Vasilios Syrakis's public site: `https://cetanu.github.io/`.
- `cetanu/sovereign`: described as a JSON control plane for Envoy, supplying dynamic config to downstream Envoy proxies through templates, data sources, and Python plugin extension points. Its README points support to `vsyrakis@atlassian.com` and Atlassian developer docs for Sovereign.
- `cetanu/steward`: described as an implementation of the Lyft rate-limit service; it loads rate-limit config from HTTP/file, runs as a gRPC server, uses Redis, and is implemented primarily in Rust.
- `cetanu/envoy-formula`: SaltStack formula for Envoy-related system configuration.
- `gufranco/regnant`: a third-party study artifact claiming to reproduce the platform Vasilios described publicly; useful as an interpretation, not as primary Atlassian authority. It combines Envoy, xDS/Sovereign, Open Service Broker, mTLS, OIDC/RBAC, OpenTelemetry, Packer/SaltStack, LocalStack/AWS-shaped infra, Keycloak, Redis, Prometheus/Grafana/Loki/Tempo, WASM filters, cosign, syft, Trivy, and SLSA provenance.
- `docs/research/2026-05-24-atlassian-platform-video-analysis.md`: local analyzed video transcript. It describes, as a personal retrospective, an Open Service Broker-style load-balancing broker, FastAPI/worker/durable-state provisioning flow, Sovereign/Envoy template/context rendering, CloudFormation/Packer/SaltStack proxy infrastructure, gateway sidecars for auth/authz/rate-limit/logging concerns, and maintenance/on-call lessons.

Operational rule: use these as design references. Do not claim Orvo has verified Atlassian-internal details unless the repo or public source directly supports the claim. The transcript is useful because it is closer to first-person architectural recollection than a third-party reconstruction, but it is still not an official Atlassian architecture document.

## Product operating thesis

Orvo should become an Atlassian-like operating system for ecommerce operations:

```text
Connectors / external systems
        ↓
Connector contracts + semantic registry
        ↓
Runtime/control plane compilation
        ↓
OperationalCase / WorkItem lifecycle
        ↓
Workflow automation + approvals + playbooks
        ↓
Operator surfaces: queue, timeline, API, WhatsApp, reports
        ↓
Trust/admin/security/observability layer
        ↓
Sellable platform, marketplace/connectors, packaging
```

External systems remain source of truth for their native facts. Orvo becomes source of truth for coordination, evidence, workflow state, decisions, permissions, and audited operator action.

## Atlassian/Vasilios tool translation map

| Reference tool/practice | What it means in Atlassian/Vasilios platform terms | Orvo translation |
|---|---|---|
| Jira issue/work item | Native unit of work with type, fields, status, transitions, comments, assignees, labels, audit | `OperationalCase` / `WorkItem` as the one native object; reports and WhatsApp messages are projections |
| Jira workflows/schemes | Status and transition model separated from UI | Workflow schemes per business/use case, deterministic guards, transition audit |
| Jira Automation | Trigger/condition/action rules with limits and audit | Rule engine with dry-run, approval gates, idempotency, and safe side-effect boundaries |
| Confluence | Durable knowledge, decision logs, runbooks, playbooks | Case-linked playbooks/SOPs and internal product docs under `docs/` until a product surface exists |
| Jira Service Management / Opsgenie / Statuspage | Incident/request/SLA/change/problem operations | Service-management layer for escalations, SLA timers, incidents, and customer-facing request queues |
| Bitbucket / PR workflow | Branch, review, CI, release discipline | External worktrees, conventional commits, review manifests, integration train |
| Atlassian Marketplace / Forge / Connect | App ecosystem with scopes, permissions, webhooks, certification | Connector/app registry, permission scopes, event contracts, developer docs, certification tests |
| Atlassian Admin / Guard | Org/site/user/security/admin controls | Tenant/workspace/project model, RBAC, audit export, secret indirection, retention policy |
| Compass | Service catalog and ownership | Internal service/component catalog for Orvo bounded contexts, owners, SLIs, docs, repos/tests |
| Sovereign / xDS control plane | Dynamic config rendered from templates plus context/data sources into Envoy resources | Compile validated Orvo runtime specs from tenant config, connector registry, policies, templates, secrets refs, and durable provisioning state |
| Open Service Broker | Self-service provisioning API with catalog/plans, provision/update/delete requests, worker execution, and status polling | Broker/API for adding businesses, connectors, workflows, SLAs, and runtime resources with validation, status ledger, and audit trail |
| Envoy edge/gateway | Central routing/auth/rate-limit/logging boundary, with some concerns handled by filters or local sidecars | Shared API/surface gateway layer: auth, RBAC, rate limits, idempotency, tenant routing, audit/logging; implement as Python middleware/contracts before any proxy/sidecar stack |
| Steward / Lyft rate limit | Central rate-limit service fed by config | Tenant/connector/operator rate-limit policies with deterministic outcomes and test fixtures |
| OpenTelemetry/Prometheus/Grafana/Loki/Tempo | Observability across proxy/runtime | Run ledger, traces/log correlation, connector health, SLOs, replay hooks, failure taxonomy |
| Packer + SaltStack | Reproducible proxy host/image configuration with observability/security/runtime agents | Reproducible worker/runtime environment docs/scripts and preflight checks; only later container/image provenance if operational scale demands it |
| Broker queue/status flow | Request path enqueues durable work; worker performs side effects and records completion/error | DB-backed provisioning queue/status ledger first; later external queue only if scale requires it |
| Sidecar extension model | Specialized auth/authz/rate-limit logic runs beside the proxy and receives dynamic config | Plugin/sidecar model for connectors, auth providers, workflow actions, renderers, redaction, and rate-limit policies, beginning in-process with certification tests |
| On-call/debug maintenance | Docs, logs, metrics, expected failure modes, onboarding, and churn management | Component catalog, runbooks, failure taxonomy, operability risks in worker manifests, and churn/deprecation review |
| cosign/syft/Trivy/SLSA | Supply-chain integrity | SBOM/provenance/vulnerability gates before customer-facing deployments |

## Organization model

The autonomous organization should be managed as a product company, not a task swarm.

### Executive/control departments

- **COO / Product Operating System**: resolves overlap, allocates capacity, enforces product-first strategy, owns the operating graph.
- **Architecture Review Board**: owns ADRs, bounded contexts, source-of-truth boundaries, and platform invariants.
- **Knowledge / Roadmap Librarian**: turns research and decisions into durable docs, ADRs, specs, roadmaps, and deprecation notes.
- **Board Reporter**: reports product progress, integration queue, risks, decisions, and next bets to Juan.

### Product/platform departments

- **Work Management Core**: Jira-like object model, issue types, fields, workflow schemes, comments, evidence, search model.
- **Workflow Automation Platform**: rule engine, dry-run/simulation, quotas, approvals, audit, templates.
- **Connector / Ecosystem Platform**: connector contracts, scopes, app permissions, webhooks, health, certification tests, developer docs.
- **Semantic Intelligence Platform**: metric/event registry, evidence model, deterministic detections, aliases/deprecation.
- **Operator Surfaces**: queue, timeline, API, WhatsApp, reports, saved views, exports; surfaces never become source of truth.
- **Service Management / SLA Platform**: incidents, request types, escalations, SLA timers, change/problem records.
- **Trust / Admin / Security Platform**: org/site/workspace/project admin, RBAC, audit export, secrets, retention, compliance boundaries.
- **Search / Query / Analytics Platform**: JQL-lite, saved filters, dashboards, evidence-backed analytics, export model.
- **Knowledge Base / Playbook Platform**: case-linked SOPs, playbooks, templates, operator/customer documentation as a product surface.
- **Edge / Developer Platform**: Vasilios-inspired broker/control-plane/gateway layer; keeps provisioning, compiled specs, rate limits, auth, and observability centralized.

### Delivery/quality departments

- **Engineering Factory Manager**: slices non-overlapping implementation work, assigns worktrees/branches, enforces TDD and service-layer reuse.
- **QA / Red Team Director**: codifies invariants, adversarial tests, permissions/workflow/automation safety, degraded-data behavior.
- **Release / Integration Manager**: manages integration trains, verifies manifests, tests branches sequentially, prepares merge notes.
- **SRE / Operations Director**: keeps gateway/cron/worktrees/repo/runtime healthy; owns service health, incident records, postmortems.
- **GTM / Pricing / Packaging**: turns product primitives into sellable SKUs, buyer narrative, demo flow, onboarding, ROI model.

## Durable artifact system

Every nontrivial autonomous unit of work must produce artifacts that can be reviewed without trusting the worker's summary:

1. **Task packet**: objective, owner, bounded context, acceptance criteria, branch/worktree, expected tests.
2. **Design brief or ADR** for cross-boundary work.
3. **Spec/contract** for new primitives, APIs, workflows, connectors, or manifests.
4. **Implementation commit** in an external worktree; parent repo remains clean.
5. **Worker handoff manifest** following `docs/specs/worker-handoff-manifest.md`.
6. **Review report**: spec compliance, quality/security, test evidence, integration risks.
7. **Integration note**: order, conflicts, migration/rollback, release notes.
8. **Decision log** when product strategy or architecture changes.

## Gates

| Gate | Owner | Pass condition | Failure behavior |
|---|---|---|---|
| Intake gate | COO / Product | Work maps to a product pillar and non-overlapping owner | Re-scope or reject |
| Architecture gate | Architecture Board | Bounded context and source-of-truth boundary clear | Require ADR/spec before code |
| Local green gate | Engineering Factory | Focused + broad tests pass in worker worktree | Keep branch unmerged; write blocked manifest |
| Contract/invariant gate | QA / Red Team | New primitive has deterministic tests and adversarial cases | Fix before integration |
| Security/admin gate | Trust/Admin | Permissions, secrets, audit, rate limits reviewed | Block customer-facing surface |
| Integration gate | Release Manager | Manifest verified; branch integrates sequentially; tests pass | Do not batch merge |
| Operability gate | SRE | Health, ledger/audit, logs, degraded state visible | Add runbook/observability before release |
| GTM gate | GTM / Board | Feature maps to sellable package/demo narrative | Keep internal until packaging exists |

## Architecture sequencing

The software architecture should grow in this order:

1. Metric/event semantic registry and evidence definitions.
2. Connector contracts and registry compilation.
3. Runtime/run ledger/audit scaffolds.
4. `OperationalCase` / `WorkItem` model and deterministic lifecycle.
5. Queue/timeline/operator API projections.
6. Workflow automation rules with dry-run and approval gates.
7. Tenant/workspace/project/admin/RBAC/audit export.
8. Search/query/saved filters/dashboards.
9. Ecosystem/app/connector marketplace layer.
10. Service-management/SLA/playbook product surfaces.
11. Edge/developer platform hardening: broker, gateway, rate limits, service catalog, telemetry, provenance.

Video-derived sequencing rule: copy the shape before the infrastructure. For Orvo this means: product contracts and registries first, then a durable request/status ledger, then compiled runtime validation, then shared gateway policies in the existing Python runtime, and only later separate broker/queue/proxy/sidecar infrastructure if scale or team boundaries require it.

## Non-goals for now

- Do not copy Atlassian's complexity before Orvo has stable primitives.
- Do not deploy Envoy/xDS/Keycloak/Prometheus stacks just because they appear in the reference material. First translate the architecture pattern into Orvo's current Python runtime and tests.
- Do not let the video push Orvo into building a generic infrastructure platform before the ecommerce operations primitives are stable: cases, workflows, connector events, semantic registry, operator surfaces, and tenant/admin/audit.
- Do not create more cron jobs from cron-run agents. Organization changes are applied by the human/controller session only.
- Do not allow multiple workers to own the same persistence model or central module.
- Do not let Hito/report-first language override the product control-plane pivot.
