from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api.common import OperatorAPIError, parse_limit
from app.brain.service_management import (
    ALLOWED_SERVICE_MANAGEMENT_ESCALATION_REASONS,
    ALLOWED_SERVICE_MANAGEMENT_OWNER_STATUSES,
    ALLOWED_SERVICE_MANAGEMENT_RECORD_TYPES,
    ALLOWED_SERVICE_MANAGEMENT_SLA_STATUSES,
    list_service_management_cases,
)

from .common import _internal_success, _with_internal_stores


def _parse_sla_status(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in ALLOWED_SERVICE_MANAGEMENT_SLA_STATUSES:
        raise OperatorAPIError("invalid_sla_status", f"unsupported sla_status: {value}", status_code=400)
    return str(value)


def _parse_service_record_type(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in ALLOWED_SERVICE_MANAGEMENT_RECORD_TYPES:
        raise OperatorAPIError(
            "invalid_service_record_type",
            f"unsupported service_record_type: {value}",
            status_code=400,
        )
    return str(value)


def _parse_owner_status(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in ALLOWED_SERVICE_MANAGEMENT_OWNER_STATUSES:
        raise OperatorAPIError(
            "invalid_owner_status",
            f"unsupported owner_status: {value}",
            status_code=400,
        )
    return str(value)


def _parse_escalation_reason(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in ALLOWED_SERVICE_MANAGEMENT_ESCALATION_REASONS:
        raise OperatorAPIError(
            "invalid_escalation_reason",
            f"unsupported escalation_reason: {value}",
            status_code=400,
        )
    return str(value)


def _parse_needs_escalation(value: str | None) -> bool | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise OperatorAPIError(
        "invalid_needs_escalation",
        f"unsupported needs_escalation: {value}",
        status_code=400,
    )


def register_service_management_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/service-management/cases")
    def internal_brain_service_management_cases(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_service_management_cases(
                    case_store,
                    business_id=business_id,
                    limit=parse_limit(request.args.get("limit")),
                    now=datetime.now(timezone.utc),
                    sla_status=_parse_sla_status(request.args.get("sla_status")),
                    service_record_type=_parse_service_record_type(request.args.get("service_record_type")),
                    owner_status=_parse_owner_status(request.args.get("owner_status")),
                    escalation_reason=_parse_escalation_reason(request.args.get("escalation_reason")),
                    needs_escalation=_parse_needs_escalation(request.args.get("needs_escalation")),
                ),
            ),
        )
