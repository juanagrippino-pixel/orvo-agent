from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
    SQLiteOperationalCaseStore,
)
from app.brain.run_ledger import ConnectorRunOutcome, InMemoryRunLedger, SQLiteRunLedger
from app.brain.storage import init_schema

AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator:juan",
    "X-Request-ID": "req-os-snapshot",
}


def _utc(hour: int) -> datetime:
    return datetime(2026, 6, 11, hour, tzinfo=timezone.utc)


def _stockout_detection(*, business_id: str = "artemea", run_id: str = "run-tn-1") -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/stockout_risk"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type="stockout_risk",
        dedupe_key=f"{business_id}/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity="critical",
        priority_score=95,
        entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        evidence_snapshots=[
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"{run_id}/{evidence_ref}/stockout_risk/business/monitored",
                captured_at=_utc(8),
                run_id=run_id,
                artifact_ref=f"ledger://runs/{run_id}/daily-report?access_token=raw_artifact_secret",
                evidence_ref=evidence_ref,
                source="tiendanube",
                source_label="Tiendanube access_token=raw_snapshot_secret",
                case_type="stockout_risk",
                entity_scope={"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
                summary="Stock evidence Bearer raw_snapshot_secret",
                freshness_state="fresh",
                metadata={"api_key": "raw_snapshot_secret"},
            )
        ],
    )


def _data_stale_detection(*, business_id: str = "artemea", run_id: str = "run-tn-failed") -> OperationalCaseDetection:
    evidence_ref = f"evidence://tiendanube/{run_id}/data_stale"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type="data_stale",
        dedupe_key=f"{business_id}/data_stale/connector/tiendanube/runtime.freshness/daily",
        title="Tiendanube sin datos frescos",
        severity="warning",
        priority_score=75,
        entity_scope={"kind": "connector", "id": "tiendanube", "label": "Tiendanube"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/connector-error"],
        evidence_snapshots=[
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"{run_id}/{evidence_ref}/data_stale/connector/tiendanube",
                captured_at=_utc(9),
                run_id=run_id,
                artifact_ref=f"ledger://runs/{run_id}/connector-error",
                evidence_ref=evidence_ref,
                source="tiendanube",
                source_label="Tiendanube",
                case_type="data_stale",
                entity_scope={"kind": "connector", "id": "tiendanube", "label": "Tiendanube"},
                summary="Connector failed",
                freshness_state="stale",
            )
        ],
    )


def _append_tiendanube_success(ledger: InMemoryRunLedger, *, business_id: str = "artemea", run_id: str = "run-tn-1") -> None:
    ledger.create_run(business_id=business_id, trigger_type="scheduled", run_id=run_id, started_at=_utc(7))
    ledger.append_connector_outcome(
        run_id,
        ConnectorRunOutcome(
            connector_id="tn-main",
            connector_type="tiendanube",
            status="succeeded",
            started_at=_utc(7),
            finished_at=_utc(8),
            metrics_count=12,
            evidence_refs=[f"evidence://{business_id}/{run_id}/daily-report"],
            metadata={"access_token": "raw_connector_secret"},
        ),
    )
    ledger.update_run(run_id, status="succeeded", finished_at=_utc(8))


def test_os_snapshot_projects_five_lapyme_modules_without_fake_readiness() -> None:
    from app.brain.operator_api import get_lapyme_os_snapshot

    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()
    _append_tiendanube_success(ledger)
    stock_case = store.upsert_detection(_stockout_detection(), detected_at=_utc(8))

    snapshot = get_lapyme_os_snapshot(store, ledger, business_id="artemea", now=_utc(10))

    assert snapshot["business_id"] == "artemea"
    assert snapshot["snapshot_key"] == "lapyme_category_os_snapshot"
    assert [module["module_id"] for module in snapshot["modules"]] == [
        "sales_orders",
        "stock_fulfillment",
        "whatsapp_attention",
        "arca_fiscal_readiness",
        "treasury_reporting",
    ]

    modules = {module["module_id"]: module for module in snapshot["modules"]}
    assert modules["sales_orders"]["status"] == "ready"
    assert modules["sales_orders"]["source_connectors"] == ["tiendanube"]
    assert modules["sales_orders"]["latest_run_id"] == "run-tn-1"
    assert modules["sales_orders"]["latest_run_status"] == "succeeded"

    assert modules["stock_fulfillment"]["status"] == "attention_required"
    assert modules["stock_fulfillment"]["actionable_case_count"] == 1
    assert modules["stock_fulfillment"]["top_case_ids"] == [stock_case.case_id]
    assert modules["stock_fulfillment"]["source_connectors"] == ["tiendanube"]

    assert modules["whatsapp_attention"]["status"] == "setup_required"
    assert modules["arca_fiscal_readiness"]["status"] == "setup_required"
    assert modules["treasury_reporting"]["status"] == "setup_required"
    assert snapshot["summary"]["setup_required"] == 3
    assert snapshot["summary"]["ready"] == 1
    assert snapshot["summary"]["attention_required"] == 1

    serialized = json.dumps(snapshot, sort_keys=True)
    assert "raw_connector_secret" not in serialized
    assert "raw_snapshot_secret" not in serialized
    assert "raw_artifact_secret" not in serialized


def test_os_snapshot_marks_commerce_modules_data_stale_from_cases_and_failed_runs() -> None:
    from app.brain.operator_api import get_lapyme_os_snapshot

    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()
    ledger.create_run(business_id="artemea", trigger_type="scheduled", run_id="run-tn-failed", started_at=_utc(8))
    ledger.append_connector_outcome(
        "run-tn-failed",
        ConnectorRunOutcome(
            connector_id="tn-main",
            connector_type="tiendanube",
            status="failed",
            started_at=_utc(8),
            finished_at=_utc(9),
            error_summary="401 access_token=raw_failure_secret",
        ),
    )
    ledger.update_run("run-tn-failed", status="failed", finished_at=_utc(9), error_summary="Bearer raw_run_secret")
    stale_case = store.upsert_detection(_data_stale_detection(), detected_at=_utc(9))

    snapshot = get_lapyme_os_snapshot(store, ledger, business_id="artemea", now=_utc(10))

    modules = {module["module_id"]: module for module in snapshot["modules"]}
    assert modules["sales_orders"]["status"] == "data_stale"
    assert modules["sales_orders"]["top_case_ids"] == [stale_case.case_id]
    assert modules["stock_fulfillment"]["status"] == "data_stale"
    assert snapshot["summary"]["data_stale"] == 2
    assert "raw_failure_secret" not in json.dumps(snapshot, sort_keys=True)


def test_internal_os_snapshot_endpoint_returns_safe_envelope(monkeypatch, tmp_path) -> None:
    from server import app

    db_path = tmp_path / "os-snapshot.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    case_store = SQLiteOperationalCaseStore(conn)
    run_ledger = SQLiteRunLedger(conn)
    run_ledger.create_run(business_id="artemea", trigger_type="scheduled", run_id="run-tn-1", started_at=_utc(7))
    run_ledger.append_connector_outcome(
        "run-tn-1",
        ConnectorRunOutcome(
            connector_id="tn-main",
            connector_type="tiendanube",
            status="succeeded",
            started_at=_utc(7),
            finished_at=_utc(8),
        ),
    )
    run_ledger.update_run("run-tn-1", status="succeeded", finished_at=_utc(8))
    case_store.upsert_detection(_stockout_detection(), detected_at=_utc(8))
    conn.close()

    response = app.test_client().get("/internal/brain/businesses/artemea/os-snapshot", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["request_id"] == "req-os-snapshot"
    assert body["data"]["snapshot_key"] == "lapyme_category_os_snapshot"
    assert [module["module_id"] for module in body["data"]["modules"]] == [
        "sales_orders",
        "stock_fulfillment",
        "whatsapp_attention",
        "arca_fiscal_readiness",
        "treasury_reporting",
    ]
