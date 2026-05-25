"""Runtime runner for scheduled Orvo Brain reports."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.brain.config import BusinessConfig, ReportSchedule
from app.brain.delivery import WhatsAppDeliveryClient
from app.brain.dispatch import IdempotencyStore, dispatch_owner_case_brief
from app.brain.execution_ledger import begin_pipeline_run, record_pipeline_failure, record_pipeline_success
from app.brain.operational_cases import OperationalCaseStore
from app.brain.pipeline import PipelineResult, run_enabled_connectors_daily_report_pipeline
from app.brain.run_ledger import RunLedger
from app.brain.runtime import compile_business_runtime, runtime_run_metadata
from app.brain.scheduler import due_schedules

_log = logging.getLogger(__name__)


class ScheduledPipelineResult(BaseModel):
    schedule_id: str
    business_id: str
    report_type: str
    pipeline: PipelineResult
    runtime_metadata: dict = Field(default_factory=dict)

    @property
    def dispatch(self):
        return self.pipeline.dispatch


def _list_all_schedules(config_store, businesses: list[BusinessConfig]) -> list[ReportSchedule]:
    schedules: list[ReportSchedule] = []
    for business in businesses:
        schedules.extend(config_store.list_schedules(business.business_id))
    return schedules


def _enabled_daily_connector_types(business: BusinessConfig) -> list[str]:
    supported = {"csv", "google_sheets", "mercadolibre", "meta_ads", "tiendanube"}
    connector_types: list[str] = []
    for connector in business.connectors:
        if not connector.enabled or connector.connector_type not in supported:
            continue
        if connector.connector_type not in connector_types:
            connector_types.append(connector.connector_type)
    return connector_types


def _with_runtime_metadata(pipeline: PipelineResult, runtime_metadata: dict) -> PipelineResult:
    return pipeline.model_copy(update={"runtime_metadata": runtime_metadata}, deep=True)


def run_due_daily_reports(
    *,
    config_store,
    idempotency_store: IdempotencyStore,
    delivery_client: WhatsAppDeliveryClient,
    sheets_service=None,
    tiendanube_http_client=None,
    mercadolibre_http_client=None,
    meta_ads_http_client=None,
    now: datetime | None = None,
    run_ledger: RunLedger | None = None,
    case_store: OperationalCaseStore | None = None,
) -> list[ScheduledPipelineResult]:
    """Run every due daily report from the config store."""

    now = now or datetime.now(tz=timezone.utc)
    businesses = config_store.list_business_configs()
    business_by_id = {business.business_id: business for business in businesses}
    schedules = _list_all_schedules(config_store, businesses)
    runs = due_schedules(schedules, now, business_by_id)

    results: list[ScheduledPipelineResult] = []
    for run in runs:
        if run.report_type != "daily":
            continue
        business = business_by_id[run.business_id]
        connector_types = _enabled_daily_connector_types(business)
        if not connector_types:
            _log.info(
                "runner no_connectors business_id=%s schedule_id=%s",
                run.business_id, run.schedule_id,
            )
            continue
        runtime = compile_business_runtime(
            business,
            schedules=[schedule for schedule in schedules if schedule.business_id == business.business_id],
            run_mode="scheduled",
        )
        runtime_metadata = begin_pipeline_run(
            run_ledger=run_ledger,
            business_id=business.business_id,
            trigger_type="scheduled",
            runtime_metadata=runtime_run_metadata(runtime),
            summary_metadata={"schedule_id": run.schedule_id, "report_type": run.report_type},
        )
        report_date = run.run_at.astimezone(timezone.utc).date()
        connector_types = runtime.execution_plan.daily_connector_types
        _log.info(
            "runner starting business_id=%s schedule_id=%s report_date=%s connectors=%s",
            run.business_id, run.schedule_id, report_date, connector_types,
        )
        run_id = runtime_metadata.get("run_id")
        try:
            pipeline = _with_runtime_metadata(
                run_enabled_connectors_daily_report_pipeline(
                    business=business,
                    report_date=report_date,
                    connector_types=connector_types,
                    delivery_client=delivery_client,
                    idempotency_store=idempotency_store,
                    sheets_service=sheets_service,
                    tiendanube_http_client=tiendanube_http_client,
                    mercadolibre_http_client=mercadolibre_http_client,
                    meta_ads_http_client=meta_ads_http_client,
                ),
                runtime_metadata,
            )
        except Exception as exc:
            record_pipeline_failure(
                run_ledger=run_ledger,
                case_store=case_store,
                run_id=run_id,
                error=exc,
                business_id=business.business_id,
                connector_types=connector_types,
                summary_metadata={"schedule_id": run.schedule_id, "report_type": run.report_type},
            )
            raise
        case_brief_dispatch = record_pipeline_success(
            run_ledger=run_ledger,
            case_store=case_store,
            run_id=run_id,
            business=business,
            connector_types=connector_types,
            pipeline=pipeline,
            summary_metadata={"schedule_id": run.schedule_id, "report_type": run.report_type},
            case_brief_dispatcher=lambda cases, business=business, report_date=report_date: dispatch_owner_case_brief(
                cases,
                business,
                report_date,
                delivery_client,
                idempotency_store,
            ),
        )
        if case_brief_dispatch is not None:
            pipeline = pipeline.model_copy(update={"case_brief_dispatch": case_brief_dispatch}, deep=True)
        results.append(
            ScheduledPipelineResult(
                schedule_id=run.schedule_id,
                business_id=run.business_id,
                report_type=run.report_type,
                pipeline=pipeline,
                runtime_metadata=runtime_metadata,
            )
        )
    return results
