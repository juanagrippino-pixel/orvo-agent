import pytest

from app.brain.models import Evidence, Metric


def _evidence(source: str = "tiendanube") -> Evidence:
    return Evidence(source=source, label=f"{source} run")


def test_advisory_metric_validation_reports_unknown_metrics_deterministically_without_mutation():
    from app.brain.semantics.metric_registry import validate_metrics

    metrics = [
        Metric(
            key="revenue_today",
            label="Ventas de hoy",
            value=120000,
            unit="ARS",
            evidence=[_evidence()],
        ),
        Metric(
            key="custom.owner_note_metric",
            label="Owner note",
            value="manual note",
            evidence=[_evidence("sample")],
        ),
    ]
    original_dump = [metric.model_dump(mode="json") for metric in metrics]

    first = validate_metrics(metrics)
    second = validate_metrics(metrics)

    assert [metric.model_dump(mode="json") for metric in metrics] == original_dump
    assert first == second
    assert first == [
        first[0].__class__(
            code="unknown_metric",
            key="custom.owner_note_metric",
            message="Metric key 'custom.owner_note_metric' is not registered in the semantic metric registry",
            severity="warning",
            index=1,
        )
    ]


def test_advisory_metric_validation_accepts_canonical_keys_and_registered_aliases():
    from app.brain.semantics.metric_registry import validate_metrics

    metrics = [
        Metric(key="commerce.orders.count", label="Orders", value=12, evidence=[_evidence()]),
        Metric(key="commerce.revenue.today", label="Revenue", value=90000, unit="ARS", evidence=[_evidence()]),
        Metric(key="avg_order_value", label="AOV", value=7500, unit="ARS", evidence=[_evidence("mercadolibre")]),
    ]

    assert validate_metrics(metrics) == []


def test_legacy_revenue_baseline_alias_resolves_to_canonical_baseline_metric():
    from app.brain.semantics.metric_registry import default_metric_registry, validate_metrics

    registry = default_metric_registry()
    canonical_key = registry.resolve_key("revenue_baseline")
    definition = registry.get("revenue_baseline")

    assert canonical_key == "commerce.revenue.baseline"
    assert definition.family == "commerce.revenue"
    assert definition.case_allowed is True
    assert "google_sheets" in definition.allowed_sources
    assert "csv" in definition.allowed_sources
    assert "sample" in definition.allowed_sources

    metrics = [
        Metric(key="revenue_baseline", label="Promedio reciente", value=120000, unit="ARS", evidence=[_evidence("google_sheets")]),
    ]
    assert validate_metrics(metrics) == []


def test_strict_metric_validation_raises_on_unknown_metric_without_mutating_input():
    from app.brain.semantics.metric_registry import UnknownMetricError, validate_metrics

    metrics = [Metric(key="mystery_metric", label="Mystery", value=1, evidence=[_evidence("sample")])]
    original_dump = metrics[0].model_dump(mode="json")

    with pytest.raises(UnknownMetricError, match="mystery_metric"):
        validate_metrics(metrics, strict=True)

    assert metrics[0].model_dump(mode="json") == original_dump
