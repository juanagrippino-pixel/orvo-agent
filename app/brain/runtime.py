"""Compiled runtime artifacts for Orvo Brain business execution.

This module compiles durable business configuration into an execution-ready,
audit-safe control-plane artifact. The compiled artifact is intentionally safe
to serialize into run metadata: raw legacy secrets are stripped and represented
as secret references.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field

from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule
from app.brain.connector_registry import (
    CAPABILITY_DAILY_REPORT,
    ConnectorSpec,
    default_connector_registry,
)
from app.brain.models import InsightThresholds
from app.brain.security.redaction import is_secret_key, redact_secrets

RuntimeMode = Literal["preview", "forced", "scheduled", "operator_triggered"]


class RuntimeCompileError(ValueError):
    """Raised when a business config cannot be compiled into a runtime."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("Invalid business runtime: " + "; ".join(self.errors))


class CompiledConnectorRuntime(BaseModel):
    """Execution-ready connector config with its registry contract attached."""

    model_config = ConfigDict(frozen=True)

    connector_id: str
    connector_type: str
    label: str
    params: dict[str, Any] = Field(default_factory=dict)
    secret_refs: dict[str, str] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)
    secret_param_names: list[str] = Field(default_factory=list)
    legacy_secret_param_names: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    emitted_metric_families: list[str] = Field(default_factory=list)
    supported_runtime_modes: list[str] = Field(default_factory=list)
    executor_factory_path: str
    health_policy: dict[str, Any] = Field(default_factory=dict)
    required_scopes: list[str] = Field(default_factory=list)
    rate_limit_policy: dict[str, Any] = Field(default_factory=dict)
    lifecycle: dict[str, str] = Field(default_factory=dict)


class CompiledReportSchedule(BaseModel):
    """Schedule normalized with the business timezone used to evaluate it."""

    model_config = ConfigDict(frozen=True)

    schedule_id: str
    business_id: str
    cron_expression: str
    report_type: str
    enabled: bool
    timezone: str


class CompiledDeliverySettings(BaseModel):
    """Delivery settings required by report dispatch paths."""

    model_config = ConfigDict(frozen=True)

    owner_phone: str


class CompiledReportSettings(BaseModel):
    """Report-generation settings compiled from business config."""

    model_config = ConfigDict(frozen=True)

    insight_thresholds: InsightThresholds


class CompiledExecutionPlan(BaseModel):
    """Minimal execution plan that current daily report paths can consume."""

    model_config = ConfigDict(frozen=True)

    daily_connector_types: list[str] = Field(default_factory=list)
    report_types: list[str] = Field(default_factory=list)


class CompiledBusinessRuntime(BaseModel):
    """Execution-ready runtime artifact for one business.

    Raw connector secrets are never embedded in this model. Current adapters can
    still receive resolved raw secrets from legacy ``BusinessConfig`` at the
    execution boundary, but the compiled control-plane artifact stores only
    public params and deterministic secret refs.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    compiled_from_hash: str
    run_mode: RuntimeMode
    business_id: str
    business_name: str
    timezone: str
    currency: str
    connectors: list[CompiledConnectorRuntime] = Field(default_factory=list)
    report_schedules: list[CompiledReportSchedule] = Field(default_factory=list)
    report_settings: CompiledReportSettings
    delivery: CompiledDeliverySettings
    execution_plan: CompiledExecutionPlan


def supported_runtime_connector_types() -> list[str]:
    """Return connector types this runtime compiler currently understands."""

    return list(default_connector_registry().connector_types())


def runtime_run_metadata(runtime: CompiledBusinessRuntime) -> dict[str, Any]:
    """Return run-ledger-compatible metadata for a compiled runtime.

    Connector refs intentionally expose registry/executor contract metadata and
    secret reference labels, but not raw public params or legacy secret values.
    Runtime metadata may be persisted in ledgers and worker summaries, so this
    function stays on the compiled artifact side of the secret boundary.
    """

    return {
        "runtime_id": runtime.runtime_id,
        "compiled_from_hash": runtime.compiled_from_hash,
        "config_digest": runtime.compiled_from_hash,
        "config_ref": runtime.runtime_id,
        "run_mode": runtime.run_mode,
        "connector_types": list(runtime.execution_plan.daily_connector_types),
        "connector_refs": [_connector_run_metadata(connector) for connector in runtime.connectors],
        "report_types": list(runtime.execution_plan.report_types),
    }


def _connector_run_metadata(connector: CompiledConnectorRuntime) -> dict[str, Any]:
    """Return a safe registry-contract summary for run metadata."""

    return {
        "connector_id": connector.connector_id,
        "connector_type": connector.connector_type,
        "label": connector.label,
        "secret_refs": dict(connector.secret_refs),
        "required_params": list(connector.required_params),
        "secret_param_names": list(connector.secret_param_names),
        "legacy_secret_param_names": list(connector.legacy_secret_param_names),
        "capabilities": list(connector.capabilities),
        "emitted_metric_families": list(connector.emitted_metric_families),
        "supported_runtime_modes": list(connector.supported_runtime_modes),
        "executor_factory_path": connector.executor_factory_path,
        "health_policy": dict(connector.health_policy),
        "required_scopes": list(connector.required_scopes),
        "rate_limit_policy": dict(connector.rate_limit_policy),
    }


def compile_business_runtime(
    business: BusinessConfig,
    *,
    schedules: Sequence[ReportSchedule] | None = None,
    run_mode: RuntimeMode = "scheduled",
) -> CompiledBusinessRuntime:
    """Compile a BusinessConfig into an execution-ready runtime artifact.

    The function is pure: it performs no I/O, does not mutate inputs, uses the
    connector registry as its source of truth, and reports all detectable
    validation errors in one RuntimeCompileError.
    """

    errors: list[str] = []

    try:
        ZoneInfo(business.timezone)
    except ZoneInfoNotFoundError:
        errors.append(f"business {business.business_id} timezone is invalid: {business.timezone}")

    compiled_connectors = _compile_connectors(business, errors, run_mode=run_mode)
    compiled_schedules = _compile_schedules(business, schedules or [], errors)

    if errors:
        raise RuntimeCompileError(errors)

    daily_connector_types = _unique_in_order(
        connector.connector_type
        for connector in compiled_connectors
        if CAPABILITY_DAILY_REPORT in connector.capabilities
    )
    report_types = _unique_in_order(schedule.report_type for schedule in compiled_schedules if schedule.enabled)
    if not report_types and daily_connector_types:
        report_types = ["daily"]

    hash_payload = _runtime_hash_payload(
        business=business,
        connectors=compiled_connectors,
        schedules=compiled_schedules,
        report_types=report_types,
        daily_connector_types=daily_connector_types,
        run_mode=run_mode,
    )
    compiled_from_hash = _sha256_digest(hash_payload)

    return CompiledBusinessRuntime(
        runtime_id=f"runtime:{business.business_id}:{compiled_from_hash.removeprefix('sha256:')[:16]}",
        compiled_from_hash=compiled_from_hash,
        run_mode=run_mode,
        business_id=business.business_id,
        business_name=business.business_name,
        timezone=business.timezone,
        currency=business.currency,
        connectors=compiled_connectors,
        report_schedules=compiled_schedules,
        report_settings=CompiledReportSettings(
            insight_thresholds=business.insight_thresholds.model_copy(deep=True)
        ),
        delivery=CompiledDeliverySettings(owner_phone=business.owner_phone),
        execution_plan=CompiledExecutionPlan(
            daily_connector_types=daily_connector_types,
            report_types=report_types,
        ),
    )


def _compile_connectors(
    business: BusinessConfig,
    errors: list[str],
    *,
    run_mode: RuntimeMode,
) -> list[CompiledConnectorRuntime]:
    enabled_connectors = [connector for connector in business.connectors if connector.enabled]
    if not enabled_connectors:
        errors.append(f"business {business.business_id} has no enabled connectors")
        return []

    registry = default_connector_registry()
    compiled: list[CompiledConnectorRuntime] = []
    for connector in enabled_connectors:
        try:
            spec = registry.get(connector.connector_type)
        except ValueError:
            errors.append(
                f"connector {connector.connector_id} has unsupported connector_type: {connector.connector_type}"
            )
            continue

        assert spec.executor is not None  # populated by ConnectorSpec.__post_init__
        supported_runtime_modes = list(spec.executor.supported_runtime_modes)
        if run_mode not in spec.executor.supported_runtime_modes:
            errors.append(
                f"connector {connector.connector_id} ({connector.connector_type}) does not support "
                f"runtime mode {run_mode}; supported modes: {', '.join(supported_runtime_modes)}"
            )
            continue

        missing_public = _missing_required_params(connector, spec.required_config_fields)
        missing_secret_refs = _missing_required_secret_refs(connector, spec)
        missing = missing_public + missing_secret_refs
        if missing:
            errors.append(
                f"connector {connector.connector_id} ({connector.connector_type}) missing required params: "
                + ", ".join(missing)
            )
            continue

        secret_names = [secret.name for secret in spec.required_secret_refs]
        legacy_secret_names = list(spec.legacy_secret_config_fields)
        public_params = _public_params(connector.params, legacy_secret_names)
        secret_refs = _secret_refs_for(business.business_id, connector, spec)
        compiled.append(
            CompiledConnectorRuntime(
                connector_id=connector.connector_id,
                connector_type=connector.connector_type,
                label=connector.label,
                params=public_params,
                secret_refs=secret_refs,
                required_params=list(spec.required_config_fields),
                secret_param_names=secret_names,
                legacy_secret_param_names=legacy_secret_names,
                capabilities=list(spec.capabilities),
                emitted_metric_families=list(spec.emitted_metric_families),
                supported_runtime_modes=supported_runtime_modes,
                executor_factory_path=spec.factory_path,
                health_policy=_health_policy_for(spec),
                required_scopes=list(spec.scopes.required),
                rate_limit_policy=_rate_limit_policy_for(spec),
                lifecycle=_lifecycle_metadata_for(spec),
            )
        )
    return compiled


def _health_policy_for(spec: ConnectorSpec) -> dict[str, Any]:
    return {
        "readiness_check": spec.health.readiness_check,
        "supports_health_check": spec.health.supports_health_check,
        "degraded_state": spec.health.degraded_state,
    }


def _rate_limit_policy_for(spec: ConnectorSpec) -> dict[str, Any]:
    return {
        "default_timeout_seconds": spec.rate_limit.default_timeout_seconds,
        "requests_per_minute": spec.rate_limit.requests_per_minute,
        "retry_policy": spec.rate_limit.retry_policy,
    }


def _lifecycle_metadata_for(spec: ConnectorSpec) -> dict[str, str]:
    return {
        "status": spec.lifecycle.status,
        "owner": spec.lifecycle.owner,
        "version": spec.lifecycle.version,
    }


def _compile_schedules(
    business: BusinessConfig,
    schedules: Sequence[ReportSchedule],
    errors: list[str],
) -> list[CompiledReportSchedule]:
    compiled: list[CompiledReportSchedule] = []
    for schedule in schedules:
        if schedule.business_id != business.business_id:
            errors.append(
                f"schedule {schedule.schedule_id} belongs to {schedule.business_id}, expected {business.business_id}"
            )
            continue

        cron_error = _daily_cron_error(schedule.cron_expression)
        if cron_error is not None:
            errors.append(f"schedule {schedule.schedule_id} has invalid cron_expression: {cron_error}")
            continue

        compiled.append(
            CompiledReportSchedule(
                schedule_id=schedule.schedule_id,
                business_id=schedule.business_id,
                cron_expression=schedule.cron_expression,
                report_type=schedule.report_type,
                enabled=schedule.enabled,
                timezone=business.timezone,
            )
        )
    return compiled


def _missing_required_params(connector: ConnectorConfig, required_params: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for param_name in required_params:
        value = connector.params.get(param_name)
        if value is None or value == "":
            missing.append(param_name)
    return missing


def _missing_required_secret_refs(connector: ConnectorConfig, spec: ConnectorSpec) -> list[str]:
    missing: list[str] = []
    for secret in spec.required_secret_refs:
        legacy_field = secret.legacy_config_field or secret.name
        # Until the config model grows explicit secret_refs, legacy inline config
        # proves the execution path has a resolvable secret. The compiled runtime
        # still strips the raw value and emits only a deterministic secret ref.
        value = connector.params.get(legacy_field)
        if value is None or value == "":
            missing.append(secret.name)
    return missing


def _public_params(params: dict, legacy_secret_names: Sequence[str]) -> dict[str, Any]:
    secret_names = set(legacy_secret_names)
    return {
        str(key): redact_secrets(value)
        for key, value in params.items()
        if key not in secret_names and not is_secret_key(str(key))
    }


def _secret_refs_for(business_id: str, connector: ConnectorConfig, spec: ConnectorSpec) -> dict[str, str]:
    refs: dict[str, str] = {}
    for secret in spec.required_secret_refs:
        refs[secret.name] = f"secret://businesses/{business_id}/connectors/{connector.connector_id}/{secret.name}"
    return refs


def _runtime_hash_payload(
    *,
    business: BusinessConfig,
    connectors: Sequence[CompiledConnectorRuntime],
    schedules: Sequence[CompiledReportSchedule],
    report_types: Sequence[str],
    daily_connector_types: Sequence[str],
    run_mode: RuntimeMode,
) -> dict[str, Any]:
    return {
        "run_mode": run_mode,
        "business": {
            "business_id": business.business_id,
            "business_name": business.business_name,
            "timezone": business.timezone,
            "currency": business.currency,
            "owner_phone": business.owner_phone,
            "insight_thresholds": business.insight_thresholds.model_dump(mode="json"),
        },
        "connectors": [connector.model_dump(mode="json") for connector in connectors],
        "schedules": [schedule.model_dump(mode="json") for schedule in schedules],
        "execution_plan": {
            "daily_connector_types": list(daily_connector_types),
            "report_types": list(report_types),
        },
    }


def _sha256_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _daily_cron_error(cron_expression: str) -> str | None:
    parts = cron_expression.split()
    if len(parts) != 5:
        return f"expected 5 fields, got {len(parts)}"
    minute_raw, hour_raw = parts[0], parts[1]
    try:
        minute = int(minute_raw)
        hour = int(hour_raw)
    except ValueError:
        return "minute and hour must be integers"
    if minute < 0 or minute > 59:
        return f"minute out of range: {minute}"
    if hour < 0 or hour > 23:
        return f"hour out of range: {hour}"
    return None


def _unique_in_order(values) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        unique.append(value)
        seen.add(value)
    return unique
