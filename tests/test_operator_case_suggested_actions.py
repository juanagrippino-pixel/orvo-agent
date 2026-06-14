"""Tests for the shared suggested-action case projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import OperatorAPIError, list_suggested_action_cases


NOW = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-suggested-1",
    suggested_action_keys: list[str] | None = None,
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Suggested action case",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"suggested_action_keys": suggested_action_keys or []},
    )


def test_list_suggested_action_cases_accepts_registered_case_scoped_operator_request_filters():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="suggested-actions/data-stale/refresh",
            run_id="run-refresh",
            suggested_action_keys=["refresh_credentials", "retry_connector"],
        ),
        detected_at=NOW - timedelta(hours=2),
    )

    result = list_suggested_action_cases(store, business_id="artemea", action_key="refresh_credentials")

    assert result["filters"] == {"action_key": "refresh_credentials"}
    assert result["suggested_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == case.case_id
    assert result["cases"][0]["suggested_action_keys"] == ["refresh_credentials"]
    assert [action["action_key"] for action in result["cases"][0]["suggested_actions"]] == [
        "refresh_credentials"
    ]


def test_list_suggested_action_cases_rejects_registered_manual_mutation_filter_key():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(
            dedupe_suffix="suggested-actions/stockout",
            run_id="run-stockout",
            suggested_action_keys=["confirm_stock"],
        ),
        detected_at=NOW - timedelta(hours=1),
    )

    with pytest.raises(OperatorAPIError) as exc_info:
        list_suggested_action_cases(store, business_id="artemea", action_key="resolve_case")

    assert exc_info.value.code == "unsupported_suggested_action_key"
    assert exc_info.value.status_code == 400
    assert "resolve_case" in exc_info.value.message
