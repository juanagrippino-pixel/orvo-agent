import pytest

from app.brain.gateway_contracts import (
    GatewayContractError,
    GatewayRateLimitPolicy,
    GatewayRoutePolicy,
    GatewayServiceCatalog,
    GatewayServiceCatalogEntry,
    build_gateway_context,
    default_gateway_service_catalog,
    validate_gateway_route_policy,
)


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
