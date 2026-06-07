"""Tests for Jira Service Management-style projections over OperationalCase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.service_management import list_service_management_cases, service_management_case_item


NOW = datetime(2026, 5, 24, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str | None = None,
    severity: str = "critical",
    priority: int = 90,
    run_id: str = "run-sm-1",
    metadata: dict | None = None,
) -> OperationalCaseDetection:
    dedupe_suffix = dedupe_suffix or f"{case_type}/business/monitored/runtime.service/daily"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso operativo token=super-secret",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[f"evidence://tiendanube/{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata=metadata or {},
    )


def test_service_management_projection_maps_record_types_owner_status_and_waiting_semantics():
    store = InMemoryOperationalCaseStore()
    incident = store.upsert_detection(
        _detection(case_type="stockout_risk", dedupe_suffix="stockout/business/monitored/inventory/daily"),
        detected_at=NOW - timedelta(hours=1),
    )
    problem = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-problem",
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    waiting_owner = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="conversations/channel/whatsapp/support/daily",
            severity="warning",
            priority=65,
            run_id="run-waiting-owner",
            metadata={"waiting_on": "owner"},
        ),
        detected_at=NOW - timedelta(hours=3),
    )
    waiting_external = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-waiting-external",
            metadata={"waiting_on": "external"},
        ),
        detected_at=NOW - timedelta(hours=4),
    )

    store.transition_case(
        waiting_owner.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2, minutes=30),
    )
    store.transition_case(
        waiting_external.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=3, minutes=30),
    )

    result = list_service_management_cases(store, business_id="artemea", now=NOW, limit=10)
    by_id = {item["case_id"]: item for item in result["service_cases"]}

    assert by_id[incident.case_id]["service_record_type"] == {
        "code": "incident",
        "label": "Incident",
        "label_es": "Incidente",
    }
    assert by_id[incident.case_id]["owner_status"] == {
        "code": "new",
        "label_es": "Nuevo",
        "status_category": "to_do",
        "source_status": "open",
    }
    assert by_id[problem.case_id]["service_record_type"]["code"] == "problem"
    assert by_id[waiting_owner.case_id]["service_record_type"]["code"] == "service_request"
    assert by_id[waiting_owner.case_id]["owner_status"]["code"] == "waiting_owner"
    assert by_id[waiting_owner.case_id]["owner_status"]["status_category"] == "in_progress"
    assert by_id[waiting_external.case_id]["owner_status"]["code"] == "waiting_external"
    assert by_id[waiting_external.case_id]["owner_status"]["status_category"] == "in_progress"
    assert {
        item["owner_status"]["status_category"] for item in result["service_cases"]
    } <= {"to_do", "in_progress", "done"}
    assert result["by_service_record_type"] == {"incident": 2, "problem": 1, "service_request": 1}
    assert result["by_owner_status"] == {
        "new": 2,
        "waiting_external": 1,
        "waiting_owner": 1,
    }


def test_service_management_projection_computes_response_sla_state_deterministically():
    store = InMemoryOperationalCaseStore()
    overdue = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="critical-stockout/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-overdue",
        ),
        detected_at=NOW - timedelta(minutes=90),
    )
    responded = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=75,
            run_id="run-responded",
        ),
        detected_at=NOW - timedelta(hours=3),
    )
    store.transition_case(
        responded.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2),
    )

    overdue_item = service_management_case_item(overdue, now=NOW)
    responded_item = service_management_case_item(store.get_case(responded.case_id), now=NOW)  # type: ignore[arg-type]

    assert overdue_item["sla"]["first_response"] == {
        "policy_key": "first_response_critical_60m",
        "target_seconds": 3600,
        "elapsed_seconds": 5400,
        "remaining_seconds": 0,
        "overdue_seconds": 1800,
        "breached": True,
        "completed": False,
        "started_at": "2026-05-24T10:30:00Z",
        "stopped_at": None,
        "due_at": "2026-05-24T11:30:00Z",
    }
    assert responded_item["sla"]["first_response"]["policy_key"] == "first_response_warning_240m"
    assert responded_item["sla"]["first_response"]["elapsed_seconds"] == 3600
    assert responded_item["sla"]["first_response"]["remaining_seconds"] == 10800
    assert responded_item["sla"]["first_response"]["overdue_seconds"] == 0
    assert responded_item["sla"]["first_response"]["breached"] is False
    assert responded_item["sla"]["first_response"]["completed"] is True


def test_list_service_management_cases_is_business_scoped_limited_and_rejects_naive_now():
    store = InMemoryOperationalCaseStore()
    own = store.upsert_detection(_detection(run_id="run-own"), detected_at=NOW - timedelta(minutes=5))
    store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(minutes=10),
    )

    result = list_service_management_cases(store, business_id="artemea", now=NOW, limit=1)

    assert result["business_id"] == "artemea"
    assert result["limit"] == 1
    assert result["count"] == 1
    assert result["total"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [own.case_id]
    assert "super-secret" not in str(result)

    with pytest.raises(ValueError, match="now must be timezone-aware"):
        list_service_management_cases(
            store,
            business_id="artemea",
            now=datetime(2026, 5, 24, 12),
        )


def test_service_management_projection_stops_sla_clocks_for_dismissed_terminal_cases():
    store = InMemoryOperationalCaseStore()
    dismissed = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="dismissed-stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-dismissed",
        ),
        detected_at=NOW - timedelta(days=5),
    )
    store.transition_case(
        dismissed.case_id,
        status="dismissed",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="False positive after manual connector check.",
        transitioned_at=NOW - timedelta(days=1),
    )

    item = service_management_case_item(store.get_case(dismissed.case_id), now=NOW)  # type: ignore[arg-type]

    assert item["owner_status"]["code"] == "dismissed"
    assert item["dismissed_at"] == "2026-05-23T12:00:00Z"
    assert item["needs_escalation"] is False
    assert item["sla"]["first_response"]["completed"] is True
    assert item["sla"]["first_response"]["stopped_at"] == "2026-05-23T12:00:00Z"
    assert item["sla"]["resolution"]["completed"] is True
    assert item["sla"]["resolution"]["stopped_at"] == "2026-05-23T12:00:00Z"


def test_service_management_projection_pauses_resolution_sla_while_waiting_external():
    store = InMemoryOperationalCaseStore()
    waiting_external = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="paused-stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-paused-waiting-external",
            metadata={"waiting_on": "external"},
        ),
        detected_at=NOW - timedelta(hours=10),
    )
    store.transition_case(
        waiting_external.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=6),
    )
    store.add_comment(
        waiting_external.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Proveedor avisado; esperando respuesta.",
        commented_at=NOW - timedelta(hours=1),
    )

    item = service_management_case_item(store.get_case(waiting_external.case_id), now=NOW)  # type: ignore[arg-type]
    resolution = item["sla"]["resolution"]

    assert item["owner_status"]["code"] == "waiting_external"
    assert resolution["completed"] is False
    assert resolution["paused"] is True
    assert resolution["paused_at"] == "2026-05-24T06:00:00Z"
    assert resolution["pause_reason"] == "waiting_external"
    assert resolution["elapsed_seconds"] == 14400
    assert resolution["remaining_seconds"] == 72000
    assert resolution["breached"] is False
    assert [reason["code"] for reason in item["escalation_reasons"]] == ["waiting_external"]


def test_service_management_projection_exposes_deterministic_escalation_reasons():
    store = InMemoryOperationalCaseStore()
    breached = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="critical-stockout/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-breached",
        ),
        detected_at=NOW - timedelta(hours=5),
    )
    waiting_external = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-waiting-external",
            metadata={"waiting_on": "external"},
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    store.transition_case(
        waiting_external.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=1, minutes=30),
    )

    breached_item = service_management_case_item(breached, now=NOW)
    waiting_item = service_management_case_item(store.get_case(waiting_external.case_id), now=NOW)  # type: ignore[arg-type]

    assert breached_item["needs_escalation"] is True
    assert breached_item["escalation_reasons"] == [
        {
            "code": "critical_case_unacknowledged",
            "label_es": "Caso crítico sin acuse",
            "source": "case_status",
        },
        {
            "code": "first_response_sla_breached",
            "label_es": "SLA de primera respuesta vencido",
            "source": "sla.first_response",
        },
        {
            "code": "resolution_sla_breached",
            "label_es": "SLA de resolución vencido",
            "source": "sla.resolution",
        },
    ]
    assert waiting_item["needs_escalation"] is True
    assert waiting_item["escalation_reasons"] == [
        {
            "code": "waiting_external",
            "label_es": "Bloqueado por un tercero",
            "source": "owner_status",
        }
    ]


def test_service_management_projection_summarizes_next_sla_status_and_counts():
    store = InMemoryOperationalCaseStore()
    breached = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="summary-breached/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-sla-breached",
        ),
        detected_at=NOW - timedelta(minutes=90),
    )
    paused = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="summary-paused/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-sla-paused",
            metadata={"waiting_on": "external"},
        ),
        detected_at=NOW - timedelta(hours=10),
    )
    store.transition_case(
        paused.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=6),
    )
    on_track = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="summary-on-track/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-sla-on-track",
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    resolved = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="summary-completed/channel/whatsapp/support/daily",
            severity="info",
            priority=50,
            run_id="run-sla-completed",
        ),
        detected_at=NOW - timedelta(hours=3),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2, minutes=30),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Owner confirmed the queue was cleared.",
        transitioned_at=NOW - timedelta(hours=1),
    )

    result = list_service_management_cases(store, business_id="artemea", now=NOW, limit=10)
    by_id = {item["case_id"]: item for item in result["service_cases"]}

    assert by_id[breached.case_id]["sla_status"] == {
        "code": "breached",
        "label_es": "SLA vencido",
        "active_policy_key": "first_response_critical_60m",
        "due_at": "2026-05-24T11:30:00Z",
        "remaining_seconds": 0,
        "overdue_seconds": 1800,
    }
    assert by_id[paused.case_id]["sla_status"] == {
        "code": "paused",
        "label_es": "SLA pausado",
        "active_policy_key": "resolution_warning_1440m",
        "due_at": "2026-05-25T02:00:00Z",
        "remaining_seconds": 72000,
        "overdue_seconds": 0,
    }
    assert by_id[on_track.case_id]["sla_status"] == {
        "code": "on_track",
        "label_es": "SLA en curso",
        "active_policy_key": "first_response_warning_240m",
        "due_at": "2026-05-24T14:00:00Z",
        "remaining_seconds": 7200,
        "overdue_seconds": 0,
    }
    assert by_id[resolved.case_id]["sla_status"] == {
        "code": "completed",
        "label_es": "SLA completado",
        "active_policy_key": None,
        "due_at": None,
        "remaining_seconds": None,
        "overdue_seconds": None,
    }
    assert result["by_sla_status"] == {
        "breached": 1,
        "completed": 1,
        "on_track": 1,
        "paused": 1,
    }


def test_service_management_projection_marks_active_sla_at_risk_near_due():
    store = InMemoryOperationalCaseStore()
    at_risk = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="summary-at-risk/business/monitored/inventory/daily",
            severity="critical",
            priority=90,
            run_id="run-sla-at-risk",
        ),
        detected_at=NOW - timedelta(minutes=50),
    )
    on_track = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="summary-at-risk-on-track/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-sla-at-risk-on-track",
        ),
        detected_at=NOW - timedelta(hours=1),
    )

    result = list_service_management_cases(store, business_id="artemea", now=NOW, limit=10)
    by_id = {item["case_id"]: item for item in result["service_cases"]}

    assert by_id[at_risk.case_id]["sla_status"] == {
        "code": "at_risk",
        "label_es": "SLA en riesgo",
        "active_policy_key": "first_response_critical_60m",
        "due_at": "2026-05-24T12:10:00Z",
        "remaining_seconds": 600,
        "overdue_seconds": 0,
    }
    assert by_id[on_track.case_id]["sla_status"]["code"] == "on_track"
    assert result["by_sla_status"] == {"at_risk": 1, "on_track": 1}


def test_list_service_management_cases_filters_by_sla_status_before_limit():
    store = InMemoryOperationalCaseStore()
    breached = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="filter-breached/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-filter-breached",
        ),
        detected_at=NOW - timedelta(minutes=90),
    )
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="filter-on-track/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-filter-on-track",
        ),
        detected_at=NOW - timedelta(hours=2),
    )

    result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        sla_status="breached",
    )

    assert result["filters"] == {"sla_status": "breached"}
    assert result["total"] == 1
    assert result["unfiltered_total"] == 2
    assert result["count"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [breached.case_id]
    assert result["by_sla_status"] == {"breached": 1, "on_track": 1}


def test_list_service_management_cases_filters_by_at_risk_sla_status_before_limit():
    store = InMemoryOperationalCaseStore()
    at_risk = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="filter-at-risk/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-filter-at-risk",
        ),
        detected_at=NOW - timedelta(minutes=50),
    )
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="filter-at-risk-on-track/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-filter-at-risk-on-track",
        ),
        detected_at=NOW - timedelta(hours=1),
    )

    result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        sla_status="at_risk",
    )

    assert result["filters"] == {"sla_status": "at_risk"}
    assert result["total"] == 1
    assert result["unfiltered_total"] == 2
    assert result["count"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [at_risk.case_id]
    assert result["by_sla_status"] == {"at_risk": 1, "on_track": 1}


def test_list_service_management_cases_filters_by_service_record_type_before_limit():
    store = InMemoryOperationalCaseStore()
    incident = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="filter-record-incident/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-filter-record-incident",
        ),
        detected_at=NOW - timedelta(minutes=30),
    )
    problem = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="filter-record-problem/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-filter-record-problem",
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="filter-record-request/channel/whatsapp/support/daily",
            severity="info",
            priority=50,
            run_id="run-filter-record-request",
        ),
        detected_at=NOW - timedelta(hours=3),
    )

    result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        service_record_type="problem",
    )

    assert result["filters"] == {"service_record_type": "problem"}
    assert result["total"] == 1
    assert result["unfiltered_total"] == 3
    assert result["count"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [problem.case_id]
    assert incident.case_id not in [item["case_id"] for item in result["service_cases"]]
    assert result["by_service_record_type"] == {"incident": 1, "problem": 1, "service_request": 1}


def test_list_service_management_cases_filters_by_owner_status_before_limit():
    store = InMemoryOperationalCaseStore()
    waiting_external = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="filter-owner-waiting/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-filter-owner-waiting",
            metadata={"waiting_on": "external"},
        ),
        detected_at=NOW - timedelta(hours=10),
    )
    store.transition_case(
        waiting_external.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=6),
    )
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="filter-owner-new/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-filter-owner-new",
        ),
        detected_at=NOW - timedelta(minutes=30),
    )

    result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        owner_status="waiting_external",
    )

    assert result["filters"] == {"owner_status": "waiting_external"}
    assert result["total"] == 1
    assert result["unfiltered_total"] == 2
    assert result["count"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [waiting_external.case_id]
    assert result["by_owner_status"] == {"new": 1, "waiting_external": 1}


def test_list_service_management_cases_filters_by_escalation_reason_before_limit():
    store = InMemoryOperationalCaseStore()
    breached = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="filter-escalation-breached/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-filter-escalation-breached",
        ),
        detected_at=NOW - timedelta(hours=5),
    )
    waiting_external = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="filter-escalation-waiting/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-filter-escalation-waiting",
            metadata={"waiting_on": "external"},
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    store.transition_case(
        waiting_external.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=1, minutes=30),
    )

    result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        escalation_reason="waiting_external",
    )

    assert result["filters"] == {"escalation_reason": "waiting_external"}
    assert result["total"] == 1
    assert result["unfiltered_total"] == 2
    assert result["count"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [waiting_external.case_id]
    assert breached.case_id not in [item["case_id"] for item in result["service_cases"]]
    assert result["by_escalation_reason"] == {
        "critical_case_unacknowledged": 1,
        "first_response_sla_breached": 1,
        "resolution_sla_breached": 1,
        "waiting_external": 1,
    }


def test_list_service_management_cases_filters_by_needs_escalation_before_limit():
    store = InMemoryOperationalCaseStore()
    breached = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="filter-needs-escalation/business/monitored/inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-filter-needs-escalation",
        ),
        detected_at=NOW - timedelta(hours=5),
    )
    calm = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="filter-no-escalation/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-filter-no-escalation",
        ),
        detected_at=NOW - timedelta(minutes=30),
    )

    escalated = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        needs_escalation=True,
    )
    not_escalated = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=1,
        needs_escalation=False,
    )

    assert escalated["filters"] == {"needs_escalation": True}
    assert escalated["total"] == 1
    assert escalated["unfiltered_total"] == 2
    assert escalated["count"] == 1
    assert [item["case_id"] for item in escalated["service_cases"]] == [breached.case_id]
    assert not_escalated["filters"] == {"needs_escalation": False}
    assert not_escalated["total"] == 1
    assert not_escalated["unfiltered_total"] == 2
    assert not_escalated["count"] == 1
    assert [item["case_id"] for item in not_escalated["service_cases"]] == [calm.case_id]
    assert escalated["by_escalation_reason"] == {
        "critical_case_unacknowledged": 1,
        "first_response_sla_breached": 1,
        "resolution_sla_breached": 1,
    }


def test_list_service_management_cases_can_sort_by_sla_urgency_before_limit():
    store = InMemoryOperationalCaseStore()
    high_priority_on_track = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="sort-sla-high-priority/business/monitored/inventory/daily",
            severity="critical",
            priority=99,
            run_id="run-sort-sla-high-priority",
        ),
        detected_at=NOW - timedelta(minutes=10),
    )
    breached_lower_priority = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sort-sla-breached/channel/all/revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-sort-sla-breached",
        ),
        detected_at=NOW - timedelta(hours=5),
    )
    at_risk_lower_priority = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="sort-sla-at-risk/business/monitored/inventory/daily",
            severity="critical",
            priority=80,
            run_id="run-sort-sla-at-risk",
        ),
        detected_at=NOW - timedelta(minutes=50),
    )

    default_result = list_service_management_cases(store, business_id="artemea", now=NOW, limit=1)
    sla_sorted = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=3,
        sort_by="sla_urgency",
    )

    assert [item["case_id"] for item in default_result["service_cases"]] == [high_priority_on_track.case_id]
    assert sla_sorted["sort_by"] == "sla_urgency"
    assert sla_sorted["total"] == 3
    assert sla_sorted["count"] == 3
    assert [item["case_id"] for item in sla_sorted["service_cases"]] == [
        breached_lower_priority.case_id,
        at_risk_lower_priority.case_id,
        high_priority_on_track.case_id,
    ]
    assert [item["sla_status"]["code"] for item in sla_sorted["service_cases"]] == [
        "breached",
        "at_risk",
        "on_track",
    ]


def test_list_service_management_cases_rejects_unknown_sla_status_filter():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(ValueError, match="unsupported sla_status"):
        list_service_management_cases(
            store,
            business_id="artemea",
            now=NOW,
            sla_status="waiting_external",
        )


def test_list_service_management_cases_rejects_unknown_service_record_type_filter():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(ValueError, match="unsupported service_record_type"):
        list_service_management_cases(
            store,
            business_id="artemea",
            now=NOW,
            service_record_type="task",
        )


def test_list_service_management_cases_rejects_unknown_owner_status_filter():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(ValueError, match="unsupported owner_status"):
        list_service_management_cases(
            store,
            business_id="artemea",
            now=NOW,
            owner_status="blocked",
        )


def test_list_service_management_cases_rejects_unknown_escalation_reason_filter():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(ValueError, match="unsupported escalation_reason"):
        list_service_management_cases(
            store,
            business_id="artemea",
            now=NOW,
            escalation_reason="manager_vibes",
        )


def test_list_service_management_cases_rejects_unknown_sort_by():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(ValueError, match="unsupported sort_by"):
        list_service_management_cases(
            store,
            business_id="artemea",
            now=NOW,
            sort_by="manager_vibes",
        )
