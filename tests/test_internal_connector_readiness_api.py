from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.run_ledger import ConnectorRunOutcome
from app.brain.storage import SQLiteConfigStore, SQLiteRunLedger, init_schema

AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator:juan",
    "X-Request-ID": "req-readiness",
}


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "operator-readiness.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    from server import app

    return app.test_client(), db_path


def _save_business(db_path, business: BusinessConfig) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        SQLiteConfigStore(conn).save_business_config(business)


def _append_connector_outcome(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        ledger = SQLiteRunLedger(conn)
        run = ledger.create_run(
            business_id="artemea",
            trigger_type="forced",
            run_id="run-readiness-latest",
            started_at=_utc(7),
        )
        ledger.append_connector_outcome(
            run.run_id,
            ConnectorRunOutcome(
                connector_id="tn-main",
                connector_type="tiendanube",
                status="failed",
                health_state="unauthorized",
                started_at=_utc(7),
                finished_at=_utc(8),
                error_summary="Tiendanube 401 access_token=raw_runtime_token",
            ),
        )
        ledger.update_run(run.run_id, status="failed", finished_at=_utc(8))


def _append_certified_success_outcome(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        ledger = SQLiteRunLedger(conn)
        run = ledger.create_run(
            business_id="artemea",
            trigger_type="forced",
            run_id="run-certification-latest",
            started_at=_utc(9),
        )
        ledger.append_connector_outcome(
            run.run_id,
            ConnectorRunOutcome(
                connector_id="tn-main",
                connector_type="tiendanube",
                status="succeeded",
                health_state="ok",
                started_at=_utc(9),
                finished_at=_utc(10),
                metadata={
                    "event_certification": {
                        "status": "passed",
                        "issue_count": 0,
                        "issues": [],
                    },
                    "metric_certification": {
                        "status": "warning",
                        "issue_count": 1,
                        "issues": [
                            {
                                "code": "undeclared_family",
                                "key": "unanswered_conversations",
                                "message": "Metric key should stay registry declared",
                            }
                        ],
                    },
                },
            ),
        )
        ledger.update_run(run.run_id, status="succeeded", finished_at=_utc(10))


def test_internal_connector_readiness_projects_config_validation_and_last_health(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-main",
                    connector_type="tiendanube",
                    label="TiendaNube principal",
                    params={"store_id": "123"},
                    secret_refs={
                        "access_token": "secret://tenant/artemea/tiendanube/raw_config_secret"
                    },
                ),
                ConnectorConfig(
                    connector_id="csv-disabled",
                    connector_type="csv",
                    label="CSV backup",
                    params={"csv_path": "examples/sample_sales.csv"},
                    enabled=False,
                ),
            ],
        ),
    )
    _append_connector_outcome(db_path)

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_config_secret" not in raw_body
    assert "raw_runtime_token" not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["request_id"] == "req-readiness"
    assert body["redaction_applied"] is True

    data = body["data"]
    assert data["summary"] == {
        "total": 2,
        "ready": 0,
        "degraded": 1,
        "not_ready": 0,
        "disabled": 1,
        "unknown": 0,
        "setup_required": 1,
    }
    connectors = {item["connector_id"]: item for item in data["connectors"]}

    tiendanube = connectors["tn-main"]
    assert tiendanube["connector_type"] == "tiendanube"
    assert tiendanube["registered"] is True
    assert tiendanube["readiness_state"] == "degraded"
    assert tiendanube["setup_required"] is True
    assert tiendanube["setup_reason"] == "connector_last_run_unauthorized"
    assert tiendanube["operator_next_step"] == "refresh_connector_credentials"
    assert tiendanube["validation"] == {"error_count": 0, "warning_count": 0, "issues": []}
    assert tiendanube["auth_requirements"] == [
        {
            "name": "access_token",
            "provider": "tiendanube_oauth",
            "present": True,
            "scopes": ["orders.read", "products.read"],
        }
    ]
    assert tiendanube["last_health"] == {
        "run_id": "run-readiness-latest",
        "status": "failed",
        "health_state": "unauthorized",
        "health_detail": None,
        "started_at": "2026-05-24T07:00:00Z",
        "finished_at": "2026-05-24T08:00:00Z",
        "duration_ms": 3_600_000,
        "error_summary": "Tiendanube 401 access_token=[REDACTED]",
        "certification": None,
    }
    assert tiendanube["health_policy"]["readiness_check"] == "metadata_only"
    assert tiendanube["health_policy"]["detailed_states"] == [
        "network_error",
        "malformed_response",
        "partial_inventory_unavailable",
        "stale_success",
    ]
    assert tiendanube["required_scopes"] == ["orders.read", "products.read"]
    assert tiendanube["required_secret_refs"] == [
        {
            "name": "access_token",
            "provider": "tiendanube_oauth",
            "description": "Tiendanube API Bearer [REDACTED] reference.",
            "scopes": ["orders.read", "products.read"],
            "legacy_config_field": "access_token",
        }
    ]
    assert tiendanube["scope_notes"] == ""
    assert tiendanube["emitted_metric_families"] == [
        "commerce.orders",
        "commerce.revenue",
        "commerce.inventory",
        "runtime.freshness",
        "runtime.data_quality",
    ]
    assert tiendanube["emitted_event_families"] == [
        "connector.execution",
        "connector.health",
    ]
    assert tiendanube["supported_runtime_modes"] == [
        "preview",
        "forced",
        "scheduled",
        "operator_triggered",
    ]
    assert (
        tiendanube["executor_factory_path"]
        == "app.brain.adapters.tiendanube.build_daily_report_from_tiendanube"
    )
    assert tiendanube["executor_factory_params"][2] == {
        "argument": "access_token",
        "source": "resolved_secret_param",
        "key": "access_token",
        "required": True,
        "fallback": None,
    }

    disabled = connectors["csv-disabled"]
    assert disabled["readiness_state"] == "disabled"
    assert disabled["required_scopes"] == []
    assert disabled["supported_runtime_modes"] == [
        "preview",
        "forced",
        "scheduled",
        "operator_triggered",
    ]
    assert disabled["executor_factory_path"] == "app.brain.adapters.csv_file.build_daily_report_from_csv_file"
    assert disabled["setup_required"] is False
    assert disabled["setup_reason"] is None
    assert disabled["operator_next_step"] is None
    assert disabled["last_health"] is None


def test_internal_connector_readiness_projects_last_health_detail_when_present(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-main",
                    connector_type="tiendanube",
                    label="TiendaNube principal",
                    params={"store_id": "123"},
                    secret_refs={"access_token": "secret://tenant/artemea/tiendanube/main"},
                )
            ],
        ),
    )
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        ledger = SQLiteRunLedger(conn)
        run = ledger.create_run(
            business_id="artemea",
            trigger_type="forced",
            run_id="run-health-detail-latest",
            started_at=_utc(11),
        )
        ledger.append_connector_outcome(
            run.run_id,
            ConnectorRunOutcome(
                connector_id="tn-main",
                connector_type="tiendanube",
                status="failed",
                health_state="failed",
                started_at=_utc(11),
                finished_at=_utc(12),
                error_summary="request timed out access_token=raw_runtime_token",
                metadata={"health_detail": "network_error"},
            ),
        )
        ledger.update_run(run.run_id, status="failed", finished_at=_utc(12))

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    connector = response.get_json()["data"]["connectors"][0]
    assert connector["last_health"]["health_state"] == "failed"
    assert connector["last_health"]["health_detail"] == "network_error"
    assert connector["last_health"]["error_summary"] == "request timed out access_token=[REDACTED]"


def test_internal_connector_readiness_does_not_borrow_same_type_health_from_other_connector(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-main",
                    connector_type="tiendanube",
                    label="TiendaNube principal",
                    params={"store_id": "123"},
                    secret_refs={"access_token": "secret://tenant/artemea/tiendanube/main"},
                ),
                ConnectorConfig(
                    connector_id="tn-secondary",
                    connector_type="tiendanube",
                    label="TiendaNube secundaria",
                    params={"store_id": "456"},
                    secret_refs={"access_token": "secret://tenant/artemea/tiendanube/secondary"},
                ),
            ],
        ),
    )
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        ledger = SQLiteRunLedger(conn)
        run = ledger.create_run(
            business_id="artemea",
            trigger_type="forced",
            run_id="run-main-latest",
            started_at=_utc(7),
        )
        ledger.append_connector_outcome(
            run.run_id,
            ConnectorRunOutcome(
                connector_id="tn-main",
                connector_type="tiendanube",
                status="failed",
                health_state="unauthorized",
                started_at=_utc(7),
                finished_at=_utc(8),
                error_summary="Tiendanube 401 access_token=raw_runtime_token",
            ),
        )
        ledger.update_run(run.run_id, status="failed", finished_at=_utc(8))

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    connectors = {item["connector_id"]: item for item in response.get_json()["data"]["connectors"]}
    assert connectors["tn-main"]["last_health"]["run_id"] == "run-main-latest"
    assert connectors["tn-main"]["readiness_state"] == "degraded"
    assert connectors["tn-secondary"]["last_health"] is None
    assert connectors["tn-secondary"]["readiness_state"] == "ready"
    assert connectors["tn-secondary"]["setup_required"] is False


def test_internal_connector_readiness_projects_last_run_certification_summary(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-main",
                    connector_type="tiendanube",
                    label="TiendaNube principal",
                    params={"store_id": "123"},
                    secret_refs={"access_token": "secret://tenant/artemea/tiendanube/main"},
                ),
            ],
        ),
    )
    _append_certified_success_outcome(db_path)

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    connector = response.get_json()["data"]["connectors"][0]
    assert connector["readiness_state"] == "ready"
    assert connector["last_health"] == {
        "run_id": "run-certification-latest",
        "status": "succeeded",
        "health_state": "ok",
        "health_detail": None,
        "started_at": "2026-05-24T09:00:00Z",
        "finished_at": "2026-05-24T10:00:00Z",
        "duration_ms": 3_600_000,
        "error_summary": None,
        "certification": {
            "events": {"status": "passed", "issue_count": 0},
            "metrics": {"status": "warning", "issue_count": 1},
        },
    }


def test_internal_connector_readiness_marks_warning_only_legacy_inline_secret_as_setup_required(
    monkeypatch,
    tmp_path,
):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-inline-mixed",
                    connector_type="tiendanube",
                    label="TiendaNube mixed secret config",
                    params={"store_id": "123", "access_token": "raw_inline_token"},
                    secret_refs={"access_token": "secret://businesses/artemea/connectors/tn-inline-mixed/access_token"},
                ),
            ],
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_inline_token" not in raw_body
    body = response.get_json()
    connector = body["data"]["connectors"][0]
    assert connector["readiness_state"] == "ready"
    assert connector["setup_required"] is True
    assert connector["setup_reason"] == "legacy_inline_secret"
    assert connector["operator_next_step"] == "review_connector_configuration"
    assert connector["auth_requirements"][0]["present"] is True
    assert connector["validation"]["error_count"] == 0
    assert connector["validation"]["warning_count"] == 1
    assert [issue["code"] for issue in connector["validation"]["issues"]] == ["legacy_inline_secret"]


def test_internal_connector_readiness_fails_closed_on_legacy_inline_secret(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-inline",
                    connector_type="tiendanube",
                    label="TiendaNube legacy",
                    params={"store_id": "123", "access_token": "raw_inline_token"},
                ),
            ],
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_inline_token" not in raw_body
    body = response.get_json()
    connector = body["data"]["connectors"][0]
    assert connector["readiness_state"] == "not_ready"
    assert connector["setup_required"] is True
    assert connector["setup_reason"] == "missing_required_secret_ref"
    assert connector["operator_next_step"] == "review_connector_configuration"
    assert connector["auth_requirements"][0]["present"] is False
    assert connector["validation"]["error_count"] == 1
    assert connector["validation"]["warning_count"] == 1
    assert [issue["code"] for issue in connector["validation"]["issues"]] == [
        "missing_required_secret_ref",
        "legacy_inline_secret",
    ]


def test_internal_connector_readiness_redacts_secret_shaped_connector_identifiers(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_business(
        db_path,
        BusinessConfig(
            business_id="artemea",
            business_name="Artemea",
            owner_phone="+5491100000000",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[
                ConnectorConfig(
                    connector_id="tn-main?api_key=raw_identifier_secret",
                    connector_type="unknown?access_token=raw_type_secret",
                    label="Connector token=raw_label_secret",
                    params={},
                ),
            ],
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_identifier_secret" not in raw_body
    assert "raw_type_secret" not in raw_body
    assert "raw_label_secret" not in raw_body
    connector = response.get_json()["data"]["connectors"][0]
    assert connector["connector_id"] == "[REDACTED]"
    assert connector["connector_type"] == "[REDACTED]"
    assert connector["readiness_state"] == "unknown"
    assert connector["supported_runtime_modes"] == []
    assert connector["executor_factory_path"] is None
    assert connector["executor_factory_params"] == []
    assert connector["setup_required"] is True
    assert connector["setup_reason"] == "unknown_connector_type"
    assert connector["operator_next_step"] == "register_or_disable_connector"
    assert connector["label"] == "Connector token=[REDACTED]"
    assert "raw_type_secret" not in connector["validation"]["issues"][0]["message"]


def test_internal_connector_readiness_missing_business_config_is_safe_404(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/connectors/readiness",
        headers=AUTH,
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "business_config_not_found"
    assert body["redaction_applied"] is True
