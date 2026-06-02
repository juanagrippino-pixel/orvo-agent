from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import CASE_ACTION_PERMISSION

from .common import (
    _internal_success,
    _internal_error,
    _internal_principal_or_error,
    _require_internal_header_permission,
    _with_internal_stores,
)


def register_case_activity_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases/stagnation")
    def internal_brain_cases_stagnation(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_stagnation(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/stagnation/by-priority-bracket")
    def internal_brain_cases_stagnation_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_stagnation_by_priority_bracket(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/workflow/throughput")
    def internal_brain_workflow_throughput(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_workflow_throughput(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/workflow/throughput/by-severity")
    def internal_brain_workflow_throughput_by_severity(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_workflow_throughput_by_severity(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/workflow/throughput/by-priority-bracket")
    def internal_brain_workflow_throughput_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_workflow_throughput_by_priority_bracket(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/workflow/throughput/by-case-type")
    def internal_brain_workflow_throughput_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_workflow_throughput_by_case_type(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/top-by-age")
    def internal_brain_cases_top_by_age(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_top_actionable_cases_by_age(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/top-by-priority")
    def internal_brain_cases_top_by_priority(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_top_actionable_cases_by_priority(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/top-degraded")
    def internal_brain_cases_top_degraded(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_top_actionable_degraded_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/top-stalled")
    def internal_brain_cases_top_stalled(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_top_stalled_actionable_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/recently-opened")
    def internal_brain_cases_recently_opened(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_opened_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/recently-acknowledged")
    def internal_brain_cases_recently_acknowledged(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_acknowledged_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/recently-resolved")
    def internal_brain_cases_recently_resolved(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_resolved_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )
