from app.brain.connector_registry import CONNECTOR_TYPE_TIENDANUBE


def test_connector_provisioning_plan_accepts_registry_valid_secret_refs():
    from app.brain.connector_provisioning import (
        CONNECTOR_PROVISIONING_SCHEMA_VERSION,
        ConnectorProvisioningRequest,
        compile_connector_provisioning_plan,
    )

    request = ConnectorProvisioningRequest(
        business_id="artemea",
        connector_id="tn-main",
        connector_type=CONNECTOR_TYPE_TIENDANUBE,
        label="Tiendanube principal",
        params={"store_id": "12345"},
        secret_refs={
            "access_token": "secret://businesses/artemea/connectors/tn-main/access_token",
        },
        actor_id="operator:ana",
    )

    plan = compile_connector_provisioning_plan(request)

    assert plan.schema_version == CONNECTOR_PROVISIONING_SCHEMA_VERSION
    assert plan.ok is True
    assert plan.next_step == "ready_for_config_save"
    assert plan.operation == "connector.provision"
    assert plan.operation_ref.startswith("connprov_")
    assert plan.audit_event["operation_ref"] == plan.operation_ref
    assert plan.business_id == "artemea"
    assert plan.connector.connector_type == CONNECTOR_TYPE_TIENDANUBE
    assert plan.connector.public_params == {"store_id": "12345"}
    assert plan.connector.secret_refs == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token",
    }
    assert plan.connector.required_config_fields == ("store_id",)
    assert plan.connector.required_secret_refs == ("access_token",)
    assert plan.connector.rate_limit_policy["retry_policy"] == "adapter_default"
    assert plan.issues == ()
    manifest = plan.public_manifest()
    assert manifest["ok"] is True
    assert manifest["operation_ref"] == plan.operation_ref
    assert manifest["connector"]["secret_refs"] == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token",
    }
    assert manifest["connector"]["required_secret_refs"] == ["access_token"]
    serialized = repr(manifest)
    assert "raw_inline_value" not in serialized
    assert "Bearer" not in serialized


def test_connector_provisioning_rejects_raw_secret_params_and_bad_secret_refs_without_echoing_values():
    from app.brain.connector_provisioning import (
        ConnectorProvisioningRequest,
        compile_connector_provisioning_plan,
    )

    request = ConnectorProvisioningRequest(
        business_id="artemea",
        connector_id="tn-main",
        connector_type=CONNECTOR_TYPE_TIENDANUBE,
        label="Tiendanube principal",
        params={"store_id": "12345", "access_token": "raw_inline_value"},
        secret_refs={"access_token": "raw_inline_value"},
        actor_id="operator access_token=raw_inline_value",
    )

    plan = compile_connector_provisioning_plan(request)

    assert plan.ok is False
    assert plan.next_step == "fix_validation_issues"
    assert [issue.code for issue in plan.issues] == [
        "secret_param_not_allowed",
        "invalid_secret_ref",
        "legacy_inline_secret",
    ]
    serialized = repr(plan.public_manifest())
    assert "raw_inline_value" not in serialized
    assert "operator access_token=raw_inline_value" not in serialized
    assert plan.audit_event["actor_id"] == "operator access_token=[REDACTED]"
    assert plan.connector.public_params["access_token"] == "[REDACTED]"
    assert plan.connector.secret_refs["access_token"] == "[REDACTED]"


def test_connector_provisioning_operation_ref_is_deterministic_secret_safe_and_config_sensitive():
    from app.brain.connector_provisioning import (
        ConnectorProvisioningRequest,
        compile_connector_provisioning_plan,
    )

    base_request = ConnectorProvisioningRequest(
        business_id="artemea",
        connector_id="tn-main",
        connector_type=CONNECTOR_TYPE_TIENDANUBE,
        label="Tiendanube principal",
        params={"store_id": "12345"},
        secret_refs={
            "access_token": "secret://businesses/artemea/connectors/tn-main/access_token",
        },
        actor_id="operator:ana",
    )

    first = compile_connector_provisioning_plan(base_request)
    second = compile_connector_provisioning_plan(base_request)
    changed_config = compile_connector_provisioning_plan(
        base_request.model_copy(update={"params": {"store_id": "67890"}})
    )
    invalid_secret = compile_connector_provisioning_plan(
        base_request.model_copy(
            update={
                "params": {"store_id": "12345", "access_token": "raw_inline_value"},
                "secret_refs": {"access_token": "raw_inline_value"},
                "actor_id": "operator access_token=raw_inline_value",
            }
        )
    )

    assert first.operation_ref == second.operation_ref
    assert first.operation_ref != changed_config.operation_ref
    assert first.operation_ref.startswith("connprov_")
    assert len(first.operation_ref) == len("connprov_" + "0" * 16)
    assert invalid_secret.audit_event["operation_ref"] == invalid_secret.operation_ref
    serialized = repr(invalid_secret.public_manifest())
    assert "raw_inline_value" not in serialized
    assert "operator access_token=raw_inline_value" not in serialized


def test_connector_provisioning_reuses_connector_registry_required_and_strict_field_validation():
    from app.brain.connector_provisioning import (
        ConnectorProvisioningRequest,
        compile_connector_provisioning_plan,
    )

    request = ConnectorProvisioningRequest(
        business_id="artemea",
        connector_id="tn-main",
        connector_type=CONNECTOR_TYPE_TIENDANUBE,
        label="Tiendanube principal",
        params={"debug_mode": True},
        secret_refs={
            "access_token": "secret://businesses/artemea/connectors/tn-main/access_token",
        },
        actor_id="operator:ana",
    )

    plan = compile_connector_provisioning_plan(request)

    assert plan.ok is False
    assert [issue.code for issue in plan.issues] == [
        "missing_required_config",
        "unknown_config_field",
    ]
    assert [issue.key for issue in plan.issues] == ["store_id", "debug_mode"]
    assert plan.next_step == "fix_validation_issues"


def test_service_catalog_includes_connector_provisioning_contract_component():
    from app.brain.service_catalog import default_service_catalog

    catalog = default_service_catalog()
    component = catalog.get("connector_provisioning")

    assert component.owner_department == "Edge / Developer Platform"
    assert component.source_of_truth == "app.brain.connector_provisioning"
    assert component.dependencies == ("connector_registry", "compiled_runtime", "run_ledger")
    assert "operation_ref" in component.observability_signals
    assert "docs/specs/connector-provisioning-contract.md" in component.docs
    assert "tests/contracts/test_connector_provisioning_contract.py" in component.test_paths
    assert "developer_platform" in component.runtime_surfaces
