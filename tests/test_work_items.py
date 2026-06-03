from __future__ import annotations

from typing import get_args

import sqlite3

from app.brain.operational_cases import OperationalCaseType, SQLiteOperationalCaseStore
from app.brain.semantics import CASE_FAMILY_METRICS
from app.brain.storage import init_schema
from app.brain.work_items import (
    allowed_priority_brackets,
    allowed_status_categories,
    allowed_work_item_query_sort_fields,
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
    assert projection["created_at"].endswith("Z")
    assert projection["updated_at"].endswith("Z")
    assert case_project_key(case) == "ARTEMEA"
    assert case_status_category(case) == "to_do"
    assert case_priority_bracket(case) == "high"


def test_issue_type_definitions_expose_release_state_from_semantic_registry():
    definitions = {definition["case_type"]: definition for definition in operational_case_issue_type_definitions()}

    assert case_type_release_state("stockout_risk") == "promoted"
    assert case_type_release_state("channel_mix_shift") == "deferred"
    assert definitions["stockout_risk"] == {
        "issue_type": "stockout_risk",
        "case_type": "stockout_risk",
        "scheme_id": "d2c-default-case-types",
        "release_state": "promoted",
    }
    assert definitions["channel_mix_shift"] == {
        "issue_type": "channel_mix_shift",
        "case_type": "channel_mix_shift",
        "scheme_id": "d2c-default-case-types",
        "release_state": "deferred",
    }
    promoted_case_types = {
        definition["case_type"]
        for definition in definitions.values()
        if definition["release_state"] == "promoted"
    }

    assert promoted_case_types == set(CASE_FAMILY_METRICS)


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

    priority_spec = work_item_query_field_spec("priority_score")
    assert priority_spec.value_type == "int"
    assert priority_spec.allowed_operators == frozenset({"=", "!=", ">", ">=", "<", "<="})
    assert allowed_work_item_query_sort_fields() == {"opened_at", "priority_score", "updated_at"}
