"""Durable workflow action ledger and approval request foundation.

This module records deterministic workflow action projections before any future
executor is allowed to mutate cases or call external systems. It keeps action
params redacted, enforces idempotency keys durably, and creates approval-request
objects for approval-required actions while executing zero side effects.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from app.brain.security.redaction import redact_secrets, redact_text

ApprovalState = Literal["not_required", "pending", "approved", "rejected", "cancelled"]
ExecutionState = Literal[
    "dry_run",
    "suggestion_only",
    "blocked_approval_required",
    "skipped_duplicate",
    "pending_execution",
    "executed",
    "failed",
]
ApprovalRequestStatus = Literal["pending", "approved", "rejected", "cancelled"]
ApprovalDecision = Literal["approved", "rejected"]
ActionSource = Literal["workflow", "manual_operator"]


@dataclass(frozen=True)
class WorkflowActionLedgerRecord:
    ledger_id: str
    business_id: str
    case_id: str
    action_key: str
    source: ActionSource
    actor_ref: str | None
    idempotency_key: str
    approval_state: ApprovalState
    execution_state: ExecutionState
    params: dict[str, Any]
    rule_id: str | None
    approval_request_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WorkflowApprovalRequest:
    approval_request_id: str
    ledger_id: str
    business_id: str
    case_id: str
    action_key: str
    requester_ref: str | None
    status: ApprovalRequestStatus
    requested_at: datetime
    decided_at: datetime | None = None
    decision_actor_ref: str | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkflowActionLedgerWrite:
    record: WorkflowActionLedgerRecord
    created: bool
    approval_request: WorkflowApprovalRequest | None = None


@dataclass(frozen=True)
class WorkflowApprovalDecisionRecord:
    """Result of deciding an approval gate without executing the action."""

    record: WorkflowActionLedgerRecord
    approval_request: WorkflowApprovalRequest
    audit_event: dict[str, Any]
    side_effects_executed: int = 0


class WorkflowActionLedgerError(Exception):
    """Safe deterministic workflow action ledger error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = redact_text(message) or "Workflow action ledger error"
        super().__init__(self.message)


class WorkflowActionLedgerStore(Protocol):
    def record_planned_action(
        self,
        *,
        business_id: str,
        case_id: str,
        action_key: str,
        idempotency_key: str,
        execution_state: ExecutionState,
        approval_required: bool,
        source: ActionSource = "workflow",
        actor_ref: str | None = None,
        params: dict[str, Any] | None = None,
        rule_id: str | None = None,
        now: datetime | None = None,
    ) -> WorkflowActionLedgerWrite: ...

    def list_actions(self, *, business_id: str) -> list[WorkflowActionLedgerRecord]: ...

    def list_approval_requests(self, *, business_id: str) -> list[WorkflowApprovalRequest]: ...

    def decide_approval_request(
        self,
        *,
        business_id: str,
        approval_request_id: str,
        decision: ApprovalDecision,
        actor_ref: str,
        reason: str,
        now: datetime | None = None,
    ) -> WorkflowApprovalDecisionRecord: ...


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime:
    return (value or _now_utc()).astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _redacted_params(params: dict[str, Any] | None) -> dict[str, Any]:
    redacted = redact_secrets(params or {})
    return redacted if isinstance(redacted, dict) else {}


def _stable_id(prefix: str, *, business_id: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{business_id}:{idempotency_key}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}/{business_id}/{digest}"


def _json_dumps(value: Any) -> str:
    return json.dumps(redact_secrets(value), sort_keys=True, separators=(",", ":"), default=str)


def _json_loads_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _validate_approval_decision(decision: str) -> ApprovalDecision:
    if decision not in {"approved", "rejected"}:
        raise WorkflowActionLedgerError("invalid_approval_decision", "approval decision must be approved or rejected")
    return cast(ApprovalDecision, decision)


def _decision_states(decision: ApprovalDecision) -> tuple[ApprovalState, ExecutionState]:
    if decision == "approved":
        return "approved", "pending_execution"
    return "rejected", "failed"


def _safe_text(value: str | None) -> str | None:
    return redact_text(value) if value else None


def _decision_audit_event(
    *,
    record: WorkflowActionLedgerRecord,
    approval_request: WorkflowApprovalRequest,
    decision: ApprovalDecision,
    actor_ref: str | None,
    reason: str | None,
    now: datetime,
) -> dict[str, Any]:
    event = {
        "event_type": "workflow_approval_decided",
        "business_id": record.business_id,
        "approval_request_id": approval_request.approval_request_id,
        "ledger_id": record.ledger_id,
        "case_id": record.case_id,
        "action_key": record.action_key,
        "decision": decision,
        "approval_state": record.approval_state,
        "execution_state": record.execution_state,
        "actor_ref": actor_ref,
        "reason": reason,
        "created_at": _iso(now),
    }
    redacted = redact_secrets(event)
    return redacted if isinstance(redacted, dict) else event


def _build_approval_decision_record(
    *,
    record: WorkflowActionLedgerRecord,
    approval_request: WorkflowApprovalRequest,
    decision: ApprovalDecision,
    actor_ref: str | None,
    reason: str | None,
    now: datetime,
) -> WorkflowApprovalDecisionRecord:
    return WorkflowApprovalDecisionRecord(
        record=record,
        approval_request=approval_request,
        audit_event=_decision_audit_event(
            record=record,
            approval_request=approval_request,
            decision=decision,
            actor_ref=actor_ref,
            reason=reason,
            now=now,
        ),
    )


class InMemoryWorkflowActionLedgerStore:
    """Process-local implementation used by focused service tests."""

    def __init__(self) -> None:
        self._actions: dict[tuple[str, str], WorkflowActionLedgerRecord] = {}
        self._approvals: dict[str, WorkflowApprovalRequest] = {}

    def record_planned_action(
        self,
        *,
        business_id: str,
        case_id: str,
        action_key: str,
        idempotency_key: str,
        execution_state: ExecutionState,
        approval_required: bool,
        source: ActionSource = "workflow",
        actor_ref: str | None = None,
        params: dict[str, Any] | None = None,
        rule_id: str | None = None,
        now: datetime | None = None,
    ) -> WorkflowActionLedgerWrite:
        key = (business_id, idempotency_key)
        existing = self._actions.get(key)
        if existing is not None:
            return WorkflowActionLedgerWrite(record=existing, created=False)
        timestamp = _coerce_utc(now)
        approval_state: ApprovalState = "pending" if approval_required else "not_required"
        ledger_id = _stable_id("workflow-action", business_id=business_id, idempotency_key=idempotency_key)
        approval_request_id = (
            _stable_id("workflow-approval", business_id=business_id, idempotency_key=idempotency_key)
            if approval_required
            else None
        )
        record = WorkflowActionLedgerRecord(
            ledger_id=ledger_id,
            business_id=business_id,
            case_id=case_id,
            action_key=action_key,
            source=source,
            actor_ref=redact_text(actor_ref) if actor_ref else None,
            idempotency_key=idempotency_key,
            approval_state=approval_state,
            execution_state=execution_state,
            params=_redacted_params(params),
            rule_id=rule_id,
            approval_request_id=approval_request_id,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._actions[key] = record
        approval = None
        if approval_request_id is not None:
            approval = WorkflowApprovalRequest(
                approval_request_id=approval_request_id,
                ledger_id=ledger_id,
                business_id=business_id,
                case_id=case_id,
                action_key=action_key,
                requester_ref=record.actor_ref,
                status="pending",
                requested_at=timestamp,
                metadata={"source": source, "rule_id": rule_id} if rule_id else {"source": source},
            )
            self._approvals[approval.approval_request_id] = approval
        return WorkflowActionLedgerWrite(record=record, created=True, approval_request=approval)

    def list_actions(self, *, business_id: str) -> list[WorkflowActionLedgerRecord]:
        return [record for record in self._actions.values() if record.business_id == business_id]

    def list_approval_requests(self, *, business_id: str) -> list[WorkflowApprovalRequest]:
        return [request for request in self._approvals.values() if request.business_id == business_id]

    def decide_approval_request(
        self,
        *,
        business_id: str,
        approval_request_id: str,
        decision: ApprovalDecision,
        actor_ref: str,
        reason: str,
        now: datetime | None = None,
    ) -> WorkflowApprovalDecisionRecord:
        approved_decision = _validate_approval_decision(decision)
        request = self._approvals.get(approval_request_id)
        if request is None or request.business_id != business_id:
            raise WorkflowActionLedgerError("approval_request_not_found", "approval request not found")
        if request.status != "pending":
            raise WorkflowActionLedgerError(
                "approval_request_already_decided",
                f"approval request already decided with status {request.status}",
            )
        record_key = next(
            (
                key
                for key, action in self._actions.items()
                if action.business_id == business_id and action.ledger_id == request.ledger_id
            ),
            None,
        )
        if record_key is None:
            raise WorkflowActionLedgerError("approval_record_not_found", "approval ledger record not found")
        timestamp = _coerce_utc(now)
        approval_state, execution_state = _decision_states(approved_decision)
        safe_actor_ref = _safe_text(actor_ref)
        safe_reason = _safe_text(reason)
        record = replace(
            self._actions[record_key],
            approval_state=approval_state,
            execution_state=execution_state,
            updated_at=timestamp,
        )
        decided_request = replace(
            request,
            status=approved_decision,
            decided_at=timestamp,
            decision_actor_ref=safe_actor_ref,
            decision_reason=safe_reason,
        )
        self._actions[record_key] = record
        self._approvals[approval_request_id] = decided_request
        return _build_approval_decision_record(
            record=record,
            approval_request=decided_request,
            decision=approved_decision,
            actor_ref=safe_actor_ref,
            reason=safe_reason,
            now=timestamp,
        )


class SQLiteWorkflowActionLedgerStore:
    """SQLite-backed durable workflow action ledger store."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_action_ledger (
                    ledger_id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    source TEXT NOT NULL,
                    actor_ref TEXT,
                    idempotency_key TEXT NOT NULL,
                    approval_state TEXT NOT NULL,
                    execution_state TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    rule_id TEXT,
                    approval_request_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (business_id, idempotency_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_approval_requests (
                    approval_request_id TEXT PRIMARY KEY,
                    ledger_id TEXT NOT NULL,
                    business_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    requester_ref TEXT,
                    status TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT,
                    decision_actor_ref TEXT,
                    decision_reason TEXT,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (ledger_id) REFERENCES workflow_action_ledger(ledger_id)
                )
                """
            )

    def record_planned_action(
        self,
        *,
        business_id: str,
        case_id: str,
        action_key: str,
        idempotency_key: str,
        execution_state: ExecutionState,
        approval_required: bool,
        source: ActionSource = "workflow",
        actor_ref: str | None = None,
        params: dict[str, Any] | None = None,
        rule_id: str | None = None,
        now: datetime | None = None,
    ) -> WorkflowActionLedgerWrite:
        timestamp = _coerce_utc(now)
        ledger_id = _stable_id("workflow-action", business_id=business_id, idempotency_key=idempotency_key)
        approval_request_id = (
            _stable_id("workflow-approval", business_id=business_id, idempotency_key=idempotency_key)
            if approval_required
            else None
        )
        approval_state: ApprovalState = "pending" if approval_required else "not_required"
        safe_actor_ref = redact_text(actor_ref) if actor_ref else None
        params_json = _json_dumps(_redacted_params(params))
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO workflow_action_ledger (
                        ledger_id, business_id, case_id, action_key, source, actor_ref,
                        idempotency_key, approval_state, execution_state, params_json,
                        rule_id, approval_request_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ledger_id,
                        business_id,
                        case_id,
                        action_key,
                        source,
                        safe_actor_ref,
                        idempotency_key,
                        approval_state,
                        execution_state,
                        params_json,
                        rule_id,
                        approval_request_id,
                        _iso(timestamp),
                        _iso(timestamp),
                    ),
                )
            except sqlite3.IntegrityError:
                record = self._get_action_by_idempotency_key(conn, business_id, idempotency_key)
                return WorkflowActionLedgerWrite(record=record, created=False)
            approval = None
            if approval_request_id is not None:
                metadata = {"source": source}
                if rule_id:
                    metadata["rule_id"] = rule_id
                conn.execute(
                    """
                    INSERT INTO workflow_approval_requests (
                        approval_request_id, ledger_id, business_id, case_id, action_key,
                        requester_ref, status, requested_at, decided_at,
                        decision_actor_ref, decision_reason, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approval_request_id,
                        ledger_id,
                        business_id,
                        case_id,
                        action_key,
                        safe_actor_ref,
                        "pending",
                        _iso(timestamp),
                        None,
                        None,
                        None,
                        _json_dumps(metadata),
                    ),
                )
                approval = WorkflowApprovalRequest(
                    approval_request_id=approval_request_id,
                    ledger_id=ledger_id,
                    business_id=business_id,
                    case_id=case_id,
                    action_key=action_key,
                    requester_ref=safe_actor_ref,
                    status="pending",
                    requested_at=timestamp,
                    metadata=metadata,
                )
            record = self._get_action_by_idempotency_key(conn, business_id, idempotency_key)
        return WorkflowActionLedgerWrite(record=record, created=True, approval_request=approval)

    def _get_action_by_idempotency_key(
        self, conn: sqlite3.Connection, business_id: str, idempotency_key: str
    ) -> WorkflowActionLedgerRecord:
        row = conn.execute(
            "SELECT * FROM workflow_action_ledger WHERE business_id = ? AND idempotency_key = ?",
            (business_id, idempotency_key),
        ).fetchone()
        if row is None:
            raise KeyError(f"workflow action ledger record not found for business_id={business_id}")
        return _record_from_row(row)

    def list_actions(self, *, business_id: str) -> list[WorkflowActionLedgerRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_action_ledger WHERE business_id = ? ORDER BY created_at, ledger_id",
                (business_id,),
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def list_approval_requests(self, *, business_id: str) -> list[WorkflowApprovalRequest]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_approval_requests WHERE business_id = ? ORDER BY requested_at, approval_request_id",
                (business_id,),
            ).fetchall()
        return [_approval_from_row(row) for row in rows]

    def decide_approval_request(
        self,
        *,
        business_id: str,
        approval_request_id: str,
        decision: ApprovalDecision,
        actor_ref: str,
        reason: str,
        now: datetime | None = None,
    ) -> WorkflowApprovalDecisionRecord:
        approved_decision = _validate_approval_decision(decision)
        timestamp = _coerce_utc(now)
        approval_state, execution_state = _decision_states(approved_decision)
        safe_actor_ref = _safe_text(actor_ref)
        safe_reason = _safe_text(reason)
        with self._connect() as conn:
            request_row = conn.execute(
                "SELECT * FROM workflow_approval_requests WHERE business_id = ? AND approval_request_id = ?",
                (business_id, approval_request_id),
            ).fetchone()
            if request_row is None:
                raise WorkflowActionLedgerError("approval_request_not_found", "approval request not found")
            request = _approval_from_row(request_row)
            if request.status != "pending":
                raise WorkflowActionLedgerError(
                    "approval_request_already_decided",
                    f"approval request already decided with status {request.status}",
                )
            record_row = conn.execute(
                "SELECT * FROM workflow_action_ledger WHERE business_id = ? AND ledger_id = ?",
                (business_id, request.ledger_id),
            ).fetchone()
            if record_row is None:
                raise WorkflowActionLedgerError("approval_record_not_found", "approval ledger record not found")
            conn.execute(
                """
                UPDATE workflow_approval_requests
                SET status = ?, decided_at = ?, decision_actor_ref = ?, decision_reason = ?
                WHERE business_id = ? AND approval_request_id = ?
                """,
                (
                    approved_decision,
                    _iso(timestamp),
                    safe_actor_ref,
                    safe_reason,
                    business_id,
                    approval_request_id,
                ),
            )
            conn.execute(
                """
                UPDATE workflow_action_ledger
                SET approval_state = ?, execution_state = ?, updated_at = ?
                WHERE business_id = ? AND ledger_id = ?
                """,
                (approval_state, execution_state, _iso(timestamp), business_id, request.ledger_id),
            )
            updated_record = _record_from_row(
                conn.execute(
                    "SELECT * FROM workflow_action_ledger WHERE business_id = ? AND ledger_id = ?",
                    (business_id, request.ledger_id),
                ).fetchone()
            )
            updated_request = _approval_from_row(
                conn.execute(
                    "SELECT * FROM workflow_approval_requests WHERE business_id = ? AND approval_request_id = ?",
                    (business_id, approval_request_id),
                ).fetchone()
            )
        return _build_approval_decision_record(
            record=updated_record,
            approval_request=updated_request,
            decision=approved_decision,
            actor_ref=safe_actor_ref,
            reason=safe_reason,
            now=timestamp,
        )


def _record_from_row(row: sqlite3.Row) -> WorkflowActionLedgerRecord:
    return WorkflowActionLedgerRecord(
        ledger_id=row["ledger_id"],
        business_id=row["business_id"],
        case_id=row["case_id"],
        action_key=row["action_key"],
        source=row["source"],
        actor_ref=row["actor_ref"],
        idempotency_key=row["idempotency_key"],
        approval_state=row["approval_state"],
        execution_state=row["execution_state"],
        params=_json_loads_object(row["params_json"]),
        rule_id=row["rule_id"],
        approval_request_id=row["approval_request_id"],
        created_at=_parse_iso(row["created_at"]) or _now_utc(),
        updated_at=_parse_iso(row["updated_at"]) or _now_utc(),
    )


def _approval_from_row(row: sqlite3.Row) -> WorkflowApprovalRequest:
    return WorkflowApprovalRequest(
        approval_request_id=row["approval_request_id"],
        ledger_id=row["ledger_id"],
        business_id=row["business_id"],
        case_id=row["case_id"],
        action_key=row["action_key"],
        requester_ref=row["requester_ref"],
        status=row["status"],
        requested_at=_parse_iso(row["requested_at"]) or _now_utc(),
        decided_at=_parse_iso(row["decided_at"]),
        decision_actor_ref=row["decision_actor_ref"],
        decision_reason=row["decision_reason"],
        metadata=_json_loads_object(row["metadata_json"]),
    )
