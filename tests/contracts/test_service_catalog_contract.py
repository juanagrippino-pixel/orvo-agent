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
        "delivery_dispatch",
        "edge_developer_platform",
    ]
    assert catalog.get("compiled_runtime").owner_department == "Edge / Developer Platform"
    assert catalog.get("connector_registry").owner_department == "Connector / Ecosystem Platform"
    assert catalog.get("metric_registry").source_of_truth == "app.brain.semantics.metric_registry"
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
        "edge_developer_platform",
    ]
    assert [component.component_id for component in api_components] == ["operator_api"]
