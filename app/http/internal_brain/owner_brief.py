from __future__ import annotations

from flask import request

from app.brain.operator_api import preview_owner_case_brief
from app.brain.security.redaction import redact_text

from .common import _internal_success, _with_internal_stores


def register_owner_brief_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/owner-case-brief/preview")
    def internal_brain_owner_case_brief_preview(business_id: str):
        business_name = redact_text(request.args.get("business_name"))
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                preview_owner_case_brief(
                    case_store,
                    business_id=business_id,
                    business_name=business_name,
                    report_date=request.args.get("report_date"),
                    max_cases=request.args.get("max_cases"),
                ),
            ),
        )
