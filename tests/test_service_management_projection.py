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
    assert by_id[waiting_owner.case_id]["owner_status"]["status_category"] == "waiting"
    assert by_id[waiting_external.case_id]["owner_status"]["code"] == "waiting_external"
    assert by_id[waiting_external.case_id]["owner_status"]["status_category"] == "waiting"
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
        "breached": True,
        "completed": False,
        "started_at": "2026-05-24T10:30:00Z",
        "stopped_at": None,
        "due_at": "2026-05-24T11:30:00Z",
    }
    assert responded_item["sla"]["first_response"]["policy_key"] == "first_response_warning_240m"
    assert responded_item["sla"]["first_response"]["elapsed_seconds"] == 3600
    assert responded_item["sla"]["first_response"]["remaining_seconds"] == 10800
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
