from __future__ import annotations

from datetime import datetime, timezone
from flask import request

from app.brain.operator_api import *  # noqa: F401,F403

from .common import (
    _internal_success,
    _with_internal_stores,
)


def register_dashboard_view_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/dashboard")
    def internal_brain_dashboard(business_id: str):
        limit = request.args.get("limit")
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_operator_dashboard(
                    case_store,
                    run_ledger,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                    limit=parse_limit(limit, default=10),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-views")
    def internal_brain_case_views(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_builtin_case_views(case_store, business_id=business_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-views/<view_id>")
    def internal_brain_case_view_detail(business_id: str, view_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_builtin_case_view_detail(
                    case_store,
                    business_id=business_id,
                    view_id=view_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-views/<view_id>/cases")
    def internal_brain_case_view_cases(business_id: str, view_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                execute_builtin_case_view(
                    case_store,
                    business_id=business_id,
                    view_id=view_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/case-query-fields")
    def internal_brain_case_query_fields(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_query_fields(field=request.args.get("field")),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/facets")
    def internal_brain_case_facets(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_facets(
                    case_store,
                    business_id=business_id,
                    field=request.args.get("field"),
                    jql=request.args.get("jql"),
                    limit=request.args.get("limit"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/<case_id>")
    def internal_brain_case_detail(business_id: str, case_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_case_projection(case_store, business_id=business_id, case_id=case_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/<case_id>/timeline")
    def internal_brain_case_timeline(business_id: str, case_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_timeline(
                    case_store,
                    business_id=business_id,
                    case_id=case_id,
                    event_type=request.args.get("event_type"),
                    actor_type=request.args.get("actor_type"),
                    actor_ref=request.args.get("actor_ref"),
                    limit=request.args.get("limit"),
                ),
            ),
        )
