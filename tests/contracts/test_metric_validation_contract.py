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


def test_source_envelope_helper_flags_metrics_emitted_by_unauthorized_connector_types():
    from app.brain.semantics.metric_registry import find_source_envelope_violations

    violations = find_source_envelope_violations(
        ("ad_spend_today",), connector_type="mercadolibre"
    )
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("disallowed_source", "ad_spend_today", 0, "warning")
    ]
    assert "mercadolibre" in violations[0].message
    assert "ads.spend.total" in violations[0].message

    assert find_source_envelope_violations(
        ("ad_spend_today",), connector_type="meta_ads"
    ) == []


def test_source_envelope_helper_resolves_aliases_before_checking_allowed_sources():
    from app.brain.semantics.metric_registry import find_source_envelope_violations

    # revenue_baseline is an alias for commerce.revenue.baseline whose
    # allowed_sources are csv/google_sheets/sample; mercadolibre is excluded.
    violations = find_source_envelope_violations(
        ("revenue_baseline",), connector_type="mercadolibre"
    )
    assert len(violations) == 1
    assert violations[0].key == "revenue_baseline"
    assert "commerce.revenue.baseline" in violations[0].message

    assert find_source_envelope_violations(
        ("revenue_baseline",), connector_type="google_sheets"
    ) == []


def test_source_envelope_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_source_envelope_violations

    # Unknown keys are owned by validate_metrics; they are intentionally
    # skipped here so the two diagnostics can be composed without overlap.
    assert find_source_envelope_violations(
        ("never_registered_metric",), connector_type="meta_ads"
    ) == []


def test_source_envelope_helper_rejects_empty_connector_type_and_empty_keys():
    import pytest

    from app.brain.semantics.metric_registry import find_source_envelope_violations

    with pytest.raises(ValueError, match="connector_type"):
        find_source_envelope_violations(("ad_spend_today",), connector_type="")

    with pytest.raises(ValueError, match="metric keys"):
        find_source_envelope_violations(("",), connector_type="meta_ads")


def test_strict_metric_validation_raises_on_unknown_metric_without_mutating_input():
    from app.brain.semantics.metric_registry import UnknownMetricError, validate_metrics

    metrics = [Metric(key="mystery_metric", label="Mystery", value=1, evidence=[_evidence("sample")])]
    original_dump = metrics[0].model_dump(mode="json")

    with pytest.raises(UnknownMetricError, match="mystery_metric"):
        validate_metrics(metrics, strict=True)

    assert metrics[0].model_dump(mode="json") == original_dump


def test_family_envelope_helper_flags_metrics_outside_connector_declared_families():
    from app.brain.semantics.metric_registry import find_family_envelope_violations

    # tiendanube connector declares commerce.* + runtime.* families but does
    # not declare ads.spend; emitting ad_spend_today through tiendanube should
    # be flagged as outside the connector's declared family envelope.
    violations = find_family_envelope_violations(
        ("orders_today", "ad_spend_today"),
        connector_type="tiendanube",
        declared_families=(
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "runtime.freshness",
            "runtime.data_quality",
        ),
    )

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("undeclared_family", "ad_spend_today", 1, "warning")
    ]
    assert "tiendanube" in violations[0].message
    assert "ads.spend" in violations[0].message
    assert "ads.spend.total" in violations[0].message


def test_family_envelope_helper_returns_empty_when_all_metrics_inside_envelope():
    from app.brain.semantics.metric_registry import find_family_envelope_violations

    assert (
        find_family_envelope_violations(
            ("orders_today", "revenue_today", "stock_units"),
            connector_type="tiendanube",
            declared_families=(
                "commerce.orders",
                "commerce.revenue",
                "commerce.inventory",
            ),
        )
        == []
    )


def test_family_envelope_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_family_envelope_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so the three diagnostics compose without overlap.
    assert (
        find_family_envelope_violations(
            ("never_registered_metric",),
            connector_type="tiendanube",
            declared_families=("commerce.orders",),
        )
        == []
    )


def test_family_envelope_helper_resolves_aliases_before_checking_declared_families():
    from app.brain.semantics.metric_registry import find_family_envelope_violations

    # revenue_baseline resolves to commerce.revenue.baseline whose family is
    # commerce.revenue. If the caller only declares commerce.orders, the
    # alias-resolved family is reported as undeclared.
    violations = find_family_envelope_violations(
        ("revenue_baseline",),
        connector_type="csv",
        declared_families=("commerce.orders",),
    )
    assert len(violations) == 1
    assert violations[0].key == "revenue_baseline"
    assert "commerce.revenue.baseline" in violations[0].message
    assert "commerce.revenue" in violations[0].message

    assert (
        find_family_envelope_violations(
            ("revenue_baseline",),
            connector_type="csv",
            declared_families=("commerce.revenue",),
        )
        == []
    )


def test_family_envelope_helper_rejects_empty_connector_type_declared_families_or_keys():
    from app.brain.semantics.metric_registry import find_family_envelope_violations

    with pytest.raises(ValueError, match="connector_type"):
        find_family_envelope_violations(
            ("orders_today",),
            connector_type="",
            declared_families=("commerce.orders",),
        )

    with pytest.raises(ValueError, match="declared_families"):
        find_family_envelope_violations(
            ("orders_today",),
            connector_type="tiendanube",
            declared_families=(),
        )

    with pytest.raises(ValueError, match="metric keys"):
        find_family_envelope_violations(
            ("",),
            connector_type="tiendanube",
            declared_families=("commerce.orders",),
        )


def test_evidence_source_helper_flags_evidence_sources_outside_canonical_allowed_sources():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    metrics = [
        Metric(
            key="commerce.orders.count",
            label="Orders",
            value=12,
            evidence=[_evidence("tiendanube")],
        ),
        Metric(
            key="ad_spend_today",
            label="Ad spend",
            value=1500,
            unit="ARS",
            evidence=[_evidence("tiendanube")],
        ),
    ]

    violations = find_evidence_source_violations(metrics)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("evidence_source_mismatch", "ad_spend_today", 1, "warning")
    ]
    assert "tiendanube" in violations[0].message
    assert "ads.spend.total" in violations[0].message
    assert "meta_ads" in violations[0].message


def test_evidence_source_helper_resolves_aliases_before_checking_allowed_sources():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    metrics = [
        Metric(
            key="revenue_baseline",
            label="Promedio reciente",
            value=120000,
            unit="ARS",
            evidence=[_evidence("mercadolibre")],
        ),
    ]

    violations = find_evidence_source_violations(metrics)
    assert len(violations) == 1
    assert violations[0].key == "revenue_baseline"
    assert "commerce.revenue.baseline" in violations[0].message


def test_evidence_source_helper_returns_empty_when_all_evidence_sources_allowed():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    metrics = [
        Metric(
            key="revenue_today",
            label="Revenue",
            value=90000,
            unit="ARS",
            evidence=[_evidence("tiendanube"), _evidence("mercadolibre")],
        ),
    ]
    assert find_evidence_source_violations(metrics) == []


def test_evidence_source_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    metrics = [
        Metric(
            key="mystery_metric",
            label="Mystery",
            value=1,
            evidence=[_evidence("never_seen_source")],
        ),
    ]
    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so all four diagnostics compose without overlap.
    assert find_evidence_source_violations(metrics) == []


def test_evidence_source_helper_reports_each_disallowed_source_once_per_metric_in_input_order():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    metrics = [
        Metric(
            key="ads.spend.total",
            label="Ad spend",
            value=1500,
            unit="ARS",
            evidence=[
                _evidence("tiendanube"),
                _evidence("mercadolibre"),
                _evidence("tiendanube"),
                _evidence("meta_ads"),
            ],
        ),
    ]

    violations = find_evidence_source_violations(metrics)
    # tiendanube appears twice but should be reported once; meta_ads is allowed
    # so should not appear; mercadolibre is also disallowed.
    assert [(issue.code, issue.index, "src=" in issue.message) for issue in violations] == [
        ("evidence_source_mismatch", 0, True),
        ("evidence_source_mismatch", 0, True),
    ]
    sources_reported = [issue.message.split("src=", 1)[1].split(";", 1)[0] for issue in violations]
    assert sources_reported == ["tiendanube", "mercadolibre"]


def test_evidence_source_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    metrics = [
        Metric(
            key="ad_spend_today",
            label="Ad spend",
            value=1500,
            unit="ARS",
            evidence=[_evidence("tiendanube"), _evidence("mercadolibre")],
        ),
    ]
    first = find_evidence_source_violations(metrics)
    second = find_evidence_source_violations(metrics)
    assert first == second


def test_evidence_source_helper_rejects_metrics_missing_key_or_evidence():
    from app.brain.semantics.metric_registry import find_evidence_source_violations

    with pytest.raises(ValueError, match="key"):
        find_evidence_source_violations([{"label": "no key", "evidence": []}])

    with pytest.raises(ValueError, match="evidence"):
        find_evidence_source_violations([{"key": "ad_spend_today"}])


def test_value_kind_helper_flags_string_value_for_numeric_money_metric():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    metrics = [
        Metric(
            key="commerce.revenue.total",
            label="Revenue",
            value=90000,
            unit="ARS",
            evidence=[_evidence("tiendanube")],
        ),
        Metric(
            key="ad_spend_today",
            label="Ad spend",
            value="1500.75",
            unit="ARS",
            evidence=[_evidence("meta_ads")],
        ),
    ]

    violations = find_value_kind_violations(metrics)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("value_kind_mismatch", "ad_spend_today", 1, "warning"),
    ]
    assert "ads.spend.total" in violations[0].message
    assert "money" in violations[0].message
    assert "str" in violations[0].message


def test_value_kind_helper_resolves_aliases_before_checking_unit_kind():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    # revenue_baseline resolves to commerce.revenue.baseline whose unit is
    # "money"; a string value should be flagged via the alias path.
    metrics = [
        Metric(
            key="revenue_baseline",
            label="Promedio reciente",
            value="120000",
            unit="ARS",
            evidence=[_evidence("google_sheets")],
        ),
    ]
    violations = find_value_kind_violations(metrics)
    assert len(violations) == 1
    assert violations[0].key == "revenue_baseline"
    assert "commerce.revenue.baseline" in violations[0].message


def test_value_kind_helper_returns_empty_when_all_values_match_canonical_unit_kind():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    metrics = [
        Metric(
            key="commerce.orders.count",
            label="Orders",
            value=12,
            evidence=[_evidence("tiendanube")],
        ),
        Metric(
            key="commerce.revenue.total",
            label="Revenue",
            value=90000.5,
            unit="ARS",
            evidence=[_evidence("tiendanube")],
        ),
        Metric(
            key="ads.delivery.impressions",
            label="Impressions",
            value=20000,
            evidence=[_evidence("meta_ads")],
        ),
    ]
    assert find_value_kind_violations(metrics) == []


def test_value_kind_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so all five diagnostics can compose without overlap.
    metrics = [
        Metric(
            key="mystery_metric",
            label="Mystery",
            value="not a number",
            evidence=[_evidence("sample")],
        ),
    ]
    assert find_value_kind_violations(metrics) == []


def test_value_kind_helper_treats_bool_as_disallowed_for_numeric_units():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    # bool is a subclass of int in Python, but a count/money/percent/duration
    # metric should reject bools so a True/False does not silently pose as a
    # numeric measurement. Use mapping form here because the Pydantic Metric
    # union ``float | int | str`` coerces True to 1.0 before validation.
    metrics = [
        {"key": "commerce.orders.count", "value": True},
    ]
    violations = find_value_kind_violations(metrics)
    assert [(issue.code, issue.key, issue.index) for issue in violations] == [
        ("value_kind_mismatch", "commerce.orders.count", 0),
    ]
    assert "count" in violations[0].message
    assert "bool" in violations[0].message


def test_value_kind_helper_flags_non_bool_for_boolean_units():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    # runtime.connector.status is canonical unit "boolean"; an int (1) must not
    # silently pose as a status flag. Use mapping form so we control the value
    # type directly (Pydantic Metric coerces int to float through the union).
    metrics = [
        {"key": "runtime.connector.status", "value": 1},
    ]
    violations = find_value_kind_violations(metrics)
    assert [(issue.code, issue.key, issue.index) for issue in violations] == [
        ("value_kind_mismatch", "runtime.connector.status", 0),
    ]
    assert "boolean" in violations[0].message
    assert "int" in violations[0].message

    # And a real bool through the mapping form passes.
    assert find_value_kind_violations(
        [{"key": "runtime.connector.status", "value": True}]
    ) == []


def test_value_kind_helper_flags_numeric_for_timestamp_units():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    # runtime.freshness.last_success_at is canonical unit "timestamp"; numeric
    # epoch-style values must not silently pose as ISO timestamps.
    metrics = [
        Metric(
            key="runtime.freshness.last_success_at",
            label="Last sync",
            value=1700000000,
            evidence=[_evidence("tiendanube")],
        ),
        Metric(
            key="runtime.freshness.last_success_at",
            label="Last sync",
            value="2025-01-15T12:00:00+00:00",
            evidence=[_evidence("tiendanube")],
        ),
    ]
    violations = find_value_kind_violations(metrics)
    assert [(issue.code, issue.key, issue.index) for issue in violations] == [
        ("value_kind_mismatch", "runtime.freshness.last_success_at", 0),
    ]
    assert "timestamp" in violations[0].message


def test_value_kind_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    metrics = [
        Metric(
            key="ad_spend_today",
            label="Ad spend",
            value="1500",
            unit="ARS",
            evidence=[_evidence("meta_ads")],
        ),
        Metric(
            key="commerce.orders.count",
            label="Orders",
            value=12,
            evidence=[_evidence("tiendanube")],
        ),
    ]
    first = find_value_kind_violations(metrics)
    second = find_value_kind_violations(metrics)
    assert first == second


def test_value_kind_helper_rejects_metrics_missing_key_or_value():
    from app.brain.semantics.metric_registry import find_value_kind_violations

    with pytest.raises(ValueError, match="key"):
        find_value_kind_violations([{"label": "no key", "value": 1}])

    with pytest.raises(ValueError, match="value"):
        find_value_kind_violations([{"key": "ad_spend_today"}])


def test_value_kind_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_value_kind_violations")
    assert "find_value_kind_violations" in semantics.__all__
