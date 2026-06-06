from __future__ import annotations

from app.brain.operator_api import (
    summarize_case_resolution_latency_histogram,
    summarize_case_resolution_latency_histogram_by_case_type,
    summarize_case_resolution_latency_histogram_by_entity_kind,
    summarize_case_resolution_latency_histogram_by_priority_bracket,
    summarize_case_resolution_latency_histogram_by_source_connector,
)

from .common import _internal_success, _with_internal_stores


def register_case_resolution_latency_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases/resolution-latency")
    def internal_brain_cases_resolution_latency(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_resolution_latency_histogram(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/resolution-latency/by-severity")
    def internal_brain_cases_resolution_latency_by_severity(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_resolution_latency_histogram(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/resolution-latency/by-case-type")
    def internal_brain_cases_resolution_latency_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_resolution_latency_histogram_by_case_type(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/resolution-latency/by-entity-kind")
    def internal_brain_cases_resolution_latency_by_entity_kind(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_resolution_latency_histogram_by_entity_kind(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/resolution-latency/by-source-connector")
    def internal_brain_cases_resolution_latency_by_source_connector(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_resolution_latency_histogram_by_source_connector(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/resolution-latency/by-priority-bracket")
    def internal_brain_cases_resolution_latency_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_resolution_latency_histogram_by_priority_bracket(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )
