"""Tests for the additive Orvo Brain run ledger foundation.

TDD: these tests define the ledger contract before implementation.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.brain.run_ledger import (
    ArtifactRef,
    ConnectorRunOutcome,
    DispatchOutcomeRef,
    InMemoryRunLedger,
    RunLedgerStatusError,
)
from app.brain.storage import SQLiteRunLedger, init_schema


def utc_dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 24, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    yield c
    c.close()


def test_in_memory_run_ledger_records_status_transitions_and_artifacts():
    ledger = InMemoryRunLedger()

    run = ledger.create_run(
        run_id="run-1",
        business_id="artemea",
        trigger_type="scheduled",
        started_at=utc_dt(8),
        config_ref="config://businesses/artemea/runtime/daily",
        config_digest="sha256:runtime-v1",
    )

    assert run.status == "running"
    assert run.finished_at is None
    assert run.config_ref == "config://businesses/artemea/runtime/daily"
    assert run.config_digest == "sha256:runtime-v1"

    ledger.append_connector_outcome(
        "run-1",
        ConnectorRunOutcome(
            connector_id="sheet-main",
            connector_type="google_sheets",
            status="succeeded",
            started_at=utc_dt(8),
            finished_at=utc_dt(8, 1),
            metrics_count=5,
            evidence_refs=["evidence://sheet-main/orders/2026-05-24"],
            metadata={"range_name": "Daily!A1:F1000"},
        ),
    )
    ledger.append_artifact_ref(
        "run-1",
        ArtifactRef(
            artifact_id="report-json",
            artifact_type="daily_report",
            uri="memory://run-1/report.json",
            evidence_refs=["evidence://sheet-main/orders/2026-05-24"],
            operational_case_ids=["case-low-conversion"],
            metadata={"metrics_count": 5, "insights_count": 2},
        ),
    )
    ledger.append_dispatch_outcome(
        "run-1",
        DispatchOutcomeRef(
            channel="whatsapp",
            status="sent",
            attempt_number=2,
            idempotency_key="artemea/2026-05-24/daily",
            message_id="wamid.1",
            provider_response_ref="dispatch://whatsapp/wamid.1",
        ),
    )
    finished = ledger.update_run(
        "run-1",
        status="succeeded",
        finished_at=utc_dt(8, 2),
        summary_metadata={"report_type": "daily"},
    )

    assert finished.status == "succeeded"
    assert finished.finished_at == utc_dt(8, 2)
    assert finished.connector_outcomes[0].connector_type == "google_sheets"
    assert finished.connector_outcomes[0].evidence_refs == ["evidence://sheet-main/orders/2026-05-24"]
    assert finished.artifacts[0].artifact_type == "daily_report"
    assert finished.artifacts[0].operational_case_ids == ["case-low-conversion"]
    assert finished.dispatch_outcomes[0].message_id == "wamid.1"
    assert finished.dispatch_outcomes[0].attempt_number == 2
    assert finished.summary_metadata == {"report_type": "daily"}


def test_terminal_run_status_cannot_be_mutated_or_appended_to():
    ledger = InMemoryRunLedger()
    ledger.create_run(run_id="run-terminal", business_id="artemea", trigger_type="forced", started_at=utc_dt(8))
    ledger.update_run("run-terminal", status="failed", finished_at=utc_dt(9), error_summary="boom")

    with pytest.raises(RunLedgerStatusError):
        ledger.update_run("run-terminal", status="running")
    with pytest.raises(RunLedgerStatusError):
        ledger.update_run("run-terminal", summary_metadata={"retry": True})
    with pytest.raises(RunLedgerStatusError):
        ledger.append_artifact_ref(
            "run-terminal",
            ArtifactRef(artifact_id="late", artifact_type="daily_report"),
        )


def test_terminal_status_requires_finished_at_and_valid_time_order():
    ledger = InMemoryRunLedger()
    ledger.create_run(run_id="run-time", business_id="artemea", trigger_type="scheduled", started_at=utc_dt(10))

    with pytest.raises(RunLedgerStatusError):
        ledger.update_run("run-time", status="succeeded")
    with pytest.raises(ValueError, match="finished_at must be after"):
        ledger.update_run("run-time", status="succeeded", finished_at=utc_dt(9))


def test_secret_redaction_covers_common_metadata_keys_error_text_and_reference_uris():
    outcome = ConnectorRunOutcome(
        connector_id="meta-main",
        connector_type="meta_ads",
        status="failed",
        started_at=utc_dt(8),
        error_summary="request failed with Bearer abc123 and api_key=supersecret",
        metadata={
            "token": "plain-token",
            "credential_blob": {"cookie": "session-cookie", "safe": "ok"},
        },
    )

    assert outcome.metadata == {
        "token": "[REDACTED]",
        "credential_blob": "[REDACTED]",
    }
    assert outcome.error_summary is not None
    assert "abc123" not in outcome.error_summary
    assert "supersecret" not in outcome.error_summary

    artifact = ArtifactRef(
        artifact_id="signed-report",
        artifact_type="daily_report",
        uri="https://artifacts.example/report.json?access_token=raw-token&signature=sig-secret&safe=ok",
    )
    dispatch = DispatchOutcomeRef(
        channel="whatsapp",
        status="failed",
        provider_response_ref="https://gateway.example/messages/1?authorization=raw-secret&safe=ok",
    )
    run = InMemoryRunLedger().create_run(
        run_id="run-secret-config",
        business_id="artemea",
        trigger_type="manual",
        config_ref="https://config.example/runtime?token=config-secret&version=1",
        summary_metadata={
            "connector_refs": [
                {
                    "connector_id": "tn-main",
                    "secret_refs": {
                        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
                    },
                }
            ]
        },
    )

    assert run.summary_metadata["connector_refs"][0]["secret_refs"] == {"access_token": "[REDACTED]"}
    assert "secret://businesses/artemea" not in run.model_dump_json()
    assert "raw-token" not in (artifact.uri or "")
    assert "sig-secret" not in (artifact.uri or "")
    assert "raw-secret" not in (dispatch.provider_response_ref or "")
    assert "config-secret" not in (run.config_ref or "")
    assert "safe=ok" in (artifact.uri or "")


def test_connector_run_outcome_defaults_registry_health_state_from_status():
    succeeded = ConnectorRunOutcome(
        connector_id="tn-main",
        connector_type="tiendanube",
        status="succeeded",
        started_at=utc_dt(8),
        finished_at=utc_dt(8, 1),
    )
    failed = ConnectorRunOutcome(
        connector_id="tn-main",
        connector_type="tiendanube",
        status="failed",
        started_at=utc_dt(8),
        finished_at=utc_dt(8, 1),
    )
    skipped = ConnectorRunOutcome(
        connector_id="sample-main",
        connector_type="sample",
        status="skipped",
        started_at=utc_dt(8),
    )
    explicit = ConnectorRunOutcome(
        connector_id="tn-main",
        connector_type="tiendanube",
        status="failed",
        health_state="unauthorized",
        started_at=utc_dt(8),
        finished_at=utc_dt(8, 1),
    )

    assert succeeded.health_state == "ok"
    assert failed.health_state == "failed"
    assert skipped.health_state == "degraded"
    assert explicit.health_state == "unauthorized"
    assert explicit.model_dump()["health_state"] == "unauthorized"


def test_sqlite_run_ledger_persists_records_and_lists_newest_first(conn):
    first = SQLiteRunLedger(conn).create_run(
        run_id="run-old",
        business_id="artemea",
        trigger_type="scheduled",
        started_at=utc_dt(7),
    )
    SQLiteRunLedger(conn).update_run(first.run_id, status="succeeded", finished_at=utc_dt(7, 5))

    ledger = SQLiteRunLedger(conn)
    ledger.create_run(
        run_id="run-new",
        business_id="artemea",
        trigger_type="forced",
        started_at=utc_dt(8),
    )
    ledger.append_connector_outcome(
        "run-new",
        ConnectorRunOutcome(
            connector_id="tn-main",
            connector_type="tiendanube",
            status="failed",
            started_at=utc_dt(8),
            finished_at=utc_dt(8, 1),
            error_summary="HTTP 401",
            metadata={"store_id": "123", "access_token": "tn_secret_token"},
        ),
    )
    ledger.append_artifact_ref(
        "run-new",
        ArtifactRef(
            artifact_id="summary",
            artifact_type="summary_metadata",
            metadata={"refresh_token": "oauth_secret", "metrics_count": 0},
        ),
    )
    ledger.append_dispatch_outcome(
        "run-new",
        DispatchOutcomeRef(
            channel="whatsapp",
            status="failed",
            idempotency_key="artemea/2026-05-24/daily",
            error_summary="delivery rejected",
        ),
    )
    ledger.update_run("run-new", status="failed", finished_at=utc_dt(8, 2), summary_metadata={"api_key": "secret"})

    reloaded = SQLiteRunLedger(conn).get_run("run-new")
    assert reloaded is not None
    assert reloaded.business_id == "artemea"
    assert reloaded.trigger_type == "forced"
    assert reloaded.status == "failed"
    assert reloaded.connector_outcomes[0].metadata == {
        "store_id": "123",
        "access_token": "[REDACTED]",
    }
    assert reloaded.artifacts[0].metadata == {"refresh_token": "[REDACTED]", "metrics_count": 0}
    assert reloaded.summary_metadata == {"api_key": "[REDACTED]"}
    assert reloaded.dispatch_outcomes[0].status == "failed"

    runs = SQLiteRunLedger(conn).list_runs(business_id="artemea")
    assert [run.run_id for run in runs] == ["run-new", "run-old"]
    assert [run.run_id for run in SQLiteRunLedger(conn).list_runs(business_id="artemea", limit=1)] == ["run-new"]


def test_sqlite_run_ledger_records_failed_secondary_dispatch_as_terminal_partial(conn):
    ledger = SQLiteRunLedger(conn)
    ledger.create_run(
        run_id="run-secondary-dispatch-failed",
        business_id="artemea",
        trigger_type="scheduled",
        started_at=utc_dt(8),
    )
    ledger.append_connector_outcome(
        "run-secondary-dispatch-failed",
        ConnectorRunOutcome(
            connector_id="tn-main",
            connector_type="tiendanube",
            status="succeeded",
            started_at=utc_dt(8),
            finished_at=utc_dt(8, 1),
            metrics_count=7,
        ),
    )
    ledger.append_dispatch_outcome(
        "run-secondary-dispatch-failed",
        DispatchOutcomeRef(
            channel="whatsapp_daily_report",
            status="sent",
            idempotency_key="artemea/2026-05-24/daily-report",
            message_id="wamid.primary",
        ),
    )
    ledger.append_dispatch_outcome(
        "run-secondary-dispatch-failed",
        DispatchOutcomeRef(
            channel="whatsapp_owner_case_brief",
            status="failed",
            idempotency_key="artemea/2026-05-24/owner-case-brief",
            error_summary="secondary dispatch failed Authorization: Basic raw_secondary_dispatch_secret",
            metadata={"provider_token": "raw_secondary_metadata_secret"},
        ),
    )

    finished = ledger.update_run(
        "run-secondary-dispatch-failed",
        status="partial",
        finished_at=utc_dt(8, 2),
        summary_metadata={
            "primary_dispatch_status": "sent",
            "secondary_dispatch_status": "failed",
        },
    )

    assert finished.status == "partial"
    assert finished.finished_at == utc_dt(8, 2)
    assert [outcome.status for outcome in finished.connector_outcomes] == ["succeeded"]
    assert [(outcome.channel, outcome.status) for outcome in finished.dispatch_outcomes] == [
        ("whatsapp_daily_report", "sent"),
        ("whatsapp_owner_case_brief", "failed"),
    ]
    assert finished.dispatch_outcomes[1].error_summary == "secondary dispatch failed Authorization: [REDACTED]"
    assert finished.dispatch_outcomes[1].metadata == {"provider_token": "[REDACTED]"}
    assert "raw_secondary" not in finished.model_dump_json()

    reloaded = SQLiteRunLedger(conn).get_run("run-secondary-dispatch-failed")
    assert reloaded is not None
    assert reloaded.status == "partial"
    assert reloaded.dispatch_outcomes[1].channel == "whatsapp_owner_case_brief"
    assert "raw_secondary" not in reloaded.model_dump_json()
    with pytest.raises(RunLedgerStatusError):
        ledger.append_dispatch_outcome(
            "run-secondary-dispatch-failed",
            DispatchOutcomeRef(channel="whatsapp_owner_case_brief", status="queued"),
        )


def test_sqlite_run_ledger_list_runs_can_filter_by_status(conn):
    ledger = SQLiteRunLedger(conn)
    ledger.create_run(run_id="run-ok", business_id="artemea", trigger_type="scheduled", started_at=utc_dt(8))
    ledger.update_run("run-ok", status="succeeded", finished_at=utc_dt(8, 1))
    ledger.create_run(run_id="run-fail", business_id="artemea", trigger_type="forced", started_at=utc_dt(9))
    ledger.update_run("run-fail", status="failed", finished_at=utc_dt(9, 1))

    failed = ledger.list_runs(business_id="artemea", status="failed")

    assert [run.run_id for run in failed] == ["run-fail"]
