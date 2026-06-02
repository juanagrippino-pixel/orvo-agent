"""Internal operator authorization helpers.

Transport code authenticates the caller, then uses this service-layer module to
interpret operator roles and permissions. The goal is intentionally small for the
first control-plane slice: keep read-only operators away from mutating case
workflow state while preserving the existing bearer-token gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


AUDIT_READ_PERMISSION: Final[str] = "audit:read"
BUSINESS_ACCESS_PERMISSION: Final[str] = "business:access"
CASE_ACTION_PERMISSION: Final[str] = "case:action"
INTERNAL_READ_PERMISSION: Final[str] = "internal:read"


_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "viewer": frozenset({INTERNAL_READ_PERMISSION}),
    "operator": frozenset({INTERNAL_READ_PERMISSION, CASE_ACTION_PERMISSION}),
    "admin": frozenset({INTERNAL_READ_PERMISSION, CASE_ACTION_PERMISSION, AUDIT_READ_PERMISSION}),
}
_DEFAULT_OPERATOR_ROLE: Final[str] = "operator"


@dataclass(frozen=True)
class InternalOperatorPrincipal:
    """Authenticated internal operator identity plus normalized role."""

    actor_ref: str
    role: str
    allowed_businesses: tuple[str, ...] | None = None


class InternalOperatorAuthorizationError(Exception):
    """Safe authorization failure for internal operator API enforcement."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        role: str,
        permission: str,
        status_code: int = 403,
        allowed_businesses: tuple[str, ...] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.role = role
        self.permission = permission
        self.status_code = status_code
        self.allowed_businesses = allowed_businesses
        super().__init__(message)


def normalize_operator_role(role: str | None) -> str:
    """Return a known internal role, defaulting legacy callers to operator.

    The default keeps existing token-authenticated internal tools compatible
    while allowing new clients to explicitly request read-only ``viewer`` access.
    Unknown roles fail closed rather than silently inheriting privileges.
    """

    if role is None or not role.strip():
        return _DEFAULT_OPERATOR_ROLE
    normalized = role.strip().lower()
    if normalized not in _ROLE_PERMISSIONS:
        raise InternalOperatorAuthorizationError(
            "unknown_operator_role",
            "Unknown operator role.",
            role=normalized,
            permission="role:known",
        )
    return normalized


def parse_allowed_businesses(value: str | None) -> tuple[str, ...] | None:
    """Parse an optional comma-separated operator business allowlist.

    ``None`` means legacy internal clients did not send a grant header and are
    treated as unrestricted for backward compatibility. A present but empty
    header becomes an empty grant set and therefore fails closed.
    """

    if value is None:
        return None
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_internal_operator_principal(
    *,
    actor_ref: str | None,
    role: str | None,
    allowed_businesses_header: str | None = None,
) -> InternalOperatorPrincipal:
    """Build an authorization principal from authenticated operator headers."""

    safe_actor_ref = actor_ref.strip() if isinstance(actor_ref, str) and actor_ref.strip() else "anonymous"
    return InternalOperatorPrincipal(
        actor_ref=safe_actor_ref,
        role=normalize_operator_role(role),
        allowed_businesses=parse_allowed_businesses(allowed_businesses_header),
    )


def require_internal_permission(principal: InternalOperatorPrincipal, permission: str) -> None:
    """Fail closed if the principal role lacks ``permission``."""

    allowed = _ROLE_PERMISSIONS.get(principal.role, frozenset())
    if permission not in allowed:
        raise InternalOperatorAuthorizationError(
            "missing_permission",
            "Operator role lacks required permission.",
            role=principal.role,
            permission=permission,
        )


def require_internal_business_scope(principal: InternalOperatorPrincipal, business_id: str) -> None:
    """Fail closed when an operator grant header excludes ``business_id``."""

    allowed_businesses = principal.allowed_businesses
    if allowed_businesses is None or "*" in allowed_businesses or business_id in allowed_businesses:
        return
    raise InternalOperatorAuthorizationError(
        "business_scope_denied",
        "Operator is not granted access to this business.",
        role=principal.role,
        permission=BUSINESS_ACCESS_PERMISSION,
        allowed_businesses=allowed_businesses,
    )
