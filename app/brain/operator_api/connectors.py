from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.connector_registry import (
    ConnectorRegistry,
    ConnectorSpec,
    ConnectorValidationIssue,
    connector_contract_metadata,
    default_connector_registry,
)
from app.brain.run_ledger import ConnectorRunOutcome, RunLedger
from app.brain.security.redaction import redact_text


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_identifier(value: str) -> str:
    """Return an operator-safe connector identifier.

    Connector ids/types are operational labels, but a pasted credential in these
    fields should not be partially echoed as an addressable-looking identifier.
    Collapse the whole value whenever inline secret redaction would change it.
    """

    redacted = redact_text(value) or "[REDACTED]"
    return redacted if redacted == value else "[REDACTED]"


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


def _certification_summary_projection(metadata: dict[str, Any]) -> dict[str, Any] | None:
    def _summary(key: str) -> dict[str, Any] | None:
        raw = metadata.get(key)
        if not isinstance(raw, dict):
            return None
        status = raw.get("status")
        issue_count = raw.get("issue_count")
        summary: dict[str, Any] = {}
        if isinstance(status, str) and status:
            summary["status"] = status
        if isinstance(issue_count, int):
            summary["issue_count"] = issue_count
        return summary or None

    events = _summary("event_certification")
    metrics = _summary("metric_certification")
    if events is None and metrics is None:
        return None
    return {
        "events": events,
        "metrics": metrics,
    }


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
        "duration_ms": outcome.duration_ms,
        "error_summary": redact_text(outcome.error_summary) if outcome.error_summary else None,
        "certification": _certification_summary_projection(outcome.metadata),
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


_HEALTH_SETUP_REASONS = {
    "degraded": "connector_last_run_degraded",
    "stale": "connector_last_run_stale",
    "unauthorized": "connector_last_run_unauthorized",
    "rate_limited": "connector_last_run_rate_limited",
    "failed": "connector_last_run_failed",
}

_SETUP_NEXT_STEPS = {
    "unknown_connector_type": "register_or_disable_connector",
    "missing_required_secret_ref": "review_connector_configuration",
    "legacy_inline_secret": "review_connector_configuration",
    "connector_last_run_unauthorized": "refresh_connector_credentials",
    "connector_last_run_rate_limited": "wait_or_review_connector_limits",
    "connector_last_run_stale": "review_last_connector_run",
    "connector_last_run_degraded": "review_last_connector_run",
    "connector_last_run_failed": "review_last_connector_run",
}


def _setup_projection(
    *,
    connector: ConnectorConfig,
    registered: bool,
    validation_issues: list[ConnectorValidationIssue],
    last_health: dict[str, Any] | None,
    readiness_state: str,
) -> dict[str, Any]:
    """Return stable setup-task hints for the connector readiness surface.

    The readiness endpoint remains an inspection surface: it does not execute
    health checks or mutate configuration. These hints make already-known config
    and last-run failures visible as setup-required tasks in the operator app.
    Non-blocking migration warnings (for example legacy inline secrets that now
    have a valid ``secret_ref``) stay ``ready`` but still surface as setup work
    so operators can finish the control-plane cleanup deterministically.
    """

    if not connector.enabled:
        return {"setup_required": False, "setup_reason": None, "operator_next_step": None}

    errors = [issue for issue in validation_issues if issue.severity == "error"]
    warnings = [issue for issue in validation_issues if issue.severity != "error"]
    if readiness_state == "ready" and not warnings:
        return {"setup_required": False, "setup_reason": None, "operator_next_step": None}

    setup_reason: str | None = None
    if not registered:
        setup_reason = "unknown_connector_type"
    elif errors:
        setup_reason = errors[0].code
    elif warnings:
        setup_reason = warnings[0].code
    elif last_health is not None:
        setup_reason = _HEALTH_SETUP_REASONS.get(str(last_health.get("health_state") or ""))

    if setup_reason is None:
        setup_reason = "review_connector_configuration"

    return {
        "setup_required": True,
        "setup_reason": setup_reason,
        "operator_next_step": _SETUP_NEXT_STEPS.get(setup_reason, "review_connector_configuration"),
    }


def _connector_projection(
    connector: ConnectorConfig,
    *,
    registry: ConnectorRegistry,
    latest_outcomes: dict[str, tuple[str, ConnectorRunOutcome]],
    connector_type_counts: dict[str, int],
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
        required_scopes: list[str] = []
        emitted_metric_families: list[str] = []
        emitted_event_families: list[str] = []
        supported_runtime_modes: list[str] = []
        executor_factory_path: str | None = None
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
        required_scopes = list(spec.scopes.required)
        emitted_metric_families = list(spec.emitted_metric_families)
        emitted_event_families = list(spec.emitted_event_families)
        assert spec.executor is not None
        supported_runtime_modes = list(spec.executor.supported_runtime_modes)
        executor_factory_path = spec.factory_path

    latest = latest_outcomes.get(f"id:{connector.connector_id}")
    if latest is None and connector_type_counts.get(connector.connector_type, 0) == 1:
        latest = latest_outcomes.get(f"type:{connector.connector_type}")
    last_health = _last_health_projection(latest)
    readiness_state = _readiness_state(
        connector=connector,
        registered=spec is not None,
        validation_issues=validation_issues,
        last_health=last_health,
    )
    setup = _setup_projection(
        connector=connector,
        registered=spec is not None,
        validation_issues=validation_issues,
        last_health=last_health,
        readiness_state=readiness_state,
    )
    errors = [issue for issue in validation_issues if issue.severity == "error"]
    warnings = [issue for issue in validation_issues if issue.severity != "error"]

    return {
        "connector_id": _safe_identifier(connector.connector_id),
        "connector_type": _safe_identifier(connector.connector_type),
        "label": redact_text(connector.label) or "[REDACTED]",
        "enabled": connector.enabled,
        "registered": spec is not None,
        "readiness_state": readiness_state,
        **setup,
        "capabilities": capabilities,
        "required_scopes": required_scopes,
        "supported_runtime_modes": supported_runtime_modes,
        "executor_factory_path": executor_factory_path,
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
    connector_type_counts: dict[str, int] = {}
    for connector in business.connectors:
        connector_type_counts[connector.connector_type] = (
            connector_type_counts.get(connector.connector_type, 0) + 1
        )
    connectors = [
        _connector_projection(
            connector,
            registry=effective_registry,
            latest_outcomes=latest_outcomes,
            connector_type_counts=connector_type_counts,
        )
        for connector in business.connectors
    ]
    states = [connector["readiness_state"] for connector in connectors]
    setup_required_count = sum(1 for connector in connectors if connector["setup_required"])
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
            "setup_required": setup_required_count,
        },
        "connectors": connectors,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
