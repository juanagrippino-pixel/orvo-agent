"""Tests for native Operational Cases.

TDD: define case lifecycle and persistence before wiring report execution.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.brain.models import DailyReport, Evidence, Insight, Metric
from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCase,
    OperationalCaseDetection,
    OperationalCaseEvidenceMetric,
    OperationalCaseEvidenceSnapshot,
    OperationalCaseStatusError,
    SQLiteOperationalCaseStore,
    detect_cases_from_report,
)
from app.brain.operator_api.projections import case_detail
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


def test_operational_case_model_enforces_dismissed_at_lifecycle_invariants():
    opened = InMemoryOperationalCaseStore().upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))
    payload = opened.model_dump(mode="python")

    with pytest.raises(ValueError, match="dismissed case requires dismissed_at"):
        OperationalCase.model_validate({**payload, "status": "dismissed", "dismissed_at": None})

    with pytest.raises(ValueError, match="only dismissed cases may have dismissed_at"):
        OperationalCase.model_validate({**payload, "status": "open", "dismissed_at": utc_dt(9)})

    with pytest.raises(ValueError, match="dismissed_at must be after opened_at"):
        OperationalCase.model_validate({**payload, "status": "dismissed", "dismissed_at": utc_dt(7)})


def test_operational_case_model_enforces_resolved_at_lifecycle_invariants():
    opened = InMemoryOperationalCaseStore().upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))
    payload = opened.model_dump(mode="python")

    with pytest.raises(ValueError, match="resolved case requires resolved_at"):
        OperationalCase.model_validate({**payload, "status": "resolved", "resolved_at": None})

    with pytest.raises(ValueError, match="only resolved cases may have resolved_at"):
        OperationalCase.model_validate({**payload, "status": "open", "resolved_at": utc_dt(9)})

    with pytest.raises(ValueError, match="resolved_at must be after opened_at"):
        OperationalCase.model_validate({**payload, "status": "resolved", "resolved_at": utc_dt(7)})


def test_sqlite_store_loads_legacy_dismissed_case_without_dismissed_at(conn):
    store = SQLiteOperationalCaseStore(conn)
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))
    store.transition_case(
        opened.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="juan",
        transitioned_at=utc_dt(9),
    )
    dismissed = store.transition_case(
        opened.case_id,
        status="dismissed",
        actor_type="operator",
        actor_ref="juan",
        reason="Legacy dismissal fixture",
        transitioned_at=utc_dt(10),
    )
    legacy_payload = dismissed.model_dump(mode="json")
    legacy_payload.pop("dismissed_at")
    conn.execute(
        """
        UPDATE operational_cases
        SET data = ?
        WHERE case_id = ?
        """,
        (json.dumps(legacy_payload), dismissed.case_id),
    )

    reloaded = SQLiteOperationalCaseStore(conn).get_case(dismissed.case_id)

    assert reloaded is not None
    assert reloaded.status == "dismissed"
    assert reloaded.dismissed_at == utc_dt(10)


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


@pytest.mark.parametrize("bad_comment", [None, "", "   "])
def test_add_comment_requires_non_empty_comment_without_mutation(conn, bad_comment):
    for label, store in (
        ("memory", InMemoryOperationalCaseStore()),
        ("sqlite", SQLiteOperationalCaseStore(conn)),
    ):
        opened = store.upsert_detection(make_stockout_detection(run_id=f"{label}-run"), detected_at=utc_dt(8))
        before = store.get_case(opened.case_id)
        assert before is not None

        with pytest.raises(ValueError, match="comment must be non-empty"):
            store.add_comment(
                opened.case_id,
                actor_type="operator",
                actor_ref="juan",
                comment=bad_comment,
                commented_at=utc_dt(9),
            )

        after = store.get_case(opened.case_id)
        assert after == before, f"{label}: rejected empty comment must not append timeline events"


@pytest.mark.parametrize("terminal_status", ["resolved", "dismissed"])
@pytest.mark.parametrize("bad_reason", [None, "", "   "])
def test_operator_terminal_transition_requires_non_empty_reason_without_mutation(terminal_status, bad_reason):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))
    if terminal_status == "resolved":
        store.transition_case(
            opened.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            reason="Lo reviso",
            transitioned_at=utc_dt(9),
        )

    before = store.get_case(opened.case_id)
    assert before is not None

    with pytest.raises(OperationalCaseStatusError, match="requires a non-empty reason"):
        store.transition_case(
            opened.case_id,
            status=terminal_status,
            actor_type="operator",
            actor_ref="juan",
            reason=bad_reason,
            transitioned_at=utc_dt(10),
        )

    after = store.get_case(opened.case_id)
    assert after == before


def test_operational_case_supports_in_progress_and_dismissed_lifecycle_with_reopen():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))

    in_progress = store.transition_case(
        opened.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="juan",
        reason="Investigating supplier ETA",
        transitioned_at=utc_dt(9),
    )
    assert in_progress.status == "in_progress"
    assert in_progress.acknowledged_at == utc_dt(9)
    assert in_progress.timeline[-1].metadata == {"from_status": "open", "to_status": "in_progress"}

    dismissed = store.transition_case(
        opened.case_id,
        status="dismissed",
        actor_type="operator",
        actor_ref="juan",
        reason="False positive after physical stock count",
        transitioned_at=utc_dt(10),
    )
    assert dismissed.status == "dismissed"
    assert dismissed.resolved_at is None
    assert dismissed.dismissed_at == utc_dt(10)
    assert dismissed.timeline[-1].metadata == {"from_status": "in_progress", "to_status": "dismissed"}

    with pytest.raises(OperationalCaseStatusError):
        store.transition_case(
            opened.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="juan",
            reason="Cannot resolve a dismissed case manually",
            transitioned_at=utc_dt(11),
        )

    reopened = store.upsert_detection(make_stockout_detection(run_id="run-2"), detected_at=utc_dt(12))
    assert reopened.case_id == opened.case_id
    assert reopened.status == "open"
    assert reopened.acknowledged_at is None
    assert reopened.dismissed_at is None
    assert reopened.timeline[-1].event_type == "case_reopened"


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


# Audit-gap regression: recurrence on a resolved case must preserve the prior
# lifecycle timeline (case_opened → status_changed[ack] → status_changed[resolved])
# AND clear acknowledged_at so the operator is forced to re-acknowledge before
# re-resolving. A future refactor that "cleaned up" timeline on reopen, or that
# left acknowledged_at stale, would silently violate the audit contract without
# tripping `test_resolved_case_reopens_when_same_dedupe_key_recurs`.
def test_recurrence_clears_ack_state_preserves_full_audit_timeline_and_supports_full_lifecycle_restart(conn):
    for label, store in (
        ("memory", InMemoryOperationalCaseStore()),
        ("sqlite", SQLiteOperationalCaseStore(conn)),
    ):
        opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
        store.transition_case(
            opened.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            reason="Lo reviso",
            transitioned_at=utc_dt(9),
        )
        resolved = store.transition_case(
            opened.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="juan",
            reason="Stock repuesto",
            transitioned_at=utc_dt(10),
        )
        assert resolved.acknowledged_at == utc_dt(9), f"{label}: pre-recurrence acknowledged_at must be set"
        pre_recurrence_event_ids = [event.event_id for event in resolved.timeline]
        pre_recurrence_event_types = [event.event_type for event in resolved.timeline]
        assert pre_recurrence_event_types == ["case_opened", "status_changed", "status_changed"], (
            f"{label}: pre-recurrence timeline must contain open + ack + resolve events"
        )

        reopened = store.upsert_detection(
            make_stockout_detection(run_id="run-2", evidence_ref="evidence://tn/stock/2026-05-25"),
            detected_at=utc_dt(11),
        )

        assert reopened.case_id == opened.case_id, f"{label}: recurrence must reuse case_id, not mint a new case"
        assert reopened.status == "open", f"{label}: recurrence must reopen status to 'open'"
        assert reopened.resolved_at is None, f"{label}: recurrence must clear resolved_at"
        assert reopened.acknowledged_at is None, (
            f"{label}: recurrence must clear acknowledged_at so operator is forced to re-acknowledge before re-resolving"
        )
        # Audit history must be additive: prior open/ack/resolve events stay, new reopen event is appended.
        reopened_event_types = [event.event_type for event in reopened.timeline]
        assert reopened_event_types == [
            "case_opened",
            "status_changed",
            "status_changed",
            "case_reopened",
        ], f"{label}: recurrence must append case_reopened without dropping prior audit events"
        assert [event.event_id for event in reopened.timeline[:3]] == pre_recurrence_event_ids, (
            f"{label}: prior audit timeline event ids must remain identical across recurrence"
        )
        assert reopened.source_run_ids == ["run-1", "run-2"], (
            f"{label}: source_run_ids must accumulate across recurrence for audit traceability"
        )
        assert reopened.latest_run_id == "run-2"

        # Full lifecycle must be re-executable on the recurred case without
        # any short-circuit caused by stale acknowledged_at/resolved_at.
        re_acked = store.transition_case(
            reopened.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            reason="Reviso recurrence",
            transitioned_at=utc_dt(12),
        )
        assert re_acked.status == "acknowledged", f"{label}: recurred case must be re-acknowledgeable"
        assert re_acked.acknowledged_at == utc_dt(12), (
            f"{label}: re-acknowledgement must set acknowledged_at to the new transition timestamp"
        )

        re_resolved = store.transition_case(
            reopened.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="juan",
            reason="Stock repuesto otra vez",
            transitioned_at=utc_dt(13),
        )
        assert re_resolved.status == "resolved", f"{label}: recurred case must be re-resolvable"
        assert re_resolved.resolved_at == utc_dt(13)
        # Final timeline must contain the entire audit: original open+ack+resolve,
        # recurrence reopen, and the second ack+resolve. Nothing removed.
        final_event_types = [event.event_type for event in re_resolved.timeline]
        assert final_event_types == [
            "case_opened",
            "status_changed",
            "status_changed",
            "case_reopened",
            "status_changed",
            "status_changed",
        ], f"{label}: full recurrence cycle must accumulate audit events without dropping any"


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


# Contract regression: every production insight title produced by
# `app.brain.insights` must continue to map to a stable case_type so that
# rewording an insight cannot silently drop a case family or its dedupe key.
# Includes title-precedence rules (stock-first, then spend-without-orders
# tokens, conversations, channel, generic ventas). Info-severity always wins.
_PRODUCTION_INSIGHT_CASE_MAPPING = [
    # (id, severity, title, expected_case_type, expected_dedupe_suffix)
    (
        "ventas-drop",
        "warning",
        "Ventas 18% debajo del promedio",
        "sales_drop",
        "sales_drop/channel/all/commerce.revenue/daily",
    ),
    (
        "stock-critico",
        "critical",
        "Stock crítico",
        "stockout_risk",
        "stockout_risk/business/monitored/commerce.inventory/daily",
    ),
    (
        "conversaciones-sin-responder",
        "warning",
        "Conversaciones sin responder",
        "unanswered_conversations",
        "unanswered_conversations/channel/whatsapp/support.conversations/daily",
    ),
    (
        "roas-bajo",
        "warning",
        "ROAS bajo: 1.4x (mínimo recomendado 3.0x)",
        "spend_without_orders",
        "spend_without_orders/channel/meta_ads/ads.spend/daily",
    ),
    (
        "gastas-sin-ventas",
        "critical",
        "Gastás en ads pero sin ventas hoy",
        "spend_without_orders",
        "spend_without_orders/channel/meta_ads/ads.spend/daily",
    ),
    (
        "ads-con-stock-bajo-routes-to-stockout",
        "critical",
        "Ads activos con stock bajo — pausar campañas",
        "stockout_risk",
        "stockout_risk/business/monitored/commerce.inventory/daily",
    ),
]


@pytest.mark.parametrize(
    ("severity", "title", "expected_case_type", "expected_dedupe_suffix"),
    [(item[1], item[2], item[3], item[4]) for item in _PRODUCTION_INSIGHT_CASE_MAPPING],
    ids=[item[0] for item in _PRODUCTION_INSIGHT_CASE_MAPPING],
)
def test_detect_cases_locks_production_insight_titles_to_case_types(
    severity, title, expected_case_type, expected_dedupe_suffix
):
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        insights=[
            Insight(
                severity=severity,
                title=title,
                explanation="Detalle determinístico.",
                recommended_action="Acción operativa.",
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

    assert len(detections) == 1, f"insight {title!r} unexpectedly dropped"
    assert detections[0].case_type == expected_case_type
    assert detections[0].dedupe_key == f"artemea/{expected_dedupe_suffix}"
    assert detections[0].metadata["insight_title"] == title


def test_detect_cases_skips_deferred_channel_mix_shift_until_case_family_metrics_exist():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        insights=[
            Insight(
                severity="warning",
                title="Canal Tiendanube posiblemente sub-rendimiento",
                explanation="El canal requiere métricas channel-scoped antes de promover casos.",
                recommended_action="Monitorear.",
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

    assert detections == []


def test_detect_cases_skips_info_severity_even_when_title_matches_case_family():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        insights=[
            Insight(
                severity="info",
                title="Stock crítico (solo informativo)",
                explanation="Dato informativo.",
                recommended_action="Monitorear.",
                evidence=[source],
            ),
            Insight(
                severity="info",
                title="Canal Tiendanube — informativo",
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

    assert detections == []


# Contract regression for `upsert_data_stale_cases`, the production entrypoint
# called from `record_pipeline_failure` when one or more connectors fail in a
# single pipeline run. The dedupe key embeds {connector_type}; dropping it
# would silently collapse N stale-connector cases into one and blind operators
# to per-connector failures without breaking the existing single-connector
# test at `test_upsert_data_stale_detection_uses_catalog_dedupe_key`.
def test_upsert_data_stale_cases_isolates_per_connector_type_and_pins_severity_contract():
    from app.brain.operational_cases import upsert_data_stale_cases

    store = InMemoryOperationalCaseStore()

    summary = upsert_data_stale_cases(
        case_store=store,
        business_id="artemea",
        connector_types=["tiendanube", "meta_ads"],
        run_id="run-failed-1",
        error_summary="connector failure",
    )

    assert summary.opened_count == 2
    assert summary.updated_count == 0
    assert len(summary.case_ids) == 2
    assert len(set(summary.case_ids)) == 2, "each connector failure must mint a distinct case"

    cases = store.list_cases(business_id="artemea")
    assert len(cases) == 2
    dedupe_keys = {case.dedupe_key for case in cases}
    assert dedupe_keys == {
        "artemea/data_stale/connector/tiendanube/runtime.freshness/daily",
        "artemea/data_stale/connector/meta_ads/runtime.freshness/daily",
    }
    for case in cases:
        assert case.case_type == "data_stale"
        assert case.severity == "warning"
        assert case.priority_score == 80
        assert case.latest_run_id == "run-failed-1"
        assert case.entity_scope["kind"] == "connector"
        assert case.entity_scope["id"] in {"tiendanube", "meta_ads"}
        assert case.title.startswith("Datos stale o fallidos: ")
        assert case.title.endswith(case.entity_scope["id"])


def test_upsert_data_stale_cases_partitions_open_vs_update_on_partial_rerun_and_redacts_secret_error():
    from app.brain.operational_cases import upsert_data_stale_cases

    store = InMemoryOperationalCaseStore()

    first = upsert_data_stale_cases(
        case_store=store,
        business_id="artemea",
        connector_types=["tiendanube"],
        run_id="run-failed-1",
        error_summary="401 Unauthorized access_token=stale_helper_secret",
    )
    assert first.opened_count == 1
    assert first.updated_count == 0

    second = upsert_data_stale_cases(
        case_store=store,
        business_id="artemea",
        connector_types=["tiendanube", "meta_ads"],
        run_id="run-failed-2",
        error_summary="429 rate_limited refresh_token=stale_helper_secret",
    )
    assert second.opened_count == 1, "meta_ads case opens fresh"
    assert second.updated_count == 1, "tiendanube case updates by dedupe_key, not opens a duplicate"

    cases = {case.entity_scope["id"]: case for case in store.list_cases(business_id="artemea")}
    assert set(cases) == {"tiendanube", "meta_ads"}
    assert cases["tiendanube"].latest_run_id == "run-failed-2"
    assert cases["meta_ads"].latest_run_id == "run-failed-2"
    assert "run-failed-1" in cases["tiendanube"].source_run_ids
    assert "run-failed-2" in cases["tiendanube"].source_run_ids

    serialized = " ".join(case.model_dump_json() for case in cases.values())
    assert "stale_helper_secret" not in serialized, (
        "error_summary must be redacted by the helper before persistence"
    )


def test_upsert_data_stale_cases_falls_back_to_unknown_connector_when_none_provided():
    from app.brain.operational_cases import upsert_data_stale_cases

    store_none = InMemoryOperationalCaseStore()
    summary_none = upsert_data_stale_cases(
        case_store=store_none,
        business_id="artemea",
        connector_types=None,
        run_id="run-failed-x",
        error_summary="generic failure",
    )
    assert summary_none.opened_count == 1
    [case_none] = store_none.list_cases(business_id="artemea")
    assert case_none.dedupe_key == "artemea/data_stale/connector/unknown/runtime.freshness/daily"
    assert case_none.entity_scope["id"] == "unknown"

    store_empty = InMemoryOperationalCaseStore()
    summary_empty = upsert_data_stale_cases(
        case_store=store_empty,
        business_id="artemea",
        connector_types=[],
        run_id="run-failed-y",
        error_summary="generic failure",
    )
    assert summary_empty.opened_count == 1
    [case_empty] = store_empty.list_cases(business_id="artemea")
    assert case_empty.dedupe_key == "artemea/data_stale/connector/unknown/runtime.freshness/daily"


def test_case_stores_isolate_tenants_when_dedupe_keys_collide_across_business_ids(conn):
    """Locks the multi-tenant isolation contract for find_by_dedupe_key/upsert_detection.

    Catalog dedupe keys today embed business_id, so collisions are unlikely in
    production. But the OperationalCaseStore contract accepts an arbitrary
    dedupe_key string — if a future refactor or operator-supplied detection ever
    drops the business_id prefix, two tenants could silently merge cases. Both
    InMemory and SQLite stores must scope find/list by business_id.
    """

    shared_dedupe_key = "shared/stockout_risk/business/monitored/commerce.inventory/daily"

    def detection_for(business_id: str, *, run_id: str) -> OperationalCaseDetection:
        return make_stockout_detection(run_id=run_id).model_copy(
            update={"business_id": business_id, "dedupe_key": shared_dedupe_key}
        )

    for label, store in (
        ("memory", InMemoryOperationalCaseStore()),
        ("sqlite", SQLiteOperationalCaseStore(conn)),
    ):
        artemea_case = store.upsert_detection(detection_for("artemea", run_id="run-a-1"), detected_at=utc_dt(8))
        tienda_b_case = store.upsert_detection(detection_for("tienda_b", run_id="run-b-1"), detected_at=utc_dt(8))

        assert artemea_case.case_id != tienda_b_case.case_id, f"{label}: colliding dedupe_keys must yield distinct case_ids per tenant"
        assert store.find_by_dedupe_key("artemea", shared_dedupe_key).case_id == artemea_case.case_id, f"{label}: find_by_dedupe_key must be scoped to business_id"
        assert store.find_by_dedupe_key("tienda_b", shared_dedupe_key).case_id == tienda_b_case.case_id, f"{label}: find_by_dedupe_key must be scoped to business_id"
        assert store.find_by_dedupe_key("unknown", shared_dedupe_key) is None, f"{label}: unrelated tenant must not see colliding case"

        assert [case.case_id for case in store.list_cases(business_id="artemea")] == [artemea_case.case_id], f"{label}: list_cases must isolate by business_id"
        assert [case.case_id for case in store.list_cases(business_id="tienda_b")] == [tienda_b_case.case_id], f"{label}: list_cases must isolate by business_id"

        rerun = store.upsert_detection(detection_for("artemea", run_id="run-a-2"), detected_at=utc_dt(9))
        assert rerun.case_id == artemea_case.case_id, f"{label}: tenant A re-upsert must reuse tenant A case"
        assert rerun.source_run_ids == ["run-a-1", "run-a-2"], f"{label}: tenant A re-upsert must accumulate only its own runs"

        unchanged_b = store.find_by_dedupe_key("tienda_b", shared_dedupe_key)
        assert unchanged_b.case_id == tienda_b_case.case_id, f"{label}: tenant B case must be untouched"
        assert unchanged_b.source_run_ids == ["run-b-1"], f"{label}: tenant B runs must not leak from tenant A re-upsert"
        assert unchanged_b.latest_run_id == "run-b-1", f"{label}: tenant B latest_run_id must be untouched"


def test_upsert_data_stale_cases_is_noop_when_store_or_business_missing():
    from app.brain.operational_cases import upsert_data_stale_cases

    store = InMemoryOperationalCaseStore()

    no_store = upsert_data_stale_cases(
        case_store=None,
        business_id="artemea",
        connector_types=["tiendanube"],
        run_id="run-failed",
        error_summary="anything",
    )
    assert no_store.case_ids == []
    assert no_store.opened_count == 0
    assert no_store.updated_count == 0

    no_business = upsert_data_stale_cases(
        case_store=store,
        business_id=None,
        connector_types=["tiendanube"],
        run_id="run-failed",
        error_summary="anything",
    )
    assert no_business.case_ids == []
    assert no_business.opened_count == 0
    assert no_business.updated_count == 0
    assert store.list_cases() == [], "missing business_id must not persist any case"

def test_detect_cases_from_report_suppresses_stale_stockout_source_into_data_stale_case():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[
            Metric(key="stock_units", label="Unidades en stock", value=2, unit="units", evidence=[source]),
            Metric(
                key="runtime.freshness.age_seconds",
                label="Edad de datos Tiendanube",
                value=172800,
                unit="seconds",
                evidence=[source],
            ),
            Metric(
                key="runtime.connector.status",
                label="Estado Tiendanube",
                value="stale",
                evidence=[source],
            ),
        ],
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan pocas unidades, pero la fuente está stale.",
                recommended_action="Reponer stock.",
                evidence=[source],
            )
        ],
    )

    detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-stale-stock",
        artifact_ref="ledger://runs/run-stale-stock/daily-report",
    )

    assert [detection.case_type for detection in detections] == ["data_stale"]
    stale = detections[0]
    assert stale.dedupe_key == "artemea/data_stale/connector/tiendanube/runtime.freshness/daily"
    assert stale.metadata["affected_case_families"] == ["stockout_risk"]
    assert stale.metadata["suppressed_case_families"] == ["stockout_risk"]
    assert stale.metadata["suggested_action_keys"] == ["refresh_credentials", "retry_connector"]
    assert len(stale.evidence_snapshots) == 1
    snapshot = stale.evidence_snapshots[0]
    assert snapshot.freshness_state == "stale"
    assert snapshot.case_type == "data_stale"
    assert [metric.metric_key for metric in snapshot.metrics] == [
        "runtime.freshness.age_seconds",
        "runtime.connector.status",
    ]


def test_stockout_detection_with_fresh_source_keeps_registered_metrics_and_action_keys():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[
            Metric(key="stock_units", label="Unidades en stock", value=3, unit="units", evidence=[source]),
            Metric(
                key="runtime.freshness.age_seconds",
                label="Edad de datos Tiendanube",
                value=300,
                unit="seconds",
                evidence=[source],
            ),
        ],
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan pocas unidades y los datos están frescos.",
                recommended_action="Confirmar stock.",
                evidence=[source],
            )
        ],
    )

    detections = detect_cases_from_report(business_id="artemea", report=report, run_id="run-fresh-stock")

    assert [detection.case_type for detection in detections] == ["stockout_risk"]
    detection = detections[0]
    assert detection.metadata["suggested_action_keys"] == ["confirm_stock", "pause_promotion"]
    snapshot = detection.evidence_snapshots[0]
    assert snapshot.freshness_state == "fresh"
    assert [metric.metric_key for metric in snapshot.metrics] == [
        "commerce.inventory.available_units",
        "runtime.freshness.age_seconds",
    ]


def test_case_detail_projects_registered_suggested_actions_only():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        make_stockout_detection(),
        detected_at=utc_dt(8),
    )
    case.metadata["suggested_action_keys"] = ["confirm_stock", "invented_action"]

    projection = case_detail(case)

    assert [action["action_key"] for action in projection["suggested_actions"]] == ["confirm_stock"]
    assert projection["suggested_action_keys"] == ["confirm_stock"]
