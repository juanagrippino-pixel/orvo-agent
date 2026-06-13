from __future__ import annotations

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403

from .common import _internal_success, _with_internal_stores


def register_case_recent_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases/recent")
    def internal_brain_cases_recent(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recent_case_activity(
                    case_store,
                    business_id=business_id,
                    activity_type=request.args.get("activity_type"),
                    limit=request.args.get("limit"),
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

    @app.get("/internal/brain/businesses/<business_id>/cases/recently-in-progress")
    def internal_brain_cases_recently_in_progress(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_in_progress_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/recently-assigned")
    def internal_brain_cases_recently_assigned(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_assigned_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/recently-commented")
    def internal_brain_cases_recently_commented(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_commented_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/recently-updated")
    def internal_brain_cases_recently_updated(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_updated_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/recently-reopened")
    def internal_brain_cases_recently_reopened(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_reopened_cases(
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

    @app.get("/internal/brain/businesses/<business_id>/cases/recently-dismissed")
    def internal_brain_cases_recently_dismissed(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_recently_dismissed_cases(
                    case_store,
                    business_id=business_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )
