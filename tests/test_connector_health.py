from app.brain.connector_health import (
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
