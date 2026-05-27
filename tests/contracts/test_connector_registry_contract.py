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


def test_connector_spec_validate_emitted_metrics_composes_unknown_source_and_family_diagnostics():
    """ConnectorSpec.validate_emitted_metrics must compose the three semantic
    envelope diagnostics deterministically so the runtime/control-plane can
    rely on one call to inspect adapter output against a connector envelope.
    """

    from app.brain.connector_registry import get_connector_spec

    tiendanube = get_connector_spec("tiendanube")

    issues = tiendanube.validate_emitted_metrics(
        (
            "orders_today",
            "mystery_metric",
            "ad_spend_today",
            "ad_roas_today",
        )
    )

    codes_keys = [(issue.code, issue.key, issue.index) for issue in issues]
    assert codes_keys == [
        ("unknown_metric", "mystery_metric", 1),
        ("disallowed_source", "ad_spend_today", 2),
        ("disallowed_source", "ad_roas_today", 3),
        ("undeclared_family", "ad_spend_today", 2),
        ("undeclared_family", "ad_roas_today", 3),
    ]
    assert all(issue.severity == "warning" for issue in issues)


def test_connector_spec_validate_emitted_metrics_returns_empty_for_in_envelope_keys():
    from app.brain.connector_registry import get_connector_spec

    tiendanube = get_connector_spec("tiendanube")

    assert tiendanube.validate_emitted_metrics(
        ("orders_today", "revenue_today", "stock_units")
    ) == []


def test_connector_spec_validate_emitted_metrics_is_deterministic_across_runs():
    from app.brain.connector_registry import get_connector_spec

    meta_ads = get_connector_spec("meta_ads")
    keys = ("ad_spend_today", "orders_today", "mystery_metric")

    first = meta_ads.validate_emitted_metrics(keys)
    second = meta_ads.validate_emitted_metrics(keys)
    assert first == second


def test_validate_emitted_metrics_for_connector_module_function_matches_spec_method():
    from app.brain.connector_registry import (
        get_connector_spec,
        validate_emitted_metrics_for_connector,
    )

    keys = ("orders_today", "ad_spend_today", "mystery_metric")
    spec_result = get_connector_spec("tiendanube").validate_emitted_metrics(keys)
    free_result = validate_emitted_metrics_for_connector("tiendanube", keys)

    assert free_result == spec_result


def test_validate_emitted_metrics_for_connector_raises_for_unknown_connector_type():
    import pytest

    from app.brain.connector_registry import (
        UnknownConnectorError,
        validate_emitted_metrics_for_connector,
    )

    with pytest.raises(UnknownConnectorError):
        validate_emitted_metrics_for_connector("not_a_connector", ("orders_today",))


def test_semantics_package_reexports_family_envelope_helper_for_runtime_callers():
    """Runtime callers depend on `app.brain.semantics` as the public surface."""

    from app.brain import semantics

    assert hasattr(semantics, "find_family_envelope_violations")
    assert "find_family_envelope_violations" in semantics.__all__
