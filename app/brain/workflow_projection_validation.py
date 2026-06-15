"""Shared validation for read-only workflow projection inputs."""

from __future__ import annotations

from app.brain.workflow_action_ledger import WorkflowActionLedgerError


def validate_workflow_business_scope(business_id: str) -> str:
    """Return a non-empty workflow business scope for read-only projections."""

    if not isinstance(business_id, str) or not business_id.strip():
        raise WorkflowActionLedgerError(
            "invalid_workflow_business_scope",
            "workflow business_id must be non-empty",
        )
    return business_id.strip()


def validate_workflow_projection_limit(limit: int | None) -> int | None:
    """Return a safe optional positive limit for workflow projection services."""

    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise WorkflowActionLedgerError(
            "invalid_workflow_projection_limit",
            "workflow projection limit must be a positive integer",
        )
    return limit
