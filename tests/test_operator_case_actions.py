from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    SQLiteOperationalCaseStore,
)
from app.brain.operator_api import OperatorAPIError, apply_case_action
from app.brain.storage import init_schema

AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator@example.com",
    "X-Request-ID": "req-comment-test",
}


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 24, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    init_schema(connection)
    yield connection
    connection.close()


def case_detection(*, business_id: str = "artemea", run_id: str = "run-comment-1") -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type="stockout_risk",
        dedupe_key=f"{business_id}/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity="critical",
        priority_score=100,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/stockout_risk"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"source": "test"},
    )


def seed_sqlite_case(db_path, detection: OperationalCaseDetection | None = None):
    connection = sqlite3.connect(db_path)
    init_schema(connection)
    store = SQLiteOperationalCaseStore(connection)
    case = store.upsert_detection(detection or case_detection(), detected_at=utc(8))
    connection.close()
    return case


def client(monkeypatch, tmp_path):
    db_path = tmp_path / "operator-comments.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    from server import app

    return app.test_client(), db_path


def assert_no_raw_comment_secret(serialized: str) -> None:
    assert "raw_comment_secret" not in serialized
    assert "raw_comment_meta_secret" not in serialized


def assert_no_raw_actor_secret(serialized: str) -> None:
    assert "raw_actor_secret" not in serialized


def test_timeline_actor_ref_is_redacted_for_comments_and_status_actions_before_persistence(conn):
    store = SQLiteOperationalCaseStore(conn)
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    commented = store.add_comment(
        opened.case_id,
        actor_type="operator",
        actor_ref="operator access_token=raw_actor_secret",
        comment="Checked supplier",
        commented_at=utc(9),
    )
    assert commented.timeline[-1].actor_ref == "operator access_token=[REDACTED]"
    assert_no_raw_actor_secret(commented.model_dump_json())

    acknowledged = store.transition_case(
        opened.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator access_token=raw_actor_secret",
        reason="Acknowledged",
        transitioned_at=utc(10),
    )
    assert acknowledged.timeline[-1].actor_ref == "operator access_token=[REDACTED]"
    assert_no_raw_actor_secret(acknowledged.model_dump_json())

    reloaded = SQLiteOperationalCaseStore(conn).get_case(opened.case_id)
    assert reloaded is not None
    assert reloaded.timeline[-2].actor_ref == "operator access_token=[REDACTED]"
    assert reloaded.timeline[-1].actor_ref == "operator access_token=[REDACTED]"
    assert_no_raw_actor_secret(reloaded.model_dump_json())


def test_store_add_comment_appends_operator_timeline_event_preserves_status_redacts_and_persists(conn):
    sqlite_store = SQLiteOperationalCaseStore(conn)
    opened = sqlite_store.upsert_detection(case_detection(), detected_at=utc(8))
    memory_store = InMemoryOperationalCaseStore()
    memory_opened = memory_store.upsert_detection(case_detection(run_id="run-memory"), detected_at=utc(8))

    memory_commented = memory_store.add_comment(
        memory_opened.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Investigating access_token=raw_comment_secret",
        metadata={"api_key": "raw_comment_meta_secret", "safe": "visible"},
        commented_at=utc(9),
    )
    sqlite_commented = sqlite_store.add_comment(
        opened.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Investigating access_token=raw_comment_secret",
        metadata={"api_key": "raw_comment_meta_secret", "safe": "visible"},
        commented_at=utc(9),
    )
    reloaded = SQLiteOperationalCaseStore(conn).get_case(opened.case_id)

    for commented in (memory_commented, sqlite_commented, reloaded):
        assert commented is not None
        assert commented.status == "open"
        assert commented.updated_at == utc(9)
        assert commented.acknowledged_at is None
        assert commented.resolved_at is None
        event = commented.timeline[-1]
        assert event.event_type == "operator_comment"
        assert event.actor_type == "operator"
        assert event.actor_ref == "operator@example.com"
        assert event.case_id == commented.case_id
        assert event.created_at == utc(9)
        assert "Investigating" in event.summary
        assert event.metadata["safe"] == "visible"
        assert_no_raw_comment_secret(commented.model_dump_json())


def test_apply_case_action_add_comment_returns_case_detail_with_redacted_comment_and_no_status_change():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    result = apply_case_action(
        store,
        business_id="artemea",
        case_id=opened.case_id,
        action_key="add_comment",
        actor_ref="operator@example.com",
        comment="Checked supplier token=raw_comment_secret",
        metadata={"access_token": "raw_comment_meta_secret", "safe": "visible"},
    )

    detail = result["case"]
    assert detail["case_id"] == opened.case_id
    assert detail["status"] == "open"
    assert detail["acknowledged_at"] is None
    assert detail["resolved_at"] is None
    event = detail["timeline"][-1]
    assert event["event_type"] == "operator_comment"
    assert event["actor_type"] == "operator"
    assert event["actor_ref"] == "operator@example.com"
    assert "Checked supplier" in event["summary"]
    assert event["metadata"]["safe"] == "visible"
    assert_no_raw_comment_secret(str(result))


def test_apply_case_action_add_comment_strips_actor_ref_before_persisting_timeline_event():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    result = apply_case_action(
        store,
        business_id="artemea",
        case_id=opened.case_id,
        action_key="add_comment",
        actor_ref="  operator@example.com  ",
        comment="Checked supplier",
    )

    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert result["case"]["timeline"][-1]["actor_ref"] == "operator@example.com"
    assert reloaded.timeline[-1].actor_ref == "operator@example.com"


@pytest.mark.parametrize("bad_comment", [None, "", "   ", 123, {"text": "hi"}])
def test_apply_case_action_add_comment_rejects_missing_blank_or_non_string_comment(bad_comment: Any):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    with pytest.raises(OperatorAPIError) as exc:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="add_comment",
            actor_ref="operator@example.com",
            comment=bad_comment,
        )

    assert exc.value.code == "invalid_comment"
    assert exc.value.status_code == 400
    assert len(store.get_case(opened.case_id).timeline) == len(opened.timeline)


@pytest.mark.parametrize(
    ("bad_actor", "expected_code"),
    [("   ", "missing_operator_actor"), (123, "invalid_operator_actor")],
)
def test_apply_case_action_add_comment_rejects_blank_or_non_string_actor_ref(bad_actor: Any, expected_code: str):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    with pytest.raises(OperatorAPIError) as exc:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="add_comment",
            actor_ref=bad_actor,
            comment="Looks good",
        )

    assert exc.value.code == expected_code
    assert exc.value.status_code == 400
    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert len(reloaded.timeline) == len(opened.timeline)


def test_store_assign_case_sets_assignee_timeline_event_preserves_status_redacts_and_persists(conn):
    sqlite_store = SQLiteOperationalCaseStore(conn)
    opened = sqlite_store.upsert_detection(case_detection(), detected_at=utc(8))
    memory_store = InMemoryOperationalCaseStore()
    memory_opened = memory_store.upsert_detection(case_detection(run_id="run-memory"), detected_at=utc(8))

    memory_assigned = memory_store.assign_case(
        memory_opened.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        assignee_ref="owner access_token=raw_assignee_secret",
        assigned_at=utc(9),
    )
    sqlite_assigned = sqlite_store.assign_case(
        opened.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        assignee_ref="owner access_token=raw_assignee_secret",
        assigned_at=utc(9),
    )
    reloaded = SQLiteOperationalCaseStore(conn).get_case(opened.case_id)

    for assigned in (memory_assigned, sqlite_assigned, reloaded):
        assert assigned is not None
        assert assigned.status == "open"
        assert assigned.assignee_ref == "owner access_token=[REDACTED]"
        assert assigned.assigned_at == utc(9)
        assert assigned.updated_at == utc(9)
        event = assigned.timeline[-1]
        assert event.event_type == "case_assigned"
        assert event.actor_type == "operator"
        assert event.actor_ref == "operator@example.com"
        assert event.case_id == assigned.case_id
        assert event.created_at == utc(9)
        assert event.metadata == {"assignee_ref": "owner access_token=[REDACTED]"}
        assert "raw_assignee_secret" not in assigned.model_dump_json()


def test_apply_case_action_assign_owner_updates_projection_and_keeps_lifecycle_status():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    result = apply_case_action(
        store,
        business_id="artemea",
        case_id=opened.case_id,
        action_key="assign_owner",
        actor_ref="operator@example.com",
        assignee_ref="  owner access_token=raw_assignee_secret  ",
    )

    detail = result["case"]
    assert detail["case_id"] == opened.case_id
    assert detail["status"] == "open"
    assert detail["assignee_ref"] == "owner access_token=[REDACTED]"
    assert detail["assigned_at"] is not None
    event = detail["timeline"][-1]
    assert event["event_type"] == "case_assigned"
    assert event["actor_type"] == "operator"
    assert event["actor_ref"] == "operator@example.com"
    assert event["metadata"] == {"assignee_ref": "owner access_token=[REDACTED]"}
    assert "raw_assignee_secret" not in str(result)


@pytest.mark.parametrize("bad_assignee", [None, "", "   ", 123, {"owner": "juan"}])
def test_apply_case_action_assign_owner_rejects_missing_blank_or_non_string_assignee_ref(bad_assignee: Any):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    with pytest.raises(OperatorAPIError) as exc:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="assign_owner",
            actor_ref="operator@example.com",
            assignee_ref=bad_assignee,
        )

    assert exc.value.code == "invalid_assignee_ref"
    assert exc.value.status_code == 400
    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert reloaded.assignee_ref is None
    assert len(reloaded.timeline) == len(opened.timeline)


@pytest.mark.parametrize("bad_assignee", ["", "   "])
def test_store_assign_case_rejects_blank_assignee_ref_without_mutation(bad_assignee: str):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    with pytest.raises(ValueError, match="assignee_ref must be non-empty"):
        store.assign_case(
            opened.case_id,
            actor_type="operator",
            actor_ref="operator@example.com",
            assignee_ref=bad_assignee,
            assigned_at=utc(9),
        )

    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert reloaded.assignee_ref is None
    assert reloaded.assigned_at is None
    assert len(reloaded.timeline) == len(opened.timeline)


@pytest.mark.parametrize("terminal_action", ["resolve_case", "dismiss_case"])
def test_apply_case_action_assign_owner_rejects_terminal_cases_without_mutation(terminal_action: str):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))
    terminal = apply_case_action(
        store,
        business_id="artemea",
        case_id=opened.case_id,
        action_key="dismiss_case" if terminal_action == "dismiss_case" else "acknowledge_case",
        actor_ref="operator@example.com",
        reason="No action needed" if terminal_action == "dismiss_case" else None,
    )["case"]
    if terminal_action == "resolve_case":
        terminal = apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="resolve_case",
            actor_ref="operator@example.com",
            reason="Recovered after owner follow-up",
        )["case"]

    with pytest.raises(OperatorAPIError) as exc:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="assign_owner",
            actor_ref="operator@example.com",
            assignee_ref="owner@example.com",
        )

    assert exc.value.code == "invalid_case_transition"
    assert exc.value.status_code == 409
    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert reloaded.status == terminal["status"]
    assert reloaded.assignee_ref is None
    assert reloaded.assigned_at is None
    assert len(reloaded.timeline) == len(terminal["timeline"])


def test_apply_case_action_mark_in_progress_and_dismiss_case_update_lifecycle_with_reason():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    in_progress = apply_case_action(
        store,
        business_id="artemea",
        case_id=opened.case_id,
        action_key="mark_in_progress",
        actor_ref="operator@example.com",
    )
    assert in_progress["case"]["status"] == "in_progress"
    assert in_progress["case"]["acknowledged_at"] is not None
    assert in_progress["case"]["timeline"][-1]["metadata"] == {
        "from_status": "open",
        "to_status": "in_progress",
    }

    dismissed = apply_case_action(
        store,
        business_id="artemea",
        case_id=opened.case_id,
        action_key="dismiss_case",
        actor_ref="operator@example.com",
        reason="False positive after physical stock count",
    )
    assert dismissed["case"]["status"] == "dismissed"
    assert dismissed["case"]["resolved_at"] is None
    assert dismissed["case"]["timeline"][-1]["summary"] == "False positive after physical stock count"


@pytest.mark.parametrize("terminal_action", ["resolve_case", "dismiss_case"])
@pytest.mark.parametrize("bad_reason", [None, "", "   "])
def test_apply_case_action_terminal_actions_require_reason(terminal_action: str, bad_reason: str | None):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))
    if terminal_action == "resolve_case":
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="acknowledge_case",
            actor_ref="operator@example.com",
        )

    with pytest.raises(OperatorAPIError) as exc:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key=terminal_action,
            actor_ref="operator@example.com",
            reason=bad_reason,
        )

    assert exc.value.code == "missing_case_action_reason"
    assert exc.value.status_code == 400
    expected_status = "acknowledged" if terminal_action == "resolve_case" else "open"
    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert reloaded.status == expected_status


@pytest.mark.parametrize("action_key", ["acknowledge_case", "mark_in_progress", "resolve_case", "dismiss_case"])
@pytest.mark.parametrize(
    ("bad_actor", "expected_code"),
    [("   ", "missing_operator_actor"), (123, "invalid_operator_actor")],
)
def test_apply_case_action_status_actions_reject_blank_or_non_string_actor_ref(
    action_key: str, bad_actor: Any, expected_code: str
):
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))

    with pytest.raises(OperatorAPIError) as exc:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key=action_key,
            actor_ref=bad_actor,
        )

    assert exc.value.code == expected_code
    assert exc.value.status_code == 400
    reloaded = store.get_case(opened.case_id)
    assert reloaded is not None
    assert len(reloaded.timeline) == len(opened.timeline)


def test_apply_case_action_add_comment_rejects_missing_actor_and_preserves_cross_business_scope():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(case_detection(), detected_at=utc(8))
    other = store.upsert_detection(case_detection(business_id="other", run_id="run-other"), detected_at=utc(8))

    with pytest.raises(OperatorAPIError) as missing_actor:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=opened.case_id,
            action_key="add_comment",
            actor_ref="",
            comment="Looks good",
        )
    with pytest.raises(OperatorAPIError) as cross_business:
        apply_case_action(
            store,
            business_id="artemea",
            case_id=other.case_id,
            action_key="add_comment",
            actor_ref="operator@example.com",
            comment="Cannot cross scope",
        )

    assert missing_actor.value.code == "missing_operator_actor"
    assert cross_business.value.code == "case_not_found"
    assert len(store.get_case(opened.case_id).timeline) == len(opened.timeline)
    assert len(store.get_case(other.case_id).timeline) == len(other.timeline)


def test_internal_case_action_route_accepts_add_comment_payload_envelope_redacts_and_persists(monkeypatch, tmp_path):
    test_client, db_path = client(monkeypatch, tmp_path)
    case = seed_sqlite_case(db_path)

    response = test_client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Orvo-Operator": "operator access_token=raw_actor_secret"},
        json={"action_key": "add_comment", "comment": "Supplier pinged api_key=raw_comment_secret"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert_no_raw_comment_secret(raw_body)
    assert_no_raw_actor_secret(raw_body)
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["request_id"] == "req-comment-test"
    assert body["redaction_applied"] is True
    detail = body["data"]["case"]
    assert detail["status"] == "open"
    assert detail["timeline"][-1]["event_type"] == "operator_comment"
    assert detail["timeline"][-1]["actor_ref"] == "operator access_token=[REDACTED]"

    connection = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(connection).get_case(case.case_id)
    connection.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert reloaded.timeline[-1].event_type == "operator_comment"
    assert reloaded.timeline[-1].actor_ref == "operator access_token=[REDACTED]"
    assert_no_raw_comment_secret(reloaded.model_dump_json())
    assert_no_raw_actor_secret(reloaded.model_dump_json())
