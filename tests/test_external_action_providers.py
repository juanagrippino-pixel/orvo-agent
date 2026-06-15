from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from app.brain.external_actions import (
    ComposioProvider,
    ExternalActionError,
    ExternalActionRequest,
    PipedreamProvider,
    execute_external_action,
)
from app.brain.run_ledger import InMemoryRunLedger
from app.brain.workflow_action_ledger import InMemoryWorkflowActionLedgerStore


def utc_dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 2, hour, minute, tzinfo=timezone.utc)


class FakeExternalActionClient:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {"external_id": "call-1", "ok": True}
        self.calls: list[dict[str, Any]] = []

    def execute(self, *, toolkit: str, action_key: str, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self.calls.append(
            {
                "toolkit": toolkit,
                "action_key": action_key,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
        )
        return self.response


class BadResponseClient:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, toolkit: str, action_key: str, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self.calls += 1
        return cast(dict[str, Any], ["not", "a", "dict"])


def _ledger() -> InMemoryRunLedger:
    ledger = InMemoryRunLedger()
    ledger.create_run(run_id="run-ext-1", business_id="artemea", trigger_type="manual", started_at=utc_dt(9))
    return ledger


def _approved_external_action_ledger(*, idempotency_key: str) -> InMemoryWorkflowActionLedgerStore:
    workflow_ledger = InMemoryWorkflowActionLedgerStore()
    write = workflow_ledger.record_planned_action(
        business_id="artemea",
        case_id="case-1",
        action_key="request_external_action",
        idempotency_key=idempotency_key,
        execution_state="blocked_approval_required",
        approval_required=True,
        source="manual_operator",
        actor_ref="operator:juan",
        params={
            "provider": "pipedream",
            "toolkit": "hubspot",
            "external_action_key": "hubspot.create_ticket",
        },
        now=utc_dt(10),
    )
    assert write.approval_request is not None
    workflow_ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=write.approval_request.approval_request_id,
        decision="approved",
        actor_ref="operator:admin",
        reason="approved low-risk CRM test",
        now=utc_dt(10, 30),
    )
    return workflow_ledger


def test_composio_read_action_executes_allowed_tool_and_records_redacted_run_ledger_outcomes():
    client = FakeExternalActionClient(response={"external_id": "sheet-call-1", "rows": 2, "refresh_token": "leak"})
    provider = ComposioProvider(
        client=client,
        allowed_actions={("googlesheets", "googlesheets.read_values")},
    )
    ledger = _ledger()
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values",
        operation_type="read",
        payload={"range": "Daily!A1:B2", "access_token": "sheet-secret"},
        idempotency_key="external/artemea/sheets/read/1",
        actor_ref="operator:juan",
    )

    result = execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(9, 1))

    assert result == {
        "provider": "composio",
        "toolkit": "googlesheets",
        "action_key": "googlesheets.read_values",
        "operation_type": "read",
        "status": "succeeded",
        "idempotency_key": "external/artemea/sheets/read/1",
        "provider_response_ref": "composio://googlesheets/googlesheets.read_values/sheet-call-1",
        "approval_state": "not_required",
        "response": {"external_id": "sheet-call-1", "rows": 2, "refresh_token": "[REDACTED]"},
    }
    assert client.calls == [
        {
            "toolkit": "googlesheets",
            "action_key": "googlesheets.read_values",
            "payload": {"range": "Daily!A1:B2", "access_token": "sheet-secret"},
            "idempotency_key": "external/artemea/sheets/read/1",
        }
    ]

    run = ledger.get_run("run-ext-1")
    assert run is not None
    assert len(run.connector_outcomes) == 2
    planned, outcome = run.connector_outcomes
    assert planned.status == "skipped"
    assert planned.metadata["execution_state"] == "attempt_planned_before_side_effect"
    assert outcome.connector_id == "external-action:composio:googlesheets:googlesheets.read_values"
    assert outcome.connector_type == "external_action"
    assert outcome.status == "succeeded"
    assert outcome.started_at == utc_dt(9, 1)
    assert outcome.finished_at == utc_dt(9, 1)
    assert outcome.metadata["payload"] == {"range": "Daily!A1:B2", "access_token": "[REDACTED]"}
    assert outcome.metadata["response_summary"] == {
        "external_id": "sheet-call-1",
        "result_keys": ["external_id", "refresh_token", "rows"],
    }
    assert "sheet-secret" not in str(outcome.metadata)
    assert "leak" not in str(outcome.metadata)


def test_disallowed_external_action_fails_closed_before_client_call_and_audits_skip():
    client = FakeExternalActionClient()
    provider = ComposioProvider(client=client, allowed_actions={("slack", "slack.post_message")})
    ledger = _ledger()
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.delete_spreadsheet",
        operation_type="write",
        payload={"spreadsheet_id": "abc", "api_key": "must-not-leak"},
        idempotency_key="external/artemea/sheets/delete/1",
        actor_ref="operator:juan",
        case_id="case-1",
        workflow_action_ledger_id="workflow-action/artemea/not-real",
    )

    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(10))

    assert exc.value.code == "external_action_not_allowed"
    assert client.calls == []
    run = ledger.get_run("run-ext-1")
    assert run is not None
    outcome = run.connector_outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.metadata["allowlist_decision"] == "denied"
    assert outcome.metadata["payload"] == {"spreadsheet_id": "abc", "api_key": "[REDACTED]"}
    assert "must-not-leak" not in str(outcome.model_dump(mode="json"))


def test_external_write_action_requires_durable_approved_workflow_action_before_side_effect():
    client = FakeExternalActionClient()
    provider = PipedreamProvider(client=client, allowed_actions={("hubspot", "hubspot.create_ticket")})
    ledger = _ledger()
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="hubspot",
        action_key="hubspot.create_ticket",
        operation_type="write",
        payload={"subject": "Pedido demorado", "token": "crm-secret"},
        idempotency_key="external/artemea/hubspot/ticket/1",
        actor_ref="operator:juan",
        case_id="case-1",
    )

    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(11))

    assert exc.value.code == "external_action_approval_required"
    assert client.calls == []
    outcome = ledger.get_run("run-ext-1").connector_outcomes[0]  # type: ignore[union-attr]
    assert outcome.status == "skipped"
    assert outcome.metadata["approval_state"] == "pending_approval"
    assert outcome.metadata["provider"] == "pipedream"
    assert "crm-secret" not in str(outcome.model_dump(mode="json"))


def test_pipedream_write_approval_must_match_requested_case_id():
    client = FakeExternalActionClient()
    provider = PipedreamProvider(client=client, allowed_actions={("hubspot", "hubspot.create_ticket")})
    ledger = _ledger()
    workflow_ledger = _approved_external_action_ledger(idempotency_key="external/artemea/hubspot/ticket/1")
    approval_record = workflow_ledger.list_actions(business_id="artemea")[0]
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="hubspot",
        action_key="hubspot.create_ticket",
        operation_type="write",
        payload={"subject": "Pedido demorado", "token": "crm-secret"},
        idempotency_key="external/artemea/hubspot/ticket/1",
        actor_ref="operator:juan",
        case_id="case-2",
        workflow_action_ledger_id=approval_record.ledger_id,
    )

    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, request, run_ledger=ledger, workflow_action_ledger=workflow_ledger, now=utc_dt(11, 1))

    assert exc.value.code == "external_action_approval_required"
    assert client.calls == []
    outcome = ledger.get_run("run-ext-1").connector_outcomes[0]  # type: ignore[union-attr]
    assert outcome.status == "skipped"
    assert outcome.metadata["approval_state"] == "pending_approval"
    assert outcome.metadata["workflow_action_ledger_id"] == approval_record.ledger_id
    assert "crm-secret" not in str(outcome.model_dump(mode="json"))


def test_pipedream_write_action_executes_when_workflow_approval_matches_request():
    client = FakeExternalActionClient(response={"id": "ticket-123", "secret": "provider-secret"})
    provider = PipedreamProvider(client=client, allowed_actions={("hubspot", "hubspot.create_ticket")})
    ledger = _ledger()
    idempotency_key = "external/artemea/hubspot/ticket/1"
    workflow_ledger = _approved_external_action_ledger(idempotency_key=idempotency_key)
    approval_record = workflow_ledger.list_actions(business_id="artemea")[0]
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="hubspot",
        action_key="hubspot.create_ticket",
        operation_type="write",
        payload={"subject": "Pedido demorado", "token": "crm-secret"},
        idempotency_key=idempotency_key,
        actor_ref="operator:juan",
        case_id="case-1",
        workflow_action_ledger_id=approval_record.ledger_id,
    )

    result = execute_external_action(provider, request, run_ledger=ledger, workflow_action_ledger=workflow_ledger, now=utc_dt(11, 1))

    assert result["status"] == "succeeded"
    assert result["provider"] == "pipedream"
    assert result["provider_response_ref"] == "pipedream://hubspot/hubspot.create_ticket/ticket-123"
    assert result["approval_state"] == "approved"
    assert result["response"] == {"id": "ticket-123", "secret": "[REDACTED]"}
    assert client.calls[0]["payload"] == {"subject": "Pedido demorado", "token": "crm-secret"}
    planned, outcome = ledger.get_run("run-ext-1").connector_outcomes  # type: ignore[union-attr]
    assert planned.metadata["execution_state"] == "attempt_planned_before_side_effect"
    assert outcome.status == "succeeded"
    assert outcome.metadata["approval_state"] == "approved"
    assert outcome.metadata["workflow_action_ledger_id"] == approval_record.ledger_id
    assert outcome.metadata["response_summary"] == {"external_id": "ticket-123", "result_keys": ["id", "secret"]}
    assert "crm-secret" not in str(outcome.model_dump(mode="json"))
    assert "provider-secret" not in str(outcome.model_dump(mode="json"))


def test_duplicate_idempotency_key_is_skipped_before_second_provider_call():
    client = FakeExternalActionClient(response={"external_id": "sheet-call-1", "ok": True})
    provider = ComposioProvider(client=client, allowed_actions={("googlesheets", "googlesheets.read_values")})
    ledger = _ledger()
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values",
        operation_type="read",
        payload={"range": "Daily!A1:B2"},
        idempotency_key="external/artemea/sheets/read/duplicate",
    )
    execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(9, 1))

    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(9, 2))

    assert exc.value.code == "external_action_duplicate"
    assert len(client.calls) == 1
    assert ledger.get_run("run-ext-1").connector_outcomes[-1].metadata["idempotency_decision"] == "duplicate"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("toolkit", "action_key"),
    [
        ("tiendanube", "tiendanube.get_orders"),
        ("woocommerce", "woocommerce.get_orders"),
    ],
)
def test_critical_core_connector_toolkits_are_structurally_denied_even_if_allowlisted(toolkit: str, action_key: str):
    client = FakeExternalActionClient()
    provider = ComposioProvider(client=client, allowed_actions={(toolkit, action_key)})
    ledger = _ledger()
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit=toolkit,
        action_key=action_key,
        operation_type="read",
        payload={},
        idempotency_key=f"external/artemea/{toolkit}/read/1",
    )

    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(12))

    assert exc.value.code == "external_action_toolkit_reserved"
    assert client.calls == []
    assert ledger.get_run("run-ext-1").connector_outcomes[0].metadata["reserved_toolkit"] == toolkit  # type: ignore[union-attr]


def test_invalid_request_and_run_scope_fail_before_provider_side_effect():
    client = FakeExternalActionClient()
    provider = ComposioProvider(client=client, allowed_actions={("googlesheets", "googlesheets.read_values")})
    ledger = _ledger()
    bad_operation = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values",
        operation_type=cast(Any, "delete"),
        payload={},
        idempotency_key="external/artemea/sheets/read/invalid",
    )
    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, bad_operation, run_ledger=ledger, now=utc_dt(13))
    assert exc.value.code == "external_action_invalid_request"

    empty_idempotency = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values",
        operation_type="read",
        payload={},
        idempotency_key="",
    )
    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, empty_idempotency, run_ledger=ledger, now=utc_dt(13, 1))
    assert exc.value.code == "external_action_invalid_request"

    wrong_business = ExternalActionRequest(
        business_id="other-business",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values",
        operation_type="read",
        payload={},
        idempotency_key="external/other/sheets/read/1",
    )
    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, wrong_business, run_ledger=ledger, now=utc_dt(13, 2))
    assert exc.value.code == "external_action_run_scope_mismatch"
    assert client.calls == []


def test_external_action_toolkit_and_action_key_must_be_safe_control_plane_identifiers():
    client = FakeExternalActionClient()
    secret_tail = "raw-provider-secret"
    provider = ComposioProvider(
        client=client,
        allowed_actions={
            ("googlesheets?access_token=" + secret_tail, "googlesheets.read_values"),
            ("googlesheets", "googlesheets.read_values/../../unsafe"),
        },
    )
    ledger = _ledger()

    bad_toolkit = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets?access_token=" + secret_tail,
        action_key="googlesheets.read_values",
        operation_type="read",
        payload={},
        idempotency_key="external/artemea/sheets/read/bad-toolkit",
    )
    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, bad_toolkit, run_ledger=ledger, now=utc_dt(13, 3))
    assert exc.value.code == "external_action_invalid_request"

    bad_action_key = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values/../../unsafe",
        operation_type="read",
        payload={},
        idempotency_key="external/artemea/sheets/read/bad-action-key",
    )
    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, bad_action_key, run_ledger=ledger, now=utc_dt(13, 4))
    assert exc.value.code == "external_action_invalid_request"

    assert client.calls == []
    assert ledger.get_run("run-ext-1").connector_outcomes == []  # type: ignore[union-attr]


def test_malformed_provider_response_has_pre_side_effect_audit_and_safe_failure_message():
    client = BadResponseClient()
    provider = ComposioProvider(client=client, allowed_actions={("googlesheets", "googlesheets.read_values")})
    ledger = _ledger()
    request = ExternalActionRequest(
        business_id="artemea",
        run_id="run-ext-1",
        toolkit="googlesheets",
        action_key="googlesheets.read_values",
        operation_type="read",
        payload={},
        idempotency_key="external/artemea/sheets/read/bad-response",
    )

    with pytest.raises(ExternalActionError) as exc:
        execute_external_action(provider, request, run_ledger=ledger, now=utc_dt(14))

    assert exc.value.code == "external_action_provider_failed"
    assert exc.value.message == "external provider failed"
    assert client.calls == 1
    planned, failed = ledger.get_run("run-ext-1").connector_outcomes  # type: ignore[union-attr]
    assert planned.metadata["execution_state"] == "attempt_planned_before_side_effect"
    assert failed.status == "failed"
    assert failed.error_summary == "external provider failed"
