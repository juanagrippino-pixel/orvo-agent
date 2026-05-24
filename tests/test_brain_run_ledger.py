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
    )

    assert run.status == "running"
    assert run.finished_at is None

    ledger.append_connector_outcome(
        "run-1",
        ConnectorRunOutcome(
            connector_id="sheet-main",
            connector_type="google_sheets",
            status="succeeded",
            started_at=utc_dt(8),
            finished_at=utc_dt(8, 1),
            metrics_count=5,
            metadata={"range_name": "Daily!A1:F1000"},
        ),
    )
    ledger.append_artifact_ref(
        "run-1",
        ArtifactRef(
            artifact_id="report-json",
            artifact_type="daily_report",
            uri="memory://run-1/report.json",
            metadata={"metrics_count": 5, "insights_count": 2},
        ),
    )
    ledger.append_dispatch_outcome(
        "run-1",
        DispatchOutcomeRef(
            channel="whatsapp",
            status="sent",
            idempotency_key="artemea/2026-05-24/daily",
            message_id="wamid.1",
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
    assert finished.artifacts[0].artifact_type == "daily_report"
    assert finished.dispatch_outcomes[0].message_id == "wamid.1"
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


def test_secret_redaction_covers_common_metadata_keys_and_error_text():
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


def test_sqlite_run_ledger_list_runs_can_filter_by_status(conn):
    ledger = SQLiteRunLedger(conn)
    ledger.create_run(run_id="run-ok", business_id="artemea", trigger_type="scheduled", started_at=utc_dt(8))
    ledger.update_run("run-ok", status="succeeded", finished_at=utc_dt(8, 1))
    ledger.create_run(run_id="run-fail", business_id="artemea", trigger_type="forced", started_at=utc_dt(9))
    ledger.update_run("run-fail", status="failed", finished_at=utc_dt(9, 1))

    failed = ledger.list_runs(business_id="artemea", status="failed")

    assert [run.run_id for run in failed] == ["run-fail"]
