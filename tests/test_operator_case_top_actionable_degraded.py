"""Tests for the top-N actionable degraded cases projection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import (
    OperatorAPIError,
    list_top_actionable_degraded_cases,
)


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-degraded-1",
    freshness_state: str = "degraded",
    snapshot_captured_at: datetime | None = None,
    source: str = "tiendanube",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_id}/{evidence_ref}/{case_type}/business/monitored",
        captured_at=snapshot_captured_at or _utc(8),
        run_id=run_id,
        artifact_ref=f"ledger://runs/{run_id}/daily-report",
        evidence_ref=evidence_ref,
        source=source,
        source_label=source.title(),
        case_type=case_type,  # type: ignore[arg-type]
        entity_scope={"kind": "business", "id": "monitored"},
        summary="Snapshot",
        freshness_state=freshness_state,  # type: ignore[arg-type]
    )
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        evidence_snapshots=[snapshot],
    )


def test_returns_empty_list_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_top_actionable_degraded_cases(
        store, business_id="artemea", now=_utc(12)
    )

    assert result == {
        "business_id": "artemea",
        "now": _utc(12).isoformat(),
        "actionable_degraded_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_by_priority_desc_then_case_id_asc_and_filters_to_actionable_degraded():
    store = InMemoryOperationalCaseStore()
    # Critical degraded stockout — should rank first.
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            priority=100,
            run_id="run-a",
            freshness_state="degraded",
            snapshot_captured_at=_utc(7),
            source="tiendanube",
        ),
        detected_at=_utc(8),
    )
    # Warning stale sales drop — should rank second.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-b",
            freshness_state="stale",
            snapshot_captured_at=_utc(6),
            source="meta_ads",
        ),
        detected_at=_utc(9),
    )
    # Warning missing data_stale acknowledged case — should rank third.
    ack_case = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/connector/tiendanube/runtime.freshness/daily",
            severity="warning",
            priority=70,
            run_id="run-c",
            freshness_state="missing",
            snapshot_captured_at=_utc(5),
            source="tiendanube",
        ),
        detected_at=_utc(10),
    )
    store.transition_case(
        ack_case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(11),
    )
    # Fresh actionable case — must be excluded (not degraded).
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.shopline/daily",
            severity="warning",
            priority=90,
            run_id="run-d",
            freshness_state="fresh",
            source="tiendanube",
        ),
        detected_at=_utc(9),
    )
    # Resolved degraded case — must be excluded (not actionable).
    resolved = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="critical",
            priority=100,
            run_id="run-e",
            freshness_state="degraded",
            source="meta_ads",
        ),
        detected_at=_utc(7),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(8),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(9),
    )

    result = list_top_actionable_degraded_cases(
        store, business_id="artemea", now=_utc(12)
    )

    assert result["business_id"] == "artemea"
    assert result["now"] == _utc(12).isoformat()
    assert result["actionable_degraded_total"] == 3
    assert result["limit"] == 50
    assert result["count"] == 3
    # Priority 100 first; tie-break on priority 70 is case_id ASC (random UUIDs, so
    # we compare per-case_type rather than by index for the tied group).
    cases = result["cases"]
    assert cases[0]["case_type"] == "stockout_risk"
    assert cases[0]["priority_score"] == 100
    assert [c["priority_score"] for c in cases] == [100, 70, 70]

    # Build a lookup by case_type for the two tied cases (order-independent).
    by_type = {c["case_type"]: c for c in cases[1:]}
    assert set(by_type) == {"sales_drop", "data_stale"}

    sd = by_type["sales_drop"]
    ds = by_type["data_stale"]
    assert sd["status"] == "open"
    assert sd["freshness_state"] == "stale"
    assert sd["age_seconds"] == 3 * 3600
    assert sd["source_connectors"] == ["meta_ads"]
    assert sd["latest_evidence_at"] == "2026-05-24T06:00:00Z"

    assert ds["status"] == "acknowledged"
    assert ds["freshness_state"] == "missing"
    assert ds["age_seconds"] == 2 * 3600
    assert ds["source_connectors"] == ["tiendanube"]
    assert ds["latest_evidence_at"] == "2026-05-24T05:00:00Z"

    # Top case attributes verified directly by index.
    assert cases[0]["status"] == "open"
    assert cases[0]["freshness_state"] == "degraded"
    assert cases[0]["age_seconds"] == 4 * 3600
    assert cases[0]["source_connectors"] == ["tiendanube"]
    assert cases[0]["latest_evidence_at"] == "2026-05-24T07:00:00Z"


def test_freshness_state_collapses_to_most_severe_when_multiple_snapshots():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            run_id="run-multi",
            freshness_state="stale",
            snapshot_captured_at=_utc(6),
            source="tiendanube",
        ),
        detected_at=_utc(8),
    )
    # Append a second snapshot via re-upsert under a different run; the
    # store-level merge appends snapshots when keys differ.
    store.upsert_detection(
        OperationalCaseDetection(
            business_id="artemea",
            case_type="stockout_risk",
            dedupe_key=case.dedupe_key,
            title="Caso",
            severity="critical",
            priority_score=100,
            entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
            evidence_refs=[f"evidence://artemea/run-multi-2/stockout_risk"],
            run_id="run-multi-2",
            artifact_refs=["ledger://runs/run-multi-2/daily-report"],
            evidence_snapshots=[
                OperationalCaseEvidenceSnapshot(
                    snapshot_key="run-multi-2/evidence/stockout_risk/missing",
                    captured_at=_utc(9),
                    run_id="run-multi-2",
                    artifact_ref="ledger://runs/run-multi-2/daily-report",
                    evidence_ref="evidence://artemea/run-multi-2/stockout_risk",
                    source="meta_ads",
                    source_label="Meta Ads",
                    case_type="stockout_risk",
                    entity_scope={"kind": "business", "id": "monitored"},
                    summary="Snapshot",
                    freshness_state="missing",
                )
            ],
        ),
        detected_at=_utc(9),
    )

    result = list_top_actionable_degraded_cases(
        store, business_id="artemea", now=_utc(12)
    )

    assert result["actionable_degraded_total"] == 1
    assert result["cases"][0]["freshness_state"] == "missing"
    assert result["cases"][0]["source_connectors"] == ["meta_ads", "tiendanube"]
    # latest_evidence_at is the newest captured_at across snapshots.
    assert result["cases"][0]["latest_evidence_at"] == "2026-05-24T09:00:00Z"


def test_respects_limit_parameter():
    store = InMemoryOperationalCaseStore()
    for index, priority in enumerate((100, 90, 80, 70, 60)):
        store.upsert_detection(
            _detection(
                case_type="stockout_risk",
                dedupe_suffix=f"stockout_risk/business/monitored/sku-{index}/daily",
                severity="warning",
                priority=priority,
                run_id=f"run-{index}",
                freshness_state="degraded",
            ),
            detected_at=_utc(8),
        )

    result = list_top_actionable_degraded_cases(
        store, business_id="artemea", limit="2", now=_utc(12)
    )

    assert result["limit"] == 2
    assert result["count"] == 2
    assert result["actionable_degraded_total"] == 5
    assert [case["priority_score"] for case in result["cases"]] == [100, 90]


def test_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(business_id="artemea", run_id="run-a"),
        detected_at=_utc(8),
    )
    store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-b"),
        detected_at=_utc(8),
    )

    result = list_top_actionable_degraded_cases(
        store, business_id="other-shop", now=_utc(12)
    )

    assert result["business_id"] == "other-shop"
    assert result["actionable_degraded_total"] == 1
    assert result["count"] == 1


def test_requires_timezone_aware_now():
    store = InMemoryOperationalCaseStore()
    naive = datetime(2026, 5, 24, 12)

    try:
        list_top_actionable_degraded_cases(store, business_id="artemea", now=naive)
    except OperatorAPIError as exc:
        assert exc.code == "invalid_now"
        assert exc.status_code == 400
    else:  # pragma: no cover - defensive
        raise AssertionError("expected OperatorAPIError")
