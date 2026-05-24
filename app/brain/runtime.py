"""Compiled runtime artifacts for Orvo Brain business execution.

This module is intentionally additive: it compiles the existing Pydantic config
models into an execution-ready shape without changing current pipeline, preview,
forced-run, scheduler, or dispatch behavior.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field

from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule
from app.brain.models import InsightThresholds


class RuntimeCompileError(ValueError):
    """Raised when a business config cannot be compiled into a runtime."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("Invalid business runtime: " + "; ".join(self.errors))


class ConnectorRuntimeDescriptor(BaseModel):
    """Static runtime contract for a connector type."""

    model_config = ConfigDict(frozen=True)

    connector_type: str
    required_params: list[str] = Field(default_factory=list)
    secret_param_names: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class CompiledConnectorRuntime(BaseModel):
    """Execution-ready connector config with its runtime contract attached."""

    model_config = ConfigDict(frozen=True)

    connector_id: str
    connector_type: str
    label: str
    params: dict[str, Any] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)
    secret_param_names: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


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
    """Minimal execution plan that current daily report paths can consume later."""

    model_config = ConfigDict(frozen=True)

    daily_connector_types: list[str] = Field(default_factory=list)
    report_types: list[str] = Field(default_factory=list)


class CompiledBusinessRuntime(BaseModel):
    """Execution-ready runtime artifact for one business.

    This is the first stable slice of the future control-plane runtime. It keeps
    original connector params intact for current adapters, while also attaching
    connector contracts so preview, forced, and scheduled paths can converge on
    one compiled artifact over time.
    """

    model_config = ConfigDict(frozen=True)

    business_id: str
    business_name: str
    timezone: str
    currency: str
    connectors: list[CompiledConnectorRuntime] = Field(default_factory=list)
    report_schedules: list[CompiledReportSchedule] = Field(default_factory=list)
    report_settings: CompiledReportSettings
    delivery: CompiledDeliverySettings
    execution_plan: CompiledExecutionPlan


_CONNECTOR_DESCRIPTORS: dict[str, ConnectorRuntimeDescriptor] = {
    "csv": ConnectorRuntimeDescriptor(
        connector_type="csv",
        required_params=["csv_path"],
        capabilities=["daily_report"],
    ),
    "google_sheets": ConnectorRuntimeDescriptor(
        connector_type="google_sheets",
        required_params=["spreadsheet_id", "range_name"],
        capabilities=["daily_report"],
    ),
    "mercadolibre": ConnectorRuntimeDescriptor(
        connector_type="mercadolibre",
        required_params=["seller_id", "access_token"],
        secret_param_names=["access_token"],
        capabilities=["daily_report"],
    ),
    "meta_ads": ConnectorRuntimeDescriptor(
        connector_type="meta_ads",
        required_params=["ad_account_id", "access_token"],
        secret_param_names=["access_token"],
        capabilities=["daily_report"],
    ),
    "tiendanube": ConnectorRuntimeDescriptor(
        connector_type="tiendanube",
        required_params=["store_id", "access_token"],
        secret_param_names=["access_token"],
        capabilities=["daily_report"],
    ),
}


def supported_runtime_connector_types() -> list[str]:
    """Return connector types this runtime compiler currently understands."""

    return list(_CONNECTOR_DESCRIPTORS.keys())


def compile_business_runtime(
    business: BusinessConfig,
    *,
    schedules: Sequence[ReportSchedule] | None = None,
) -> CompiledBusinessRuntime:
    """Compile a BusinessConfig into an execution-ready runtime artifact.

    The function is pure: it performs no I/O, does not mutate its inputs, and
    reports all currently-detectable validation errors in one RuntimeCompileError.
    """

    errors: list[str] = []

    try:
        ZoneInfo(business.timezone)
    except ZoneInfoNotFoundError:
        errors.append(f"business {business.business_id} timezone is invalid: {business.timezone}")

    compiled_connectors = _compile_connectors(business, errors)
    compiled_schedules = _compile_schedules(business, schedules or [], errors)

    if errors:
        raise RuntimeCompileError(errors)

    daily_connector_types = _unique_in_order(
        connector.connector_type
        for connector in compiled_connectors
        if "daily_report" in connector.capabilities
    )
    report_types = _unique_in_order(schedule.report_type for schedule in compiled_schedules if schedule.enabled)
    if not report_types and daily_connector_types:
        report_types = ["daily"]

    return CompiledBusinessRuntime(
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
) -> list[CompiledConnectorRuntime]:
    enabled_connectors = [connector for connector in business.connectors if connector.enabled]
    if not enabled_connectors:
        errors.append(f"business {business.business_id} has no enabled connectors")
        return []

    compiled: list[CompiledConnectorRuntime] = []
    for connector in enabled_connectors:
        descriptor = _CONNECTOR_DESCRIPTORS.get(connector.connector_type)
        if descriptor is None:
            errors.append(
                f"connector {connector.connector_id} has unsupported connector_type: {connector.connector_type}"
            )
            continue

        missing = _missing_required_params(connector, descriptor.required_params)
        if missing:
            errors.append(
                f"connector {connector.connector_id} ({connector.connector_type}) missing required params: "
                + ", ".join(missing)
            )
            continue

        compiled.append(
            CompiledConnectorRuntime(
                connector_id=connector.connector_id,
                connector_type=connector.connector_type,
                label=connector.label,
                params=dict(connector.params),
                required_params=list(descriptor.required_params),
                secret_param_names=list(descriptor.secret_param_names),
                capabilities=list(descriptor.capabilities),
            )
        )
    return compiled


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
