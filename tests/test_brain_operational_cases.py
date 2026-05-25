"""Tests for native Operational Cases.

TDD: define case lifecycle and persistence before wiring report execution.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.brain.models import DailyReport, Evidence, Insight, Metric
from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceMetric,
    OperationalCaseEvidenceSnapshot,
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


def make_stockout_detection(*, run_id: str = "run-1", evidence_ref: str = "evidence://tn/stock/2026-05-24", snapshots=None):
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
        evidence_snapshots=snapshots or [],
        metadata={"recommended_action": "Reponer stock", "access_token": "fixture_secret_token"},
    )


def make_stock_snapshot(
    *,
    run_id: str = "run-1",
    captured_at: datetime | None = None,
    token: str = "raw_snapshot_secret",
    snapshot_id: str | None = None,
    snapshot_key: str | None = None,
):
    kwargs = {"snapshot_id": snapshot_id} if snapshot_id is not None else {}
    return OperationalCaseEvidenceSnapshot(
        **kwargs,
        snapshot_key=snapshot_key or f"{run_id}/evidence://tn/stock/2026-05-24/stockout_risk/business/monitored",
        captured_at=captured_at or utc_dt(8),
        run_id=run_id,
        artifact_ref=f"ledger://runs/{run_id}/daily-report?access_token={token}",
        evidence_ref=f"evidence://tiendanube/{run_id}/stockout_risk?api_key={token}",
        source="tiendanube",
        source_label=f"Tiendanube access_token={token}",
        case_type="stockout_risk",
        entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        summary=f"Quedan pocas unidades. Bearer {token}",
        freshness_state="fresh",
        metrics=[
            OperationalCaseEvidenceMetric(
                metric_key="commerce.inventory.available_units",
                label=f"Stock access_token={token}",
                value=3,
                unit="units",
                window="daily",
                observed_at=captured_at or utc_dt(8),
                metadata={"access_token": token},
            )
        ],
        metadata={"access_token": token, "safe_note": "fixture"},
    )


def test_operational_case_persists_redacted_evidence_snapshots_and_dedupes_by_snapshot_key(conn):
    snapshot = make_stock_snapshot(run_id="run-1", captured_at=utc_dt(8), token="raw_snapshot_secret")
    store = InMemoryOperationalCaseStore()

    opened = store.upsert_detection(make_stockout_detection(run_id="run-1", snapshots=[snapshot]), detected_at=utc_dt(8))
    duplicate = store.upsert_detection(make_stockout_detection(run_id="run-1", snapshots=[snapshot]), detected_at=utc_dt(9))
    sqlite_store = SQLiteOperationalCaseStore(conn)
    sqlite_case = sqlite_store.upsert_detection(make_stockout_detection(run_id="run-1", snapshots=[snapshot]), detected_at=utc_dt(8))
    reloaded = sqlite_store.get_case(sqlite_case.case_id)

    assert duplicate.case_id == opened.case_id
    assert len(duplicate.evidence_snapshots) == 1
    assert duplicate.evidence_snapshots[0].snapshot_key == snapshot.snapshot_key
    assert duplicate.timeline[-1].evidence_snapshot_ids == [snapshot.snapshot_id]
    assert reloaded is not None
    assert len(reloaded.evidence_snapshots) == 1
    assert "raw_snapshot_secret" not in duplicate.model_dump_json()
    assert "raw_snapshot_secret" not in reloaded.model_dump_json()


def test_evidence_snapshot_key_is_redacted_before_persistence(conn):
    snapshot = make_stock_snapshot(
        snapshot_key="run-1/evidence://tiendanube/stockout?access_token=raw_snapshot_key_secret",
        token="raw_snapshot_key_secret",
    )
    sqlite_store = SQLiteOperationalCaseStore(conn)

    persisted = sqlite_store.upsert_detection(make_stockout_detection(snapshots=[snapshot]), detected_at=utc_dt(8))
    reloaded = sqlite_store.get_case(persisted.case_id)

    assert reloaded is not None
    assert "raw_snapshot_key_secret" not in reloaded.model_dump_json()
    assert reloaded.evidence_snapshots[0].snapshot_key == "run-1/evidence://tiendanube/stockout?access_token=%5BREDACTED%5D"


def test_evidence_update_timeline_references_canonical_snapshot_id_when_duplicate_key_recurs():
    store = InMemoryOperationalCaseStore()
    original = make_stock_snapshot(snapshot_id="snapshot-original", snapshot_key="run-1/evidence://tn/stock/shared")
    duplicate = make_stock_snapshot(snapshot_id="snapshot-discarded", snapshot_key="run-1/evidence://tn/stock/shared")

    opened = store.upsert_detection(make_stockout_detection(run_id="run-1", snapshots=[original]), detected_at=utc_dt(8))
    updated = store.upsert_detection(make_stockout_detection(run_id="run-2", snapshots=[duplicate]), detected_at=utc_dt(9))

    assert updated.case_id == opened.case_id
    assert [snapshot.snapshot_id for snapshot in updated.evidence_snapshots] == ["snapshot-original"]
    assert updated.timeline[-1].evidence_snapshot_ids == ["snapshot-original"]


def test_detect_cases_from_report_synthesizes_minimal_evidence_snapshots():
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
            )
        ],
    )

    detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-1",
        artifact_ref="ledger://runs/run-1/daily-report",
    )

    assert len(detections) == 1
    assert len(detections[0].evidence_snapshots) == 1
    snapshot = detections[0].evidence_snapshots[0]
    assert snapshot.snapshot_key == "run-1/evidence://tiendanube/2026-05-24/stockout_risk/stockout_risk/business/monitored"
    assert snapshot.source == "tiendanube"
    assert snapshot.source_label == "Tiendanube"
    assert snapshot.summary == "Stock crítico"
    assert snapshot.freshness_state == "unknown"
    assert snapshot.artifact_ref == "ledger://runs/run-1/daily-report"


def test_detect_cases_from_report_attaches_canonical_case_metrics_and_advisory_issues_without_mutation():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[
            Metric(key="stock_units", label="Unidades en stock", value=3, unit="units", evidence=[source]),
            Metric(key="custom.owner_note_metric", label="Owner note", value="manual", evidence=[source]),
        ],
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan 3 unidades disponibles.",
                recommended_action="Reponer stock.",
                evidence=[source],
            )
        ],
    )
    original_report_dump = report.model_dump(mode="json")

    detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-1",
        artifact_ref="ledger://runs/run-1/daily-report",
    )

    assert report.model_dump(mode="json") == original_report_dump
    assert len(detections) == 1
    assert detections[0].metadata["metric_registry_issues"] == [
        {
            "code": "unknown_metric",
            "key": "custom.owner_note_metric",
            "message": "Metric key 'custom.owner_note_metric' is not registered in the semantic metric registry",
            "severity": "warning",
            "index": 1,
        }
    ]
    assert detections[0].metadata["metric_registry_mode"] == "advisory"
    assert detections[0].title == "Stock crítico"
    assert detections[0].metadata["recommended_action"] == "Reponer stock."
    assert len(detections[0].evidence_snapshots) == 1
    snapshot = detections[0].evidence_snapshots[0]
    assert [metric.metric_key for metric in snapshot.metrics] == ["commerce.inventory.available_units"]
    assert snapshot.metrics[0].label == "Unidades en stock"
    assert snapshot.metrics[0].value == 3
    assert snapshot.metrics[0].unit == "units"


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
