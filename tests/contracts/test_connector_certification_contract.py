from pathlib import Path

from app.brain.connector_registry import (
    CONNECTOR_TYPE_TIENDANUBE,
    CONNECTOR_TYPE_MERCADOLIBRE,
    CONNECTOR_TYPE_META_ADS,
    CONNECTOR_TYPE_WOOCOMMERCE,
    connector_certification_for_spec,
    default_connector_registry,
    get_connector_spec,
    render_connector_certification_markdown,
)


def test_connector_certification_for_spec_exposes_safe_provisioning_metadata():
    spec = get_connector_spec(CONNECTOR_TYPE_TIENDANUBE)

    certification = connector_certification_for_spec(spec)

    assert certification.connector_type == CONNECTOR_TYPE_TIENDANUBE
    assert certification.display_name == "Tiendanube"
    assert certification.status == "active"
    assert certification.owner == "orvo-brain"
    assert certification.version == "phase-a"
    assert certification.capabilities == (
        "daily_report",
        "commerce_metrics",
        "inventory_metrics",
    )
    assert certification.scopes == ("orders.read", "products.read")
    assert certification.secret_refs == ("access_token",)
    assert certification.rate_limit == {
        "default_timeout_seconds": 30,
        "requests_per_minute": 120,
        "retry_policy": "adapter_default",
    }
    assert certification.health_states == (
        "ok",
        "degraded",
        "stale",
        "unauthorized",
        "rate_limited",
        "failed",
    )
    assert certification.runtime_modes == (
        "preview",
        "forced",
        "scheduled",
        "operator_triggered",
    )


def test_connector_certification_markdown_covers_registered_connectors():
    rendered = render_connector_certification_markdown()

    for connector_type in default_connector_registry().connector_types():
        assert f"| `{connector_type}` |" in rendered

    assert f"| `{CONNECTOR_TYPE_TIENDANUBE}` |" in rendered
    assert f"| `{CONNECTOR_TYPE_MERCADOLIBRE}` |" in rendered
    assert f"| `{CONNECTOR_TYPE_META_ADS}` |" in rendered
    assert f"| `{CONNECTOR_TYPE_WOOCOMMERCE}` |" in rendered
    assert "orders.read, products.read" in rendered
    assert "120 rpm / retry adapter_default" in rendered
    assert "access_token" in rendered
    assert "tn_test_token" not in rendered


def test_connector_certification_markdown_is_stable_for_default_catalog():
    rendered_once = render_connector_certification_markdown()
    rendered_twice = render_connector_certification_markdown()

    assert rendered_once == rendered_twice


def test_connector_certification_contract_doc_matches_renderer():
    doc_path = (
        Path(__file__).resolve().parents[2]
        / "docs/specs/connector-certification-contract.md"
    )
    rendered = render_connector_certification_markdown()

    assert rendered in doc_path.read_text()


def test_connector_certification_markdown_keeps_secret_names_safe():
    rendered = render_connector_certification_markdown()

    assert "mercado_token" not in rendered
    assert "meta_token" not in rendered
    assert "tiendanube_token" not in rendered
    assert "access_token" in rendered
    assert "consumer_key" in rendered
    assert "consumer_secret" in rendered
    assert "secret value" not in rendered.lower()
