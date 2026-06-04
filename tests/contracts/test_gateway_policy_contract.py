import pytest

from app.brain.operator_auth import (
    CASE_ACTION_PERMISSION,
    INTERNAL_READ_PERMISSION,
    RUNTIME_EXECUTE_PERMISSION,
    permissions_for_role,
)

def test_default_gateway_policy_registry_covers_current_internal_boundaries():
    from app.brain.gateway_policy import default_gateway_policy_registry

    registry = default_gateway_policy_registry()

    assert registry.route_keys() == [
        "operator_api.case_queue.read",
        "operator_api.case_action.mutate",
        "runtime.force_run.mutate",
    ]
    case_queue = registry.get("operator_api.case_queue.read")
    case_action = registry.get("operator_api.case_action.mutate")

    assert case_queue.method == "GET"
    assert case_queue.required_permissions == (INTERNAL_READ_PERMISSION,)
    assert case_queue.idempotency_required is False
    assert case_queue.rate_limit.bucket == "operator_api_read"

    assert case_action.method == "POST"
    assert case_action.required_permissions == (CASE_ACTION_PERMISSION,)
    assert case_action.idempotency_required is True
    assert case_action.audit_event_type == "operator_case_action_requested"

    assert registry.get("operator_api.case_queue.read").enforcement_state == "enforced"
    assert registry.get("operator_api.case_action.mutate").enforcement_state == "enforced"
    assert registry.get("runtime.force_run.mutate").enforcement_state == "contract_only"


def test_gateway_policy_permissions_reuse_internal_operator_auth_contract():
    from app.brain.gateway_policy import default_gateway_policy_registry

    registry = default_gateway_policy_registry()

    assert registry.get("operator_api.case_queue.read").required_permissions == (
        INTERNAL_READ_PERMISSION,
    )
    assert registry.get("operator_api.case_action.mutate").required_permissions == (
        CASE_ACTION_PERMISSION,
    )
    assert registry.get("runtime.force_run.mutate").required_permissions == (
        RUNTIME_EXECUTE_PERMISSION,
    )


def test_gateway_policy_manifest_is_stable_and_secret_safe():
    from app.brain.gateway_policy import gateway_policy_manifest

    manifest = gateway_policy_manifest()

    assert manifest["schema_version"] == "2026-05-31.gateway-policy.v1"
    assert [route["route_key"] for route in manifest["routes"]] == [
        "operator_api.case_queue.read",
        "operator_api.case_action.mutate",
        "runtime.force_run.mutate",
    ]
    assert {route["route_key"]: route["enforcement_state"] for route in manifest["routes"]} == {
        "operator_api.case_queue.read": "enforced",
        "operator_api.case_action.mutate": "enforced",
        "runtime.force_run.mutate": "contract_only",
    }
    serialized = repr(manifest).lower()
    assert "bearer" not in serialized
    assert "token" not in serialized
    assert "secret" not in serialized
    assert "authorization" not in serialized


def test_gateway_policy_evaluation_requires_auth_business_scope_permission_and_idempotency():
    from app.brain.gateway_policy import (
        GatewayPrincipal,
        GatewayRequestContext,
        default_gateway_policy_registry,
    )

    registry = default_gateway_policy_registry()
    base = GatewayRequestContext(
        route_key="operator_api.case_action.mutate",
        method="POST",
        business_id="artemea",
        idempotency_key="case-action:artemea:case-1:acknowledge:v1",
    )

    unauthenticated = registry.evaluate(base)
    assert unauthenticated.allowed is False
    assert unauthenticated.code == "unauthenticated"
    assert unauthenticated.status_code == 401
    assert unauthenticated.audit_event["decision_code"] == "unauthenticated"

    cross_business = registry.evaluate(
        base.model_copy(
            update={
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("other",),
                    permissions=(CASE_ACTION_PERMISSION,),
                )
            }
        )
    )
    assert cross_business.allowed is False
    assert cross_business.code == "business_scope_forbidden"
    assert cross_business.status_code == 403

    missing_permission = registry.evaluate(
        base.model_copy(
            update={
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(INTERNAL_READ_PERMISSION,),
                )
            }
        )
    )
    assert missing_permission.allowed is False
    assert missing_permission.code == "permission_denied"
    assert missing_permission.status_code == 403

    missing_idempotency = registry.evaluate(
        base.model_copy(
            update={
                "idempotency_key": None,
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(CASE_ACTION_PERMISSION,),
                ),
            }
        )
    )
    assert missing_idempotency.allowed is False
    assert missing_idempotency.code == "missing_idempotency_key"
    assert missing_idempotency.status_code == 428

    invalid_idempotency = registry.evaluate(
        base.model_copy(
            update={
                "idempotency_key": "case-action:other:case-1:acknowledge:v1",
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(CASE_ACTION_PERMISSION,),
                ),
            }
        )
    )
    assert invalid_idempotency.allowed is False
    assert invalid_idempotency.code == "invalid_idempotency_key"
    assert invalid_idempotency.status_code == 400
    assert invalid_idempotency.audit_event["idempotency_key_present"] is True

    whitespace_idempotency = registry.evaluate(
        base.model_copy(
            update={
                "idempotency_key": "case-action:artemea:case 1:acknowledge:v1",
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(CASE_ACTION_PERMISSION,),
                ),
            }
        )
    )
    assert whitespace_idempotency.allowed is False
    assert whitespace_idempotency.code == "invalid_idempotency_key"

    overlong_idempotency = registry.evaluate(
        base.model_copy(
            update={
                "idempotency_key": "case-action:artemea:" + "x" * 201,
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(CASE_ACTION_PERMISSION,),
                ),
            }
        )
    )
    assert overlong_idempotency.allowed is False
    assert overlong_idempotency.code == "invalid_idempotency_key"

    secret_shaped_idempotency = registry.evaluate(
        base.model_copy(
            update={
                "idempotency_key": "case-action:artemea:access_token=raw_gateway_secret",
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(CASE_ACTION_PERMISSION,),
                ),
            }
        )
    )
    assert secret_shaped_idempotency.allowed is False
    assert secret_shaped_idempotency.code == "invalid_idempotency_key"
    assert "raw_gateway_secret" not in repr(secret_shaped_idempotency.model_dump())

    allowed = registry.evaluate(
        base.model_copy(
            update={
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=(CASE_ACTION_PERMISSION,),
                )
            }
        )
    )
    assert allowed.allowed is True
    assert allowed.code == "allowed"
    assert allowed.status_code == 200
    assert allowed.rate_limit_key == "operator_api_mutation:artemea:operator:ana"
    assert allowed.audit_event == {
        "event_type": "operator_case_action_requested",
        "route_key": "operator_api.case_action.mutate",
        "business_id": "artemea",
        "actor_id": "operator:ana",
        "decision_code": "allowed",
        "idempotency_key_present": True,
        "rate_limit_key": "operator_api_mutation:artemea:operator:ana",
        "request_id": None,
        "trace_id": None,
    }


def test_gateway_policy_projects_safe_request_provenance_without_idempotency_values():
    from app.brain.gateway_policy import (
        GatewayPrincipal,
        GatewayRequestContext,
        default_gateway_policy_registry,
    )

    decision = default_gateway_policy_registry().evaluate(
        GatewayRequestContext(
            route_key="runtime.force_run.mutate",
            method="POST",
            business_id="artemea",
            principal=GatewayPrincipal(
                actor_id="operator:ana",
                business_ids=("artemea",),
                permissions=(RUNTIME_EXECUTE_PERMISSION,),
            ),
            idempotency_key="force-run:artemea:2026-06-02:v1",
            request_id="req_access_token=raw_gateway_secret",
            trace_id="trace-20260602-0001",
        )
    )

    assert decision.allowed is True
    assert decision.audit_event["request_id"] == "[REDACTED]"
    assert decision.audit_event["trace_id"] == "trace-20260602-0001"
    assert decision.telemetry_event["schema_version"] == "2026-06-04.gateway-telemetry.v1"
    assert decision.telemetry_event["event_type"] == "gateway.policy.decision"
    assert decision.telemetry_event["policy_schema_version"] == "2026-05-31.gateway-policy.v1"
    assert decision.telemetry_event["source_component"] == "gateway_policy"
    assert decision.telemetry_event["route_key"] == "runtime.force_run.mutate"
    assert decision.telemetry_event["surface"] == "runtime"
    assert decision.telemetry_event["business_id"] == "artemea"
    assert decision.telemetry_event["decision_code"] == "allowed"
    assert decision.telemetry_event["allowed"] is True
    assert decision.telemetry_event["status_code"] == 200
    assert decision.telemetry_event["rate_limit_bucket"] == "runtime_force_run"
    assert decision.telemetry_event["idempotency_required"] is True
    assert decision.telemetry_event["idempotency_key_present"] is True
    assert decision.telemetry_event["request_id"] == "[REDACTED]"
    assert decision.telemetry_event["trace_id"] == "trace-20260602-0001"
    assert len(decision.telemetry_event["provenance_ref"]) == len("gwprov_" + "0" * 16)
    assert "force-run:artemea" not in repr(decision.model_dump())
    assert "raw_gateway_secret" not in repr(decision.model_dump())


def test_gateway_policy_telemetry_provenance_is_deterministic_and_secret_safe():
    from app.brain.gateway_policy import (
        GatewayPrincipal,
        GatewayRequestContext,
        default_gateway_policy_registry,
    )

    registry = default_gateway_policy_registry()
    context = GatewayRequestContext(
        route_key="operator_api.case_queue.read",
        method="GET",
        business_id="artemea",
        principal=GatewayPrincipal(
            actor_id="operator access_token=raw_gateway_secret",
            business_ids=("artemea",),
            permissions=(INTERNAL_READ_PERMISSION,),
        ),
        request_id="req-20260604-0001",
        trace_id="trace_token=raw_gateway_secret",
    )

    first = registry.evaluate(context)
    second = registry.evaluate(context)

    assert first.telemetry_event == second.telemetry_event
    assert first.telemetry_event["actor_id"] == "operator access_token=[REDACTED]"
    assert first.telemetry_event["trace_id"] == "[REDACTED]"
    assert first.telemetry_event["route_enforcement_state"] == "enforced"
    serialized = repr(first.model_dump())
    assert "raw_gateway_secret" not in serialized
    assert "access_token=raw_gateway_secret" not in serialized


def test_gateway_policy_runtime_execute_permission_is_granted_only_to_admin_role():
    from app.brain.gateway_policy import (
        GatewayPrincipal,
        GatewayRequestContext,
        default_gateway_policy_registry,
    )

    registry = default_gateway_policy_registry()
    base = GatewayRequestContext(
        route_key="runtime.force_run.mutate",
        method="POST",
        business_id="artemea",
        idempotency_key="force-run:artemea:2026-06-02:v1",
    )

    operator_decision = registry.evaluate(
        base.model_copy(
            update={
                "principal": GatewayPrincipal(
                    actor_id="operator:ana",
                    business_ids=("artemea",),
                    permissions=tuple(permissions_for_role("operator")),
                )
            }
        )
    )
    assert operator_decision.allowed is False
    assert operator_decision.code == "permission_denied"

    admin_decision = registry.evaluate(
        base.model_copy(
            update={
                "principal": GatewayPrincipal(
                    actor_id="admin:sol",
                    business_ids=("artemea",),
                    permissions=tuple(permissions_for_role("admin")),
                )
            }
        )
    )
    assert admin_decision.allowed is True
    assert admin_decision.code == "allowed"


def test_gateway_policy_redacts_actor_id_in_decision_audit_event():
    from app.brain.gateway_policy import (
        GatewayPrincipal,
        GatewayRequestContext,
        default_gateway_policy_registry,
    )

    decision = default_gateway_policy_registry().evaluate(
        GatewayRequestContext(
            route_key="operator_api.case_queue.read",
            method="GET",
            business_id="artemea",
            principal=GatewayPrincipal(
                actor_id="operator access_token=raw_gateway_secret",
                business_ids=("artemea",),
                permissions=(INTERNAL_READ_PERMISSION,),
            ),
        )
    )

    assert decision.allowed is True
    assert decision.audit_event["actor_id"] == "operator access_token=[REDACTED]"
    assert "raw_gateway_secret" not in repr(decision.model_dump())


def test_gateway_policy_rejects_duplicate_routes_and_unknown_routes():
    from app.brain.gateway_policy import GatewayPolicyRegistry, GatewayRoutePolicy

    policy = GatewayRoutePolicy(
        route_key="operator_api.case_queue.read",
        method="GET",
        path_template="/internal/brain/businesses/{business_id}/cases",
        surface="operator_api",
        required_permissions=(INTERNAL_READ_PERMISSION,),
        audit_event_type="operator_case_queue_requested",
    )

    with pytest.raises(ValueError, match="duplicate gateway route policy"):
        GatewayPolicyRegistry((policy, policy))

    registry = GatewayPolicyRegistry((policy,))
    with pytest.raises(KeyError, match="unknown gateway route policy"):
        registry.get("unknown.route")
