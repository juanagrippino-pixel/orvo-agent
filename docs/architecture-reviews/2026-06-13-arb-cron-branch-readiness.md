# Branch Readiness Matrix — 2026-06-13 (cron)

**Base:** `feat/orvo-brain-control-plane`  
**Review mode:** Read-only architecture review. No cron jobs changed. No push, merge, or deploy performed.

## Summary matrix

| Branch | Ahead / behind vs base | Diff shape | Verdict | Why |
|---|---:|---|---|---|
| `N2-Pro/connector-platform` | `+4 / -2` | `9 files, +257, -5` | **Merge-ready** | Connector/runtime metadata hardening without breaking adapter/service/storage separation. |
| `N2-Pro/workflow-automation` | `+7 / -14` | `9 files, +929, -26` | **Merge-ready candidate** | Ledger-first approval/execution/audit projections; needs rebase. |
| `N2-Pro/trust-admin-security` | `+7 / -83` | `7 files, +424, -24` | **Merge-ready candidate** | Strong audit/redaction/global-scope hardening; RBAC model still coarse. |
| `n2-pro-work-management` | `+7 / -15` | `7 files, +889, -15` | **Merge-ready candidate** | Best Atlassian-pattern uplift: SLA, due date, owner visibility, richer work-item query fields. |
| `N2-Pro/operator-surfaces` | `+62 / -86` | `63 files, +6644, -307` | **Needs work** | Correct product direction, but far too broad and route-heavy for safe merge. |
| `n2/metric-registry-source-gate-20260613` | `+0 / -15` | `already contained in base` | **Absorbed into base** | Review outcome should track current base behavior, not reopen a merged gate branch. |
| `n2/metric-registry-case-gate-20260613` | `+0 / -16` | `already contained in base` | **Absorbed into base** | Same as above. |

## Notes by branch

### `N2-Pro/connector-platform`
- Adds executor/runtime metadata to connector readiness projections.
- Hardens `secret://` handle shape validation.
- Improves health-event family certification without changing adapter ownership boundaries.

### `N2-Pro/workflow-automation`
- Adds internal workflow approval queue / execution queue / audit routes.
- Keeps those surfaces read-only and ledger-derived.
- Good architecture; main risk is branch freshness, not design direction.

### `N2-Pro/trust-admin-security`
- Tightens explicit global-business grant handling.
- Collapses secret-shaped nested `business_id` labels in internal responses and audit exports.
- Improves admin/audit trust posture without introducing a new auth model.

### `n2-pro-work-management`
- Adds SLA and due-date semantics at the `OperationalCase` layer.
- Expands `WorkItem` query fields with operator-relevant evidence/timeline metadata.
- Preserves `OperationalCase` as source of truth rather than forking a parallel task store.

### `N2-Pro/operator-surfaces`
- Valuable direction: owner brief, suggested actions, recent activity, top cases.
- Architectural problem is packaging: too many surfaces in one branch, plus endpoint proliferation.
- Should be decomposed into smaller, reusable projection-led slices.

## Repo-level board call

The repo is now stronger on semantic-registry enforcement than earlier reviews suggested, because persisted case upserts run with `metric_registry_mode="enforced"`. The remaining gap is **uniform enforcement across preview/report/surface paths**, not case persistence itself.

## Recommended order

1. `N2-Pro/connector-platform`
2. `N2-Pro/trust-admin-security`
3. `n2-pro-work-management`
4. `N2-Pro/workflow-automation`
5. Split `N2-Pro/operator-surfaces` before reconsidering merge readiness
