"""Self-service connector provisioning contracts for the Python control plane.

This module is intentionally validation-only. It translates a developer/operator
request into a deterministic, redacted provisioning plan that can later be wired
to config persistence and run-ledger/audit flows without letting raw connector
secrets become durable control-plane data.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.brain.connector_registry import (
    ConnectorRegistry,
    ConnectorSpec,
    ConnectorValidationIssue as RegistryValidationIssue,
    UnknownConnectorError,
    default_connector_registry,
)
from app.brain.security.redaction import is_secret_key, redact_secrets, redact_text

CONNECTOR_PROVISIONING_SCHEMA_VERSION = "2026-06-07.connector-provisioning.v1"
ProvisioningOperation = Literal["connector.provision"]
ProvisioningNextStep = Literal["ready_for_config_save", "fix_validation_issues"]


class ConnectorProvisioningRequest(BaseModel):
    """Input contract for self-service connector provisioning.

    ``params`` is public connector configuration only. Credential material must be
    supplied as opaque ``secret://`` handles in ``secret_refs``; raw secret values
    are never accepted as valid self-service provisioning input.
    """

    model_config = ConfigDict(frozen=True)

    business_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    connector_type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    secret_refs: dict[str, str] = Field(default_factory=dict)
    actor_id: str = Field(min_length=1)
    strict: bool = True


class ConnectorProvisioningIssue(BaseModel):
    """Redacted provisioning diagnostic for developer/operator surfaces."""

    model_config = ConfigDict(frozen=True)

    code: str
    key: str
    message: str
    severity: Literal["error", "warning"] = "error"


class ConnectorProvisioningConnector(BaseModel):
    """Redacted connector payload safe to expose in provisioning manifests."""

    model_config = ConfigDict(frozen=True)

    connector_id: str
    connector_type: str
    label: str
    capabilities: tuple[str, ...]
    public_params: dict[str, Any]
    secret_refs: dict[str, Any]
    required_config_fields: tuple[str, ...]
    optional_config_fields: tuple[str, ...]
    required_secret_refs: tuple[str, ...]
    required_secret_scopes: dict[str, tuple[str, ...]]
    health_policy: dict[str, Any]
    rate_limit_policy: dict[str, Any]
    lifecycle: dict[str, str]


class ConnectorProvisioningPlan(BaseModel):
    """Deterministic, redacted outcome for a connector provisioning request."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = CONNECTOR_PROVISIONING_SCHEMA_VERSION
    operation: ProvisioningOperation = "connector.provision"
    ok: bool
    next_step: ProvisioningNextStep
    business_id: str
    connector: ConnectorProvisioningConnector
    issues: tuple[ConnectorProvisioningIssue, ...] = ()
    audit_event: dict[str, Any]

    def public_manifest(self) -> dict[str, Any]:
        """Return a stable redacted manifest safe for API/docs projection."""

        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "ok": self.ok,
            "next_step": self.next_step,
            "business_id": self.business_id,
            "connector": self.connector.model_dump(mode="json"),
            "issues": [issue.model_dump(mode="json") for issue in self.issues],
            "audit_event": self.audit_event,
        }


def _redact_secret_refs(secret_refs: Mapping[str, str]) -> dict[str, Any]:
    return redact_secrets({"secret_refs": dict(secret_refs)}).get("secret_refs", {})


def _safe_actor_id(actor_id: str) -> str:
    return redact_text(actor_id) or "[REDACTED]"


def _safe_text(value: str) -> str:
    return redact_text(value) or "[REDACTED]"


def _safe_label(label: str) -> str:
    return _safe_text(label)


def _issue_from_registry_issue(issue: RegistryValidationIssue) -> ConnectorProvisioningIssue:
    return ConnectorProvisioningIssue(
        code=issue.code,
        key=issue.key,
        message=redact_text(issue.message) or issue.message,
        severity=issue.severity,  # type: ignore[arg-type]
    )


def _unknown_connector_spec(request: ConnectorProvisioningRequest) -> ConnectorProvisioningConnector:
    return ConnectorProvisioningConnector(
        connector_id=_safe_text(request.connector_id),
        connector_type=_safe_text(request.connector_type),
        label=_safe_label(request.label),
        capabilities=(),
        public_params=redact_secrets(request.params),
        secret_refs=_redact_secret_refs(request.secret_refs),
        required_config_fields=(),
        optional_config_fields=(),
        required_secret_refs=(),
        required_secret_scopes={},
        health_policy={},
        rate_limit_policy={},
        lifecycle={},
    )


def _connector_manifest(
    request: ConnectorProvisioningRequest,
    spec: ConnectorSpec,
) -> ConnectorProvisioningConnector:
    return ConnectorProvisioningConnector(
        connector_id=_safe_text(request.connector_id),
        connector_type=_safe_text(request.connector_type),
        label=_safe_label(request.label),
        capabilities=tuple(spec.capabilities),
        public_params=redact_secrets(request.params),
        secret_refs=_redact_secret_refs(request.secret_refs),
        required_config_fields=tuple(spec.required_config_fields),
        optional_config_fields=tuple(spec.optional_config_fields),
        required_secret_refs=tuple(secret.name for secret in spec.required_secret_refs),
        required_secret_scopes={
            secret.name: tuple(secret.scopes)
            for secret in spec.required_secret_refs
            if secret.scopes
        },
        health_policy=spec.health_policy_metadata(),
        rate_limit_policy=spec.rate_limit_policy_metadata(),
        lifecycle=spec.lifecycle_metadata(),
    )


def _secret_param_issues(params: Mapping[str, Any]) -> list[ConnectorProvisioningIssue]:
    return [
        ConnectorProvisioningIssue(
            code="secret_param_not_allowed",
            key=key,
            message=f"connector provisioning params must not include secret-shaped key {key}; use secret_refs",
        )
        for key in sorted(params)
        if is_secret_key(key)
    ]


def _invalid_secret_ref_issues(secret_refs: Mapping[str, str]) -> list[ConnectorProvisioningIssue]:
    return [
        ConnectorProvisioningIssue(
            code="invalid_secret_ref",
            key=key,
            message=f"connector provisioning secret_refs.{key} must be an opaque secret:// reference",
        )
        for key, value in sorted(secret_refs.items())
        if not isinstance(value, str) or not value.startswith("secret://")
    ]


def compile_connector_provisioning_plan(
    request: ConnectorProvisioningRequest,
    *,
    registry: ConnectorRegistry | None = None,
) -> ConnectorProvisioningPlan:
    """Validate a provisioning request against the connector registry.

    The function has no side effects: it does not persist config, resolve secrets,
    call adapters, or create ledger rows. It only emits a redacted plan that makes
    the next action explicit for control-plane/operator callers.
    """

    connector_registry = registry or default_connector_registry()
    audit_event = {
        "operation": "connector.provision.validate",
        "business_id": _safe_text(request.business_id),
        "connector_id": _safe_text(request.connector_id),
        "connector_type": _safe_text(request.connector_type),
        "actor_id": _safe_actor_id(request.actor_id),
    }

    try:
        spec = connector_registry.get(request.connector_type)
    except UnknownConnectorError:
        issue = ConnectorProvisioningIssue(
            code="unknown_connector_type",
            key="connector_type",
            message=redact_text(f"unknown connector type {request.connector_type}")
            or "unknown connector type [REDACTED]",
        )
        return ConnectorProvisioningPlan(
            ok=False,
            next_step="fix_validation_issues",
            business_id=_safe_text(request.business_id),
            connector=_unknown_connector_spec(request),
            issues=(issue,),
            audit_event=audit_event,
        )

    issues: list[ConnectorProvisioningIssue] = []
    issues.extend(_secret_param_issues(request.params))
    issues.extend(_invalid_secret_ref_issues(request.secret_refs))
    issues.extend(
        _issue_from_registry_issue(issue)
        for issue in connector_registry.validate_control_plane_config(
            request.connector_type,
            params=request.params,
            secret_refs=request.secret_refs,
            strict=request.strict,
        )
    )

    ok = not issues
    return ConnectorProvisioningPlan(
        ok=ok,
        next_step="ready_for_config_save" if ok else "fix_validation_issues",
        business_id=_safe_text(request.business_id),
        connector=_connector_manifest(request, spec),
        issues=tuple(issues),
        audit_event=audit_event,
    )
