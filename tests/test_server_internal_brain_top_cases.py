"""HTTP endpoint tests for the shared top actionable cases endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
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
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-1",
    freshness_state: str | None = None,
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshots = []
    if freshness_state is not None:
        snapshots.append(
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"{run_id}/{case_type}/{freshness_state}",
                captured_at=datetime.now(timezone.utc) - timedelta(hours=1),
                run_id=run_id,
                artifact_ref=f"ledger://runs/{run_id}/daily-report",
                evidence_ref=evidence_ref,
                source="tiendanube",
                source_label="Tiendanube",
                case_type=case_type,
                entity_scope={"kind": "business", "id": "monitored"},
                summary="Snapshot",
                freshness_state=freshness_state,
            )
        )
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Case under test api_key=raw_title_secret",
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        evidence_snapshots=snapshots,
    )


def _seed_case(
    db_path,
    *,
    business_id: str = "artemea",
    priority: int = 100,
    run_id: str = "run-1",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    freshness_state: str | None = None,
    opened_hours_ago: int = 2,
) -> str:
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    case = store.upsert_detection(
        _detection(
            business_id=business_id,
            priority=priority,
            run_id=run_id,
            dedupe_suffix=dedupe_suffix,
            freshness_state=freshness_state,
        ),
        detected_at=now - timedelta(hours=opened_hours_ago),
    )
    conn.close()
    return case.case_id


def test_top_cases_defaults_to_priority_ranking(_isolate_db):
    from server import app

    _seed_case(_isolate_db, priority=20, run_id="run-low", dedupe_suffix="shared/low")
    _seed_case(_isolate_db, priority=95, run_id="run-high", dedupe_suffix="shared/high")
    _seed_case(_isolate_db, priority=60, run_id="run-mid", dedupe_suffix="shared/mid")

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top?limit=2",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["projection_type"] == "top_actionable_cases"
    assert data["ranking"] == "priority"
    assert data["actionable_total"] == 3
    assert data["count"] == 2
    assert [case["priority_score"] for case in data["cases"]] == [95, 60]


def test_top_cases_supports_degraded_ranking(_isolate_db):
    from server import app

    _seed_case(
        _isolate_db,
        priority=90,
        run_id="run-degraded",
        dedupe_suffix="shared/degraded",
        freshness_state="degraded",
    )
    _seed_case(
        _isolate_db,
        priority=99,
        run_id="run-fresh",
        dedupe_suffix="shared/fresh",
        freshness_state="fresh",
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top?ranking=degraded",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 200
    body = response.get_json()
    data = body["data"]
    assert data["projection_type"] == "top_actionable_cases"
    assert data["ranking"] == "degraded"
    assert data["actionable_degraded_total"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["freshness_state"] == "degraded"


def test_top_cases_enforces_explicit_business_scope(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top",
        headers=AUTH_WRONG_SCOPE,
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True


def test_top_cases_rejects_invalid_ranking_with_safe_error(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top?ranking=api_key=raw_secret",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 400
    response_text = response.get_data(as_text=True)
    assert "raw_secret" not in response_text
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_top_case_ranking"
    assert body["redaction_applied"] is True
