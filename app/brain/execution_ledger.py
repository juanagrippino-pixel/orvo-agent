"""Helpers that record real report execution into the run ledger.

The runner/script remain responsible for executing existing report pipelines. This
module owns the compatibility shim between those legacy pipeline results and the
control-plane run ledger contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.brain.config import BusinessConfig
from app.brain.operational_cases import (
    OperationalCaseStore,
    upsert_cases_from_report,
    upsert_data_stale_cases,
)
from app.brain.pipeline import PipelineResult
from app.brain.run_ledger import ArtifactRef, ConnectorRunOutcome, DispatchOutcomeRef, RunLedger


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def begin_pipeline_run(
    *,
    run_ledger: RunLedger | None,
    business_id: str,
    trigger_type: str,
    runtime_metadata: dict[str, Any],
    summary_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a running ledger record and return runtime metadata with run_id.

    If no ledger is supplied, the returned metadata is unchanged so existing
    callers preserve their old behavior.
    """

    if run_ledger is None:
        return dict(runtime_metadata)

    merged_summary = {
        "runtime_id": runtime_metadata.get("runtime_id"),
        "compiled_from_hash": runtime_metadata.get("compiled_from_hash"),
        "run_mode": runtime_metadata.get("run_mode"),
        "connector_types": runtime_metadata.get("connector_types", []),
        "report_types": runtime_metadata.get("report_types", []),
        **(summary_metadata or {}),
    }
    run = run_ledger.create_run(
        business_id=business_id,
        trigger_type=trigger_type,  # type: ignore[arg-type]
        config_ref=runtime_metadata.get("config_ref"),
        config_digest=runtime_metadata.get("config_digest"),
        summary_metadata=merged_summary,
    )
    return {**runtime_metadata, "run_id": run.run_id}


def _connector_by_type(business: BusinessConfig, connector_types: Sequence[str]):
    for connector_type in connector_types:
        connector = next(
            (
                candidate
                for candidate in business.connectors
                if candidate.enabled and candidate.connector_type == connector_type
            ),
            None,
        )
        if connector is not None:
            yield connector


def _metric_count_for_connector(pipeline: PipelineResult, connector_type: str, connector_count: int) -> int:
    if connector_count == 1:
        return len(pipeline.report.metrics)
    return sum(
        1
        for metric in pipeline.report.metrics
        if any(evidence.source == connector_type for evidence in metric.evidence)
    )


def record_pipeline_success(
    *,
    run_ledger: RunLedger | None,
    case_store: OperationalCaseStore | None = None,
    run_id: str | None,
    business: BusinessConfig,
    connector_types: Sequence[str],
    pipeline: PipelineResult,
    summary_metadata: dict[str, Any] | None = None,
) -> None:
    """Append successful connector/artifact/dispatch records and finish the run."""

    if run_ledger is None or run_id is None:
        return

    finished_at = _now_utc()
    connectors = list(_connector_by_type(business, connector_types))
    connector_count = max(len(connectors), 1)
    for connector in connectors:
        run_ledger.append_connector_outcome(
            run_id,
            ConnectorRunOutcome(
                connector_id=connector.connector_id,
                connector_type=connector.connector_type,
                status="succeeded",
                started_at=finished_at,
                finished_at=finished_at,
                metrics_count=_metric_count_for_connector(pipeline, connector.connector_type, connector_count),
                evidence_refs=[f"evidence://{connector.connector_id}/{pipeline.report.report_date.isoformat()}"],
                metadata={"label": connector.label},
            ),
        )

    artifact_uri = f"ledger://runs/{run_id}/daily-report"
    case_summary = upsert_cases_from_report(
        case_store=case_store,
        business_id=business.business_id,
        report=pipeline.report,
        run_id=run_id,
        artifact_ref=artifact_uri,
    )

    run_ledger.append_artifact_ref(
        run_id,
        ArtifactRef(
            artifact_id=f"{run_id}:daily_report",
            artifact_type="daily_report",
            uri=artifact_uri,
            evidence_refs=[
                f"evidence://{connector.connector_id}/{pipeline.report.report_date.isoformat()}"
                for connector in connectors
            ],
            operational_case_ids=case_summary.case_ids,
            metadata={
                "report_date": pipeline.report.report_date.isoformat(),
                "metrics_count": len(pipeline.report.metrics),
                "insights_count": len(pipeline.report.insights),
            },
        ),
    )

    dispatch = pipeline.dispatch
    delivery = dispatch.delivery
    run_ledger.append_dispatch_outcome(
        run_id,
        DispatchOutcomeRef(
            channel="whatsapp",
            status=dispatch.status,
            idempotency_key=dispatch.idempotency_key,
            message_id=delivery.message_id if delivery else None,
            error_summary=dispatch.error or (delivery.error if delivery else None),
        ),
    )

    final_status = "succeeded" if dispatch.status in {"sent", "skipped_duplicate"} else "partial"
    run_ledger.update_run(
        run_id,
        status=final_status,  # type: ignore[arg-type]
        finished_at=finished_at,
        summary_metadata={
            "report_type": "daily",
            "cases_opened": case_summary.opened_count,
            "cases_updated": case_summary.updated_count,
            **(summary_metadata or {}),
        },
    )


def record_pipeline_failure(
    *,
    run_ledger: RunLedger | None,
    case_store: OperationalCaseStore | None = None,
    run_id: str | None,
    error: BaseException,
    business_id: str | None = None,
    connector_types: Sequence[str] | None = None,
    summary_metadata: dict[str, Any] | None = None,
) -> None:
    """Mark a running ledger record as failed and open/update data_stale cases."""

    error_summary = f"{type(error).__name__}: {error}"
    case_summary = upsert_data_stale_cases(
        case_store=case_store,
        business_id=business_id,
        connector_types=list(connector_types or []),
        run_id=run_id,
        error_summary=error_summary,
    )
    if run_ledger is None or run_id is None:
        return
    run_ledger.update_run(
        run_id,
        status="failed",
        finished_at=_now_utc(),
        summary_metadata={
            "cases_opened": case_summary.opened_count,
            "cases_updated": case_summary.updated_count,
            **(summary_metadata or {}),
        },
        error_summary=error_summary,
    )
