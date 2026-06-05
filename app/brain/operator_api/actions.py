from __future__ import annotations

from .common import *  # noqa: F401,F403
from .common import _ALLOWED_CASE_ACTIONS, _REGISTERED_CASE_ACTIONS
from .projections import *  # noqa: F401,F403
from ..storage import SQLiteIdempotencyStore
from .cases import get_scoped_case


def apply_case_action(
    store: OperationalCaseStore,
    *,
    business_id: str,
    case_id: str,
    action_key: str,
    idempotency_key: str | None = None,
    actor_ref: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    comment: Any = None,
    metadata: dict[str, Any] | None = None,
    assignee_ref: Any = None,
    owner_ref: Any = None,
) -> dict[str, Any]:
    if action_key not in _REGISTERED_CASE_ACTIONS:
        raise OperatorAPIError("unknown_action_key", f"unknown action_key: {action_key}", status_code=400)
    if action_key not in _ALLOWED_CASE_ACTIONS:
        raise OperatorAPIError(
            "case_action_api_disabled",
            f"action_key is registered but disabled for this API boundary: {action_key}",
            status_code=400,
        )
    effective_actor_ref = normalize_operator_actor(actor_ref, actor)

    case = get_scoped_case(store, business_id=business_id, case_id=case_id)
    if action_key == "add_comment":
        if not isinstance(comment, str) or not comment.strip():
            raise OperatorAPIError("invalid_comment", "comment must be a non-empty string", status_code=400)
        replay = _reserve_case_action_idempotency(store, idempotency_key, case=case)
        if replay is not None:
            return replay
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
        replay = _reserve_case_action_idempotency(store, idempotency_key, case=case)
        if replay is not None:
            return replay
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
    replay = _reserve_case_action_idempotency(store, idempotency_key, case=case)
    if replay is not None:
        return replay
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


def _reserve_case_action_idempotency(
    store: OperationalCaseStore,
    idempotency_key: str | None,
    *,
    case: OperationalCase,
) -> dict[str, Any] | None:
    """Reserve a durable action key before mutating a SQLite-backed case.

    Returns a replay projection when the same scoped request was already
    reserved. Non-SQLite stores do not have the durable idempotency table and are
    left unchanged for unit-test/direct service callers.
    """

    if not idempotency_key:
        return None
    conn = getattr(store, "_conn", None)
    if conn is None:
        return None
    if SQLiteIdempotencyStore(conn).reserve(idempotency_key):
        return None
    current = store.get_case(case.case_id) or case
    return {"case": case_detail(current), "_idempotency_replayed": True}


__all__ = [name for name in globals() if not name.startswith("__")]
