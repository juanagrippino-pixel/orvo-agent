"""HTTP endpoint tests for the recently-commented case listing endpoint."""

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
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Recently commented case under test access_token=raw_title_secret",
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _seed_open_case(
    db_path,
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    opened_hours_ago: int = 2,
    run_id: str = "run-1",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
) -> str:
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    case = store.upsert_detection(
        _detection(
            business_id=business_id,
            case_type=case_type,
            run_id=run_id,
            dedupe_suffix=dedupe_suffix,
        ),
        detected_at=now - timedelta(hours=opened_hours_ago),
    )
    conn.close()
    return case.case_id


def _comment_case(
    db_path,
    case_id: str,
    *,
    commented_minutes_ago: int,
    comment: str = "comment",
    actor_ref: str = "operator:juan",
) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.add_comment(
        case_id,
        actor_type="operator",
        actor_ref=actor_ref,
        comment=comment,
        commented_at=datetime.now(timezone.utc) - timedelta(minutes=commented_minutes_ago),
    )
    conn.close()


def test_recently_commented_returns_scoped_cases_ordered_newest_first_and_redacted(_isolate_db):
    from server import app

    older = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-older",
        dedupe_suffix="recent/commented/older",
    )
    newest = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-newest",
        dedupe_suffix="recent/commented/newest",
    )
    no_comment = _seed_open_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-no-comment",
        dedupe_suffix="recent/commented/no-comment",
    )
    other_business = _seed_open_case(
        _isolate_db,
        business_id="other-biz",
        opened_hours_ago=8,
        run_id="run-other",
        dedupe_suffix="recent/commented/other",
    )

    _comment_case(_isolate_db, older, commented_minutes_ago=30, comment="older comment")
    _comment_case(
        _isolate_db,
        newest,
        commented_minutes_ago=5,
        comment="follow-up access_token=raw_comment_secret",
        actor_ref="operator access_token=raw_actor_secret",
    )
    _comment_case(_isolate_db, other_business, commented_minutes_ago=1, comment="other business")

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-commented?limit=1",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["commented_total"] == 2
    assert data["limit"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["case_id"] == newest
    assert data["cases"][0]["status"] == "open"
    assert data["cases"][0]["title"] == "Recently commented case under test access_token=[REDACTED]"
    assert data["cases"][0]["entity_scope"] == {"kind": "business", "id": "monitored"}
    assert data["cases"][0]["latest_comment_summary"] == "follow-up access_token=[REDACTED]"
    assert data["cases"][0]["latest_comment_actor_ref"] == "operator access_token=[REDACTED]"
    assert data["cases"][0]["comment_count"] == 1
    serialized = str(body)
    assert "raw_comment_secret" not in serialized
    assert "raw_actor_secret" not in serialized
    assert "raw_title_secret" not in serialized
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert older not in returned_case_ids
    assert no_comment not in returned_case_ids
    assert other_business not in returned_case_ids


def test_recently_commented_requires_internal_auth(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-commented",
    )

    assert response.status_code == 401
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "unauthorized"
    assert body["redaction_applied"] is True


def test_recently_commented_enforces_explicit_business_scope(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-commented",
        headers=AUTH_WRONG_SCOPE,
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True
