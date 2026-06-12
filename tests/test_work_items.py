from __future__ import annotations

from datetime import datetime, timezone
from typing import get_args

import sqlite3

from app.brain.operational_cases import OperationalCaseType, SQLiteOperationalCaseStore
from app.brain.semantics import CASE_FAMILY_METRICS
from app.brain.storage import init_schema
from app.brain.work_items import (
    allowed_priority_brackets,
    allowed_status_categories,
    allowed_work_item_facet_fields,
    allowed_work_item_query_sort_fields,
    case_priority_bracket,
    case_project_key,
    case_sla_status,
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
    now = datetime(2026, 5, 24, 9, tzinfo=timezone.utc)

    projection = case_work_item_projection(case, now=now)

    assert projection["case_id"] == case.case_id
    assert projection["work_item_id"] == f"ARTEMEA:{case.case_id}"
    assert projection["project_key"] == "ARTEMEA"
    assert projection["issue_type"] == "stockout_risk"
    assert projection["release_state"] == "promoted"
    assert projection["owner_visible"] is True
    assert projection["status"] == "open"
    assert projection["status_category"] == "to_do"
    assert projection["priority_score"] == 87
    assert projection["priority_bracket"] == "high"
    assert projection["sla_target_seconds"] == 2 * 60 * 60
    assert projection["due_at"] == "2026-05-24T10:00:00Z"
    assert projection["sla_status"] == "pending"
    assert projection["assignee_ref"] is None
    assert projection["evidence_snapshot_ids"] == [case.evidence_snapshots[0].snapshot_id]
    assert projection["evidence_snapshot_count"] == 1
    assert projection["evidence_source_count"] == 1
    assert projection["source_connectors"] == ["tiendanube"]
    assert projection["latest_evidence_at"] == "2026-05-24T08:00:00Z"
    assert projection["degraded"] is False
    assert projection["created_at"].endswith("Z")
    assert projection["updated_at"].endswith("Z")
    assert case_project_key(case) == "ARTEMEA"
    assert case_status_category(case) == "to_do"
    assert case_priority_bracket(case) == "high"
    assert case_sla_status(case, now=now) == "pending"
    assert case_sla_status(case, now=datetime(2026, 5, 24, 10, 1, tzinfo=timezone.utc)) == "breached"


def test_case_work_item_projection_marks_readiness_gated_cases_operator_only(tmp_path):
    db_path = tmp_path / "work-items-readiness-gated.sqlite3"
    case = _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            title="Conversaciones sin responder",
            run_id="run-readiness-gated-owner-visible",
        ),
    )

    projection = case_work_item_projection(case, now=datetime(2026, 5, 24, 9, tzinfo=timezone.utc))

    assert projection["release_state"] == "readiness_gated"
    assert projection["owner_visible"] is False


def test_case_work_item_projection_exposes_evidence_lineage(tmp_path):
    db_path = tmp_path / "work-item-evidence-lineage.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-evidence-lineage", priority=87))
    first_snapshot_id = case.evidence_snapshots[0].snapshot_id
    later_snapshot = case.evidence_snapshots[0].model_copy(
        update={
            "snapshot_id": "snapshot-later-evidence",
            "snapshot_key": "run-evidence-lineage-google/evidence://artemea/run-evidence-lineage-google/stockout_risk/stockout_risk/business/monitored",
            "captured_at": datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
            "run_id": "run-evidence-lineage-google",
            "artifact_ref": "ledger://runs/run-evidence-lineage-google/daily-report",
            "evidence_ref": "evidence://artemea/run-evidence-lineage-google/stockout_risk",
            "source": "google_sheets",
            "source_label": "Google Sheets",
            "summary": "Stock snapshot from Google Sheets.",
        }
    )

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    case = store.attach_evidence(
        case.case_id,
        snapshots=[later_snapshot],
        run_id="run-evidence-lineage-google",
        artifact_ref="ledger://runs/run-evidence-lineage-google/daily-report",
        summary="Attached Google Sheets evidence.",
    )
    conn.close()

    projection = case_work_item_projection(case, now=datetime(2026, 5, 24, 9, tzinfo=timezone.utc))

    assert projection["evidence_snapshot_ids"] == [first_snapshot_id, "snapshot-later-evidence"]
    assert projection["evidence_snapshot_count"] == 2
    assert projection["evidence_source_count"] == 2
    assert projection["source_connectors"] == ["google_sheets", "tiendanube"]
    assert projection["latest_evidence_at"] == "2026-05-24T09:30:00Z"


def test_issue_type_definitions_expose_release_state_from_semantic_registry():
    definitions = {definition["case_type"]: definition for definition in operational_case_issue_type_definitions()}

    assert case_type_release_state("stockout_risk") == "promoted"
    assert case_type_release_state("unanswered_conversations") == "readiness_gated"
    assert case_type_release_state("channel_mix_shift") == "deferred"
    assert definitions["stockout_risk"] == {
        "issue_type": "stockout_risk",
        "case_type": "stockout_risk",
        "scheme_id": "d2c-default-case-types",
        "release_state": "promoted",
    }
    assert definitions["unanswered_conversations"] == {
        "issue_type": "unanswered_conversations",
        "case_type": "unanswered_conversations",
        "scheme_id": "d2c-default-case-types",
        "release_state": "readiness_gated",
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

    readiness_gated_case_types = {
        definition["case_type"]
        for definition in definitions.values()
        if definition["release_state"] == "readiness_gated"
    }

    assert promoted_case_types == {"sales_drop", "stockout_risk", "data_stale"}
    assert readiness_gated_case_types == {
        "fulfillment_backlog",
        "spend_without_orders",
        "unanswered_conversations",
    }
    assert promoted_case_types | readiness_gated_case_types == set(CASE_FAMILY_METRICS)


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
    assert workflow["manual_transitions"] == workflow["transitions"]
    assert workflow["system_transitions"]["open"] == []
    assert workflow["system_transitions"]["resolved"] == ["open"]
    assert workflow["system_transitions"]["dismissed"] == ["open"]
    assert status_by_key["resolved"]["system_transitions"] == ["open"]
    assert status_by_key["dismissed"]["system_transitions"] == ["open"]
    assert workflow["system_transition_events"] == [
        {
            "event_type": "case_reopened",
            "actor_type": "system",
            "from_status": "dismissed",
            "to_status": "open",
        },
        {
            "event_type": "case_reopened",
            "actor_type": "system",
            "from_status": "resolved",
            "to_status": "open",
        },
    ]


def test_query_field_registry_is_canonical_work_item_semantics():
    fields = {definition["field"]: definition for definition in work_item_query_field_definitions()}

    assert "business_id" not in fields
    assert fields["project"] == {
        "field": "project",
        "value_type": "string",
        "allowed_values": None,
        "allowed_operators": ["!=", "=", "IN"],
        "sortable": False,
        "facetable": True,
    }
    assert fields["issue_type"]["allowed_values"] == sorted(get_args(OperationalCaseType))
    assert fields["release_state"] == {
        "field": "release_state",
        "value_type": "enum",
        "allowed_values": ["deferred", "internal_only", "promoted", "readiness_gated"],
        "allowed_operators": ["!=", "=", "IN"],
        "sortable": False,
        "facetable": True,
    }
    assert fields["owner_visible"] == {
        "field": "owner_visible",
        "value_type": "bool",
        "allowed_values": None,
        "allowed_operators": ["!=", "="],
        "sortable": False,
        "facetable": True,
    }
    assert fields["status_category"]["allowed_values"] == sorted(allowed_status_categories())
    assert fields["assignee_ref"]["value_type"] == "string"
    assert fields["priority_score"] == {
        "field": "priority_score",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert fields["sla_target_seconds"] == {
        "field": "sla_target_seconds",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert fields["due_at"] == {
        "field": "due_at",
        "value_type": "datetime",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert fields["sla_status"] == {
        "field": "sla_status",
        "value_type": "enum",
        "allowed_values": ["breached", "met", "not_applicable", "not_configured", "pending"],
        "allowed_operators": ["!=", "=", "IN"],
        "sortable": False,
        "facetable": True,
    }
    assert fields["latest_evidence_at"] == {
        "field": "latest_evidence_at",
        "value_type": "datetime",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert fields["evidence_snapshot_count"] == {
        "field": "evidence_snapshot_count",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert fields["evidence_source_count"] == {
        "field": "evidence_source_count",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }

    priority_spec = work_item_query_field_spec("priority_score")
    assert priority_spec.value_type == "int"
    assert priority_spec.allowed_operators == frozenset({"=", "!=", ">", ">=", "<", "<="})
    assert allowed_work_item_query_sort_fields() == {
        "due_at",
        "evidence_snapshot_count",
        "evidence_source_count",
        "latest_evidence_at",
        "opened_at",
        "priority_score",
        "sla_target_seconds",
        "updated_at",
    }
    assert allowed_work_item_facet_fields() == {
        "assignee_ref",
        "case_type",
        "degraded",
        "entity.kind",
        "issue_type",
        "priority_bracket",
        "project",
        "release_state",
        "owner_visible",
        "severity",
        "sla_status",
        "source_connector",
        "status",
        "status_category",
    }
