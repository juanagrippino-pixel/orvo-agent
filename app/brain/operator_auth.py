"""Internal operator authorization helpers.

Transport code authenticates the caller, then uses this service-layer module to
interpret operator roles and permissions. The goal is intentionally small for the
first control-plane slice: keep read-only operators away from mutating case
workflow state while preserving the existing bearer-token gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


CASE_ACTION_PERMISSION: Final[str] = "case:action"
INTERNAL_READ_PERMISSION: Final[str] = "internal:read"


_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "viewer": frozenset({INTERNAL_READ_PERMISSION}),
    "operator": frozenset({INTERNAL_READ_PERMISSION, CASE_ACTION_PERMISSION}),
    "admin": frozenset({INTERNAL_READ_PERMISSION, CASE_ACTION_PERMISSION}),
}
_DEFAULT_OPERATOR_ROLE: Final[str] = "operator"


@dataclass(frozen=True)
class InternalOperatorPrincipal:
    """Authenticated internal operator identity plus normalized role."""

    actor_ref: str
    role: str


class InternalOperatorAuthorizationError(Exception):
    """Safe authorization failure for internal operator API enforcement."""

    def __init__(self, code: str, message: str, *, role: str, permission: str, status_code: int = 403) -> None:
        self.code = code
        self.message = message
        self.role = role
        self.permission = permission
        self.status_code = status_code
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


def build_internal_operator_principal(*, actor_ref: str | None, role: str | None) -> InternalOperatorPrincipal:
    """Build an authorization principal from authenticated operator headers."""

    safe_actor_ref = actor_ref.strip() if isinstance(actor_ref, str) and actor_ref.strip() else "anonymous"
    return InternalOperatorPrincipal(actor_ref=safe_actor_ref, role=normalize_operator_role(role))


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
