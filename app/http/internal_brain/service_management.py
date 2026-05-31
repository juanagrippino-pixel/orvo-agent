from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api.common import parse_limit
from app.brain.service_management import list_service_management_cases

from .common import _internal_success, _with_internal_stores


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
                ),
            ),
        )
