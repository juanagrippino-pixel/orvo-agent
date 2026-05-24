"""Connector registry for Orvo Brain runtime/control-plane validation.

This module is intentionally additive: it describes the connector adapters that
already exist in ``app.brain.adapters`` without changing the current pipeline
execution paths. Future runtime compilation can depend on these specs to check
connector availability, capabilities, and required config shape before a run.
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


class UnknownConnectorError(ValueError):
    """Raised when a connector type is not registered."""


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
    secret_config_fields: tuple[str, ...] = ()

    @property
    def factory_path(self) -> str:
        """Fully qualified path to the adapter report-builder callable."""

        return f"{self.adapter_module}.{self.report_factory}"

    def validate_params(self, params: Mapping[str, object]) -> list[str]:
        """Return missing required-param errors without touching credentials."""

        missing_fields = [
            field
            for field in self.required_config_fields
            if field not in params or params[field] in (None, "")
        ]
        return [
            f"{self.connector_type} connector params must include {field}"
            for field in missing_fields
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


DEFAULT_CONNECTOR_SPECS: tuple[ConnectorSpec, ...] = (
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_CSV,
        display_name="CSV file",
        adapter_module="app.brain.adapters.csv_file",
        report_factory="build_daily_report_from_csv_file",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_FILE_IMPORT),
        required_config_fields=("csv_path",),
        optional_config_fields=("source_label",),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_GOOGLE_SHEETS,
        display_name="Google Sheets",
        adapter_module="app.brain.adapters.google_sheets",
        report_factory="build_daily_report_from_sheet",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_SHEET_IMPORT),
        required_config_fields=("spreadsheet_id", "range_name"),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_MERCADOLIBRE,
        display_name="MercadoLibre",
        adapter_module="app.brain.adapters.mercadolibre",
        report_factory="build_daily_report_from_mercadolibre",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_COMMERCE_METRICS),
        required_config_fields=("seller_id", "access_token"),
        optional_config_fields=("site_id", "source_label"),
        secret_config_fields=("access_token",),
    ),
    ConnectorSpec(
        connector_type=CONNECTOR_TYPE_META_ADS,
        display_name="Meta Ads",
        adapter_module="app.brain.adapters.meta_ads",
        report_factory="build_daily_report_from_meta_ads",
        capabilities=(CAPABILITY_DAILY_REPORT, CAPABILITY_AD_METRICS),
        required_config_fields=("ad_account_id", "access_token"),
        optional_config_fields=("source_label",),
        secret_config_fields=("access_token",),
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
        required_config_fields=("store_id", "access_token"),
        optional_config_fields=("include_stock",),
        secret_config_fields=("access_token",),
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
