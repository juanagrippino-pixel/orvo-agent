from __future__ import annotations

from typing import get_args

import sqlite3
from datetime import datetime, timezone

from app.brain.operational_cases import OperationalCaseType, SQLiteOperationalCaseStore
from app.brain.semantics import CASE_FAMILY_METRICS
from app.brain.storage import init_schema
from app.brain.work_items import (
    allowed_priority_brackets,
    allowed_status_categories,
    allowed_work_item_query_sort_fields,
    case_available_operator_transitions,
    case_priority_bracket,
    case_project_key,
    case_status_category,
    case_type_release_state,
    case_work_item_projection,
    operational_case_issue_type_definitions,
    operational_case_priority_definitions,
    operational_case_status_definitions,
    operational_case_workflow_definition,
    priority_bracket_for_score,
    project_key_for_business,
    project_projection,
    work_item_query_field_definitions,
    work_item_query_field_spec,
)
from tests.test_internal_operator_api import _case_detection, _seed_case


def test_project_projection_derives_stable_project_key_from_business_scope():
    assert project_key_for_business("artemea") == "ARTEMEA"
    assert project_key_for_business("demo store 01") == "DEMO_STORE_01"

    project = project_projection("artemea")

    assert project == {
        "project_id": "business:artemea",
        "business_id": "artemea",
        "project_key": "ARTEMEA",
        "display_name": "artemea",
        "case_type_scheme_id": "d2c-default-case-types",
        "workflow_scheme_id": "operational-case-default-workflow",
    }


def test_project_key_for_business_avoids_truncation_collisions():
    first = project_key_for_business("north buenos aires demo store warehouse alpha")
    second = project_key_for_business("north buenos aires demo store warehouse beta")

    assert first != second
    assert len(first) <= 32
    assert len(second) <= 32
    assert first.startswith("NORTH_BUENOS_AIRES_DEMO_")
    assert second.startswith("NORTH_BUENOS_AIRES_DEMO_")
    assert project_key_for_business("north buenos aires demo store warehouse alpha") == first


def test_case_work_item_projection_wraps_operational_case_without_changing_source_of_truth(tmp_path):
    db_path = tmp_path / "work-items.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item", priority=87))

    projection = case_work_item_projection(case)

    assert projection["case_id"] == case.case_id
    assert projection["work_item_id"] == f"ARTEMEA:{case.case_id}"
    assert projection["project_key"] == "ARTEMEA"
    assert projection["issue_type"] == "stockout_risk"
    assert projection["status"] == "open"
    assert projection["status_category"] == "to_do"
    assert projection["priority_score"] == 87
    assert projection["priority_bracket"] == "high"
    assert projection["assignee_ref"] is None
    assert projection["assigned_at"] is None
    assert projection["latest_run_id"] == "run-work-item"
    assert projection["source_run_ids"] == ["run-work-item"]
    assert projection["source_connectors"] == ["tiendanube"]
    assert projection["latest_evidence_at"] == "2026-05-24T08:00:00Z"
    assert projection["evidence_snapshot_count"] == 1
    assert projection["evidence_snapshot_ids"] == [case.evidence_snapshots[0].snapshot_id]
    assert projection["created_at"].endswith("Z")
    assert projection["updated_at"].endswith("Z")
    assert projection["comment_count"] == 0
    assert projection["last_commented_at"] is None
    assert case_project_key(case) == "ARTEMEA"
    assert case_status_category(case) == "to_do"
    assert case_priority_bracket(case) == "high"


def test_issue_type_definitions_expose_release_state_from_semantic_registry():
    definitions = {definition["case_type"]: definition for definition in operational_case_issue_type_definitions()}

    assert case_type_release_state("stockout_risk") == "promoted"
    assert case_type_release_state("channel_mix_shift") == "deferred"
    assert definitions["stockout_risk"]["release_state"] == "promoted"
    assert definitions["channel_mix_shift"]["release_state"] == "deferred"
    promoted_case_types = {
        definition["case_type"]
        for definition in definitions.values()
        if definition["release_state"] == "promoted"
    }

    assert promoted_case_types == set(CASE_FAMILY_METRICS)


def test_case_work_item_projection_exposes_operator_transition_boundaries(tmp_path):
    db_path = tmp_path / "work-item-transition-boundaries.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-transitions"))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    resolved = store.transition_case(
        store.transition_case(
            case.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator:ana",
        ).case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="Restocked",
    )
    conn.close()

    open_projection = case_work_item_projection(case)
    resolved_projection = case_work_item_projection(resolved)

    assert case_available_operator_transitions(case) == ["acknowledged", "dismissed", "in_progress"]
    assert open_projection["available_operator_transitions"] == ["acknowledged", "dismissed", "in_progress"]
    assert open_projection["system_reopen_transition"] is None
    assert resolved_projection["available_operator_transitions"] == []
    assert resolved_projection["system_reopen_transition"] == "open"


def test_priority_definitions_are_canonical_work_item_semantics(tmp_path):
    db_path = tmp_path / "priority-definition.sqlite3"
    low_case = _seed_case(db_path, _case_detection(run_id="run-priority-low", priority=49))
    medium_case = _seed_case(db_path, _case_detection(run_id="run-priority-medium", priority=50))
    high_case = _seed_case(db_path, _case_detection(run_id="run-priority-high", priority=80))

    assert priority_bracket_for_score(0) == "low"
    assert priority_bracket_for_score(49) == "low"
    assert priority_bracket_for_score(50) == "medium"
    assert priority_bracket_for_score(79) == "medium"
    assert priority_bracket_for_score(80) == "high"
    assert priority_bracket_for_score(100) == "high"
    assert case_priority_bracket(low_case) == "low"
    assert case_priority_bracket(medium_case) == "medium"
    assert case_priority_bracket(high_case) == "high"

    definitions = operational_case_priority_definitions()

    assert allowed_priority_brackets() == {"low", "medium", "high"}
    assert definitions == [
        {
            "bracket": "low",
            "label": "Low",
            "lower_bound": 0,
            "upper_bound": 49,
        },
        {
            "bracket": "medium",
            "label": "Medium",
            "lower_bound": 50,
            "upper_bound": 79,
        },
        {
            "bracket": "high",
            "label": "High",
            "lower_bound": 80,
            "upper_bound": 100,
        },
    ]


def test_case_work_item_projection_exposes_canonical_priority_brackets(tmp_path):
    db_path = tmp_path / "work-item-priority-brackets.sqlite3"

    low = _seed_case(db_path, _case_detection(run_id="run-low", priority=49, dedupe_suffix="low"))
    medium = _seed_case(db_path, _case_detection(run_id="run-medium", priority=50, dedupe_suffix="medium"))
    high = _seed_case(db_path, _case_detection(run_id="run-high", priority=80, dedupe_suffix="high"))

    assert case_work_item_projection(low)["priority_bracket"] == "low"
    assert case_work_item_projection(medium)["priority_bracket"] == "medium"
    assert case_work_item_projection(high)["priority_bracket"] == "high"


def test_case_work_item_projection_exposes_assignment_timestamp(tmp_path):
    db_path = tmp_path / "work-item-assignment-clock.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-assignment"))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    assigned = store.assign_case(
        case.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        assignee_ref="operator:lucia",
        assigned_at=datetime(2026, 6, 4, 15, 30, tzinfo=timezone.utc),
    )
    conn.close()

    projection = case_work_item_projection(assigned)

    assert projection["assignee_ref"] == "operator:lucia"
    assert projection["assigned_at"] == "2026-06-04T15:30:00Z"


def test_case_work_item_projection_summarizes_comments_without_copying_bodies(tmp_path):
    db_path = tmp_path / "work-item-comments.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-comments"))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    first_comment_at = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    second_comment_at = datetime(2026, 6, 3, 12, 5, tzinfo=timezone.utc)

    store.add_comment(
        case.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        comment="Initial follow-up note",
        commented_at=first_comment_at,
    )
    commented = store.add_comment(
        case.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        comment="Private owner context should stay in timeline, not queue summary",
        commented_at=second_comment_at,
    )
    conn.close()

    projection = case_work_item_projection(commented)

    assert projection["comment_count"] == 2
    assert projection["last_commented_at"] == "2026-06-03T12:05:00Z"
    assert "Initial follow-up note" not in projection.values()
    assert "Private owner context" not in str(projection)


def test_case_work_item_projection_exposes_acknowledgment_sla_clock(tmp_path):
    db_path = tmp_path / "work-item-sla-clock.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-sla", priority=87))

    on_time_projection = case_work_item_projection(case, as_of=datetime(2026, 5, 24, 8, 30, tzinfo=timezone.utc))
    overdue_projection = case_work_item_projection(case, as_of=datetime(2026, 5, 24, 9, 1, tzinfo=timezone.utc))

    assert on_time_projection["acknowledgment_sla_minutes"] == 60
    assert on_time_projection["acknowledgment_due_at"] == "2026-05-24T09:00:00Z"
    assert on_time_projection["acknowledged_at"] is None
    assert on_time_projection["acknowledgment_sla_breached"] is False
    assert on_time_projection["acknowledgment_sla_status"] == "pending"
    assert overdue_projection["acknowledgment_sla_breached"] is True
    assert overdue_projection["acknowledgment_sla_status"] == "breached"

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    acknowledged = store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=datetime(2026, 5, 24, 9, 15, tzinfo=timezone.utc),
    )
    conn.close()

    acknowledged_projection = case_work_item_projection(
        acknowledged,
        as_of=datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
    )

    assert acknowledged_projection["acknowledged_at"] == "2026-05-24T09:15:00Z"
    assert acknowledged_projection["acknowledgment_sla_breached"] is True
    assert acknowledged_projection["acknowledgment_sla_status"] == "breached"


def test_acknowledgment_sla_stops_at_terminal_status_when_never_acknowledged(tmp_path):
    """A done case should not become artificially overdue after closure.

    Open -> dismissed is a valid operator transition. If the case is dismissed
    before the first-ack SLA due time, WorkItem projections must evaluate the
    SLA at dismissed_at rather than at the later dashboard request time.
    """

    db_path = tmp_path / "work-item-sla-terminal-clock.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-terminal-sla", priority=87))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    dismissed_on_time = store.transition_case(
        case.case_id,
        status="dismissed",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="Duplicate alert",
        transitioned_at=datetime(2026, 5, 24, 8, 30, tzinfo=timezone.utc),
    )
    late_case = store.upsert_detection(
        _case_detection(
            run_id="run-work-item-terminal-sla-late",
            priority=87,
            dedupe_suffix="stockout_risk/business/late-terminal/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "late-terminal", "label": "Late terminal"},
        ),
        detected_at=datetime(2026, 5, 24, 8, 0, tzinfo=timezone.utc),
    )
    dismissed_late = store.transition_case(
        late_case.case_id,
        status="dismissed",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="Closed after SLA",
        transitioned_at=datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
    )
    conn.close()

    on_time_projection = case_work_item_projection(
        dismissed_on_time,
        as_of=datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc),
    )
    late_projection = case_work_item_projection(
        dismissed_late,
        as_of=datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc),
    )

    assert on_time_projection["status"] == "dismissed"
    assert on_time_projection["acknowledged_at"] is None
    assert on_time_projection["acknowledgment_due_at"] == "2026-05-24T09:00:00Z"
    assert on_time_projection["acknowledgment_sla_breached"] is False
    assert on_time_projection["acknowledgment_sla_status"] == "met"
    assert late_projection["acknowledgment_sla_breached"] is True
    assert late_projection["acknowledgment_sla_status"] == "breached"


def test_reopened_case_work_item_sla_clock_restarts_from_recurrence_event(tmp_path):
    """Recurring evidence should make a done case actionable with a fresh SLA clock."""

    db_path = tmp_path / "work-item-reopened-sla-clock.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-reopen-sla", priority=87))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    acknowledged = store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=datetime(2026, 5, 24, 8, 30, tzinfo=timezone.utc),
    )
    store.transition_case(
        acknowledged.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="Restocked",
        transitioned_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
    )
    reopened = store.upsert_detection(
        _case_detection(run_id="run-work-item-reopen-sla-2", priority=87),
        detected_at=datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc),
    )
    conn.close()

    projection = case_work_item_projection(
        reopened,
        as_of=datetime(2026, 5, 26, 8, 30, tzinfo=timezone.utc),
    )

    assert projection["status"] == "open"
    assert projection["sla_started_at"] == "2026-05-26T08:00:00Z"
    assert projection["acknowledged_at"] is None
    assert projection["resolved_at"] is None
    assert projection["acknowledgment_due_at"] == "2026-05-26T09:00:00Z"
    assert projection["acknowledgment_sla_status"] == "pending"
    assert projection["resolution_due_at"] == "2026-05-27T08:00:00Z"
    assert projection["resolution_sla_status"] == "pending"


def test_case_work_item_projection_exposes_resolution_sla_clock(tmp_path):
    db_path = tmp_path / "work-item-resolution-sla-clock.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-resolution-sla", priority=87))

    on_time_projection = case_work_item_projection(case, as_of=datetime(2026, 5, 25, 7, 59, tzinfo=timezone.utc))
    overdue_projection = case_work_item_projection(case, as_of=datetime(2026, 5, 25, 8, 1, tzinfo=timezone.utc))

    assert on_time_projection["resolution_sla_minutes"] == 1440
    assert on_time_projection["resolution_due_at"] == "2026-05-25T08:00:00Z"
    assert on_time_projection["resolved_at"] is None
    assert on_time_projection["resolution_sla_breached"] is False
    assert on_time_projection["resolution_sla_status"] == "pending"
    assert overdue_projection["resolution_sla_breached"] is True
    assert overdue_projection["resolution_sla_status"] == "breached"

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    acknowledged = store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
    )
    resolved_on_time = store.transition_case(
        acknowledged.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="Restocked before resolution SLA",
        transitioned_at=datetime(2026, 5, 25, 7, 30, tzinfo=timezone.utc),
    )
    conn.close()

    resolved_projection = case_work_item_projection(
        resolved_on_time,
        as_of=datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc),
    )

    assert resolved_projection["status"] == "resolved"
    assert resolved_projection["resolved_at"] == "2026-05-25T07:30:00Z"
    assert resolved_projection["resolution_due_at"] == "2026-05-25T08:00:00Z"
    assert resolved_projection["resolution_sla_breached"] is False
    assert resolved_projection["resolution_sla_status"] == "met"


def test_resolution_sla_stops_at_terminal_status_when_closed_late(tmp_path):
    db_path = tmp_path / "work-item-resolution-sla-terminal-clock.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-work-item-late-resolution-sla", priority=50))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    acknowledged = store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
    )
    resolved_late = store.transition_case(
        acknowledged.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="Fixed after target",
        transitioned_at=datetime(2026, 5, 27, 9, 30, tzinfo=timezone.utc),
    )
    conn.close()

    projection = case_work_item_projection(
        resolved_late,
        as_of=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )

    assert projection["priority_bracket"] == "medium"
    assert projection["resolution_sla_minutes"] == 4320
    assert projection["resolution_due_at"] == "2026-05-27T08:00:00Z"
    assert projection["resolved_at"] == "2026-05-27T09:30:00Z"
    assert projection["resolution_sla_breached"] is True
    assert projection["resolution_sla_status"] == "breached"


def test_issue_type_definitions_expose_owner_visibility_and_metric_gates():
    definitions = {definition["issue_type"]: definition for definition in operational_case_issue_type_definitions()}

    stockout = definitions["stockout_risk"]
    channel_mix = definitions["channel_mix_shift"]

    assert stockout["case_type"] == "stockout_risk"
    assert stockout["scheme_id"] == "d2c-default-case-types"
    assert stockout["detectable"] is True
    assert stockout["owner_facing"] is True
    assert stockout["visibility"] == "owner_facing"
    assert stockout["required_metric_keys"] == [
        "commerce.inventory.available_units",
        "commerce.orders.count",
        "runtime.freshness.age_seconds",
    ]

    assert channel_mix["detectable"] is False
    assert channel_mix["owner_facing"] is False
    assert channel_mix["visibility"] == "internal_deferred"
    assert channel_mix["required_metric_keys"] == []


def test_status_and_workflow_definitions_expose_current_transition_table(tmp_path):
    db_path = tmp_path / "workflow-definition.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-status"))
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    acknowledged = store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
    )
    in_progress = store.transition_case(
        acknowledged.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator:juan",
    )
    resolved = store.transition_case(
        in_progress.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:juan",
        reason="fixture complete",
    )
    conn.close()

    status_by_key = {definition["status"]: definition for definition in operational_case_status_definitions()}
    workflow = operational_case_workflow_definition()

    assert case_status_category(acknowledged) == "in_progress"
    assert case_status_category(in_progress) == "in_progress"
    assert case_status_category(resolved) == "done"
    assert status_by_key["open"]["status_category"] == "to_do"
    assert status_by_key["open"]["terminal"] is False
    assert status_by_key["resolved"]["status_category"] == "done"
    assert status_by_key["resolved"]["terminal"] is True
    assert status_by_key["dismissed"]["terminal"] is True
    assert "acknowledged" in workflow["transitions"]["open"]
    assert "resolved" in workflow["transitions"]["in_progress"]
    assert workflow["transitions"]["resolved"] == []
    assert status_by_key["resolved"]["system_reopen_transition"] == "open"
    assert status_by_key["dismissed"]["system_reopen_transition"] == "open"
    assert status_by_key["open"]["system_reopen_transition"] is None
    assert workflow["system_reopen_transitions"] == {"resolved": "open", "dismissed": "open"}
    assert workflow["transition_actor_boundaries"] == {
        "operator": workflow["transitions"],
        "system_recurrence": {"resolved": ["open"], "dismissed": ["open"]},
    }


def test_query_field_registry_is_canonical_work_item_semantics():
    fields = {definition["field"]: definition for definition in work_item_query_field_definitions()}

    assert "business_id" not in fields
    assert fields["project"] == {
        "field": "project",
        "value_type": "string",
        "allowed_values": None,
        "allowed_operators": ["!=", "=", "IN"],
        "sortable": False,
    }
    assert fields["issue_type"]["allowed_values"] == sorted(get_args(OperationalCaseType))
    assert fields["status_category"]["allowed_values"] == sorted(allowed_status_categories())
    assert fields["assignee_ref"]["value_type"] == "string"
    assert fields["priority_score"] == {
        "field": "priority_score",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
    }

    assert fields["acknowledgment_due_at"] == {
        "field": "acknowledgment_due_at",
        "value_type": "datetime",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
    }
    assert fields["resolution_due_at"] == {
        "field": "resolution_due_at",
        "value_type": "datetime",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
    }
    assert fields["comment_count"] == {
        "field": "comment_count",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
    }
    assert fields["last_commented_at"] == {
        "field": "last_commented_at",
        "value_type": "datetime",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
    }

    priority_spec = work_item_query_field_spec("priority_score")
    assert priority_spec.value_type == "int"
    assert priority_spec.allowed_operators == frozenset({"=", "!=", ">", ">=", "<", "<="})
    assert allowed_work_item_query_sort_fields() == {
        "acknowledgment_due_at",
        "comment_count",
        "last_commented_at",
        "opened_at",
        "priority_score",
        "resolution_due_at",
        "updated_at",
    }
