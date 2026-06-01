"""End-to-end Orvo Brain report pipelines."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.connector_registry import CAPABILITY_DAILY_REPORT, default_connector_registry
from app.brain.delivery import WhatsAppDeliveryClient
from app.brain.dispatch import IdempotencyStore, ReportDispatchResult, dispatch_daily_report
from app.brain.insights import generate_insights
from app.brain.models import DailyReport, Metric


class PipelineResult(BaseModel):
    report: DailyReport
    dispatch: ReportDispatchResult
    case_brief_dispatch: ReportDispatchResult | None = None
    runtime_metadata: dict = Field(default_factory=dict)


class PipelineConnectorError(RuntimeError):
    """Connector-scoped pipeline failure with exact attribution context."""

    def __init__(
        self,
        *,
        connector_type: str,
        connector_id: str | None = None,
        original_exception: BaseException,
    ) -> None:
        super().__init__(str(original_exception))
        self.connector_type = connector_type
        self.connector_id = connector_id
        self.original_exception = original_exception


def _find_enabled_connector_for_type(business: BusinessConfig, connector_type: str) -> ConnectorConfig | None:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == connector_type:
            return connector
    return None


def _is_number(value: float | int | str) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def merge_daily_reports(reports: list[DailyReport], *, business: BusinessConfig | None = None) -> DailyReport:
    """Merge adapter reports into one DailyReport.

    Duplicate metric keys are collapsed so downstream insight/report code sees a
    single canonical key. Numeric duplicates with the same unit are summed and
    their evidence is combined; non-numeric or unit-mismatched duplicates use
    last-wins to keep the key unique and deterministic.
    """
    if not reports:
        raise ValueError("at least one report is required to merge daily reports")
    if len(reports) == 1 and business is None:
        return reports[0]

    merged_by_key = {}
    for report in reports:
        for metric in report.metrics:
            existing = merged_by_key.get(metric.key)
            if existing is None:
                merged_by_key[metric.key] = metric
                continue

            if _is_number(existing.value) and _is_number(metric.value) and existing.unit == metric.unit:
                evidence = [*existing.evidence]
                seen = {(item.source, item.label) for item in evidence}
                for item in metric.evidence:
                    key = (item.source, item.label)
                    if key not in seen:
                        evidence.append(item)
                        seen.add(key)
                merged_by_key[metric.key] = existing.model_copy(
                    update={"value": existing.value + metric.value, "evidence": evidence}
                )
            else:
                merged_by_key[metric.key] = metric

    metrics = list(merged_by_key.values())
    return DailyReport(
        business_name=reports[0].business_name,
        report_date=reports[0].report_date,
        metrics=metrics,
        insights=generate_insights(metrics, thresholds=business.insight_thresholds if business else None),
    )


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
) -> PipelineResult:
    """Build one connector report via registry metadata and dispatch it once.

    This keeps connector-specific adapters behind the registry executor contract:
    wrappers below select a connector type and optional service binding only;
    factory kwargs and callable loading come from ``ConnectorSpec`` metadata.
    """

    report = _build_daily_report_for_connector_type(
        connector_type=connector_type,
        business=business,
        report_date=report_date,
        sheets_service=sheets_service,
        tiendanube_http_client=tiendanube_http_client,
        mercadolibre_http_client=mercadolibre_http_client,
        meta_ads_http_client=meta_ads_http_client,
    )
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
) -> PipelineResult:
    """Build a daily report from Tiendanube and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="tiendanube",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        tiendanube_http_client=http_client,
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
) -> PipelineResult:
    """Build a daily report from Meta Ads and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="meta_ads",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        meta_ads_http_client=http_client,
    )


def run_mercadolibre_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
) -> PipelineResult:
    """Build a daily report from MercadoLibre and dispatch it to WhatsApp."""

    return run_connector_daily_report_pipeline(
        connector_type="mercadolibre",
        business=business,
        report_date=report_date,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
        mercadolibre_http_client=http_client,
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
) -> DailyReport:
    registry = default_connector_registry()
    spec = registry.get(connector_type)
    if CAPABILITY_DAILY_REPORT not in spec.capabilities:
        raise ValueError(f"Unsupported connector type for daily report: {connector_type}")

    connector = _find_enabled_connector_for_type(business, connector_type)
    if connector is None:
        raise ValueError(f"Business {business.business_id} has no enabled {connector_type} connector")

    kwargs = spec.build_report_factory_kwargs(
        connector=connector,
        business=business,
        report_date=report_date,
        service_bindings={
            "sheets_service": sheets_service,
            "tiendanube_http_client": tiendanube_http_client,
            "mercadolibre_http_client": mercadolibre_http_client,
            "meta_ads_http_client": meta_ads_http_client,
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
) -> PipelineResult:
    """Build all enabled connector reports, merge metrics, then dispatch once."""

    reports: list[DailyReport] = []
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
                )
            )
        except PipelineConnectorError:
            raise
        except Exception as exc:
            raise PipelineConnectorError(
                connector_type=connector_type,
                connector_id=connector.connector_id if connector is not None else None,
                original_exception=exc,
            ) from exc
    report = merge_daily_reports(reports, business=business)
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)
