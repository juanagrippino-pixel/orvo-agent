# Orvo Architecture Review Board — Branch Alignment Review — 2026-06-02

## Scope and evidence

Read-only architecture review of recent Orvo Brain/control-plane branches against the target architecture: a sellable Atlassian/Jira-like operations control plane for LatAm D2C ecommerce.

Repository reviewed: `/root/orvo-agent`.

Baseline at review time:

- Branch: `feat/orvo-brain-control-plane`
- HEAD: `9aca5fe` (`feat: add external action provider boundary`)
- Git status before this report write: clean, branch ahead of `origin/feat/orvo-brain-control-plane` by 3 commits.

Commands/evidence used:

- `git status --short --branch`
- `git rev-parse --short HEAD`
- `git diff --name-status feat/orvo-brain-control-plane...<branch>`
- `git diff feat/orvo-brain-control-plane...<branch> -- <target files>`
- `git rev-list --left-right --count feat/orvo-brain-control-plane...<branch>`
- `git merge-tree feat/orvo-brain-control-plane <branch>`
- Targeted reads of control-plane implementation and contracts, including `app/brain/operational_cases.py`, `app/brain/operator_views.py`, `app/brain/operator_api/*`, `app/brain/workflow_automation.py`, `app/brain/workflow_action_ledger.py`, `app/brain/external_actions.py`, `app/brain/connector_registry.py`, `app/brain/runtime.py`, `app/brain/run_ledger.py`, `app/brain/operator_auth.py`, `app/brain/operator_audit.py`, `app/brain/security/redaction.py`, and relevant specs under `docs/specs/`.

No source code was edited. This markdown report is the only intended write.

No full test suite was run during this review. Branch verdicts below are architectural verdicts; merge-ready branches still require their normal targeted tests plus `pytest -q` in the branch/worktree before merge.

## Executive verdict

The current control-plane baseline is directionally sound: `OperationalCase` is the canonical work item, JQL-lite is a safe projection/query layer, semantic metrics are registry-backed, connectors are registry/runtime-ledger driven, workflow automation is ledger/idempotency/approval oriented, and internal trust surfaces have RBAC + audit + redaction foundations.

The main architectural risk in the recent branches is **semantic duplication**, not missing effort. Several branches add overlapping Jira-like concepts:

- `codex/eng-factory-work-item-status-category-20260602` introduces a fuller WorkItem/project/issue-type/workflow/status-category projection.
- `codex/status-category-jql-20260602` introduces a narrower status-category/JQL slice but uses a different category key (`todo` vs `to_do`).
- `codex/service-management` introduces owner-facing/service-management statuses and a `waiting` status category that must not collide with canonical work-item status categories.

ARB recommendation: make the WorkItem/status-category layer a single canonical additive registry/projection, then rebase service-management and analytics surfaces on top of that. Do not merge multiple status-category vocabularies.

## Branch merge-readiness summary

| Branch | Diff vs baseline | Merge-tree | ARB verdict | Notes |
|---|---:|---:|---|---|
| `codex/workflow-automation` | `5 / 0`; no remaining diff shown by `diff --name-status` | Clean | **Already absorbed / no action** | Workflow automation foundations appear present in baseline. Continue with executor ledger only after approval/idempotency invariants remain intact. |
| `codex/eng-factory-audit-export-admin-20260602` | `24 / 2` | Clean | **Superseded/mostly absorbed** | Baseline already has admin-only audit export. Keep only if a rebase shows missing tests or docs. |
| `codex/trust-admin-security` | `5 / 1` | Clean | **Merge-ready after tests** | Adds bounded audit export retention (`retention_days <= 90`) and safe error handling. Strong trust/admin alignment. |
| `qa/redaction-url-userinfo-20260602131915` | `5 / 1` | Clean | **Merge-ready after invariant tests** | Redacts URL userinfo credentials while preserving host/path/safe query. Good secret-boundary hardening. |
| `codex/connector-platform` | `5 / 5` | Clean | **Merge-ready with one boundary check** | Registry-driven daily connector discovery and metadata are aligned. Ensure raw `secret_refs` handles from `runtime_run_metadata()` never cross public/operator API boundaries unredacted. |
| `codex/eng-factory-work-item-status-category-20260602` | `3 / 1` | Clean | **Preferred WorkItem/status-category branch; merge-ready after tests/polish** | Best aligned with Atlassian primitives: project key, issue type, workflow definition, status category, JQL fields. Use this as canonical direction. |
| `codex/status-category-jql-20260602` | `7 / 1` | Clean | **Needs consolidation / likely superseded** | Adds useful `status_category` JQL, but uses `todo` rather than `to_do` and lacks project/workflow projection. Do not merge alongside WorkItem branch without unifying vocabulary. |
| `codex/operator-surfaces` | `5 / 13` | Clean | **Merge-ready after tests** | Adds recently-in-progress and recently-dismissed read-only projections. Aligned if they remain projections over `OperationalCase.timeline` and do not become state. |
| `codex/search-analytics` | `5 / 6` | Clean | **Merge-ready after tests** | Adds view totals/export and actionable/unassigned predicates. Aligned as read-only JQL/projection analytics. Ensure export remains redacted and scoped. |
| `codex/service-management` | `17 / 4` | Clean | **Needs work before merge** | Valuable Jira Service Management projection, but `waiting` must be namespaced as owner/service status, not canonical WorkItem status category. Integrate after WorkItem categories are canonical. |
| `codex/work-management` | `7 / 4` | Clean | **Selective merge-ready after tests** | Valuable invariants: monotonic mutation timestamps, first-ack preservation, owner-facing evidence gate, idempotent assignment. Review assignee redaction tradeoff before merge. |

## 1. OperationalCase / WorkItem versus Atlassian patterns

### Current baseline alignment

`OperationalCase` already follows the core Jira work-item pattern:

- Tenant/workspace scope: `business_id`.
- Work-item identity: `case_id`, `dedupe_key`.
- Issue type analogue: `case_type`.
- Workflow statuses: `open`, `acknowledged`, `in_progress`, `resolved`, `dismissed`.
- Workflow rules: hardcoded transition table, terminal-state restrictions, operator terminal reasons.
- Audit/history: timeline events including open/update/reopen/status change/assignment/evidence/comment.
- Evidence backing: evidence refs, snapshots, source run IDs, artifact refs, semantic evidence metrics.
- Query layer: safe JQL-lite parsing over projections, not raw SQL.
- Action catalog: central registered action keys rather than arbitrary operator verbs.

This is the correct deterministic core. Reports/WhatsApp text remain projections, not workflow state.

### Gaps still present in baseline

1. **Project is not first-class.** `business_id` currently doubles as tenant and project. That is acceptable for the first D2C wedge, but Atlassian-like scale needs a stable project projection/model: `project_id`, `project_key`, `business_id`, `case_type_scheme_id`, `workflow_scheme_id`.

2. **Status category is not yet canonical in baseline.** Dashboards infer actionable/done from status sets. The platform should publish a small immutable mapping: `open -> to_do`, `acknowledged/in_progress -> in_progress`, `resolved/dismissed -> done`.

3. **Workflow scheme is still only a hardcoded transition table.** For v1 this is acceptable, but the platform should expose it as an internal deterministic workflow definition before adding customization.

4. **JQL-lite needs canonical WorkItem fields.** Add `project`, `issue_type`, `status_category`, and assignee fields only through the canonical WorkItem projection/registry to avoid one-off dashboard predicates.

### Branch findings

#### `codex/eng-factory-work-item-status-category-20260602` — preferred direction

This branch adds `app/brain/work_items.py` as an additive projection layer over `OperationalCase`. It introduces:

- `project_key_for_business()` and `project_projection()`.
- Work item ID projection: `<PROJECT_KEY>:<case_id>`.
- `issue_type` derived from `case_type`.
- Canonical status categories: `to_do`, `in_progress`, `done`.
- Status definitions with `actionable`, `terminal`, and transition metadata.
- Workflow definition with `tenant_customizable: False`.
- JQL fields: `project`, `issue_type`, `status_category`, `assignee_ref`.
- Queue/detail projections that include WorkItem fields without creating a parallel store.

ARB verdict: **merge-ready after tests/polish** and preferred over the narrower status-category branch. It matches Atlassian primitives while preserving `OperationalCase` as source of truth.

Required polish:

- Keep the WorkItem layer explicitly read-only/projection-only.
- Add or confirm tests for project-key normalization/truncation collisions.
- Confirm naming: use one category key, preferably `to_do`, consistently across code/docs/tests.
- Do not create a separate WorkItem persistence table until there is a concrete need; `OperationalCase` remains canonical.

#### `codex/status-category-jql-20260602` — consolidate, do not merge independently

This branch adds `OperationalCaseStatusCategory`, `operational_case_status_category()`, projection fields, and `status_category` in JQL-lite.

Architectural issue: it uses `todo`, while the WorkItem branch uses `to_do`. This is exactly the kind of semantic drift the platform must avoid.

ARB verdict: **needs consolidation / likely superseded**. Salvage tests or small implementation pieces only after choosing the canonical status-category vocabulary.

#### `codex/service-management` — valuable but needs category namespace fix

This branch adds Jira Service Management-style projections: record types (`incident`, `service_request`, `problem`, `change`), owner-facing statuses, SLA clocks, and deterministic escalation reasons.

What is aligned:

- Read-only projection over `OperationalCase`.
- Deterministic SLA calculations from timestamps.
- No lifecycle mutation.
- Secret redaction at projection boundary.
- Tenant-scoped internal endpoint.

Architectural issue:

- Owner/service status returns `status_category: waiting` for `waiting_owner` / `waiting_external`. That must not be confused with canonical WorkItem status categories (`to_do`, `in_progress`, `done`). Jira Service Management can have customer-visible/service statuses, but they should be named separately, e.g. `owner_status_category` or `service_status_category`, not `status_category` if the canonical WorkItem field exists.

ARB verdict: **needs work before merge**. Rebase it after the WorkItem/status-category branch and namespace service-management status categories clearly.

## 2. Semantic registry as canonical source of truth

### Current baseline alignment

The semantic registry remains the canonical metric source:

- `MetricRegistry` owns canonical keys, aliases, allowed sources, families, units, aggregation, freshness, report/case permissions, and PII class.
- `CASE_FAMILY_METRICS` ties detections/case families to semantic metrics.
- Connector registry validates emitted metric families/sources through semantic registry helpers.
- Operational cases carry evidence snapshots/metrics and do not let LLM/report text invent metrics.

### Branch findings

No reviewed recent branch introduces a new competing metric registry or obvious metric-source bypass.

- WorkItem/status-category branches add workflow/query semantics, not metrics.
- Operator-surface/search/service-management branches compute projections from case state/timestamps, not new business metrics.
- `codex/connector-platform` adds connector metadata and health/rate-limit policy, not metric definitions.

### Remaining drift risks

1. Adapter-local legacy keys still exist and rely on aliases. This is tolerable for transition but should not expand.
2. Operational-case dedupe/evidence suffix strings can drift from registry family names if copied manually.
3. Dashboard/service projections should avoid inventing metric-like names that later compete with registry metrics. If a projection becomes a product KPI, register it or clearly mark it as workflow analytics derived from case state.

ARB recommendation: enforce “new metric keys are registry-first.” New adapters should either emit canonical keys directly or include tests proving each legacy emitted key resolves through `default_metric_registry()`.

## 3. Connector platform: adapter / service / storage separation

### Current baseline alignment

The platform separation is mostly correct:

- Connector definitions live in `connector_registry.py`.
- Runtime compilation is in `runtime.py`.
- Scheduled/forced execution planning is in `runner.py` / runtime scripts.
- Run persistence is in `run_ledger.py` / `execution_ledger.py`.
- Adapter factories remain in adapter modules.
- Secrets are referenced through secret refs and redacted at persistence/projection boundaries.

### `codex/connector-platform`

This branch is now architecturally aligned in intent and merge-tree clean. It adds:

- `ConnectorHealthMetadata.allowed_states` with stable states: `ok`, `degraded`, `stale`, `unauthorized`, `rate_limited`, `failed`.
- Serializable health/rate-limit/lifecycle metadata methods on `ConnectorSpec`.
- Registry-driven daily connector discovery in `_enabled_daily_connector_types()` instead of a hardcoded supported set.
- Connector metadata in `runtime_run_metadata()`.
- Run-ledger-specific redaction of `secret_refs` values before persistence.
- Tests around connector metadata discovery and secret-ref redaction.

ARB verdict: **merge-ready with one boundary check**.

Boundary check:

- `runtime_run_metadata()` includes `connector_refs[*].secret_refs` as raw `secret://...` handles before ledger redaction. That may be acceptable as internal compiled-runtime metadata, but only if no public/operator API returns it unredacted. Add/keep contract tests that prove persisted run ledger records and API projections replace secret-ref URI values with `[REDACTED]` while preserving safe metadata such as `secret_param_names`.

Do not regress:

- Adapter factory validation should remain stronger than “callable exists.” Preserve worker/daily-report adapter contracts.
- No connector endpoint should bypass connector registry, runtime compilation, run ledger, or semantic metric validation.

## 4. Workflow automation: idempotency, approval gates, audit

### Current baseline alignment

The baseline is strong and now includes an external action provider boundary:

- Workflow action records have durable idempotency keys.
- Approval-required actions are gated and do not execute side effects automatically.
- Simulation remains no-side-effect.
- Action params are redacted before persistence/projection.
- Action keys come from `ACTION_CATALOG`.
- Provider boundaries in `external_actions.py` separate external action execution from planning/audit.

### Branch findings

#### `codex/workflow-automation`

No remaining diff was shown against the current baseline; it appears absorbed. Continue to treat approval decisions as audit/gating state, not execution authority.

#### `codex/work-management`

This branch adds useful work-management invariants:

- Rejects backdated mutation timestamps so timeline/audit order cannot be rewound.
- Preserves first `acknowledged_at` when moving from acknowledged to in-progress, protecting time-to-ack metrics.
- Makes repeated assignment to the same redacted assignee idempotent/no-op.
- Excludes legacy owner-facing cases with no evidence snapshots.

ARB verdict: **selective merge-ready after tests**.

Review point before merge:

- The branch redacts `assignee_ref` before storing it. This is safe for secrets, but product/admin workflows may need stable non-secret assignee identifiers. If real operator IDs are expected, prefer validating/storing opaque safe IDs (`operator:<id>`, `team:<id>`) and redacting only secret-shaped substrings, not collapsing all assignee values to `[REDACTED]`.

Future workflow executor requirements:

- Explicit executor identity and RBAC permission.
- Execution-attempt ledger linked to approval record.
- External idempotency key per provider/action.
- Dry-run parity.
- Retry/failure semantics.
- Redacted audit events for approval, execution, failure, and denial.

## 5. Trust / Admin / Security: RBAC, audit, secret boundaries

### Current baseline alignment

The trust/admin/security layer has a useful v1 foundation:

- Internal auth separates token authentication from role/permission projection.
- Roles include `viewer`, `operator`, `admin`.
- Permissions include internal read, case action, and operator audit read.
- Case actions enforce mutation permission.
- Operator audit events are persisted and business-scoped.
- Internal API envelopes are safe and include `redaction_applied=true`.
- Secret redaction covers headers, query params, token-like keys, OAuth code patterns, and persisted audit payloads.

### `codex/trust-admin-security`

This branch extends audit export safety:

- Adds bounded audit retention defaults/max (`90` days).
- Rejects invalid or abusive `retention_days` values.
- Filters audit export by `created_at >= cutoff`.
- Keeps redacted response envelopes.

ARB verdict: **merge-ready after tests**. This strengthens admin trust controls without weakening audit persistence.

### `qa/redaction-url-userinfo-20260602131915`

This branch hardens `redact_uri()` so credentials embedded in URL userinfo are replaced with `[REDACTED]@host` while preserving safe host/path/query context.

ARB verdict: **merge-ready after invariant tests**. This is a direct secret-boundary improvement.

### Remaining security gaps

1. **Business authorization grants are still header/token-level.** Route scoping exists, but there is no durable operator-to-business grant store yet.
2. **Audit denials should be uniformly logged.** Ensure auth failures, permission denials, invalid action attempts, and approval denials all produce safe audit records where appropriate.
3. **Permission registry is still constants.** This is fine for v1, but should become registry-backed when role/permission count grows.
4. **Secret refs should be treated as sensitive handles on external surfaces.** Even if not raw tokens, they reveal tenant/connector topology. Persisted/exported/operator API metadata should redact values and preserve only parameter names or safe labels.

## Operator surfaces and analytics

### `codex/operator-surfaces`

Adds recently-in-progress and recently-dismissed projections/endpoints. This is aligned because it derives timestamps from canonical case timeline/terminal timestamps and returns read-only scoped projections.

ARB verdict: **merge-ready after tests**.

Requirements to preserve:

- Recently-in-progress must derive from the `status_changed` timeline event, not comments or UI updates.
- Recently-dismissed must use `dismissed_at` and not infer terminal state from report text.
- Responses must remain redacted and business-scoped.

### `codex/search-analytics`

Adds built-in view totals, export rows, actionable/unassigned predicates, and dashboard totals. This is aligned as an Atlassian-like saved-view/search analytics layer.

ARB verdict: **merge-ready after tests**.

Requirements to preserve:

- Built-in view totals must run through the same JQL-lite parser/executor as queues.
- Export rows must be projections, not persisted state.
- `assigned` and `actionable` predicates should be backed by canonical WorkItem/status-category semantics once the WorkItem branch lands.
- Export output must remain redacted and tenant-scoped.

## Strategic recommendations

1. **Canonicalize WorkItem semantics first.** Merge/adapt the fuller WorkItem branch, choose `to_do/in_progress/done`, and publish project/issue-type/workflow/status definitions as additive projections over `OperationalCase`.

2. **Retire duplicate status-category branches.** Do not merge both `todo` and `to_do` vocabularies. Mark the narrower branch as superseded once tests are salvaged.

3. **Namespace service-management statuses.** Use `owner_status_category` or `service_status_category` for `waiting_owner`/`waiting_external`; keep canonical `status_category` reserved for WorkItem categories.

4. **Keep semantic metrics registry-first.** No new metric literals outside registry/tests/adapters without validation that they resolve to canonical metrics.

5. **Keep connector execution on the platform path.** Registry → compiled runtime → run ledger → metric validation → cases. No connector-specific shortcuts.

6. **Treat secret refs as internal-sensitive handles.** They are safer than tokens but still should be redacted from persisted/exported/operator surfaces unless there is a deliberate admin-only reason.

7. **Run branch tests before merge.** Suggested focused tests:
   - WorkItem/status: `tests/test_work_items.py`, `tests/test_operator_case_views.py`, relevant internal API projection tests.
   - Connector: `tests/test_brain_connector_registry.py`, `tests/test_brain_runner.py`, `tests/test_brain_runtime.py`, `tests/test_brain_run_ledger.py`, `tests/invariants/test_secret_redaction.py`.
   - Trust/redaction: `tests/test_internal_operator_api.py`, `tests/invariants/test_secret_redaction.py`.
   - Workflow/work-management: `tests/test_brain_operational_cases.py`, `tests/test_operator_case_actions.py`, workflow automation tests.

## Final ARB call

Merge-ready after tests:

- `codex/eng-factory-work-item-status-category-20260602` — preferred canonical WorkItem/status-category direction.
- `codex/trust-admin-security` — audit export retention hardening.
- `qa/redaction-url-userinfo-20260602131915` — URL userinfo secret redaction.
- `codex/connector-platform` — registry/runtime connector metadata, with secret-ref boundary tests.
- `codex/operator-surfaces` — read-only recent-case projections.
- `codex/search-analytics` — read-only view totals/export analytics.
- `codex/work-management` — selectively, after reviewing assignee identifier handling.

Needs work / consolidate before merge:

- `codex/status-category-jql-20260602` — supersede or rebase onto canonical WorkItem categories.
- `codex/service-management` — namespace service/owner status categories and rebase on WorkItem definitions.

Already absorbed / no action unless missing tests are identified:

- `codex/workflow-automation`.
- `codex/eng-factory-audit-export-admin-20260602`.
