"""Tests for native Operational Cases.

TDD: define case lifecycle and persistence before wiring report execution.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.brain.models import DailyReport, Evidence, Insight
from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseStatusError,
    SQLiteOperationalCaseStore,
    detect_cases_from_report,
)
from app.brain.storage import init_schema


def utc_dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 24, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    yield c
    c.close()


def make_stockout_detection(*, run_id: str = "run-1", evidence_ref: str = "evidence://tn/stock/2026-05-24"):
    return OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key="artemea/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity="critical",
        priority_score=100,
        entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"recommended_action": "Reponer stock", "access_token": "fixture_secret_token"},
    )


def test_in_memory_operational_case_store_upserts_dedupe_and_tracks_lifecycle():
    store = InMemoryOperationalCaseStore()

    opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
    updated = store.upsert_detection(
        make_stockout_detection(run_id="run-2", evidence_ref="evidence://tn/stock/2026-05-25"),
        detected_at=utc_dt(9),
    )

    assert updated.case_id == opened.case_id
    assert updated.status == "open"
    assert updated.latest_run_id == "run-2"
    assert updated.evidence_refs == ["evidence://tn/stock/2026-05-24", "evidence://tn/stock/2026-05-25"]
    assert updated.artifact_refs == ["ledger://runs/run-1/daily-report", "ledger://runs/run-2/daily-report"]
    assert len(store.list_cases(business_id="artemea")) == 1
    assert "fixture_secret_token" not in updated.model_dump_json()
    assert updated.timeline[0].event_type == "case_opened"
    assert updated.timeline[-1].event_type == "case_updated"

    acknowledged = store.transition_case(
        opened.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="juan",
        reason="Lo reviso hoy",
        transitioned_at=utc_dt(10),
    )
    assert acknowledged.status == "acknowledged"
    assert acknowledged.timeline[-1].event_type == "status_changed"

    resolved = store.transition_case(
        opened.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="juan",
        reason="Stock repuesto",
        transitioned_at=utc_dt(11),
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at == utc_dt(11)

    with pytest.raises(OperationalCaseStatusError):
        store.transition_case(opened.case_id, status="open", actor_type="operator", actor_ref="juan")


def test_operational_case_requires_acknowledged_before_resolved():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))

    with pytest.raises(OperationalCaseStatusError):
        store.transition_case(
            opened.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="juan",
            reason="Trying to skip acknowledgement",
        )


def test_sqlite_operational_case_store_persists_and_filters_by_status(conn):
    store = SQLiteOperationalCaseStore(conn)
    opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
    store.transition_case(
        opened.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="juan",
        reason="En seguimiento",
        transitioned_at=utc_dt(9),
    )

    reloaded = SQLiteOperationalCaseStore(conn).get_case(opened.case_id)

    assert reloaded is not None
    assert reloaded.status == "acknowledged"
    assert reloaded.dedupe_key == "artemea/stockout_risk/business/monitored/commerce.inventory/daily"
    assert SQLiteOperationalCaseStore(conn).find_by_dedupe_key("artemea", reloaded.dedupe_key).case_id == opened.case_id
    assert [case.case_id for case in SQLiteOperationalCaseStore(conn).list_cases(business_id="artemea", status="acknowledged")] == [opened.case_id]
    assert SQLiteOperationalCaseStore(conn).list_cases(business_id="other") == []


def test_operational_case_titles_are_redacted_in_memory_and_sqlite(conn):
    detection = make_stockout_detection()
    detection = detection.model_copy(update={"title": "Stock issue access_token=raw_case_secret"})

    memory_case = InMemoryOperationalCaseStore().upsert_detection(detection, detected_at=utc_dt(8))
    sqlite_store = SQLiteOperationalCaseStore(conn)
    sqlite_case = sqlite_store.upsert_detection(detection, detected_at=utc_dt(8))

    reloaded = sqlite_store.get_case(sqlite_case.case_id)
    assert reloaded is not None

    assert "raw_case_secret" not in memory_case.model_dump_json()
    assert "raw_case_secret" not in reloaded.model_dump_json()


def test_resolved_case_reopens_when_same_dedupe_key_recurs():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
    store.transition_case(opened.case_id, status="acknowledged", actor_type="operator", actor_ref="juan", transitioned_at=utc_dt(9))
    store.transition_case(opened.case_id, status="resolved", actor_type="operator", actor_ref="juan", reason="Fixed", transitioned_at=utc_dt(10))

    reopened = store.upsert_detection(make_stockout_detection(run_id="run-2"), detected_at=utc_dt(11))

    assert reopened.case_id == opened.case_id
    assert reopened.status == "open"
    assert reopened.resolved_at is None
    assert reopened.latest_run_id == "run-2"
    assert reopened.timeline[-1].event_type == "case_reopened"


def test_open_case_queue_orders_by_priority_then_age():
    store = InMemoryOperationalCaseStore()
    warning = make_stockout_detection(run_id="run-1")
    warning = warning.model_copy(
        update={
            "case_type": "sales_drop",
            "dedupe_key": "artemea/sales_drop/channel/all/commerce.revenue/daily",
            "severity": "warning",
            "priority_score": 70,
        }
    )
    critical = make_stockout_detection(run_id="run-2")

    warning_case = store.upsert_detection(warning, detected_at=utc_dt(8))
    critical_case = store.upsert_detection(critical, detected_at=utc_dt(9))

    assert [case.case_id for case in store.list_cases(business_id="artemea", status="open")] == [
        critical_case.case_id,
        warning_case.case_id,
    ]


def test_upsert_data_stale_detection_uses_catalog_dedupe_key():
    from app.brain.operational_cases import make_data_stale_detection

    detection = make_data_stale_detection(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-failed",
        error_summary="401 access_token=raw_failure_secret",
    )
    case = InMemoryOperationalCaseStore().upsert_detection(detection, detected_at=utc_dt(8))

    assert case.case_type == "data_stale"
    assert case.dedupe_key == "artemea/data_stale/connector/tiendanube/runtime.freshness/daily"
    assert case.latest_run_id == "run-failed"
    assert "raw_failure_secret" not in case.model_dump_json()


def test_detect_cases_from_report_maps_actionable_insights_to_deterministic_dedupe_keys():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan 3 unidades disponibles.",
                recommended_action="Reponer stock.",
                evidence=[source],
            ),
            Insight(
                severity="info",
                title="Revenue total multi-canal hoy",
                explanation="Dato informativo.",
                recommended_action="Monitorear.",
                evidence=[source],
            ),
        ],
    )

    detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-1",
        artifact_ref="ledger://runs/run-1/daily-report",
    )

    assert len(detections) == 1
    assert detections[0].case_type == "stockout_risk"
    assert detections[0].dedupe_key == "artemea/stockout_risk/business/monitored/commerce.inventory/daily"
    assert detections[0].evidence_refs == ["evidence://tiendanube/2026-05-24/stockout_risk"]
    assert detections[0].metadata["insight_title"] == "Stock crítico"
