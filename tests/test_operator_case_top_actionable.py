"""Tests for the shared top actionable cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import (
    OperatorAPIError,
    list_top_actionable_cases,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-top-shared-1",
    freshness_state: str | None = None,
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshots = []
    if freshness_state is not None:
        snapshots.append(
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"{run_id}/{case_type}/{freshness_state}",
                captured_at=NOW - timedelta(hours=1),
                run_id=run_id,
                artifact_ref=f"ledger://runs/{run_id}/daily-report",
                evidence_ref=evidence_ref,
                source="tiendanube",
                source_label="Tiendanube",
                case_type=case_type,  # type: ignore[arg-type]
                entity_scope={"kind": "business", "id": "monitored"},
                summary="Snapshot",
                freshness_state=freshness_state,  # type: ignore[arg-type]
            )
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
        evidence_snapshots=snapshots,
    )


def test_list_top_actionable_cases_defaults_to_priority_projection():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(priority=20, run_id="run-low", dedupe_suffix="shared/low"),
        detected_at=NOW - timedelta(hours=2),
    )
    store.upsert_detection(
        _detection(priority=95, run_id="run-high", dedupe_suffix="shared/high"),
        detected_at=NOW - timedelta(hours=4),
    )
    store.upsert_detection(
        _detection(priority=60, run_id="run-mid", dedupe_suffix="shared/mid"),
        detected_at=NOW - timedelta(hours=1),
    )

    result = list_top_actionable_cases(
        store,
        business_id="artemea",
        now=NOW,
        limit="2",
    )

    assert result["projection_type"] == "top_actionable_cases"
    assert result["ranking"] == "priority"
    assert result["actionable_total"] == 3
    assert result["count"] == 2
    assert [case["priority_score"] for case in result["cases"]] == [95, 60]


def test_list_top_actionable_cases_supports_degraded_ranking():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(
            priority=90,
            run_id="run-degraded",
            dedupe_suffix="shared/degraded",
            freshness_state="degraded",
        ),
        detected_at=NOW - timedelta(hours=3),
    )
    store.upsert_detection(
        _detection(
            priority=99,
            run_id="run-fresh",
            dedupe_suffix="shared/fresh",
            freshness_state="fresh",
        ),
        detected_at=NOW - timedelta(hours=2),
    )

    result = list_top_actionable_cases(
        store,
        business_id="artemea",
        ranking="degraded",
        now=NOW,
    )

    assert result["projection_type"] == "top_actionable_cases"
    assert result["ranking"] == "degraded"
    assert result["actionable_degraded_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["freshness_state"] == "degraded"


def test_list_top_actionable_cases_rejects_invalid_ranking_with_safe_error():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as excinfo:
        list_top_actionable_cases(
            store,
            business_id="artemea",
            ranking="api_key=raw_secret",
            now=NOW,
        )

    assert excinfo.value.code == "invalid_top_case_ranking"
    assert "raw_secret" not in excinfo.value.message
    assert "[REDACTED]" in excinfo.value.message
