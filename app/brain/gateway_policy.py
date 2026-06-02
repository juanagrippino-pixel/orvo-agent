"""Gateway policy contracts for Orvo Brain internal runtime boundaries.

This module is the lightweight Python-runtime translation of centralized gateway
concerns: authentication, business scoping, permissions, rate-limit buckets,
idempotency requirements, and audit event names. It is deliberately pure and
in-process; it does not introduce proxy, identity-provider, or rate-limit
infrastructure.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.brain.operator_auth import (
    CASE_ACTION_PERMISSION,
    INTERNAL_READ_PERMISSION,
    RUNTIME_EXECUTE_PERMISSION,
)
from app.brain.security.redaction import is_secret_key, redact_text

GatewayMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
GatewaySurface = Literal["operator_api", "runtime"]

GATEWAY_POLICY_SCHEMA_VERSION = "2026-05-31.gateway-policy.v1"


class GatewayRateLimitPolicy(BaseModel):
    """Static rate-limit bucket metadata for a gateway route."""

    model_config = ConfigDict(frozen=True)

    bucket: str
    requests_per_minute: int = Field(default=60, ge=1)
    burst: int = Field(default=10, ge=1)

    def public_manifest(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "requests_per_minute": self.requests_per_minute,
            "burst": self.burst,
        }


class GatewayRoutePolicy(BaseModel):
    """Central policy metadata for one internal route family."""

    model_config = ConfigDict(frozen=True)

    route_key: str
    method: GatewayMethod
    path_template: str
    surface: GatewaySurface
    required_permissions: tuple[str, ...] = Field(default_factory=tuple)
    rate_limit: GatewayRateLimitPolicy = Field(default_factory=lambda: GatewayRateLimitPolicy(bucket="default"))
    idempotency_required: bool = False
    audit_event_type: str

    def public_manifest(self) -> dict[str, Any]:
        return {
            "route_key": self.route_key,
            "method": self.method,
            "path_template": self.path_template,
            "surface": self.surface,
            "required_permissions": list(self.required_permissions),
            "rate_limit": self.rate_limit.public_manifest(),
            "idempotency_required": self.idempotency_required,
            "audit_event_type": self.audit_event_type,
        }


class GatewayPrincipal(BaseModel):
    """Authenticated actor context supplied by the gateway/auth boundary."""

    model_config = ConfigDict(frozen=True)

    actor_id: str
    business_ids: tuple[str, ...] = Field(default_factory=tuple)
    permissions: tuple[str, ...] = Field(default_factory=tuple)

    def can_access_business(self, business_id: str) -> bool:
        return "*" in self.business_ids or business_id in self.business_ids

    def has_permissions(self, required_permissions: tuple[str, ...]) -> bool:
        granted = set(self.permissions)
        return "*" in granted or set(required_permissions).issubset(granted)


class GatewayRequestContext(BaseModel):
    """Request facts needed for deterministic gateway policy evaluation."""

    model_config = ConfigDict(frozen=True)

    route_key: str
    method: GatewayMethod
    business_id: str
    principal: GatewayPrincipal | None = None
    idempotency_key: str | None = None
    request_id: str | None = None
    trace_id: str | None = None


class GatewayPolicyDecision(BaseModel):
    """Gateway decision safe to project into logs, ledgers, or API envelopes."""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    code: str
    status_code: int
    reason: str
    rate_limit_key: str
    idempotency_required: bool
    audit_event: dict[str, Any]


class GatewayPolicyRegistry:
    """Immutable registry of gateway route policies with deterministic evaluation."""

    def __init__(self, policies: tuple[GatewayRoutePolicy, ...]) -> None:
        route_keys = [policy.route_key for policy in policies]
        duplicates = sorted({route_key for route_key in route_keys if route_keys.count(route_key) > 1})
        if duplicates:
            raise ValueError(f"duplicate gateway route policy: {duplicates[0]}")
        self._policies = policies
        self._by_route_key = {policy.route_key: policy for policy in policies}

    @property
    def policies(self) -> tuple[GatewayRoutePolicy, ...]:
        return self._policies

    def route_keys(self) -> list[str]:
        return [policy.route_key for policy in self._policies]

    def get(self, route_key: str) -> GatewayRoutePolicy:
        try:
            return self._by_route_key[route_key]
        except KeyError as exc:
            raise KeyError(f"unknown gateway route policy: {route_key}") from exc

    def public_manifest(self) -> dict[str, Any]:
        return {
            "schema_version": GATEWAY_POLICY_SCHEMA_VERSION,
            "routes": [policy.public_manifest() for policy in self._policies],
        }

    def evaluate(self, context: GatewayRequestContext) -> GatewayPolicyDecision:
        policy = self.get(context.route_key)
        rate_limit_key = _rate_limit_key(policy, context)

        if context.method != policy.method:
            return _decision(
                policy,
                context,
                allowed=False,
                code="method_not_allowed",
                status_code=405,
                reason=f"Expected {policy.method} for {policy.route_key}.",
                rate_limit_key=rate_limit_key,
            )
        if context.principal is None:
            return _decision(
                policy,
                context,
                allowed=False,
                code="unauthenticated",
                status_code=401,
                reason="Authenticated principal is required.",
                rate_limit_key=rate_limit_key,
            )
        if not context.principal.can_access_business(context.business_id):
            return _decision(
                policy,
                context,
                allowed=False,
                code="business_scope_forbidden",
                status_code=403,
                reason="Principal is not scoped to this business.",
                rate_limit_key=rate_limit_key,
            )
        if not context.principal.has_permissions(policy.required_permissions):
            return _decision(
                policy,
                context,
                allowed=False,
                code="permission_denied",
                status_code=403,
                reason="Principal lacks required route permissions.",
                rate_limit_key=rate_limit_key,
            )
        if policy.idempotency_required and not context.idempotency_key:
            return _decision(
                policy,
                context,
                allowed=False,
                code="missing_idempotency_key",
                status_code=428,
                reason="Mutating gateway route requires an idempotency key.",
                rate_limit_key=rate_limit_key,
            )
        if policy.idempotency_required and not _idempotency_key_is_valid(
            context.idempotency_key,
            context.business_id,
        ):
            return _decision(
                policy,
                context,
                allowed=False,
                code="invalid_idempotency_key",
                status_code=400,
                reason=(
                    "Idempotency key must be scoped to the business, contain no whitespace, "
                    "and contain no secret-shaped material."
                ),
                rate_limit_key=rate_limit_key,
            )
        return _decision(
            policy,
            context,
            allowed=True,
            code="allowed",
            status_code=200,
            reason="Request satisfies gateway policy.",
            rate_limit_key=rate_limit_key,
        )


def default_gateway_policy_registry() -> GatewayPolicyRegistry:
    """Return current in-process gateway policies for internal Orvo routes."""

    return GatewayPolicyRegistry(
        (
            GatewayRoutePolicy(
                route_key="operator_api.case_queue.read",
                method="GET",
                path_template="/internal/brain/businesses/{business_id}/cases",
                surface="operator_api",
                required_permissions=(INTERNAL_READ_PERMISSION,),
                rate_limit=GatewayRateLimitPolicy(bucket="operator_api_read", requests_per_minute=120, burst=30),
                idempotency_required=False,
                audit_event_type="operator_case_queue_requested",
            ),
            GatewayRoutePolicy(
                route_key="operator_api.case_action.mutate",
                method="POST",
                path_template="/internal/brain/businesses/{business_id}/cases/{case_id}/actions",
                surface="operator_api",
                required_permissions=(CASE_ACTION_PERMISSION,),
                rate_limit=GatewayRateLimitPolicy(bucket="operator_api_mutation", requests_per_minute=60, burst=10),
                idempotency_required=True,
                audit_event_type="operator_case_action_requested",
            ),
            GatewayRoutePolicy(
                route_key="runtime.force_run.mutate",
                method="POST",
                path_template="/internal/brain/businesses/{business_id}/runs/force",
                surface="runtime",
                required_permissions=(RUNTIME_EXECUTE_PERMISSION,),
                rate_limit=GatewayRateLimitPolicy(bucket="runtime_force_run", requests_per_minute=12, burst=3),
                idempotency_required=True,
                audit_event_type="runtime_force_run_requested",
            ),
        )
    )


def gateway_policy_manifest() -> dict[str, Any]:
    """Return the default public gateway-policy manifest."""

    return default_gateway_policy_registry().public_manifest()


def _idempotency_key_is_valid(idempotency_key: str | None, business_id: str) -> bool:
    if not idempotency_key:
        return False
    if len(idempotency_key) > 200:
        return False
    if any(character.isspace() for character in idempotency_key):
        return False
    if redact_text(idempotency_key) != idempotency_key:
        return False
    return business_id in idempotency_key.split(":")


def _rate_limit_key(policy: GatewayRoutePolicy, context: GatewayRequestContext) -> str:
    actor_id = _safe_actor_id(context)
    return f"{policy.rate_limit.bucket}:{context.business_id}:{actor_id}"


def _safe_actor_id(context: GatewayRequestContext) -> str:
    if context.principal is None:
        return "anonymous"
    return redact_text(context.principal.actor_id) or "[REDACTED]"


def _safe_optional_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = redact_text(value) or "[REDACTED]"
    key, separator, _rest = redacted.partition("=")
    if separator and redacted == value and is_secret_key(key):
        return "[REDACTED]"
    if redacted == value and is_secret_key(value):
        return "[REDACTED]"
    return redacted


def _decision(
    policy: GatewayRoutePolicy,
    context: GatewayRequestContext,
    *,
    allowed: bool,
    code: str,
    status_code: int,
    reason: str,
    rate_limit_key: str,
) -> GatewayPolicyDecision:
    actor_id = _safe_actor_id(context)
    return GatewayPolicyDecision(
        allowed=allowed,
        code=code,
        status_code=status_code,
        reason=reason,
        rate_limit_key=rate_limit_key,
        idempotency_required=policy.idempotency_required,
        audit_event={
            "event_type": policy.audit_event_type,
            "route_key": policy.route_key,
            "business_id": context.business_id,
            "actor_id": actor_id,
            "decision_code": code,
            "idempotency_key_present": bool(context.idempotency_key),
            "rate_limit_key": rate_limit_key,
            "request_id": _safe_optional_identifier(context.request_id),
            "trace_id": _safe_optional_identifier(context.trace_id),
        },
    )
