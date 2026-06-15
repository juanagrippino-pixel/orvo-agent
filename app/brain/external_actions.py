"""External action provider boundary for sidecar integration tooling.

This module keeps Composio/Pipedream-style connector marketplaces behind an
Orvo-owned contract: explicit action allowlists, approval gates for writes,
durable pre-side-effect run-ledger audit records, idempotency checks, and
redacted summaries. The providers here are client-adapter shells; production
clients can be injected later without changing Orvo's control-plane ownership
boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from app.brain.run_ledger import ConnectorRunOutcome, RunLedger, RunRecord
from app.brain.security.redaction import redact_secrets, redact_text
from app.brain.workflow_action_ledger import WorkflowActionLedgerRecord, WorkflowActionLedgerStore

ExternalActionOperationType = Literal["read", "write"]
ExternalActionStatus = Literal["succeeded", "failed", "skipped"]

RESERVED_CORE_TOOLKITS: set[str] = {
    "tiendanube",
    "nuvemshop",
    "mercadolibre",
    "mercado_libre",
    "woocommerce",
    "whatsapp",
    "meta_whatsapp",
    "meta_cloud_api",
}
_SAFE_TOOLKIT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SAFE_ACTION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class ExternalActionClient(Protocol):
    """Minimal injected client contract for provider SDKs/workflow APIs."""

    def execute(
        self,
        *,
        toolkit: str,
        action_key: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]: ...


class ExternalActionError(Exception):
    """Safe error raised by the external action boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = redact_text(message) or "External action error"
        super().__init__(self.message)


@dataclass(frozen=True)
class ExternalActionRequest:
    """Provider-agnostic request to a low-risk external action/read.

    ``payload`` is passed raw to the injected client so the provider can perform
    the action, but all Orvo-owned projections and ledger records are redacted.
    Write requests must reference an approved WorkflowActionLedger record.
    """

    business_id: str
    run_id: str
    toolkit: str
    action_key: str
    operation_type: ExternalActionOperationType
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    actor_ref: str | None = None
    case_id: str = ""
    workflow_action_ledger_id: str | None = None


@dataclass(frozen=True)
class ExternalActionProvider:
    """Common provider shell with explicit toolkit/action allowlists."""

    client: ExternalActionClient
    allowed_actions: set[tuple[str, str]]
    provider_name: str

    def is_allowed(self, request: ExternalActionRequest) -> bool:
        return (request.toolkit, request.action_key) in self.allowed_actions

    def execute(self, request: ExternalActionRequest) -> dict[str, Any]:
        return self.client.execute(
            toolkit=request.toolkit,
            action_key=request.action_key,
            payload=request.payload,
            idempotency_key=request.idempotency_key,
        )

    def provider_response_ref(self, request: ExternalActionRequest, response: dict[str, Any]) -> str:
        external_id = response.get("external_id") or response.get("id") or "unknown"
        return f"{self.provider_name}://{request.toolkit}/{request.action_key}/{external_id}"


class ComposioProvider(ExternalActionProvider):
    def __init__(self, *, client: ExternalActionClient, allowed_actions: set[tuple[str, str]]) -> None:
        super().__init__(client=client, allowed_actions=allowed_actions, provider_name="composio")


class PipedreamProvider(ExternalActionProvider):
    def __init__(self, *, client: ExternalActionClient, allowed_actions: set[tuple[str, str]]) -> None:
        super().__init__(client=client, allowed_actions=allowed_actions, provider_name="pipedream")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _redacted_dict(value: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_secrets(value or {})
    return redacted if isinstance(redacted, dict) else {}


def _response_summary(response: dict[str, Any]) -> dict[str, Any]:
    external_id = response.get("external_id") or response.get("id") or "unknown"
    return {
        "external_id": str(external_id),
        "result_keys": sorted(str(key) for key in response.keys()),
    }


def _validate_request(request: ExternalActionRequest) -> None:
    required = {
        "business_id": request.business_id,
        "run_id": request.run_id,
        "toolkit": request.toolkit,
        "action_key": request.action_key,
        "idempotency_key": request.idempotency_key,
    }
    if any(not isinstance(value, str) or not value.strip() for value in required.values()):
        raise ExternalActionError("external_action_invalid_request", "external action request requires non-empty ids")
    if not _SAFE_TOOLKIT_RE.fullmatch(request.toolkit):
        raise ExternalActionError(
            "external_action_invalid_request",
            "external action toolkit must be a lowercase safe control-plane identifier",
        )
    if not _SAFE_ACTION_KEY_RE.fullmatch(request.action_key):
        raise ExternalActionError(
            "external_action_invalid_request",
            "external action key must be a lowercase safe control-plane identifier",
        )
    if request.operation_type not in {"read", "write"}:
        raise ExternalActionError("external_action_invalid_request", "external action operation_type must be read or write")
    if request.operation_type == "write" and (not isinstance(request.case_id, str) or not request.case_id.strip()):
        raise ExternalActionError("external_action_invalid_request", "external write action requires a non-empty case_id")
    if not isinstance(request.payload, dict):
        raise ExternalActionError("external_action_invalid_request", "external action payload must be an object")


def _load_scoped_run(run_ledger: RunLedger, request: ExternalActionRequest) -> RunRecord:
    run = run_ledger.get_run(request.run_id)
    if run is None:
        raise ExternalActionError("external_action_run_not_found", "external action run not found")
    if run.business_id != request.business_id:
        raise ExternalActionError("external_action_run_scope_mismatch", "external action run scope mismatch")
    return run


def _ledger_metadata(
    *,
    provider: ExternalActionProvider,
    request: ExternalActionRequest,
    approval_state: str,
    allowlist_decision: str = "allowed",
    idempotency_decision: str = "new",
    execution_state: str | None = None,
    reserved_toolkit: str | None = None,
    response: dict[str, Any] | None = None,
    provider_response_ref: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "provider": provider.provider_name,
        "toolkit": request.toolkit,
        "action_key": request.action_key,
        "operation_type": request.operation_type,
        "idempotency_key": request.idempotency_key,
        "idempotency_decision": idempotency_decision,
        "actor_ref": request.actor_ref,
        "approval_state": approval_state,
        "allowlist_decision": allowlist_decision,
        "payload": _redacted_dict(request.payload),
    }
    if request.workflow_action_ledger_id is not None:
        metadata["workflow_action_ledger_id"] = request.workflow_action_ledger_id
    if execution_state is not None:
        metadata["execution_state"] = execution_state
    if reserved_toolkit is not None:
        metadata["reserved_toolkit"] = reserved_toolkit
    if response is not None:
        metadata["response_summary"] = _response_summary(response)
    if provider_response_ref is not None:
        metadata["provider_response_ref"] = provider_response_ref
    return redact_secrets(metadata)


def _append_audit_outcome(
    *,
    run_ledger: RunLedger,
    provider: ExternalActionProvider,
    request: ExternalActionRequest,
    status: ExternalActionStatus,
    now: datetime,
    metadata: dict[str, Any],
    error_summary: str | None = None,
) -> None:
    run_ledger.append_connector_outcome(
        request.run_id,
        ConnectorRunOutcome(
            connector_id=f"external-action:{provider.provider_name}:{request.toolkit}:{request.action_key}",
            connector_type="external_action",
            status=status,
            started_at=now,
            finished_at=now,
            error_summary=error_summary,
            metadata=metadata,
        ),
    )


def _has_executed_idempotency_key(run: RunRecord, idempotency_key: str) -> bool:
    for outcome in run.connector_outcomes:
        if outcome.metadata.get("idempotency_key") != idempotency_key:
            continue
        if outcome.status == "succeeded" or outcome.metadata.get("execution_state") == "executed":
            return True
    return False


def _find_approved_workflow_action(
    workflow_action_ledger: WorkflowActionLedgerStore | None,
    *,
    provider: ExternalActionProvider,
    request: ExternalActionRequest,
) -> WorkflowActionLedgerRecord | None:
    if workflow_action_ledger is None or not request.workflow_action_ledger_id:
        return None
    for record in workflow_action_ledger.list_actions(business_id=request.business_id):
        if record.ledger_id != request.workflow_action_ledger_id:
            continue
        if record.approval_state != "approved" or record.execution_state != "pending_execution":
            return None
        if record.idempotency_key != request.idempotency_key:
            return None
        if record.case_id != request.case_id:
            return None
        if record.action_key != "request_external_action":
            return None
        if record.params.get("provider") != provider.provider_name:
            return None
        if record.params.get("toolkit") != request.toolkit:
            return None
        if record.params.get("external_action_key") != request.action_key:
            return None
        return record
    return None


def _approval_state(
    request: ExternalActionRequest,
    workflow_record: WorkflowActionLedgerRecord | None,
) -> str:
    if request.operation_type == "read":
        return "not_required"
    return "approved" if workflow_record is not None else "pending_approval"


def _result_projection(
    *,
    provider: ExternalActionProvider,
    request: ExternalActionRequest,
    status: ExternalActionStatus,
    approval_state: str,
    response: dict[str, Any] | None = None,
    provider_response_ref: str | None = None,
) -> dict[str, Any]:
    projection: dict[str, Any] = {
        "provider": provider.provider_name,
        "toolkit": request.toolkit,
        "action_key": request.action_key,
        "operation_type": request.operation_type,
        "status": status,
        "idempotency_key": request.idempotency_key,
        "provider_response_ref": provider_response_ref,
        "approval_state": approval_state,
    }
    if response is not None:
        projection["response"] = _redacted_dict(response)
    return redact_secrets(projection)


def execute_external_action(
    provider: ExternalActionProvider,
    request: ExternalActionRequest,
    *,
    run_ledger: RunLedger,
    workflow_action_ledger: WorkflowActionLedgerStore | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute one allowlisted provider action and append Orvo audit outcomes.

    Fail-closed cases are audited as ``skipped`` connector outcomes after run
    scope is verified. Successful/provider-failed calls get a durable
    ``attempt_planned_before_side_effect`` audit outcome before the client is
    called, so Orvo has a pre-side-effect ledger entry even if the provider call
    or final append fails.
    """

    timestamp = (now or _now_utc()).astimezone(timezone.utc)
    _validate_request(request)
    scoped_run = _load_scoped_run(run_ledger, request)
    workflow_record = _find_approved_workflow_action(workflow_action_ledger, provider=provider, request=request)
    approval_state = _approval_state(request, workflow_record)

    if _has_executed_idempotency_key(scoped_run, request.idempotency_key):
        metadata = _ledger_metadata(
            provider=provider,
            request=request,
            approval_state=approval_state,
            idempotency_decision="duplicate",
        )
        _append_audit_outcome(
            run_ledger=run_ledger,
            provider=provider,
            request=request,
            status="skipped",
            now=timestamp,
            metadata=metadata,
            error_summary="external action duplicate idempotency key",
        )
        raise ExternalActionError("external_action_duplicate", "external action idempotency key was already executed")

    normalized_toolkit = request.toolkit.lower().strip()
    if normalized_toolkit in RESERVED_CORE_TOOLKITS:
        metadata = _ledger_metadata(
            provider=provider,
            request=request,
            approval_state=approval_state,
            allowlist_decision="denied",
            reserved_toolkit=normalized_toolkit,
        )
        _append_audit_outcome(
            run_ledger=run_ledger,
            provider=provider,
            request=request,
            status="skipped",
            now=timestamp,
            metadata=metadata,
            error_summary="external action toolkit is reserved for Orvo core connectors",
        )
        raise ExternalActionError(
            "external_action_toolkit_reserved",
            "external action toolkit is reserved for Orvo core connectors",
        )

    if not provider.is_allowed(request):
        metadata = _ledger_metadata(
            provider=provider,
            request=request,
            approval_state=approval_state,
            allowlist_decision="denied",
        )
        _append_audit_outcome(
            run_ledger=run_ledger,
            provider=provider,
            request=request,
            status="skipped",
            now=timestamp,
            metadata=metadata,
            error_summary="external action not allowed by Orvo allowlist",
        )
        raise ExternalActionError("external_action_not_allowed", "external action is not allowed by Orvo policy")

    if request.operation_type == "write" and workflow_record is None:
        metadata = _ledger_metadata(provider=provider, request=request, approval_state=approval_state)
        _append_audit_outcome(
            run_ledger=run_ledger,
            provider=provider,
            request=request,
            status="skipped",
            now=timestamp,
            metadata=metadata,
            error_summary="external write action requires approved workflow action before execution",
        )
        raise ExternalActionError(
            "external_action_approval_required",
            "external write action requires approved workflow action before side effects",
        )

    planned_metadata = _ledger_metadata(
        provider=provider,
        request=request,
        approval_state=approval_state,
        execution_state="attempt_planned_before_side_effect",
    )
    _append_audit_outcome(
        run_ledger=run_ledger,
        provider=provider,
        request=request,
        status="skipped",
        now=timestamp,
        metadata=planned_metadata,
    )

    try:
        response = provider.execute(request)
        if not isinstance(response, dict):
            raise TypeError("external provider response must be an object")
    except Exception as exc:
        metadata = _ledger_metadata(provider=provider, request=request, approval_state=approval_state)
        _append_audit_outcome(
            run_ledger=run_ledger,
            provider=provider,
            request=request,
            status="failed",
            now=timestamp,
            metadata=metadata,
            error_summary="external provider failed",
        )
        raise ExternalActionError("external_action_provider_failed", "external provider failed") from exc

    response_ref = provider.provider_response_ref(request, response)
    metadata = _ledger_metadata(
        provider=provider,
        request=request,
        approval_state=approval_state,
        response=response,
        provider_response_ref=response_ref,
        execution_state="executed",
    )
    _append_audit_outcome(
        run_ledger=run_ledger,
        provider=provider,
        request=request,
        status="succeeded",
        now=timestamp,
        metadata=metadata,
    )
    return _result_projection(
        provider=provider,
        request=request,
        status="succeeded",
        approval_state=approval_state,
        response=response,
        provider_response_ref=response_ref,
    )
