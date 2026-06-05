# Architecture Review Board — 2026-06-05 cron review

Repository: `/root/orvo-agent`
Reviewed baseline: `feat/orvo-brain-control-plane` @ `e67fa3a` (`codex: expose resolution latency source endpoint`)
Review timestamp: `2026-06-05T17:21:34Z`
Review mode: architecture/code/branch inspection only; no merges, pushes, deployments, or cron changes.

## Executive decision

The current control-plane train remains architecturally aligned with Orvo's accepted direction: a deterministic D2C ecommerce operations control plane with Atlassian/Jira-like work management primitives, not a chatbot or report-script shortcut.

Since the prior ARB checkpoint (`9c9791d`), the train improved in three important areas:

1. **Manual operator case-action idempotency moved in the right direction.** `apply_case_action_with_idempotency` now reserves a `workflow_action_ledger` record with `pending_execution` before mutating the case, returns `skipped_duplicate` for replay of executed actions, and blocks pending/failed duplicate keys with `409` responses.
2. **Trust/admin/security hardening landed.** Internal envelope route `business_id` echoes now redact secret-shaped path values, failed/missing internal auth probes are audited without raw `Authorization` persistence, and operator-audit business scope uses deterministic hash keys plus redacted display IDs.
3. **Operator analytics remain projection-oriented.** Resolution/handling latency endpoints split by case type, entity kind, source connector, and priority bracket are derived from OperationalCase state/evidence; they do not introduce business metric drift.

ARB status: **baseline is aligned and usable as the current merge-train base**, with two strategic caveats:

- WorkItem is still explicitly a projection over OperationalCase, not a persisted Jira issue aggregate with project/issue/workflow schemes.
- Manual case-action idempotency is now pre-side-effect, but the ledger update to `executed` and the case mutation are not yet a single transactional command boundary; a crash after mutation but before ledger update can leave a retry blocked as `pending_execution` even though the side effect happened.

## Branch disposition

Generated from `git for-each-ref`, `git rev-list`, `git diff --name-only HEAD...branch`, and `git merge-tree HEAD branch` against `HEAD=e67fa3a`.

| Branch | Tip | Ahead/behind vs HEAD | Merge-tree | ARB disposition | Notes |
|---|---:|---:|---|---|---|
| `feat/orvo-brain-control-plane` | `e67fa3a` | baseline | n/a | **Current baseline / aligned** | Keep as integration base. Recent manual idempotency and security fixes are directionally correct. |
| `codex/run-artifact-route-validation-20260605170229` | `e67fa3a` | 0/0 | clean | **Already integrated** | Same commit as HEAD. |
| `codex/eng-factory-trust-admin-security-integration-20260605` | `a1a661f` | 0/1 | clean | **Already integrated** | Its unique security changes are in HEAD. |
| `codex/handling-latency-entity-endpoint-20260605135531` | `8618128` | 0/5 | clean | **Already integrated** | No unique diff vs current train. |
| `codex/resolution-entity-kind-endpoint-20260605104805` | `d5d99e7` | 0/12 | clean | **Already integrated** | No unique diff vs current train. |
| `codex/eng-factory-manual-action-preledger-current-20260605` | `0c41e9e` | 0/7 | clean | **Already integrated** | Pre-ledger idempotency fix is on HEAD. |
| `codex/trust-admin-security` | `6cc925f` | 1/4 | clean | **No merge needed / stale duplicate** | Tip is superseded by integrated `a1a661f`; do not merge the older branch. |
| `qa-case-action-idempotency-20260605150417` | `479f8f1` | 1/4 | conflicts | **No merge needed unless test gap remains** | The idempotency invariant appears covered on HEAD; branch conflicts in action/store/test files. Cherry-pick only if it contains a missing edge-case test. |
| `qa/case-action-idempotency` | `0284ea2` | 1/12 | conflicts | **Stale / do not merge whole branch** | Older idempotency shape conflicts with current pre-ledger implementation. |
| `codex/connector-platform` | `a723b70` | 6/4 | clean | **Strategic merge candidate, needs focused review/tests** | Adds event-family certification and connector registry/runtime refinements. Architecturally aligned; merge after contract tests and backward compatibility checks for Google Sheets, CSV, Tiendanube, scheduler, and run ledger. |
| `codex/work-management` | `14ede6d` | 17/6 | clean | **Candidate after focused review** | Good Atlassian alignment around actor types/work-item projection. Keep WorkItem projection-only; do not imply durable Jira parity. |
| `codex/workflow-automation` | `121440f` | 7/8 | clean | **Candidate after rebase/focused tests** | Approval-gate direction is aligned. Rebase onto the new manual-action ledger shape before merging. |
| `codex/operator-surfaces` | `0810814` | 28/4 | conflicts | **Needs split/rebase** | Contains useful suggested-action/owner-brief surface ideas, but broad and conflicting. Rebuild narrow projections on current HEAD. |
| `codex/search-analytics` | `b0e5881` | 15/4 | conflicts | **Needs work / metric-drift pass** | Useful JQL/view analytics, but conflicts and broad projection changes. Confirm every numeric field is workflow-derived or semantic-registry-backed. |
| `codex/edge-developer-platform` | `34541e9` | 18/18 | conflicts | **Needs work** | Gateway/service catalog contracts are useful but conflict with internal route/common code; separate manifest docs from enforced auth/rate-limit/idempotency behavior. |
| `codex/service-management` | `1375628` | 10/16 | clean | **Lower-priority candidate** | Adjacent to Atlassian service-management concepts, but only merge if directly tied to D2C operator workflows; avoid broadening away from ecommerce cases. |
| `main` | `d5e5e7f` | 7/476 | conflicts | **Do not merge wholesale** | Divergent research/owner-brief line; cherry-pick only explicitly desired docs or product insights. |

## 1. OperationalCase / WorkItem vs Atlassian patterns

### Alignment

- `OperationalCase` remains the canonical issue/work object. It carries business scope, case type, deterministic status, severity, priority score, entity scope, evidence snapshots, source run IDs, timestamps, assignee fields, and timeline.
- Status categories exist and match Jira concepts: `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done`.
- Workflow transitions are constrained in code, and terminal manual actions require reasons.
- Timeline events provide an issue audit stream. Actor types are bounded, and timeline fields are redacted by model validators.
- `app/brain/work_items.py` explicitly says WorkItem is a projection/registry layer over OperationalCase and exposes project key, issue type, workflow definition, status definitions, and status category without creating a competing task store.
- JQL-lite/built-in views are bounded projections over case fields, not SQL passthrough.

### Gaps

- **WorkItem is not a durable Jira issue aggregate.** There are no persisted Project, IssueTypeScheme, WorkflowScheme, StatusScheme, board, saved filter, rank, watcher, comment table, or issue-link records. This is acceptable for the MVP only if presented as projection semantics.
- **Project keys are derived from `business_id`, not governed project records.** This is good enough for a D2C tenant surface, but not a full Atlassian control-plane object model.
- **JQL-lite is a safe operator filter, not a platform query engine.** It still lacks saved filters, query audit, permissions-per-field, cursor pagination, grammar versioning, and cross-project semantics.
- **Severity taxonomy is still compact (`info`, `warning`, `critical`) while docs describe richer levels.** This is not blocking, but future Work Management should decide whether Jira-like priority/severity schemes are configurable or fixed.

### ARB call

**Merge-ready as MVP projection architecture.** Do not market or document it as a full Jira-like issue platform until durable project/issue/workflow scheme records exist.

## 2. Semantic registry as canonical source of truth

### Alignment

- `MetricRegistry` and `MetricDefinition` remain the canonical registry for semantic business metrics, including aliases, allowed sources, units, aggregation, freshness, report/case flags, evidence requirements, and PII class.
- `CASE_FAMILY_METRICS` keeps owner-facing case families tied to registered canonical metrics.
- Operational case evidence construction validates case metrics through the semantic layer and restricts evidence metrics to allowed case-family keys.
- Connector registry validation checks emitted metric families/objects against the metric registry.
- New resolution/handling/acknowledgment latency splits are workflow analytics derived from OperationalCase lifecycle timestamps/evidence, not new commerce metrics. They should remain labeled as case/workflow analytics.

### Gaps / drift risks

- `codex/search-analytics` adds broad run/case summary fields and JQL facets. Before merge, classify each numeric field as one of: registered business metric, deterministic case/workflow counter, or UI-only projection label.
- `codex/connector-platform` adds connector event-family certification that is not in current HEAD. That is directionally correct and should reduce drift in event semantics, but it must come with contract tests and docs synchronization.
- Owner-facing copy branches must not turn workflow counters (`evidence_count`, latency buckets, priority score) into unsupported revenue/stock/root-cause claims.

### ARB call

**Current HEAD passes the semantic-source-of-truth test.** The most important next guard is a metric-drift review before merging search/analytics or owner-copy branches.

## 3. Connector platform: adapter / service / storage separation

### Alignment

- `connector_registry.py` owns connector metadata: adapter module/factory, capabilities, emitted metric families, config fields, secret requirements, health metadata, rate-limit metadata, scopes, and lifecycle metadata.
- Runtime/pipeline paths use the registry to select connector factories instead of embedding all adapter calls directly in HTTP routes.
- Adapter execution remains separate from run-ledger storage; execution metadata and connector health are recorded as control-plane outcomes.
- Secret refs are treated as execution-boundary inputs, and legacy raw secret fields are documented as transitional.

### Gaps

- `ConnectorSpec` on HEAD still lacks emitted event-family certification; that exists on `codex/connector-platform` and should be merged after tests.
- Rate-limit metadata is not durable enforcement. It should not be represented as real throttling until counters/backoff state are persisted/enforced.
- Some internal routes proliferate one endpoint per analytics split. This is acceptable for early operator surfaces, but a longer-term service layer should avoid duplicating authorization/envelope/query mechanics per route.

### ARB call

**Connector architecture is aligned, but `codex/connector-platform` is the next strategic integration candidate.** Merge carefully with contract tests rather than rewriting adapter paths.

## 4. Workflow automation: idempotency, approvals, audit

### Alignment

- Manual case-action idempotency now records a durable `WorkflowActionLedgerRecord` before the side effect when `X-Idempotency-Key` is present.
- Duplicate executed manual actions replay the current case and return `data.action.status = "skipped_duplicate"` without adding timeline events.
- Duplicate pending/failed keys fail closed with safe `409` errors.
- Failed validation does not consume an idempotency key.
- External workflow/action modules continue to treat side-effecting integrations as gated, audited, Orvo-owned commands rather than direct marketplace shortcuts.
- Approval request records and approval decisions are redacted and do not execute side effects directly.

### Gaps

- **Manual case action ledger + case mutation are not one atomic transaction.** The new order is correct (reserve before mutate), but a process failure after case mutation and before marking the ledger `executed` leaves a conservative `pending_execution` replay. Next step: one transaction/command store boundary or a reconciliation routine that can prove the mutation happened.
- Manual actions without an idempotency key still execute directly. This is acceptable for compatibility, but live operator clients should be required to send keys for mutating actions.
- Workflow approval branches must be rebased onto the current shared ledger schema to avoid divergent execution-state semantics.

### ARB call

**No longer a merge blocker for the current MVP train, but still needs transactional hardening before high-volume or externalized operator use.**

## 5. Trust / Admin / Security: RBAC, audit trail, secret boundaries

### Alignment

- Internal auth still fails closed when `ORVO_INTERNAL_OPERATOR_TOKEN` is missing and uses constant-time bearer comparison.
- Roles are explicit: `viewer`, `operator`, `admin`; permissions include `internal:read`, `case:action`, and `operator_audit:read`.
- `X-Orvo-Businesses` enforces explicit business grants when present, while legacy no-header callers remain token-scoped during migration.
- Internal envelopes redact secret-shaped `business_id` path values and request IDs.
- Authentication/authorization denials are audited without raw bearer tokens, raw grant headers, or secret-shaped business identifiers.
- Operator audit persistence now separates redacted display ID from hashed scope key via `audit_scope.py`.
- Case/timeline/evidence models redact secret-shaped strings, URIs, metadata, assignee refs, actor refs, and artifacts.

### Gaps

- Auth is still shared-token/header-based, not per-operator identity with rotated credentials and policy-bound service principals.
- Failed-auth audit is best-effort and intentionally non-blocking; alerting/rate limiting for repeated probes is not implemented.
- RBAC is static in code, not a tenant-admin policy model.
- Gateway/rate-limit/idempotency policy is not yet enforced consistently at an edge layer.

### ARB call

**Security posture is strong for an internal MVP control plane, not yet sufficient for broad external admin exposure.** Keep internal-only until per-operator identity, durable rate limits, and audit alerting mature.

## Strategic recommendations

1. **Keep `e67fa3a` as the current integration base.** It incorporates the important security and manual idempotency fixes from the last review cycle.
2. **Merge `codex/connector-platform` next if focused contract tests pass.** It fills an actual connector-platform gap: emitted event-family certification.
3. **Rebase/split `codex/workflow-automation`.** Preserve approval-gate semantics but align execution states and idempotency handling with the now-integrated manual-action ledger.
4. **Treat `codex/work-management` as additive projection hardening.** Do not use it to claim persisted Jira parity.
5. **Do not merge `codex/operator-surfaces` or `codex/search-analytics` wholesale.** Rebuild narrow slices after a metric-drift and route-duplication review.
6. **Require idempotency keys for live mutating operator clients.** Compatibility can remain, but production operator UIs should always send keys.
7. **Plan a transaction boundary for case-command mutations.** The next architecture increment should make ledger reservation, case mutation, audit/timeline append, and ledger completion recoverable as one command.

## Final ARB status

- **Current baseline:** architecturally aligned and improved since prior review.
- **Merge-ready / already integrated:** current security/idempotency/resolution-latency work on `feat/orvo-brain-control-plane`.
- **Highest strategic candidate:** `codex/connector-platform` after focused tests.
- **Highest workflow candidate:** `codex/workflow-automation` after rebase and ledger-schema alignment.
- **Needs split/rework:** `codex/operator-surfaces`, `codex/search-analytics`, `codex/edge-developer-platform`.
- **Do not merge wholesale:** stale QA/idempotency branches and `main` into the control-plane train.
