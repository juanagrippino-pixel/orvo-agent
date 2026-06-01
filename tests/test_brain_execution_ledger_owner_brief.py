from __future__ import annotations

from datetime import date, datetime, timezone

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.dispatch import ReportDispatchResult
from app.brain.execution_ledger import record_pipeline_success
from app.brain.models import DailyReport
from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection, OperationalCaseType
from app.brain.pipeline import PipelineResult
from app.brain.run_ledger import InMemoryRunLedger


def utc(hour: int) -> datetime:
    return datetime(2026, 6, 1, hour, tzinfo=timezone.utc)


def case_detection(
    *, run_id: str, case_type: OperationalCaseType = "stockout_risk", business_id: str = "artemea"
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{case_type}/business/monitored/commerce.inventory/daily/{run_id}",
        title="Stock crítico",
        severity="critical",
        priority_score=100,
        entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        evidence_refs=[f"evidence://tiendanube/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def test_record_pipeline_success_sends_owner_brief_all_actionable_statuses_only():
    """Owner WhatsApp briefs must project canonical actionable cases, including work already in progress.

    The source of truth is the case store/status category, not a report-only open/acknowledged subset.
    Resolved cases stay hidden so completed work does not become actionable again via the delivery surface.
    """

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(connector_id="tn", connector_type="tiendanube", label="Tiendanube", params={}),
        ],
    )
    ledger = InMemoryRunLedger()
    run = ledger.create_run(business_id="artemea", trigger_type="scheduled")
    case_store = InMemoryOperationalCaseStore()

    open_case = case_store.upsert_detection(case_detection(run_id="run-open"), detected_at=utc(7))
    in_progress_case = case_store.upsert_detection(case_detection(run_id="run-progress"), detected_at=utc(7))
    case_store.transition_case(
        in_progress_case.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=utc(8),
    )
    resolved_case = case_store.upsert_detection(case_detection(run_id="run-resolved"), detected_at=utc(7))
    case_store.transition_case(
        resolved_case.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=utc(8),
    )
    case_store.transition_case(
        resolved_case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Stock replenished",
        transitioned_at=utc(9),
    )

    dispatched_case_ids: list[str] = []

    def owner_brief_dispatcher(cases):
        dispatched_case_ids.extend(case.case_id for case in cases)
        return ReportDispatchResult(status="sent", idempotency_key="artemea/2026-06-01/owner_case_brief")

    record_pipeline_success(
        run_ledger=ledger,
        case_store=case_store,
        run_id=run.run_id,
        business=business,
        connector_types=["tiendanube"],
        pipeline=PipelineResult(
            report=DailyReport(business_name="Artemea", report_date=date(2026, 6, 1)),
            dispatch=ReportDispatchResult(status="sent", idempotency_key="artemea/2026-06-01/daily"),
        ),
        case_brief_dispatcher=owner_brief_dispatcher,
    )

    assert dispatched_case_ids == [open_case.case_id, in_progress_case.case_id]
