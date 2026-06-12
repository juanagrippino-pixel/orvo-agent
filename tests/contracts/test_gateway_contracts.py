import pytest

from app.brain.gateway_contracts import (
    GatewayContractError,
    GatewayRateLimitDecision,
    GatewayRateLimitPolicy,
    GatewayRequestContext,
    authorization_scheme,
    build_gateway_context,
    build_gateway_audit_event,
    evaluate_gateway_rate_limit,
    normalize_idempotency_key,
    normalize_request_id,
)


def test_gateway_request_context_normalizes_auth_actor_and_request_id_without_echoing_secrets():
    context = build_gateway_context(
        {
            "Authorization": "Bearer raw_internal_token_should_not_echo",
            "X-Orvo-Operator": "operator:juan access_token=raw_actor_secret",
            "X-Request-ID": "req-safe",
        },
        route_key="internal.cases.list",
        business_id="artemea",
        method="GET",
    )

    assert context == GatewayRequestContext(
        request_id="req-safe",
        route_key="internal.cases.list",
        method="GET",
        business_id="artemea",
        actor_ref="[REDACTED]",
        auth_scheme="Bearer",
        idempotency_key=None,
    )


def test_gateway_request_context_generates_request_id_when_missing():
    context = build_gateway_context({}, route_key="internal.runs.summary", method="GET")

    assert context.request_id.startswith("req_")
    assert len(context.request_id) <= 36
    assert context.route_key == "internal.runs.summary"


def test_gateway_request_context_rejects_secret_shaped_request_id():
    context = build_gateway_context(
        {"X-Request-ID": "req access_token=raw_request_id_secret"},
        route_key="internal.cases.list",
        method="GET",
    )

    assert context.request_id == "[REDACTED]"


def test_gateway_request_context_rejects_oversized_request_id():
    context = build_gateway_context(
        {"X-Request-ID": "req-" + "a" * 256},
        route_key="internal.cases.list",
        method="GET",
    )

    assert context.request_id == "[REDACTED]"


def test_idempotency_key_contract_accepts_safe_keys_and_rejects_secret_shaped_keys():
    assert normalize_idempotency_key("case-action:artemea:123") == "case-action:artemea:123"

    with pytest.raises(GatewayContractError) as exc:
        normalize_idempotency_key("case-action access_token=raw_idempotency_secret")

    assert exc.value.code == "invalid_idempotency_key"
    assert "raw_idempotency_secret" not in str(exc.value)


def test_idempotency_key_contract_rejects_oversized_keys_without_echoing_value():
    key = "case-action:" + "a" * 256

    with pytest.raises(GatewayContractError) as exc:
        normalize_idempotency_key(key)

    assert exc.value.code == "invalid_idempotency_key"
    assert key not in str(exc.value)


def test_authorization_scheme_never_echoes_token_tail():
    assert authorization_scheme("Bearer raw_internal_token") == "Bearer"
    assert authorization_scheme("Basic dXNlcjpwYXNz") == "Basic"
    assert authorization_scheme("raw_internal_token_should_not_echo") == "[REDACTED]"
    assert authorization_scheme("Bearer access_token=raw_scheme_secret") == "[REDACTED]"


def test_gateway_audit_event_keeps_provenance_safe_and_redacted():
    context = build_gateway_context(
        {
            "Authorization": "Bearer raw_internal_token",
            "X-Orvo-Operator": "operator:juan",
            "X-Request-ID": "req-audit",
            "Idempotency-Key": "audit:artemea:1",
        },
        route_key="internal.cases.ack",
        business_id="artemea",
        method="POST",
    )

    event = build_gateway_audit_event(
        context,
        event_type="operator.case.action.denied",
        status="denied",
        reason="missing_permission",
        data={"note": "Bearer raw_audit_secret"},
    )

    assert event == {
        "event_type": "operator.case.action.denied",
        "status": "denied",
        "reason": "missing_permission",
        "request_id": "req-audit",
        "route_key": "internal.cases.ack",
        "method": "POST",
        "business_id": "artemea",
        "actor_ref": "operator:juan",
        "auth_scheme": "Bearer",
        "idempotency_key": "audit:artemea:1",
        "redaction_applied": True,
        "data": {"note": "Bearer [REDACTED]"},
    }


def test_gateway_rate_limit_policy_is_allowlisted_and_deterministic():
    policy = GatewayRateLimitPolicy(scope="business", requests_per_minute=2, retry_after_seconds=30)

    assert evaluate_gateway_rate_limit(policy, current_requests=1) == GatewayRateLimitDecision(
        allowed=True,
        retry_after_seconds=None,
    )
    assert evaluate_gateway_rate_limit(policy, current_requests=2) == GatewayRateLimitDecision(
        allowed=False,
        retry_after_seconds=30,
    )


def test_gateway_rate_limit_policy_without_limit_allows_by_default():
    assert evaluate_gateway_rate_limit(
        GatewayRateLimitPolicy(scope="operator"), current_requests=100
    ) == GatewayRateLimitDecision(allowed=True, retry_after_seconds=None)
