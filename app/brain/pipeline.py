"""End-to-end Orvo Brain report pipelines."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.connector_registry import CAPABILITY_DAILY_REPORT, default_connector_registry
from app.brain.delivery import WhatsAppDeliveryClient
from app.brain.dispatch import IdempotencyStore, ReportDispatchResult, dispatch_daily_report
from app.brain.models import DailyReport
from app.brain.report_merge_policy import merge_daily_reports
from app.brain.security.redaction import redact_text
from app.brain.secret_refs import (
    SecretResolutionError,
    SecretResolver,
    connector_with_resolved_secrets,
)

class PipelineConnectorError(RuntimeError):
    """Connector-scoped pipeline failure with exact attribution context."""

    def __init__(
        self,
        *,
        connector_type: str,
        connector_id: str | None = None,
        business_id: str | None = None,
        original_exception: BaseException,
    ) -> None:
        super().__init__(
            redact_text(f"{type(original_exception).__name__}: {original_exception}")
            or "[REDACTED]"
        )
        self.connector_type = connector_type
        self.connector_id = connector_id
        self.business_id = business_id
        self.original_exception = original_exception


class PipelineConnectorFailure(BaseModel):
    """Audit-safe connector failure captured during a partial multi-connector run."""

    connector_type: str
    connector_id: str | None = None
    business_id: str | None = None
    error_summary: str

    @field_validator("error_summary", mode="before")
    @classmethod
    def redact_error_summary(cls, value: str) -> str:
        return redact_text(value) or "[REDACTED]"

    @classmethod
    def from_error(cls, error: PipelineConnectorError) -> "PipelineConnectorFailure":
        original = error.original_exception
        return cls(
            connector_type=error.connector_type,
            connector_id=error.connector_id,
            business_id=error.business_id,
            error_summary=f"{type(original).__name__}: {original}",
        )


class PipelineAllConnectorsFailedError(RuntimeError):
    """Raised after every attempted data connector failed without usable metrics."""

    def __init__(
        self,
        *,
        business_id: str,
        connector_failures: list[PipelineConnectorFailure],
    ) -> None:
        summary = "; ".join(
            f"{failure.connector_type}: {failure.error_summary}" for failure in connector_failures
        )
        super().__init__(
            redact_text(f"All enabled data connectors failed for {business_id}: {summary}")
            or "All enabled data connectors failed"
        )
        self.business_id = business_id
        self.connector_failures = connector_failures


class PipelineResult(BaseModel):
    report: DailyReport
    dispatch: ReportDispatchResult
    case_brief_dispatch: ReportDispatchResult | None = None
    runtime_metadata: dict = Field(default_factory=dict)
    partial_connector_failures: list[PipelineConnectorFailure] = Field(default_factory=list)


def _find_enabled_connector_for_type(business: BusinessConfig, connector_type: str) -> ConnectorConfig | None:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == connector_type:
            return connector
    return None


def run_connector_daily_report_pipeline(
    *,
    connector_type: str,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    sheets_service=None,
    tiendanube_http_client=None,
    mercadolibre_http_client=None,
    meta_ads_http_client=None,
    woocommerce_http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> PipelineResult:
    """Build one connector report via registry metadata and dispatch it once.

    This keeps connector-specific adapters behind the registry executor contract:
    wrappers below select a connector type and optional service binding only;
    factory kwargs and callable loading come from ``ConnectorSpec`` metadata.
    """

    connector = _find_enabled_connector_for_type(business, connector_type)
    try:
        report = _build_daily_report_for_connector_type(
            connector_type=connector_type,
            business=business,
            report_date=report_date,
            sheets_service=sheets_service,
            tiendanube_http_client=tiendanube_http_client,
            mercadolibre_http_client=mercadolibre_http_client,
            meta_ads_http_client=meta_ads_http_client,
            woocommerce_http_client=woocommerce_http_client,
            secret_resolver=secret_resolver,
        )
    except (ValueError, TypeError):
        raise
    except Exception as exc:
        raise PipelineConnectorError(
            connector_type=connector_type,
            connector_id=connector.connector_id if connector is not None else None,
            business_id=business.business_id,
            original_exception=exc,
        ) from exc
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)


def run_google_sheets_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    sheets_service=None,
) -> PipelineResult:
    """Build a daily report from Google Sheets and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="google_sheets",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        sheets_service=sheets_service,
    )


def run_tiendanube_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> PipelineResult:
    """Build a daily report from Tiendanube and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="tiendanube",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        tiendanube_http_client=http_client,
        secret_resolver=secret_resolver,
    )


def run_csv_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
) -> PipelineResult:
    """Build a daily report from a local CSV file and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="csv",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )


def run_meta_ads_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> PipelineResult:
    """Build a daily report from Meta Ads and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="meta_ads",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        meta_ads_http_client=http_client,
        secret_resolver=secret_resolver,
    )


def run_mercadolibre_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> PipelineResult:
    """Build a daily report from MercadoLibre and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="mercadolibre",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        mercadolibre_http_client=http_client,
        secret_resolver=secret_resolver,
    )


def run_woocommerce_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> PipelineResult:
    """Build a daily report from WooCommerce and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="woocommerce",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        woocommerce_http_client=http_client,
        secret_resolver=secret_resolver,
    )


def _build_daily_report_for_connector_type(
    *,
    connector_type: str,
    business: BusinessConfig,
    report_date: date,
    sheets_service=None,
    tiendanube_http_client=None,
    mercadolibre_http_client=None,
    meta_ads_http_client=None,
    woocommerce_http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> DailyReport:
    registry = default_connector_registry()
    spec = registry.get(connector_type)
    if CAPABILITY_DAILY_REPORT not in spec.capabilities:
        raise ValueError(f"Unsupported connector type for daily report: {connector_type}")

    connector = _find_enabled_connector_for_type(business, connector_type)
    if connector is None:
        raise ValueError(f"Business {business.business_id} has no enabled {connector_type} connector")
    if any(connector.params.get(field) in (None, "") for field in spec.required_config_fields):
        execution_connector = connector
    else:
        execution_connector = connector_with_resolved_secrets(
            connector=connector,
            spec=spec,
            secret_resolver=secret_resolver,
        )

    kwargs = spec.build_report_factory_kwargs(
        connector=execution_connector,
        business=business,
        report_date=report_date,
        service_bindings={
            "sheets_service": sheets_service,
            "tiendanube_http_client": tiendanube_http_client,
            "mercadolibre_http_client": mercadolibre_http_client,
            "meta_ads_http_client": meta_ads_http_client,
            "woocommerce_http_client": woocommerce_http_client,
        },
    )
    report = spec.load_report_factory()(**kwargs)
    if not isinstance(report, DailyReport):
        raise TypeError(f"Connector {connector_type} report factory did not return DailyReport")
    return report


def run_enabled_connectors_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    connector_types: list[str],
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    sheets_service=None,
    tiendanube_http_client=None,
    mercadolibre_http_client=None,
    meta_ads_http_client=None,
    woocommerce_http_client=None,
    secret_resolver: SecretResolver | None = None,
) -> PipelineResult:
    """Build enabled connector reports while preserving typed failure evidence.

    Any connector auth/HTTP/runtime failure is carried forward as audited partial
    connector evidence for the run ledger/case engine. Successful connectors may
    still produce a report. If every attempted source fails, the pipeline raises a
    redacted aggregate error with one failure record per connector instead of
    inventing metrics or dispatching an empty report.
    """

    reports: list[DailyReport] = []
    partial_connector_failures: list[PipelineConnectorFailure] = []
    for connector_type in connector_types:
        connector = _find_enabled_connector_for_type(business, connector_type)
        try:
            reports.append(
                _build_daily_report_for_connector_type(
                    connector_type=connector_type,
                    business=business,
                    report_date=report_date,
                    sheets_service=sheets_service,
                    tiendanube_http_client=tiendanube_http_client,
                    mercadolibre_http_client=mercadolibre_http_client,
                    meta_ads_http_client=meta_ads_http_client,
                    woocommerce_http_client=woocommerce_http_client,
                    secret_resolver=secret_resolver,
                )
            )
        except PipelineConnectorError as exc:
            partial_connector_failures.append(PipelineConnectorFailure.from_error(exc))
            continue
        except SecretResolutionError:
            raise
        except Exception as exc:
            connector_error = PipelineConnectorError(
                connector_type=connector_type,
                connector_id=connector.connector_id if connector is not None else None,
                business_id=business.business_id,
                original_exception=exc,
            )
            partial_connector_failures.append(PipelineConnectorFailure.from_error(connector_error))
            continue
    if not reports and partial_connector_failures:
        raise PipelineAllConnectorsFailedError(
            business_id=business.business_id,
            connector_failures=partial_connector_failures,
        )
    report = merge_daily_reports(reports, business=business)
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(
        report=report,
        dispatch=dispatch,
        partial_connector_failures=partial_connector_failures,
    )
