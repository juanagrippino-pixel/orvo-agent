"""Connector registry for Orvo Brain runtime/control-plane validation.

This module describes the connector adapters that already exist in
``app.brain.adapters`` and exposes allowlisted executor metadata so runtime
orchestration can invoke daily-report factories through the registry rather than
hardcoding every connector branch. Runtime compilation can depend on these specs
to check connector availability, capabilities, secret-reference requirements,
config shape, and adapter kwargs before a run.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlsplit

from app.brain.connector_health import CONNECTOR_HEALTH_STATES, ConnectorHealthState
from app.brain.security.redaction import is_secret_key
from app.brain.semantics.metric_registry import (
    MetricRegistry,
    MetricValidationIssue,
    find_duplicate_canonical_violations,
    find_evidence_required_violations,
    find_evidence_source_violations,
    find_family_envelope_violations,
    find_money_currency_violations,
    find_negative_value_violations,
    find_source_envelope_violations,
    find_value_kind_violations,
    validate_metrics,
)
from app.brain.worker_contracts import validate_daily_report_adapter

CONNECTOR_TYPE_CSV = "csv"
CONNECTOR_TYPE_GOOGLE_SHEETS = "google_sheets"
CONNECTOR_TYPE_MERCADOLIBRE = "mercadolibre"
CONNECTOR_TYPE_META_ADS = "meta_ads"
CONNECTOR_TYPE_SAMPLE = "sample"
CONNECTOR_TYPE_TIENDANUBE = "tiendanube"
CONNECTOR_TYPE_WOOCOMMERCE = "woocommerce"

CAPABILITY_DAILY_REPORT = "daily_report"
CAPABILITY_AD_METRICS = "ad_metrics"
CAPABILITY_COMMERCE_METRICS = "commerce_metrics"
CAPABILITY_FILE_IMPORT = "file_import"
CAPABILITY_INVENTORY_METRICS = "inventory_metrics"
CAPABILITY_MANUAL_PAYLOAD = "manual_payload"
CAPABILITY_SHEET_IMPORT = "sheet_import"

RUNTIME_MODE_PREVIEW = "preview"
RUNTIME_MODE_MANUAL = "manual"
RUNTIME_MODE_FORCED = "forced"
RUNTIME_MODE_SCHEDULED = "scheduled"
RUNTIME_MODE_OPERATOR_TRIGGERED = "operator_triggered"
RUNTIME_MODE_HEALTH_CHECK = "health_check"

EVENT_FAMILY_CONNECTOR_EXECUTION = "connector.execution"
EVENT_FAMILY_CONNECTOR_HEALTH = "connector.health"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


def _metric_object_key(metric: object) -> str:
    """Extract a metric key from a Metric-shaped object or mapping."""

    if isinstance(metric, Mapping):
        key = metric.get("key")
    else:
        key = getattr(metric, "key", None)
    if not isinstance(key, str) or not key:
        raise ValueError(
            "validate_emitted_metric_objects requires metrics with a non-empty string key"
        )
    return key


def _event_type_value(event: object) -> str:
    """Extract an event type from a string, Event-shaped object, or mapping."""

    if isinstance(event, str):
        event_type = event
    elif isinstance(event, Mapping):
        event_type = event.get("event_type")
    else:
        event_type = getattr(event, "event_type", None)
    if not isinstance(event_type, str) or not event_type:
        raise ValueError(
            "validate_emitted_events requires events with a non-empty string event_type"
        )
    return event_type


def _declared_health_state_for_event(
    health_event_suffix: str,
    *,
    allowed_health_states: tuple[ConnectorHealthState, ...],
) -> ConnectorHealthState | None:
    """Resolve the canonical declared health state for a concrete health event.

    Health event types may append detail after the canonical registry state, such
    as ``connector.health.rate_limited.retry_scheduled``. Certification should
    accept those detailed events only when their leading canonical health state
    is declared for the connector.
    """

    for allowed_state in allowed_health_states:
        if health_event_suffix == allowed_state or health_event_suffix.startswith(f"{allowed_state}."):
            return allowed_state
    return None


def is_secret_ref_handle(value: object) -> bool:
    """Return True when a value is an opaque secret manager reference."""

    if not isinstance(value, str) or not value.startswith("secret://") or len(value) <= len("secret://"):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    if parts.scheme != "secret":
        return False
    if not parts.netloc and not parts.path:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    return not any(
        key.lower().replace("-", "_") == "code" or is_secret_key(key)
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    )


class UnknownConnectorError(ValueError):
    """Raised when a connector type is not registered."""


@dataclass(frozen=True, slots=True)
class SecretRequirement:
    """Control-plane metadata for a required secret reference.

    ``name`` is the config key expected in control-plane ``secret_refs``. It is a
    reference/handle, not the raw secret value. ``legacy_config_field`` documents
    the transitional inline execution parameter still required by current
    adapters until runtime compilation resolves secret refs at execution time.
    """

    name: str
    provider: str
    description: str = ""
    scopes: tuple[str, ...] = ()
    legacy_config_field: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectorValidationIssue:
    """Structured validation diagnostic for control-plane clients."""

    code: str
    key: str
    message: str
    severity: str = SEVERITY_ERROR


@dataclass(frozen=True, slots=True)
class ConnectorEventValidationIssue:
    """Deterministic advisory diagnostic for connector event certification."""

    code: str
    event_type: str
    message: str
    severity: str = SEVERITY_WARNING
    index: int | None = None


@dataclass(frozen=True, slots=True)
class ConnectorFactoryParam:
    """Declarative binding from connector/runtime context to adapter kwargs.

    ``source`` is intentionally allowlisted so registry-driven execution cannot
    smuggle arbitrary connector params into adapter calls. Secret-backed legacy
    adapter kwargs must use ``resolved_secret_param``: those values may exist
    only on the execution-scoped connector copy returned by the secret resolver,
    while durable control-plane config carries ``secret_refs``. ``fallback`` is
    used only for absent/empty optional values and must be non-secret static
    data.
    """

    argument: str
    source: str
    key: str | None = None
    required: bool = True
    fallback: Any = None


@dataclass(frozen=True, slots=True)
class ConnectorExecutorMetadata:
    """Callable metadata for registry-driven runtime execution."""

    adapter_module: str
    report_factory: str
    supported_runtime_modes: tuple[str, ...] = (
        RUNTIME_MODE_PREVIEW,
        RUNTIME_MODE_FORCED,
        RUNTIME_MODE_SCHEDULED,
        RUNTIME_MODE_OPERATOR_TRIGGERED,
    )
    factory_params: tuple[ConnectorFactoryParam, ...] = ()

    @property
    def factory_path(self) -> str:
        return f"{self.adapter_module}.{self.report_factory}"

    def load_factory(self):
        """Import and return the configured report factory callable."""

        module = import_module(self.adapter_module)
        factory = getattr(module, self.report_factory)
        return validate_daily_report_adapter(factory)

@dataclass(frozen=True, slots=True)
class ConnectorHealthMetadata:
    """Readiness/health metadata for registry-driven connector planning.

    ``allowed_states`` mirrors the connector-registry contract taxonomy so
    compiled runtime/run metadata can expose stable health semantics before a
    connector-specific health checker is implemented.
    """

    readiness_check: str = "metadata_only"
    supports_health_check: bool = False
    degraded_state: str = "degraded"
    allowed_states: tuple[ConnectorHealthState, ...] = CONNECTOR_HEALTH_STATES


@dataclass(frozen=True, slots=True)
class ConnectorRateLimitMetadata:
    """Simple rate-limit/retry defaults for connector planning."""

    default_timeout_seconds: int = 30
    requests_per_minute: int | None = None
    retry_policy: str = "adapter_default"


@dataclass(frozen=True, slots=True)
class ConnectorScopeMetadata:
    """Permission/scope metadata for least-privilege provisioning."""

    required: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ConnectorLifecycleMetadata:
    """Lifecycle metadata for self-service provisioning and migrations."""

    status: str = "active"
    owner: str = "orvo-brain"
    version: str = "phase-a"


@dataclass(frozen=True, slots=True)
class ConnectorSpec:
    """Static metadata for one existing Orvo Brain connector adapter."""

    connector_type: str
    display_name: str
    adapter_module: str
    report_factory: str
    capabilities: tuple[str, ...]
    emitted_metric_families: tuple[str, ...] = ()
    emitted_event_families: tuple[str, ...] = (
        EVENT_FAMILY_CONNECTOR_EXECUTION,
        EVENT_FAMILY_CONNECTOR_HEALTH,
    )
    required_config_fields: tuple[str, ...] = ()
    optional_config_fields: tuple[str, ...] = ()
    required_secret_refs: tuple[SecretRequirement, ...] = ()
    legacy_secret_config_fields: tuple[str, ...] = ()
    secret_config_fields: tuple[str, ...] = ()
    executor: ConnectorExecutorMetadata | None = None
    health: ConnectorHealthMetadata = ConnectorHealthMetadata()
    rate_limit: ConnectorRateLimitMetadata = ConnectorRateLimitMetadata()
    scopes: ConnectorScopeMetadata = ConnectorScopeMetadata()
    lifecycle: ConnectorLifecycleMetadata = ConnectorLifecycleMetadata()

    def __post_init__(self) -> None:
        if self.executor is None:
            object.__setattr__(
                self,
                "executor",
                ConnectorExecutorMetadata(
                    adapter_module=self.adapter_module,
                    report_factory=self.report_factory,
                ),
            )
        if not self.legacy_secret_config_fields and self.secret_config_fields:
            object.__setattr__(self, "legacy_secret_config_fields", self.secret_config_fields)
        if not self.secret_config_fields and self.legacy_secret_config_fields:
            object.__setattr__(self, "secret_config_fields", self.legacy_secret_config_fields)

    @property
    def factory_path(self) -> str:
        """Fully qualified path to the adapter report-builder callable."""

        return f"{self.adapter_module}.{self.report_factory}"

    def health_policy_metadata(self) -> dict[str, Any]:
        """Return serializable connector health policy metadata."""

        return {
            "readiness_check": self.health.readiness_check,
            "supports_health_check": self.health.supports_health_check,
            "degraded_state": self.health.degraded_state,
            "allowed_states": list(self.health.allowed_states),
        }

    def rate_limit_policy_metadata(self) -> dict[str, Any]:
        """Return serializable connector rate-limit policy metadata."""

        return {
            "default_timeout_seconds": self.rate_limit.default_timeout_seconds,
            "requests_per_minute": self.rate_limit.requests_per_minute,
            "retry_policy": self.rate_limit.retry_policy,
        }

    def lifecycle_metadata(self) -> dict[str, str]:
        """Return serializable connector lifecycle metadata."""

        return {
            "status": self.lifecycle.status,
            "owner": self.lifecycle.owner,
            "version": self.lifecycle.version,
        }

    def load_report_factory(self):
        """Import the configured report-builder callable from executor metadata."""

        assert self.executor is not None  # set in __post_init__
        return self.executor.load_factory()

    def _resolve_factory_param(
        self,
        binding: ConnectorFactoryParam,
        *,
        connector: object,
        business: object,
        report_date: object,
        service_bindings: Mapping[str, object],
    ) -> tuple[bool, object]:
        params = getattr(connector, "params", {}) or {}
        if not isinstance(params, Mapping):
            raise TypeError(f"{self.connector_type} connector params must be a mapping")

        if binding.source == "business_attr":
            return True, getattr(business, binding.key or binding.argument)
        if binding.source == "report_date":
            return True, report_date
        if binding.source == "connector_param":
            value = params.get(binding.key or binding.argument)
            if value in (None, "") and binding.fallback is not None:
                value = binding.fallback
            return value not in (None, ""), value
        if binding.source == "resolved_secret_param":
            key = binding.key or binding.argument
            if key not in set(self.legacy_secret_config_fields):
                raise ValueError(
                    f"{self.connector_type} connector resolved_secret_param {key} "
                    "is not declared in legacy_secret_config_fields"
                )
            value = params.get(key)
            return value not in (None, ""), value
        if binding.source == "connector_param_bool":
            return True, bool(params.get(binding.key or binding.argument, binding.fallback))
        if binding.source == "connector_label":
            return True, getattr(connector, "label")
        if binding.source == "connector_param_or_label":
            value = params.get(binding.key or binding.argument)
            if value in (None, ""):
                value = getattr(connector, "label")
            return True, value
        if binding.source == "service_binding":
            key = binding.key or binding.argument
            if key in service_bindings:
                return True, service_bindings[key]
            return False, None
        if binding.source == "insight_thresholds":
            return True, getattr(business, "insight_thresholds")
        if binding.source == "literal":
            return True, binding.fallback
        raise ValueError(f"Unsupported connector factory param source: {binding.source}")

    def build_report_factory_kwargs(
        self,
        *,
        connector: object,
        business: object,
        report_date: object,
        service_bindings: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Build adapter kwargs from allowlisted executor metadata.

        Required connector params are reported by key name only; values are never
        included in errors so inline legacy secrets cannot leak through pipeline
        failures.
        """

        assert self.executor is not None  # set in __post_init__
        kwargs: dict[str, object] = {}
        missing_required: list[str] = []
        bindings = service_bindings or {}
        for binding in self.executor.factory_params:
            present, value = self._resolve_factory_param(
                binding,
                connector=connector,
                business=business,
                report_date=report_date,
                service_bindings=bindings,
            )
            if not present:
                if binding.required:
                    missing_required.append(binding.key or binding.argument)
                continue
            kwargs[binding.argument] = value

        if missing_required:
            missing = (
                missing_required[0]
                if len(missing_required) == 1
                else f"{', '.join(missing_required[:-1])} and {missing_required[-1]}"
            )
            raise ValueError(f"{self.connector_type} connector params must include {missing}")
        return kwargs

    def _validate_key_presence(
        self,
        values: Mapping[str, object],
        keys: tuple[str, ...],
        *,
        missing_code: str,
        empty_code: str,
        label: str,
    ) -> list[ConnectorValidationIssue]:
        issues: list[ConnectorValidationIssue] = []
        for key in keys:
            if key not in values:
                issues.append(
                    ConnectorValidationIssue(
                        code=missing_code,
                        key=key,
                        message=f"{self.connector_type} connector {label} must include {key}",
                    )
                )
            elif values[key] in (None, ""):
                issues.append(
                    ConnectorValidationIssue(
                        code=empty_code,
                        key=key,
                        message=f"{self.connector_type} connector {label} must not leave {key} empty",
                    )
                )
        return issues

    def validate_control_plane_config(
        self,
        *,
        params: Mapping[str, object],
        secret_refs: Mapping[str, object] | None = None,
        strict: bool = False,
    ) -> list[ConnectorValidationIssue]:
        """Validate self-service/control-plane config without requiring raw secrets.

        ``params`` contains public, non-secret connector config. ``secret_refs``
        contains secret handles/IDs that will be resolved by execution runtime.
        Inline legacy secret values in ``params`` never satisfy
        ``required_secret_refs``; they are reported as warnings and remain only
        for current adapter compatibility via ``validate_params``.
        """

        secret_ref_values = secret_refs or {}
        issues = self._validate_key_presence(
            params,
            self.required_config_fields,
            missing_code="missing_required_config",
            empty_code="empty_required_config",
            label="params",
        )
        issues.extend(
            self._validate_key_presence(
                secret_ref_values,
                tuple(secret.name for secret in self.required_secret_refs),
                missing_code="missing_required_secret_ref",
                empty_code="empty_required_secret_ref",
                label="secret_refs",
            )
        )

        for secret in self.required_secret_refs:
            ref_value = secret_ref_values.get(secret.name)
            if ref_value not in (None, "") and not is_secret_ref_handle(ref_value):
                issues.append(
                    ConnectorValidationIssue(
                        code="invalid_secret_ref",
                        key=secret.name,
                        message=(
                            f"{self.connector_type} connector secret_refs.{secret.name} "
                            "must be an opaque secret:// handle"
                        ),
                    )
                )

        for key in self.legacy_secret_config_fields:
            if key in params:
                issues.append(
                    ConnectorValidationIssue(
                        code="legacy_inline_secret",
                        key=key,
                        message=(
                            f"{self.connector_type} connector received legacy inline secret "
                            f"param {key}; control-plane config should use secret_refs"
                        ),
                        severity=SEVERITY_WARNING,
                    )
                )

        if strict:
            known_params = set(self.required_config_fields) | set(self.optional_config_fields) | set(
                self.legacy_secret_config_fields
            )
            for key in sorted(params):
                if key not in known_params:
                    issues.append(
                        ConnectorValidationIssue(
                            code="unknown_config_field",
                            key=key,
                            message=f"{self.connector_type} connector params do not define {key}",
                        )
                    )

        return issues

    def validate_emitted_metrics(
        self,
        metric_keys: Iterable[str],
        *,
        registry: MetricRegistry | None = None,
    ) -> list[MetricValidationIssue]:
        """Compose unknown-metric + source-envelope + family-envelope +
        duplicate-canonical diagnostics for keys emitted under this connector's
        envelope.

        The four diagnostics are independently deterministic and composable by
        design. Concatenating them in the fixed order ``unknown_metric`` ->
        ``disallowed_source`` -> ``undeclared_family`` ->
        ``duplicate_canonical_metric`` yields a stable result the
        runtime/control-plane can compare across runs without overlap: the
        downstream helpers already skip unknown keys. Duplicate-canonical lands
        last on the key level because an alias/canonical pair resolving to one
        metric is a payload-shape problem (double-counting risk in run-ledger
        aggregation) rather than an envelope violation of any single key.
        """

        materialized = list(metric_keys)
        unknown_issues = validate_metrics(
            [{"key": key} for key in materialized],
            registry=registry,
        )
        source_issues = find_source_envelope_violations(
            materialized,
            connector_type=self.connector_type,
            registry=registry,
        )
        family_issues = find_family_envelope_violations(
            materialized,
            connector_type=self.connector_type,
            declared_families=self.emitted_metric_families,
            registry=registry,
        )
        duplicate_issues = find_duplicate_canonical_violations(
            materialized,
            registry=registry,
        )
        return [*unknown_issues, *source_issues, *family_issues, *duplicate_issues]

    def validate_emitted_metric_objects(
        self,
        metrics: Iterable[object],
        *,
        registry: MetricRegistry | None = None,
    ) -> list[MetricValidationIssue]:
        """Compose all nine envelope diagnostics for emitted metric objects.

        Symmetric extension of :meth:`validate_emitted_metrics` that operates
        on metric-shaped objects (each exposing ``key``, ``value``, ``unit``,
        and ``evidence``). The fixed concatenation order ``unknown_metric`` ->
        ``disallowed_source`` -> ``undeclared_family`` ->
        ``duplicate_canonical_metric`` -> ``evidence_missing``
        -> ``evidence_source_mismatch`` -> ``value_kind_mismatch`` ->
        ``value_negative`` -> ``money_currency_missing`` lets the runtime
        treat object-level validation as a superset of key-level validation:
        when every required metric carries non-empty evidence with
        in-envelope sources, every value type matches the canonical unit
        kind, every count/duration value is non-negative, and every money
        metric carries a currency string, the result equals
        ``validate_emitted_metrics`` over the same keys — the four key-level
        diagnostics stay contiguous and in the same relative order.
        ``evidence_missing`` slots between ``duplicate_canonical_metric`` and
        ``evidence_source_mismatch`` so structural ``no evidence at all``
        diagnostics surface before content diagnostics about wrong-source
        evidence; this mirrors the slot reserved by
        :func:`validate_report_metric_objects` and
        :func:`validate_case_metric_objects`. ``value_negative`` slots
        immediately after ``value_kind_mismatch`` so the value-type
        diagnostic (wrong runtime type for canonical unit) precedes the
        value-sign diagnostic (right type but negative for count/duration);
        both populations are disjoint with ``money_currency_missing`` (scoped
        to ``unit="money"``). ``money_currency_missing`` lands last so
        structural and value-type diagnostics surface before the
        rendering-metadata diagnostic that money metrics must carry a
        currency string for the runtime/control-plane to interpret values
        unambiguously, mirroring the slot reserved by
        :func:`validate_report_metric_objects`,
        :func:`validate_case_metric_objects`, and
        :func:`validate_surface_metric_objects`.
        """

        materialized = list(metrics)
        unknown_issues = validate_metrics(materialized, registry=registry)
        keys = [_metric_object_key(metric) for metric in materialized]
        source_issues = find_source_envelope_violations(
            keys,
            connector_type=self.connector_type,
            registry=registry,
        )
        family_issues = find_family_envelope_violations(
            keys,
            connector_type=self.connector_type,
            declared_families=self.emitted_metric_families,
            registry=registry,
        )
        duplicate_issues = find_duplicate_canonical_violations(
            keys,
            registry=registry,
        )
        evidence_missing_issues = find_evidence_required_violations(
            materialized, registry=registry
        )
        evidence_issues = find_evidence_source_violations(
            materialized, registry=registry
        )
        value_kind_issues = find_value_kind_violations(
            materialized, registry=registry
        )
        value_negative_issues = find_negative_value_violations(
            materialized, registry=registry
        )
        money_currency_issues = find_money_currency_violations(
            materialized, registry=registry
        )
        return [
            *unknown_issues,
            *source_issues,
            *family_issues,
            *duplicate_issues,
            *evidence_missing_issues,
            *evidence_issues,
            *value_kind_issues,
            *value_negative_issues,
            *money_currency_issues,
        ]

    def validate_emitted_events(
        self,
        events: Iterable[object],
    ) -> list[ConnectorEventValidationIssue]:
        """Validate emitted connector event types against registry families.

        Connector specs declare event *families* (for example
        ``connector.execution`` and ``connector.health``). Runtime/adapters may
        emit concrete event types under those families, such as
        ``connector.execution.succeeded``. This deterministic certification check
        flags event types outside the connector's declared envelope without
        inventing connector-specific event registries. Health outcome events are
        additionally checked against the spec's health-state taxonomy so
        connector-health logs cannot drift beyond declared runtime states.
        """

        allowed_families = tuple(self.emitted_event_families)
        allowed_health_states = tuple(self.health.allowed_states)
        issues: list[ConnectorEventValidationIssue] = []
        for index, event in enumerate(events):
            event_type = _event_type_value(event)
            is_in_declared_family = any(
                event_type == family or event_type.startswith(f"{family}.")
                for family in allowed_families
            )
            if not is_in_declared_family:
                issues.append(
                    ConnectorEventValidationIssue(
                        code="undeclared_event_family",
                        event_type=event_type,
                        index=index,
                        message=(
                            f"{self.connector_type} connector emitted event {event_type} "
                            "outside declared event families: "
                            + ", ".join(allowed_families)
                        ),
                    )
                )
                continue
            health_prefix = f"{EVENT_FAMILY_CONNECTOR_HEALTH}."
            if (
                EVENT_FAMILY_CONNECTOR_HEALTH in allowed_families
                and event_type.startswith(health_prefix)
            ):
                health_state = event_type.removeprefix(health_prefix)
                declared_health_state = _declared_health_state_for_event(
                    health_state,
                    allowed_health_states=allowed_health_states,
                )
                if declared_health_state is None:
                    issues.append(
                        ConnectorEventValidationIssue(
                            code="undeclared_health_state",
                            event_type=event_type,
                            index=index,
                            message=(
                                f"{self.connector_type} connector emitted health state "
                                f"{health_state} outside declared health states: "
                                + ", ".join(allowed_health_states)
                            ),
                        )
                    )
        return issues

    def validate_params(self, params: Mapping[str, object]) -> list[str]:
        """Return legacy inline execution-param errors without logging credentials.

        Current adapters still accept resolved raw token values as execution
        parameters. Keep this compatibility shim while the control plane moves to
        first-class ``required_secret_refs``.
        """

        issues = self._validate_key_presence(
            params,
            self.required_config_fields + self.legacy_secret_config_fields,
            missing_code="missing_required_param",
            empty_code="empty_required_param",
            label="params",
        )
        return [
            f"{self.connector_type} connector params must include {issue.key}"
            for issue in issues
        ]


class ConnectorRegistry:
    """Typed registry mapping connector type to adapter/spec metadata."""

    def __init__(self, specs: tuple[ConnectorSpec, ...] | None = None) -> None:
        self._specs: dict[str, ConnectorSpec] = {}
        for spec in specs or ():
            self.register(spec)

    def register(self, spec: ConnectorSpec) -> None:
        """Register one spec, rejecting duplicate connector types."""

        if spec.connector_type in self._specs:
            raise ValueError(f"Connector type '{spec.connector_type}' is already registered")
        self._specs[spec.connector_type] = spec

    def get(self, connector_type: str) -> ConnectorSpec:
        """Return a connector spec or raise a helpful unknown-type error."""

        try:
            return self._specs[connector_type]
        except KeyError as exc:
            available = ", ".join(self.connector_types()) or "none"
            raise UnknownConnectorError(
                f"Unknown connector type '{connector_type}'. Available connector types: {available}"
            ) from exc

    def has(self, connector_type: str) -> bool:
        return connector_type in self._specs

    def connector_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def specs(self) -> tuple[ConnectorSpec, ...]:
        return tuple(self._specs[key] for key in self.connector_types())

    def as_mapping(self) -> Mapping[str, ConnectorSpec]:
        """Read-only view for callers that need a mapping interface."""

        return MappingProxyType(self._specs)

    def validate_config(self, connector_type: str, params: Mapping[str, object]) -> list[str]:
        return self.get(connector_type).validate_params(params)

    def validate_control_plane_config(
        self,
        connector_type: str,
        *,
        params: Mapping[str, object],
        secret_refs: Mapping[str, object] | None = None,
        strict: bool = False,
    ) -> list[ConnectorValidationIssue]:
        return self.get(connector_type).validate_control_plane_config(
            params=params,
            secret_refs=secret_refs,
            strict=strict,
        )


def connector_contract_metadata(
    spec: ConnectorSpec,
    *,
    connector_label: str | None = None,
) -> dict[str, Any]:
    """Return serializable registry contract metadata for a connector spec."""

    metadata: dict[str, Any] = {}
    if connector_label:
        metadata["label"] = connector_label
    assert spec.executor is not None  # populated by ConnectorSpec.__post_init__
    metadata.update(
        {
            "executor_factory_path": spec.factory_path,
            "supported_runtime_modes": list(spec.executor.supported_runtime_modes),
            "capabilities": list(spec.capabilities),
            "emitted_metric_families": list(spec.emitted_metric_families),
            "emitted_event_families": list(spec.emitted_event_families),
            "required_scopes": list(spec.scopes.required),
            "health_policy": spec.health_policy_metadata(),
            "rate_limit_policy": spec.rate_limit_policy_metadata(),
            "lifecycle": spec.lifecycle_metadata(),
        }
    )
    return metadata


def _access_token_requirement(
    *,
    provider: str,
    description: str,
    scopes: tuple[str, ...],
) -> SecretRequirement:
    return SecretRequirement(
        name="access_token",
        provider=provider,
        description=description,
        scopes=scopes,
        legacy_config_field="access_token",
    )


def _woocommerce_secret_requirement(
    *,
    name: str,
    description: str,
) -> SecretRequirement:
    return SecretRequirement(
        name=name,
        provider="woocommerce_rest_api",
        description=description,
        scopes=("orders.read", "products.read"),
        legacy_config_field=name,
    )


def _daily_executor(
    *,
    adapter_module: str,
    report_factory: str,
    factory_params: tuple[ConnectorFactoryParam, ...],
) -> ConnectorExecutorMetadata:
    return ConnectorExecutorMetadata(
        adapter_module=adapter_module,
        report_factory=report_factory,
        factory_params=factory_params,
    )


def _common_daily_params() -> tuple[ConnectorFactoryParam, ConnectorFactoryParam]:
    return (
        ConnectorFactoryParam("business_name", "business_attr", key="business_name"),
        ConnectorFactoryParam("report_date", "report_date"),
    )


DEFAULT_CONNECTOR_SPECS: tuple[ConnectorSpec, ...] = (
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_CSV,
        display_name="CSV file",
        adapter_module="app.brain.adapters.csv_file",
        report_factory="build_daily_report_from_csv_file",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_FILE_IMPORT),
        emitted_metric_families=(
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ),
        required_config_fields=("csv_path",),
        optional_config_fields=("source_label",),
        executor=_daily_executor(
            adapter_module="app.brain.adapters.csv_file",
            report_factory="build_daily_report_from_csv_file",
            factory_params=(
                *_common_daily_params(),
                ConnectorFactoryParam("csv_path", "connector_param", key="csv_path"),
                ConnectorFactoryParam(
                    "source_label",
                    "connector_param_or_label",
                    key="source_label",
                ),
                ConnectorFactoryParam("insight_thresholds", "insight_thresholds"),
            ),
        ),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=10),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_GOOGLE_SHEETS,
        display_name="Google Sheets",
        adapter_module="app.brain.adapters.google_sheets",
        report_factory="build_daily_report_from_sheet",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_SHEET_IMPORT),
        emitted_metric_families=(
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ),
        required_config_fields=("spreadsheet_id", "range_name"),
        executor=_daily_executor(
            adapter_module="app.brain.adapters.google_sheets",
            report_factory="build_daily_report_from_sheet",
            factory_params=(
                *_common_daily_params(),
                ConnectorFactoryParam("spreadsheet_id", "connector_param", key="spreadsheet_id"),
                ConnectorFactoryParam("range_name", "connector_param", key="range_name"),
                ConnectorFactoryParam("source_label", "connector_label"),
                ConnectorFactoryParam(
                    "service",
                    "service_binding",
                    key="sheets_service",
                    required=False,
                ),
                ConnectorFactoryParam("insight_thresholds", "insight_thresholds"),
            ),
        ),
        scopes=ConnectorScopeMetadata(required=("spreadsheets.readonly",)),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_MERCADOLIBRE,
        display_name="MercadoLibre",
        adapter_module="app.brain.adapters.mercadolibre",
        report_factory="build_daily_report_from_mercadolibre",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_COMMERCE_METRICS),
        emitted_metric_families=(
            "commerce.orders",
            "commerce.revenue",
            "commerce.average_order_value",
            "runtime.freshness",
            "runtime.data_quality",
        ),
        required_config_fields=("seller_id",),
        optional_config_fields=("site_id", "source_label"),
        required_secret_refs=(
            _access_token_requirement(
                provider="mercadolibre_oauth",
                description="MercadoLibre API bearer token reference.",
                scopes=("orders.read", "items.read"),
            ),
        ),
        legacy_secret_config_fields=("access_token",),
        executor=_daily_executor(
            adapter_module="app.brain.adapters.mercadolibre",
            report_factory="build_daily_report_from_mercadolibre",
            factory_params=(
                *_common_daily_params(),
                ConnectorFactoryParam("seller_id", "connector_param", key="seller_id"),
                ConnectorFactoryParam("access_token", "resolved_secret_param", key="access_token"),
                ConnectorFactoryParam(
                    "site_id",
                    "connector_param",
                    key="site_id",
                    required=False,
                    fallback="MLA",
                ),
                ConnectorFactoryParam(
                    "source_label",
                    "connector_param_or_label",
                    key="source_label",
                ),
                ConnectorFactoryParam(
                    "http_client",
                    "service_binding",
                    key="mercadolibre_http_client",
                    required=False,
                ),
            ),
        ),
        scopes=ConnectorScopeMetadata(required=("orders.read", "items.read")),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=30, requests_per_minute=60),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_META_ADS,
        display_name="Meta Ads",
        adapter_module="app.brain.adapters.meta_ads",
        report_factory="build_daily_report_from_meta_ads",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_AD_METRICS),
        emitted_metric_families=(
            "ads.spend",
            "ads.delivery",
            "ads.roas",
            "runtime.freshness",
            "runtime.data_quality",
        ),
        required_config_fields=("ad_account_id",),
        optional_config_fields=("source_label",),
        required_secret_refs=(
            _access_token_requirement(
                provider="meta_marketing_api",
                description="Meta Marketing API access token reference.",
                scopes=("ads_read", "read_insights"),
            ),
        ),
        legacy_secret_config_fields=("access_token",),
        executor=_daily_executor(
            adapter_module="app.brain.adapters.meta_ads",
            report_factory="build_daily_report_from_meta_ads",
            factory_params=(
                *_common_daily_params(),
                ConnectorFactoryParam("ad_account_id", "connector_param", key="ad_account_id"),
                ConnectorFactoryParam("access_token", "resolved_secret_param", key="access_token"),
                ConnectorFactoryParam(
                    "source_label",
                    "connector_param_or_label",
                    key="source_label",
                ),
                ConnectorFactoryParam(
                    "http_client",
                    "service_binding",
                    key="meta_ads_http_client",
                    required=False,
                ),
            ),
        ),
        scopes=ConnectorScopeMetadata(required=("ads_read", "read_insights")),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=30, requests_per_minute=200),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_SAMPLE,
        display_name="Manual sample payload",
        adapter_module="app.brain.adapters.sample",
        report_factory="build_daily_report_from_payload",
        capabilities=(CAPABILITY_MANUAL_PAYLOAD,),
        emitted_metric_families=("manual.payload", "runtime.freshness", "runtime.data_quality"),
        executor=ConnectorExecutorMetadata(
            adapter_module="app.brain.adapters.sample",
            report_factory="build_daily_report_from_payload",
            supported_runtime_modes=(RUNTIME_MODE_PREVIEW, RUNTIME_MODE_OPERATOR_TRIGGERED),
        ),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_WOOCOMMERCE,
        display_name="WooCommerce",
        adapter_module="app.brain.adapters.woocommerce",
        report_factory="build_daily_report_from_woocommerce",
        capabilities=(
            CAPABILITY_DAILY_REPORT,
            CAPABILITY_COMMERCE_METRICS,
            CAPABILITY_INVENTORY_METRICS,
        ),
        emitted_metric_families=(
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ),
        required_config_fields=("store_url",),
        optional_config_fields=("include_stock", "source_label"),
        required_secret_refs=(
            _woocommerce_secret_requirement(
                name="consumer_key",
                description="WooCommerce REST API consumer key reference.",
            ),
            _woocommerce_secret_requirement(
                name="consumer_secret",
                description="WooCommerce REST API consumer secret reference.",
            ),
        ),
        legacy_secret_config_fields=("consumer_key", "consumer_secret"),
        executor=_daily_executor(
            adapter_module="app.brain.adapters.woocommerce",
            report_factory="build_daily_report_from_woocommerce",
            factory_params=(
                *_common_daily_params(),
                ConnectorFactoryParam("store_url", "connector_param", key="store_url"),
                ConnectorFactoryParam("consumer_key", "resolved_secret_param", key="consumer_key"),
                ConnectorFactoryParam(
                    "consumer_secret", "resolved_secret_param", key="consumer_secret"
                ),
                ConnectorFactoryParam(
                    "http_client",
                    "service_binding",
                    key="woocommerce_http_client",
                    required=False,
                ),
                ConnectorFactoryParam(
                    "include_stock",
                    "connector_param_bool",
                    key="include_stock",
                    required=False,
                    fallback=False,
                ),
                ConnectorFactoryParam(
                    "source_label",
                    "connector_param_or_label",
                    key="source_label",
                ),
            ),
        ),
        scopes=ConnectorScopeMetadata(required=("orders.read", "products.read")),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=30, requests_per_minute=120),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_TIENDANUBE,
        display_name="Tiendanube",
        adapter_module="app.brain.adapters.tiendanube",
        report_factory="build_daily_report_from_tiendanube",
        capabilities=(
            CAPABILITY_DAILY_REPORT,
            CAPABILITY_COMMERCE_METRICS,
            CAPABILITY_INVENTORY_METRICS,
        ),
        emitted_metric_families=(
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ),
        required_config_fields=("store_id",),
        optional_config_fields=("include_stock",),
        required_secret_refs=(
            _access_token_requirement(
                provider="tiendanube_oauth",
                description="Tiendanube API bearer token reference.",
                scopes=("orders.read", "products.read"),
            ),
        ),
        legacy_secret_config_fields=("access_token",),
        executor=_daily_executor(
            adapter_module="app.brain.adapters.tiendanube",
            report_factory="build_daily_report_from_tiendanube",
            factory_params=(
                ConnectorFactoryParam("business_name", "business_attr", key="business_name"),
                ConnectorFactoryParam("store_id", "connector_param", key="store_id"),
                ConnectorFactoryParam("access_token", "resolved_secret_param", key="access_token"),
                ConnectorFactoryParam("report_date", "report_date"),
                ConnectorFactoryParam(
                    "http_client",
                    "service_binding",
                    key="tiendanube_http_client",
                    required=False,
                ),
                ConnectorFactoryParam(
                    "include_stock",
                    "connector_param_bool",
                    key="include_stock",
                    required=False,
                    fallback=False,
                ),
                ConnectorFactoryParam("source_label", "connector_label"),
            ),
        ),
        scopes=ConnectorScopeMetadata(required=("orders.read", "products.read")),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=30, requests_per_minute=120),
    ),
)

_DEFAULT_CONNECTOR_REGISTRY = ConnectorRegistry(DEFAULT_CONNECTOR_SPECS)


def default_connector_registry() -> ConnectorRegistry:
    """Return the process-wide default registry of current connector adapters."""

    return _DEFAULT_CONNECTOR_REGISTRY


def get_connector_spec(connector_type: str) -> ConnectorSpec:
    return default_connector_registry().get(connector_type)


def list_connector_specs() -> tuple[ConnectorSpec, ...]:
    return default_connector_registry().specs()


def validate_connector_config(connector_type: str, params: Mapping[str, object]) -> list[str]:
    return default_connector_registry().validate_config(connector_type, params)


def validate_connector_control_plane_config(
    connector_type: str,
    *,
    params: Mapping[str, object],
    secret_refs: Mapping[str, object] | None = None,
    strict: bool = False,
) -> list[ConnectorValidationIssue]:
    return default_connector_registry().validate_control_plane_config(
        connector_type,
        params=params,
        secret_refs=secret_refs,
        strict=strict,
    )


def validate_emitted_metrics_for_connector(
    connector_type: str,
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Convenience wrapper around ``ConnectorSpec.validate_emitted_metrics``.

    Raises ``UnknownConnectorError`` when ``connector_type`` is not registered
    so callers fail loudly instead of silently skipping envelope diagnostics.
    """

    return get_connector_spec(connector_type).validate_emitted_metrics(
        metric_keys, registry=registry
    )


def validate_emitted_metric_objects_for_connector(
    connector_type: str,
    metrics: Iterable[object],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Convenience wrapper around ``ConnectorSpec.validate_emitted_metric_objects``.

    Raises ``UnknownConnectorError`` when ``connector_type`` is not registered
    so callers cannot silently skip the four-diagnostic composition.
    """

    return get_connector_spec(connector_type).validate_emitted_metric_objects(
        metrics, registry=registry
    )


def validate_emitted_events_for_connector(
    connector_type: str,
    events: Iterable[object],
) -> list[ConnectorEventValidationIssue]:
    """Convenience wrapper around ``ConnectorSpec.validate_emitted_events``.

    Raises ``UnknownConnectorError`` when ``connector_type`` is not registered
    so callers cannot silently skip event-family certification.
    """

    return get_connector_spec(connector_type).validate_emitted_events(events)
