from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operator_api import *  # noqa: F401,F403

from .common import _internal_success, _with_internal_stores


def register_case_stagnation_routes(app):
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

    @app.get("/internal/brain/businesses/<business_id>/cases/stagnation/by-case-type")
    def internal_brain_cases_stagnation_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_stagnation_by_case_type(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/stagnation/by-entity-kind")
    def internal_brain_cases_stagnation_by_entity_kind(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_stagnation_by_entity_kind(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/stagnation/by-source-connector")
    def internal_brain_cases_stagnation_by_source_connector(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_stagnation_by_source_connector(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/stagnation/by-severity")
    def internal_brain_cases_stagnation_by_severity(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_queue_stagnation_by_severity(
                    case_store,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )
