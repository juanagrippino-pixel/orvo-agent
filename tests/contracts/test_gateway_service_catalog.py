from pathlib import Path

import pytest

from app.brain.gateway_contracts import (
    GatewayContractError,
    GatewayPathIdentity,
    GatewayRateLimitPolicy,
    GatewayRouteIdentity,
    GatewayRoutePolicy,
    GatewayServiceCatalog,
    GatewayServiceCatalogDiff,
    GatewayServiceCatalogEntry,
    build_gateway_context,
    default_gateway_service_catalog,
    render_gateway_service_catalog_markdown,
    validate_gateway_route_policy,
)


def test_gateway_service_catalog_diff_reports_added_and_removed_routes():
    base = GatewayServiceCatalog(
        (
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Read one route.",
                path_pattern="/internal/brain/businesses/<business_id>/runs/<run_id>",
                policy=GatewayRoutePolicy(
                    route_key="internal.brain.runs.detail",
                    method="GET",
                ),
            ),
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Compile runtime.",
                path_pattern="/internal/brain/businesses/<business_id>/runtime/compile-preview",
                policy=GatewayRoutePolicy(
                    route_key="internal.brain.runtime.compile_preview",
                    method="POST",
                ),
            ),
        )
    )
    other = GatewayServiceCatalog(
        (
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Read one route.",
                path_pattern="/internal/brain/businesses/<business_id>/runs/<run_id>",
                policy=GatewayRoutePolicy(
                    route_key="internal.brain.runs.detail",
                    method="GET",
                ),
            ),
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Read connector readiness.",
                path_pattern="/internal/brain/businesses/<business_id>/connectors/readiness",
                policy=GatewayRoutePolicy(
                    route_key="internal.brain.connectors.readiness",
                    method="GET",
                ),
            ),
        )
    )

    diff = base.diff(other)

    assert diff == GatewayServiceCatalogDiff(
        added=(
            GatewayRouteIdentity(
                service="internal-brain",
                route_key="internal.brain.connectors.readiness",
                method="GET",
                path_pattern="/internal/brain/businesses/<business_id>/connectors/readiness",
            ),
        ),
        removed=(
            GatewayRouteIdentity(
                service="internal-brain",
                route_key="internal.brain.runtime.compile_preview",
                method="POST",
                path_pattern="/internal/brain/businesses/<business_id>/runtime/compile-preview",
            ),
        ),
    )
    assert diff.is_empty is False
    assert base.diff(base).is_empty is True


def test_gateway_service_catalog_path_diff_ignores_route_key_for_coverage_checks():
    catalog = GatewayServiceCatalog(
        (
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Read one route.",
                path_pattern="/internal/brain/businesses/<business_id>/runs/<run_id>",
                policy=GatewayRoutePolicy(
                    route_key="internal.brain.runs.detail",
                    method="GET",
                ),
            ),
        )
    )
    actual_routes = GatewayServiceCatalog(
        (
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="internal_brain_run_detail",
                path_pattern="/internal/brain/businesses/<business_id>/runs/<run_id>",
                policy=GatewayRoutePolicy(
                    route_key="internal_brain_run_detail",
                    method="GET",
                ),
            ),
        )
    )

    assert catalog.path_diff(actual_routes) == GatewayServiceCatalogDiff()
    assert catalog.path_diff(actual_routes).path_added == ()


def test_gateway_service_catalog_rejects_duplicate_route_method():
    policy = GatewayRoutePolicy(
        route_key="internal.brain.runtime.compile_preview",
        method="POST",
        requires_business_id=True,
        requires_actor_ref=True,
        allowed_auth_schemes=("Bearer",),
    )
    catalog = GatewayServiceCatalog(
        (
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Compile a runtime preview.",
                policy=policy,
            ),
        )
    )

    with pytest.raises(GatewayContractError) as exc:
        catalog.register(
            GatewayServiceCatalogEntry(
                service="internal-brain",
                description="Duplicate runtime compile route.",
                policy=policy,
            )
        )

    assert exc.value.code == "duplicate_gateway_service_route"
    assert "internal.brain.runtime.compile_preview" not in str(exc.value)


def test_gateway_service_catalog_returns_registered_policy_without_echoing_unknown_route():
    catalog = GatewayServiceCatalog()

    with pytest.raises(GatewayContractError) as exc:
        catalog.policy_for("internal.brain.access_token=raw_route_secret", "POST")

    assert exc.value.code == "unknown_gateway_service_route"
    assert "access_token" not in str(exc.value)


def test_default_gateway_service_catalog_contains_internal_runtime_compile_preview():
    catalog = default_gateway_service_catalog()
    policy = catalog.policy_for("internal.brain.runtime.compile_preview", "POST")

    assert policy == GatewayRoutePolicy(
        route_key="internal.brain.runtime.compile_preview",
        method="POST",
        requires_business_id=True,
        requires_actor_ref=True,
        allowed_auth_schemes=("Bearer",),
    )


def test_default_gateway_service_catalog_enforces_case_action_idempotency_and_rate_limit():
    catalog = default_gateway_service_catalog()
    policy = catalog.policy_for("internal.brain.cases.action", "POST")
    context = build_gateway_context(
        {"Authorization": "Bearer route_token", "X-Orvo-Operator": "operator:ana"},
        route_key="internal.brain.cases.action",
        business_id="artemea",
        method="POST",
    )

    decision = validate_gateway_route_policy(policy, context, current_requests=1)

    assert decision.reason == "idempotency_key_required"
    assert policy.rate_limit_policy == GatewayRateLimitPolicy(
        scope="business",
        requests_per_minute=30,
        retry_after_seconds=60,
    )


def test_gateway_service_catalog_resolves_request_path_to_specific_static_route_policy():
    catalog = default_gateway_service_catalog()

    policy = catalog.policy_for_request_path(
        "/internal/brain/businesses/artemea/cases/summary",
        "GET",
    )

    assert policy.route_key == "internal.brain.cases.summary"


def test_gateway_service_catalog_resolves_dynamic_request_path_for_mutating_case_action():
    catalog = default_gateway_service_catalog()

    entry = catalog.entry_for_request_path(
        "/internal/brain/businesses/artemea/cases/CASE-123/actions",
        "POST",
    )

    assert entry.service == "internal-brain"
    assert entry.route_key == "internal.brain.cases.action"


def test_gateway_service_catalog_request_path_matching_prefers_static_summary_over_case_id_slot():
    catalog = default_gateway_service_catalog()

    summary = catalog.entry_for_request_path(
        "/internal/brain/businesses/artemea/cases/summary",
        "GET",
    )
    detail = catalog.entry_for_request_path(
        "/internal/brain/businesses/artemea/cases/CASE-123",
        "GET",
    )

    assert summary.route_key == "internal.brain.cases.summary"
    assert detail.route_key == "internal.brain.cases.detail"


def test_gateway_service_catalog_request_path_lookup_fails_closed_without_echoing_path():
    catalog = default_gateway_service_catalog()

    with pytest.raises(GatewayContractError) as exc:
        catalog.entry_for_request_path(
            "/internal/brain/businesses/artemea/cases/access_token=raw_path_secret",
            "GET",
        )

    assert exc.value.code == "unknown_gateway_service_route"
    assert "raw_path_secret" not in str(exc.value)


def test_render_gateway_service_catalog_markdown_lists_core_internal_brain_routes():
    markdown = render_gateway_service_catalog_markdown(default_gateway_service_catalog())

    assert markdown.startswith("# Gateway service catalog\n")
    assert "## internal-brain" in markdown
    assert "| POST | /internal/brain/businesses/<business_id>/runtime/compile-preview | internal.brain.runtime.compile_preview |" in markdown
    assert "| POST | /internal/brain/businesses/<business_id>/cases/<case_id>/actions | internal.brain.cases.action |" in markdown
    assert "30 rpm / retry 60s" in markdown
    assert "optional" in markdown
    assert "required" in markdown


def test_committed_gateway_service_catalog_doc_matches_default_catalog_snapshot():
    doc_path = Path(__file__).parents[2] / "docs" / "specs" / "gateway-service-catalog.md"

    assert doc_path.read_text(encoding="utf-8") == render_gateway_service_catalog_markdown(
        default_gateway_service_catalog()
    )
