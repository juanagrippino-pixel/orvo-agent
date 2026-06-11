from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.connector_registry import (
    ConnectorRegistry,
    ConnectorSpec,
    ConnectorValidationIssue,
    default_connector_registry,
)
from app.brain.run_ledger import ConnectorRunOutcome, RunLedger
from app.brain.security.redaction import redact_text


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validation_issue_projection(issue: ConnectorValidationIssue) -> dict[str, str]:
    return {
        "code": issue.code,
        "key": issue.key,
        "message": redact_text(issue.message) or "[REDACTED]",
        "severity": issue.severity,
    }


def _auth_requirements_projection(spec: ConnectorSpec, connector: ConnectorConfig) -> list[dict[str, Any]]:
    return [
        {
            "name": requirement.name,
            "provider": requirement.provider,
            "present": bool(str(connector.secret_refs.get(requirement.name, "")).strip()),
            "scopes": list(requirement.scopes),
        }
        for requirement in spec.required_secret_refs
    ]


def _last_connector_outcomes(ledger: RunLedger, business_id: str) -> dict[str, tuple[str, ConnectorRunOutcome]]:
    """Return most recent connector outcomes by connector id and type.

    The run ledger is append-only and ``list_runs`` returns newest runs first.
    Keeping only the first outcome per connector id/type gives a bounded,
    deterministic last-health projection without executing live health probes.
    """

    latest: dict[str, tuple[str, ConnectorRunOutcome]] = {}
    for run in ledger.list_runs(business_id=business_id, limit=100):
        for outcome in reversed(run.connector_outcomes):
            latest.setdefault(f"id:{outcome.connector_id}", (run.run_id, outcome))
            latest.setdefault(f"type:{outcome.connector_type}", (run.run_id, outcome))
    return latest


def _last_health_projection(latest: tuple[str, ConnectorRunOutcome] | None) -> dict[str, Any] | None:
    if latest is None:
        return None
    run_id, outcome = latest
    return {
        "run_id": run_id,
        "status": outcome.status,
        "health_state": outcome.health_state,
        "started_at": _iso(outcome.started_at),
        "finished_at": _iso(outcome.finished_at),
        "error_summary": redact_text(outcome.error_summary) if outcome.error_summary else None,
    }


def _readiness_state(
    *,
    connector: ConnectorConfig,
    registered: bool,
    validation_issues: list[ConnectorValidationIssue],
    last_health: dict[str, Any] | None,
) -> str:
    if not connector.enabled:
        return "disabled"
    if not registered:
        return "unknown"
    if any(issue.severity == "error" for issue in validation_issues):
        return "not_ready"
    if last_health is not None and last_health.get("health_state") not in (None, "ok"):
        return "degraded"
    return "ready"


def _connector_projection(
    connector: ConnectorConfig,
    *,
    registry: ConnectorRegistry,
    latest_outcomes: dict[str, tuple[str, ConnectorRunOutcome]],
) -> dict[str, Any]:
    spec: ConnectorSpec | None = registry.get(connector.connector_type) if registry.has(connector.connector_type) else None
    validation_issues: list[ConnectorValidationIssue]
    if spec is None:
        validation_issues = [
            ConnectorValidationIssue(
                code="unknown_connector_type",
                key="connector_type",
                message=f"Unknown connector type: {connector.connector_type}",
            )
        ]
        auth_requirements: list[dict[str, Any]] = []
        health_policy: dict[str, Any] | None = None
        rate_limit_policy: dict[str, Any] | None = None
        lifecycle: dict[str, Any] | None = None
        capabilities: list[str] = []
        emitted_metric_families: list[str] = []
        emitted_event_families: list[str] = []
    else:
        validation_issues = spec.validate_control_plane_config(
            params=connector.params,
            secret_refs=connector.secret_refs,
            strict=True,
        )
        auth_requirements = _auth_requirements_projection(spec, connector)
        health_policy = spec.health_policy_metadata()
        rate_limit_policy = spec.rate_limit_policy_metadata()
        lifecycle = spec.lifecycle_metadata()
        capabilities = list(spec.capabilities)
        emitted_metric_families = list(spec.emitted_metric_families)
        emitted_event_families = list(spec.emitted_event_families)

    latest = latest_outcomes.get(f"id:{connector.connector_id}") or latest_outcomes.get(
        f"type:{connector.connector_type}"
    )
    last_health = _last_health_projection(latest)
    readiness_state = _readiness_state(
        connector=connector,
        registered=spec is not None,
        validation_issues=validation_issues,
        last_health=last_health,
    )
    errors = [issue for issue in validation_issues if issue.severity == "error"]
    warnings = [issue for issue in validation_issues if issue.severity != "error"]

    return {
        "connector_id": connector.connector_id,
        "connector_type": connector.connector_type,
        "label": redact_text(connector.label) or "[REDACTED]",
        "enabled": connector.enabled,
        "registered": spec is not None,
        "readiness_state": readiness_state,
        "capabilities": capabilities,
        "emitted_metric_families": emitted_metric_families,
        "emitted_event_families": emitted_event_families,
        "required_config_fields": list(spec.required_config_fields) if spec is not None else [],
        "optional_config_fields": list(spec.optional_config_fields) if spec is not None else [],
        "auth_requirements": auth_requirements,
        "validation": {
            "error_count": len(errors),
            "warning_count": len(warnings),
            "issues": [_validation_issue_projection(issue) for issue in validation_issues],
        },
        "health_policy": health_policy,
        "rate_limit_policy": rate_limit_policy,
        "lifecycle": lifecycle,
        "last_health": last_health,
    }


def connector_readiness_projection(
    business: BusinessConfig,
    ledger: RunLedger,
    *,
    registry: ConnectorRegistry | None = None,
) -> dict[str, Any]:
    """Project connector readiness without executing connectors.

    This is an operator-surface projection over durable business config,
    registry policy, and run-ledger outcomes. It intentionally does not resolve
    raw secrets or perform live health checks; current health policy is
    registry-declared metadata plus the latest recorded connector outcome.
    """

    effective_registry = registry or default_connector_registry()
    latest_outcomes = _last_connector_outcomes(ledger, business.business_id)
    connectors = [
        _connector_projection(connector, registry=effective_registry, latest_outcomes=latest_outcomes)
        for connector in business.connectors
    ]
    states = [connector["readiness_state"] for connector in connectors]
    return {
        "business_id": business.business_id,
        "readiness_check": "metadata_and_last_run",
        "summary": {
            "total": len(connectors),
            "ready": states.count("ready"),
            "degraded": states.count("degraded"),
            "not_ready": states.count("not_ready"),
            "disabled": states.count("disabled"),
            "unknown": states.count("unknown"),
        },
        "connectors": connectors,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
