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


def test_report_allowed_helper_flags_metrics_whose_canonical_definition_is_not_report_allowed():
    from app.brain.semantics.metric_registry import find_report_allowed_violations

    # runtime.freshness.* and runtime.connector.status are report_allowed=False;
    # they back control-plane health signals and must never reach a user-facing
    # report path. revenue_today is report_allowed=True and must not be flagged.
    metric_keys = (
        "revenue_today",
        "runtime.freshness.last_success_at",
        "runtime.connector.status",
    )

    violations = find_report_allowed_violations(metric_keys)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("report_not_allowed", "runtime.freshness.last_success_at", 1, "warning"),
        ("report_not_allowed", "runtime.connector.status", 2, "warning"),
    ]
    assert "runtime.freshness.last_success_at" in violations[0].message
    assert "report_allowed" in violations[0].message


def test_report_allowed_helper_returns_empty_when_all_keys_report_allowed():
    from app.brain.semantics.metric_registry import find_report_allowed_violations

    assert find_report_allowed_violations(
        ("orders_today", "revenue_today", "stock_units", "ad_spend_today")
    ) == []


def test_report_allowed_helper_resolves_aliases_before_checking_report_allowed():
    from app.brain.semantics.metric_registry import find_report_allowed_violations

    # All current aliases resolve to report_allowed=True canonical metrics, so
    # add a synthetic report_not_allowed metric exposed only via an alias to
    # prove alias resolution feeds into the report_allowed check.
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="runtime.health.score",
                family="runtime.health",
                label="Runtime health score",
                unit="percent",
                allowed_sources=("sample",),
                aliases=("runtime_health_score_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
            ),
        )
    )

    violations = find_report_allowed_violations(
        ("runtime_health_score_legacy",), registry=registry
    )
    assert len(violations) == 1
    assert violations[0].key == "runtime_health_score_legacy"
    assert "runtime.health.score" in violations[0].message


def test_report_allowed_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_report_allowed_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so it can compose cleanly with the existing envelope helpers.
    assert find_report_allowed_violations(("never_registered_metric",)) == []


def test_report_allowed_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_report_allowed_violations

    metric_keys = (
        "revenue_today",
        "runtime.freshness.age_seconds",
        "runtime.connector.status",
    )
    first = find_report_allowed_violations(metric_keys)
    second = find_report_allowed_violations(metric_keys)
    assert first == second


def test_report_allowed_helper_rejects_empty_metric_keys():
    from app.brain.semantics.metric_registry import find_report_allowed_violations

    with pytest.raises(ValueError, match="metric keys"):
        find_report_allowed_violations(("",))


def test_report_allowed_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_report_allowed_violations")
    assert "find_report_allowed_violations" in semantics.__all__


def test_validate_report_metric_keys_composes_unknown_then_report_not_allowed_diagnostics():
    from app.brain.semantics.metric_registry import validate_report_metric_keys

    # Mixed bag: one canonical report-allowed key, one report_not_allowed
    # runtime key, and one unknown key. The composition must report unknowns
    # first (owned by validate_metrics) and then report_not_allowed (owned by
    # find_report_allowed_violations). Each diagnostic preserves its own
    # input-order index.
    metric_keys = (
        "revenue_today",
        "runtime.connector.status",
        "custom.unknown_report_metric",
    )

    issues = validate_report_metric_keys(metric_keys)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_report_metric", 2, "warning"),
        ("report_not_allowed", "runtime.connector.status", 1, "warning"),
    ]


def test_validate_report_metric_keys_returns_empty_when_all_keys_are_canonical_report_allowed():
    from app.brain.semantics.metric_registry import validate_report_metric_keys

    assert validate_report_metric_keys(
        ("orders_today", "revenue_today", "stock_units", "ad_spend_today")
    ) == []


def test_validate_report_metric_keys_threads_custom_registry_into_both_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_report_metric_keys,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="runtime.health.score",
                family="runtime.health",
                label="Runtime health score",
                unit="percent",
                allowed_sources=("sample",),
                aliases=("runtime_health_score_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
            ),
        )
    )

    issues = validate_report_metric_keys(
        ("runtime_health_score_legacy", "revenue_today"), registry=registry
    )
    # revenue_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a report_not_allowed canonical metric.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "revenue_today", 1),
        ("report_not_allowed", "runtime_health_score_legacy", 0),
    ]


def test_validate_report_metric_keys_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import validate_report_metric_keys

    metric_keys = (
        "revenue_today",
        "runtime.freshness.age_seconds",
        "custom.unknown_report_metric",
        "runtime.connector.status",
    )
    first = validate_report_metric_keys(metric_keys)
    second = validate_report_metric_keys(metric_keys)
    assert first == second


def test_validate_report_metric_keys_rejects_empty_keys():
    from app.brain.semantics.metric_registry import validate_report_metric_keys

    with pytest.raises(ValueError):
        validate_report_metric_keys(("",))


def test_validate_report_metric_keys_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_report_metric_keys")
    assert "validate_report_metric_keys" in semantics.__all__


def test_case_allowed_helper_flags_metrics_whose_canonical_definition_is_not_case_allowed():
    from app.brain.semantics.metric_registry import find_case_allowed_violations

    # commerce.average_order_value and ads.delivery.* are case_allowed=False;
    # they must not back Operational Case detections. commerce.orders.count is
    # case_allowed=True and must not be flagged.
    metric_keys = (
        "commerce.orders.count",
        "avg_order_value",
        "ad_impressions_today",
    )

    violations = find_case_allowed_violations(metric_keys)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("case_not_allowed", "avg_order_value", 1, "warning"),
        ("case_not_allowed", "ad_impressions_today", 2, "warning"),
    ]
    assert "commerce.average_order_value" in violations[0].message
    assert "case_allowed" in violations[0].message


def test_case_allowed_helper_returns_empty_when_all_keys_case_allowed():
    from app.brain.semantics.metric_registry import find_case_allowed_violations

    assert find_case_allowed_violations(
        ("orders_today", "revenue_today", "stock_units", "ad_spend_today")
    ) == []


def test_case_allowed_helper_resolves_aliases_before_checking_case_allowed():
    from app.brain.semantics.metric_registry import find_case_allowed_violations

    # avg_order_value is an alias for commerce.average_order_value whose
    # case_allowed=False; the alias path must resolve before the check so
    # legacy keys are still pinned out of case input.
    violations = find_case_allowed_violations(("avg_order_value",))
    assert len(violations) == 1
    assert violations[0].key == "avg_order_value"
    assert "commerce.average_order_value" in violations[0].message


def test_case_allowed_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_case_allowed_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so it composes cleanly with the existing envelope helpers.
    assert find_case_allowed_violations(("never_registered_metric",)) == []


def test_case_allowed_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_case_allowed_violations

    metric_keys = (
        "orders_today",
        "avg_order_value",
        "ad_impressions_today",
    )
    first = find_case_allowed_violations(metric_keys)
    second = find_case_allowed_violations(metric_keys)
    assert first == second


def test_case_allowed_helper_rejects_empty_metric_keys():
    from app.brain.semantics.metric_registry import find_case_allowed_violations

    with pytest.raises(ValueError, match="metric keys"):
        find_case_allowed_violations(("",))


def test_case_allowed_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_case_allowed_violations")
    assert "find_case_allowed_violations" in semantics.__all__


def test_validate_case_metric_keys_composes_unknown_then_case_not_allowed_diagnostics():
    from app.brain.semantics.metric_registry import validate_case_metric_keys

    # Mixed bag: one canonical case-allowed key, one case_not_allowed key, and
    # one unknown key. The composition must report unknowns first (owned by
    # validate_metrics) then case_not_allowed (owned by find_case_allowed_violations).
    # Each diagnostic preserves its own input-order index.
    metric_keys = (
        "orders_today",
        "avg_order_value",
        "custom.unknown_case_metric",
    )

    issues = validate_case_metric_keys(metric_keys)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_case_metric", 2, "warning"),
        ("case_not_allowed", "avg_order_value", 1, "warning"),
    ]


def test_validate_case_metric_keys_returns_empty_when_all_keys_are_canonical_case_allowed():
    from app.brain.semantics.metric_registry import validate_case_metric_keys

    assert validate_case_metric_keys(
        ("orders_today", "revenue_today", "stock_units", "ad_spend_today")
    ) == []


def test_validate_case_metric_keys_threads_custom_registry_into_both_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_case_metric_keys,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="ads.delivery.legacy_impressions",
                family="ads.delivery",
                label="Legacy ad impressions",
                unit="count",
                allowed_sources=("sample",),
                aliases=("legacy_impressions",),
                aggregation="sum",
                case_allowed=False,
            ),
        )
    )

    issues = validate_case_metric_keys(
        ("legacy_impressions", "orders_today"), registry=registry
    )
    # orders_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a case_not_allowed canonical metric.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "orders_today", 1),
        ("case_not_allowed", "legacy_impressions", 0),
    ]


def test_validate_case_metric_keys_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import validate_case_metric_keys

    metric_keys = (
        "orders_today",
        "avg_order_value",
        "custom.unknown_case_metric",
        "ad_impressions_today",
    )
    first = validate_case_metric_keys(metric_keys)
    second = validate_case_metric_keys(metric_keys)
    assert first == second


def test_validate_case_metric_keys_rejects_empty_keys():
    from app.brain.semantics.metric_registry import validate_case_metric_keys

    with pytest.raises(ValueError):
        validate_case_metric_keys(("",))


def test_validate_case_metric_keys_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_case_metric_keys")
    assert "validate_case_metric_keys" in semantics.__all__


def _metric(key: str, *sources: str, value: float | int | str = 1, unit: str | None = None) -> Metric:
    return Metric(
        key=key,
        label=key,
        value=value,
        unit=unit,
        evidence=[_evidence(source) for source in sources],
    )


def test_validate_report_metric_objects_composes_unknown_then_report_then_evidence_then_value_kind():
    """Parallel to ``ConnectorSpec.validate_emitted_metric_objects`` but on the
    report-rendering side: the five-diagnostic composition must report
    unknown_metric first, then report_not_allowed, then evidence_missing, then
    evidence_source_mismatch, and finally value_kind_mismatch. Each diagnostic
    preserves its own input-order index. This case carries non-empty evidence
    on every metric so the evidence_missing slot is exercised by a separate
    dedicated test.
    """

    from app.brain.semantics.metric_registry import validate_report_metric_objects

    metrics = [
        _metric("revenue_today", "tiendanube", unit="ARS"),
        _metric("custom.unknown_report_metric", "tiendanube"),
        _metric("runtime.freshness.age_seconds", "tiendanube", value=42),
        _metric("ad_spend_today", "whatsapp", unit="ARS"),
        _metric("orders_today", "tiendanube", value="not a number"),
    ]

    issues = validate_report_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_report_metric", 1, "warning"),
        ("report_not_allowed", "runtime.freshness.age_seconds", 2, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 3, "warning"),
        ("value_kind_mismatch", "orders_today", 4, "warning"),
    ]


def test_validate_report_metric_objects_slots_evidence_missing_between_report_and_evidence_source():
    """Mixed bag exercising the evidence_missing slot. The composition order
    inside :func:`validate_report_metric_objects` must put evidence_missing
    immediately after report_not_allowed and before evidence_source_mismatch
    so structural ``no evidence at all`` diagnostics surface before content
    diagnostics about wrong-source evidence. Each diagnostic preserves its own
    input-order index. Mapping form is required because Pydantic ``Metric``
    enforces ``min_length=1`` on evidence and cannot represent the missing
    case directly."""

    from app.brain.semantics.metric_registry import validate_report_metric_objects

    metrics = [
        {
            "key": "revenue_today",
            "value": 120000,
            "unit": "ARS",
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "custom.unknown_report_metric",
            "value": 1,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "runtime.freshness.age_seconds",
            "value": 42,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {"key": "commerce.revenue.total", "value": 90000, "unit": "ARS", "evidence": []},
        {
            "key": "ad_spend_today",
            "value": 1500,
            "unit": "ARS",
            "evidence": [{"source": "whatsapp", "label": "wa run"}],
        },
        {
            "key": "orders_today",
            "value": "not a number",
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
    ]

    issues = validate_report_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_report_metric", 1, "warning"),
        ("report_not_allowed", "runtime.freshness.age_seconds", 2, "warning"),
        ("evidence_missing", "commerce.revenue.total", 3, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 4, "warning"),
        ("value_kind_mismatch", "orders_today", 5, "warning"),
    ]


def test_validate_report_metric_objects_appends_money_currency_missing_after_value_kind():
    """The six-diagnostic composition inside
    :func:`validate_report_metric_objects` must place money_currency_missing
    after value_kind_mismatch: structural and value-type diagnostics surface
    before the rendering-metadata diagnostic that money metrics must carry a
    currency string for reports to render unambiguously. Each diagnostic
    preserves its own input-order index, and a single metric that is both
    value-kind invalid and missing currency must surface in both slots."""

    from app.brain.semantics.metric_registry import validate_report_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_report_metric", "tiendanube"),
        _metric("runtime.freshness.age_seconds", "tiendanube", value=42),
        _metric("commerce.revenue.baseline", "google_sheets", value=80000),
        _metric("ad_spend_today", "meta_ads", value="invalid"),
    ]

    issues = validate_report_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_report_metric", 1, "warning"),
        ("report_not_allowed", "runtime.freshness.age_seconds", 2, "warning"),
        ("value_kind_mismatch", "ad_spend_today", 4, "warning"),
        ("money_currency_missing", "commerce.revenue.baseline", 3, "warning"),
        ("money_currency_missing", "ad_spend_today", 4, "warning"),
    ]


def test_validate_report_metric_objects_returns_empty_for_clean_report_metrics():
    from app.brain.semantics.metric_registry import validate_report_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("revenue_today", "mercadolibre", value=120000, unit="ARS"),
        _metric("stock_units", "tiendanube", value=42),
        _metric("ad_spend_today", "meta_ads", value=1500, unit="ARS"),
    ]

    assert validate_report_metric_objects(metrics) == []


def test_validate_report_metric_objects_matches_key_path_when_no_object_violations():
    """When every metric object has in-envelope evidence sources and the value
    type matches the canonical unit kind, the object-level result must equal
    ``validate_report_metric_keys`` over the same keys so callers can freely
    upgrade from keys to objects without a behavior change."""

    from app.brain.semantics.metric_registry import (
        validate_report_metric_keys,
        validate_report_metric_objects,
    )

    metrics = [
        _metric("revenue_today", "tiendanube", value=120000, unit="ARS"),
        _metric("custom.unknown_report_metric", "tiendanube"),
        _metric("runtime.freshness.age_seconds", "tiendanube", value=42),
    ]
    keys = [metric.key for metric in metrics]

    assert validate_report_metric_objects(metrics) == validate_report_metric_keys(keys)


def test_validate_report_metric_objects_threads_custom_registry_into_all_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_report_metric_objects,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="runtime.health.score",
                family="runtime.health",
                label="Runtime health score",
                unit="percent",
                allowed_sources=("sample",),
                aliases=("runtime_health_score_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
            ),
        )
    )

    metrics = [
        _metric("runtime_health_score_legacy", "sample", value=0.95),
        _metric("revenue_today", "tiendanube", value=120000),
    ]

    issues = validate_report_metric_objects(metrics, registry=registry)
    # revenue_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a report_not_allowed canonical metric.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "revenue_today", 1),
        ("report_not_allowed", "runtime_health_score_legacy", 0),
    ]


def test_validate_report_metric_objects_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import validate_report_metric_objects

    metrics = [
        _metric("revenue_today", "tiendanube", value=120000),
        _metric("custom.unknown_report_metric", "tiendanube"),
        _metric("runtime.freshness.age_seconds", "tiendanube", value=42),
        _metric("ad_spend_today", "whatsapp"),
    ]

    first = validate_report_metric_objects(metrics)
    second = validate_report_metric_objects(metrics)
    assert first == second


def test_validate_report_metric_objects_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_report_metric_objects")
    assert "validate_report_metric_objects" in semantics.__all__


def test_validate_case_metric_objects_composes_unknown_then_case_then_evidence_then_value_kind():
    """Parallel to :func:`validate_report_metric_objects` but on the case
    detection side: the four-diagnostic composition must report unknown_metric
    first, then case_not_allowed, then evidence_source_mismatch, and finally
    value_kind_mismatch. Each diagnostic preserves its own input-order index.
    """

    from app.brain.semantics.metric_registry import validate_case_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_case_metric", "tiendanube"),
        _metric("avg_order_value", "tiendanube", value=7500, unit="ARS"),
        _metric("ad_spend_today", "whatsapp", value=1500, unit="ARS"),
        _metric("commerce.orders.count", "tiendanube", value="not a number"),
    ]

    issues = validate_case_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_case_metric", 1, "warning"),
        ("case_not_allowed", "avg_order_value", 2, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 3, "warning"),
        ("value_kind_mismatch", "commerce.orders.count", 4, "warning"),
    ]


def test_validate_case_metric_objects_slots_evidence_missing_between_case_and_evidence_source():
    """Mixed bag exercising the evidence_missing slot. The composition order
    inside :func:`validate_case_metric_objects` must put evidence_missing
    immediately after case_not_allowed and before evidence_source_mismatch
    so structural ``no evidence at all`` diagnostics surface before content
    diagnostics about wrong-source evidence. Each diagnostic preserves its own
    input-order index. Mapping form is required because Pydantic ``Metric``
    enforces ``min_length=1`` on evidence and cannot represent the missing
    case directly."""

    from app.brain.semantics.metric_registry import validate_case_metric_objects

    metrics = [
        {
            "key": "orders_today",
            "value": 12,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "custom.unknown_case_metric",
            "value": 1,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "avg_order_value",
            "value": 7500,
            "unit": "ARS",
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {"key": "commerce.revenue.total", "value": 90000, "unit": "ARS", "evidence": []},
        {
            "key": "ad_spend_today",
            "value": 1500,
            "unit": "ARS",
            "evidence": [{"source": "whatsapp", "label": "wa run"}],
        },
        {
            "key": "commerce.orders.count",
            "value": "not a number",
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
    ]

    issues = validate_case_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_case_metric", 1, "warning"),
        ("case_not_allowed", "avg_order_value", 2, "warning"),
        ("evidence_missing", "commerce.revenue.total", 3, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 4, "warning"),
        ("value_kind_mismatch", "commerce.orders.count", 5, "warning"),
    ]


def test_validate_case_metric_objects_appends_money_currency_missing_after_value_kind():
    """The six-diagnostic composition inside
    :func:`validate_case_metric_objects` must place money_currency_missing
    after value_kind_mismatch: structural and value-type diagnostics surface
    before the rendering-metadata diagnostic that money metrics must carry a
    currency string for case detections to compare values unambiguously. Each
    diagnostic preserves its own input-order index, and a single metric that is
    both value-kind invalid and missing currency must surface in both slots."""

    from app.brain.semantics.metric_registry import validate_case_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_case_metric", "tiendanube"),
        _metric("avg_order_value", "tiendanube", value=7500),
        _metric("revenue_today", "tiendanube", value=120000),
        _metric("ad_spend_today", "meta_ads", value="invalid"),
    ]

    issues = validate_case_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_case_metric", 1, "warning"),
        ("case_not_allowed", "avg_order_value", 2, "warning"),
        ("value_kind_mismatch", "ad_spend_today", 4, "warning"),
        ("money_currency_missing", "avg_order_value", 2, "warning"),
        ("money_currency_missing", "revenue_today", 3, "warning"),
        ("money_currency_missing", "ad_spend_today", 4, "warning"),
    ]


def test_validate_case_metric_objects_returns_empty_for_clean_case_metrics():
    from app.brain.semantics.metric_registry import validate_case_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("revenue_today", "mercadolibre", value=120000, unit="ARS"),
        _metric("stock_units", "tiendanube", value=42),
        _metric("ad_spend_today", "meta_ads", value=1500, unit="ARS"),
    ]

    assert validate_case_metric_objects(metrics) == []


def test_validate_case_metric_objects_matches_key_path_when_no_object_violations():
    """When every metric object has in-envelope evidence sources and the value
    type matches the canonical unit kind, the object-level result must equal
    ``validate_case_metric_keys`` over the same keys so callers can freely
    upgrade from keys to objects without a behavior change."""

    from app.brain.semantics.metric_registry import (
        validate_case_metric_keys,
        validate_case_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_case_metric", "tiendanube"),
        _metric("avg_order_value", "tiendanube", value=7500, unit="ARS"),
    ]
    keys = [metric.key for metric in metrics]

    assert validate_case_metric_objects(metrics) == validate_case_metric_keys(keys)


def test_validate_case_metric_objects_threads_custom_registry_into_all_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_case_metric_objects,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="ads.delivery.legacy_impressions",
                family="ads.delivery",
                label="Legacy ad impressions",
                unit="count",
                allowed_sources=("sample",),
                aliases=("legacy_impressions",),
                aggregation="sum",
                case_allowed=False,
            ),
        )
    )

    metrics = [
        _metric("legacy_impressions", "sample", value=20000),
        _metric("orders_today", "tiendanube", value=12),
    ]

    issues = validate_case_metric_objects(metrics, registry=registry)
    # orders_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a case_not_allowed canonical metric.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "orders_today", 1),
        ("case_not_allowed", "legacy_impressions", 0),
    ]


def test_validate_case_metric_objects_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import validate_case_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_case_metric", "tiendanube"),
        _metric("avg_order_value", "tiendanube", value=7500),
        _metric("ad_spend_today", "whatsapp", value=1500),
    ]

    first = validate_case_metric_objects(metrics)
    second = validate_case_metric_objects(metrics)
    assert first == second


def test_validate_case_metric_objects_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_case_metric_objects")
    assert "validate_case_metric_objects" in semantics.__all__


def test_evidence_required_helper_flags_metric_with_empty_evidence_collection():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    # commerce.revenue.total has evidence_required=True (the default). A metric
    # with a zero-entry evidence collection must be reported as missing
    # evidence. Use the mapping form because Pydantic Metric enforces
    # min_length=1 on evidence and cannot represent this state directly.
    metrics = [
        {"key": "commerce.orders.count", "value": 12, "evidence": [{"source": "tiendanube", "label": "tn run"}]},
        {"key": "commerce.revenue.total", "value": 120000, "evidence": []},
    ]

    violations = find_evidence_required_violations(metrics)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("evidence_missing", "commerce.revenue.total", 1, "warning"),
    ]
    assert "commerce.revenue.total" in violations[0].message
    assert "evidence_required" in violations[0].message


def test_evidence_required_helper_resolves_aliases_before_checking_evidence_required():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    # revenue_baseline is an alias for commerce.revenue.baseline whose
    # evidence_required=True; an empty evidence collection via the alias path
    # must be reported and the canonical key surfaced in the message.
    metrics = [{"key": "revenue_baseline", "value": 90000, "evidence": []}]
    violations = find_evidence_required_violations(metrics)
    assert len(violations) == 1
    assert violations[0].key == "revenue_baseline"
    assert "commerce.revenue.baseline" in violations[0].message


def test_evidence_required_helper_returns_empty_when_all_metrics_carry_evidence():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    metrics = [
        Metric(
            key="commerce.orders.count",
            label="Orders",
            value=12,
            evidence=[_evidence("tiendanube")],
        ),
        Metric(
            key="revenue_today",
            label="Revenue",
            value=90000,
            unit="ARS",
            evidence=[_evidence("tiendanube"), _evidence("mercadolibre")],
        ),
    ]
    assert find_evidence_required_violations(metrics) == []


def test_evidence_required_helper_treats_none_evidence_as_empty_collection():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    # Some intermediate runtime states (e.g., draft metric envelopes) may
    # carry ``evidence=None``. The helper must treat None as a zero-entry
    # collection rather than raising, so it can compose with the rest of the
    # metric-validation surface during a control-plane sweep.
    metrics = [{"key": "commerce.orders.count", "value": 12, "evidence": None}]
    violations = find_evidence_required_violations(metrics)
    assert [(issue.code, issue.key, issue.index) for issue in violations] == [
        ("evidence_missing", "commerce.orders.count", 0),
    ]


def test_evidence_required_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so it can compose cleanly with the existing helpers without
    # double-reporting.
    metrics = [{"key": "never_registered_metric", "value": 1, "evidence": []}]
    assert find_evidence_required_violations(metrics) == []


def test_evidence_required_helper_skips_metrics_whose_canonical_definition_does_not_require_evidence():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        find_evidence_required_violations,
    )

    # No canonical metric in the default registry currently sets
    # evidence_required=False, so prove the flag is honored via a custom
    # registry. An empty evidence collection on a non-evidence-required metric
    # must not be flagged.
    registry = MetricRegistry(
        (
            MetricDefinition(
                key="runtime.health.score",
                family="runtime.health",
                label="Runtime health score",
                unit="percent",
                allowed_sources=("sample",),
                aliases=("runtime_health_score_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
                evidence_required=False,
            ),
        )
    )

    metrics = [
        {"key": "runtime.health.score", "value": 0.95, "evidence": []},
        {"key": "runtime_health_score_legacy", "value": 0.91, "evidence": []},
    ]
    assert find_evidence_required_violations(metrics, registry=registry) == []


def test_evidence_required_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    metrics = [
        {"key": "commerce.orders.count", "value": 12, "evidence": []},
        {"key": "commerce.revenue.total", "value": 90000, "evidence": []},
    ]
    first = find_evidence_required_violations(metrics)
    second = find_evidence_required_violations(metrics)
    assert first == second


def test_evidence_required_helper_rejects_metrics_missing_key_or_evidence_field():
    from app.brain.semantics.metric_registry import find_evidence_required_violations

    with pytest.raises(ValueError, match="key"):
        find_evidence_required_violations([{"label": "no key", "evidence": []}])

    with pytest.raises(ValueError, match="evidence"):
        find_evidence_required_violations([{"key": "commerce.orders.count"}])


def test_evidence_required_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_evidence_required_violations")
    assert "find_evidence_required_violations" in semantics.__all__


def test_pii_class_helper_flags_metrics_whose_canonical_pii_class_is_not_allowed_on_surface():
    from app.brain.semantics.metric_registry import find_pii_class_violations

    # support.conversations.unanswered_count is pii_class="low" in the default
    # registry; commerce.orders.count is pii_class="none". A surface that only
    # allows "none" must flag the low-pii metric but accept the no-pii metric.
    metric_keys = (
        "commerce.orders.count",
        "support.conversations.unanswered_count",
        "unanswered_conversations",  # alias of the same low-pii metric
    )

    violations = find_pii_class_violations(
        metric_keys, allowed_pii_classes=("none",)
    )
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("pii_class_disallowed", "support.conversations.unanswered_count", 1, "warning"),
        ("pii_class_disallowed", "unanswered_conversations", 2, "warning"),
    ]
    assert "support.conversations.unanswered_count" in violations[0].message
    assert "low" in violations[0].message
    assert "none" in violations[0].message


def test_pii_class_helper_returns_empty_when_all_keys_within_allowed_pii_classes():
    from app.brain.semantics.metric_registry import find_pii_class_violations

    # "low" surface accepts both pii_class="none" and pii_class="low" metrics.
    assert (
        find_pii_class_violations(
            (
                "commerce.orders.count",
                "support.conversations.unanswered_count",
            ),
            allowed_pii_classes=("none", "low"),
        )
        == []
    )


def test_pii_class_helper_resolves_aliases_before_checking_pii_class():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        find_pii_class_violations,
    )

    # Synthetic sensitive metric exposed only via an alias proves alias
    # resolution feeds into the pii_class check.
    registry = MetricRegistry(
        (
            MetricDefinition(
                key="support.identity.email",
                family="support.identity",
                label="Owner identity email",
                unit="count",
                allowed_sources=("sample",),
                aliases=("owner_email_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
                pii_class="sensitive",
            ),
        )
    )

    violations = find_pii_class_violations(
        ("owner_email_legacy",),
        allowed_pii_classes=("none",),
        registry=registry,
    )
    assert len(violations) == 1
    assert violations[0].key == "owner_email_legacy"
    assert "support.identity.email" in violations[0].message
    assert "sensitive" in violations[0].message


def test_pii_class_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_pii_class_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so it can compose cleanly with the existing envelope helpers.
    assert (
        find_pii_class_violations(
            ("never_registered_metric",),
            allowed_pii_classes=("none",),
        )
        == []
    )


def test_pii_class_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_pii_class_violations

    metric_keys = (
        "commerce.orders.count",
        "support.conversations.unanswered_count",
        "support.conversations.oldest_unanswered_age_minutes",
    )
    first = find_pii_class_violations(metric_keys, allowed_pii_classes=("none",))
    second = find_pii_class_violations(metric_keys, allowed_pii_classes=("none",))
    assert first == second


def test_pii_class_helper_rejects_empty_metric_keys_or_allowed_classes():
    from app.brain.semantics.metric_registry import find_pii_class_violations

    with pytest.raises(ValueError, match="allowed_pii_classes"):
        find_pii_class_violations(
            ("commerce.orders.count",), allowed_pii_classes=()
        )

    with pytest.raises(ValueError, match="metric keys"):
        find_pii_class_violations(("",), allowed_pii_classes=("none",))


def test_pii_class_helper_rejects_unsupported_pii_class_in_allowed_set():
    from app.brain.semantics.metric_registry import find_pii_class_violations

    with pytest.raises(ValueError, match="pii_class"):
        find_pii_class_violations(
            ("commerce.orders.count",),
            allowed_pii_classes=("none", "ultra-secret"),
        )


def test_pii_class_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_pii_class_violations")
    assert "find_pii_class_violations" in semantics.__all__


def test_validate_surface_metric_keys_composes_unknown_then_pii_class_disallowed_diagnostics():
    from app.brain.semantics.metric_registry import validate_surface_metric_keys

    # Mixed bag: one canonical pii-none key, one low-pii canonical key, one
    # low-pii alias of the same canonical key, and one unknown key. The
    # composition must report unknowns first (owned by validate_metrics) and
    # then pii_class_disallowed (owned by find_pii_class_violations). Each
    # diagnostic preserves its own input-order index.
    metric_keys = (
        "commerce.orders.count",
        "support.conversations.unanswered_count",
        "unanswered_conversations",
        "custom.unknown_surface_metric",
    )

    issues = validate_surface_metric_keys(
        metric_keys, allowed_pii_classes=("none",)
    )
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_surface_metric", 3, "warning"),
        ("pii_class_disallowed", "support.conversations.unanswered_count", 1, "warning"),
        ("pii_class_disallowed", "unanswered_conversations", 2, "warning"),
    ]


def test_validate_surface_metric_keys_returns_empty_when_all_keys_within_allowed_pii_classes():
    from app.brain.semantics.metric_registry import validate_surface_metric_keys

    assert (
        validate_surface_metric_keys(
            (
                "commerce.orders.count",
                "support.conversations.unanswered_count",
            ),
            allowed_pii_classes=("none", "low"),
        )
        == []
    )


def test_validate_surface_metric_keys_threads_custom_registry_into_both_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_surface_metric_keys,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="support.identity.email",
                family="support.identity",
                label="Owner identity email",
                unit="count",
                allowed_sources=("sample",),
                aliases=("owner_email_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
                pii_class="sensitive",
            ),
        )
    )

    issues = validate_surface_metric_keys(
        ("owner_email_legacy", "commerce.orders.count"),
        allowed_pii_classes=("none",),
        registry=registry,
    )
    # commerce.orders.count is unknown under the custom registry; the alias on
    # the custom registry resolves to a sensitive pii_class.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "commerce.orders.count", 1),
        ("pii_class_disallowed", "owner_email_legacy", 0),
    ]


def test_validate_surface_metric_keys_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import validate_surface_metric_keys

    metric_keys = (
        "commerce.orders.count",
        "support.conversations.unanswered_count",
        "custom.unknown_surface_metric",
        "unanswered_conversations",
    )
    first = validate_surface_metric_keys(
        metric_keys, allowed_pii_classes=("none",)
    )
    second = validate_surface_metric_keys(
        metric_keys, allowed_pii_classes=("none",)
    )
    assert first == second


def test_validate_surface_metric_keys_rejects_empty_keys_or_allowed_classes():
    from app.brain.semantics.metric_registry import validate_surface_metric_keys

    with pytest.raises(ValueError, match="allowed_pii_classes"):
        validate_surface_metric_keys(
            ("commerce.orders.count",), allowed_pii_classes=()
        )

    with pytest.raises(ValueError):
        validate_surface_metric_keys(
            ("",), allowed_pii_classes=("none",)
        )


def test_validate_surface_metric_keys_rejects_unsupported_pii_class_in_allowed_set():
    from app.brain.semantics.metric_registry import validate_surface_metric_keys

    with pytest.raises(ValueError, match="pii_class"):
        validate_surface_metric_keys(
            ("commerce.orders.count",),
            allowed_pii_classes=("none", "ultra-secret"),
        )


def test_validate_surface_metric_keys_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_surface_metric_keys")
    assert "validate_surface_metric_keys" in semantics.__all__


def test_validate_surface_metric_objects_composes_unknown_then_pii_then_evidence_then_value_kind():
    """Parallel to :func:`validate_report_metric_objects` and
    :func:`validate_case_metric_objects` but on the surface dispatch side
    (WhatsApp, owner brief): the five-diagnostic composition must report
    unknown_metric first, then pii_class_disallowed, then evidence_missing,
    then evidence_source_mismatch, and finally value_kind_mismatch. Each
    diagnostic preserves its own input-order index. This case carries
    non-empty evidence on every metric so the evidence_missing slot is
    exercised by a separate dedicated test.
    """

    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_surface_metric", "tiendanube"),
        _metric("unanswered_conversations", "whatsapp", value=5),
        _metric("ad_spend_today", "whatsapp", unit="ARS"),
        _metric("commerce.orders.count", "tiendanube", value="not a number"),
    ]

    issues = validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",)
    )

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_surface_metric", 1, "warning"),
        ("pii_class_disallowed", "unanswered_conversations", 2, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 3, "warning"),
        ("value_kind_mismatch", "commerce.orders.count", 4, "warning"),
    ]


def test_validate_surface_metric_objects_slots_evidence_missing_between_pii_and_evidence_source():
    """Mixed bag exercising the evidence_missing slot. The composition order
    inside :func:`validate_surface_metric_objects` must put evidence_missing
    immediately after pii_class_disallowed and before evidence_source_mismatch
    so structural ``no evidence at all`` diagnostics surface before content
    diagnostics about wrong-source evidence. Each diagnostic preserves its own
    input-order index. Mapping form is required because Pydantic ``Metric``
    enforces ``min_length=1`` on evidence and cannot represent the missing
    case directly."""

    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [
        {
            "key": "orders_today",
            "value": 12,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "custom.unknown_surface_metric",
            "value": 1,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "unanswered_conversations",
            "value": 5,
            "unit": None,
            "evidence": [{"source": "whatsapp", "label": "wa run"}],
        },
        {"key": "commerce.revenue.total", "value": 90000, "unit": "ARS", "evidence": []},
        {
            "key": "ad_spend_today",
            "value": 1500,
            "unit": "ARS",
            "evidence": [{"source": "whatsapp", "label": "wa run"}],
        },
        {
            "key": "commerce.orders.count",
            "value": "not a number",
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
    ]

    issues = validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",)
    )

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_surface_metric", 1, "warning"),
        ("pii_class_disallowed", "unanswered_conversations", 2, "warning"),
        ("evidence_missing", "commerce.revenue.total", 3, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 4, "warning"),
        ("value_kind_mismatch", "commerce.orders.count", 5, "warning"),
    ]


def test_validate_surface_metric_objects_appends_money_currency_missing_after_value_kind():
    """The six-diagnostic composition inside
    :func:`validate_surface_metric_objects` must place money_currency_missing
    after value_kind_mismatch: structural and value-type diagnostics surface
    before the rendering-metadata diagnostic that money metrics must carry a
    currency string for surfaces (WhatsApp dispatch, owner brief) to render
    unambiguously. Each diagnostic preserves its own input-order index, and a
    single metric that is both value-kind invalid and missing currency must
    surface in both slots."""

    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_surface_metric", "tiendanube"),
        _metric("unanswered_conversations", "whatsapp", value=5),
        _metric("commerce.revenue.baseline", "google_sheets", value=80000),
        _metric("ad_spend_today", "meta_ads", value="invalid"),
    ]

    issues = validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",)
    )

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_surface_metric", 1, "warning"),
        ("pii_class_disallowed", "unanswered_conversations", 2, "warning"),
        ("value_kind_mismatch", "ad_spend_today", 4, "warning"),
        ("money_currency_missing", "commerce.revenue.baseline", 3, "warning"),
        ("money_currency_missing", "ad_spend_today", 4, "warning"),
    ]


def test_validate_surface_metric_objects_returns_empty_for_clean_surface_metrics():
    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("revenue_today", "mercadolibre", value=120000, unit="ARS"),
        _metric("stock_units", "tiendanube", value=42),
        _metric("ad_spend_today", "meta_ads", value=1500, unit="ARS"),
    ]

    assert (
        validate_surface_metric_objects(
            metrics, allowed_pii_classes=("none",)
        )
        == []
    )


def test_validate_surface_metric_objects_matches_key_path_when_no_object_violations():
    """When every metric object has in-envelope evidence sources and the value
    type matches the canonical unit kind, the object-level result must equal
    ``validate_surface_metric_keys`` over the same keys so callers can freely
    upgrade from keys to objects without a behavior change."""

    from app.brain.semantics.metric_registry import (
        validate_surface_metric_keys,
        validate_surface_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_surface_metric", "tiendanube"),
        _metric("unanswered_conversations", "whatsapp", value=5),
    ]
    keys = [metric.key for metric in metrics]

    assert validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",)
    ) == validate_surface_metric_keys(
        keys, allowed_pii_classes=("none",)
    )


def test_validate_surface_metric_objects_threads_custom_registry_into_all_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_surface_metric_objects,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="support.identity.email",
                family="support.identity",
                label="Owner identity email",
                unit="count",
                allowed_sources=("sample",),
                aliases=("owner_email_legacy",),
                aggregation="latest",
                case_allowed=False,
                report_allowed=False,
                pii_class="sensitive",
            ),
        )
    )

    metrics = [
        _metric("owner_email_legacy", "sample", value=1),
        _metric("revenue_today", "tiendanube", value=120000),
    ]

    issues = validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",), registry=registry
    )
    # revenue_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a sensitive pii_class.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "revenue_today", 1),
        ("pii_class_disallowed", "owner_email_legacy", 0),
    ]


def test_validate_surface_metric_objects_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_surface_metric", "tiendanube"),
        _metric("unanswered_conversations", "whatsapp", value=5),
        _metric("commerce.orders.count", "tiendanube", value="not a number"),
    ]

    first = validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",)
    )
    second = validate_surface_metric_objects(
        metrics, allowed_pii_classes=("none",)
    )
    assert first == second


def test_validate_surface_metric_objects_rejects_empty_allowed_pii_classes():
    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [_metric("orders_today", "tiendanube", value=12)]

    with pytest.raises(ValueError, match="allowed_pii_classes"):
        validate_surface_metric_objects(metrics, allowed_pii_classes=())


def test_validate_surface_metric_objects_rejects_unsupported_pii_class_in_allowed_set():
    from app.brain.semantics.metric_registry import validate_surface_metric_objects

    metrics = [_metric("orders_today", "tiendanube", value=12)]

    with pytest.raises(ValueError, match="pii_class"):
        validate_surface_metric_objects(
            metrics, allowed_pii_classes=("none", "ultra-secret")
        )


def test_validate_surface_metric_objects_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_surface_metric_objects")
    assert "validate_surface_metric_objects" in semantics.__all__


def test_freshness_companion_helper_flags_freshness_required_keys_without_runtime_freshness_companion():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    # Business metrics (freshness_required=True) without any runtime.freshness
    # companion metric in the same payload must be flagged once each, in
    # input order. commerce.average_order_value also defaults to
    # freshness_required=True so it surfaces alongside the other business keys.
    metric_keys = (
        "commerce.orders.count",
        "ad_spend_today",
        "avg_order_value",
    )

    issues = find_freshness_companion_violations(metric_keys)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("freshness_companion_missing", "commerce.orders.count", 0, "warning"),
        ("freshness_companion_missing", "ad_spend_today", 1, "warning"),
        ("freshness_companion_missing", "avg_order_value", 2, "warning"),
    ]
    assert "runtime.freshness" in issues[0].message
    assert "commerce.orders.count" in issues[0].message


def test_freshness_companion_helper_returns_empty_when_runtime_freshness_companion_present():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    # Any runtime.freshness family metric (canonical or alias-resolved) in the
    # payload satisfies the companion requirement and suppresses the diagnostic
    # for every freshness_required key, regardless of where it appears.
    assert (
        find_freshness_companion_violations(
            (
                "commerce.orders.count",
                "runtime.freshness.last_success_at",
                "ad_spend_today",
            )
        )
        == []
    )

    assert (
        find_freshness_companion_violations(
            (
                "commerce.orders.count",
                "runtime.freshness.age_seconds",
            )
        )
        == []
    )


def test_freshness_companion_helper_skips_metrics_whose_canonical_definition_does_not_require_freshness():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    # runtime.connector.status, runtime.data_quality.*, and the runtime.freshness
    # metrics themselves are freshness_required=False. A payload composed only of
    # such control-plane signals does not need a runtime.freshness companion to
    # pass.
    assert (
        find_freshness_companion_violations(
            (
                "runtime.connector.status",
                "runtime.data_quality.completeness_ratio",
            )
        )
        == []
    )


def test_freshness_companion_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    # Unknown keys are owned by validate_metrics; this helper intentionally
    # skips them so the diagnostics compose without overlap. With no resolvable
    # metrics in the payload, no freshness_required check can fire.
    assert (
        find_freshness_companion_violations(("never_registered_metric",))
        == []
    )


def test_freshness_companion_helper_resolves_aliases_before_checking_companion_and_freshness_required():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    # revenue_today is an alias for commerce.revenue.total (freshness_required=True);
    # the companion check must resolve aliases on both sides so the diagnostic is
    # symmetric with the rest of the registry.
    issues = find_freshness_companion_violations(("revenue_today",))
    assert [(issue.code, issue.key) for issue in issues] == [
        ("freshness_companion_missing", "revenue_today")
    ]
    assert "commerce.revenue.total" in issues[0].message


def test_freshness_companion_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    metric_keys = (
        "commerce.orders.count",
        "ad_spend_today",
        "custom.unknown_metric",
        "avg_order_value",
    )
    first = find_freshness_companion_violations(metric_keys)
    second = find_freshness_companion_violations(metric_keys)
    assert first == second


def test_freshness_companion_helper_threads_custom_registry_through_resolution():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        find_freshness_companion_violations,
    )

    # A custom registry whose only metric requires freshness but offers no
    # runtime.freshness family must surface the diagnostic regardless of the
    # default registry's contents.
    registry = MetricRegistry(
        (
            MetricDefinition(
                key="commerce.subscriptions.count",
                family="commerce.subscriptions",
                label="Active subscriptions",
                unit="count",
                allowed_sources=("sample",),
                aliases=("subscriptions_today",),
                aggregation="latest",
                case_allowed=True,
            ),
        )
    )

    issues = find_freshness_companion_violations(
        ("subscriptions_today",), registry=registry
    )
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("freshness_companion_missing", "subscriptions_today", 0),
    ]
    assert "commerce.subscriptions.count" in issues[0].message


def test_freshness_companion_helper_rejects_empty_or_non_string_metric_keys():
    from app.brain.semantics.metric_registry import find_freshness_companion_violations

    with pytest.raises(ValueError, match="metric keys"):
        find_freshness_companion_violations(("",))

    with pytest.raises(ValueError, match="metric keys"):
        find_freshness_companion_violations((123,))


def test_freshness_companion_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_freshness_companion_violations")
    assert "find_freshness_companion_violations" in semantics.__all__


def test_validate_freshness_envelope_metric_keys_composes_unknown_then_freshness_companion_missing():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_keys,
    )

    # Mixed bag: two canonical freshness_required keys, one unknown key, and no
    # runtime.freshness companion. The composition must report unknowns first
    # (owned by validate_metrics) then freshness_companion_missing (owned by
    # find_freshness_companion_violations). Each diagnostic preserves its own
    # input-order index.
    metric_keys = (
        "orders_today",
        "custom.unknown_freshness_metric",
        "ad_spend_today",
    )

    issues = validate_freshness_envelope_metric_keys(metric_keys)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_freshness_metric", 1, "warning"),
        ("freshness_companion_missing", "orders_today", 0, "warning"),
        ("freshness_companion_missing", "ad_spend_today", 2, "warning"),
    ]


def test_validate_freshness_envelope_metric_keys_returns_empty_when_companion_present():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_keys,
    )

    # When a runtime.freshness.* companion accompanies the freshness_required
    # business keys, freshness_companion_missing is suppressed for every key.
    assert (
        validate_freshness_envelope_metric_keys(
            (
                "orders_today",
                "revenue_today",
                "runtime.freshness.last_success_at",
            )
        )
        == []
    )


def test_validate_freshness_envelope_metric_keys_returns_empty_when_no_freshness_required_keys():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_keys,
    )

    # runtime.connector.status and runtime.data_quality.completeness_ratio are
    # registered but not freshness_required; with no freshness_required keys in
    # the payload there is nothing to companion.
    assert (
        validate_freshness_envelope_metric_keys(
            (
                "runtime.connector.status",
                "runtime.data_quality.completeness_ratio",
            )
        )
        == []
    )


def test_validate_freshness_envelope_metric_keys_threads_custom_registry_into_both_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_freshness_envelope_metric_keys,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="commerce.subscriptions.count",
                family="commerce.subscriptions",
                label="Active subscriptions",
                unit="count",
                allowed_sources=("sample",),
                aliases=("subscriptions_today",),
                aggregation="latest",
                case_allowed=True,
            ),
        )
    )

    issues = validate_freshness_envelope_metric_keys(
        ("subscriptions_today", "orders_today"), registry=registry
    )
    # orders_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a freshness_required canonical metric whose
    # companion runtime.freshness family is absent from the input.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "orders_today", 1),
        ("freshness_companion_missing", "subscriptions_today", 0),
    ]


def test_validate_freshness_envelope_metric_keys_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_keys,
    )

    metric_keys = (
        "orders_today",
        "custom.unknown_freshness_metric",
        "ad_spend_today",
        "avg_order_value",
    )
    first = validate_freshness_envelope_metric_keys(metric_keys)
    second = validate_freshness_envelope_metric_keys(metric_keys)
    assert first == second


def test_validate_freshness_envelope_metric_keys_rejects_empty_keys():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_keys,
    )

    with pytest.raises(ValueError):
        validate_freshness_envelope_metric_keys(("",))


def test_validate_freshness_envelope_metric_keys_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_freshness_envelope_metric_keys")
    assert "validate_freshness_envelope_metric_keys" in semantics.__all__


def test_validate_freshness_envelope_metric_objects_composes_unknown_then_freshness_then_evidence_source_then_value_kind():
    """Parallel to :func:`validate_freshness_envelope_metric_keys` but on the
    object side: the five-diagnostic composition must report unknown_metric
    first, then freshness_companion_missing, then evidence_source_mismatch,
    and finally value_kind_mismatch. Each diagnostic preserves its own
    input-order index. This case carries non-empty evidence on every metric so
    the evidence_missing slot is exercised by a separate dedicated test.
    """

    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_freshness_metric", "tiendanube"),
        _metric("ad_spend_today", "whatsapp", value=1500, unit="ARS"),
        _metric("commerce.orders.count", "tiendanube", value="not a number"),
    ]

    issues = validate_freshness_envelope_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_freshness_metric", 1, "warning"),
        ("freshness_companion_missing", "orders_today", 0, "warning"),
        ("freshness_companion_missing", "ad_spend_today", 2, "warning"),
        ("freshness_companion_missing", "commerce.orders.count", 3, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 2, "warning"),
        ("value_kind_mismatch", "commerce.orders.count", 3, "warning"),
    ]


def test_validate_freshness_envelope_metric_objects_slots_evidence_missing_between_freshness_and_evidence_source():
    """Mixed bag exercising the evidence_missing slot. The composition order
    inside :func:`validate_freshness_envelope_metric_objects` must put
    evidence_missing immediately after freshness_companion_missing and before
    evidence_source_mismatch so structural ``no evidence at all`` diagnostics
    surface before content diagnostics about wrong-source evidence. Each
    diagnostic preserves its own input-order index. Mapping form is required
    because Pydantic ``Metric`` enforces ``min_length=1`` on evidence and
    cannot represent the missing case directly."""

    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_objects,
    )

    metrics = [
        {
            "key": "orders_today",
            "value": 12,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {
            "key": "custom.unknown_freshness_metric",
            "value": 1,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
        {"key": "commerce.revenue.total", "value": 90000, "unit": "ARS", "evidence": []},
        {
            "key": "ad_spend_today",
            "value": 1500,
            "unit": "ARS",
            "evidence": [{"source": "whatsapp", "label": "wa run"}],
        },
        {
            "key": "commerce.orders.count",
            "value": "not a number",
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn run"}],
        },
    ]

    issues = validate_freshness_envelope_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_freshness_metric", 1, "warning"),
        ("freshness_companion_missing", "orders_today", 0, "warning"),
        ("freshness_companion_missing", "commerce.revenue.total", 2, "warning"),
        ("freshness_companion_missing", "ad_spend_today", 3, "warning"),
        ("freshness_companion_missing", "commerce.orders.count", 4, "warning"),
        ("evidence_missing", "commerce.revenue.total", 2, "warning"),
        ("evidence_source_mismatch", "ad_spend_today", 3, "warning"),
        ("value_kind_mismatch", "commerce.orders.count", 4, "warning"),
    ]


def test_validate_freshness_envelope_metric_objects_appends_money_currency_missing_after_value_kind():
    """The six-diagnostic composition inside
    :func:`validate_freshness_envelope_metric_objects` must place
    money_currency_missing after value_kind_mismatch: structural, freshness, and
    value-type diagnostics surface before the rendering-metadata diagnostic that
    money metrics must carry a currency string for the runtime/control-plane to
    interpret values unambiguously. Each diagnostic preserves its own
    input-order index, and a single metric that is both value-kind invalid and
    missing currency must surface in both slots."""

    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_freshness_metric", "tiendanube"),
        _metric("commerce.revenue.baseline", "google_sheets", value=80000),
        _metric("ad_spend_today", "meta_ads", value="invalid"),
    ]

    issues = validate_freshness_envelope_metric_objects(metrics)

    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in issues] == [
        ("unknown_metric", "custom.unknown_freshness_metric", 1, "warning"),
        ("freshness_companion_missing", "orders_today", 0, "warning"),
        ("freshness_companion_missing", "commerce.revenue.baseline", 2, "warning"),
        ("freshness_companion_missing", "ad_spend_today", 3, "warning"),
        ("value_kind_mismatch", "ad_spend_today", 3, "warning"),
        ("money_currency_missing", "commerce.revenue.baseline", 2, "warning"),
        ("money_currency_missing", "ad_spend_today", 3, "warning"),
    ]


def test_validate_freshness_envelope_metric_objects_returns_empty_when_companion_present_and_all_clean():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("revenue_today", "mercadolibre", value=120000, unit="ARS"),
        _metric(
            "runtime.freshness.last_success_at",
            "tiendanube",
            value="2026-05-30T00:00:00+00:00",
        ),
    ]

    assert validate_freshness_envelope_metric_objects(metrics) == []


def test_validate_freshness_envelope_metric_objects_matches_key_path_when_no_object_violations():
    """When every metric object has in-envelope evidence sources and the value
    type matches the canonical unit kind, the object-level result must equal
    ``validate_freshness_envelope_metric_keys`` over the same keys so callers
    can freely upgrade from keys to objects without a behavior change."""

    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_keys,
        validate_freshness_envelope_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_freshness_metric", "tiendanube"),
        _metric("ad_spend_today", "meta_ads", value=1500, unit="ARS"),
    ]
    keys = [metric.key for metric in metrics]

    assert validate_freshness_envelope_metric_objects(
        metrics
    ) == validate_freshness_envelope_metric_keys(keys)


def test_validate_freshness_envelope_metric_objects_threads_custom_registry_into_all_diagnostics():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        validate_freshness_envelope_metric_objects,
    )

    registry = MetricRegistry(
        (
            MetricDefinition(
                key="commerce.subscriptions.count",
                family="commerce.subscriptions",
                label="Active subscriptions",
                unit="count",
                allowed_sources=("sample",),
                aliases=("subscriptions_today",),
                aggregation="latest",
                case_allowed=True,
            ),
        )
    )

    metrics = [
        _metric("subscriptions_today", "sample", value=42),
        _metric("orders_today", "tiendanube", value=12),
    ]

    issues = validate_freshness_envelope_metric_objects(metrics, registry=registry)
    # orders_today is unknown under the custom registry; the alias on the
    # custom registry resolves to a freshness_required canonical metric whose
    # companion runtime.freshness family is absent from the input.
    assert [(issue.code, issue.key, issue.index) for issue in issues] == [
        ("unknown_metric", "orders_today", 1),
        ("freshness_companion_missing", "subscriptions_today", 0),
    ]


def test_validate_freshness_envelope_metric_objects_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import (
        validate_freshness_envelope_metric_objects,
    )

    metrics = [
        _metric("orders_today", "tiendanube", value=12),
        _metric("custom.unknown_freshness_metric", "tiendanube"),
        _metric("ad_spend_today", "whatsapp", value=1500),
        _metric("commerce.orders.count", "tiendanube", value="not a number"),
    ]

    first = validate_freshness_envelope_metric_objects(metrics)
    second = validate_freshness_envelope_metric_objects(metrics)
    assert first == second


def test_validate_freshness_envelope_metric_objects_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "validate_freshness_envelope_metric_objects")
    assert "validate_freshness_envelope_metric_objects" in semantics.__all__


def test_money_currency_helper_flags_money_metric_missing_currency_context():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    # commerce.revenue.total has canonical unit="money"; runtime metric objects
    # must carry a non-empty unit (currency code) so reports can render the
    # value with currency context. A missing unit must be reported.
    metrics = [
        Metric(
            key="commerce.orders.count",
            label="Orders",
            value=12,
            evidence=[_evidence()],
        ),
        Metric(
            key="commerce.revenue.total",
            label="Revenue",
            value=120000,
            unit=None,
            evidence=[_evidence()],
        ),
    ]

    violations = find_money_currency_violations(metrics)
    assert [(issue.code, issue.key, issue.index, issue.severity) for issue in violations] == [
        ("money_currency_missing", "commerce.revenue.total", 1, "warning"),
    ]
    assert "commerce.revenue.total" in violations[0].message
    assert "money" in violations[0].message


def test_money_currency_helper_resolves_aliases_before_checking_unit_kind():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    # revenue_today is an alias for commerce.revenue.total (unit="money"); the
    # diagnostic must resolve the alias and surface the canonical key in the
    # message.
    metrics = [
        Metric(
            key="revenue_today",
            label="Ventas",
            value=90000,
            unit=None,
            evidence=[_evidence()],
        ),
    ]
    violations = find_money_currency_violations(metrics)
    assert len(violations) == 1
    assert violations[0].key == "revenue_today"
    assert "commerce.revenue.total" in violations[0].message


def test_money_currency_helper_returns_empty_when_money_metrics_carry_currency():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    metrics = [
        Metric(
            key="commerce.revenue.total",
            label="Revenue",
            value=120000,
            unit="ARS",
            evidence=[_evidence()],
        ),
        Metric(
            key="ad_spend_today",
            label="Spend",
            value=1500,
            unit="USD",
            evidence=[_evidence("meta_ads")],
        ),
    ]
    assert find_money_currency_violations(metrics) == []


def test_money_currency_helper_skips_non_money_metrics():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    # commerce.orders.count (unit="count") and runtime.freshness.age_seconds
    # (unit="duration") have non-money unit kinds; their unit field is
    # irrelevant to the money-currency check and must never be flagged.
    metrics = [
        Metric(
            key="commerce.orders.count",
            label="Orders",
            value=12,
            unit=None,
            evidence=[_evidence()],
        ),
        Metric(
            key="runtime.freshness.age_seconds",
            label="Freshness",
            value=300,
            unit=None,
            evidence=[_evidence()],
        ),
    ]
    assert find_money_currency_violations(metrics) == []


def test_money_currency_helper_skips_unknown_keys_so_diagnostics_compose():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    metrics = [
        {
            "key": "never_registered_metric",
            "value": 1000,
            "unit": None,
            "evidence": [{"source": "sample", "label": "s"}],
        },
    ]
    assert find_money_currency_violations(metrics) == []


def test_money_currency_helper_treats_empty_string_unit_as_missing():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    # An empty-string unit is semantically the same as no currency context for
    # a money metric; both must produce a diagnostic.
    metrics = [
        {
            "key": "commerce.revenue.total",
            "value": 120000,
            "unit": "",
            "evidence": [{"source": "tiendanube", "label": "tn"}],
        },
        {
            "key": "commerce.revenue.total",
            "value": 120000,
            "unit": "   ",
            "evidence": [{"source": "tiendanube", "label": "tn"}],
        },
    ]
    violations = find_money_currency_violations(metrics)
    assert [(issue.code, issue.index) for issue in violations] == [
        ("money_currency_missing", 0),
        ("money_currency_missing", 1),
    ]


def test_money_currency_helper_rejects_non_string_unit():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    # A non-string unit on a money metric is a contract violation the helper
    # must surface explicitly rather than silently coercing.
    metrics = [
        {
            "key": "commerce.revenue.total",
            "value": 120000,
            "unit": 123,
            "evidence": [{"source": "tiendanube", "label": "tn"}],
        },
    ]
    with pytest.raises(ValueError, match="unit"):
        find_money_currency_violations(metrics)


def test_money_currency_helper_is_deterministic_across_runs():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    metrics = [
        {
            "key": "commerce.revenue.total",
            "value": 120000,
            "unit": None,
            "evidence": [{"source": "tiendanube", "label": "tn"}],
        },
        {
            "key": "ad_spend_today",
            "value": 1500,
            "unit": None,
            "evidence": [{"source": "meta_ads", "label": "ma"}],
        },
    ]
    first = find_money_currency_violations(metrics)
    second = find_money_currency_violations(metrics)
    assert first == second
    assert [issue.key for issue in first] == [
        "commerce.revenue.total",
        "ad_spend_today",
    ]


def test_money_currency_helper_rejects_metrics_missing_key_field():
    from app.brain.semantics.metric_registry import find_money_currency_violations

    with pytest.raises(ValueError, match="key"):
        find_money_currency_violations(
            [{"label": "no key", "value": 1, "unit": "ARS", "evidence": []}]
        )


def test_money_currency_helper_threads_custom_registry_into_alias_resolution():
    from app.brain.semantics.metric_registry import (
        MetricDefinition,
        MetricRegistry,
        find_money_currency_violations,
    )

    # A custom registry can declare new money metrics; the helper must use the
    # passed registry rather than the process-wide default for resolution.
    registry = MetricRegistry(
        (
            MetricDefinition(
                key="custom.margin.total",
                family="custom.margin",
                label="Margin",
                unit="money",
                allowed_sources=("sample",),
                aliases=("margin_today",),
                aggregation="sum",
                case_allowed=False,
                report_allowed=True,
            ),
        )
    )

    metrics = [
        {"key": "custom.margin.total", "value": 5000, "unit": None, "evidence": []},
        {"key": "margin_today", "value": 4000, "unit": "ARS", "evidence": []},
    ]
    violations = find_money_currency_violations(metrics, registry=registry)
    assert [(issue.code, issue.key, issue.index) for issue in violations] == [
        ("money_currency_missing", "custom.margin.total", 0),
    ]


def test_money_currency_helper_is_reexported_from_semantics_public_surface():
    from app.brain import semantics

    assert hasattr(semantics, "find_money_currency_violations")
    assert "find_money_currency_violations" in semantics.__all__
