from app.brain.connector_health import (
    classify_connector_failure_detail,
    classify_connector_failure_health_state,
    default_connector_health_state,
)


def test_default_connector_health_state_maps_lifecycle_statuses():
    assert default_connector_health_state("succeeded") == "ok"
    assert default_connector_health_state("skipped") == "degraded"
    assert default_connector_health_state("failed") == "failed"


def test_classify_connector_failure_health_state_recognizes_rate_limit_language():
    assert classify_connector_failure_health_state("HTTP 429 from provider") == "rate_limited"
    assert classify_connector_failure_health_state("Too Many Requests; retry after 60 seconds") == "rate_limited"
    assert classify_connector_failure_health_state("provider quota exceeded for the current window") == "rate_limited"


def test_classify_connector_failure_health_state_recognizes_auth_and_stale_language():
    assert classify_connector_failure_health_state("credentials revoked by provider") == "unauthorized"
    assert classify_connector_failure_health_state("data is too old to support claims") == "stale"
    assert classify_connector_failure_health_state("unexpected malformed response") == "failed"


def test_classify_connector_failure_detail_uses_declared_connector_specific_states_only():
    assert classify_connector_failure_detail(
        "request timed out while fetching orders",
        detailed_states=("network_error", "malformed_response"),
    ) == "network_error"
    assert classify_connector_failure_detail(
        "request timed out while fetching orders",
        detailed_states=("connection_error", "api_server_error"),
    ) == "connection_error"
    assert classify_connector_failure_detail(
        "provider returned malformed response payload",
        detailed_states=("network_error", "malformed_response"),
    ) == "malformed_response"
    assert classify_connector_failure_detail(
        "HTTP 503 upstream server error",
        detailed_states=("api_server_error", "connection_error"),
    ) == "api_server_error"
    assert classify_connector_failure_detail(
        "request timed out while fetching orders",
        detailed_states=("partial_inventory_unavailable",),
    ) is None
