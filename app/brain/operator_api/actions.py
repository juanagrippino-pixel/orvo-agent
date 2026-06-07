from __future__ import annotations

from typing import Any, cast

from .common import *  # noqa: F401,F403
from .common import _ALLOWED_CASE_ACTIONS, _REGISTERED_CASE_ACTIONS
from .projections import *  # noqa: F401,F403
from .cases import get_scoped_case
from app.brain.workflow_action_ledger import WorkflowActionLedgerRecord, WorkflowActionLedgerStore


_IDEMPOTENCY_KEY_MAX_LENGTH = 200
_IDEMPOTENCY_KEY_ALLOWED_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:/")
_ACTION_TARGETS = {
    "acknowledge_case": ("acknowledged", "Acknowledged by operator."),
    "mark_in_progress": ("in_progress", "Marked in progress by operator."),
    "resolve_case": ("resolved", "Resolved by operator."),
    "dismiss_case": ("dismissed", "Dismissed by operator."),
}


def normalize_case_action_idempotency_key(value: Any) -> str | None:
    """Return a safe optional idempotency key for manual operator mutations."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise OperatorAPIError(
            "invalid_idempotency_key",
            "X-Idempotency-Key must be a safe non-empty string when provided",
            status_code=400,
        )
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > _IDEMPOTENCY_KEY_MAX_LENGTH or any(
        char not in _IDEMPOTENCY_KEY_ALLOWED_CHARS for char in normalized
    ):
        raise OperatorAPIError(
            "invalid_idempotency_key",
            "X-Idempotency-Key must be a safe non-empty string when provided",
            status_code=400,
        )
    redacted = redact_text(normalized)
    if redacted != normalized:
        raise OperatorAPIError(
            "invalid_idempotency_key",
            "X-Idempotency-Key must not contain credentials or secret-shaped values",
            status_code=400,
        )
    return normalized


def require_case_action_idempotency_key(value: Any) -> str:
    """Return a safe idempotency key required by mutating HTTP operator boundaries."""

    normalized = normalize_case_action_idempotency_key(value)
    if normalized is None:
        raise OperatorAPIError(
            "missing_idempotency_key",
            "X-Idempotency-Key is required for case actions",
            status_code=400,
        )
    return normalized


def _manual_action_params(
    *,
    reason: str | None = None,
    comment: Any = None,
    metadata: dict[str, Any] | None = None,
    assignee_ref: Any = None,
    owner_ref: Any = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if reason is not None:
        params["reason"] = reason
    if comment is not None:
        params["comment"] = comment
    if metadata:
        params["metadata"] = metadata
    if assignee_ref is not None:
        params["assignee_ref"] = assignee_ref
    if owner_ref is not None:
        params["owner_ref"] = owner_ref
    return params


def _action_response(record: WorkflowActionLedgerRecord, *, status: str) -> dict[str, Any]:
    return {
        "ledger_id": record.ledger_id,
        "case_id": record.case_id,
        "action_key": record.action_key,
        "idempotency_key": record.idempotency_key,
        "status": status,
        "execution_state": record.execution_state,
    }


def _ensure_idempotent_replay_matches(
    record: WorkflowActionLedgerRecord,
    *,
    case_id: str,
    action_key: str,
) -> None:
    if record.source != "manual_operator" or record.case_id != case_id or record.action_key != action_key:
        raise OperatorAPIError(
            "idempotency_key_conflict",
            "X-Idempotency-Key was already used for a different manual case action",
            status_code=409,
        )


def _ensure_replay_executed(record: WorkflowActionLedgerRecord) -> None:
    if record.execution_state == "pending_execution":
        raise OperatorAPIError(
            "idempotency_key_in_progress",
            "X-Idempotency-Key is already attached to a manual case action that has not completed",
            status_code=409,
        )
    if record.execution_state != "executed":
        raise OperatorAPIError(
            "idempotency_key_not_replayable",
            "X-Idempotency-Key is already attached to a manual case action that did not complete successfully",
            status_code=409,
        )


def _validate_case_action_inputs(
    store: OperationalCaseStore,
    *,
    business_id: str,
    case_id: str,
    action_key: str,
    actor_ref: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    comment: Any = None,
    assignee_ref: Any = None,
    owner_ref: Any = None,
) -> tuple[OperationalCase, str]:
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
        return case, effective_actor_ref

    if action_key == "assign_owner":
        normalize_case_assignee(assignee_ref, owner_ref)
        return case, effective_actor_ref

    target_status, _default_reason = _ACTION_TARGETS[action_key]
    provided_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
    if target_status in TERMINAL_OPERATIONAL_CASE_STATUSES and provided_reason is None:
        raise OperatorAPIError(
            "missing_case_action_reason",
            f"{action_key} requires a non-empty reason",
            status_code=400,
        )
    return case, effective_actor_ref


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
    case, effective_actor_ref = _validate_case_action_inputs(
        store,
        business_id=business_id,
        case_id=case_id,
        action_key=action_key,
        actor_ref=actor_ref,
        actor=actor,
        reason=reason,
        comment=comment,
        assignee_ref=assignee_ref,
        owner_ref=owner_ref,
    )
    if action_key == "add_comment":
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

    target_status, default_reason = _ACTION_TARGETS[action_key]
    provided_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
    try:
        updated = store.transition_case(
            case.case_id,
            status=cast(Any, target_status),
            actor_type="operator",
            actor_ref=effective_actor_ref,
            reason=provided_reason or default_reason,
        )
    except OperationalCaseStatusError as exc:
        raise OperatorAPIError("invalid_case_transition", str(exc), status_code=409) from exc
    return {"case": case_detail(updated)}


def apply_case_action_with_idempotency(
    store: OperationalCaseStore,
    action_ledger: WorkflowActionLedgerStore,
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
    normalized_idempotency_key = require_case_action_idempotency_key(idempotency_key)

    _case, effective_actor_ref = _validate_case_action_inputs(
        store,
        business_id=business_id,
        case_id=case_id,
        action_key=action_key,
        actor_ref=actor_ref,
        actor=actor,
        reason=reason,
        comment=comment,
        assignee_ref=assignee_ref,
        owner_ref=owner_ref,
    )
    params = _manual_action_params(
        reason=reason,
        comment=comment,
        metadata=metadata,
        assignee_ref=assignee_ref,
        owner_ref=owner_ref,
    )
    write = action_ledger.record_planned_action(
        business_id=business_id,
        case_id=case_id,
        action_key=action_key,
        idempotency_key=normalized_idempotency_key,
        execution_state="pending_execution",
        approval_required=False,
        source="manual_operator",
        actor_ref=effective_actor_ref,
        params=params,
    )
    if not write.created:
        _ensure_idempotent_replay_matches(write.record, case_id=case_id, action_key=action_key)
        _ensure_replay_executed(write.record)
        case = get_scoped_case(store, business_id=business_id, case_id=case_id)
        return {"case": case_detail(case), "action": _action_response(write.record, status="skipped_duplicate")}

    try:
        data = apply_case_action(
            store,
            business_id=business_id,
            case_id=case_id,
            action_key=action_key,
            actor_ref=effective_actor_ref,
            reason=reason,
            comment=comment,
            metadata=metadata,
            assignee_ref=assignee_ref,
            owner_ref=owner_ref,
        )
    except Exception:
        action_ledger.update_action_execution_state(
            business_id=business_id,
            ledger_id=write.record.ledger_id,
            execution_state="failed",
        )
        raise
    executed_record = action_ledger.update_action_execution_state(
        business_id=business_id,
        ledger_id=write.record.ledger_id,
        execution_state="executed",
    )
    data["action"] = _action_response(executed_record, status="executed")
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
