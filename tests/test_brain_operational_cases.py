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
    make_data_stale_detection,
    owner_facing_actionable_cases,
    upsert_cases_from_report,
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


@pytest.fixture(params=["memory", "sqlite"])
def case_store(request, conn):
    if request.param == "memory":
        return "memory", InMemoryOperationalCaseStore()
    return "sqlite", SQLiteOperationalCaseStore(conn)


def make_stockout_detection(
    *,
    run_id: str = "run-1",
    evidence_ref: str = "evidence://tn/stock/2026-05-24",
    snapshots=None,
    severity="critical",
    priority_score=100,
):
    return OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key="artemea/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity=severity,
        priority_score=priority_score,
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


def test_owner_and_worker_timeline_actor_types_survive_sqlite_reload(conn):
    store = SQLiteOperationalCaseStore(conn)
    opened = store.upsert_detection(make_stockout_detection(run_id="run-actor"), detected_at=utc_dt(8))
    store.add_comment(
        opened.case_id,
        actor_type="owner",
        actor_ref="owner@example.com",
        comment="Owner confirmed the follow-up.",
        commented_at=utc_dt(9),
    )
    store.add_comment(
        opened.case_id,
        actor_type="worker",
        actor_ref="worker:triage",
        comment="Autonomous worker attached context.",
        commented_at=utc_dt(10),
    )

    reloaded = SQLiteOperationalCaseStore(conn).get_case(opened.case_id)

    assert reloaded is not None
    assert [event.actor_type for event in reloaded.timeline[-2:]] == ["owner", "worker"]
    assert [event.actor_ref for event in reloaded.timeline[-2:]] == ["owner@example.com", "worker:triage"]


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


def test_owner_facing_actionable_cases_excludes_legacy_cases_without_evidence_snapshots():
    store = InMemoryOperationalCaseStore()
    with_evidence = store.upsert_detection(
        make_stockout_detection(run_id="run-visible", snapshots=[make_stock_snapshot(run_id="run-visible")]),
        detected_at=utc_dt(8),
    )
    legacy_without_snapshot = OperationalCase.model_validate(
        {
            **with_evidence.model_dump(),
            "case_id": "case-legacy-no-snapshot",
            "dedupe_key": "artemea/stockout_risk/business/legacy/commerce.inventory/daily",
            "evidence_snapshots": [],
        }
    )

    owner_cases = owner_facing_actionable_cases([legacy_without_snapshot, with_evidence])

    assert [case.case_id for case in owner_cases] == [with_evidence.case_id]


def test_owner_facing_actionable_cases_excludes_terminal_and_worker_only_families():
    store = InMemoryOperationalCaseStore()
    visible = store.upsert_detection(
        make_stockout_detection(run_id="run-visible", snapshots=[make_stock_snapshot(run_id="run-visible")]),
        detected_at=utc_dt(8),
    )
    resolved = OperationalCase.model_validate(
        {
            **visible.model_dump(),
            "case_id": "case-resolved-owner-hidden",
            "dedupe_key": "artemea/stockout_risk/business/resolved/commerce.inventory/daily",
            "status": "resolved",
            "resolved_at": utc_dt(9),
        }
    )
    worker_only = OperationalCase.model_validate(
        {
            **visible.model_dump(),
            "case_id": "case-worker-only",
            "dedupe_key": "artemea/unanswered_conversations/channel/whatsapp/support.conversations/daily",
            "case_type": "unanswered_conversations",
            "title": "Conversaciones sin responder",
        }
    )

    owner_cases = owner_facing_actionable_cases([visible, resolved, worker_only])

    assert [case.case_id for case in owner_cases] == [visible.case_id]


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
        metric_registry_mode="enforced",
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
    assert detections[0].metadata["metric_registry_mode"] == "enforced"
    assert detections[0].title == "Stock crítico"
    assert detections[0].metadata["recommended_action"] == "Reponer stock."
    assert len(detections[0].evidence_snapshots) == 1
    snapshot = detections[0].evidence_snapshots[0]
    assert [metric.metric_key for metric in snapshot.metrics] == ["commerce.inventory.available_units"]
    assert snapshot.metrics[0].label == "Unidades en stock"
    assert snapshot.metrics[0].value == 3
    assert snapshot.metrics[0].unit == "units"


def test_detect_cases_from_report_enforced_mode_suppresses_case_when_insight_source_has_unknown_metric():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[
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

    advisory_detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-advisory",
        metric_registry_mode="advisory",
    )
    enforced_detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-enforced",
        metric_registry_mode="enforced",
    )

    assert [detection.case_type for detection in advisory_detections] == ["stockout_risk"]
    assert enforced_detections == []


def test_detect_cases_from_report_uses_enforced_metric_registry_gate_by_default():
    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[
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

    advisory_detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-advisory",
        metric_registry_mode="advisory",
    )
    default_detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-default",
    )

    assert [detection.case_type for detection in advisory_detections] == ["stockout_risk"]
    assert default_detections == []


def test_detect_cases_from_report_enforced_mode_ignores_unknown_metric_from_unrelated_source():
    case_source = Evidence(source="tiendanube", label="Tiendanube")
    unrelated_source = Evidence(source="google_sheets", label="Ventas manuales")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[
            Metric(key="stock_units", label="Unidades en stock", value=3, unit="units", evidence=[case_source]),
            Metric(
                key="custom.owner_note_metric",
                label="Owner note",
                value="manual",
                evidence=[unrelated_source],
            ),
        ],
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan 3 unidades disponibles.",
                recommended_action="Reponer stock.",
                evidence=[case_source],
            )
        ],
    )

    detections = detect_cases_from_report(
        business_id="artemea",
        report=report,
        run_id="run-enforced",
        metric_registry_mode="enforced",
    )

    assert [detection.case_type for detection in detections] == ["stockout_risk"]
    assert "metric_registry_issues" not in detections[0].metadata
    assert "metric_registry_mode" not in detections[0].metadata


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
        reason="Stock producto",
        transitioned_at=utc_dt(11),
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at == utc_dt(11)

    with pytest.raises(OperationalCaseStatusError):
        store.transition_case(opened.case_id, status="open", actor_type="operator", actor_ref="juan")


def test_data_stale_recurrence_reopens_terminal_case_without_manual_transition():
    store = InMemoryOperationalCaseStore()

    opened = store.upsert_detection(
        make_data_stale_detection(
            business_id="artemea",
            connector_type="tiendanube",
            run_id="run-stale-1",
            error_summary="Connector token expired",
        ),
        detected_at=utc_dt(8),
    )
    acknowledged = store.transition_case(
        opened.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Lo reviso hoy",
        transitioned_at=utc_dt(9),
    )
    resolved = store.transition_case(
        opened.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Token renovado",
        transitioned_at=utc_dt(10),
    )

    assert acknowledged.status == "acknowledged"
    assert resolved.status == "resolved"
    assert resolved.resolved_at == utc_dt(10)

    reopened = store.upsert_detection(
        make_data_stale_detection(
            business_id="artemea",
            connector_type="tiendanube",
            run_id="run-stale-2",
            error_summary="Connector failed again",
        ),
        detected_at=utc_dt(12),
    )

    assert reopened.case_id == opened.case_id
    assert reopened.status == "open"
    assert reopened.resolved_at is None
    assert reopened.dismissed_at is None
    assert reopened.acknowledged_at is None
    assert reopened.latest_run_id == "run-stale-2"
    assert reopened.source_run_ids == ["run-stale-1", "run-stale-2"]
    assert reopened.evidence_refs == [
        "evidence://tiendanube/run-stale-1/data_stale",
        "evidence://tiendanube/run-stale-2/data_stale",
    ]
    assert reopened.artifact_refs == [
        "ledger://runs/run-stale-1/failure",
        "ledger://runs/run-stale-2/failure",
    ]
    assert reopened.timeline[-1].event_type == "case_reopened"
    assert reopened.timeline[-1].actor_type == "system"
    assert reopened.timeline[-1].summary == "Reopened data_stale case from deterministic detection."
    assert len(store.list_cases(business_id="artemea", status="open")) == 1


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


def test_recurring_detection_reopens_terminal_case_without_stale_assignment():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
    assigned = store.assign_case(
        opened.case_id,
        actor_type="operator",
        actor_ref="juan",
        assignee_ref="dueña access_token=raw_assignee_secret",
        assigned_at=utc_dt(9),
    )
    acknowledged = store.transition_case(
        assigned.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="juan",
        reason="Checking supplier replenishment",
        transitioned_at=utc_dt(9, minute=30),
    )
    resolved = store.transition_case(
        acknowledged.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="juan",
        reason="Stock count completed",
        transitioned_at=utc_dt(10),
    )

    reopened = store.upsert_detection(make_stockout_detection(run_id="run-2"), detected_at=utc_dt(12))

    assert reopened.case_id == opened.case_id
    assert reopened.status == "open"
    assert reopened.assignee_ref is None
    assert reopened.assigned_at is None
    assert reopened.due_at == utc_dt(14)
    assert reopened.timeline[-1].event_type == "case_reopened"
    assert reopened.timeline[-1].metadata["previous_assignee_ref"] == "dueña access_token=[REDACTED]"
    assert reopened.timeline[-1].metadata["due_at"] == utc_dt(14).isoformat()
    assert "raw_assignee_secret" not in reopened.model_dump_json()


# Lifecycle-contract regression: lock down the full transition_case matrix so
# that a future refactor of `_CASE_STATUS_TRANSITIONS` (e.g. allowing operators
# to "un-resolve" a case, skip acknowledgement, or no-op self-transitions) is
# caught before it silently invalidates the audit trail or the
# acknowledged-before-resolved safety property.
@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("open", "open"),
        ("open", "resolved"),
        ("acknowledged", "open"),
        ("acknowledged", "acknowledged"),
        ("resolved", "open"),
        ("resolved", "acknowledged"),
        ("resolved", "resolved"),
    ],
)
def test_transition_case_rejects_every_forbidden_status_transition(from_status, to_status):
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
    if from_status in {"acknowledged", "resolved"}:
        store.transition_case(
            case.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            transitioned_at=utc_dt(9),
        )
    if from_status == "resolved":
        store.transition_case(
            case.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="juan",
            reason="Resolved test fixture",
            transitioned_at=utc_dt(10),
        )

    before = store.get_case(case.case_id)
    assert before is not None and before.status == from_status

    with pytest.raises(OperationalCaseStatusError):
        store.transition_case(
            case.case_id,
            status=to_status,
            actor_type="operator",
            actor_ref="juan",
            transitioned_at=utc_dt(11),
        )

    after = store.get_case(case.case_id)
    assert after is not None
    assert after.status == from_status, (
        f"rejected transition {from_status}->{to_status} must not mutate case status"
    )
    assert after.timeline == before.timeline, (
        f"rejected transition {from_status}->{to_status} must not append a timeline event"
    )
    assert after.updated_at == before.updated_at, (
        f"rejected transition {from_status}->{to_status} must not bump updated_at"
    )


def test_upsert_priority_and_severity_changes_are_auditable(case_store):
    label, store = case_store
    opened = store.upsert_detection(make_stockout_detection(run_id=f"{label}-run-1"), detected_at=utc_dt(8))
    lower_priority = make_stockout_detection(
        run_id=f"{label}-run-2",
        evidence_ref="evidence://tn/stock/2026-05-25",
        severity="warning",
        priority_score=80,
    )

    updated = store.upsert_detection(lower_priority, detected_at=utc_dt(9))

    assert updated.case_id == opened.case_id
    assert updated.priority_score == 80
    assert updated.severity == "warning"
    assert updated.timeline[-1].event_type == "case_updated"
    assert updated.timeline[-1].metadata == {
        "dedupe_key": opened.dedupe_key,
        "previous_priority_score": 100,
        "priority_score": 80,
        "previous_severity": "critical",
        "severity": "warning",
    }


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
    assert reopened.timeline[-1].metadata == {
        "dedupe_key": opened.dedupe_key,
    }


def test_resolved_case_reopens_and_records_priority_change_metadata():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
    store.transition_case(opened.case_id, status="acknowledged", actor_type="operator", actor_ref="juan", transitioned_at=utc_dt(9))
    store.transition_case(opened.case_id, status="resolved", actor_type="operator", actor_ref="juan", reason="Fixed", transitioned_at=utc_dt(10))

    reopened = store.upsert_detection(
        make_stockout_detection(
            run_id="run-2",
            severity="warning",
            priority_score=80,
        ),
        detected_at=utc_dt(10),
    )

    assert reopened.case_id == opened.case_id
    assert reopened.status == "open"
    assert reopened.resolved_at is None
    assert reopened.latest_run_id == "run-2"
    assert reopened.timeline[-1].event_type == "case_reopened"
    assert reopened.timeline[-1].metadata == {
        "dedupe_key": opened.dedupe_key,
        "previous_priority_score": 100,
        "priority_score": 80,
        "previous_severity": "critical",
        "severity": "warning",
    }


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
            reason="Stock producto",
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
            reason="Stock producto otra vez",
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


def test_case_update_records_severity_and_priority_change_audit_metadata():
    store = InMemoryOperationalCaseStore()
    initial = make_stockout_detection(run_id="run-1").model_copy(
        update={"severity": "warning", "priority_score": 70}
    )
    escalated = make_stockout_detection(run_id="run-2")

    store.upsert_detection(initial, detected_at=utc_dt(8))
    updated = store.upsert_detection(escalated, detected_at=utc_dt(9))

    event = updated.timeline[-1]
    assert event.event_type == "case_updated"
    assert event.metadata["dedupe_key"] == initial.dedupe_key
    assert event.metadata["severity_from"] == "warning"
    assert event.metadata["severity_to"] == "critical"
    assert event.metadata["priority_score_from"] == 70
    assert event.metadata["priority_score_to"] == 100

    unchanged = store.upsert_detection(
        make_stockout_detection(run_id="run-3"), detected_at=utc_dt(10)
    )
    event = unchanged.timeline[-1]
    assert event.event_type == "case_updated"
    assert "severity_from" not in event.metadata
    assert "severity_to" not in event.metadata
    assert "priority_score_from" not in event.metadata
    assert "priority_score_to" not in event.metadata


def test_case_recurrence_reopen_records_severity_change_audit_metadata():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(
        make_stockout_detection(run_id="run-1").model_copy(
            update={"severity": "warning", "priority_score": 70}
        ),
        detected_at=utc_dt(8),
    )
    store.transition_case(opened.case_id, status="acknowledged", actor_type="operator", actor_ref="juan", transitioned_at=utc_dt(9))
    store.transition_case(
        opened.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="juan",
        reason="Resolved test fixture",
        transitioned_at=utc_dt(10),
    )

    reopened = store.upsert_detection(make_stockout_detection(run_id="run-2"), detected_at=utc_dt(11))

    event = reopened.timeline[-1]
    assert event.event_type == "case_reopened"
    assert event.metadata["severity_from"] == "warning"
    assert event.metadata["severity_to"] == "critical"
    assert event.metadata["priority_score_from"] == 70
    assert event.metadata["priority_score_to"] == 100


def test_operator_reopen_restores_resolved_case_and_emits_case_reopened_event(conn):
    memory_store = InMemoryOperationalCaseStore()
    sqlite_store = SQLiteOperationalCaseStore(conn)
    reopened_by_store: dict[str, OperationalCase] = {}
    for name, store in (("memory", memory_store), ("sqlite", sqlite_store)):
        opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
        store.transition_case(opened.case_id, status="acknowledged", actor_type="operator", actor_ref="juan", transitioned_at=utc_dt(9))
        store.transition_case(opened.case_id, status="resolved", actor_type="operator", actor_ref="juan", reason="Fixed", transitioned_at=utc_dt(10))

        reopened = store.reopen_case(
            opened.case_id,
            actor_type="operator",
            actor_ref="operator access_token=raw_actor_secret",
            reason="Stock volvió a caer",
            reopened_at=utc_dt(11),
        )
        reopened_by_store[name] = reopened

        assert reopened.status == "open"
        assert reopened.resolved_at is None
        assert reopened.acknowledged_at is None
        assert reopened.updated_at == utc_dt(11)
        event = reopened.timeline[-1]
        assert event.event_type == "case_reopened"
        assert event.actor_type == "operator"
        assert event.actor_ref == "operator access_token=[REDACTED]"
        assert event.created_at == utc_dt(11)
        assert "Stock volvió a caer" in event.summary
        assert event.metadata == {"from_status": "resolved", "to_status": "open"}
        assert "raw_actor_secret" not in reopened.model_dump_json()

        acknowledged_again = store.transition_case(
            reopened.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            transitioned_at=utc_dt(12),
        )
        assert acknowledged_again.status == "acknowledged"

    reloaded = SQLiteOperationalCaseStore(conn).get_case(reopened_by_store["sqlite"].case_id)
    assert reloaded is not None
    assert reloaded.status == "acknowledged"
    assert "raw_actor_secret" not in reloaded.model_dump_json()
    assert any(event.event_type == "case_reopened" for event in reloaded.timeline)


def test_reopen_case_normalizes_blank_reason_to_default_summary():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))
    store.transition_case(opened.case_id, status="acknowledged", actor_type="operator", actor_ref="juan", transitioned_at=utc_dt(9))
    store.transition_case(opened.case_id, status="resolved", actor_type="operator", actor_ref="juan", reason="Fixed", transitioned_at=utc_dt(10))

    reopened = store.reopen_case(
        opened.case_id,
        actor_type="operator",
        actor_ref="juan",
        reason="   ",
        reopened_at=utc_dt(11),
    )

    assert reopened.timeline[-1].summary == "Case reopened by operator."


def test_reopen_case_rejects_non_resolved_cases_and_unknown_case():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))

    with pytest.raises(OperationalCaseStatusError):
        store.reopen_case(opened.case_id, actor_type="operator", actor_ref="juan")

    store.transition_case(opened.case_id, status="acknowledged", actor_type="operator", actor_ref="juan", transitioned_at=utc_dt(9))
    with pytest.raises(OperationalCaseStatusError):
        store.reopen_case(opened.case_id, actor_type="operator", actor_ref="juan")

    with pytest.raises(KeyError):
        store.reopen_case("missing-case", actor_type="operator", actor_ref="juan")


# Audit-gap regression: when an *acknowledged* case receives a new detection
# (within the same lifecycle, without first being resolved), the contract is
# that the operator's ack persists AND the severity/priority/title escalate to
# reflect the new detection. The WhatsApp owner brief relies on this so a case
# that escalates from warning to critical still surfaces with the "✓ Visto"
# tag instead of either (a) silently dropping the ack or (b) silently
# suppressing the new severity. A refactor that flipped either direction would
# slip past the open/resolved recurrence tests above.
def test_upsert_detection_on_acknowledged_case_preserves_ack_and_reflects_escalated_detection(conn):
    initial = OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key="artemea/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock bajo",
        severity="warning",
        priority_score=70,
        entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        evidence_refs=["evidence://tn/stock/2026-05-24"],
        run_id="run-1",
        artifact_refs=["ledger://runs/run-1/daily-report"],
        metadata={"recommended_action": "Vigilar stock"},
    )
    escalated = OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key="artemea/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity="critical",
        priority_score=100,
        entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        evidence_refs=["evidence://tn/stock/2026-05-25"],
        run_id="run-2",
        artifact_refs=["ledger://runs/run-2/daily-report"],
        metadata={"recommended_action": "Reponer stock ya"},
    )

    for label, store in (
        ("memory", InMemoryOperationalCaseStore()),
        ("sqlite", SQLiteOperationalCaseStore(conn)),
    ):
        opened = store.upsert_detection(initial, detected_at=utc_dt(8))
        acked = store.transition_case(
            opened.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            reason="Lo reviso",
            transitioned_at=utc_dt(9),
        )
        assert acked.acknowledged_at == utc_dt(9), (
            f"{label}: ack must be persisted before the escalated re-detection"
        )

        escalated_case = store.upsert_detection(escalated, detected_at=utc_dt(10))

        assert escalated_case.case_id == opened.case_id, (
            f"{label}: escalated detection must reuse the same case_id, not mint a new case"
        )
        assert escalated_case.status == "acknowledged", (
            f"{label}: escalated detection on an acked case must NOT silently drop the ack — the operator already saw it"
        )
        assert escalated_case.acknowledged_at == utc_dt(9), (
            f"{label}: acknowledged_at must be preserved across escalation as the audit anchor"
        )
        assert escalated_case.resolved_at is None, (
            f"{label}: acked-case escalation must not invent a resolved_at"
        )
        assert escalated_case.severity == "critical", (
            f"{label}: severity must reflect the new detection so escalation is visible in the brief"
        )
        assert escalated_case.priority_score == 100, (
            f"{label}: priority_score must reflect the new detection so the case re-ranks in the operator queue"
        )
        assert escalated_case.title == "Stock crítico", (
            f"{label}: title must reflect the new detection so the brief surfaces the escalated context"
        )
        assert escalated_case.latest_run_id == "run-2", (
            f"{label}: latest_run_id must advance to the escalation run"
        )
        assert escalated_case.source_run_ids == ["run-1", "run-2"], (
            f"{label}: source_run_ids must accumulate both runs for audit traceability"
        )
        event_types = [event.event_type for event in escalated_case.timeline]
        assert event_types == ["case_opened", "status_changed", "case_updated"], (
            f"{label}: escalation on an acked case must append `case_updated`, not `case_reopened` (no recurrence)"
        )


# Audit-gap regression: operator comments (`operator_comment` timeline events)
# must survive a full ack -> resolve -> recurrence cycle alongside the system
# `status_changed` / `case_opened` / `case_reopened` events. The existing
# recurrence-audit test only adds status_changed events, so a refactor that
# accidentally filtered the carried-over timeline to system events on
# recurrence (e.g. trying to "reset" the case while keeping the dedupe key)
# would silently erase operator commentary without tripping any current test.
# Operator commentary is the human audit trail Hito 0 supervisors rely on to
# explain why a recurred case was previously resolved.
def test_recurrence_preserves_operator_comments_across_full_lifecycle(conn):
    for label, store in (
        ("memory", InMemoryOperationalCaseStore()),
        ("sqlite", SQLiteOperationalCaseStore(conn)),
    ):
        opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))

        open_comment = store.add_comment(
            opened.case_id,
            actor_type="operator",
            actor_ref="juan",
            comment="Pinged supplier, awaiting reply",
            commented_at=utc_dt(8, 30),
        )
        assert open_comment.timeline[-1].event_type == "operator_comment", (
            f"{label}: comment on open case must append an operator_comment event"
        )

        store.transition_case(
            opened.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="juan",
            reason="Lo reviso",
            transitioned_at=utc_dt(9),
        )

        ack_comment = store.add_comment(
            opened.case_id,
            actor_type="operator",
            actor_ref="juan",
            comment="Supplier confirmed restock for Monday",
            commented_at=utc_dt(9, 30),
        )
        assert ack_comment.timeline[-1].event_type == "operator_comment", (
            f"{label}: comment on acked case must append an operator_comment event"
        )

        resolved = store.transition_case(
            opened.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="juan",
            reason="Stock repuesto",
            transitioned_at=utc_dt(10),
        )

        pre_recurrence_event_types = [event.event_type for event in resolved.timeline]
        assert pre_recurrence_event_types == [
            "case_opened",
            "operator_comment",
            "status_changed",
            "operator_comment",
            "status_changed",
        ], (
            f"{label}: pre-recurrence timeline must interleave operator_comment events with system events"
        )
        pre_recurrence_event_ids = [event.event_id for event in resolved.timeline]
        pre_recurrence_comment_summaries = [
            event.summary for event in resolved.timeline if event.event_type == "operator_comment"
        ]

        reopened = store.upsert_detection(
            make_stockout_detection(run_id="run-2", evidence_ref="evidence://tn/stock/2026-05-25"),
            detected_at=utc_dt(11),
        )

        assert reopened.case_id == opened.case_id, (
            f"{label}: recurrence must reuse case_id, not mint a new case"
        )
        assert reopened.status == "open", f"{label}: recurrence must reopen status to 'open'"

        reopened_event_types = [event.event_type for event in reopened.timeline]
        assert reopened_event_types == [
            "case_opened",
            "operator_comment",
            "status_changed",
            "operator_comment",
            "status_changed",
            "case_reopened",
        ], (
            f"{label}: recurrence must preserve operator_comment events from the prior lifecycle, "
            f"not silently filter them out when carrying the timeline forward"
        )
        assert [event.event_id for event in reopened.timeline[:5]] == pre_recurrence_event_ids, (
            f"{label}: prior timeline event ids (including operator_comment ids) must remain identical across recurrence"
        )
        recurred_comment_summaries = [
            event.summary for event in reopened.timeline if event.event_type == "operator_comment"
        ]
        assert recurred_comment_summaries == pre_recurrence_comment_summaries, (
            f"{label}: operator comment text must be preserved verbatim across recurrence"
        )

        # New comments after recurrence must keep appending without disturbing
        # the prior commentary — the audit trail is purely additive.
        post_recurrence_comment = store.add_comment(
            reopened.case_id,
            actor_type="operator",
            actor_ref="juan",
            comment="Recurrió, revisando supplier de nuevo",
            commented_at=utc_dt(11, 30),
        )
        final_event_types = [event.event_type for event in post_recurrence_comment.timeline]
        assert final_event_types == [
            "case_opened",
            "operator_comment",
            "status_changed",
            "operator_comment",
            "status_changed",
            "case_reopened",
            "operator_comment",
        ], (
            f"{label}: post-recurrence comment must append without dropping prior operator commentary"
        )
        assert [event.event_id for event in post_recurrence_comment.timeline[:5]] == pre_recurrence_event_ids, (
            f"{label}: post-recurrence comment must not rewrite prior timeline event ids"
        )


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
    unrelated_source = Evidence(source="google_sheets", label="Ventas manuales")
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
            Metric(
                key="custom.owner_note_metric",
                label="Owner note",
                value="manual",
                evidence=[unrelated_source],
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
    assert "metric_registry_issues" not in stale.metadata
    assert "metric_registry_mode" not in stale.metadata
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


def test_attach_evidence_appends_snapshot_and_emits_evidence_attached_event(conn):
    for store in (InMemoryOperationalCaseStore(), SQLiteOperationalCaseStore(conn)):
        opened = store.upsert_detection(make_stockout_detection(run_id="run-1"), detected_at=utc_dt(8))
        snapshot = make_stock_snapshot(run_id="run-2", captured_at=utc_dt(9), token="raw_attach_secret")

        attached = store.attach_evidence(
            opened.case_id,
            snapshots=[snapshot],
            actor_type="system",
            actor_ref="orvo_runtime",
            run_id="run-2",
            artifact_ref="ledger://runs/run-2/daily-report",
            summary="Attached Tiendanube stock metric snapshot",
            attached_at=utc_dt(9),
        )

        assert attached.case_id == opened.case_id
        assert attached.status == opened.status
        assert attached.updated_at == utc_dt(9)
        assert [s.snapshot_key for s in attached.evidence_snapshots] == [
            *[s.snapshot_key for s in opened.evidence_snapshots],
            snapshot.snapshot_key,
        ]
        assert snapshot.evidence_ref in attached.evidence_refs
        assert "ledger://runs/run-2/daily-report" in attached.artifact_refs
        assert attached.latest_run_id == "run-2"
        assert attached.source_run_ids == ["run-1", "run-2"]
        event = attached.timeline[-1]
        assert event.event_type == "evidence_attached"
        assert event.actor_type == "system"
        assert event.actor_ref == "orvo_runtime"
        assert event.run_id == "run-2"
        assert event.case_id == opened.case_id
        assert event.artifact_ref == "ledger://runs/run-2/daily-report"
        assert event.created_at == utc_dt(9)
        assert event.summary == "Attached Tiendanube stock metric snapshot"
        assert event.evidence_snapshot_ids == [attached.evidence_snapshots[-1].snapshot_id]
        assert "raw_attach_secret" not in attached.model_dump_json()
        reloaded = store.get_case(opened.case_id)
        assert reloaded is not None
        assert reloaded.timeline[-1].event_type == "evidence_attached"


def test_attach_evidence_dedupes_by_snapshot_key_and_references_canonical_snapshot():
    store = InMemoryOperationalCaseStore()
    snapshot = make_stock_snapshot(run_id="run-1", captured_at=utc_dt(8))
    opened = store.upsert_detection(
        make_stockout_detection(run_id="run-1", snapshots=[snapshot]),
        detected_at=utc_dt(8),
    )

    duplicate = make_stock_snapshot(run_id="run-1", captured_at=utc_dt(9))
    attached = store.attach_evidence(opened.case_id, snapshots=[duplicate], attached_at=utc_dt(9))

    assert len(attached.evidence_snapshots) == 1
    assert attached.evidence_snapshots[0].snapshot_id == opened.evidence_snapshots[0].snapshot_id
    event = attached.timeline[-1]
    assert event.event_type == "evidence_attached"
    assert event.evidence_snapshot_ids == [opened.evidence_snapshots[0].snapshot_id]
    assert event.summary == "Attached 1 evidence snapshot."


def test_attach_evidence_rejects_unknown_case_and_empty_snapshots():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))

    with pytest.raises(KeyError):
        store.attach_evidence("missing-case", snapshots=[make_stock_snapshot()])
    with pytest.raises(ValueError):
        store.attach_evidence(opened.case_id, snapshots=[])


def test_attach_evidence_normalizes_blank_summary_to_default_event_text():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(make_stockout_detection(), detected_at=utc_dt(8))

    attached = store.attach_evidence(
        opened.case_id,
        snapshots=[make_stock_snapshot(run_id="run-2")],
        summary="   ",
        attached_at=utc_dt(9),
    )

    assert attached.timeline[-1].event_type == "evidence_attached"
    assert attached.timeline[-1].summary == "Attached 1 evidence snapshot."


# Audit contract regression: a single report can carry two actionable insights
# that map to the same case family (e.g. "Stock crítico" + "Ads activos con
# stock bajo — pausar campañas" both route to stockout_risk). They must merge
# into one case via dedupe_key, and the mutation summary — which feeds run
# ledger `operational_case_ids` and the audited `cases_opened`/`cases_updated`
# counters — must count that case exactly once, not once per insight.
def test_upsert_cases_from_report_counts_same_run_dedupe_collision_once():
    from app.brain.operational_cases import upsert_cases_from_report

    source = Evidence(source="tiendanube", label="Tiendanube")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 24),
        metrics=[Metric(key="stock_units", label="Unidades en stock", value=3, unit="units", evidence=[source])],
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan 3 unidades disponibles.",
                recommended_action="Reponer stock.",
                evidence=[source],
            ),
            Insight(
                severity="critical",
                title="Ads activos con stock bajo — pausar campañas",
                explanation="Campañas activas apuntan a productos sin stock.",
                recommended_action="Pausar campañas.",
                evidence=[source],
            ),
        ],
    )
    store = InMemoryOperationalCaseStore()

    summary = upsert_cases_from_report(
        case_store=store,
        business_id="artemea",
        report=report,
        run_id="run-1",
        artifact_ref="ledger://runs/run-1/daily-report",
    )

    [case] = store.list_cases(business_id="artemea")
    assert case.dedupe_key == "artemea/stockout_risk/business/monitored/commerce.inventory/daily"
    assert summary.case_ids == [case.case_id], "run ledger must not reference the same case twice"
    assert summary.opened_count == 1
    assert summary.updated_count == 0, "a case opened by this run must not also count as updated"
    timeline_types = [event.event_type for event in case.timeline]
    assert timeline_types == ["case_opened"], (
        "duplicate same-run detections must not duplicate mutation counts or case timeline events"
    )


# Silent metric-drift regression: case.metadata must reflect the LATEST
# detection's metric-registry advisory state, not accumulate stale advisory
# fields from a prior run. If a first run carried `metric_registry_mode` /
# `metric_registry_issues` because the report had an unregistered metric, a
# subsequent clean re-detection of the same case family must clear those keys
# from case.metadata. Otherwise operators see a case that looks like it still
# has registry issues even though the latest evidence is clean — a classic
# metric-drift silent breakage where the audit surface diverges from the
# deterministic detection.
def test_advisory_detection_clears_stale_metric_registry_metadata_on_clean_recurrence():
    from app.brain.operational_cases import detect_cases_from_report

    source = Evidence(source="tiendanube", label="Tiendanube")
    advisory_report = DailyReport(
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
    clean_report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 25),
        metrics=[
            Metric(key="stock_units", label="Unidades en stock", value=2, unit="units", evidence=[source]),
        ],
        insights=[
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation="Quedan 2 unidades disponibles.",
                recommended_action="Reponer stock.",
                evidence=[source],
            )
        ],
    )
    store = InMemoryOperationalCaseStore()

    [advisory_detection] = detect_cases_from_report(
        business_id="artemea",
        report=advisory_report,
        run_id="run-1",
        artifact_ref="ledger://runs/run-1/daily-report",
        metric_registry_mode="advisory",
    )
    case_after_advisory = store.upsert_detection(advisory_detection)
    assert case_after_advisory.metadata["metric_registry_mode"] == "advisory", (
        "first advisory detection must surface state when the report carries an unregistered metric"
    )
    assert case_after_advisory.metadata["metric_registry_issues"], (
        "first advisory detection must surface the deterministic issue list"
    )

    [clean_detection] = detect_cases_from_report(
        business_id="artemea",
        report=clean_report,
        run_id="run-2",
        artifact_ref="ledger://runs/run-2/daily-report",
        metric_registry_mode="advisory",
    )
    case_after_clean = store.upsert_detection(clean_detection)

    assert case_after_clean.case_id == case_after_advisory.case_id, (
        "same dedupe key must update the existing case rather than open a new one"
    )
    assert "metric_registry_mode" not in case_after_clean.metadata, (
        "case.metadata must not retain stale 'metric_registry_mode' once the latest "
        "detection is registry-clean — operators would otherwise see phantom advisory state"
    )
    assert "metric_registry_issues" not in case_after_clean.metadata, (
        "case.metadata must not retain stale 'metric_registry_issues' once the latest "
        "detection is registry-clean — operators would otherwise see phantom issue lists"
    )
    assert case_after_clean.metadata["insight_title"] == "Stock crítico", (
        "non-advisory detection-sourced metadata must still reflect the latest detection"
    )
