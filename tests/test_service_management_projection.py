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
    run_id: str = "run-sm",
    metadata: dict | None = None,
) -> OperationalCaseDetection:
    suffix = dedupe_suffix or f"{case_type}/business/monitored/inventory/daily"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{suffix}",
        title=f"Caso operativo token=super-secret {run_id}",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[f"evidence://tiendanube/{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata=metadata or {},
    )


def test_service_management_projection_maps_record_types_waiting_statuses_and_counts():
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
    request_waiting_owner = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="conversations/channel/whatsapp/support/daily",
            severity="warning",
            priority=65,
            run_id="run-request-owner",
            metadata={"waiting_on": "owner", "waiting_since": (NOW - timedelta(hours=3)).isoformat()},
        ),
        detected_at=NOW - timedelta(hours=3),
    )
    change_override = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="change/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=60,
            run_id="run-change",
            metadata={"service_record_type": "change"},
        ),
        detected_at=NOW - timedelta(hours=4),
    )

    store.transition_case(
        request_waiting_owner.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2, minutes=30),
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
    assert by_id[request_waiting_owner.case_id]["service_record_type"]["code"] == "service_request"
    assert by_id[request_waiting_owner.case_id]["owner_status"]["code"] == "waiting_owner"
    assert by_id[request_waiting_owner.case_id]["owner_status"]["status_category"] == "in_progress"
    assert by_id[change_override.case_id]["service_record_type"]["code"] == "change"
    assert {
        item["owner_status"]["status_category"] for item in result["service_cases"]
    } <= {"to_do", "in_progress", "done"}
    assert result["by_service_record_type"] == {
        "incident": 1,
        "problem": 1,
        "service_request": 1,
        "change": 1,
    }
    assert result["by_owner_status"] == {
        "new": 3,
        "waiting_owner": 1,
    }


def test_service_management_projection_computes_sla_and_escalation_reasons_deterministically():
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
    acknowledged = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=75,
            run_id="run-ack",
        ),
        detected_at=NOW - timedelta(hours=3),
    )
    store.transition_case(
        acknowledged.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2),
    )

    overdue_item = service_management_case_item(overdue, now=NOW)
    acknowledged_item = service_management_case_item(store.get_case(acknowledged.case_id), now=NOW)  # type: ignore[arg-type]

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
    assert overdue_item["sla_status"]["code"] == "breached"
    assert {reason["code"] for reason in overdue_item["escalation_reasons"]} == {
        "critical_case_unacknowledged",
        "first_response_sla_breached",
    }
    assert acknowledged_item["sla"]["first_response"]["completed"] is True
    assert acknowledged_item["sla"]["first_response"]["stopped_at"] == "2026-05-24T10:00:00Z"
    assert acknowledged_item["sla_status"]["code"] == "on_track"
    assert acknowledged_item["escalation_reasons"] == []
    assert acknowledged_item["needs_escalation"] is False


def test_service_management_projection_pauses_resolution_sla_while_waiting_external():
    store = InMemoryOperationalCaseStore()
    waiting_external = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="paused-stale/connector/tiendanube/freshness/daily",
            severity="warning",
            priority=80,
            run_id="run-paused-waiting-external",
            metadata={
                "waiting_on": "external",
                "waiting_since": (NOW - timedelta(hours=5)).isoformat(),
            },
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

    item = service_management_case_item(store.get_case(waiting_external.case_id), now=NOW)  # type: ignore[arg-type]

    assert item["owner_status"]["code"] == "waiting_external"
    assert item["sla"]["resolution"]["paused"] is True
    assert item["sla"]["resolution"]["paused_at"] == "2026-05-24T07:00:00Z"
    assert item["sla"]["resolution"]["pause_reason"] == "waiting_external"
    assert item["sla_status"]["code"] == "paused"
    assert item["needs_escalation"] is True
    assert {"code": "waiting_external", "label_es": "Bloqueado por un tercero", "source": "owner_status"} in item[
        "escalation_reasons"
    ]


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


def test_list_service_management_cases_filters_by_sla_status_and_sorts_by_sla_urgency():
    store = InMemoryOperationalCaseStore()
    on_track = store.upsert_detection(
        _detection(run_id="run-on-track", severity="warning", priority=90),
        detected_at=NOW - timedelta(minutes=5),
    )
    breached = store.upsert_detection(
        _detection(
            run_id="run-breached",
            severity="critical",
            priority=95,
            dedupe_suffix="breached-stockout/business/monitored/inventory/daily",
        ),
        detected_at=NOW - timedelta(hours=2),
    )

    result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=10,
        sla_status="breached",
        sort_by="sla_urgency",
    )

    assert result["filters"] == {"sla_status": "breached"}
    assert result["total"] == 1
    assert [item["case_id"] for item in result["service_cases"]] == [breached.case_id]
    assert result["by_sla_status"]["breached"] == 1
    assert result["by_sla_status"]["on_track"] == 1

    urgency_result = list_service_management_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit=10,
        sort_by="sla_urgency",
    )
    assert [item["case_id"] for item in urgency_result["service_cases"]] == [breached.case_id, on_track.case_id]
