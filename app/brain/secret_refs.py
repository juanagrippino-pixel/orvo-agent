"""Secret-reference resolution helpers for connector execution.

Control-plane artifacts store secret refs/digests only. This module provides the
small execution-boundary contract that turns a registered ref into a raw value
just long enough to call the legacy adapter signature.
"""

from __future__ import annotations

from typing import Mapping, Protocol

from app.brain.config import ConnectorConfig
from app.brain.connector_registry import ConnectorSpec


class SecretResolutionError(ValueError):
    """Typed, redacted connector credential-resolution failure."""

    def __init__(
        self,
        *,
        connector_type: str,
        connector_id: str,
        secret_name: str,
        reason: str = "missing_secret_ref_value",
    ) -> None:
        self.connector_type = connector_type
        self.connector_id = connector_id
        self.secret_name = secret_name
        self.reason = reason
        super().__init__(
            "credential resolution failed "
            f"for connector_type={connector_type} connector_id={connector_id} "
            f"secret_name={secret_name} reason={reason}"
        )


class SecretResolver(Protocol):
    """Execution-boundary protocol for resolving a secret ref to a raw value."""

    def resolve(self, secret_ref: str, *, connector: ConnectorConfig, secret_name: str) -> str: ...


class MappingSecretResolver:
    """Deterministic resolver for tests and local wiring."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def resolve(self, secret_ref: str, *, connector: ConnectorConfig, secret_name: str) -> str:
        try:
            value = self._values[secret_ref]
        except KeyError as exc:
            raise SecretResolutionError(
                connector_type=connector.connector_type,
                connector_id=connector.connector_id,
                secret_name=secret_name,
                reason="secret_ref_not_found",
            ) from exc
        if value == "":
            raise SecretResolutionError(
                connector_type=connector.connector_type,
                connector_id=connector.connector_id,
                secret_name=secret_name,
                reason="secret_ref_empty",
            )
        return value


def connector_with_resolved_secrets(
    *,
    connector: ConnectorConfig,
    spec: ConnectorSpec,
    secret_resolver: SecretResolver | None,
) -> ConnectorConfig:
    """Return an execution-only connector copy with raw legacy secret params.

    Existing inline legacy secrets remain supported for backward compatibility.
    If first-class ``secret_refs`` are present, they are resolved here and copied
    into the legacy adapter param names on a temporary model only.
    """

    if not spec.required_secret_refs:
        return connector

    execution_params = dict(connector.params)
    changed = False
    for requirement in spec.required_secret_refs:
        legacy_field = requirement.legacy_config_field or requirement.name
        secret_ref = connector.secret_refs.get(requirement.name)
        if secret_ref:
            if secret_resolver is None:
                raise SecretResolutionError(
                    connector_type=connector.connector_type,
                    connector_id=connector.connector_id,
                    secret_name=requirement.name,
                    reason="secret_resolver_not_configured",
                )
            execution_params[legacy_field] = secret_resolver.resolve(
                secret_ref,
                connector=connector,
                secret_name=requirement.name,
            )
            changed = True
            continue

        if execution_params.get(legacy_field) in (None, ""):
            raise SecretResolutionError(
                connector_type=connector.connector_type,
                connector_id=connector.connector_id,
                secret_name=requirement.name,
                reason="secret_ref_missing",
            )

    if not changed:
        return connector
    return connector.model_copy(update={"params": execution_params}, deep=True)
