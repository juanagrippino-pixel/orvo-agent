from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import CASE_ACTION_PERMISSION, INTERNAL_READ_PERMISSION, permissions_for_role

from .common import (
    _authorize_internal_operator,
    _internal_success,
    _internal_error,
    _internal_principal_or_error,
    _require_internal_header_permission,
    _with_internal_stores,
)


def register_case_summary_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases")
    def internal_brain_cases(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_queue(
                    case_store,
                    business_id=business_id,
                    status=request.args.get("status"),
                    limit=request.args.get("limit"),
                    jql=request.args.get("jql"),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-actions")
    def internal_brain_case_actions(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        principal, permission_error = _internal_principal_or_error(business_id, INTERNAL_READ_PERMISSION)
        if permission_error is not None:
            return permission_error
        assert principal is not None
        can_execute_case_actions = CASE_ACTION_PERMISSION in permissions_for_role(principal.role)
        return _internal_success(
            business_id,
            list_case_action_catalog(
                business_id=business_id,
                can_execute_case_actions=can_execute_case_actions,
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/summary")
    def internal_brain_cases_summary(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue(case_store, business_id=business_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/summary/by-priority-bracket")
    def internal_brain_cases_summary_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_by_priority_bracket(case_store, business_id=business_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/summary/by-case-type")
    def internal_brain_cases_summary_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_by_case_type(case_store, business_id=business_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/summary/by-entity-kind")
    def internal_brain_cases_summary_by_entity_kind(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_by_entity_kind(case_store, business_id=business_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/summary/by-source-connector")
    def internal_brain_cases_summary_by_source_connector(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_by_source_connector(case_store, business_id=business_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/aging")
    def internal_brain_cases_aging(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_aging(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/aging/by-priority-bracket")
    def internal_brain_cases_aging_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_aging_by_priority_bracket(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/aging/by-case-type")
    def internal_brain_cases_aging_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_aging_by_case_type(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/aging/by-severity")
    def internal_brain_cases_aging_by_severity(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_aging_by_severity(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )
