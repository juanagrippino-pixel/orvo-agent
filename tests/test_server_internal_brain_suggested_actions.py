"""HTTP endpoint tests for the suggested-action case queue projection."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import OperationalCaseDetection, OperationalCaseSeverity, OperationalCaseType
from app.brain.storage import SQLiteOperationalCaseStore, init_schema

AUTH_WITH_SCOPE = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator@example.com",
    "X-Orvo-Businesses": "artemea",
}
AUTH_WRONG_SCOPE = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator@example.com",
    "X-Orvo-Businesses": "other-biz",
}


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_brain.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    with closing(sqlite3.connect(str(db_path))) as conn:
        init_schema(conn)
    yield db_path


def _detection(
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: OperationalCaseSeverity = "critical",
    priority: int = 100,
    run_id: str = "run-1",
    suggested_action_keys: list[str] | None = None,
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Suggested action case access_token=raw_title_secret",
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "sku", "id": "SKU-1", "label": "Campera access_token=raw_entity_secret"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"suggested_action_keys": suggested_action_keys or []},
    )


def _seed_case(
    db_path,
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    opened_hours_ago: int = 2,
    run_id: str = "run-1",
    dedupe_suffix: str = "suggested/actions/case",
    priority: int = 100,
    suggested_action_keys: list[str] | None = None,
) -> str:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    case = store.upsert_detection(
        _detection(
            business_id=business_id,
            case_type=case_type,
            run_id=run_id,
            dedupe_suffix=dedupe_suffix,
            priority=priority,
            suggested_action_keys=suggested_action_keys,
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=opened_hours_ago),
    )
    conn.close()
    return case.case_id


def _transition_case(db_path, case_id: str, status: str) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.transition_case(
        case_id,
        status=status,  # type: ignore[arg-type]
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="done",
        transitioned_at=datetime.now(timezone.utc),
    )
    conn.close()


def test_suggested_actions_returns_scoped_actionable_cases_with_registered_actions_only(_isolate_db):
    from server import app

    high_priority = _seed_case(
        _isolate_db,
        opened_hours_ago=4,
        run_id="run-high",
        dedupe_suffix="suggested/actions/high",
        suggested_action_keys=["confirm_stock", "pause_promotion", "invented_action"],
    )
    lower_priority = _seed_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-low",
        dedupe_suffix="suggested/actions/low",
        priority=70,
        suggested_action_keys=["confirm_stock"],
    )
    no_actions = _seed_case(
        _isolate_db,
        opened_hours_ago=6,
        run_id="run-none",
        dedupe_suffix="suggested/actions/none",
        suggested_action_keys=[],
    )
    other_business = _seed_case(
        _isolate_db,
        business_id="other-biz",
        opened_hours_ago=1,
        run_id="run-other",
        dedupe_suffix="suggested/actions/other",
        suggested_action_keys=["confirm_stock"],
    )
    resolved = _seed_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-resolved",
        dedupe_suffix="suggested/actions/resolved",
        suggested_action_keys=["confirm_stock"],
    )
    _transition_case(_isolate_db, resolved, "acknowledged")
    _transition_case(_isolate_db, resolved, "resolved")

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/suggested-actions?limit=2",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["suggested_total"] == 2
    assert data["limit"] == 2
    assert data["count"] == 2
    assert [case["case_id"] for case in data["cases"]] == [high_priority, lower_priority]
    assert data["cases"][0]["suggested_action_keys"] == ["confirm_stock", "pause_promotion"]
    assert [action["action_key"] for action in data["cases"][0]["suggested_actions"]] == [
        "confirm_stock",
        "pause_promotion",
    ]
    assert data["cases"][0]["suggested_actions"][0]["operator_executable"] is False
    assert data["cases"][0]["suggested_actions"][1]["approval_required"] is True
    assert data["cases"][0]["action_count"] == 2
    serialized = str(body)
    assert "raw_title_secret" not in serialized
    assert "raw_entity_secret" not in serialized
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert no_actions not in returned_case_ids
    assert other_business not in returned_case_ids
    assert resolved not in returned_case_ids


def test_suggested_actions_filters_by_registered_action_key(_isolate_db):
    from server import app

    confirm_only = _seed_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-confirm",
        dedupe_suffix="suggested/actions/confirm",
        priority=90,
        suggested_action_keys=["confirm_stock"],
    )
    pause_and_confirm = _seed_case(
        _isolate_db,
        opened_hours_ago=2,
        run_id="run-pause",
        dedupe_suffix="suggested/actions/pause",
        priority=70,
        suggested_action_keys=["pause_promotion", "confirm_stock"],
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/suggested-actions",
        headers=AUTH_WITH_SCOPE,
        query_string={"action_key": "pause_promotion"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["filters"] == {"action_key": "pause_promotion"}
    assert data["suggested_total"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["case_id"] == pause_and_confirm
    assert data["cases"][0]["suggested_action_keys"] == ["pause_promotion"]
    assert [action["action_key"] for action in data["cases"][0]["suggested_actions"]] == ["pause_promotion"]
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert confirm_only not in returned_case_ids


def test_suggested_actions_rejects_unknown_action_key_without_echoing_secret(_isolate_db):
    from server import app

    _seed_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-secret-query",
        dedupe_suffix="suggested/actions/secret-query",
        suggested_action_keys=["confirm_stock"],
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/suggested-actions",
        headers=AUTH_WITH_SCOPE,
        query_string={"action_key": "confirm_stock access_token=raw_action_filter_secret"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "unknown_suggested_action_key"
    assert body["redaction_applied"] is True
    assert "raw_action_filter_secret" not in str(body)


def test_suggested_actions_requires_internal_auth(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get("/internal/brain/businesses/artemea/cases/suggested-actions")

    assert response.status_code == 401
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "unauthorized"
    assert body["redaction_applied"] is True


def test_suggested_actions_enforces_explicit_business_scope(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/suggested-actions",
        headers=AUTH_WRONG_SCOPE,
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True
