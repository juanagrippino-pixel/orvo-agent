from __future__ import annotations

from flask import request

from app.brain.operator_api import list_suggested_action_cases

from .common import _internal_success, _with_internal_stores


def register_case_suggested_action_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases/suggested-actions")
    def internal_brain_cases_suggested_actions(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_suggested_action_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )
