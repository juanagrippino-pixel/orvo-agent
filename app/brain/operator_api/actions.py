from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403
from .cases import get_scoped_case


def apply_case_action(
    store: OperationalCaseStore,
    *,
    business_id: str,
    case_id: str,
    action_key: str,
    actor_ref: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    comment: Any = None,
    metadata: dict[str, Any] | None = None,
    assignee_ref: Any = None,
    owner_ref: Any = None,
) -> dict[str, Any]:
    if action_key not in _ALLOWED_CASE_ACTIONS:
        raise OperatorAPIError("unknown_action_key", f"unknown action_key: {action_key}", status_code=400)
    effective_actor_ref = normalize_operator_actor(actor_ref, actor)

    case = get_scoped_case(store, business_id=business_id, case_id=case_id)
    if action_key == "add_comment":
        if not isinstance(comment, str) or not comment.strip():
            raise OperatorAPIError("invalid_comment", "comment must be a non-empty string", status_code=400)
        updated = store.add_comment(
            case.case_id,
            actor_type="operator",
            actor_ref=effective_actor_ref,
            comment=comment.strip(),
            metadata=metadata,
        )
        return {"case": case_detail(updated)}

    if action_key == "assign_owner":
        normalized_assignee_ref = normalize_case_assignee(assignee_ref, owner_ref)
        try:
            updated = store.assign_case(
                case.case_id,
                actor_type="operator",
                actor_ref=effective_actor_ref,
                assignee_ref=normalized_assignee_ref,
            )
        except OperationalCaseStatusError as exc:
            raise OperatorAPIError("invalid_case_transition", str(exc), status_code=409) from exc
        return {"case": case_detail(updated)}

    action_targets: dict[str, tuple[OperationalCaseStatus, str]] = {
        "acknowledge_case": ("acknowledged", "Acknowledged by operator."),
        "mark_in_progress": ("in_progress", "Marked in progress by operator."),
        "resolve_case": ("resolved", "Resolved by operator."),
        "dismiss_case": ("dismissed", "Dismissed by operator."),
    }
    target_status, default_reason = action_targets[action_key]
    provided_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
    if target_status in TERMINAL_OPERATIONAL_CASE_STATUSES and provided_reason is None:
        raise OperatorAPIError(
            "missing_case_action_reason",
            f"{action_key} requires a non-empty reason",
            status_code=400,
        )
    try:
        updated = store.transition_case(
            case.case_id,
            status=target_status,
            actor_type="operator",
            actor_ref=effective_actor_ref,
            reason=provided_reason or default_reason,
        )
    except OperationalCaseStatusError as exc:
        raise OperatorAPIError("invalid_case_transition", str(exc), status_code=409) from exc
    return {"case": case_detail(updated)}

__all__ = [name for name in globals() if not name.startswith("__")]
