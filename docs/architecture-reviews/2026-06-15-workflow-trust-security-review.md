# Architecture Review — Workflow Automation + Trust/Admin/Security

Date: 2026-06-15
Reviewed HEAD: `5d1a947d`
Branch: `feat/orvo-brain-control-plane`
Scope: read-only review of workflow automation, idempotency, approval gates, audit, RBAC, and secret boundaries.

## Verdict
**Promising primitives, but automation is still projection-only.**
The code has the right shape for a governed workflow layer: deterministic plans, idempotency keys, approval gates, action ledgers, RBAC, and redaction. But the system does not yet have a complete execution engine with durable approval decisions and audited side-effect application.

## What is aligned
- Workflow automation is explicitly a **dry-run / projection primitive** and does not mutate case state or dispatch externally (`app/brain/workflow_automation.py:1-6`).
- Workflow actions have an explicit mode: `manual`, `suggestion`, or `approval_required` (`app/brain/workflow_automation.py:42`).
- Idempotency is modeled before execution (`app/brain/workflow_automation.py:109-119`).
- Approval gates are represented as deterministic projections (`app/brain/workflow_automation.py:332-340`).
- `WorkflowActionLedgerStore` defines a durable ledger contract for planned actions, execution state, approvals, and decisions (`app/brain/workflow_action_ledger.py:106-156`).
- Manual operator actions already go through idempotency and ledger recording (`app/brain/operator_api/actions.py:264-345`).
- RBAC exists in code with `viewer`, `operator`, and `admin` roles (`app/brain/operator_auth.py:16-25`).
- Internal routes have auth helpers, principal checks, and audit append support (`app/http/internal_brain/common.py:191-304`).
- Redaction is centralized and recursive (`app/brain/security/redaction.py:196-198`).

## Gaps / needs work
- **No real executor yet.** The workflow layer plans actions but does not yet apply them through a governed runtime hook.
- **Approval state is not fully durable.** The ledger contract exists, but approval decisions are not yet a complete audited workflow state machine.
- **Audit coverage is partial.** Case actions and internal routes have audit hooks, but workflow approvals and side-effect execution need stronger end-to-end audit coverage.
- **RBAC is present but not deeply wired everywhere.** Some surfaces still rely on shared internal token auth rather than a full role/scope enforcement model.
- **Secret boundaries need reinforcement.** Redaction exists, but workflow params and connector params must remain consistently redacted across ledger, audit, and projections.

## Branch readiness
- **Merge-ready:** the existing dry-run workflow primitives are acceptable as-is for planning and audit visibility.
- **Needs work:** any branch that claims end-to-end workflow automation needs a real executor, durable approval decisions, and full audit integration before merge.

## Notes
- No code changes were made.
- `pytest -q` passed on this HEAD.
