def test_default_connector_specs_expose_control_plane_runtime_modes_and_metric_families():
    from app.brain.connector_registry import (
        CONNECTOR_TYPE_CSV,
        CONNECTOR_TYPE_GOOGLE_SHEETS,
        CONNECTOR_TYPE_TIENDANUBE,
        get_connector_spec,
    )

    expected_modes = ("preview", "forced", "scheduled", "operator_triggered")
    for connector_type in (CONNECTOR_TYPE_CSV, CONNECTOR_TYPE_GOOGLE_SHEETS, CONNECTOR_TYPE_TIENDANUBE):
        spec = get_connector_spec(connector_type)
        assert spec.executor.supported_runtime_modes == expected_modes
        assert "runtime.freshness" in spec.emitted_metric_families
        assert "runtime.data_quality" in spec.emitted_metric_families

    tiendanube = get_connector_spec(CONNECTOR_TYPE_TIENDANUBE)
    assert "commerce.orders" in tiendanube.emitted_metric_families
    assert "commerce.revenue" in tiendanube.emitted_metric_families
    assert "commerce.inventory" in tiendanube.emitted_metric_families


def test_runtime_compiler_uses_connector_registry_contract_not_private_duplicate_descriptors():
    from app.brain.config import BusinessConfig, ConnectorConfig
    from app.brain.connector_registry import CAPABILITY_COMMERCE_METRICS
    from app.brain.runtime import compile_business_runtime

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="Tiendanube principal",
                params={"store_id": "12345", "access_token": "tn_test_token"},
            )
        ],
    )

    runtime = compile_business_runtime(business)

    assert CAPABILITY_COMMERCE_METRICS in runtime.connectors[0].capabilities
    assert runtime.connectors[0].required_params == ["store_id"]
    assert runtime.connectors[0].secret_refs == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
    }


def test_sample_connector_is_not_declared_as_forced_or_scheduled_daily_runtime():
    from app.brain.connector_registry import CAPABILITY_DAILY_REPORT, CONNECTOR_TYPE_SAMPLE, get_connector_spec

    sample = get_connector_spec(CONNECTOR_TYPE_SAMPLE)

    assert CAPABILITY_DAILY_REPORT not in sample.capabilities
    assert sample.executor.supported_runtime_modes == ("preview", "operator_triggered")
