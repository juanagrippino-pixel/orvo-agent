import pytest


def test_default_registry_contains_current_brain_connector_specs():
    from app.brain.connector_registry import (
        CONNECTOR_TYPE_CSV,
        CONNECTOR_TYPE_GOOGLE_SHEETS,
        CONNECTOR_TYPE_MERCADOLIBRE,
        CONNECTOR_TYPE_META_ADS,
        CONNECTOR_TYPE_SAMPLE,
        CONNECTOR_TYPE_TIENDANUBE,
        default_connector_registry,
    )

    registry = default_connector_registry()

    assert registry.connector_types() == (
        CONNECTOR_TYPE_CSV,
        CONNECTOR_TYPE_GOOGLE_SHEETS,
        CONNECTOR_TYPE_MERCADOLIBRE,
        CONNECTOR_TYPE_META_ADS,
        CONNECTOR_TYPE_SAMPLE,
        CONNECTOR_TYPE_TIENDANUBE,
    )


def test_google_sheets_spec_exposes_runtime_metadata_without_credentials():
    from app.brain.connector_registry import CONNECTOR_TYPE_GOOGLE_SHEETS, get_connector_spec

    spec = get_connector_spec(CONNECTOR_TYPE_GOOGLE_SHEETS)

    assert spec.connector_type == "google_sheets"
    assert spec.display_name == "Google Sheets"
    assert spec.adapter_module == "app.brain.adapters.google_sheets"
    assert spec.report_factory == "build_daily_report_from_sheet"
    assert spec.required_config_fields == ("spreadsheet_id", "range_name")
    assert spec.secret_config_fields == ()
    assert "daily_report" in spec.capabilities


def test_registry_reports_helpful_error_for_unknown_connector_type():
    from app.brain.connector_registry import UnknownConnectorError, get_connector_spec

    with pytest.raises(UnknownConnectorError) as exc_info:
        get_connector_spec("shopify")

    message = str(exc_info.value)
    assert "shopify" in message
    assert "Unknown connector type" in message
    assert "google_sheets" in message
    assert "tiendanube" in message


def test_validate_connector_config_reports_missing_required_fields():
    from app.brain.connector_registry import CONNECTOR_TYPE_TIENDANUBE, validate_connector_config

    errors = validate_connector_config(CONNECTOR_TYPE_TIENDANUBE, {"store_id": "123"})

    assert errors == ["tiendanube connector params must include access_token"]


def test_validate_connector_config_reuses_unknown_connector_error():
    from app.brain.connector_registry import UnknownConnectorError, validate_connector_config

    with pytest.raises(UnknownConnectorError, match="shopify"):
        validate_connector_config("shopify", {})
