"""Run ledger models and append-oriented stores for Orvo Brain.

This module is intentionally additive: it defines the first durable contract for
report/run lifecycle history without wiring it into the current production paths.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

RunTriggerType = Literal["scheduled", "forced", "manual", "preview", "backfill"]
RunStatus = Literal["running", "succeeded", "failed", "partial", "cancelled"]
ConnectorRunStatus = Literal["succeeded", "failed", "skipped"]
DispatchRunStatus = Literal["sent", "failed", "skipped_duplicate", "skipped", "queued"]

TERMINAL_RUN_STATUSES: set[str] = {"succeeded", "failed", "partial", "cancelled"}
_SECRET_KEY_PARTS = (
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "password",
    "private_key",
    "credential",
    "cookie",
    "session",
    "signature",
    "secret",
    "token",
)


class RunLedgerStatusError(ValueError):
    """Raised when an invalid run ledger status transition is requested."""


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("run ledger timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = re.sub(r"Bearer\s+[^\s,;]+", "Bearer [REDACTED]", value, flags=re.IGNORECASE)
    redacted = re.sub(
        r"(?i)\b(access_token|refresh_token|api_key|apikey|authorization|auth_header|password|private_key|credential|cookie|session|signature|secret|token)=([^\s,;&]+)",
        lambda match: f"{match.group(1)}=[REDACTED]",
        redacted,
    )
    return redacted


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def _redact_uri(value: str | None) -> str | None:
    """Redact secret-shaped query params from artifact/config references."""

    redacted = _redact_text(value)
    if redacted is None:
        return None
    try:
        parts = urlsplit(redacted)
    except ValueError:
        return redacted
    if not parts.query:
        return redacted

    safe_query = urlencode(
        [
            (key, "[REDACTED]" if _is_secret_key(key) else query_value)
            for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, safe_query, parts.fragment))


def redact_metadata(value: Any) -> Any:
    """Recursively redact secret-shaped metadata values.

    The ledger should store references and non-sensitive summary metadata only.
    This helper is intentionally conservative for metadata dictionaries while
    avoiding broad keys such as ``idempotency_key`` that are audit references.
    """

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            redacted[key] = "[REDACTED]" if _is_secret_key(key) else redact_metadata(raw_value)
        return redacted
    if isinstance(value, list):
        return [redact_metadata(item) for item in value]
    return value


class ArtifactRef(BaseModel):
    """Reference to an output artifact without embedding large/secret payloads."""

    artifact_id: str = Field(..., min_length=1)
    artifact_type: str = Field(..., min_length=1)
    uri: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    operational_case_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now_utc)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_validator("uri", mode="before")
    @classmethod
    def redact_uri(cls, value: str | None) -> str | None:
        return _redact_uri(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def redact_metadata_values(cls, value: Any) -> dict[str, Any]:
        return redact_metadata(value or {})


class ConnectorRunOutcome(BaseModel):
    """Lifecycle outcome for one connector during a report/run."""

    connector_id: str = Field(..., min_length=1)
    connector_type: str = Field(..., min_length=1)
    status: ConnectorRunStatus
    started_at: datetime
    finished_at: datetime | None = None
    metrics_count: int | None = Field(default=None, ge=0)
    error_summary: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None

    @field_validator("error_summary", mode="before")
    @classmethod
    def redact_error_summary(cls, value: str | None) -> str | None:
        return _redact_text(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def redact_metadata_values(cls, value: Any) -> dict[str, Any]:
        return redact_metadata(value or {})

    @model_validator(mode="after")
    def validate_time_order(self) -> "ConnectorRunOutcome":
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at must be after started_at")
        return self


class DispatchOutcomeRef(BaseModel):
    """Reference to a dispatch attempt/result for a run."""

    channel: str = Field(..., min_length=1)
    status: DispatchRunStatus
    attempt_number: int = Field(default=1, ge=1)
    idempotency_key: str | None = None
    message_id: str | None = None
    provider_response_ref: str | None = None
    error_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now_utc)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_validator("provider_response_ref", mode="before")
    @classmethod
    def redact_provider_response_ref(cls, value: str | None) -> str | None:
        return _redact_uri(value)

    @field_validator("error_summary", mode="before")
    @classmethod
    def redact_error_summary(cls, value: str | None) -> str | None:
        return _redact_text(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def redact_metadata_values(cls, value: Any) -> dict[str, Any]:
        return redact_metadata(value or {})


class RunRecord(BaseModel):
    """Audit-safe summary of one Orvo Brain report/run lifecycle."""

    run_id: str = Field(..., min_length=1)
    business_id: str = Field(..., min_length=1)
    trigger_type: RunTriggerType
    status: RunStatus = "running"
    started_at: datetime = Field(default_factory=_now_utc)
    finished_at: datetime | None = None
    config_ref: str | None = None
    config_digest: str | None = None
    connector_outcomes: list[ConnectorRunOutcome] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    dispatch_outcomes: list[DispatchOutcomeRef] = Field(default_factory=list)
    summary_metadata: dict[str, Any] = Field(default_factory=dict)
    error_summary: str | None = None

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value is not None else None

    @field_validator("config_ref", mode="before")
    @classmethod
    def redact_config_ref(cls, value: str | None) -> str | None:
        return _redact_uri(value)

    @field_validator("summary_metadata", mode="before")
    @classmethod
    def redact_summary_metadata_values(cls, value: Any) -> dict[str, Any]:
        return redact_metadata(value or {})

    @field_validator("error_summary", mode="before")
    @classmethod
    def redact_error_summary(cls, value: str | None) -> str | None:
        return _redact_text(value)

    @model_validator(mode="after")
    def validate_lifecycle_times(self) -> "RunRecord":
        if self.status in TERMINAL_RUN_STATUSES and self.finished_at is None:
            raise ValueError("terminal run requires finished_at")
        if self.status == "running" and self.finished_at is not None:
            raise ValueError("running run cannot have finished_at")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at must be after started_at")
        return self


class RunLedger(Protocol):
    """Append-oriented run ledger interface for future operator/audit APIs."""

    def create_run(
        self,
        *,
        business_id: str,
        trigger_type: RunTriggerType,
        run_id: str | None = None,
        started_at: datetime | None = None,
        config_ref: str | None = None,
        config_digest: str | None = None,
        summary_metadata: dict[str, Any] | None = None,
    ) -> RunRecord: ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        finished_at: datetime | None = None,
        summary_metadata: dict[str, Any] | None = None,
        error_summary: str | None = None,
    ) -> RunRecord: ...

    def append_connector_outcome(self, run_id: str, outcome: ConnectorRunOutcome) -> RunRecord: ...
    def append_artifact_ref(self, run_id: str, artifact: ArtifactRef) -> RunRecord: ...
    def append_dispatch_outcome(self, run_id: str, outcome: DispatchOutcomeRef) -> RunRecord: ...
    def get_run(self, run_id: str) -> RunRecord | None: ...
    def list_runs(
        self,
        *,
        business_id: str | None = None,
        status: RunStatus | None = None,
        limit: int | None = 100,
    ) -> list[RunRecord]: ...


class _RunLedgerMutations:
    """Shared mutation semantics for concrete ledger stores."""

    def _load_for_update(self, run_id: str) -> RunRecord:
        record = self.get_run(run_id)  # type: ignore[attr-defined]
        if record is None:
            raise KeyError(f"run not found: {run_id}")
        return record

    def _persist(self, record: RunRecord) -> None:
        raise NotImplementedError

    def create_run(
        self,
        *,
        business_id: str,
        trigger_type: RunTriggerType,
        run_id: str | None = None,
        started_at: datetime | None = None,
        config_ref: str | None = None,
        config_digest: str | None = None,
        summary_metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        record = RunRecord(
            run_id=run_id or str(uuid4()),
            business_id=business_id,
            trigger_type=trigger_type,
            status="running",
            started_at=started_at or _now_utc(),
            config_ref=config_ref,
            config_digest=config_digest,
            summary_metadata=summary_metadata or {},
        )
        if self.get_run(record.run_id) is not None:  # type: ignore[attr-defined]
            raise ValueError(f"run already exists: {record.run_id}")
        self._persist(record)
        return record.model_copy(deep=True)

    def _ensure_open_for_append(self, record: RunRecord) -> None:
        if record.status in TERMINAL_RUN_STATUSES:
            raise RunLedgerStatusError(f"terminal run {record.run_id} cannot be appended to")

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        finished_at: datetime | None = None,
        summary_metadata: dict[str, Any] | None = None,
        error_summary: str | None = None,
    ) -> RunRecord:
        record = self._load_for_update(run_id)
        has_mutation = any(
            value is not None for value in (status, finished_at, summary_metadata, error_summary)
        )
        if record.status in TERMINAL_RUN_STATUSES and has_mutation:
            raise RunLedgerStatusError(f"terminal run {run_id} cannot be mutated")

        effective_status = status or record.status
        effective_finished_at = finished_at or record.finished_at
        if effective_status in TERMINAL_RUN_STATUSES and effective_finished_at is None:
            raise RunLedgerStatusError(f"terminal run {run_id} requires finished_at")
        if effective_status == "running" and finished_at is not None:
            raise RunLedgerStatusError(f"running run {run_id} cannot have finished_at")

        update: dict[str, Any] = {}
        if status is not None:
            update["status"] = status
        if finished_at is not None:
            update["finished_at"] = finished_at
        if summary_metadata is not None:
            update["summary_metadata"] = {**record.summary_metadata, **summary_metadata}
        if error_summary is not None:
            update["error_summary"] = error_summary

        updated = record.model_copy(update=update)
        updated = RunRecord.model_validate(updated.model_dump())
        self._persist(updated)
        return updated.model_copy(deep=True)

    def append_connector_outcome(self, run_id: str, outcome: ConnectorRunOutcome) -> RunRecord:
        record = self._load_for_update(run_id)
        self._ensure_open_for_append(record)
        updated = record.model_copy(update={"connector_outcomes": [*record.connector_outcomes, outcome]})
        self._persist(updated)
        return updated.model_copy(deep=True)

    def append_artifact_ref(self, run_id: str, artifact: ArtifactRef) -> RunRecord:
        record = self._load_for_update(run_id)
        self._ensure_open_for_append(record)
        updated = record.model_copy(update={"artifacts": [*record.artifacts, artifact]})
        self._persist(updated)
        return updated.model_copy(deep=True)

    def append_dispatch_outcome(self, run_id: str, outcome: DispatchOutcomeRef) -> RunRecord:
        record = self._load_for_update(run_id)
        self._ensure_open_for_append(record)
        updated = record.model_copy(update={"dispatch_outcomes": [*record.dispatch_outcomes, outcome]})
        self._persist(updated)
        return updated.model_copy(deep=True)


class InMemoryRunLedger(_RunLedgerMutations):
    """Dependency-free run ledger for tests and first in-process integrations."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def _persist(self, record: RunRecord) -> None:
        self._runs[record.run_id] = record.model_copy(deep=True)

    def get_run(self, run_id: str) -> RunRecord | None:
        record = self._runs.get(run_id)
        return record.model_copy(deep=True) if record is not None else None

    def list_runs(
        self,
        *,
        business_id: str | None = None,
        status: RunStatus | None = None,
        limit: int | None = 100,
    ) -> list[RunRecord]:
        records = list(self._runs.values())
        if business_id is not None:
            records = [record for record in records if record.business_id == business_id]
        if status is not None:
            records = [record for record in records if record.status == status]
        records.sort(key=lambda record: (record.started_at, record.run_id), reverse=True)
        if limit is not None:
            records = records[:limit]
        return [record.model_copy(deep=True) for record in records]


class SQLiteRunLedger(_RunLedgerMutations):
    """SQLite-backed run ledger using the existing Orvo Brain storage pattern."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _persist(self, record: RunRecord) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO run_ledger
                (run_id, business_id, trigger_type, status, started_at, finished_at, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.business_id,
                record.trigger_type,
                record.status,
                record.started_at.isoformat(),
                record.finished_at.isoformat() if record.finished_at else None,
                record.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        cursor = self._conn.execute("SELECT data FROM run_ledger WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return RunRecord.model_validate_json(row[0])

    def list_runs(
        self,
        *,
        business_id: str | None = None,
        status: RunStatus | None = None,
        limit: int | None = 100,
    ) -> list[RunRecord]:
        clauses: list[str] = []
        params: list[str | int] = []
        if business_id is not None:
            clauses.append("business_id = ?")
            params.append(business_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)

        query = "SELECT data FROM run_ledger"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY started_at DESC, run_id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self._conn.execute(query, tuple(params))
        return [RunRecord.model_validate_json(row[0]) for row in cursor.fetchall()]
