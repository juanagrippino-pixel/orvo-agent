from __future__ import annotations

from datetime import datetime, timezone

from flask import request
from app.brain.operator_api import *  # noqa: F401,F403

from .common import _internal_success, _with_internal_stores


def register_case_activity_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/cases/acknowledgment-latency")
    def internal_brain_cases_acknowledgment_latency(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_acknowledgment_latency_histogram(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-severity")
    def internal_brain_cases_acknowledgment_latency_by_severity(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_acknowledgment_latency_histogram_by_severity(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-case-type")
    def internal_brain_cases_acknowledgment_latency_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_acknowledgment_latency_histogram_by_case_type(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-entity-kind")
    def internal_brain_cases_acknowledgment_latency_by_entity_kind(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_acknowledgment_latency_histogram_by_entity_kind(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-source-connector")
    def internal_brain_cases_acknowledgment_latency_by_source_connector(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_acknowledgment_latency_histogram_by_source_connector(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/acknowledgment-latency/by-priority-bracket")
    def internal_brain_cases_acknowledgment_latency_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_acknowledgment_latency_histogram_by_priority_bracket(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/handling-latency")
    def internal_brain_cases_handling_latency(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_handling_latency_histogram(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/handling-latency/by-severity")
    def internal_brain_cases_handling_latency_by_severity(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_handling_latency_histogram_by_severity(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/handling-latency/by-case-type")
    def internal_brain_cases_handling_latency_by_case_type(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_handling_latency_histogram_by_case_type(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/handling-latency/by-entity-kind")
    def internal_brain_cases_handling_latency_by_entity_kind(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_handling_latency_histogram_by_entity_kind(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/handling-latency/by-source-connector")
    def internal_brain_cases_handling_latency_by_source_connector(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_handling_latency_histogram_by_source_connector(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/handling-latency/by-priority-bracket")
    def internal_brain_cases_handling_latency_by_priority_bracket(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_handling_latency_histogram_by_priority_bracket(
                    case_store,
                    business_id=business_id,
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


    @app.get("/internal/brain/businesses/<business_id>/workflow/throughput/by-entity-kind")
    def internal_brain_workflow_throughput_by_entity_kind(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_workflow_throughput_by_entity_kind(
                    case_store,
                    business_id=business_id,
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/workflow/throughput/by-source-connector")
    def internal_brain_workflow_throughput_by_source_connector(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_case_workflow_throughput_by_source_connector(
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


    def _register_recent_cases_route(path_suffix: str, endpoint_name: str, projection):
        def _handler(business_id: str, _projection=projection):
            return _with_internal_stores(
                business_id,
                lambda case_store, run_ledger: _internal_success(
                    business_id,
                    _projection(
                        case_store,
                        business_id=business_id,
                        limit=request.args.get("limit"),
                    ),
                ),
            )

        _handler.__name__ = endpoint_name
        app.add_url_rule(
            f"/internal/brain/businesses/<business_id>/cases/{path_suffix}",
            endpoint=endpoint_name,
            view_func=_handler,
            methods=["GET"],
        )

    _register_recent_cases_route(
        "recently-opened",
        "internal_brain_cases_recently_opened",
        list_recently_opened_cases,
    )
    _register_recent_cases_route(
        "recently-reopened",
        "internal_brain_cases_recently_reopened",
        list_recently_reopened_cases,
    )
    _register_recent_cases_route(
        "recently-acknowledged",
        "internal_brain_cases_recently_acknowledged",
        list_recently_acknowledged_cases,
    )
    _register_recent_cases_route(
        "recently-in-progress",
        "internal_brain_cases_recently_in_progress",
        list_recently_in_progress_cases,
    )
    _register_recent_cases_route(
        "recently-resolved",
        "internal_brain_cases_recently_resolved",
        list_recently_resolved_cases,
    )
    _register_recent_cases_route(
        "recently-dismissed",
        "internal_brain_cases_recently_dismissed",
        list_recently_dismissed_cases,
    )
