"""Runtime runner for scheduled Orvo Brain reports."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from app.brain.config import BusinessConfig, ReportSchedule
from app.brain.delivery import WhatsAppDeliveryClient
from app.brain.dispatch import IdempotencyStore
from app.brain.pipeline import PipelineResult, run_google_sheets_daily_report_pipeline
from app.brain.scheduler import due_schedules


class ScheduledPipelineResult(BaseModel):
    schedule_id: str
    business_id: str
    report_type: str
    pipeline: PipelineResult

    @property
    def dispatch(self):
        return self.pipeline.dispatch


def _list_all_schedules(config_store, businesses: list[BusinessConfig]) -> list[ReportSchedule]:
    schedules: list[ReportSchedule] = []
    for business in businesses:
        schedules.extend(config_store.list_schedules(business.business_id))
    return schedules


def run_due_daily_reports(
    *,
    config_store,
    idempotency_store: IdempotencyStore,
    delivery_client: WhatsAppDeliveryClient,
    sheets_service=None,
    now: datetime | None = None,
) -> list[ScheduledPipelineResult]:
    """Run every due daily Google Sheets report from the config store."""

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
        pipeline = run_google_sheets_daily_report_pipeline(
            business=business,
            report_date=run.run_at.astimezone(timezone.utc).date(),
            delivery_client=delivery_client,
            idempotency_store=idempotency_store,
            sheets_service=sheets_service,
        )
        results.append(
            ScheduledPipelineResult(
                schedule_id=run.schedule_id,
                business_id=run.business_id,
                report_type=run.report_type,
                pipeline=pipeline,
            )
        )
    return results
