"""Connector registry for Orvo Brain runtime/control-plane validation.

This module is intentionally additive: it describes the connector adapters that
already exist in ``app.brain.adapters`` without changing the current pipeline
execution paths. Future runtime compilation can depend on these specs to check
connector availability, capabilities, secret-reference requirements, and config
shape before a run.

TODO(phase-a-runtime): pipeline execution still contains connector-specific
branching. This branch only hardens the registry/control-plane contract; a later
slice should consume ``ConnectorSpec.executor`` from compiled runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

CONNECTOR_TYPE_CSV = "csv"
CONNECTOR_TYPE_GOOGLE_SHEETS = "google_sheets"
CONNECTOR_TYPE_MERCADOLIBRE = "mercadolibre"
CONNECTOR_TYPE_META_ADS = "meta_ads"
CONNECTOR_TYPE_SAMPLE = "sample"
CONNECTOR_TYPE_TIENDANUBE = "tiendanube"

CAPABILITY_DAILY_REPORT = "daily_report"
CAPABILITY_AD_METRICS = "ad_metrics"
CAPABILITY_COMMERCE_METRICS = "commerce_metrics"
CAPABILITY_FILE_IMPORT = "file_import"
CAPABILITY_INVENTORY_METRICS = "inventory_metrics"
CAPABILITY_MANUAL_PAYLOAD = "manual_payload"
CAPABILITY_SHEET_IMPORT = "sheet_import"

RUNTIME_MODE_PREVIEW = "preview"
RUNTIME_MODE_MANUAL = "manual"
RUNTIME_MODE_SCHEDULED = "scheduled"
RUNTIME_MODE_HEALTH_CHECK = "health_check"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


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
class ConnectorExecutorMetadata:
    """Minimal callable metadata for a future registry-driven runtime."""

    adapter_module: str
    report_factory: str
    supported_runtime_modes: tuple[str, ...] = (
        RUNTIME_MODE_PREVIEW,
        RUNTIME_MODE_MANUAL,
        RUNTIME_MODE_SCHEDULED,
    )

    @property
    def factory_path(self) -> str:
        return f"{self.adapter_module}.{self.report_factory}"


@dataclass(frozen=True, slots=True)
class ConnectorHealthMetadata:
    """Readiness/health metadata; implementation remains a later runtime slice."""

    readiness_check: str = "metadata_only"
    supports_health_check: bool = False
    degraded_state: str = "degraded"


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


DEFAULT_CONNECTOR_SPECS: tuple[ConnectorSpec, ...] = (
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_CSV,
        display_name="CSV file",
        adapter_module="app.brain.adapters.csv_file",
        report_factory="build_daily_report_from_csv_file",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_FILE_IMPORT),
        required_config_fields=("csv_path",),
        optional_config_fields=("source_label",),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=10),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_GOOGLE_SHEETS,
        display_name="Google Sheets",
        adapter_module="app.brain.adapters.google_sheets",
        report_factory="build_daily_report_from_sheet",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_SHEET_IMPORT),
        required_config_fields=("spreadsheet_id", "range_name"),
        scopes=ConnectorScopeMetadata(required=("spreadsheets.readonly",)),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_MERCADOLIBRE,
        display_name="MercadoLibre",
        adapter_module="app.brain.adapters.mercadolibre",
        report_factory="build_daily_report_from_mercadolibre",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_COMMERCE_METRICS),
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
        scopes=ConnectorScopeMetadata(required=("orders.read", "items.read")),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=30, requests_per_minute=60),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_META_ADS,
        display_name="Meta Ads",
        adapter_module="app.brain.adapters.meta_ads",
        report_factory="build_daily_report_from_meta_ads",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_AD_METRICS),
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
        scopes=ConnectorScopeMetadata(required=("ads_read", "read_insights")),
        rate_limit=ConnectorRateLimitMetadata(default_timeout_seconds=30, requests_per_minute=200),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_SAMPLE,
        display_name="Manual sample payload",
        adapter_module="app.brain.adapters.sample",
        report_factory="build_daily_report_from_payload",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_MANUAL_PAYLOAD),
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
