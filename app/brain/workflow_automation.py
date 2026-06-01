"""Deterministic workflow automation simulation for Operational Cases.

This module is intentionally a service-layer dry-run/projection primitive. It
reads canonical ``OperationalCase`` objects and returns auditable plans; it does
not mutate case state, dispatch messages, or call external systems. Operator/API
routes and future runtime hooks should call this service instead of embedding
workflow logic in transport code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from app.brain.action_catalog import ActionDefinition as WorkflowActionDefinition
from app.brain.action_catalog import workflow_action_registry
from app.brain.operational_cases import OperationalCase
from app.brain.security.redaction import redact_secrets, redact_text

WorkflowTrigger = Literal["case_opened", "case_updated", "manual"]
WORKFLOW_TRIGGER_VALUES = {"case_opened", "case_updated", "manual"}
WorkflowConditionField = Literal["status", "case_type", "severity", "min_priority_score", "degraded"]
WorkflowActionMode = Literal["manual", "suggestion", "approval_required"]
WorkflowSideEffect = Literal["none", "case_transition", "case_comment", "operator_request", "external"]


# Code whitelist aligned with docs/specs/d2c-action-key-catalog.md. Suggested
# D2C actions remain projection-only until a governed executor exists.
WORKFLOW_ACTION_REGISTRY: dict[str, WorkflowActionDefinition] = workflow_action_registry()


class WorkflowAutomationError(Exception):
    """Safe deterministic workflow automation error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = redact_text(message) or "Workflow automation error"
        super().__init__(self.message)


@dataclass(frozen=True)
class CaseWorkflowCondition:
    """Single allowlisted condition over canonical OperationalCase fields."""

    field: WorkflowConditionField
    value: Any


@dataclass(frozen=True)
class WorkflowAction:
    """Action requested by a workflow rule.

    ``params`` are redacted at projection/audit boundaries and included in the
    deterministic idempotency fingerprint after redaction so secrets never leak
    into keys or logs.
    """

    action_key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowRule:
    """Deterministic trigger/condition/action rule for case workflows."""

    rule_id: str
    business_id: str
    trigger: WorkflowTrigger
    conditions: list[CaseWorkflowCondition] = field(default_factory=list)
    actions: list[WorkflowAction] = field(default_factory=list)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _redacted_params(params: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_secrets(params or {})
    return redacted if isinstance(redacted, dict) else {}


def _canonical_json(value: Any) -> str:
    return json.dumps(redact_secrets(value), sort_keys=True, separators=(",", ":"), default=str)


def make_workflow_idempotency_key(
    *,
    business_id: str,
    rule_id: str,
    case_id: str,
    action_key: str,
    params: dict[str, Any] | None = None,
) -> str:
    """Return a stable, non-secret idempotency key for a planned workflow action."""

    fingerprint_payload = {
        "business_id": business_id,
        "rule_id": rule_id,
        "case_id": case_id,
        "action_key": action_key,
        "params": _redacted_params(params or {}),
    }
    digest = hashlib.sha256(_canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()[:16]
    return f"workflow/{business_id}/{rule_id}/{case_id}/{action_key}/{digest}"


def _is_case_degraded(case: OperationalCase) -> bool:
    return any(snapshot.freshness_state in {"stale", "degraded", "missing"} for snapshot in case.evidence_snapshots)


def _condition_actual(case: OperationalCase, field_name: str) -> Any:
    if field_name == "status":
        return case.status
    if field_name == "case_type":
        return case.case_type
    if field_name == "severity":
        return case.severity
    if field_name == "min_priority_score":
        return case.priority_score
    if field_name == "degraded":
        return _is_case_degraded(case)
    raise WorkflowAutomationError("unsupported_workflow_condition", f"unsupported workflow condition field: {field_name}")


def _condition_matches(condition: CaseWorkflowCondition, actual: Any) -> bool:
    if condition.field == "min_priority_score":
        try:
            return int(actual) >= int(condition.value)
        except (TypeError, ValueError) as exc:
            raise WorkflowAutomationError(
                "invalid_workflow_condition",
                "min_priority_score condition value must be an integer",
            ) from exc
    return actual == condition.value


def _condition_projection(case: OperationalCase, condition: CaseWorkflowCondition) -> dict[str, Any]:
    actual = _condition_actual(case, condition.field)
    return redact_secrets(
        {
            "field": condition.field,
            "expected": condition.value,
            "actual": actual,
            "matched": _condition_matches(condition, actual),
        }
    )


def _validate_rule(rule: WorkflowRule, case: OperationalCase) -> None:
    if rule.business_id != case.business_id:
        raise WorkflowAutomationError("business_scope_mismatch", "workflow rule business_id does not match case business_id")
    if not rule.rule_id.strip():
        raise WorkflowAutomationError("invalid_workflow_rule", "workflow rule_id is required")
    if rule.trigger not in WORKFLOW_TRIGGER_VALUES:
        raise WorkflowAutomationError(
            "unsupported_workflow_trigger",
            f"unsupported workflow trigger: {rule.trigger}",
        )
    for action in rule.actions:
        if action.action_key not in WORKFLOW_ACTION_REGISTRY:
            raise WorkflowAutomationError(
                "unknown_workflow_action_key",
                f"unknown workflow action_key: {action.action_key}",
            )
        definition = WORKFLOW_ACTION_REGISTRY[action.action_key]
        if definition.case_families and case.case_type not in definition.case_families:
            raise WorkflowAutomationError(
                "action_not_allowed_for_case_type",
                f"workflow action_key {action.action_key} is not registered for case_type {case.case_type}",
            )


def _execution_status(definition: WorkflowActionDefinition) -> str:
    if definition.requires_approval:
        return "blocked_approval_required"
    if definition.mode == "suggestion":
        return "suggestion_only"
    return "dry_run"


def _planned_action_projection(
    *,
    rule: WorkflowRule,
    case: OperationalCase,
    action: WorkflowAction,
    now: datetime,
) -> dict[str, Any]:
    definition = WORKFLOW_ACTION_REGISTRY[action.action_key]
    status = _execution_status(definition)
    idempotency_key = make_workflow_idempotency_key(
        business_id=case.business_id,
        rule_id=rule.rule_id,
        case_id=case.case_id,
        action_key=action.action_key,
        params=action.params,
    )
    audit_event = {
        "event_type": "workflow_action_planned",
        "rule_id": rule.rule_id,
        "case_id": case.case_id,
        "action_key": action.action_key,
        "idempotency_key": idempotency_key,
        "execution_status": status,
        "created_at": _iso(now),
    }
    return redact_secrets(
        {
            "action_key": action.action_key,
            "mode": definition.mode,
            "side_effect": definition.side_effect,
            "requires_approval": definition.requires_approval,
            "execution_status": status,
            "idempotency_key": idempotency_key,
            "params": _redacted_params(action.params),
            "audit_event": audit_event,
        }
    )


def _skipped_duplicate_action_projection(
    *,
    rule: WorkflowRule,
    case: OperationalCase,
    action_key: str,
    idempotency_key: str,
    now: datetime,
) -> dict[str, Any]:
    status = "skipped_duplicate"
    reason = "duplicate_idempotency_key"
    audit_event = {
        "event_type": "workflow_action_skipped_duplicate",
        "rule_id": rule.rule_id,
        "case_id": case.case_id,
        "action_key": action_key,
        "idempotency_key": idempotency_key,
        "execution_status": status,
        "reason": reason,
        "created_at": _iso(now),
    }
    return redact_secrets(
        {
            "action_key": action_key,
            "idempotency_key": idempotency_key,
            "execution_status": status,
            "reason": reason,
            "audit_event": audit_event,
        }
    )


def _dedupe_planned_actions(
    *,
    rule: WorkflowRule,
    case: OperationalCase,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    skipped_actions: list[dict[str, Any]] = []
    seen_idempotency_keys: set[str] = set()
    for action in rule.actions:
        planned_action = _planned_action_projection(rule=rule, case=case, action=action, now=now)
        idempotency_key = str(planned_action["idempotency_key"])
        if idempotency_key in seen_idempotency_keys:
            skipped_actions.append(
                _skipped_duplicate_action_projection(
                    rule=rule,
                    case=case,
                    action_key=action.action_key,
                    idempotency_key=idempotency_key,
                    now=now,
                )
            )
            continue
        seen_idempotency_keys.add(idempotency_key)
        actions.append(planned_action)
    return actions, skipped_actions


def simulate_case_workflow(rule: WorkflowRule, case: OperationalCase, *, now: datetime | None = None) -> dict[str, Any]:
    """Dry-run a workflow rule against one canonical Operational Case.

    The function validates action keys before evaluating conditions so invented
    LLM/copy-layer actions fail closed even when the rule would not match. The
    returned projection is redacted and contains deterministic idempotency/audit
    handles, but ``side_effects_executed`` is always zero.
    """

    _validate_rule(rule, case)
    generated_at = _now_utc() if now is None else now.astimezone(timezone.utc)
    condition_results = [_condition_projection(case, condition) for condition in rule.conditions]
    matched = all(result["matched"] for result in condition_results)
    actions: list[dict[str, Any]] = []
    skipped_actions: list[dict[str, Any]] = []
    if matched:
        actions, skipped_actions = _dedupe_planned_actions(rule=rule, case=case, now=generated_at)
    return redact_secrets(
        {
            "rule_id": rule.rule_id,
            "business_id": rule.business_id,
            "trigger": rule.trigger,
            "case": {
                "case_id": case.case_id,
                "case_type": case.case_type,
                "status": case.status,
                "severity": case.severity,
                "priority_score": case.priority_score,
                "title": case.title,
            },
            "matched": matched,
            "conditions": condition_results,
            "actions": actions,
            "skipped_actions": skipped_actions,
            "side_effects_executed": 0,
            "generated_at": _iso(generated_at),
        }
    )
