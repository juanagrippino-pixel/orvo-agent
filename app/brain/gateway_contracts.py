"""Gateway middleware contracts for Orvo Brain Python runtime surfaces.

This module keeps request-boundary conventions in a thin service layer so Flask
routes can remain orchestration code: request IDs, idempotency keys, auth scheme
inspection, rate-limit decisions, and audit provenance are normalized before
they reach case, ledger, connector, or runtime stores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Any, Literal, Mapping
from uuid import uuid4

from app.brain.operator_auth import safe_internal_operator_actor_ref
from app.brain.security.redaction import redact_secrets, redact_text

RequestId = str
RouteKey = str
Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
GatewayIdempotencyMode = Literal["optional", "required", "forbidden"]

_REQUEST_ID_LENGTH_LIMIT: int = 128
_IDEMPOTENCY_KEY_LENGTH_LIMIT: int = 128
_IDEMPOTENCY_KEY_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_ROUTE_KEY_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_SAFE_AUTH_SCHEMES: frozenset[str] = frozenset({"Bearer", "Basic", "Token", "ApiKey", "Api-Key"})
_SECRET_KEY_RE: re.Pattern[str] = re.compile(
    r"(?i)\b(access_token|refresh_token|api_key|apikey|authorization|auth_header|password|private_key|credential|cookie|session|signature|secret|token)\b"
)


class GatewayContractError(ValueError):
    """Safe gateway contract violation.

    Messages are redacted because headers and keys are caller-controlled and may
    accidentally contain credential material.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = redact_text(message) or "[REDACTED]"
        super().__init__(self.message)


@dataclass(frozen=True)
class GatewayRequestContext:
    """Normalized request metadata that is safe to persist in audit/ledger data."""

    request_id: RequestId
    route_key: RouteKey
    method: Method
    business_id: str | None = None
    actor_ref: str | None = None
    auth_scheme: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class GatewayRateLimitPolicy:
    """Allowlisted rate-limit metadata for a gateway surface.

    The first runtime slice deliberately avoids storage semantics. The decision
    helper is deterministic and can be wired to Redis/SQLite counters later
    without changing route code or audit contracts.
    """

    scope: Literal["business", "operator", "connector"]
    requests_per_minute: int | None = None
    retry_after_seconds: int = 60

    def __post_init__(self) -> None:
        if self.requests_per_minute is not None and self.requests_per_minute <= 0:
            raise GatewayContractError(
                "invalid_rate_limit_policy",
                "requests_per_minute must be positive when configured.",
            )
        if self.retry_after_seconds <= 0:
            raise GatewayContractError(
                "invalid_rate_limit_policy",
                "retry_after_seconds must be positive.",
            )


@dataclass(frozen=True)
class GatewayRateLimitDecision:
    """Deterministic rate-limit decision for middleware/storage integration."""

    allowed: bool
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class GatewayRoutePolicy:
    """Allowlisted gateway policy for one route/method pair.

    This is still deterministic and storage-agnostic. It lets future middleware
    enforce idempotency, business scoping, auth-shape expectations, and
    rate-limit decisions without copying validation rules into Flask handlers.
    """

    route_key: RouteKey
    method: Method
    idempotency_mode: GatewayIdempotencyMode = "optional"
    requires_business_id: bool = False
    requires_actor_ref: bool = False
    allowed_auth_schemes: tuple[str, ...] = ()
    rate_limit_policy: GatewayRateLimitPolicy | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_key", _normalize_route_key(self.route_key))
        object.__setattr__(self, "method", _normalize_method(self.method))
        object.__setattr__(self, "allowed_auth_schemes", tuple(self.allowed_auth_schemes))
        if self.idempotency_mode not in {"optional", "required", "forbidden"}:
            raise GatewayContractError(
                "invalid_gateway_route_policy",
                "Idempotency mode must be optional, required, or forbidden.",
            )
        invalid_auth_schemes = [scheme for scheme in self.allowed_auth_schemes if scheme not in _SAFE_AUTH_SCHEMES]
        if invalid_auth_schemes:
            raise GatewayContractError(
                "invalid_gateway_route_policy",
                "Allowed auth schemes must come from the safe gateway auth-scheme allowlist.",
            )


@dataclass(frozen=True)
class GatewayServiceCatalogEntry:
    """One service-catalog row binding a route to a gateway policy."""

    service: str
    description: str
    policy: GatewayRoutePolicy

    @property
    def route_key(self) -> RouteKey:
        return self.policy.route_key

    @property
    def method(self) -> Method:
        return self.policy.method


@dataclass(frozen=True)
class GatewayServiceCatalog:
    """Read-only route-policy catalog for gateway middleware/service registry use.

    The catalog is intentionally storage-agnostic: it does not authenticate,
    rate-limit, or persist decisions. It centralizes the allowlisted route/method
    policies that future middleware can evaluate before delegating to business
    handlers.
    """

    entries: tuple[GatewayServiceCatalogEntry, ...] = field(default_factory=tuple)
    _index: Mapping[tuple[RouteKey, Method], GatewayServiceCatalogEntry] = field(
        init=False,
        repr=False,
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        index: dict[tuple[RouteKey, Method], GatewayServiceCatalogEntry] = {}
        for entry in self.entries:
            key = (entry.route_key, entry.method)
            if key in index:
                raise GatewayContractError(
                    "duplicate_gateway_service_route",
                    "Gateway service catalog already contains this route/method policy.",
                )
            index[key] = entry
        object.__setattr__(self, "_index", MappingProxyType(index))

    def register(self, entry: GatewayServiceCatalogEntry) -> "GatewayServiceCatalog":
        """Return a new catalog with the service route registered."""

        key = (entry.route_key, entry.method)
        if key in self._index:
            raise GatewayContractError(
                "duplicate_gateway_service_route",
                "Gateway service catalog already contains this route/method policy.",
            )
        return GatewayServiceCatalog((*self.entries, entry))

    def policy_for(self, route_key: str, method: str) -> GatewayRoutePolicy:
        """Return a registered route policy or fail closed without echoing route keys."""

        method_value: Method = _normalize_method(method)
        try:
            return self._index[(route_key, method_value)].policy
        except KeyError as exc:
            raise GatewayContractError(
                "unknown_gateway_service_route",
                "Gateway route policy is not registered.",
            ) from exc

    def entry_for(self, route_key: str, method: str) -> GatewayServiceCatalogEntry:
        """Return the catalog entry for a route/method pair."""

        method_value: Method = _normalize_method(method)
        try:
            return self._index[(route_key, method_value)]
        except KeyError as exc:
            raise GatewayContractError(
                "unknown_gateway_service_route",
                "Gateway route policy is not registered.",
            ) from exc

    def services(self) -> tuple[str, ...]:
        """Return service names in insertion order, without duplicates."""

        seen: set[str] = set()
        ordered: list[str] = []
        for entry in self.entries:
            if entry.service in seen:
                continue
            seen.add(entry.service)
            ordered.append(entry.service)
        return tuple(ordered)

    def entries_for_service(self, service: str) -> tuple[GatewayServiceCatalogEntry, ...]:
        """Return catalog entries for one service in insertion order."""

        return tuple(entry for entry in self.entries if entry.service == service)


@dataclass(frozen=True)
class GatewayRouteDecision:
    """Decision returned by a gateway route-policy evaluation."""

    allowed: bool
    reason: str | None = None
    retry_after_seconds: int | None = None


def normalize_request_id(value: str | None) -> RequestId:
    """Return a safe request ID, generating one when the caller omits it."""

    if value is None or not value.strip():
        return f"req_{uuid4().hex}"
    request_id = value.strip()
    if len(request_id) > _REQUEST_ID_LENGTH_LIMIT:
        return "[REDACTED]"
    redacted = redact_text(request_id) or "[REDACTED]"
    return request_id if redacted == request_id else "[REDACTED]"


def normalize_idempotency_key(value: str | None) -> str | None:
    """Validate a mutating request idempotency key without echoing it.

    Missing keys remain optional so read-only surfaces can reuse the gateway
    context builder. When a key is present, it must be a short safe identifier
    and must not be secret-shaped.
    """

    if value is None or not value.strip():
        return None
    key = value.strip()
    if len(key) > _IDEMPOTENCY_KEY_LENGTH_LIMIT:
        raise GatewayContractError(
            "invalid_idempotency_key",
            "Idempotency key is too long.",
        )
    if redact_text(key) != key or _IDEMPOTENCY_KEY_RE.fullmatch(key) is None:
        raise GatewayContractError(
            "invalid_idempotency_key",
            "Idempotency key contains unsafe characters or secret-shaped material.",
        )
    return key


def authorization_scheme(value: str | None) -> str | None:
    """Return only the auth scheme from an Authorization header.

    The credential tail is intentionally discarded. Secret-shaped credential
    tails such as ``access_token=...`` collapse the whole header to
    ``[REDACTED]`` so accidental credential paste is not persisted as a scheme.
    """

    if value is None or not value.strip():
        return None
    header = value.strip()
    if " " not in header and "\t" not in header:
        return "[REDACTED]"

    scheme, _credential_tail = header.split(None, 1)
    if scheme in _SAFE_AUTH_SCHEMES:
        return "[REDACTED]" if _SECRET_KEY_RE.search(header) else scheme

    redacted_scheme = redact_text(scheme) or "[REDACTED]"
    return scheme if redacted_scheme == scheme else "[REDACTED]"


def _header(headers: Mapping[str, str] | None, *names: str) -> str | None:
    if headers is None:
        return None
    lowered = {name.lower(): name for name in names}
    for raw_name, value in headers.items():
        if raw_name in names or raw_name.lower() in lowered:
            return str(value)
    return None


def _safe_business_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    business_id = value.strip()
    redacted = redact_text(business_id) or "[REDACTED]"
    return business_id if redacted == business_id else "[REDACTED]"


def _normalize_method(value: str | None) -> Method:
    if value is None or not value.strip():
        raise GatewayContractError("invalid_method", "HTTP method is required.")
    method = value.strip().upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise GatewayContractError("invalid_method", "HTTP method is not allowlisted.")
    return method  # type: ignore[return-value]


def _normalize_route_key(route_key: str) -> RouteKey:
    redacted = redact_text(route_key) or "[REDACTED]"
    if redacted != route_key:
        raise GatewayContractError(
            "invalid_route_key",
            "Route key contains unsafe material.",
        )
    if _ROUTE_KEY_RE.fullmatch(route_key) is None:
        raise GatewayContractError(
            "invalid_route_key",
            "Route key must be a short safe identifier.",
        )
    return route_key


def build_gateway_context(
    headers: Mapping[str, str] | None,
    *,
    route_key: str,
    method: str | None = None,
    business_id: str | None = None,
    actor_ref: str | None = None,
    idempotency_key: str | None = None,
) -> GatewayRequestContext:
    """Build normalized gateway context from request headers and route metadata."""

    effective_actor_ref = actor_ref or _header(headers, "X-Orvo-Operator", "X-Operator")
    effective_idempotency_key = idempotency_key or _header(
        headers,
        "Idempotency-Key",
        "X-Idempotency-Key",
    )

    return GatewayRequestContext(
        request_id=normalize_request_id(_header(headers, "X-Request-ID", "X-Orvo-Request-ID")),
        route_key=_normalize_route_key(route_key),
        method=_normalize_method(method or _header(headers, "X-HTTP-Method-Override")),
        business_id=_safe_business_id(business_id),
        actor_ref=safe_internal_operator_actor_ref(effective_actor_ref),
        auth_scheme=authorization_scheme(_header(headers, "Authorization")),
        idempotency_key=normalize_idempotency_key(effective_idempotency_key),
    )


def evaluate_gateway_rate_limit(
    policy: GatewayRateLimitPolicy,
    *,
    current_requests: int,
) -> GatewayRateLimitDecision:
    """Evaluate a deterministic rate-limit decision from a counter snapshot."""

    if policy.requests_per_minute is None:
        return GatewayRateLimitDecision(allowed=True)
    if current_requests < policy.requests_per_minute:
        return GatewayRateLimitDecision(allowed=True)
    return GatewayRateLimitDecision(
        allowed=False,
        retry_after_seconds=policy.retry_after_seconds,
    )


_INTERNAL_BRAIN_AUTH_SCHEMES: tuple[str, ...] = ("Bearer",)
_INTERNAL_BRAIN_ACTION_RATE_LIMIT = GatewayRateLimitPolicy(
    scope="business",
    requests_per_minute=30,
    retry_after_seconds=60,
)


def _internal_brain_policy(
    route_key: str,
    method: Method,
    *,
    description: str,
    idempotency_mode: GatewayIdempotencyMode = "optional",
    requires_business_id: bool = True,
    rate_limit_policy: GatewayRateLimitPolicy | None = None,
) -> GatewayServiceCatalogEntry:
    return GatewayServiceCatalogEntry(
        service="internal-brain",
        description=description,
        policy=GatewayRoutePolicy(
            route_key=route_key,
            method=method,
            idempotency_mode=idempotency_mode,
            requires_business_id=requires_business_id,
            requires_actor_ref=True,
            allowed_auth_schemes=_INTERNAL_BRAIN_AUTH_SCHEMES,
            rate_limit_policy=rate_limit_policy,
        ),
    )


def default_gateway_service_catalog() -> GatewayServiceCatalog:
    """Return Orvo Brain's built-in gateway route-policy catalog."""

    return GatewayServiceCatalog(
        (
            _internal_brain_policy(
                "internal.brain.runtime.compile_preview",
                "POST",
                description="Compile an immutable runtime preview plan.",
            ),
            _internal_brain_policy(
                "internal.brain.connectors.readiness",
                "GET",
                description="Read connector readiness projections.",
            ),
            _internal_brain_policy(
                "internal.brain.operator_session",
                "GET",
                description="Read the authenticated operator session projection.",
            ),
            _internal_brain_policy(
                "internal.brain.runs.list",
                "GET",
                description="List run ledger projections.",
            ),
            _internal_brain_policy(
                "internal.brain.runs.dispatch_status_summary",
                "GET",
                description="Summarize run dispatch status.",
            ),
            _internal_brain_policy(
                "internal.brain.runs.detail",
                "GET",
                description="Read one run ledger projection.",
            ),
            _internal_brain_policy(
                "internal.brain.whatsapp.delivery_statuses",
                "GET",
                description="Read WhatsApp delivery status audit events.",
                requires_business_id=False,
            ),
            _internal_brain_policy(
                "internal.brain.cases.list",
                "GET",
                description="List actionable operational cases.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.summary",
                "GET",
                description="Summarize the operational case queue.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.case_actions",
                "GET",
                description="List the case action catalog for the operator role.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.detail",
                "GET",
                description="Read one operational case projection.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.timeline",
                "GET",
                description="List one operational case timeline.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.action",
                "POST",
                description="Execute one whitelisted case action.",
                idempotency_mode="required",
                rate_limit_policy=_INTERNAL_BRAIN_ACTION_RATE_LIMIT,
            ),
            _internal_brain_policy(
                "internal.brain.case_views.list",
                "GET",
                description="List built-in case views.",
            ),
            _internal_brain_policy(
                "internal.brain.case_views.execute",
                "GET",
                description="Execute one built-in case view.",
            ),
            _internal_brain_policy(
                "internal.brain.case_facets.list",
                "GET",
                description="List case queue facets.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.resolution_latency",
                "GET",
                description="Summarize case resolution latency.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.stagnation",
                "GET",
                description="Summarize case queue stagnation.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.acknowledgment_latency",
                "GET",
                description="Summarize case acknowledgment latency.",
            ),
            _internal_brain_policy(
                "internal.brain.cases.handling_latency",
                "GET",
                description="Summarize case handling latency.",
            ),
            _internal_brain_policy(
                "internal.brain.dashboard",
                "GET",
                description="Read the operator dashboard projection.",
            ),
            _internal_brain_policy(
                "internal.brain.operator_audit_events",
                "GET",
                description="Read redacted operator audit events.",
            ),
        )
    )


def validate_gateway_route_policy(
    policy: GatewayRoutePolicy,
    context: GatewayRequestContext,
    *,
    current_requests: int = 0,
) -> GatewayRouteDecision:
    """Evaluate a route policy against normalized gateway request context."""

    if policy.route_key != context.route_key:
        return GatewayRouteDecision(allowed=False, reason="route_key_mismatch")
    if policy.method != context.method:
        return GatewayRouteDecision(allowed=False, reason="method_mismatch")
    if policy.requires_business_id and context.business_id is None:
        return GatewayRouteDecision(allowed=False, reason="business_id_required")
    if policy.requires_actor_ref and context.actor_ref in {None, "anonymous", "[REDACTED]"}:
        return GatewayRouteDecision(allowed=False, reason="actor_ref_required")
    if policy.allowed_auth_schemes and context.auth_scheme not in policy.allowed_auth_schemes:
        return GatewayRouteDecision(allowed=False, reason="auth_scheme_not_allowed")
    if policy.idempotency_mode == "required" and context.idempotency_key is None:
        return GatewayRouteDecision(allowed=False, reason="idempotency_key_required")
    if policy.idempotency_mode == "forbidden" and context.idempotency_key is not None:
        return GatewayRouteDecision(allowed=False, reason="idempotency_key_forbidden")
    if policy.rate_limit_policy is not None:
        rate_decision = evaluate_gateway_rate_limit(
            policy.rate_limit_policy,
            current_requests=current_requests,
        )
        if not rate_decision.allowed:
            return GatewayRouteDecision(
                allowed=False,
                reason="rate_limited",
                retry_after_seconds=rate_decision.retry_after_seconds,
            )
    return GatewayRouteDecision(allowed=True)


def build_gateway_audit_event(
    context: GatewayRequestContext,
    *,
    event_type: str,
    status: str,
    reason: str | None = None,
    data: Any | None = None,
) -> dict[str, Any]:
    """Build a redacted audit/provenance event for gateway boundaries."""

    raw_event: dict[str, Any] = {
        "event_type": event_type,
        "status": status,
        "reason": reason,
        "request_id": context.request_id,
        "route_key": context.route_key,
        "method": context.method,
        "business_id": context.business_id,
        "actor_ref": context.actor_ref,
        "auth_scheme": context.auth_scheme,
        "idempotency_key": context.idempotency_key,
        "data": data,
    }
    safe_event = redact_secrets(raw_event)
    safe_event["redaction_applied"] = safe_event != raw_event
    return safe_event
