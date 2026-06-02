from datetime import date
import importlib
from typing import Any

import pytest


EXPECTED_CONNECTOR_TYPES = (
    "csv",
    "google_sheets",
    "mercadolibre",
    "meta_ads",
    "sample",
    "tiendanube",
    "woocommerce",
)

EXPECTED_PUBLIC_REQUIRED_FIELDS = {
    "csv": ("csv_path",),
    "google_sheets": ("spreadsheet_id", "range_name"),
    "mercadolibre": ("seller_id",),
    "meta_ads": ("ad_account_id",),
    "sample": (),
    "tiendanube": ("store_id",),
    "woocommerce": ("store_url",),
}

EXPECTED_SECRET_FIELDS = {
    "mercadolibre": ("access_token",),
    "meta_ads": ("access_token",),
    "tiendanube": ("access_token",),
    "woocommerce": ("consumer_key", "consumer_secret"),
}


def test_default_registry_contains_current_brain_connector_specs():
    from app.brain.connector_registry import default_connector_registry

    registry = default_connector_registry()

    assert registry.connector_types() == EXPECTED_CONNECTOR_TYPES


def test_all_default_specs_expose_importable_factory_paths_and_executor_metadata():
    from app.brain.connector_registry import list_connector_specs

    for spec in list_connector_specs():
        module = importlib.import_module(spec.adapter_module)
        factory = getattr(module, spec.report_factory)

        assert callable(factory)
        assert spec.factory_path == f"{spec.adapter_module}.{spec.report_factory}"
        assert spec.executor.factory_path == spec.factory_path
        assert spec.load_report_factory() is factory
        expected_modes = (
            ("preview", "operator_triggered")
            if spec.connector_type == "sample"
            else ("preview", "forced", "scheduled", "operator_triggered")
        )
        assert spec.executor.supported_runtime_modes == expected_modes
        assert spec.health.readiness_check == "metadata_only"
        assert spec.rate_limit.default_timeout_seconds > 0
        assert spec.lifecycle.status == "active"
        assert isinstance(spec.scopes.required, tuple)


def test_executor_metadata_builds_adapter_kwargs_without_connector_branching():
    from app.brain.config import BusinessConfig, ConnectorConfig
    from app.brain.connector_registry import get_connector_spec

    http_client = object()
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[],
    )
    connector = ConnectorConfig(
        connector_id="tn-main",
        connector_type="tiendanube",
        label="TN Artemea",
        params={"store_id": "123", "access_token": "tn_test_token", "include_stock": True},
    )

    kwargs = get_connector_spec("tiendanube").build_report_factory_kwargs(
        connector=connector,
        business=business,
        report_date=date(2026, 5, 30),
        service_bindings={"tiendanube_http_client": http_client},
    )

    assert kwargs == {
        "business_name": "Artemea",
        "store_id": "123",
        "access_token": "tn_test_token",
        "report_date": date(2026, 5, 30),
        "http_client": http_client,
        "include_stock": True,
        "source_label": "TN Artemea",
    }


def test_executor_metadata_reports_missing_execution_params_without_secret_values():
    from app.brain.config import BusinessConfig, ConnectorConfig
    from app.brain.connector_registry import get_connector_spec

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[],
    )
    connector = ConnectorConfig(
        connector_id="tn-main",
        connector_type="tiendanube",
        label="TN Artemea",
        params={"store_id": "123"},
    )

    with pytest.raises(ValueError) as exc_info:
        get_connector_spec("tiendanube").build_report_factory_kwargs(
            connector=connector,
            business=business,
            report_date=date(2026, 5, 30),
        )

    message = str(exc_info.value)
    assert message == "tiendanube connector params must include access_token"
    assert "123" not in message
    assert "tn_test_token" not in message


def test_executor_metadata_rejects_non_callable_factory_path():
    from app.brain.connector_registry import ConnectorExecutorMetadata

    executor = ConnectorExecutorMetadata(
        adapter_module="app.brain.connector_registry",
        report_factory="CONNECTOR_TYPE_CSV",
    )

    with pytest.raises(TypeError, match="factory is not callable"):
        executor.load_factory()


def test_registry_reports_helpful_error_for_unknown_connector_type():
    from app.brain.connector_registry import UnknownConnectorError, get_connector_spec

    with pytest.raises(UnknownConnectorError) as exc_info:
        get_connector_spec("shopify")

    message = str(exc_info.value)
    assert "shopify" in message
    assert "Unknown connector type" in message
    assert "google_sheets" in message
    assert "tiendanube" in message


def test_registry_rejects_duplicate_connector_type_registration():
    from app.brain.connector_registry import ConnectorRegistry, get_connector_spec

    spec = get_connector_spec("csv")
    registry = ConnectorRegistry((spec,))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)


def test_registry_as_mapping_is_read_only():
    from app.brain.connector_registry import default_connector_registry

    mapping = default_connector_registry().as_mapping()
    mutable_mapping: Any = mapping

    assert mapping["csv"].display_name == "CSV file"
    with pytest.raises(TypeError):
        mutable_mapping["new"] = mapping["csv"]


def test_default_specs_separate_public_required_fields_from_secret_refs():
    from app.brain.connector_registry import list_connector_specs

    for spec in list_connector_specs():
        assert spec.required_config_fields == EXPECTED_PUBLIC_REQUIRED_FIELDS[spec.connector_type]
        assert "access_token" not in spec.required_config_fields

        secret_ref_names = tuple(secret.name for secret in spec.required_secret_refs)
        expected_secret_fields = EXPECTED_SECRET_FIELDS.get(spec.connector_type, ())
        if expected_secret_fields:
            assert secret_ref_names == expected_secret_fields
            assert spec.legacy_secret_config_fields == expected_secret_fields
            assert spec.secret_config_fields == expected_secret_fields
        else:
            assert secret_ref_names == ()
            assert spec.legacy_secret_config_fields == ()
            assert spec.secret_config_fields == ()


def test_control_plane_validation_returns_structured_issue_shape_for_public_fields_and_secret_refs():
    from app.brain.connector_registry import get_connector_spec

    issues = get_connector_spec("tiendanube").validate_control_plane_config(
        params={"store_id": "", "unexpected": "value", "access_token": "legacy-token"},
        secret_refs={},
        strict=True,
    )

    assert [(issue.code, issue.key, issue.severity) for issue in issues] == [
        ("empty_required_config", "store_id", "error"),
        ("missing_required_secret_ref", "access_token", "error"),
        ("legacy_inline_secret", "access_token", "warning"),
        ("unknown_config_field", "unexpected", "error"),
    ]
    assert all(issue.message for issue in issues)


def test_control_plane_validation_distinguishes_missing_and_empty_values():
    from app.brain.connector_registry import get_connector_spec

    google_issues = get_connector_spec("google_sheets").validate_control_plane_config(
        params={"spreadsheet_id": "", "range_name": "Daily!A:F"},
        secret_refs={},
    )
    meta_issues = get_connector_spec("meta_ads").validate_control_plane_config(
        params={},
        secret_refs={"access_token": ""},
    )

    assert [(issue.code, issue.key, issue.severity) for issue in google_issues] == [
        ("empty_required_config", "spreadsheet_id", "error"),
    ]
    assert [(issue.code, issue.key, issue.severity) for issue in meta_issues] == [
        ("missing_required_config", "ad_account_id", "error"),
        ("empty_required_secret_ref", "access_token", "error"),
    ]


def test_legacy_validate_params_still_checks_inline_execution_secrets():
    from app.brain.connector_registry import validate_connector_config

    assert validate_connector_config("tiendanube", {"store_id": "123"}) == [
        "tiendanube connector params must include access_token"
    ]
    assert validate_connector_config("tiendanube", {"store_id": "123", "access_token": "legacy"}) == []


def test_validate_connector_config_reuses_unknown_connector_error():
    from app.brain.connector_registry import UnknownConnectorError, validate_connector_config

    with pytest.raises(UnknownConnectorError, match="shopify"):
        validate_connector_config("shopify", {})
