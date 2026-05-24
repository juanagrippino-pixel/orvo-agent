"""Native Operational Cases for Orvo Brain.

Cases are deterministic, evidence-backed work items derived from report insights.
They are the control-plane source of truth for follow-up state; WhatsApp/report
surfaces are projections of this state, not owners of lifecycle.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.brain.models import DailyReport, Insight
from app.brain.security.redaction import redact_secrets, redact_text, redact_uri

OperationalCaseStatus = Literal["open", "acknowledged", "resolved"]
OperationalCaseType = Literal[
    "sales_drop",
    "stockout_risk",
    "spend_without_orders",
    "data_stale",
    "unanswered_conversations",
    "channel_mix_shift",
]
OperationalCaseSeverity = Literal["info", "warning", "critical"]
TimelineEventType = Literal["case_opened", "case_updated", "case_reopened", "status_changed"]
ActorType = Literal["system", "operator"]

_CASE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged"},
    "acknowledged": {"resolved"},
    "resolved": set(),
}


class OperationalCaseStatusError(ValueError):
    """Raised when a case lifecycle transition is invalid."""


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("operational case timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _safe_metadata(value: Any) -> dict[str, Any]:
    redacted = redact_secrets(value or {})
    return redacted if isinstance(redacted, dict) else {}


class OperationalCaseTimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: TimelineEventType
    actor_type: ActorType = "system"
    actor_ref: str = "orvo_runtime"
    run_id: str | None = None
    created_at: datetime = Field(default_factory=_now_utc)
    summary: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_validator("summary", mode="before")
    @classmethod
    def redact_summary(cls, value: str) -> str:
        return redact_text(value) or "[REDACTED]"

    @field_validator("metadata", mode="before")
    @classmethod
    def redact_metadata_values(cls, value: Any) -> dict[str, Any]:
        return _safe_metadata(value)


class OperationalCaseDetection(BaseModel):
    """Deterministic detection input used to open or update a case."""

    business_id: str = Field(..., min_length=1)
    case_type: OperationalCaseType
    dedupe_key: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    severity: OperationalCaseSeverity
    priority_score: int = Field(..., ge=0, le=100)
    entity_scope: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    run_id: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", mode="before")
    @classmethod
    def redact_title(cls, value: str) -> str:
        return redact_text(value) or "[REDACTED]"

    @field_validator("metadata", "entity_scope", mode="before")
    @classmethod
    def redact_dict_values(cls, value: Any) -> dict[str, Any]:
        return _safe_metadata(value)

    @field_validator("artifact_refs", "evidence_refs", mode="before")
    @classmethod
    def redact_ref_values(cls, value: Any) -> list[str]:
        return [redact_uri(str(item)) or "[REDACTED]" for item in (value or [])]


class OperationalCase(BaseModel):
    case_id: str = Field(..., min_length=1)
    business_id: str = Field(..., min_length=1)
    case_type: OperationalCaseType
    dedupe_key: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status: OperationalCaseStatus = "open"
    severity: OperationalCaseSeverity
    priority_score: int = Field(..., ge=0, le=100)
    entity_scope: dict[str, Any] = Field(default_factory=dict)
    opened_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    latest_run_id: str | None = None
    source_run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    timeline: list[OperationalCaseTimelineEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", mode="before")
    @classmethod
    def redact_title(cls, value: str) -> str:
        return redact_text(value) or "[REDACTED]"

    @field_validator("opened_at", "updated_at", "acknowledged_at", "resolved_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None

    @field_validator("metadata", "entity_scope", mode="before")
    @classmethod
    def redact_dict_values(cls, value: Any) -> dict[str, Any]:
        return _safe_metadata(value)

    @field_validator("artifact_refs", "evidence_refs", mode="before")
    @classmethod
    def redact_ref_values(cls, value: Any) -> list[str]:
        return [redact_uri(str(item)) or "[REDACTED]" for item in (value or [])]

    @model_validator(mode="after")
    def validate_lifecycle_times(self) -> "OperationalCase":
        if self.updated_at < self.opened_at:
            raise ValueError("updated_at must be after opened_at")
        if self.acknowledged_at is not None and self.acknowledged_at < self.opened_at:
            raise ValueError("acknowledged_at must be after opened_at")
        if self.resolved_at is not None and self.resolved_at < self.opened_at:
            raise ValueError("resolved_at must be after opened_at")
        if self.status == "resolved" and self.resolved_at is None:
            raise ValueError("resolved case requires resolved_at")
        return self


class OperationalCaseStore(Protocol):
    def upsert_detection(
        self,
        detection: OperationalCaseDetection,
        *,
        detected_at: datetime | None = None,
    ) -> OperationalCase: ...

    def transition_case(
        self,
        case_id: str,
        *,
        status: OperationalCaseStatus,
        actor_type: ActorType,
        actor_ref: str,
        reason: str | None = None,
        transitioned_at: datetime | None = None,
    ) -> OperationalCase: ...

    def get_case(self, case_id: str) -> OperationalCase | None: ...
    def find_by_dedupe_key(self, business_id: str, dedupe_key: str) -> OperationalCase | None: ...
    def list_cases(
        self,
        *,
        business_id: str | None = None,
        status: OperationalCaseStatus | None = None,
        limit: int | None = 100,
    ) -> list[OperationalCase]: ...


class _OperationalCaseMutations:
    def _persist(self, record: OperationalCase) -> None:
        raise NotImplementedError

    def _load_for_update(self, case_id: str) -> OperationalCase:
        record = self.get_case(case_id)  # type: ignore[attr-defined]
        if record is None:
            raise KeyError(f"case not found: {case_id}")
        return record

    def upsert_detection(
        self,
        detection: OperationalCaseDetection,
        *,
        detected_at: datetime | None = None,
    ) -> OperationalCase:
        detected_at = _as_utc(detected_at) if detected_at is not None else _now_utc()
        existing = self.find_by_dedupe_key(detection.business_id, detection.dedupe_key)  # type: ignore[attr-defined]
        if existing is None:
            case = OperationalCase(
                case_id=str(uuid4()),
                business_id=detection.business_id,
                case_type=detection.case_type,
                dedupe_key=detection.dedupe_key,
                title=detection.title,
                status="open",
                severity=detection.severity,
                priority_score=detection.priority_score,
                entity_scope=detection.entity_scope,
                opened_at=detected_at,
                updated_at=detected_at,
                latest_run_id=detection.run_id,
                source_run_ids=[detection.run_id] if detection.run_id else [],
                evidence_refs=_unique(detection.evidence_refs),
                artifact_refs=_unique(detection.artifact_refs),
                metadata=detection.metadata,
                timeline=[
                    OperationalCaseTimelineEvent(
                        event_type="case_opened",
                        actor_type="system",
                        actor_ref="orvo_runtime",
                        run_id=detection.run_id,
                        created_at=detected_at,
                        summary=f"Opened {detection.case_type} case from deterministic detection.",
                        metadata={"dedupe_key": detection.dedupe_key},
                    )
                ],
            )
        else:
            is_recurrence = existing.status == "resolved"
            event_type: TimelineEventType = "case_reopened" if is_recurrence else "case_updated"
            event_verb = "Reopened" if is_recurrence else "Updated"
            update: dict[str, Any] = {
                "title": detection.title,
                "status": "open" if is_recurrence else existing.status,
                "severity": detection.severity,
                "priority_score": detection.priority_score,
                "entity_scope": detection.entity_scope or existing.entity_scope,
                "updated_at": detected_at,
                "latest_run_id": detection.run_id or existing.latest_run_id,
                "source_run_ids": _unique([
                    *existing.source_run_ids,
                    *([detection.run_id] if detection.run_id else []),
                ]),
                "evidence_refs": _unique([*existing.evidence_refs, *detection.evidence_refs]),
                "artifact_refs": _unique([*existing.artifact_refs, *detection.artifact_refs]),
                "metadata": {**existing.metadata, **detection.metadata},
                "timeline": [
                    *existing.timeline,
                    OperationalCaseTimelineEvent(
                        event_type=event_type,
                        actor_type="system",
                        actor_ref="orvo_runtime",
                        run_id=detection.run_id,
                        created_at=detected_at,
                        summary=f"{event_verb} {detection.case_type} case from deterministic detection.",
                        metadata={"dedupe_key": detection.dedupe_key},
                    ),
                ],
            }
            if is_recurrence:
                update["resolved_at"] = None
                update["acknowledged_at"] = None
            case = existing.model_copy(update=update, deep=True)
            case = OperationalCase.model_validate(case.model_dump())
        self._persist(case)
        return case.model_copy(deep=True)

    def transition_case(
        self,
        case_id: str,
        *,
        status: OperationalCaseStatus,
        actor_type: ActorType,
        actor_ref: str,
        reason: str | None = None,
        transitioned_at: datetime | None = None,
    ) -> OperationalCase:
        record = self._load_for_update(case_id)
        if status == record.status:
            raise OperationalCaseStatusError(f"case {case_id} already has status {status}")
        if status not in _CASE_STATUS_TRANSITIONS[record.status]:
            raise OperationalCaseStatusError(f"case {case_id} cannot transition from {record.status} to {status}")
        transitioned_at = _as_utc(transitioned_at) if transitioned_at is not None else _now_utc()
        update: dict[str, Any] = {
            "status": status,
            "updated_at": transitioned_at,
            "timeline": [
                *record.timeline,
                OperationalCaseTimelineEvent(
                    event_type="status_changed",
                    actor_type=actor_type,
                    actor_ref=actor_ref,
                    created_at=transitioned_at,
                    summary=reason or f"Status changed from {record.status} to {status}.",
                    metadata={"from_status": record.status, "to_status": status},
                ),
            ],
        }
        if status == "acknowledged":
            update["acknowledged_at"] = transitioned_at
        if status == "resolved":
            update["resolved_at"] = transitioned_at
        updated = record.model_copy(update=update, deep=True)
        updated = OperationalCase.model_validate(updated.model_dump())
        self._persist(updated)
        return updated.model_copy(deep=True)


class InMemoryOperationalCaseStore(_OperationalCaseMutations):
    def __init__(self) -> None:
        self._cases: dict[str, OperationalCase] = {}

    def _persist(self, record: OperationalCase) -> None:
        self._cases[record.case_id] = record.model_copy(deep=True)

    def get_case(self, case_id: str) -> OperationalCase | None:
        record = self._cases.get(case_id)
        return record.model_copy(deep=True) if record is not None else None

    def find_by_dedupe_key(self, business_id: str, dedupe_key: str) -> OperationalCase | None:
        for record in self._cases.values():
            if record.business_id == business_id and record.dedupe_key == dedupe_key:
                return record.model_copy(deep=True)
        return None

    def list_cases(
        self,
        *,
        business_id: str | None = None,
        status: OperationalCaseStatus | None = None,
        limit: int | None = 100,
    ) -> list[OperationalCase]:
        records = list(self._cases.values())
        if business_id is not None:
            records = [record for record in records if record.business_id == business_id]
        if status is not None:
            records = [record for record in records if record.status == status]
        records.sort(key=lambda record: (-record.priority_score, record.opened_at, record.case_id))
        if limit is not None:
            records = records[:limit]
        return [record.model_copy(deep=True) for record in records]


class SQLiteOperationalCaseStore(_OperationalCaseMutations):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _persist(self, record: OperationalCase) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO operational_cases
                (case_id, business_id, dedupe_key, status, case_type, priority_score, opened_at, updated_at, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.case_id,
                record.business_id,
                record.dedupe_key,
                record.status,
                record.case_type,
                record.priority_score,
                record.opened_at.isoformat(),
                record.updated_at.isoformat(),
                record.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_case(self, case_id: str) -> OperationalCase | None:
        cursor = self._conn.execute("SELECT data FROM operational_cases WHERE case_id = ?", (case_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return OperationalCase.model_validate_json(row[0])

    def find_by_dedupe_key(self, business_id: str, dedupe_key: str) -> OperationalCase | None:
        cursor = self._conn.execute(
            "SELECT data FROM operational_cases WHERE business_id = ? AND dedupe_key = ?",
            (business_id, dedupe_key),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return OperationalCase.model_validate_json(row[0])

    def list_cases(
        self,
        *,
        business_id: str | None = None,
        status: OperationalCaseStatus | None = None,
        limit: int | None = 100,
    ) -> list[OperationalCase]:
        clauses: list[str] = []
        params: list[str | int] = []
        if business_id is not None:
            clauses.append("business_id = ?")
            params.append(business_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT data FROM operational_cases"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY priority_score DESC, opened_at ASC, case_id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        cursor = self._conn.execute(query, tuple(params))
        return [OperationalCase.model_validate_json(row[0]) for row in cursor.fetchall()]


def _priority_for_severity(severity: OperationalCaseSeverity) -> int:
    return {"critical": 100, "warning": 70, "info": 30}[severity]


def _case_type_for_insight(insight: Insight) -> OperationalCaseType | None:
    title = insight.title.lower()
    if insight.severity == "info":
        return None
    if "stock" in title:
        return "stockout_risk"
    if "sin ventas" in title or "roas bajo" in title:
        return "spend_without_orders"
    if "conversaciones" in title:
        return "unanswered_conversations"
    if "tiendanube" in title or "canal" in title:
        return "channel_mix_shift"
    if "ventas" in title:
        return "sales_drop"
    return None


def _dedupe_key(business_id: str, case_type: OperationalCaseType) -> str:
    suffix_by_type = {
        "sales_drop": "sales_drop/channel/all/commerce.revenue/daily",
        "stockout_risk": "stockout_risk/business/monitored/commerce.inventory/daily",
        "spend_without_orders": "spend_without_orders/channel/meta_ads/ads.spend/daily",
        "data_stale": "data_stale/connector/unknown/runtime.freshness/daily",
        "unanswered_conversations": "unanswered_conversations/channel/whatsapp/support.conversations/daily",
        "channel_mix_shift": "channel_mix_shift/business/all_channels/commerce.revenue/daily",
    }
    return f"{business_id}/{suffix_by_type[case_type]}"


def _entity_scope(case_type: OperationalCaseType) -> dict[str, str]:
    return {
        "sales_drop": {"kind": "channel", "id": "all", "label": "Canales monitoreados"},
        "stockout_risk": {"kind": "business", "id": "monitored", "label": "Productos monitoreados"},
        "spend_without_orders": {"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
        "data_stale": {"kind": "connector", "id": "unknown", "label": "Unknown connector"},
        "unanswered_conversations": {"kind": "channel", "id": "whatsapp", "label": "WhatsApp"},
        "channel_mix_shift": {"kind": "business", "id": "all_channels", "label": "Todos los canales"},
    }[case_type]


def _evidence_refs_for_insight(insight: Insight, report: DailyReport, case_type: OperationalCaseType) -> list[str]:
    sources = _unique([evidence.source for evidence in insight.evidence])
    return [f"evidence://{source}/{report.report_date.isoformat()}/{case_type}" for source in sources]


def make_data_stale_detection(
    *,
    business_id: str,
    connector_type: str,
    run_id: str | None = None,
    error_summary: str | None = None,
) -> OperationalCaseDetection:
    """Build the catalog-backed data_stale case for failed/stale connector execution."""

    return OperationalCaseDetection(
        business_id=business_id,
        case_type="data_stale",
        dedupe_key=f"{business_id}/data_stale/connector/{connector_type}/runtime.freshness/daily",
        title=f"Datos stale o fallidos: {connector_type}",
        severity="warning",
        priority_score=80,
        entity_scope={"kind": "connector", "id": connector_type, "label": connector_type},
        evidence_refs=[f"evidence://{connector_type}/{run_id or 'unknown-run'}/data_stale"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/failure"] if run_id else [],
        metadata={"connector_type": connector_type, "error_summary": error_summary},
    )


def upsert_data_stale_cases(
    *,
    case_store: OperationalCaseStore | None,
    business_id: str | None,
    connector_types: list[str] | None,
    run_id: str | None,
    error_summary: str | None,
) -> OperationalCaseMutationSummary:
    if case_store is None or business_id is None:
        return OperationalCaseMutationSummary(case_ids=[], opened_count=0, updated_count=0)
    case_ids: list[str] = []
    opened_count = 0
    updated_count = 0
    for connector_type in connector_types or ["unknown"]:
        detection = make_data_stale_detection(
            business_id=business_id,
            connector_type=connector_type,
            run_id=run_id,
            error_summary=error_summary,
        )
        existing = case_store.find_by_dedupe_key(detection.business_id, detection.dedupe_key)
        case = case_store.upsert_detection(detection)
        case_ids.append(case.case_id)
        if existing is None:
            opened_count += 1
        else:
            updated_count += 1
    return OperationalCaseMutationSummary(case_ids=case_ids, opened_count=opened_count, updated_count=updated_count)


def detect_cases_from_report(
    *,
    business_id: str,
    report: DailyReport,
    run_id: str | None = None,
    artifact_ref: str | None = None,
) -> list[OperationalCaseDetection]:
    detections: list[OperationalCaseDetection] = []
    for insight in report.insights:
        case_type = _case_type_for_insight(insight)
        if case_type is None:
            continue
        detections.append(
            OperationalCaseDetection(
                business_id=business_id,
                case_type=case_type,
                dedupe_key=_dedupe_key(business_id, case_type),
                title=insight.title,
                severity=insight.severity,
                priority_score=_priority_for_severity(insight.severity),
                entity_scope=_entity_scope(case_type),
                evidence_refs=_evidence_refs_for_insight(insight, report, case_type),
                run_id=run_id,
                artifact_refs=[artifact_ref] if artifact_ref else [],
                metadata={
                    "insight_title": insight.title,
                    "insight_explanation": insight.explanation,
                    "recommended_action": insight.recommended_action,
                },
            )
        )
    return detections


@dataclass(frozen=True)
class OperationalCaseMutationSummary:
    case_ids: list[str]
    opened_count: int
    updated_count: int


def upsert_cases_from_report(
    *,
    case_store: OperationalCaseStore | None,
    business_id: str,
    report: DailyReport,
    run_id: str | None,
    artifact_ref: str,
) -> OperationalCaseMutationSummary:
    if case_store is None:
        return OperationalCaseMutationSummary(case_ids=[], opened_count=0, updated_count=0)

    case_ids: list[str] = []
    opened_count = 0
    updated_count = 0
    for detection in detect_cases_from_report(
        business_id=business_id,
        report=report,
        run_id=run_id,
        artifact_ref=artifact_ref,
    ):
        existing = case_store.find_by_dedupe_key(detection.business_id, detection.dedupe_key)
        case = case_store.upsert_detection(detection)
        case_ids.append(case.case_id)
        if existing is None:
            opened_count += 1
        else:
            updated_count += 1
    return OperationalCaseMutationSummary(case_ids=case_ids, opened_count=opened_count, updated_count=updated_count)
