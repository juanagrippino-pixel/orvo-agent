import pytest


REQUIRED_CANONICAL_KEYS = {
    "commerce.orders.count",
    "commerce.revenue.total",
    "commerce.revenue.baseline",
    "commerce.inventory.available_units",
    "commerce.fulfillment.pending_count",
    "commerce.fulfillment.oldest_pending_age_hours",
    "support.conversations.unanswered_count",
    "support.conversations.oldest_unanswered_age_minutes",
    "runtime.freshness.last_success_at",
    "runtime.freshness.age_seconds",
    "runtime.data_quality.completeness_ratio",
    "runtime.connector.status",
    "ads.spend.total",
    "ads.delivery.impressions",
    "ads.delivery.clicks",
    "ads.roas.estimated",
    "commerce.average_order_value",
}


REQUIRED_ALIASES = {
    "revenue_today": "commerce.revenue.total",
    "revenue_baseline": "commerce.revenue.baseline",
    "orders_today": "commerce.orders.count",
    "stock_units": "commerce.inventory.available_units",
    "unanswered_conversations": "support.conversations.unanswered_count",
    "ad_spend_today": "ads.spend.total",
    "ad_impressions_today": "ads.delivery.impressions",
    "ad_clicks_today": "ads.delivery.clicks",
    "ad_roas_today": "ads.roas.estimated",
    "avg_order_value": "commerce.average_order_value",
    "commerce.revenue.today": "commerce.revenue.total",
    "commerce.orders.today": "commerce.orders.count",
    "commerce.inventory.stock_units": "commerce.inventory.available_units",
    "mercadolibre.revenue_today": "commerce.revenue.total",
    "tiendanube.revenue_today": "commerce.revenue.total",
}


def test_default_registry_contains_canonical_d2c_metrics_with_required_contract_fields():
    from app.brain.semantics.metric_registry import default_metric_registry

    registry = default_metric_registry()
    definitions = {definition.key: definition for definition in registry.definitions()}

    assert REQUIRED_CANONICAL_KEYS <= set(definitions)
    for key in REQUIRED_CANONICAL_KEYS:
        definition = definitions[key]
        assert definition.key == key
        assert definition.family
        assert definition.label
        assert definition.unit in {"count", "money", "percent", "duration", "boolean", "timestamp", "status"}
        assert definition.allowed_sources
        assert definition.aggregation in {"sum", "latest", "average", "min", "max", "ratio", "none"}
        assert isinstance(definition.freshness_required, bool)
        assert isinstance(definition.report_allowed, bool)
        assert isinstance(definition.case_allowed, bool)
        assert isinstance(definition.evidence_required, bool)
        assert definition.pii_class in {"none", "low", "sensitive"}


def test_canonical_keys_and_legacy_aliases_resolve_deterministically():
    from app.brain.semantics.metric_registry import default_metric_registry

    registry = default_metric_registry()

    for key in REQUIRED_CANONICAL_KEYS:
        assert registry.resolve_key(key) == key
        assert registry.get(key).key == key

    for alias, canonical_key in REQUIRED_ALIASES.items():
        assert registry.resolve_key(alias) == canonical_key
        assert registry.resolve_key(alias) == registry.resolve_key(alias)
        assert registry.get(alias).key == canonical_key


def _metric_definition(
    key: str,
    *,
    aliases: tuple[str, ...] = (),
):
    from app.brain.semantics.metric_registry import MetricDefinition

    return MetricDefinition(
        key=key,
        family="commerce.example",
        label=key.rsplit(".", 1)[-1].title(),
        unit="count",
        allowed_sources=("sample",),
        aliases=aliases,
        aggregation="sum",
        freshness_required=True,
        report_allowed=True,
        case_allowed=True,
        evidence_required=True,
        pii_class="none",
    )


def test_registry_rejects_duplicate_canonical_metric_keys():
    from app.brain.semantics.metric_registry import MetricRegistry

    with pytest.raises(ValueError, match="already registered"):
        MetricRegistry(
            (
                _metric_definition("commerce.example.duplicate"),
                _metric_definition("commerce.example.duplicate"),
            )
        )


def test_registry_rejects_duplicate_aliases_and_aliases_that_shadow_canonical_keys():
    from app.brain.semantics.metric_registry import MetricRegistry

    first = _metric_definition("commerce.example.first", aliases=("legacy_metric",))
    second = _metric_definition("commerce.example.second", aliases=("legacy_metric",))

    with pytest.raises(ValueError, match="legacy_metric"):
        MetricRegistry((first, second))

    shadow = _metric_definition("commerce.example.shadow", aliases=("commerce.example.first",))
    with pytest.raises(ValueError, match="canonical"):
        MetricRegistry((first, shadow))


def test_case_family_metric_mappings_only_reference_registered_case_allowed_metrics():
    from app.brain.semantics.metric_registry import CASE_FAMILY_METRICS, default_metric_registry

    assert set(CASE_FAMILY_METRICS) == {
        "sales_drop",
        "stockout_risk",
        "data_stale",
        "fulfillment_backlog",
        "unanswered_conversations",
        "spend_without_orders",
    }

    registry = default_metric_registry()
    for case_family, metric_keys in CASE_FAMILY_METRICS.items():
        assert metric_keys, case_family
        for metric_key in metric_keys:
            definition = registry.get(metric_key)
            assert definition.case_allowed, f"{case_family} references non-case metric {metric_key}"


def test_case_family_catalogs_stay_aligned_with_operational_cases_and_actions():
    from typing import get_args

    from app.brain.action_catalog import workflow_action_registry
    from app.brain.operational_cases import OperationalCaseType
    from app.brain.semantics.metric_registry import CASE_FAMILY_METRICS

    implemented_case_types = set(get_args(OperationalCaseType))
    registered_case_families = set(CASE_FAMILY_METRICS)

    assert registered_case_families <= implemented_case_types

    dangling_action_families = {
        case_family
        for action in workflow_action_registry().values()
        for case_family in action.case_families
        if case_family not in registered_case_families
    }
    assert dangling_action_families == set()


def test_connector_emitted_metric_families_are_registered_or_explicitly_compatible():
    from app.brain.connector_registry import list_connector_specs
    from app.brain.semantics.metric_registry import CONNECTOR_FAMILY_COMPATIBILITY, default_metric_registry

    registry = default_metric_registry()
    registered_families = {definition.family for definition in registry.definitions()}
    compatible_families = {
        family
        for compatible in CONNECTOR_FAMILY_COMPATIBILITY.values()
        for family in compatible
    }
    assert compatible_families <= registered_families

    missing = []
    for connector in list_connector_specs():
        for family in connector.emitted_metric_families:
            if family in registered_families:
                continue
            if family in CONNECTOR_FAMILY_COMPATIBILITY:
                assert CONNECTOR_FAMILY_COMPATIBILITY[family], family
                continue
            missing.append(f"{connector.connector_type}:{family}")

    assert missing == []


def test_connector_specs_only_declare_families_with_a_canonical_metric_for_that_source():
    """Each declared emitted family must be backed by at least one canonical
    metric whose ``allowed_sources`` includes the connector type. A connector
    cannot legitimately emit metrics in a family the registry forbids it from,
    so declaring such a family in ``emitted_metric_families`` is meaningless
    and lets the unified envelope validator drift from the registry's source
    contract. Families resolved through ``CONNECTOR_FAMILY_COMPATIBILITY`` are
    intentionally exempt because they are transitional envelopes (e.g.
    ``manual.payload``) without a direct canonical family of their own.
    """

    from app.brain.connector_registry import list_connector_specs
    from app.brain.semantics.metric_registry import (
        CONNECTOR_FAMILY_COMPATIBILITY,
        default_metric_registry,
    )

    registry = default_metric_registry()

    sources_by_family: dict[str, set[str]] = {}
    for definition in registry.definitions():
        sources_by_family.setdefault(definition.family, set()).update(definition.allowed_sources)

    unsupported: list[str] = []
    for connector in list_connector_specs():
        for family in connector.emitted_metric_families:
            if family in CONNECTOR_FAMILY_COMPATIBILITY:
                continue
            allowed_sources = sources_by_family.get(family, set())
            if connector.connector_type in allowed_sources:
                continue
            unsupported.append(f"{connector.connector_type}:{family}")

    assert unsupported == [], (
        "Connector specs declare emitted_metric_families that have no canonical "
        "metric authorizing the connector as a source. Either remove the family "
        "or extend allowed_sources on a canonical metric: " + ", ".join(unsupported)
    )
