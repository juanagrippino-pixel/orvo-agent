from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import SQLiteOperationalCaseStore
from app.brain.storage import init_schema
from tests.test_internal_operator_api import AUTH, _case_detection, _client
from tests.test_server_internal_brain_resolution_entity_kind import _resolve_case


def test_internal_case_resolution_latency_by_severity_endpoint_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)

    critical = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-critical-resolved-severity",
            dedupe_suffix="stockout_risk/business/critical/commerce.inventory/daily",
            severity="critical",
        ),
        detected_at=opened_at,
    )
    _resolve_case(store, critical.case_id, opened_at, resolve_after=timedelta(hours=3))

    warning = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-warning-resolved-severity",
            dedupe_suffix="sales_drop/business/warning/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    _resolve_case(store, warning.case_id, opened_at, resolve_after=timedelta(hours=10))

    open_case = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-open-severity",
            dedupe_suffix="stockout_risk/business/open/commerce.inventory/daily",
            severity="critical",
        ),
        detected_at=opened_at,
    )
    assert open_case.resolved_at is None

    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-resolved-severity",
            dedupe_suffix="stockout_risk/business/other/commerce.inventory/daily",
            severity="critical",
        ),
        detected_at=opened_at,
    )
    _resolve_case(store, other.case_id, opened_at, resolve_after=timedelta(days=8))
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/resolution-latency/by-severity",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["resolved_total"] == 2
    assert data["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_resolution_bucket_severity"] == {
        "under_1h": {},
        "under_6h": {"critical": 1},
        "under_24h": {"warning": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_resolved"]["case_id"] == critical.case_id
    assert data["slowest_resolved"]["case_id"] == warning.case_id
