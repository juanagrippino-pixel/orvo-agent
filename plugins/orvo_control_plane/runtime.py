"""Registry-driven execution runtime for Orvo connector calls.

The contract registry is the source of truth for what a connector may execute
and which configuration keys are public versus secret references. The execution
shim compiles raw runtime input into a contract-bound call, invokes a thin
adapter, and normalizes connector outcomes/evidence/events for downstream cases
and operator surfaces.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
import re
import threading
import time
from typing import Any, Literal

from app.brain.security.redaction import redact_text as redact_sensitive_text

ConnectorStatus = Literal["succeeded", "failed"]
_SECRET_REF_RE = re.compile(r"secret://[^\s\"'`),}\]]+")
_SK_LIVE_TOKEN_RE = re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}")
_AUDIT_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bearer",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "raw_secret",
    "secret",
    "secret_ref",
    "token",
)


@dataclass(frozen=True)
class ConnectorContract:
    """Static connector capability contract owned by the registry."""

    connector_id: str
    contract_name: str
    contract_version: str
    operations: tuple[str, ...]
    allowed_public_config_keys: tuple[str, ...] = ()
    required_secret_ref_keys: tuple[str, ...] = ()
    evidence_kinds: tuple[str, ...] = ()


class ConnectorContractViolation(ValueError):
    """Raised when an adapter result violates its registry contract."""


@dataclass(frozen=True)
class CompiledConnectorCall:
    """A runtime-ready connector call compiled from registry metadata."""

    run_id: str
    connector_id: str
    operation: str
    contract_name: str
    contract_version: str
    public_config: Mapping[str, Any]
    secret_refs: Mapping[str, str]
    evidence_kinds: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorExecutionRequest:
    """Raw execution request before registry validation/compilation."""

    run_id: str
    connector_id: str
    operation: str
    public_config: Mapping[str, Any] = field(default_factory=dict)
    secret_refs: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorResult:
    """Adapter-returned execution result before runtime provenance is added."""

    status: ConnectorStatus
    summary: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ConnectorOutcome:
    """Normalized connector outcome consumed by cases/workflows/operator APIs."""

    run_id: str
    connector_id: str
    operation: str
    status: ConnectorStatus
    summary: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ConnectorAuditEvent:
    """Append-only audit event for connector workflow replay/debugging."""

    sequence: int
    run_id: str
    event_type: str
    connector_id: str
    operation: str
    contract_name: str
    contract_version: str
    from_state: str
    to_state: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


@dataclass(frozen=True)
class ConnectorRunSummary:
    """Operator-facing summary of a connector run, derived from audit events."""

    run_id: str
    connector_id: str
    operation: str
    status: ConnectorStatus | None
    started_at: float
    finished_at: float | None
    evidence_count: int = 0
    event_count: int = 0


class ConnectorRunLedger:
    """In-memory run ledger for audited connector execution transitions."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._events: list[ConnectorAuditEvent] = []
        self._lock = threading.Lock()

    def append(
        self,
        *,
        compiled_call: CompiledConnectorCall,
        event_type: str,
        from_state: str,
        to_state: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ConnectorAuditEvent:
        created_at = self._clock()
        redacted_payload = _redacted_audit_payload(payload or {})
        with self._lock:
            event = ConnectorAuditEvent(
                sequence=len(self._events) + 1,
                run_id=compiled_call.run_id,
                event_type=event_type,
                connector_id=compiled_call.connector_id,
                operation=compiled_call.operation,
                contract_name=compiled_call.contract_name,
                contract_version=compiled_call.contract_version,
                from_state=from_state,
                to_state=to_state,
                payload=redacted_payload,
                created_at=created_at,
            )
            self._events.append(event)
        return event

    def events_for_run(self, run_id: str) -> tuple[ConnectorAuditEvent, ...]:
        with self._lock:
            return tuple(event for event in self._events if event.run_id == run_id)

    def replay_run(self, run_id: str) -> list[dict[str, Any]]:
        return [asdict(event) for event in self.events_for_run(run_id)]

    def run_summary(self, run_id: str) -> ConnectorRunSummary | None:
        """Return the operator-facing summary for a single run, or None if not found."""
        with self._lock:
            events = [event for event in self._events if event.run_id == run_id]
        if not events:
            return None

        first = events[0]
        last = events[-1]

        terminal_types = {"connector.execution.succeeded", "connector.execution.failed"}
        has_terminal = any(e.event_type in terminal_types for e in events)
        status: ConnectorStatus | None = last.to_state if has_terminal else None  # type: ignore[assignment]
        finished_at: float | None = last.created_at if has_terminal else None

        evidence_count = last.payload.get("evidence_count", 0) if has_terminal else 0
        event_count = last.payload.get("event_count", 0) if has_terminal else 0

        return ConnectorRunSummary(
            run_id=run_id,
            connector_id=first.connector_id,
            operation=first.operation,
            status=status,
            started_at=first.created_at,
            finished_at=finished_at,
            evidence_count=evidence_count,
            event_count=event_count,
        )

    def run_summaries(self) -> list[ConnectorRunSummary]:
        """Return operator-facing summaries for all tracked runs, in insertion order."""
        with self._lock:
            runs: dict[str, list[ConnectorAuditEvent]] = {}
            for event in self._events:
                runs.setdefault(event.run_id, []).append(event)

        summaries: list[ConnectorRunSummary] = []
        for run_id, events in runs.items():
            first = events[0]
            last = events[-1]

            # Determine final status from the terminal audit event if any.
            terminal_types = {"connector.execution.succeeded", "connector.execution.failed"}
            has_terminal = any(e.event_type in terminal_types for e in events)
            if has_terminal:
                status: ConnectorStatus | None = last.to_state  # type: ignore[assignment]
            else:
                status = None

            finished_at: float | None = last.created_at if has_terminal else None

            # Pull evidence_count and event_count from the terminal event payload if present.
            evidence_count = last.payload.get("evidence_count", 0) if has_terminal else 0
            event_count = last.payload.get("event_count", 0) if has_terminal else 0

            summaries.append(
                ConnectorRunSummary(
                    run_id=run_id,
                    connector_id=first.connector_id,
                    operation=first.operation,
                    status=status,
                    started_at=first.created_at,
                    finished_at=finished_at,
                    evidence_count=evidence_count,
                    event_count=event_count,
                )
            )

        return summaries

    def runs_by_connector(self, connector_id: str) -> list[ConnectorRunSummary]:
        """Return operator-facing run summaries filtered to a specific connector, in insertion order."""
        return [s for s in self.run_summaries() if s.connector_id == connector_id]

    def open_runs(self) -> list[ConnectorRunSummary]:
        """Return operator-facing summaries for runs that have not yet reached a terminal state."""
        return [s for s in self.run_summaries() if s.status is None]

    def last_completed_run(self, connector_id: str) -> ConnectorRunSummary | None:
        """Return the most recently finished run for a connector, or None if none completed."""
        completed = [
            s
            for s in self.runs_by_connector(connector_id)
            if s.status is not None and s.finished_at is not None
        ]
        if not completed:
            return None
        return max(completed, key=lambda s: s.finished_at or 0.0)


class ConnectorRegistry:
    """In-memory connector contract registry.

    This deliberately stores contract metadata separately from adapters so the
    registry remains the runtime source of truth and execution paths cannot
    invent undeclared public configuration or operations.
    """

    def __init__(self) -> None:
        self._contracts: dict[str, ConnectorContract] = {}

    def register(self, contract: ConnectorContract) -> None:
        if not contract.connector_id:
            raise ValueError("connector_id is required")
        if not contract.operations:
            raise ValueError("at least one connector operation is required")
        if contract.connector_id in self._contracts:
            raise ValueError(f"connector already registered: {contract.connector_id}")
        self._contracts[contract.connector_id] = contract

    def get(self, connector_id: str) -> ConnectorContract:
        try:
            return self._contracts[connector_id]
        except KeyError as exc:
            raise ValueError(f"connector not registered: {connector_id}") from exc

    def __contains__(self, connector_id: str) -> bool:
        return connector_id in self._contracts

    def operations_for(self, connector_id: str) -> tuple[str, ...]:
        """Return the declared operations for a connector, or raise ValueError."""
        return self.get(connector_id).operations

    def list_all(self) -> list[ConnectorContract]:
        """Return all registered contracts sorted by connector_id for operator surfaces."""
        return sorted(self._contracts.values(), key=lambda c: c.connector_id)


ConnectorAdapter = Callable[[CompiledConnectorCall], ConnectorResult]


def compile_connector_call(
    *,
    registry: ConnectorRegistry,
    connector_id: str,
    operation: str,
    public_config: Mapping[str, Any],
    secret_refs: Mapping[str, str],
    run_id: str,
) -> CompiledConnectorCall:
    """Compile raw execution input against the connector registry contract."""

    contract = registry.get(connector_id)
    if operation not in contract.operations:
        raise ValueError(
            f"operation {operation!r} is not declared by connector registry "
            f"for {connector_id!r}"
        )

    allowed_public_keys = set(contract.allowed_public_config_keys)
    provided_public_keys = set(public_config.keys())
    undeclared_public_keys = provided_public_keys - allowed_public_keys
    if undeclared_public_keys:
        keys = ", ".join(sorted(undeclared_public_keys))
        raise ValueError(
            f"public config key(s) not declared by connector registry for "
            f"{connector_id!r}: {keys}"
        )

    required_secret_keys = set(contract.required_secret_ref_keys)
    provided_secret_keys = set(secret_refs.keys())
    missing_secret_keys = required_secret_keys - provided_secret_keys
    if missing_secret_keys:
        keys = ", ".join(sorted(missing_secret_keys))
        raise ValueError(f"missing required secret reference(s) for {connector_id!r}: {keys}")

    undeclared_secret_keys = provided_secret_keys - required_secret_keys
    if undeclared_secret_keys:
        keys = ", ".join(sorted(undeclared_secret_keys))
        raise ValueError(
            f"secret reference key(s) not declared by connector registry for "
            f"{connector_id!r}: {keys}"
        )

    return CompiledConnectorCall(
        run_id=run_id,
        connector_id=contract.connector_id,
        operation=operation,
        contract_name=contract.contract_name,
        contract_version=contract.contract_version,
        public_config=dict(public_config),
        secret_refs=dict(secret_refs),
        evidence_kinds=contract.evidence_kinds,
    )


class ConnectorExecutor:
    """Execution shim over legacy/thin connector adapters."""

    def __init__(
        self,
        *,
        registry: ConnectorRegistry,
        adapters: Mapping[str, ConnectorAdapter],
        audit_ledger: ConnectorRunLedger | None = None,
    ) -> None:
        self._registry = registry
        self._adapters = dict(adapters)
        self._audit_ledger = audit_ledger

    def execute(self, request: ConnectorExecutionRequest) -> ConnectorOutcome:
        compiled_call = compile_connector_call(
            registry=self._registry,
            connector_id=request.connector_id,
            operation=request.operation,
            public_config=request.public_config,
            secret_refs=request.secret_refs,
            run_id=request.run_id,
        )
        self._record_audit_event(
            compiled_call=compiled_call,
            event_type="connector.execution.started",
            from_state="requested",
            to_state="running",
            payload={
                "public_config": compiled_call.public_config,
                "secret_ref_keys": sorted(compiled_call.secret_refs.keys()),
                "evidence_kinds": list(compiled_call.evidence_kinds),
            },
        )
        try:
            adapter = self._adapter_for(compiled_call.connector_id)
            result = adapter(compiled_call)
            _validate_connector_result(result, compiled_call=compiled_call)
        except Exception as exc:  # noqa: BLE001 - normalize connector failures for cases.
            outcome = _failed_outcome(compiled_call, exc)
            self._record_audit_event(
                compiled_call=compiled_call,
                event_type="connector.execution.failed",
                from_state="running",
                to_state="failed",
                payload={
                    "summary": outcome.summary,
                    "error_type": type(exc).__name__,
                },
            )
            return outcome

        outcome = ConnectorOutcome(
            run_id=compiled_call.run_id,
            connector_id=compiled_call.connector_id,
            operation=compiled_call.operation,
            status=result.status,
            summary=result.summary,
            evidence=[
                _with_runtime_provenance(item, compiled_call=compiled_call)
                for item in result.evidence
            ],
            events=[
                _with_runtime_provenance(item, compiled_call=compiled_call)
                for item in result.events
            ],
        )
        self._record_audit_event(
            compiled_call=compiled_call,
            event_type=f"connector.execution.{outcome.status}",
            from_state="running",
            to_state=outcome.status,
            payload={
                "summary": outcome.summary,
                "evidence_count": len(outcome.evidence),
                "event_count": len(outcome.events),
            },
        )
        return outcome

    def _record_audit_event(
        self,
        *,
        compiled_call: CompiledConnectorCall,
        event_type: str,
        from_state: str,
        to_state: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self._audit_ledger is None:
            return
        try:
            self._audit_ledger.append(
                compiled_call=compiled_call,
                event_type=event_type,
                from_state=from_state,
                to_state=to_state,
                payload=payload,
            )
        except Exception:
            return

    def is_available(self, connector_id: str) -> bool:
        """Return True when both a registry contract and a wired adapter exist for connector_id."""
        if connector_id not in self._registry:
            return False
        return connector_id in self._adapters

    def _adapter_for(self, connector_id: str) -> ConnectorAdapter:
        try:
            return self._adapters[connector_id]
        except KeyError as exc:
            raise ValueError(f"no adapter registered for connector: {connector_id}") from exc


def _redacted_audit_payload(value: Any, *, key_hint: str | None = None) -> Any:
    """Return a JSON-friendly, force-redacted copy of audit payload values."""

    if _is_sensitive_audit_key(key_hint):
        return "***"
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _redact_audit_string(str(key))
            redacted[safe_key] = _redacted_audit_payload(item, key_hint=str(key))
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redacted_audit_payload(item, key_hint=key_hint) for item in value]
    if isinstance(value, set):
        return [_redacted_audit_payload(item, key_hint=key_hint) for item in sorted(value, key=str)]
    if isinstance(value, str):
        return _redact_audit_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_audit_string(str(value))


def _redact_audit_string(value: str) -> str:
    redacted = redact_sensitive_text(value) or ""
    redacted = _SK_LIVE_TOKEN_RE.sub("[REDACTED_API_KEY]", redacted)
    return _SECRET_REF_RE.sub("secret://***", redacted)


def _is_sensitive_audit_key(key: str | None) -> bool:
    if not key:
        return False
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    if normalized in {"secret_ref_keys"}:
        return False
    return any(part in normalized for part in _AUDIT_SENSITIVE_KEY_PARTS)


def _with_runtime_provenance(
    item: Mapping[str, Any],
    *,
    compiled_call: CompiledConnectorCall,
) -> dict[str, Any]:
    enriched = dict(item)
    enriched.update(
        {
            "run_id": compiled_call.run_id,
            "connector_id": compiled_call.connector_id,
            "operation": compiled_call.operation,
        }
    )
    return enriched


def _validate_connector_result(
    result: ConnectorResult,
    *,
    compiled_call: CompiledConnectorCall,
) -> None:
    if result.status not in ("succeeded", "failed"):
        raise ConnectorContractViolation(
            f"adapter returned undeclared status for {compiled_call.connector_id!r}: "
            f"{result.status!r}"
        )

    allowed_evidence_kinds = set(compiled_call.evidence_kinds)
    for evidence in result.evidence:
        kind = evidence.get("kind")
        if kind not in allowed_evidence_kinds:
            raise ConnectorContractViolation(
                f"adapter returned undeclared evidence kind for "
                f"{compiled_call.connector_id!r}: {kind!r}"
            )


def _failed_outcome(
    compiled_call: CompiledConnectorCall,
    exc: Exception,
) -> ConnectorOutcome:
    return ConnectorOutcome(
        run_id=compiled_call.run_id,
        connector_id=compiled_call.connector_id,
        operation=compiled_call.operation,
        status="failed",
        summary=_safe_error_summary(exc),
        events=[
            _with_runtime_provenance(
                {"type": "connector.failed", "error_type": type(exc).__name__},
                compiled_call=compiled_call,
            )
        ],
    )


def _safe_error_summary(exc: Exception) -> str:
    return f"{type(exc).__name__}: connector adapter failed"
