"""Jira Service Management-style projections over Operational Cases.

The functions in this module are read-only service-layer helpers. They translate
canonical ``OperationalCase`` state into service-management views (record type,
owner-facing status, and SLA clock state) without mutating lifecycle state or
making surfaces a source of truth.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.brain.operational_cases import OperationalCase, OperationalCaseStore
from app.brain.security.redaction import redact_secrets

_SERVICE_RECORD_LABELS: dict[str, dict[str, str]] = {
    "incident": {"label": "Incident", "label_es": "Incidente"},
    "service_request": {"label": "Service request", "label_es": "Solicitud"},
    "problem": {"label": "Problem", "label_es": "Problema"},
    "change": {"label": "Change", "label_es": "Cambio"},
}

_SERVICE_RECORD_TYPE_BY_CASE_TYPE: dict[str, str] = {
    "stockout_risk": "incident",
    "spend_without_orders": "incident",
    "data_stale": "incident",
    "sales_drop": "problem",
    "channel_mix_shift": "problem",
    "unanswered_conversations": "service_request",
}

_OWNER_STATUS_BY_CASE_STATUS: dict[str, dict[str, str]] = {
    "open": {"code": "new", "label_es": "Nuevo", "status_category": "to_do"},
    "acknowledged": {"code": "triaged", "label_es": "En triage", "status_category": "in_progress"},
    "in_progress": {"code": "in_progress", "label_es": "En progreso", "status_category": "in_progress"},
    "resolved": {"code": "resolved", "label_es": "Resuelto", "status_category": "done"},
    "dismissed": {"code": "dismissed", "label_es": "Descartado", "status_category": "done"},
}

_WAITING_OWNER_STATUSES: dict[str, dict[str, str]] = {
    "owner": {"code": "waiting_owner", "label_es": "Esperando al dueño", "status_category": "waiting"},
    "external": {"code": "waiting_external", "label_es": "Esperando a un tercero", "status_category": "waiting"},
}

_FIRST_RESPONSE_TARGET_SECONDS: dict[str, int] = {
    "critical": 60 * 60,
    "warning": 4 * 60 * 60,
    "info": 24 * 60 * 60,
}

_RESOLUTION_TARGET_SECONDS: dict[str, int] = {
    "critical": 4 * 60 * 60,
    "warning": 24 * 60 * 60,
    "info": 72 * 60 * 60,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_reference_time(now: datetime | None) -> datetime:
    if now is None:
        return _now_utc()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _service_record_type(case: OperationalCase) -> dict[str, str]:
    metadata_record_type = case.metadata.get("service_record_type")
    if metadata_record_type in _SERVICE_RECORD_LABELS:
        code = str(metadata_record_type)
    else:
        code = _SERVICE_RECORD_TYPE_BY_CASE_TYPE.get(case.case_type, "incident")
    labels = _SERVICE_RECORD_LABELS[code]
    return {"code": code, **labels}


def _owner_status(case: OperationalCase) -> dict[str, str]:
    waiting_on = case.metadata.get("waiting_on")
    if case.status in {"acknowledged", "in_progress"} and waiting_on in _WAITING_OWNER_STATUSES:
        payload = dict(_WAITING_OWNER_STATUSES[str(waiting_on)])
    else:
        payload = dict(_OWNER_STATUS_BY_CASE_STATUS[case.status])
    payload["source_status"] = case.status
    return payload


def _sla_clock(
    *,
    case: OperationalCase,
    target_seconds: int,
    policy_key: str,
    stopped_at: datetime | None,
    reference: datetime,
) -> dict[str, Any]:
    started_at = case.opened_at.astimezone(timezone.utc)
    effective_stop = stopped_at.astimezone(timezone.utc) if stopped_at is not None else reference
    elapsed_seconds = max(int((effective_stop - started_at).total_seconds()), 0)
    due_at = started_at + timedelta(seconds=target_seconds)
    return {
        "policy_key": policy_key,
        "target_seconds": target_seconds,
        "elapsed_seconds": elapsed_seconds,
        "remaining_seconds": max(target_seconds - elapsed_seconds, 0),
        "breached": elapsed_seconds > target_seconds,
        "completed": stopped_at is not None,
        "started_at": _iso(started_at),
        "stopped_at": _iso(stopped_at),
        "due_at": _iso(due_at),
    }


def _sla_projection(case: OperationalCase, *, reference: datetime) -> dict[str, Any]:
    severity = str(case.severity)
    first_response_target = _FIRST_RESPONSE_TARGET_SECONDS[severity]
    resolution_target = _RESOLUTION_TARGET_SECONDS[severity]
    terminal_stopped_at = case.resolved_at or case.dismissed_at
    first_response_stopped_at = case.acknowledged_at or terminal_stopped_at
    resolution_stopped_at = terminal_stopped_at
    return {
        "first_response": _sla_clock(
            case=case,
            target_seconds=first_response_target,
            policy_key=f"first_response_{severity}_{first_response_target // 60}m",
            stopped_at=first_response_stopped_at,
            reference=reference,
        ),
        "resolution": _sla_clock(
            case=case,
            target_seconds=resolution_target,
            policy_key=f"resolution_{severity}_{resolution_target // 60}m",
            stopped_at=resolution_stopped_at,
            reference=reference,
        ),
    }


def _escalation_reasons(
    case: OperationalCase,
    *,
    owner_status: dict[str, str],
    sla: dict[str, Any],
) -> list[dict[str, str]]:
    """Return deterministic service-management escalation reasons.

    These are read-only labels for operator triage and do not mutate case
    priority, status, SLA clocks, or workflow lifecycle.
    """

    reasons: list[dict[str, str]] = []
    if case.severity == "critical" and case.status == "open":
        reasons.append(
            {
                "code": "critical_case_unacknowledged",
                "label_es": "Caso crítico sin acuse",
                "source": "case_status",
            }
        )
    first_response = sla["first_response"]
    if first_response["breached"] and not first_response["completed"]:
        reasons.append(
            {
                "code": "first_response_sla_breached",
                "label_es": "SLA de primera respuesta vencido",
                "source": "sla.first_response",
            }
        )
    resolution = sla["resolution"]
    if resolution["breached"] and not resolution["completed"]:
        reasons.append(
            {
                "code": "resolution_sla_breached",
                "label_es": "SLA de resolución vencido",
                "source": "sla.resolution",
            }
        )
    if owner_status["code"] == "waiting_external":
        reasons.append(
            {
                "code": "waiting_external",
                "label_es": "Bloqueado por un tercero",
                "source": "owner_status",
            }
        )
    elif owner_status["code"] == "waiting_owner":
        reasons.append(
            {
                "code": "waiting_owner",
                "label_es": "Esperando decisión del dueño",
                "source": "owner_status",
            }
        )
    return reasons


def service_management_case_item(case: OperationalCase, *, now: datetime | None = None) -> dict[str, Any]:
    """Project one OperationalCase into a service-management case row.

    The returned status and SLA fields are deterministic projections. They do
    not replace ``case.status`` and should not be used as lifecycle state.
    """

    reference = _normalize_reference_time(now)
    owner_status = _owner_status(case)
    sla = _sla_projection(case, reference=reference)
    escalation_reasons = _escalation_reasons(case, owner_status=owner_status, sla=sla)
    return redact_secrets(
        {
            "case_id": case.case_id,
            "business_id": case.business_id,
            "case_type": case.case_type,
            "title": case.title,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "entity_scope": case.entity_scope,
            "service_record_type": _service_record_type(case),
            "owner_status": owner_status,
            "opened_at": _iso(case.opened_at),
            "updated_at": _iso(case.updated_at),
            "acknowledged_at": _iso(case.acknowledged_at),
            "resolved_at": _iso(case.resolved_at),
            "dismissed_at": _iso(case.dismissed_at),
            "latest_run_id": case.latest_run_id,
            "sla": sla,
            "needs_escalation": bool(escalation_reasons),
            "escalation_reasons": escalation_reasons,
        }
    )


def list_service_management_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: int | None = 50,
    now: datetime | None = None,
) -> dict[str, Any]:
    """List service-management projections for cases in one business scope."""

    reference = _normalize_reference_time(now)
    all_cases = store.list_cases(business_id=business_id, limit=None)
    limited_cases = all_cases[:limit] if limit is not None else all_cases
    rows = [service_management_case_item(case, now=reference) for case in limited_cases]
    by_record_type: dict[str, int] = {}
    by_owner_status: dict[str, int] = {}
    for case in all_cases:
        record_type = _service_record_type(case)["code"]
        status = _owner_status(case)["code"]
        by_record_type[record_type] = by_record_type.get(record_type, 0) + 1
        by_owner_status[status] = by_owner_status.get(status, 0) + 1
    return redact_secrets(
        {
            "business_id": business_id,
            "now": _iso(reference),
            "limit": limit,
            "count": len(rows),
            "total": len(all_cases),
            "by_service_record_type": by_record_type,
            "by_owner_status": by_owner_status,
            "service_cases": rows,
        }
    )
