# ARB architecture alignment review — 2026-06-15

Reviewed against `feat/orvo-brain-control-plane` at `3fd74eed`.

## Scope reviewed
- `n2-pro-work-management` (`ff972f8a`)
- `N2-Pro/connector-platform` (`9f89b657`)
- `N2-Pro/workflow-automation` (`2ee9a57b`)
- `N2-Pro/operator-surfaces` (`351288b0`)
- `N2-Pro/trust-admin-security` (`a19944f9`)
- `N2-Pro/search-analytics` (`55850e7c`)
- `N2-Pro/service-management` (`5ea2b181`)

## Branch verdicts
| Branch | Verdict | ARB note |
| --- | --- | --- |
| `n2-pro-work-management` | Merge-ready after rebase | Best step toward Atlassian-style work management: expands canonical `WorkItem` fields (`project`, `issue_type`, `status_category`, `owner_visible`, `sla_status`), strengthens JQL/query metadata, and keeps the source of truth in `OperationalCase`/`WorkItem` projections rather than UI state. |
| `N2-Pro/connector-platform` | Merge-ready | Tight, low-risk hardening. Rejects undeclared `secret_refs` in both registry validation and runtime compilation, which improves adapter/service/config separation and secret-boundary enforcement. |
| `N2-Pro/workflow-automation` | Merge-ready | Good control-plane fit. Keeps automation read/write truth in the workflow action ledger, adds shared action-key validation, and exposes read-only approval/execution/audit projections without bypassing approval or idempotency controls. |
| `N2-Pro/trust-admin-security` | Merge-ready | Strong boundary hardening. Redacts nested `business_id` values, request IDs, and audit export payloads more consistently, while fitting the existing internal operator auth model. |
| `N2-Pro/search-analytics` | Merge-ready after `n2-pro-work-management` | Architecturally aligned if landed on top of the work-management field model. Reuses canonical query metadata, adds built-in views/query-field discovery/CSV export, and improves audit-safe business display IDs. |
| `N2-Pro/operator-surfaces` | Needs work | Valuable product direction, but too broad and too duplicative right now. It introduces many bespoke recent-case and owner-brief projections that overlap with the emerging built-in-view/JQL/query-field stack. Split and rebase onto the canonical queue/view layer before merge. |
| `N2-Pro/service-management` | Needs work | Useful Atlassian/JSM direction, but it currently introduces a parallel service-management filter vocabulary and route family before projects/workflow schemes/JQL are fully unified. Should compile down to canonical case/work-item query contracts, not become a second search model. |

## Findings by review question

### 1) OperationalCase / WorkItem vs Atlassian patterns
**What is aligned**
- `app/brain/work_items.py` already treats `OperationalCase` as the canonical issue-like record and derives stable work-item projections such as `project_key`, `issue_type`, and `status_category`.
- `n2-pro-work-management` materially improves the model by making those fields first-class query metadata and by adding operational fields like `owner_visible`, `sla_status`, `reopen_count`, and canonical timestamps.
- `N2-Pro/search-analytics` builds the right next layer: built-in readonly views, `case-query-fields`, safer JQL parsing, and CSV export reusing the same allowlisted query path.

**What is still missing**
- Projects/workflow schemes are still mostly derived defaults, not first-class persisted admin objects. The current shape is Jira-like, but not yet Jira-level configurable.
- Workflow automation is still action-key centric. Orvo still needs a clearer project/issue-type/workflow-scheme contract for status transitions if it wants full Atlassian parity.
- `N2-Pro/operator-surfaces` regresses toward bespoke per-panel projections (`recently_opened`, `recently_acknowledged`, `recently_resolved`, etc.) where built-in views + query metadata should be the common abstraction.

**ARB conclusion**
- Core direction is good.
- `n2-pro-work-management` and `N2-Pro/search-analytics` are the right backbone.
- `N2-Pro/operator-surfaces` and `N2-Pro/service-management` should be normalized onto that backbone before merge.

### 2) Semantic registry as canonical source of truth
**What is aligned**
- Current `app/brain/operational_cases.py` already imports and uses `CASE_FAMILY_METRICS`, `default_metric_registry`, `validate_case_metric_objects`, and `validate_metrics`.
- Current case-detection code also clears stale `metric_registry_*` advisory metadata when a newer registry-clean detection arrives, which is the right anti-drift behavior.
- `N2-Pro/service-management` explicitly validates its case-family defaults against `CASE_FAMILY_METRICS`, which is good and should be preserved.
- `N2-Pro/search-analytics` and `n2-pro-work-management` mostly add projections over canonical work-item fields instead of inventing new metric stores.

**Risk / gap**
- The biggest drift risk is now not metric math, but surface duplication: export columns, recent-case panels, owner-brief projections, and service-management filters can drift from the canonical `WorkItem` query-field registry if each route family keeps its own projection vocabulary.

**ARB conclusion**
- Metric truth is in reasonable shape.
- The next governance problem is projection-contract drift, not raw metric drift.
- New surfaces should derive from the same query-field/view registry whenever possible.

### 3) Connector platform separation of adapter / service / storage
**What is aligned**
- `N2-Pro/connector-platform` is a good platform-hardening branch: undeclared `secret_refs` are rejected both in `ConnectorSpec.validate_control_plane_config(...)` and in `compile_business_runtime(...)`.
- This keeps connector configuration truth in the registry/runtime contracts instead of letting adapters accept ad hoc secrets.
- Secret values are not echoed back in validation/runtime errors, which respects boundary contracts.

**Risk / gap**
- The codebase still spreads connector concerns across registry/runtime/health modules rather than a more obviously segmented per-connector package layout. That is acceptable for now, but ARB recommends resisting more route-specific connector logic until the registry contract is fully settled.

**ARB conclusion**
- Merge `N2-Pro/connector-platform`.
- Keep pushing all connector-specific validation through registry/runtime contracts, not endpoint code.

### 4) Workflow automation: idempotency, approvals, audit
**What is aligned**
- Current `workflow_action_ledger.py` already keeps `idempotency_key`, `approval_state`, and `execution_state` as the canonical workflow-action truth.
- `N2-Pro/workflow-automation` reinforces that correctly:
  - shared validation for `action_key` filters,
  - shared projection-limit validation,
  - read-only workflow audit projection,
  - internal approval/execution/audit routes over canonical ledger records.
- The branch does not move truth into HTTP routes or UI payloads.

**Risk / gap**
- Automation is still mostly a governed action ledger, not yet a first-class workflow engine tied to issue-type workflow schemes and transition guards.
- That is acceptable for this phase, but it means Orvo is closer to “audited action automation” than “full Jira workflow engine” today.

**ARB conclusion**
- Merge `N2-Pro/workflow-automation`.
- Next architectural milestone should be workflow-scheme/transition contracts, not more bespoke workflow endpoints.

### 5) Trust / admin / security
**What is aligned**
- Current `operator_auth.py` already has a coarse but real RBAC model (`viewer`, `operator`, `admin`) plus business allowlisting.
- `N2-Pro/trust-admin-security` improves service-boundary redaction for nested payloads, route-scoped business IDs, request IDs, and audit exports.
- `N2-Pro/search-analytics` also improves `audit_business_display_id(...)` so secret-shaped business labels collapse entirely to `[REDACTED]`.

**Risk / gap**
- Authorization is still coarse-grained. There is no project-level, queue-level, or workflow-scope permission model yet.
- That is acceptable for internal surfaces, but ARB does not recommend expanding admin/audit/export breadth much further before permission scopes become more explicit.

**ARB conclusion**
- Merge `N2-Pro/trust-admin-security`.
- Treat finer-grained RBAC as a near-term control-plane prerequisite for broader operator-console rollout.

## Cross-branch duplication / strategic risks
1. **Recent-case duplication**
   - `N2-Pro/operator-surfaces` adds many bespoke “recently X” projections.
   - `N2-Pro/search-analytics` already establishes built-in views + JQL + query-field discovery.
   - ARB recommendation: recent-case panels should be thin consumers of built-in views, not separate service families.

2. **Second query language risk**
   - `N2-Pro/service-management` adds a dedicated service-management filter vocabulary.
   - ARB recommendation: either compile those filters to canonical case-view/JQL semantics or wait until workflow/project schemes are more formalized.

3. **Projection-contract sprawl**
   - Owner brief, suggested actions, case exports, recent queues, and service-management queues are all useful, but they should reuse a smaller shared set of projection contracts.
   - The right center of gravity is: `OperationalCase` -> `WorkItem` -> canonical query/view registry -> specialized UI/report surfaces.

## ARB recommendation
**Merge now**
- `n2-pro-work-management` (after rebase)
- `N2-Pro/connector-platform`
- `N2-Pro/workflow-automation`
- `N2-Pro/trust-admin-security`
- `N2-Pro/search-analytics` (after `n2-pro-work-management`)

**Do not merge as-is**
- `N2-Pro/operator-surfaces`
- `N2-Pro/service-management`

**Recommended sequence**
1. Land work-management backbone.
2. Land connector/workflow/security hardening.
3. Land search-analytics on top of the canonical work-item query model.
4. Re-scope operator-surfaces to consume built-in views/query metadata instead of defining parallel recent-case services.
5. Rework service-management so it is a projection over the same query/workflow contracts, not a second search model.
