from __future__ import annotations

from flask import request

from app.brain.operator_api.common import OperatorAPIError, parse_limit
from app.brain.service_management import (
    ALLOWED_SERVICE_MANAGEMENT_ACTIVE_SLA_CLOCKS,
    ALLOWED_SERVICE_MANAGEMENT_ESCALATION_REASONS,
    ALLOWED_SERVICE_MANAGEMENT_OWNER_STATUSES,
    ALLOWED_SERVICE_MANAGEMENT_OWNER_STATUS_CATEGORIES,
    ALLOWED_SERVICE_MANAGEMENT_RECORD_TYPES,
    ALLOWED_SERVICE_MANAGEMENT_SLA_STATUSES,
    ALLOWED_SERVICE_MANAGEMENT_SORTS,
    list_service_management_cases,
)

from .common import _internal_success, _with_internal_stores


def _parse_service_management_filter(value: str | None, *, name: str, allowed: frozenset[str]) -> str | None:
    if value in (None, ""):
        return None
    if value not in allowed:
        raise OperatorAPIError("invalid_request", f"Unsupported {name} filter.", status_code=400)
    return value


def _parse_service_management_bool(value: str | None, *, name: str) -> bool | None:
    if value in (None, ""):
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise OperatorAPIError("invalid_request", f"Unsupported {name} filter.", status_code=400)


def register_case_service_management_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases/service-management")
    def internal_brain_cases_service_management(business_id: str):
        def handler(case_store, run_ledger):
            return _internal_success(
                business_id,
                list_service_management_cases(
                    case_store,
                    business_id=business_id,
                    limit=parse_limit(request.args.get("limit"), default=50, max_limit=200),
                    service_record_type=_parse_service_management_filter(
                        request.args.get("service_record_type"),
                        name="service_record_type",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_RECORD_TYPES,
                    ),
                    owner_status=_parse_service_management_filter(
                        request.args.get("owner_status"),
                        name="owner_status",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_OWNER_STATUSES,
                    ),
                    owner_status_category=_parse_service_management_filter(
                        request.args.get("owner_status_category"),
                        name="owner_status_category",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_OWNER_STATUS_CATEGORIES,
                    ),
                    sla_status=_parse_service_management_filter(
                        request.args.get("sla_status"),
                        name="sla_status",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_SLA_STATUSES,
                    ),
                    escalation_reason=_parse_service_management_filter(
                        request.args.get("escalation_reason"),
                        name="escalation_reason",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_ESCALATION_REASONS,
                    ),
                    needs_escalation=_parse_service_management_bool(
                        request.args.get("needs_escalation"),
                        name="needs_escalation",
                    ),
                    active_sla_clock=_parse_service_management_filter(
                        request.args.get("active_sla_clock"),
                        name="active_sla_clock",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_ACTIVE_SLA_CLOCKS,
                    ),
                    sort_by=_parse_service_management_filter(
                        request.args.get("sort_by"),
                        name="sort_by",
                        allowed=ALLOWED_SERVICE_MANAGEMENT_SORTS,
                    )
                    or "priority",
                ),
            )

        return _with_internal_stores(business_id, handler)
