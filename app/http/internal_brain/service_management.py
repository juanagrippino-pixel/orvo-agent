from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api.common import OperatorAPIError, parse_limit
from app.brain.service_management import ALLOWED_SERVICE_MANAGEMENT_SLA_STATUSES, list_service_management_cases

from .common import _internal_success, _with_internal_stores


def _parse_sla_status(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in ALLOWED_SERVICE_MANAGEMENT_SLA_STATUSES:
        raise OperatorAPIError("invalid_sla_status", f"unsupported sla_status: {value}", status_code=400)
    return str(value)


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
                ),
            ),
        )
