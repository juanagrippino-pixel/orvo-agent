# Architecture Review Board — 2026-06-05

Repository: `/root/orvo-agent`
Reviewed branch: `feat/orvo-brain-control-plane` @ `9c9791d` (`docs: refresh integration train`)
Review mode: read-only code/branch review; no merges, pushes, deployments, or cron changes.
Verification run: `pytest -q` on current HEAD → **1296 passed in 14.13s**.
Git state before report write: clean.

## Executive decision

Current HEAD is architecturally aligned with the accepted Orvo direction: a deterministic Atlassian/Jira-like D2C operations control plane, not a chatbot or shortcut pipeline. The strongest current areas are:

- Operational Cases as the canonical work state, with Jira-like statuses, status categories, transitions, timeline, work-item projections, built-in views, and JQL-lite filtering.
- Semantic/metric registry enforcement across reports, case evidence, surfaces, freshness envelopes, and connector-emitted metrics.
- Connector registry/runtime separation with adapter factories, control-plane config validation, secret-ref boundaries, run ledger outcomes, connector health/rate-limit metadata, and metric validation.
- Workflow/external-action contracts that mostly respect approval gates, idempotency keys, redacted audit, and Orvo-owned control-plane boundaries.
- Internal-operator RBAC/audit hardening through bearer-token checks, business scoping, role permissions, redaction, and bounded audit exports.

The main architectural risks are not product-direction misalignment; they are integration risks from parallel branches and a few incomplete control-plane contracts:

1. Manual operator case mutations are still not idempotent on HEAD. The idempotency branch is directionally correct but should reserve/check the idempotency key before the side effect, not only record after mutation.
2. WorkItem is still a projection over OperationalCase, not a persisted Jira-like issue/work item entity with project/issue-type/workflow scheme versioning. That is acceptable for MVP if documented as a projection, but not enough for the long-term Atlassian-like control-plane core.
3. JQL-lite is safe and useful, but still a limited projection query language rather than a canonical query engine with saved filters, permissions, pagination cursors, and full audit.
4. Gateway/rate-limit policy branches add useful policy manifests, but some enforcement is still contract-only or in-process metadata rather than durable gateway enforcement.
5. Several owner-brief/mainline branches are highly divergent and conflict with the integration train. Do not merge those whole branches; cherry-pick/rebuild the small owner-brief ideas onto current HEAD if still desired.

## Branch disposition

The following was generated from `git for-each-ref`, `git rev-list`, `git diff --name-only HEAD...branch`, and `git merge-tree HEAD branch`.

| Branch | Tip | Merge-tree vs HEAD | ARB disposition | Notes |
|---|---:|---|---|---|
| `codex/eng-factory-manual-case-action-idempotency-20260605` | `d528439` | no conflicts | **Needs work** | Important gap, but records idempotency after mutation. Make ledger reservation/unique insert happen before `transition_case` / `add_comment` / `assign_case`, or move mutation+ledger into one store transaction. |
| `qa/internal-operator-wrong-token-auth-invariant` | `8ea7397` | no unique diff | **Already integrated / no merge needed** | Wrong-token invariant appears covered in current train. |
| `codex/work-management` | `e61e934` | no conflicts | **Candidate after rebase/focused review** | Good Jira alignment: assignment timestamp and WorkItem projection improvements. Still projection-only; do not treat as a durable work-item table. |
| `codex/connector-health-rate-limit-20260605001908` | `7a02299` | no unique diff | **Already integrated / no merge needed** | Current code has `rate_limited` connector health classification and runtime/run-ledger projections. |
| `codex/operator-audit-business-scope-redaction-20260604` | `aa6749b` | no conflicts | **Merge-ready candidate** | Strong security fix: tenant/business scoping for audit lookup using redacted keys. Run focused audit-store tests after merge. |
| `codex/qa-redteam-case-action-payload-redaction-20260604` | `b91d9ec` | no unique diff | **Already integrated / no merge needed** | Denied action payload redaction invariant appears in current train. |
| `codex/trust-admin-security` | `1084c69` | no conflicts | **Merge-ready candidate** | Good trust/admin hardening: best-effort audit for failed internal auth without persisting raw Authorization material. |
| `codex/search-analytics` | `6eb4023` | no conflicts | **Needs split/review before merge** | Useful filters/analytics, but broad across 14 files. Confirm every analytics field is a projection or registered metric; avoid metric drift. |
| `codex/connector-platform` | `60eee38` | no conflicts | **Strategic merge candidate after contract tests** | Strong alignment with connector registry, runtime, execution ledger, metric validation. Broad branch; merge only with contract tests and registry docs review. |
| `codex/workflow-automation` | `f0e003f` | no conflicts | **Candidate after rebase/focused tests** | Good approval-gate cancellation and workflow ledger semantics. Branch is far behind current HEAD; rebase and re-run workflow/external-action tests. |
| `feat/owner-brief-dispatch-policy` | `15e53f3` | conflicts | **Do not merge whole branch** | Branch is 460 commits behind and conflicts across core files. The small dispatch-policy idea is good; cherry-pick/rebuild only onto current operator-brief surface. |
| `feat/spanish-owner-brief-copy` | `f65389e` | conflicts | **Do not merge whole branch** | Spanish WhatsApp copy is product-aligned if derived only from case projections/action keys. Rebuild on current HEAD rather than merging divergent history. |
| `feat/mvp-owner-brief-endpoint` | `6b430c4` | conflicts | **Do not merge whole branch** | Endpoint idea is aligned, but branch is divergent. Integrate as a narrow current-HEAD change if needed. |
| `codex/edge-developer-platform` | `1035f05` | conflicts | **Needs work** | Gateway/service catalog contracts are useful, but conflicts in internal route common/dashboard code. Also separate contract manifest from actual enforced auth/rate-limit/idempotency behavior. |
| `codex/service-management` | `89b4e3d` | no conflicts | **Candidate, lower priority** | Service-management projection is adjacent to Atlassian patterns, but should not distract from D2C Operational Cases/WorkItems unless tied to current operator workflows. |
| `main` | `d5e5e7f` | conflicts | **Do not merge into control-plane train wholesale** | Divergent from `feat/orvo-brain-control-plane`; includes owner-brief/post-purchase research changes and conflicts in core files. |

## 1. OperationalCase / WorkItem against Atlassian patterns

### Alignment

Current HEAD has a credible Jira-like foundation:

- `OperationalCase` is the canonical issue-like entity with `case_id`, `business_id`, `case_type`, `status`, `severity`, `priority_score`, `entity_scope`, assignee fields, timestamps, evidence snapshots, timeline, and metadata.
- Statuses map to Jira-style status categories: `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done`.
- Lifecycle transitions are deterministic and constrained: `open -> acknowledged/in_progress/dismissed`, `acknowledged -> in_progress/resolved/dismissed`, `in_progress -> resolved/dismissed`, and terminal statuses have no manual outgoing transition. Recurrence is handled by detection/upsert reopening terminal cases via `case_reopened`, which keeps runtime detection separate from operator transition authority.
- Timeline events model an issue audit stream: `case_opened`, `case_updated`, `case_reopened`, `status_changed`, `case_assigned`, `evidence_attached`, `operator_comment`; actors are bounded to `system` / `operator`.
- `work_items.py` creates Jira-like projections: business project keys, project projection, case work item id, issue type definitions, status definitions, workflow definition, and status categories. This is the right direction for an Atlassian-like surface while preserving OperationalCase as source of truth.
- Operator surfaces expose built-in read-only case views and JQL-lite filters over canonical case projections rather than generating SQL directly from user input.

### Gaps

- **No durable Project/IssueType/WorkflowScheme entities yet.** Project keys and issue type/status definitions are generated functions, not persisted/versioned control-plane records. This is acceptable for the narrow D2C MVP but limits Atlassian-like extensibility.
- **WorkItem is projection-only.** There is no independent WorkItem store, issue history table, rank, watcher, comment table, link table, or saved filter table. Continue calling it a projection until a true WorkItem aggregate exists.
- **JQL-lite is intentionally limited.** It is safer than SQL passthrough and good for MVP, but it lacks saved filters, cursor pagination, permissioned fields, query audit, and a stable grammar/version contract. Treat it as operator-view filtering, not yet a platform query engine.
- **Manual mutation idempotency remains the top work-management gap.** HEAD applies case actions directly (`add_comment`, `assign_owner`, status transitions) without an idempotency ledger at the operator action boundary.

### ARB requirement before claiming “Jira-like issue platform”

Add an explicit Work Management contract that separates:

1. **Canonical source:** OperationalCase.
2. **Projection:** WorkItem view over OperationalCase for current D2C MVP.
3. **Future aggregate:** persisted WorkItem/Issue entity only when project/issue/workflow schemes and audit migrations are designed.

## 2. Semantic registry as canonical source of truth

### Alignment

The semantic registry is being treated as the canonical source of truth for metrics:

- `MetricDefinition` carries key, family, label, unit, allowed sources, aliases, aggregation, freshness requirement, report/case allowed flags, evidence requirement, and PII class.
- Registry validators cover unknown metrics, allowed source envelopes, family envelopes, required evidence, value kind, PII class, money currency, freshness companion metrics, report-allowed, case-allowed, surface metrics, and freshness envelope metrics.
- Operational case evidence snapshots derive metrics through registry-aware helpers and validate case metric objects through the semantic layer.
- Connector specs declare emitted metric families and validate emitted metric keys/objects against the metric registry. This is the right anti-drift boundary.

### Gaps / watchpoints

- Some analytics/operator branches add new summary/filter fields. Those are acceptable as projections if they remain clearly derived from cases/runs; if any field becomes a business metric, it must be added to the metric registry first.
- Owner brief copy must not invent metric claims. The reviewed owner-brief branches are mostly safe because they summarize `actionable_total`, degraded evidence count, case type, severity, priority score, freshness state, source connectors, and registered action keys. Keep it that way: no revenue/stock/root-cause language unless backed by registered evidence metrics.
- Search/analytics branch needs a metric-drift pass before merge because it is broad and touches run summaries, case projections, JQL views, and internal API contracts.

### ARB rule

Any new numeric business field exposed outside a purely technical projection must answer: **registered metric, derived case/workflow counter, or UI-only label?** If registered metric: add it to the semantic registry and tests first.

## 3. Connector platform separation

### Alignment

Current connector architecture preserves the platform contract:

- `connector_registry.py` owns `ConnectorSpec`, secret requirements, config fields, adapter/report-factory paths, capabilities, emitted metric families, executor metadata, health metadata, rate-limit metadata, scopes, and lifecycle metadata.
- Runtime compilation uses registry specs to produce connector runtime config and projections, keeping compiled runtime in control of connector invocation details.
- Execution/run ledgers capture connector outcomes and health state (`ok`, `stale`, `degraded`, `unauthorized`, `rate_limited`, `failed`) without making adapter response text the canonical control-plane state.
- Secret requirements are expressed as `secret_ref` boundaries, with legacy raw secret config fields flagged separately. This is the right direction for tenant-secret containment.
- Adapter/service/storage separation is mostly preserved: adapters produce data/report factories, registry validates config/metrics, runtime executes, run ledger stores outcomes, semantic registry validates metrics.

### Gaps / watchpoints

- Connector health/rate-limit policy is partly metadata/classification, not a full durable rate-limit enforcement service. Do not market it as enforced throttling until request counters/backoff state are actually persisted/enforced.
- `codex/connector-platform` is strategically strong, but broad. Merge with contract tests and a careful review of backward compatibility for Google Sheets, CSV, Tiendanube, and existing scheduler paths.
- Avoid connector shortcuts that bypass compiled runtime/run ledger/metric registry, especially for WhatsApp/Tiendanube-specific MVP convenience paths.

## 4. Workflow automation, idempotency, approvals, audit

### Alignment

The automation model is close to the desired deterministic contract:

- `workflow_automation.py` supports allowlisted triggers (`case_opened`, `case_updated`, `manual`), bounded condition fields (`status`, `case_type`, `severity`, `min_priority_score`, `degraded`), and action modes/side effects.
- Workflow simulation creates deterministic idempotency keys and projections instead of executing side effects directly.
- `external_actions.py` explicitly keeps Composio/Pipedream-style marketplaces behind Orvo-owned contracts: allowlists, approval gates for writes, pre-side-effect run-ledger audit records, idempotency checks, and redacted summaries.
- External write execution requires an approved `WorkflowActionLedgerRecord` with matching ledger id, idempotency key, provider, and pending execution state.
- Duplicate external action idempotency keys are rejected based on executed/succeeded run outcomes.

### Gaps / watchpoints

- Manual case actions need the same rigor as external actions. Current HEAD lacks a pre-side-effect idempotency reservation for operator case actions.
- The manual-action idempotency branch should not be merged until the ledger write is atomic relative to the case mutation. A duplicate request racing between “check duplicate” and “record ledger” can still apply a second mutation if the side effect happens first.
- Workflow approval cancellation branch is aligned, but old relative to HEAD; rebase and verify it still composes with current external-action ledger schema and tests.
- Consider one generic “mutation command ledger” abstraction for operator case actions, workflow actions, and external actions, instead of separate idempotency behaviors per surface.

## 5. Trust / Admin / Security

### Alignment

Current HEAD is materially better than a typical MVP internal API:

- Internal routes use `ORVO_INTERNAL_OPERATOR_TOKEN` with constant-time bearer comparison and fail closed when not configured.
- Roles are explicit: `viewer`, `operator`, `admin`; permissions include `internal:read`, `case:action`, and `operator_audit:read`.
- Business scoping is enforced through `X-Orvo-Businesses`; explicit grants must include the route business id.
- Operator session projection redacts actor references/business grants when secret-shaped.
- Operator audit store redacts identifiers/data, bounds retention exports, and exposes audit reads as admin-only.
- Recent security branches correctly focus on wrong-token invariants, failed-auth audit without raw token persistence, tenant-scope redaction in audit storage, and denied action payload redaction.

### Gaps / watchpoints

- Current internal auth is still shared-token/header-based. That is fine for internal MVP, but the platform target eventually needs per-operator identity, rotated credentials, and policy-bound service principals.
- Failed-auth audit is best-effort and deliberately does not block fail-closed auth; this is good behavior, but operational alerting around repeated failures is not yet present.
- Gateway policy branch adds useful central metadata, but conflicts and should not be considered enforced gateway infrastructure until real rate-limit/idempotency enforcement is wired into route handling and durable stores.
- Secret boundaries are conceptually strong; keep docs/examples using placeholders only. No raw OAuth/refresh/API tokens should enter review reports, tests, ledgers, or examples.

## Strategic recommendation

1. **Merge security fixes first:** `operator-audit-business-scope-redaction` and `trust-admin-security`, with focused tests.
2. **Fix manual mutation idempotency before more operator-action expansion:** reserve idempotency before mutation or transact case mutation + ledger insert together.
3. **Integrate connector-platform carefully:** it is strategically aligned and should become a core platform layer, but requires contract tests and backward-compatibility review.
4. **Rebase workflow automation:** preserve approval cancellation/idempotency semantics, then test against current external-action ledger behavior.
5. **Keep owner brief as a projection:** rebuild/cherry-pick the small endpoint/Spanish copy/dispatch-policy pieces onto current HEAD; never merge the divergent branches wholesale.
6. **Document WorkItem as projection:** avoid overclaiming Atlassian parity until projects, issue types, workflow/status schemes, and saved filters become first-class persisted control-plane records.

## Final ARB status

- **Current HEAD:** merge-train health is good; full test suite passes.
- **Architecture:** aligned with D2C control-plane strategy.
- **Primary blocker for next wave:** idempotent, audited, pre-side-effect operator mutation ledger.
- **Highest strategic merge candidate:** connector platform after contract validation.
- **Highest security merge candidates:** audit scope redaction and failed-auth audit.
- **Branches to avoid merging wholesale:** divergent owner-brief branches and `main` into the control-plane train.
