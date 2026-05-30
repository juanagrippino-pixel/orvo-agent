import json
import threading
from dataclasses import asdict

import pytest

from plugins.orvo_control_plane.runtime import (
    ConnectorContract,
    ConnectorExecutionRequest,
    ConnectorExecutor,
    ConnectorRegistry,
    ConnectorResult,
    ConnectorRunLedger,
    compile_connector_call,
)


def test_compile_connector_call_uses_registry_contract_and_preserves_secret_refs_only():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain", "api_version"),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )

    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo-test.myshopify.com", "api_version": "2026-04"},
        secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        run_id="run_123",
    )

    assert compiled.run_id == "run_123"
    assert compiled.connector_id == "shopify"
    assert compiled.contract_name == "shopify.orders"
    assert compiled.contract_version == "2026-05-26"
    assert compiled.public_config == {
        "shop_domain": "orvo-test.myshopify.com",
        "api_version": "2026-04",
    }
    assert compiled.secret_refs == {"admin_token": "secret://tenant/shopify/admin-token"}
    assert "secret://tenant/shopify/admin-token" not in repr(compiled.public_config)
    assert asdict(compiled)["public_config"] == {
        "shop_domain": "orvo-test.myshopify.com",
        "api_version": "2026-04",
    }
    assert json.loads(json.dumps(compiled.public_config)) == {
        "shop_domain": "orvo-test.myshopify.com",
        "api_version": "2026-04",
    }


def test_compile_connector_call_rejects_public_config_not_declared_by_registry():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )

    with pytest.raises(ValueError, match="not declared by connector registry"):
        compile_connector_call(
            registry=registry,
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com", "admin_token": "raw-token"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
            run_id="run_123",
        )


def test_connector_executor_captures_run_scoped_outcome_and_evidence():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )

    seen_calls = []

    def shopify_adapter(compiled_call):
        seen_calls.append(compiled_call)
        return ConnectorResult(
            status="succeeded",
            summary="pulled 2 orders",
            evidence=[{"kind": "orders_snapshot", "uri": "store://evidence/orders-1"}],
            events=[{"type": "orders.pulled", "count": 2}],
        )

    executor = ConnectorExecutor(registry=registry, adapters={"shopify": shopify_adapter})

    outcome = executor.execute(
        ConnectorExecutionRequest(
            run_id="run_abc",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    assert seen_calls[0].run_id == "run_abc"
    assert outcome.run_id == "run_abc"
    assert outcome.connector_id == "shopify"
    assert outcome.operation == "orders.pull"
    assert outcome.status == "succeeded"
    assert outcome.summary == "pulled 2 orders"
    assert outcome.evidence == [
        {
            "run_id": "run_abc",
            "connector_id": "shopify",
            "operation": "orders.pull",
            "kind": "orders_snapshot",
            "uri": "store://evidence/orders-1",
        }
    ]
    assert outcome.events == [
        {
            "run_id": "run_abc",
            "connector_id": "shopify",
            "operation": "orders.pull",
            "type": "orders.pulled",
            "count": 2,
        }
    ]


def test_connector_executor_turns_adapter_exception_into_failed_outcome_for_case_workflows():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )

    def broken_adapter(_compiled_call):
        raise RuntimeError("Shopify 503 secret://tenant/shopify/admin-token unavailable")

    executor = ConnectorExecutor(registry=registry, adapters={"shopify": broken_adapter})

    outcome = executor.execute(
        ConnectorExecutionRequest(
            run_id="run_failure",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    assert outcome.status == "failed"
    assert outcome.run_id == "run_failure"
    assert outcome.summary == "RuntimeError: connector adapter failed"
    assert "secret://tenant/shopify/admin-token" not in repr(outcome)
    assert outcome.events == [
        {
            "run_id": "run_failure",
            "connector_id": "shopify",
            "operation": "orders.pull",
            "type": "connector.failed",
            "error_type": "RuntimeError",
        }
    ]


def test_connector_executor_rejects_adapter_status_not_declared_by_runtime_contract():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )

    def invalid_status_adapter(_compiled_call):
        return ConnectorResult(status="partial")  # type: ignore[arg-type]

    executor = ConnectorExecutor(registry=registry, adapters={"shopify": invalid_status_adapter})

    outcome = executor.execute(
        ConnectorExecutionRequest(
            run_id="run_bad_status",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    assert outcome.status == "failed"
    assert outcome.summary == "ConnectorContractViolation: connector adapter failed"
    assert outcome.events == [
        {
            "run_id": "run_bad_status",
            "connector_id": "shopify",
            "operation": "orders.pull",
            "type": "connector.failed",
            "error_type": "ConnectorContractViolation",
        }
    ]


def test_connector_executor_rejects_evidence_kind_not_declared_by_registry():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )

    def invalid_evidence_adapter(_compiled_call):
        return ConnectorResult(
            status="succeeded",
            evidence=[{"kind": "raw_admin_token_dump", "uri": "store://bad"}],
        )

    executor = ConnectorExecutor(registry=registry, adapters={"shopify": invalid_evidence_adapter})

    outcome = executor.execute(
        ConnectorExecutionRequest(
            run_id="run_bad_evidence",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    assert outcome.status == "failed"
    assert outcome.summary == "ConnectorContractViolation: connector adapter failed"
    assert outcome.events == [
        {
            "run_id": "run_bad_evidence",
            "connector_id": "shopify",
            "operation": "orders.pull",
            "type": "connector.failed",
            "error_type": "ConnectorContractViolation",
        }
    ]


def test_connector_executor_records_ordered_audit_transitions_with_lineage():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([101.0, 102.0]).__next__)

    def shopify_adapter(_compiled_call):
        return ConnectorResult(
            status="succeeded",
            summary="pulled 2 orders",
            evidence=[{"kind": "orders_snapshot", "uri": "store://evidence/orders-1"}],
            events=[{"type": "orders.pulled", "count": 2}],
        )

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": shopify_adapter},
        audit_ledger=ledger,
    )

    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_audit_success",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    events = ledger.events_for_run("run_audit_success")
    assert [event.sequence for event in events] == [1, 2]
    assert [event.created_at for event in events] == [101.0, 102.0]
    assert [event.event_type for event in events] == [
        "connector.execution.started",
        "connector.execution.succeeded",
    ]
    assert [(event.from_state, event.to_state) for event in events] == [
        ("requested", "running"),
        ("running", "succeeded"),
    ]
    assert all(event.contract_name == "shopify.orders" for event in events)
    assert all(event.contract_version == "2026-05-26" for event in events)
    assert events[0].payload == {
        "public_config": {"shop_domain": "orvo-test.myshopify.com"},
        "secret_ref_keys": ["admin_token"],
        "evidence_kinds": ["orders_snapshot"],
    }
    assert "secret://tenant/shopify/admin-token" not in repr(events)
    assert events[1].payload == {
        "summary": "pulled 2 orders",
        "evidence_count": 1,
        "event_count": 1,
    }


def test_connector_executor_records_redacted_failed_audit_transition():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    raw_token = "sk_live_" + "abcdefghijklmnopqrstuvwxyz123456"
    ledger = ConnectorRunLedger(clock=iter([201.0, 202.0]).__next__)

    def broken_adapter(_compiled_call):
        raise RuntimeError(
            f"Shopify 503 token={raw_token} secret://tenant/shopify/admin-token unavailable"
        )

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": broken_adapter},
        audit_ledger=ledger,
    )

    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_audit_failure",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    failed = ledger.events_for_run("run_audit_failure")[-1]
    assert failed.event_type == "connector.execution.failed"
    assert failed.from_state == "running"
    assert failed.to_state == "failed"
    assert failed.payload == {
        "summary": "RuntimeError: connector adapter failed",
        "error_type": "RuntimeError",
    }
    assert raw_token not in repr(ledger.events_for_run("run_audit_failure"))
    assert "secret://tenant/shopify/admin-token" not in repr(ledger.events_for_run("run_audit_failure"))


def test_connector_run_ledger_replay_is_run_scoped_ordered_and_redacted():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    raw_token = "sk_live_" + "abcdefghijklmnopqrstuvwxyz123456"
    ledger = ConnectorRunLedger(clock=iter([301.0, 302.0, 303.0, 304.0]).__next__)

    def shopify_adapter(_compiled_call):
        return ConnectorResult(
            status="succeeded",
            summary=f"pulled with token {raw_token}",
            events=[{"type": "debug", "authorization": f"Bearer {raw_token}"}],
        )

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": shopify_adapter},
        audit_ledger=ledger,
    )
    for run_id in ("run_replay_a", "run_replay_b"):
        executor.execute(
            ConnectorExecutionRequest(
                run_id=run_id,
                connector_id="shopify",
                operation="orders.pull",
                public_config={"shop_domain": "orvo-test.myshopify.com"},
                secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
            )
        )

    replay = ledger.replay_run("run_replay_b")
    assert [event["sequence"] for event in replay] == [3, 4]
    assert [event["event_type"] for event in replay] == [
        "connector.execution.started",
        "connector.execution.succeeded",
    ]
    replay_json = json.dumps(replay, sort_keys=True)
    assert raw_token not in replay_json
    assert "secret://tenant/shopify/admin-token" not in replay_json
    assert replay[-1]["payload"]["event_count"] == 1


def test_connector_run_ledger_redacts_structured_sensitive_fields_and_secret_refs():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo-test.myshopify.com"},
        secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        run_id="run_redaction",
    )
    raw_opaque = "opaqueverysecrettokenvalue"
    secret_ref = "secret://tenant/shopify/admin-token"
    ledger = ConnectorRunLedger(clock=iter([401.0]).__next__)

    ledger.append(
        compiled_call=compiled,
        event_type="connector.debug.snapshot",
        from_state="running",
        to_state="running",
        payload={
            "authorization": f"Bearer {raw_opaque}",
            "password": raw_opaque,
            "nested": {"secret_ref": secret_ref},
        },
    )

    replay_json = json.dumps(ledger.replay_run("run_redaction"), sort_keys=True)
    assert raw_opaque not in replay_json
    assert secret_ref not in replay_json
    assert "***" in replay_json


def test_connector_executor_records_failed_transition_when_adapter_is_missing():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([501.0, 502.0]).__next__)
    executor = ConnectorExecutor(registry=registry, adapters={}, audit_ledger=ledger)

    outcome = executor.execute(
        ConnectorExecutionRequest(
            run_id="run_missing_adapter",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    assert outcome.status == "failed"
    assert outcome.summary == "ValueError: connector adapter failed"
    assert [event.event_type for event in ledger.events_for_run("run_missing_adapter")] == [
        "connector.execution.started",
        "connector.execution.failed",
    ]


def test_connector_executor_does_not_fail_primary_execution_when_audit_ledger_fails():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )

    class BrokenLedger:
        def append(self, **_kwargs):
            raise RuntimeError("audit sink unavailable")

    def shopify_adapter(_compiled_call):
        return ConnectorResult(status="succeeded", summary="pulled 2 orders")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": shopify_adapter},
        audit_ledger=BrokenLedger(),
    )

    outcome = executor.execute(
        ConnectorExecutionRequest(
            run_id="run_audit_sink_down",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo-test.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        )
    )

    assert outcome.status == "succeeded"
    assert outcome.summary == "pulled 2 orders"


def test_connector_run_ledger_assigns_unique_sequences_under_concurrent_appends():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo-test.myshopify.com"},
        secret_refs={"admin_token": "secret://tenant/shopify/admin-token"},
        run_id="run_concurrent",
    )
    worker_count = 8
    barrier = threading.Barrier(worker_count)

    def blocked_clock():
        barrier.wait(timeout=5)
        return 601.0

    ledger = ConnectorRunLedger(clock=blocked_clock)

    threads = [
        threading.Thread(
            target=ledger.append,
            kwargs={
                "compiled_call": compiled,
                "event_type": "connector.debug.snapshot",
                "from_state": "running",
                "to_state": "running",
            },
        )
        for _ in range(worker_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    sequences = [event.sequence for event in ledger.events_for_run("run_concurrent")]
    assert sorted(sequences) == list(range(1, worker_count + 1))


def test_registry_contains_returns_true_for_registered_connector():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
        )
    )

    assert "shopify" in registry
    assert "whatsapp" not in registry


def test_registry_list_all_returns_contracts_sorted_by_connector_id():
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="whatsapp",
            contract_name="whatsapp.messaging",
            contract_version="2026-05-26",
            operations=("message.send",),
        )
    )
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
        )
    )

    contracts = registry.list_all()
    assert len(contracts) == 2
    assert contracts[0].connector_id == "shopify"
    assert contracts[1].connector_id == "whatsapp"
    assert contracts[0].contract_name == "shopify.orders"


def test_registry_list_all_returns_empty_when_no_connectors_registered():
    registry = ConnectorRegistry()
    assert registry.list_all() == []


def test_run_ledger_run_summaries_returns_operator_facing_summaries_for_all_runs():
    from plugins.orvo_control_plane.runtime import ConnectorRunSummary

    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )
    registry.register(
        ConnectorContract(
            connector_id="whatsapp",
            contract_name="whatsapp.messaging",
            contract_version="2026-05-26",
            operations=("message.send",),
            allowed_public_config_keys=("to_number",),
            required_secret_ref_keys=("api_token",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([1000.0, 1001.0, 2000.0, 2001.0]).__next__)

    def shopify_adapter(_call):
        return ConnectorResult(
            status="succeeded",
            summary="pulled 3 orders",
            evidence=[{"kind": "orders_snapshot", "uri": "store://orders/3"}],
            events=[{"type": "orders.pulled", "count": 3}],
        )

    def whatsapp_adapter(_call):
        raise RuntimeError("whatsapp gateway timeout")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": shopify_adapter, "whatsapp": whatsapp_adapter},
        audit_ledger=ledger,
    )

    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_shopify_1",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/token"},
        )
    )
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_whatsapp_1",
            connector_id="whatsapp",
            operation="message.send",
            public_config={"to_number": "+5491100001111"},
            secret_refs={"api_token": "secret://tenant/whatsapp/token"},
        )
    )

    summaries = ledger.run_summaries()
    assert len(summaries) == 2
    assert all(isinstance(s, ConnectorRunSummary) for s in summaries)

    shopify_summary = next(s for s in summaries if s.connector_id == "shopify")
    assert shopify_summary.run_id == "run_shopify_1"
    assert shopify_summary.operation == "orders.pull"
    assert shopify_summary.status == "succeeded"
    assert shopify_summary.started_at == 1000.0
    assert shopify_summary.finished_at == 1001.0
    assert shopify_summary.evidence_count == 1
    assert shopify_summary.event_count == 1

    whatsapp_summary = next(s for s in summaries if s.connector_id == "whatsapp")
    assert whatsapp_summary.run_id == "run_whatsapp_1"
    assert whatsapp_summary.operation == "message.send"
    assert whatsapp_summary.status == "failed"
    assert whatsapp_summary.started_at == 2000.0
    assert whatsapp_summary.finished_at == 2001.0


def test_run_ledger_run_summaries_returns_empty_list_for_empty_ledger():
    ledger = ConnectorRunLedger()
    assert ledger.run_summaries() == []


def test_run_ledger_run_summaries_excludes_runs_with_only_started_transition():
    """A run that is still in-progress (only 'started' event) should show status as None."""
    from plugins.orvo_control_plane.runtime import ConnectorRunSummary

    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo.myshopify.com"},
        secret_refs={"admin_token": "secret://tenant/shopify/token"},
        run_id="run_in_progress",
    )
    ledger = ConnectorRunLedger(clock=iter([3000.0]).__next__)
    ledger.append(
        compiled_call=compiled,
        event_type="connector.execution.started",
        from_state="requested",
        to_state="running",
    )

    summaries = ledger.run_summaries()
    assert len(summaries) == 1
    summary = summaries[0]
    assert isinstance(summary, ConnectorRunSummary)
    assert summary.run_id == "run_in_progress"
    assert summary.status is None
    assert summary.started_at == 3000.0
    assert summary.finished_at is None


def test_run_ledger_run_summary_returns_single_run_by_id():
    """run_summary(run_id) returns the summary for a specific run, or None if not found."""
    from plugins.orvo_control_plane.runtime import ConnectorRunSummary

    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([4000.0, 4001.0]).__next__)

    def shopify_adapter(_call):
        return ConnectorResult(
            status="succeeded",
            summary="pulled 5 orders",
            evidence=[{"kind": "orders_snapshot", "uri": "store://orders/5"}],
            events=[{"type": "orders.pulled", "count": 5}],
        )

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": shopify_adapter},
        audit_ledger=ledger,
    )
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_lookup_target",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo.myshopify.com"},
            secret_refs={"admin_token": "secret://tenant/shopify/token"},
        )
    )

    summary = ledger.run_summary("run_lookup_target")
    assert isinstance(summary, ConnectorRunSummary)
    assert summary.run_id == "run_lookup_target"
    assert summary.connector_id == "shopify"
    assert summary.operation == "orders.pull"
    assert summary.status == "succeeded"
    assert summary.started_at == 4000.0
    assert summary.finished_at == 4001.0
    assert summary.evidence_count == 1
    assert summary.event_count == 1


def test_run_ledger_run_summary_returns_none_for_unknown_run_id():
    """run_summary(run_id) returns None when the run_id does not exist."""
    ledger = ConnectorRunLedger()
    assert ledger.run_summary("nonexistent_run_id") is None


def test_run_ledger_run_summary_returns_in_progress_run_with_none_status():
    """run_summary(run_id) for a run that only has a 'started' event returns status=None."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo.myshopify.com"},
        secret_refs={"admin_token": "secret://tenant/shopify/token"},
        run_id="run_in_progress_lookup",
    )
    ledger = ConnectorRunLedger(clock=iter([5000.0]).__next__)
    ledger.append(
        compiled_call=compiled,
        event_type="connector.execution.started",
        from_state="requested",
        to_state="running",
    )

    summary = ledger.run_summary("run_in_progress_lookup")
    assert summary is not None
    assert summary.status is None
    assert summary.finished_at is None
    assert summary.evidence_count == 0
    assert summary.event_count == 0


def test_registry_operations_for_returns_declared_operations():
    """operations_for(connector_id) returns the tuple of operations declared by the contract."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull", "orders.count"),
        )
    )

    ops = registry.operations_for("shopify")
    assert ops == ("orders.pull", "orders.count")


def test_registry_operations_for_raises_for_unregistered_connector():
    """operations_for(connector_id) raises ValueError if the connector is not registered."""
    registry = ConnectorRegistry()

    with pytest.raises(ValueError, match="connector not registered"):
        registry.operations_for("nonexistent")


def test_run_ledger_runs_by_connector_filters_summaries_by_connector_id():
    """runs_by_connector(connector_id) returns only summaries matching the given connector."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    registry.register(
        ConnectorContract(
            connector_id="whatsapp",
            contract_name="whatsapp.messaging",
            contract_version="2026-05-26",
            operations=("message.send",),
            allowed_public_config_keys=("to_number",),
            required_secret_ref_keys=("api_token",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([100.0, 101.0, 200.0, 201.0, 300.0, 301.0]).__next__)

    def ok_adapter(_call):
        return ConnectorResult(status="succeeded", summary="ok")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": ok_adapter, "whatsapp": ok_adapter},
        audit_ledger=ledger,
    )

    base_secrets = {"admin_token": "secret://t/s/a"}
    wa_secrets = {"api_token": "secret://t/w/a"}
    # Two shopify runs, one whatsapp run
    for run_id in ("run_s1", "run_s2"):
        executor.execute(
            ConnectorExecutionRequest(
                run_id=run_id,
                connector_id="shopify",
                operation="orders.pull",
                public_config={"shop_domain": "orvo.myshopify.com"},
                secret_refs=base_secrets,
            )
        )
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_w1",
            connector_id="whatsapp",
            operation="message.send",
            public_config={"to_number": "+5491100001111"},
            secret_refs=wa_secrets,
        )
    )

    shopify_runs = ledger.runs_by_connector("shopify")
    assert len(shopify_runs) == 2
    assert all(s.connector_id == "shopify" for s in shopify_runs)
    assert [s.run_id for s in shopify_runs] == ["run_s1", "run_s2"]

    whatsapp_runs = ledger.runs_by_connector("whatsapp")
    assert len(whatsapp_runs) == 1
    assert whatsapp_runs[0].connector_id == "whatsapp"
    assert whatsapp_runs[0].run_id == "run_w1"


def test_run_ledger_runs_by_connector_returns_empty_for_unknown_connector():
    """runs_by_connector(connector_id) returns [] when no runs exist for the connector."""
    ledger = ConnectorRunLedger()
    assert ledger.runs_by_connector("nonexistent") == []


def test_run_ledger_open_runs_returns_only_in_progress_runs():
    """open_runs() returns ConnectorRunSummary entries for runs with no terminal event."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
            evidence_kinds=("orders_snapshot",),
        )
    )
    registry.register(
        ConnectorContract(
            connector_id="whatsapp",
            contract_name="whatsapp.messaging",
            contract_version="2026-05-26",
            operations=("message.send",),
            allowed_public_config_keys=("to_number",),
            required_secret_ref_keys=("api_token",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([100.0, 101.0, 200.0, 201.0, 300.0]).__next__)

    def ok_adapter(_call):
        return ConnectorResult(status="succeeded", summary="ok")

    def failing_adapter(_call):
        raise RuntimeError("boom")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": ok_adapter, "whatsapp": failing_adapter},
        audit_ledger=ledger,
    )

    # run_completed: shopify run with a terminal 'succeeded' event
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_completed",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo.myshopify.com"},
            secret_refs={"admin_token": "secret://t/s/a"},
        )
    )
    # run_also_failed: whatsapp run with a terminal 'failed' event
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_also_failed",
            connector_id="whatsapp",
            operation="message.send",
            public_config={"to_number": "+5491100001111"},
            secret_refs={"api_token": "secret://t/w/a"},
        )
    )
    # run_stuck: shopify run still in progress (only 'started' event appended manually)
    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo.myshopify.com"},
        secret_refs={"admin_token": "secret://t/s/a"},
        run_id="run_stuck",
    )
    ledger.append(
        compiled_call=compiled,
        event_type="connector.execution.started",
        from_state="requested",
        to_state="running",
    )

    open_runs = ledger.open_runs()
    assert len(open_runs) == 1
    assert open_runs[0].run_id == "run_stuck"
    assert open_runs[0].connector_id == "shopify"
    assert open_runs[0].status is None
    assert open_runs[0].finished_at is None


def test_run_ledger_open_runs_returns_empty_when_all_runs_are_terminal():
    """open_runs() returns [] when every run has a terminal event."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([100.0, 101.0]).__next__)

    def ok_adapter(_call):
        return ConnectorResult(status="succeeded", summary="ok")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": ok_adapter},
        audit_ledger=ledger,
    )
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_done",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo.myshopify.com"},
            secret_refs={"admin_token": "secret://t/s/a"},
        )
    )

    assert ledger.open_runs() == []


def test_run_ledger_open_runs_returns_empty_for_empty_ledger():
    """open_runs() returns [] when the ledger has no events."""
    ledger = ConnectorRunLedger()
    assert ledger.open_runs() == []


def test_run_ledger_last_completed_run_returns_most_recent_terminal_run():
    """last_completed_run(connector_id) returns the most recently finished run by finished_at."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    ledger = ConnectorRunLedger(clock=iter([100.0, 101.0, 200.0, 201.0]).__next__)

    def ok_adapter(_call):
        return ConnectorResult(status="succeeded", summary="ok")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": ok_adapter},
        audit_ledger=ledger,
    )

    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_first",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo.myshopify.com"},
            secret_refs={"admin_token": "secret://t/s/a"},
        )
    )
    executor.execute(
        ConnectorExecutionRequest(
            run_id="run_second",
            connector_id="shopify",
            operation="orders.pull",
            public_config={"shop_domain": "orvo.myshopify.com"},
            secret_refs={"admin_token": "secret://t/s/a"},
        )
    )

    last = ledger.last_completed_run("shopify")
    assert last is not None
    assert last.run_id == "run_second"
    assert last.status == "succeeded"
    assert last.finished_at == 201.0


def test_run_ledger_last_completed_run_skips_in_progress_runs():
    """last_completed_run(connector_id) returns None when only in-progress runs exist."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    compiled = compile_connector_call(
        registry=registry,
        connector_id="shopify",
        operation="orders.pull",
        public_config={"shop_domain": "orvo.myshopify.com"},
        secret_refs={"admin_token": "secret://t/s/a"},
        run_id="run_no_terminal",
    )
    ledger = ConnectorRunLedger(clock=iter([500.0]).__next__)
    ledger.append(
        compiled_call=compiled,
        event_type="connector.execution.started",
        from_state="requested",
        to_state="running",
    )

    assert ledger.last_completed_run("shopify") is None


def test_run_ledger_last_completed_run_returns_none_for_unknown_connector():
    """last_completed_run(connector_id) returns None when no runs exist for the connector."""
    ledger = ConnectorRunLedger()
    assert ledger.last_completed_run("nonexistent") is None


def test_executor_is_available_returns_true_when_contract_and_adapter_both_exist():
    """is_available(connector_id) returns True only when the registry has a contract AND an adapter is wired."""
    registry = ConnectorRegistry()
    registry.register(
        ConnectorContract(
            connector_id="shopify",
            contract_name="shopify.orders",
            contract_version="2026-05-26",
            operations=("orders.pull",),
            allowed_public_config_keys=("shop_domain",),
            required_secret_ref_keys=("admin_token",),
        )
    )
    registry.register(
        ConnectorContract(
            connector_id="whatsapp",
            contract_name="whatsapp.messaging",
            contract_version="2026-05-26",
            operations=("message.send",),
            allowed_public_config_keys=("to_number",),
            required_secret_ref_keys=("api_token",),
        )
    )

    def shopify_adapter(_call):
        return ConnectorResult(status="succeeded")

    executor = ConnectorExecutor(
        registry=registry,
        adapters={"shopify": shopify_adapter},
    )

    assert executor.is_available("shopify") is True
    # Contract registered but no adapter wired
    assert executor.is_available("whatsapp") is False
    # Not registered at all
    assert executor.is_available("nonexistent") is False
