# Orvo Architecture Review Board Update — 2026-06-03

## Scope and evidence

Read-only architecture review of the current Orvo Brain control-plane baseline and recent local branches against the accepted architecture: a sellable Atlassian/Jira-like operations control plane for LatAm D2C ecommerce.

Repository reviewed: `/root/orvo-agent`.

Baseline at review time:

- Branch: `feat/orvo-brain-control-plane`
- HEAD: `e6f174b` (`codex: expose handling latency by case type endpoint`)
- Git status before this report write: clean.

Evidence used:

- Current branch list, HEAD log, diff/merge-tree comparisons against `feat/orvo-brain-control-plane`.
- Source inspection of `app/brain/work_items.py`, `app/brain/operational_cases.py`, `app/brain/semantics/metric_registry.py`, `app/brain/connector_registry.py`, `app/brain/runtime.py`, `app/brain/pipeline.py`, `app/brain/secret_refs.py`, `app/brain/workflow_automation.py`, `app/brain/workflow_action_ledger.py`, `app/brain/operator_auth.py`, `app/brain/operator_audit.py`, and operator API histogram/projection modules.
- Branch-specific inspection of `codex/workflow-automation:app/brain/workflow_action_audit.py`, `codex/edge-developer-platform:app/brain/gateway_policy.py`, `codex/edge-developer-platform:app/brain/service_catalog.py`, `codex/trust-admin-security:app/http/internal_brain/common.py`, and `codex/operator-surfaces:app/brain/operator_api/commented_cases.py`.
- Focused baseline tests: `pytest tests/test_work_items.py tests/test_brain_connector_registry.py tests/test_workflow_automation_simulation.py tests/test_internal_operator_api.py tests/contracts/test_metric_registry_contract.py tests/test_operator_dashboard.py -q` -> `110 passed in 6.81s`.

No source code was edited. This markdown report is the only intended write. No cron jobs, pushes, merges, or deployments were performed.

## Executive verdict

The baseline remains architecturally aligned and has improved since the earlier 2026-06-03 review. The most important previously identified WorkItem gap is now fixed in baseline: `project_key_for_business()` uses a deterministic SHA-1 suffix for long project keys rather than simple truncation, reducing Jira-style project-key collision risk while keeping `WorkItem` projection-only.

Current baseline is strongest in these areas:

- `OperationalCase` is still the durable lifecycle source of truth.
- `WorkItem` remains a projection layer over cases, with project, issue type, workflow, and status-category semantics but no duplicate task store.
- Status categories remain canonical Jira-style categories: `to_do`, `in_progress`, `done`.
- JQL/operator views operate over bounded deterministic projections.
- Metric semantics remain centralized in `MetricRegistry` / `CASE_FAMILY_METRICS`; no reviewed branch creates a competing registry.
- Connector execution continues through registry/runtime/ledger/secret-ref boundaries.
- Workflow automation remains conservative: action catalog, idempotency, approval queues/ledger, audit projections, and explicit zero side effects in read/simulation paths.
- Trust surfaces include role/permission checks, business scoping, redaction, and audit denial patterns.

Main remaining ARB concerns:

1. **Operator analytics proliferation.** Ack/handling/resolution histograms by case type, entity kind, source connector, and priority bracket are useful Jira-like views, but they are workflow analytics, not registered business metrics. Keep them out of the semantic metric registry unless product positioning turns them into sellable KPIs.
2. **Gateway policy branch overclaim risk.** `codex/edge-developer-platform` has useful policy/service-catalog contracts, but its own module states it is in-process and not proxy/rate-limit infrastructure. Merge only if framed as contract/enforcement metadata, not complete gateway security.
3. **Workflow execution gap.** Audit/projection/approval foundations are good. External side effects still need executor identity, provider idempotency, attempt ledger, approval-decision audit, RBAC linkage, and retry/failure semantics before production execution.
4. **Shared token identity ceiling.** Current internal bearer token + role headers are acceptable migration scaffolding, but not a production operator identity model.

## Branch merge-readiness summary

Comparison base: `feat/orvo-brain-control-plane` at `e6f174b`.

| Branch | Unique branch commits vs baseline | Merge-tree | ARB verdict | Rationale |
|---|---:|---|---|---|
| `codex/eng-factory-recent-in-progress-20260603` | 1 | Clean | **Merge-ready after focused tests** | Adds a read-only recent in-progress case projection/API. Aligned if it remains derived from canonical case status/timeline. |
| `codex/trust-admin-security` | 3 | Clean | **Merge-ready after focused tests** | Adds audit for invalid operator bearer tokens and strengthens internal API contract docs. Good trust alignment because raw `Authorization` is not persisted; only safe scheme/header metadata is stored. |
| `codex/qa-runtime-config-immutability-20260603` | 1 | Clean | **Merge-ready** | Test-only invariant guarding runtime compile immutability. Directly supports compiled-runtime contract. |
| `codex/operator-surfaces` | 18 | Clean | **Merge-ready after larger operator-suite run** | Adds read-only recently assigned/commented/dismissed/in-progress/reopened surfaces. Strategically aligned with Jira-like operator UX; large diff should be sequenced after smaller recent-case branch to avoid duplication. |
| `codex/search-analytics` | 9 | Clean | **Merge-ready after tests; watch semantics** | Adds view summaries/facets/dashboard analytics. Keep as case/workflow analytics, not hidden business metrics or saved-view state. |
| `codex/connector-platform` | 0 | Clean | **Already absorbed / no action** | No remaining diff; connector lifecycle/health metadata is in baseline. |
| `codex/workflow-automation` | 1 | Clean | **Merge-ready after tests** | Adds workflow action audit event projection from canonical action/approval ledgers with `side_effects_executed = 0`. Strong approval/audit alignment. |
| `codex/work-management` | 8 | Clean | **Merge-ready after tests** | Adds richer issue-type metric requirements, system reopen boundaries, and lifecycle/audit invariants. Aligned with Atlassian workflow patterns and metric registry dependency. |
| `codex/eng-factory-workflow-approval-queue-integration-20260603` | 0 | Clean | **Already absorbed / no action** | No remaining diff; approval queue hardening is in baseline. |
| `codex/qa-internal-route-auth-invariant-20260603` | 1 | Clean | **Merge-ready** | Test-only route auth invariant. Supports trust/admin/security gate. |
| `codex/ack-latency-case-type-endpoint-20260603` | 0 | Clean | **Already absorbed / no action** | Baseline has the case-type ack/latency endpoint work. |
| `codex/qa-auth-scheme-redaction-20260603` | 1 | Clean | **Merge-ready after redaction regression check** | Good invariant coverage for auth scheme redaction, but touches shared redaction helper; run full redaction/operator tests before merge. |
| `codex/edge-developer-platform` | 12 | Clean | **Needs-work / merge only as explicit contract slice** | Gateway policy and service catalog are strategically useful. Do not position as full gateway enforcement/rate limiting. Ensure new permissions, route policy checks, audit, and idempotency behavior are wired consistently before treating as security-critical. |
| `codex/service-management` | 8 | Clean | **Merge-ready after tests; keep projection-only** | Jira Service Management-style projections are directionally good if service records/status/SLA remain projections over cases rather than a second lifecycle source. |
| `codex/eng-factory-project-key-hash-20260603` | 0 | Clean | **Already absorbed / no action** | Baseline now includes deterministic hash suffix project-key hardening. |
| `codex/run-api-secret-ref-boundary-20260602` | 0 | Clean | **Already absorbed / no action** | No remaining diff; run projection redaction boundary is integrated. |
| `codex/qa-action-whitelist-20260602` | 1 | Clean | **Merge-ready** | Test-only invariant around action catalog whitelist/execution ordering. Supports deterministic action platform. |

## 1. OperationalCase / WorkItem vs Atlassian patterns

### Alignment

Current baseline follows the intended Atlassian/Jira pattern without splitting state:

- **Project:** route-owned `business_id` projects to `project_id`, `project_key`, `display_name`, `case_type_scheme_id`, and `workflow_scheme_id`.
- **Project key:** long keys are now stabilized with a deterministic hash suffix.
- **Issue/work item:** `case_id` and projected `work_item_id` identify the item; `OperationalCase` still owns storage.
- **Issue type:** `case_type` projects to `issue_type`.
- **Workflow:** canonical statuses are `open`, `acknowledged`, `in_progress`, `resolved`, `dismissed`.
- **Status categories:** `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done`.
- **Workflow definition:** exposed by `operational_case_workflow_definition()`; tenant customization remains disabled.
- **Query layer:** JQL-lite/operator views remain bounded deterministic filters over case/work-item projections.
- **History/audit:** timeline events continue to represent lifecycle, assignments, evidence attachments, and comments.

### Gaps / guardrails

- Keep `WorkItem` projection-only. Do not introduce a WorkItem table unless it stores board metadata that links back to `case_id`, not lifecycle state.
- Treat system reopen transitions as a separate actor boundary from operator transitions. `codex/work-management` is directionally right here.
- Service-management waiting/SLA states must remain nested projections, not new canonical status categories.
- Avoid any branch that reintroduces alternate status-category vocabulary such as `todo` instead of `to_do`.

## 2. Semantic registry canonical source of truth

### Alignment

`MetricRegistry` remains the canonical semantic layer:

- Canonical keys, aliases, families, units, aggregation, freshness, source permissions, report/case participation, evidence requirements, and PII class remain centralized.
- `CASE_FAMILY_METRICS` remains the source for case-family metric dependencies.
- `OperationalCase` evidence snapshots validate metric payloads and keep owner-facing cases evidence-backed.
- Connector specs list emitted metric families and validate metric objects through registry helpers.
- Recent work-management branch additions use `CASE_FAMILY_METRICS` for issue-type metric requirements instead of local duplicate lists.

### Drift risks

- Histogram and dashboard outputs are case-state/workflow analytics. They should stay outside the business semantic metric registry unless Orvo productizes them as formal KPIs with units, freshness rules, and evidence policy.
- Legacy adapter keys remain acceptable only where aliases resolve deterministically. New connector/report logic should emit canonical keys or include explicit alias tests.
- `channel_mix_shift` remains a deferred case family unless deterministic channel-scoped metrics/evidence and stale-source suppression tests exist.

## 3. Connector platform separation: adapter / service / storage

### Alignment

Current implementation preserves the correct separation:

- `connector_registry.py` owns specs, capabilities, required params/secrets, health/rate-limit/lifecycle metadata, emitted families, and factory metadata.
- Adapter modules remain connector-specific translation code under `app/brain/adapters/`.
- `runtime.py` compiles business config through the registry into a serializable `CompiledBusinessRuntime` with secret refs, not raw values.
- `runner.py` records compiled runtime metadata in the run ledger before execution.
- `secret_refs.py` resolves raw values only at the execution boundary for legacy adapter compatibility.
- Storage remains ledger/config/case-store owned, not adapter-owned.

### Gaps / guardrails

- The pipeline still carries connector-specific service binding parameters (`tiendanube_http_client`, `mercadolibre_http_client`, etc.). This is acceptable compatibility shim work, but future connectors should move toward a typed connector execution context.
- Rate-limit and lifecycle metadata are declarative unless enforced by execution/gateway code.
- Keep `secret://...` references internal. Operator-facing projections should show redacted refs while preserving safe connector id/type metadata.

## 4. Workflow automation: idempotency, approval gates, audit

### Alignment

Workflow automation is correctly conservative:

- Action keys come from `ACTION_CATALOG`.
- Idempotency keys are deterministic.
- Duplicate planned actions are skipped.
- Approval-required actions are blocked with explicit approval state.
- Ledger and approval request projections are durable and redacted.
- Branch `codex/workflow-automation` adds audit-event projection only; it declares `side_effects_executed = 0` and reads canonical ledgers.

### Required before side effects

Do not add external action execution until these are in place:

- Executor actor identity and permission model.
- Execution-attempt ledger linked to action record and approval request.
- Provider idempotency key per external action.
- Approve/reject/execute/fail/deny audit event taxonomy.
- Retry/failure semantics and degraded-state behavior.
- Explicit guarantee that WhatsApp/report copy never mutates case lifecycle state.

## 5. Trust / Admin / Security: RBAC, audit trail, secret boundaries

### Alignment

Baseline and reviewed branches move in the right direction:

- Internal bearer-token authentication remains fail-closed when token is absent or invalid.
- Roles map to permissions: `viewer`, `operator`, `admin`.
- Business-scope checks use explicit business grant headers.
- Operator audit events are durable and redacted.
- Error/success envelopes carry `redaction_applied` semantics.
- `codex/trust-admin-security` correctly audits invalid token attempts without persisting the raw authorization header.
- Redaction helpers cover secret refs, token-like strings, query parameters, and URL userinfo credentials.

### Gaps / guardrails

- Shared token + role headers are not a production identity provider. Before live external/admin exposure, move to signed gateway principals or an operator identity provider with durable grants.
- Gateway policy branch must not be treated as abuse protection until rate limits and enforcement are implemented across routes.
- If forensic audit ever requires raw payload fidelity, store encrypted privileged audit payloads with break-glass controls; never plaintext secrets.

## Strategic recommendations for the next merge train

1. **Merge small low-risk branches first:** `codex/qa-runtime-config-immutability-20260603`, `codex/qa-internal-route-auth-invariant-20260603`, `codex/qa-action-whitelist-20260602`, then `codex/eng-factory-recent-in-progress-20260603`.
2. **Merge trust/workflow improvements after focused suites:** `codex/trust-admin-security`, `codex/workflow-automation`, `codex/qa-auth-scheme-redaction-20260603`.
3. **Merge larger operator/work-management surfaces after full operator suite:** `codex/operator-surfaces`, `codex/search-analytics`, `codex/work-management`, `codex/service-management`.
4. **Reframe before merge:** `codex/edge-developer-platform`; accept as policy/service-catalog scaffolding unless route enforcement, idempotency, rate-limit, and audit linkage are proven.
5. **Archive absorbed branches:** `codex/connector-platform`, `codex/eng-factory-workflow-approval-queue-integration-20260603`, `codex/ack-latency-case-type-endpoint-20260603`, `codex/eng-factory-project-key-hash-20260603`, and `codex/run-api-secret-ref-boundary-20260602`.

## Final ARB position

Orvo remains aligned with the accepted product direction: a D2C ecommerce operations control plane with Jira-like work management, deterministic metric semantics, connector/runtime/ledger governance, and trust-first operator surfaces. The architecture is not drifting toward a generic chatbot or generic agent platform. The highest-value next step is consolidation: keep one case/work-item lifecycle, one metric registry, one connector/runtime path, one action catalog/approval ledger, and one trust boundary model.
