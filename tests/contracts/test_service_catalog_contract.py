from pathlib import Path

import pytest


def test_default_service_catalog_covers_core_control_plane_components():
    from app.brain.service_catalog import default_service_catalog

    catalog = default_service_catalog()

    assert [component.component_id for component in catalog.components] == [
        "compiled_runtime",
        "connector_registry",
        "metric_registry",
        "run_ledger",
        "operational_cases",
        "operator_api",
        "gateway_policy",
        "connector_provisioning",
        "delivery_dispatch",
        "edge_developer_platform",
    ]
    assert catalog.get("compiled_runtime").owner_department == "Edge / Developer Platform"
    assert catalog.get("connector_registry").owner_department == "Connector / Ecosystem Platform"
    assert catalog.get("metric_registry").source_of_truth == "app.brain.semantics.metric_registry"
    assert catalog.get("gateway_policy").source_of_truth == "app.brain.gateway_policy"
    assert catalog.get("connector_provisioning").source_of_truth == "app.brain.connector_provisioning"
    assert catalog.get("gateway_policy").runtime_surfaces == ("operator_api", "developer_platform")
    assert "actor_id_redacted" in catalog.get("gateway_policy").observability_signals
    assert "rate_limit_key_redacted" in catalog.get("gateway_policy").observability_signals
    assert "request_id_redacted" in catalog.get("gateway_policy").observability_signals
    assert "trace_id_redacted" in catalog.get("gateway_policy").observability_signals
    assert "gateway_telemetry_schema" in catalog.get("gateway_policy").observability_signals
    assert "provenance_ref" in catalog.get("gateway_policy").observability_signals
    assert catalog.get("gateway_policy").runbooks == (
        "docs/operability/gateway-policy-telemetry-runbook.md",
    )
    assert "docs/specs/compiled-runtime-contract.md" in catalog.get("compiled_runtime").docs


def test_service_catalog_manifest_is_stable_public_and_secret_safe():
    from app.brain.service_catalog import service_catalog_manifest

    manifest = service_catalog_manifest()

    assert manifest["schema_version"] == "2026-05-31.service-catalog.v1"
    assert [component["component_id"] for component in manifest["components"]][:3] == [
        "compiled_runtime",
        "connector_registry",
        "metric_registry",
    ]
    serialized = repr(manifest).lower()
    assert "token" not in serialized
    assert "secret://" not in serialized
    assert "access_token" not in serialized


def test_service_catalog_runbooks_are_public_durable_and_exist():
    from app.brain.service_catalog import service_catalog_manifest

    manifest = service_catalog_manifest()
    components = {component["component_id"]: component for component in manifest["components"]}

    gateway_policy = components["gateway_policy"]
    assert gateway_policy["runbooks"] == [
        "docs/operability/gateway-policy-telemetry-runbook.md",
    ]

    repo_root = Path(__file__).resolve().parents[2]
    for component in manifest["components"]:
        for runbook in component["runbooks"]:
            path = repo_root / runbook
            assert path.exists(), f"missing service catalog runbook: {runbook}"
            content = path.read_text(encoding="utf-8")
            assert component["component_id"] in content
            assert "[REDACTED]" in content


def test_service_catalog_rejects_duplicate_ids_and_unknown_dependencies():
    from app.brain.service_catalog import ServiceCatalog, ServiceComponent

    component = ServiceComponent(
        component_id="compiled_runtime",
        display_name="Compiled runtime",
        owner_department="Edge / Developer Platform",
        source_of_truth="app.brain.runtime",
        status="active",
        tier="control_plane",
        docs=("docs/specs/compiled-runtime-contract.md",),
        code_paths=("app/brain/runtime.py",),
        test_paths=("tests/test_brain_runtime.py",),
    )
    duplicate = component.model_copy(update={"display_name": "Duplicate"})
    dangling = component.model_copy(
        update={"component_id": "gateway_policy", "dependencies": ("does_not_exist",)}
    )

    with pytest.raises(ValueError, match="duplicate service component id"):
        ServiceCatalog((component, duplicate))

    with pytest.raises(ValueError, match="unknown service dependency"):
        ServiceCatalog((component, dangling))


def test_service_catalog_queries_by_owner_and_runtime_surface():
    from app.brain.service_catalog import default_service_catalog

    catalog = default_service_catalog()
    edge_components = catalog.by_owner("Edge / Developer Platform")
    api_components = catalog.by_runtime_surface("operator_api")

    assert [component.component_id for component in edge_components] == [
        "compiled_runtime",
        "gateway_policy",
        "connector_provisioning",
        "edge_developer_platform",
    ]
    assert [component.component_id for component in api_components] == ["operator_api", "gateway_policy"]


def test_service_catalog_certification_accepts_default_catalog_paths_and_metadata():
    from app.brain.service_catalog import certify_service_catalog, default_service_catalog

    repo_root = Path(__file__).resolve().parents[2]
    report = certify_service_catalog(default_service_catalog(), repo_root=repo_root)

    assert report.schema_version == "2026-06-11.service-catalog-certification.v1"
    assert report.ok is True
    assert report.checked_component_count == 10
    assert report.checked_path_count >= 30
    assert report.findings == ()
    serialized = repr(report.model_dump()).lower()
    assert "access_token" not in serialized
    assert "secret://" not in serialized


def test_service_catalog_certification_flags_missing_paths_and_unsafe_metadata(tmp_path):
    from app.brain.service_catalog import ServiceCatalog, ServiceComponent, certify_service_catalog

    secret_marker = "raw_" + "catalog_secret"
    secret_assignment = "access_token=" + secret_marker
    component = ServiceComponent(
        component_id="unsafe_component",
        display_name="Unsafe component " + secret_assignment,
        owner_department="Edge / Developer Platform",
        source_of_truth="app.brain." + secret_assignment,
        status="draft",
        tier="platform",
        docs=("docs/missing-catalog-doc.md",),
        code_paths=("app/brain/missing_catalog_component.py",),
        test_paths=("tests/missing_catalog_test.py",),
        runbooks=("docs/operability/missing-catalog-runbook.md",),
        observability_signals=("api_key=" + secret_marker,),
    )

    report = certify_service_catalog(ServiceCatalog((component,)), repo_root=tmp_path)

    assert report.ok is False
    assert [finding.code for finding in report.findings] == [
        "unsafe_component_metadata",
        "unsafe_component_metadata",
        "unsafe_component_metadata",
        "missing_catalog_path",
        "missing_catalog_path",
        "missing_catalog_path",
        "missing_catalog_path",
    ]
    assert {(finding.component_id, finding.field) for finding in report.findings[:3]} == {
        ("unsafe_component", "display_name"),
        ("unsafe_component", "source_of_truth"),
        ("unsafe_component", "observability_signals"),
    }
    assert {finding.field for finding in report.findings[3:]} == {
        "docs",
        "code_paths",
        "test_paths",
        "runbooks",
    }
    serialized = repr(report.model_dump())
    assert secret_marker not in serialized
    assert secret_assignment not in serialized
