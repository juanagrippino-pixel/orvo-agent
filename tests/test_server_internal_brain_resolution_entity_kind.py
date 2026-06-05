from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import SQLiteOperationalCaseStore
from app.brain.storage import init_schema
from tests.test_internal_operator_api import AUTH, _case_detection, _client


def _resolve_case(store: SQLiteOperationalCaseStore, case_id: str, opened_at: datetime, *, resolve_after: timedelta) -> None:
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + resolve_after,
    )


def test_internal_case_resolution_latency_by_entity_kind_endpoint_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)

    product = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-product-resolved-entity-kind",
            dedupe_suffix="stockout_risk/product/sku-entity-kind/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-entity-kind", "label": "SKU Entity Kind"},
        ),
        detected_at=opened_at,
    )
    _resolve_case(store, product.case_id, opened_at, resolve_after=timedelta(hours=3))

    channel = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-channel-resolved-entity-kind",
            dedupe_suffix="sales_drop/channel/online/commerce.revenue/daily",
            entity_scope={"kind": "channel", "id": "online", "label": "Online"},
        ),
        detected_at=opened_at,
    )
    _resolve_case(store, channel.case_id, opened_at, resolve_after=timedelta(hours=10))

    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-resolved-entity-kind",
            dedupe_suffix="stockout_risk/product/sku-other-entity-kind/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-other", "label": "Other"},
        ),
        detected_at=opened_at,
    )
    _resolve_case(store, other.case_id, opened_at, resolve_after=timedelta(days=8))
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/resolution-latency/by-entity-kind",
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
    assert data["by_resolution_bucket_entity_kind"] == {
        "under_1h": {},
        "under_6h": {"product": 1},
        "under_24h": {"channel": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_resolved"]["case_id"] == product.case_id
    assert data["slowest_resolved"]["case_id"] == channel.case_id
