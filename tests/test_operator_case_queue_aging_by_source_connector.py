"""Tests for the source-connector-split case-queue aging projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    OperatorAPIError,
    summarize_case_queue_aging_by_source_connector,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-aging-source-1",
    source: str = "tiendanube",
) -> OperationalCaseDetection:
    # _source_from_evidence_ref parses the host segment after evidence://,
    # so embedding ``source`` there exercises the same path used in production.
    evidence_ref = f"evidence://{source}/{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _empty_buckets() -> dict[str, int]:
    return {"under_1h": 0, "under_6h": 0, "under_24h": 0, "under_7d": 0, "over_7d": 0}


def test_summarize_case_queue_aging_by_source_connector_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    assert result == {
        "business_id": "artemea",
        "now": "2026-05-26T12:00:00+00:00",
        "actionable_total": 0,
        "by_age_bucket": _empty_buckets(),
        "by_age_bucket_source_connector": {bucket: {} for bucket in _empty_buckets()},
        "oldest_actionable": None,
    }


def test_summarize_case_queue_aging_by_source_connector_splits_actionable_by_source_per_bucket():
    store = InMemoryOperationalCaseStore()

    schedule = [
        # (run_id, case_type, dedupe_suffix, source, age_offset)
        ("a", "stockout_risk", "stockout_risk/product/sku-a/commerce.inventory/daily", "tiendanube", timedelta(minutes=30)),    # under_1h
        ("b", "stockout_risk", "stockout_risk/product/sku-b/commerce.inventory/daily", "tiendanube", timedelta(hours=3)),       # under_6h
        ("c", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "google_sheets", timedelta(hours=3)),              # under_6h
        ("d", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "google_sheets", timedelta(hours=10)),        # under_24h
        ("e", "unanswered_conversations", "unanswered_conversations/channel/whatsapp/support.conversations/daily", "csv", timedelta(days=2)),  # under_7d
        ("f", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "tiendanube", timedelta(days=10)),       # over_7d
    ]
    for run_id, case_type, dedupe_suffix, source, age in schedule:
        store.upsert_detection(
            _detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
                source=source,
            ),
            detected_at=NOW - age,
        )

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 6
    assert result["by_age_bucket"] == {
        "under_1h": 1,
        "under_6h": 2,
        "under_24h": 1,
        "under_7d": 1,
        "over_7d": 1,
    }
    assert result["by_age_bucket_source_connector"] == {
        "under_1h": {"tiendanube": 1},
        "under_6h": {"tiendanube": 1, "google_sheets": 1},
        "under_24h": {"google_sheets": 1},
        "under_7d": {"csv": 1},
        "over_7d": {"tiendanube": 1},
    }
    oldest = result["oldest_actionable"]
    assert oldest is not None
    assert oldest["case_type"] == "data_stale"
    assert oldest["age_seconds"] == int(timedelta(days=10).total_seconds())


def test_summarize_case_queue_aging_by_source_connector_buckets_missing_source_as_unknown():
    # A detection with no evidence_refs leaves the case with zero evidence
    # snapshots, so _source_connectors returns []. Such cases must still be
    # accounted for under the "unknown" bucket so totals never silently drop.
    store = InMemoryOperationalCaseStore()
    detection = OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key="artemea/stockout_risk/product/sku-x/commerce.inventory/daily",
        title="Caso sin evidencia",
        severity="critical",
        priority_score=90,
        entity_scope={"kind": "product", "id": "sku-x", "label": "SKU X"},
        evidence_refs=[],
        run_id="run-x",
        artifact_refs=[],
    )
    store.upsert_detection(detection, detected_at=NOW - timedelta(hours=2))

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["by_age_bucket"]["under_6h"] == 1
    assert result["by_age_bucket_source_connector"]["under_6h"] == {"unknown": 1}


def test_summarize_case_queue_aging_by_source_connector_uses_first_sorted_source_for_multi_source_cases():
    # Cases with evidence from multiple connectors attribute to the first
    # sorted source name — mirroring the workflow-throughput-by-source rule —
    # so bucket counts stay equal to the count of actionable cases without
    # double-counting.
    store = InMemoryOperationalCaseStore()
    first_detection = _detection(
        dedupe_suffix="stockout_risk/product/sku-multi/commerce.inventory/daily",
        run_id="run-multi-1",
        source="tiendanube",
    )
    store.upsert_detection(first_detection, detected_at=NOW - timedelta(hours=3))
    second_detection = _detection(
        dedupe_suffix="stockout_risk/product/sku-multi/commerce.inventory/daily",
        run_id="run-multi-2",
        source="google_sheets",
    )
    store.upsert_detection(second_detection, detected_at=NOW - timedelta(hours=2))

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    # sorted(["tiendanube", "google_sheets"]) -> "google_sheets" first.
    assert result["actionable_total"] == 1
    assert result["by_age_bucket"]["under_6h"] == 1
    assert result["by_age_bucket_source_connector"]["under_6h"] == {"google_sheets": 1}


def test_summarize_case_queue_aging_by_source_connector_excludes_resolved_cases():
    store = InMemoryOperationalCaseStore()
    open_case = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open", source="tiendanube"),
        detected_at=NOW - timedelta(hours=2),
    )
    resolved = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-done",
            source="google_sheets",
        ),
        detected_at=NOW - timedelta(days=20),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(days=19),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(days=18),
    )

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["by_age_bucket"]["under_6h"] == 1
    assert result["by_age_bucket"]["over_7d"] == 0
    assert result["by_age_bucket_source_connector"] == {
        "under_1h": {},
        "under_6h": {"tiendanube": 1},
        "under_24h": {},
        "under_7d": {},
        "over_7d": {},
    }
    assert result["oldest_actionable"]["case_id"] == open_case.case_id


def test_summarize_case_queue_aging_by_source_connector_includes_acknowledged_as_actionable():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-ack", source="tiendanube"),
        detected_at=NOW - timedelta(hours=8),
    )
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=1),
    )

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    # Bucket is based on opened_at, not the ack timestamp.
    assert result["by_age_bucket"]["under_24h"] == 1
    assert result["by_age_bucket_source_connector"]["under_24h"] == {"tiendanube": 1}


def test_summarize_case_queue_aging_by_source_connector_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(
            business_id="artemea",
            case_type="stockout_risk",
            run_id="run-a",
            source="tiendanube",
        ),
        detected_at=NOW - timedelta(hours=4),
    )
    store.upsert_detection(
        _detection(
            business_id="other-shop",
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            run_id="run-other",
            source="google_sheets",
        ),
        detected_at=NOW - timedelta(days=30),
    )

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["by_age_bucket"]["under_6h"] == 1
    assert result["by_age_bucket"]["over_7d"] == 0
    assert result["by_age_bucket_source_connector"] == {
        "under_1h": {},
        "under_6h": {"tiendanube": 1},
        "under_24h": {},
        "under_7d": {},
        "over_7d": {},
    }
    assert result["oldest_actionable"]["case_type"] == "stockout_risk"


def test_summarize_case_queue_aging_by_source_connector_uses_current_utc_when_now_not_provided(monkeypatch):
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-now", source="tiendanube"),
        detected_at=NOW - timedelta(minutes=10),
    )

    import app.brain.operator_api as operator_api

    monkeypatch.setattr(operator_api, "_now_utc", lambda: NOW)

    result = summarize_case_queue_aging_by_source_connector(store, business_id="artemea")

    assert result["now"] == "2026-05-26T12:00:00+00:00"
    assert result["actionable_total"] == 1
    assert result["by_age_bucket"]["under_1h"] == 1
    assert result["by_age_bucket_source_connector"]["under_1h"] == {"tiendanube": 1}


def test_summarize_case_queue_aging_by_source_connector_rejects_naive_now():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        summarize_case_queue_aging_by_source_connector(
            store,
            business_id="artemea",
            now=datetime(2026, 5, 26, 12),
        )

    assert exc_info.value.code == "invalid_now"
    assert exc_info.value.status_code == 400
