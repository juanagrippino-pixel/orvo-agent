"""Shared validation for workflow action-key query filters."""

from __future__ import annotations

from app.brain.action_catalog import ACTION_CATALOG, is_workflow_approval_required_action
from app.brain.workflow_action_ledger import WorkflowActionLedgerError


def validate_workflow_action_key_filter(
    action_key: str | None,
    *,
    require_approval_required: bool = False,
) -> None:
    """Validate a caller-supplied workflow action key used as a projection filter.

    When ``require_approval_required`` is true, the key must also be cataloged as
    a governed approval-required workflow action. This keeps queue projections
    from accidentally promoting manual or suggestion-only actions into workflow
    automation surfaces.
    """

    if action_key is not None and not action_key.strip():
        raise WorkflowActionLedgerError(
            "invalid_workflow_action_key",
            "workflow action_key must be non-empty",
        )
    if action_key is not None and action_key not in ACTION_CATALOG:
        raise WorkflowActionLedgerError(
            "invalid_workflow_action_key",
            f"unsupported workflow action_key: {action_key}",
        )
    if (
        require_approval_required
        and action_key is not None
        and not is_workflow_approval_required_action(action_key)
    ):
        raise WorkflowActionLedgerError(
            "invalid_workflow_action_key",
            f"workflow action_key must be approval-required: {action_key}",
        )
