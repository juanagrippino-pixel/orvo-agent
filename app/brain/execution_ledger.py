"""Helpers that record real report execution into the run ledger.

The runner/script remain responsible for executing existing report pipelines. This
module owns the compatibility shim between those legacy pipeline results and the
control-plane run ledger contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from app.brain.config import BusinessConfig
from app.brain.operational_cases import (
    OperationalCase,
    OperationalCaseStore,
    upsert_cases_from_report,
    upsert_data_stale_cases,
)
from app.brain.dispatch import ReportDispatchResult
from app.brain.delivery import make_idempotency_key
from app.brain.pipeline import PipelineResult
from app.brain.run_ledger import ArtifactRef, ConnectorRunOutcome, DispatchOutcomeRef, RunLedger
from app.brain.security.redaction import redact_text


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


def _owner_brief_cases(case_store: OperationalCaseStore, business_id: str) -> list[OperationalCase]:
    cases: list[OperationalCase] = []
    for status in ("open", "acknowledged"):
        cases.extend(case_store.list_cases(business_id=business_id, status=status, limit=None))
    return cases


def _dispatch_outcome(
    dispatch: ReportDispatchResult,
    *,
    message_type: str,
    metadata: dict[str, Any] | None = None,
) -> DispatchOutcomeRef:
    delivery = dispatch.delivery
    return DispatchOutcomeRef(
        channel="whatsapp",
        status=dispatch.status,
        idempotency_key=dispatch.idempotency_key,
        message_id=delivery.message_id if delivery else None,
        error_summary=dispatch.error or (delivery.error if delivery else None),
        metadata={"message_type": message_type, **(metadata or {})},
    )


def _failed_connector_outcomes(
    *,
    business: BusinessConfig | None,
    connector_types: Sequence[str] | None,
    error_summary: str,
    failed_at: datetime,
) -> list[ConnectorRunOutcome]:
    """Build exact failed connector outcomes when the failed connector is unambiguous."""

    if business is None or not connector_types:
        return []

    exact_types = list(dict.fromkeys(connector_types))
    matching_connectors = [
        connector
        for connector in business.connectors
        if connector.enabled and connector.connector_type in exact_types
    ]
    if len(exact_types) != 1 or len(matching_connectors) != 1:
        return []

    connector = matching_connectors[0]
    return [
        ConnectorRunOutcome(
            connector_id=connector.connector_id,
            connector_type=connector.connector_type,
            status="failed",
            started_at=failed_at,
            finished_at=failed_at,
            error_summary=error_summary,
            metadata={"label": connector.label, "failure_stage": "pre_dispatch"},
        )
    ]


def record_pipeline_success(
    *,
    run_ledger: RunLedger | None,
    case_store: OperationalCaseStore | None = None,
    run_id: str | None,
    business: BusinessConfig,
    connector_types: Sequence[str],
    pipeline: PipelineResult,
    summary_metadata: dict[str, Any] | None = None,
    case_brief_dispatcher: Callable[[Sequence[OperationalCase]], ReportDispatchResult | None] | None = None,
) -> ReportDispatchResult | None:
    """Append successful connector/artifact/dispatch records and finish the run."""

    if run_ledger is None or run_id is None:
        return None

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
    run_ledger.append_dispatch_outcome(
        run_id,
        _dispatch_outcome(dispatch, message_type="daily_report"),
    )

    case_brief_dispatch: ReportDispatchResult | None = None
    if case_store is not None and case_brief_dispatcher is not None and dispatch.status in {"sent", "skipped_duplicate"}:
        owner_cases = _owner_brief_cases(case_store, business.business_id)
        try:
            case_brief_dispatch = case_brief_dispatcher(owner_cases)
        except Exception as exc:  # keep the run ledger terminal even if the secondary brief fails unexpectedly
            case_brief_dispatch = ReportDispatchResult(
                status="failed",
                idempotency_key=make_idempotency_key(
                    business.business_id,
                    pipeline.report.report_date,
                    "owner_case_brief",
                ),
                error=redact_text(f"{type(exc).__name__}: {exc}"),
            )
        if case_brief_dispatch is not None:
            run_ledger.append_dispatch_outcome(
                run_id,
                _dispatch_outcome(
                    case_brief_dispatch,
                    message_type="owner_case_brief",
                    metadata={"case_count": len(owner_cases)},
                ),
            )

    dispatch_ok = dispatch.status in {"sent", "skipped_duplicate"}
    case_brief_ok = case_brief_dispatch is None or case_brief_dispatch.status in {"sent", "skipped_duplicate"}
    final_status = "succeeded" if dispatch_ok and case_brief_ok else "partial"
    final_summary = {
        "report_type": "daily",
        "cases_opened": case_summary.opened_count,
        "cases_updated": case_summary.updated_count,
        **(summary_metadata or {}),
    }
    if case_brief_dispatch is not None:
        final_summary["case_brief_dispatch_status"] = case_brief_dispatch.status
    run_ledger.update_run(
        run_id,
        status=final_status,  # type: ignore[arg-type]
        finished_at=finished_at,
        summary_metadata=final_summary,
    )
    return case_brief_dispatch


def record_pipeline_failure(
    *,
    run_ledger: RunLedger | None,
    case_store: OperationalCaseStore | None = None,
    run_id: str | None,
    error: BaseException,
    business: BusinessConfig | None = None,
    business_id: str | None = None,
    connector_types: Sequence[str] | None = None,
    summary_metadata: dict[str, Any] | None = None,
) -> None:
    """Record failed connector context, mark run failed, and open/update data_stale cases."""

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
    failed_at = _now_utc()
    for outcome in _failed_connector_outcomes(
        business=business,
        connector_types=connector_types,
        error_summary=error_summary,
        failed_at=failed_at,
    ):
        run_ledger.append_connector_outcome(run_id, outcome)
    run_ledger.update_run(
        run_id,
        status="failed",
        finished_at=failed_at,
        summary_metadata={
            "cases_opened": case_summary.opened_count,
            "cases_updated": case_summary.updated_count,
            **(summary_metadata or {}),
        },
        error_summary=error_summary,
    )
