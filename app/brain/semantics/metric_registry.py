"""Semantic metric registry foundation for D2C control-plane contracts.

This module is intentionally standalone. It defines the canonical semantic keys
used by reports, future deterministic detections, Operational Cases, and
operator surfaces without changing existing adapters or report rendering paths.
Legacy/current adapter keys are resolved through explicit aliases only.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping

_METRIC_UNITS = {"count", "money", "percent", "duration", "boolean", "timestamp"}
_AGGREGATIONS = {"sum", "latest", "average", "min", "max", "ratio", "none"}
_PII_CLASSES = {"none", "low", "sensitive"}


class UnknownMetricError(ValueError):
    """Raised when strict semantic metric validation sees an unknown key."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Metric key '{key}' is not registered in the semantic metric registry")


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Semantic definition for one canonical metric key."""

    key: str
    family: str
    label: str
    unit: str
    allowed_sources: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    aggregation: str = "none"
    freshness_required: bool = True
    report_allowed: bool = True
    case_allowed: bool = False
    evidence_required: bool = True
    pii_class: str = "none"

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("MetricDefinition.key must not be empty")
        if not self.family:
            raise ValueError(f"MetricDefinition {self.key} must include a family")
        if not self.label:
            raise ValueError(f"MetricDefinition {self.key} must include a label")
        if self.unit not in _METRIC_UNITS:
            raise ValueError(f"MetricDefinition {self.key} has unsupported unit {self.unit!r}")
        if self.aggregation not in _AGGREGATIONS:
            raise ValueError(f"MetricDefinition {self.key} has unsupported aggregation {self.aggregation!r}")
        if self.pii_class not in _PII_CLASSES:
            raise ValueError(f"MetricDefinition {self.key} has unsupported pii_class {self.pii_class!r}")
        if not self.allowed_sources:
            raise ValueError(f"MetricDefinition {self.key} must include at least one allowed source")

        object.__setattr__(self, "allowed_sources", tuple(self.allowed_sources))
        object.__setattr__(self, "aliases", tuple(self.aliases))


@dataclass(frozen=True, slots=True)
class MetricValidationIssue:
    """Deterministic advisory diagnostic for semantic metric validation."""

    code: str
    key: str
    message: str
    severity: str = "warning"
    index: int | None = None


class MetricRegistry:
    """Canonical metric definition registry with deterministic alias resolution."""

    def __init__(self, definitions: Iterable[MetricDefinition]) -> None:
        by_key: dict[str, MetricDefinition] = {}
        definitions_tuple = tuple(definitions)
        for definition in definitions_tuple:
            if definition.key in by_key:
                raise ValueError(f"Metric key '{definition.key}' is already registered")
            by_key[definition.key] = definition

        alias_to_key: dict[str, str] = {}
        canonical_keys = set(by_key)
        for definition in definitions_tuple:
            seen_aliases: set[str] = set()
            for alias in definition.aliases:
                if not alias:
                    raise ValueError(f"MetricDefinition {definition.key} includes an empty alias")
                if alias in seen_aliases:
                    raise ValueError(f"Alias '{alias}' is duplicated on metric {definition.key}")
                seen_aliases.add(alias)
                if alias in canonical_keys:
                    raise ValueError(
                        f"Alias '{alias}' on metric {definition.key} cannot shadow a canonical metric key"
                    )
                previous = alias_to_key.get(alias)
                if previous is not None and previous != definition.key:
                    raise ValueError(
                        f"Alias '{alias}' is already registered for canonical metric {previous}"
                    )
                alias_to_key[alias] = definition.key

        self._definitions = tuple(sorted(definitions_tuple, key=lambda definition: definition.key))
        self._by_key = MappingProxyType(dict(sorted(by_key.items())))
        self._alias_to_key = MappingProxyType(dict(sorted(alias_to_key.items())))

    def definitions(self) -> tuple[MetricDefinition, ...]:
        """Return canonical metric definitions sorted by key."""

        return self._definitions

    def as_mapping(self) -> Mapping[str, MetricDefinition]:
        """Read-only mapping of canonical key to metric definition."""

        return self._by_key

    def aliases(self) -> Mapping[str, str]:
        """Read-only mapping of registered alias to canonical key."""

        return self._alias_to_key

    def has(self, key: str) -> bool:
        """Return true when ``key`` is either canonical or a registered alias."""

        return key in self._by_key or key in self._alias_to_key

    def resolve_key(self, key: str) -> str:
        """Resolve a canonical key or alias to its canonical key.

        Canonical keys resolve to themselves. Unknown keys raise
        ``UnknownMetricError`` so strict callers get a clear, typed failure.
        """

        if key in self._by_key:
            return key
        try:
            return self._alias_to_key[key]
        except KeyError as exc:
            raise UnknownMetricError(key) from exc

    def try_resolve_key(self, key: str) -> str | None:
        """Resolve a key if registered, returning ``None`` instead of raising."""

        if key in self._by_key:
            return key
        return self._alias_to_key.get(key)

    def get(self, key: str) -> MetricDefinition:
        """Return the canonical metric definition for a key or alias."""

        return self._by_key[self.resolve_key(key)]


# Initial D2C case-family contract from docs/specs/metric-registry-contract.md.
CASE_FAMILY_METRICS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "sales_drop": (
            "commerce.orders.count",
            "commerce.revenue.total",
            "runtime.freshness.age_seconds",
        ),
        "stockout_risk": (
            "commerce.inventory.available_units",
            "commerce.orders.count",
            "runtime.freshness.age_seconds",
        ),
        "data_stale": (
            "runtime.freshness.last_success_at",
            "runtime.freshness.age_seconds",
            "runtime.connector.status",
        ),
        "fulfillment_backlog": (
            "commerce.fulfillment.pending_count",
            "commerce.fulfillment.oldest_pending_age_hours",
        ),
        "unanswered_conversations": (
            "support.conversations.unanswered_count",
            "support.conversations.oldest_unanswered_age_minutes",
        ),
        "spend_without_orders": (
            "ads.spend.total",
            "commerce.orders.count",
            "commerce.revenue.total",
            "runtime.freshness.last_success_at",
            "runtime.freshness.age_seconds",
        ),
    }
)

# Connector registry compatibility for families that are transitional envelopes
# rather than direct semantic metric families. ``manual.payload`` can emit legacy
# sample keys which are resolved by aliases into canonical families.
CONNECTOR_FAMILY_COMPATIBILITY: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "manual.payload": (
            "commerce.orders",
            "commerce.revenue",
            "commerce.inventory",
            "support.conversations",
            "ads.spend",
        ),
    }
)


def _definition(
    *,
    key: str,
    family: str,
    label: str,
    unit: str,
    allowed_sources: tuple[str, ...],
    aliases: tuple[str, ...] = (),
    aggregation: str,
    case_allowed: bool,
    report_allowed: bool = True,
    freshness_required: bool = True,
    evidence_required: bool = True,
    pii_class: str = "none",
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        family=family,
        label=label,
        unit=unit,
        allowed_sources=allowed_sources,
        aliases=aliases,
        aggregation=aggregation,
        freshness_required=freshness_required,
        report_allowed=report_allowed,
        case_allowed=case_allowed,
        evidence_required=evidence_required,
        pii_class=pii_class,
    )


DEFAULT_METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    _definition(
        key="commerce.orders.count",
        family="commerce.orders",
        label="Orders",
        unit="count",
        allowed_sources=("csv", "google_sheets", "mercadolibre", "sample", "tiendanube"),
        aliases=("orders_today", "commerce.orders.today", "orders_today_tn", "orders_today_ml"),
        aggregation="sum",
        case_allowed=True,
    ),
    _definition(
        key="commerce.revenue.total",
        family="commerce.revenue",
        label="Revenue",
        unit="money",
        allowed_sources=("csv", "google_sheets", "mercadolibre", "sample", "tiendanube"),
        aliases=(
            "revenue_today",
            "commerce.revenue.today",
            "mercadolibre.revenue_today",
            "tiendanube.revenue_today",
            "ml_revenue_today",
            "tn_revenue_today",
            "revenue_today_ml",
            "revenue_today_tn",
        ),
        aggregation="sum",
        case_allowed=True,
    ),
    _definition(
        key="commerce.revenue.baseline",
        family="commerce.revenue",
        label="Revenue baseline",
        unit="money",
        allowed_sources=("csv", "google_sheets", "sample"),
        aliases=("revenue_baseline",),
        aggregation="average",
        case_allowed=True,
    ),
    _definition(
        key="commerce.inventory.available_units",
        family="commerce.inventory",
        label="Available inventory units",
        unit="count",
        allowed_sources=("csv", "google_sheets", "sample", "tiendanube"),
        aliases=("stock_units", "commerce.inventory.stock_units"),
        aggregation="latest",
        case_allowed=True,
    ),
    _definition(
        key="commerce.fulfillment.pending_count",
        family="commerce.fulfillment",
        label="Pending fulfillment orders",
        unit="count",
        allowed_sources=("tiendanube", "mercadolibre"),
        aggregation="latest",
        case_allowed=True,
    ),
    _definition(
        key="commerce.fulfillment.oldest_pending_age_hours",
        family="commerce.fulfillment",
        label="Oldest pending fulfillment age",
        unit="duration",
        allowed_sources=("tiendanube", "mercadolibre"),
        aggregation="max",
        case_allowed=True,
    ),
    _definition(
        key="commerce.average_order_value",
        family="commerce.average_order_value",
        label="Average order value",
        unit="money",
        allowed_sources=("mercadolibre", "sample", "tiendanube"),
        aliases=("avg_order_value",),
        aggregation="average",
        case_allowed=False,
    ),
    _definition(
        key="support.conversations.unanswered_count",
        family="support.conversations",
        label="Unanswered conversations",
        unit="count",
        allowed_sources=("google_sheets", "sample", "whatsapp"),
        aliases=("unanswered_conversations",),
        aggregation="latest",
        case_allowed=True,
        pii_class="low",
    ),
    _definition(
        key="support.conversations.oldest_unanswered_age_minutes",
        family="support.conversations",
        label="Oldest unanswered conversation age",
        unit="duration",
        allowed_sources=("whatsapp",),
        aggregation="max",
        case_allowed=True,
        pii_class="low",
    ),
    _definition(
        key="runtime.freshness.last_success_at",
        family="runtime.freshness",
        label="Last successful sync time",
        unit="timestamp",
        allowed_sources=("csv", "google_sheets", "mercadolibre", "meta_ads", "sample", "tiendanube"),
        aggregation="latest",
        case_allowed=True,
        freshness_required=False,
        report_allowed=False,
    ),
    _definition(
        key="runtime.freshness.age_seconds",
        family="runtime.freshness",
        label="Source freshness age",
        unit="duration",
        allowed_sources=("csv", "google_sheets", "mercadolibre", "meta_ads", "sample", "tiendanube"),
        aggregation="max",
        case_allowed=True,
        freshness_required=False,
        report_allowed=False,
    ),
    _definition(
        key="runtime.data_quality.completeness_ratio",
        family="runtime.data_quality",
        label="Data completeness ratio",
        unit="percent",
        allowed_sources=("csv", "google_sheets", "mercadolibre", "meta_ads", "sample", "tiendanube"),
        aggregation="ratio",
        case_allowed=False,
        freshness_required=False,
        report_allowed=False,
    ),
    _definition(
        key="runtime.connector.status",
        family="runtime.connector",
        label="Connector status",
        unit="boolean",
        allowed_sources=("csv", "google_sheets", "mercadolibre", "meta_ads", "sample", "tiendanube"),
        aggregation="latest",
        case_allowed=True,
        freshness_required=False,
        report_allowed=False,
    ),
    _definition(
        key="ads.spend.total",
        family="ads.spend",
        label="Ad spend",
        unit="money",
        allowed_sources=("google_sheets", "meta_ads", "sample"),
        aliases=("ad_spend_today",),
        aggregation="sum",
        case_allowed=True,
    ),
    _definition(
        key="ads.delivery.impressions",
        family="ads.delivery",
        label="Ad impressions",
        unit="count",
        allowed_sources=("meta_ads",),
        aliases=("ad_impressions_today",),
        aggregation="sum",
        case_allowed=False,
    ),
    _definition(
        key="ads.delivery.clicks",
        family="ads.delivery",
        label="Ad clicks",
        unit="count",
        allowed_sources=("meta_ads",),
        aliases=("ad_clicks_today",),
        aggregation="sum",
        case_allowed=False,
    ),
    _definition(
        key="ads.roas.estimated",
        family="ads.roas",
        label="Estimated ROAS",
        unit="percent",
        allowed_sources=("meta_ads",),
        aliases=("ad_roas_today",),
        aggregation="ratio",
        case_allowed=False,
    ),
)

_DEFAULT_METRIC_REGISTRY = MetricRegistry(DEFAULT_METRIC_DEFINITIONS)


def default_metric_registry() -> MetricRegistry:
    """Return the process-wide default semantic metric registry."""

    return _DEFAULT_METRIC_REGISTRY


def _metric_key(metric: Any) -> str:
    if isinstance(metric, Mapping):
        key = metric.get("key")
    else:
        key = getattr(metric, "key", None)
    if not isinstance(key, str) or not key:
        raise ValueError("Metrics passed to semantic validation must expose a non-empty string key")
    return key


def _metric_value(metric: Any) -> Any:
    if isinstance(metric, Mapping):
        if "value" not in metric:
            raise ValueError(
                "Metrics passed to value-kind validation must expose a value field"
            )
        return metric.get("value")
    if not hasattr(metric, "value"):
        raise ValueError(
            "Metrics passed to value-kind validation must expose a value field"
        )
    return getattr(metric, "value")


_NUMERIC_UNIT_KINDS = frozenset({"money", "count", "percent", "duration"})


def _value_matches_unit_kind(value: Any, unit_kind: str) -> bool:
    if unit_kind == "boolean":
        return isinstance(value, bool)
    if unit_kind == "timestamp":
        return isinstance(value, str)
    if unit_kind in _NUMERIC_UNIT_KINDS:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    # Unknown unit kinds should never reach here because MetricDefinition
    # validates ``unit`` against ``_METRIC_UNITS``; treat as opaque rather than
    # raising so the diagnostic remains advisory and never crashes a run.
    return True


def _metric_evidence_sources(metric: Any) -> tuple[str, ...]:
    if isinstance(metric, Mapping):
        if "evidence" not in metric:
            raise ValueError(
                "Metrics passed to evidence-source validation must expose an evidence collection"
            )
        evidence = metric.get("evidence")
    else:
        if not hasattr(metric, "evidence"):
            raise ValueError(
                "Metrics passed to evidence-source validation must expose an evidence collection"
            )
        evidence = getattr(metric, "evidence")
    sources: list[str] = []
    for item in evidence or ():
        if isinstance(item, Mapping):
            source = item.get("source")
        else:
            source = getattr(item, "source", None)
        if not isinstance(source, str) or not source:
            raise ValueError(
                "Evidence entries passed to evidence-source validation must expose a non-empty string source"
            )
        sources.append(source)
    return tuple(sources)


def find_source_envelope_violations(
    metric_keys: Iterable[str],
    *,
    connector_type: str,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric keys emitted by an unauthorized source.

    A "source envelope" violation means a metric key resolved to a canonical
    definition whose ``allowed_sources`` does not include ``connector_type``.
    Unknown (unresolved) keys are intentionally skipped so this diagnostic
    composes cleanly with :func:`validate_metrics`, which already pins unknown
    keys. Result order matches input order and is deterministic.
    """

    if not connector_type:
        raise ValueError("find_source_envelope_violations requires a non-empty connector_type")

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, key in enumerate(metric_keys):
        if not isinstance(key, str) or not key:
            raise ValueError(
                "find_source_envelope_violations requires non-empty string metric keys"
            )
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if connector_type in definition.allowed_sources:
            continue
        issues.append(
            MetricValidationIssue(
                code="disallowed_source",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') is not allowed "
                    f"from connector source '{connector_type}'; allowed_sources="
                    f"{list(definition.allowed_sources)}"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def find_family_envelope_violations(
    metric_keys: Iterable[str],
    *,
    connector_type: str,
    declared_families: Iterable[str],
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric keys whose canonical family is
    not in the connector spec's declared ``emitted_metric_families``.

    The caller passes ``declared_families`` (typically a connector spec's
    ``emitted_metric_families``) so this helper stays independent of the
    connector registry. Unknown (unresolved) keys are intentionally skipped so
    this diagnostic composes cleanly with :func:`validate_metrics` (unknown
    keys) and :func:`find_source_envelope_violations` (disallowed sources).
    Result order matches input order and is deterministic.
    """

    if not connector_type:
        raise ValueError("find_family_envelope_violations requires a non-empty connector_type")

    declared = tuple(declared_families)
    if not declared:
        raise ValueError(
            "find_family_envelope_violations requires non-empty declared_families"
        )
    declared_set = set(declared)

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, key in enumerate(metric_keys):
        if not isinstance(key, str) or not key:
            raise ValueError(
                "find_family_envelope_violations requires non-empty string metric keys"
            )
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        family = active_registry.get(canonical).family
        if family in declared_set:
            continue
        issues.append(
            MetricValidationIssue(
                code="undeclared_family",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has family "
                    f"'{family}' which is not declared in connector "
                    f"'{connector_type}' emitted_metric_families="
                    f"{list(declared)}"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def find_evidence_source_violations(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for evidence sources outside the canonical
    metric's ``allowed_sources``.

    Each metric must expose a non-empty string ``key`` and a non-``None``
    ``evidence`` collection whose entries expose a non-empty string ``source``.
    Unknown (unresolved) keys are intentionally skipped so this diagnostic
    composes with :func:`validate_metrics` (unknown keys),
    :func:`find_source_envelope_violations` (connector_type), and
    :func:`find_family_envelope_violations` (declared families). Within one
    metric, each disallowed source is reported at most once and in
    first-appearance order; across metrics, results follow input order.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, metric in enumerate(metrics):
        key = _metric_key(metric)
        sources = _metric_evidence_sources(metric)
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        allowed = definition.allowed_sources
        seen: set[str] = set()
        for source in sources:
            if source in allowed or source in seen:
                continue
            seen.add(source)
            issues.append(
                MetricValidationIssue(
                    code="evidence_source_mismatch",
                    key=key,
                    message=(
                        f"Metric key '{key}' (canonical '{canonical}') received "
                        f"evidence src={source}; allowed_sources="
                        f"{list(allowed)}"
                    ),
                    severity="warning",
                    index=index,
                )
            )
    return issues


def find_value_kind_violations(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric values whose runtime type does
    not match the canonical metric's unit kind.

    Numeric unit kinds (``money``, ``count``, ``percent``, ``duration``) require
    ``int`` or ``float`` (and reject ``bool``, even though ``bool`` is a subclass
    of ``int`` in Python). ``boolean`` requires ``bool``. ``timestamp`` requires
    ``str``. Each metric must expose a non-empty string ``key`` and a ``value``
    attribute (or mapping field). Unknown (unresolved) keys are intentionally
    skipped so this diagnostic composes cleanly with :func:`validate_metrics`,
    :func:`find_source_envelope_violations`, :func:`find_family_envelope_violations`,
    and :func:`find_evidence_source_violations`. Result order matches input
    order and is deterministic.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, metric in enumerate(metrics):
        key = _metric_key(metric)
        value = _metric_value(metric)
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if _value_matches_unit_kind(value, definition.unit):
            continue
        issues.append(
            MetricValidationIssue(
                code="value_kind_mismatch",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') expects unit "
                    f"kind '{definition.unit}' but received value of type "
                    f"{type(value).__name__}"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def find_report_allowed_violations(
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric keys whose canonical definition
    is not allowed in user-facing report output.

    A ``report_not_allowed`` violation means a metric key resolved to a canonical
    definition whose ``report_allowed`` flag is ``False`` (control-plane signals
    such as ``runtime.freshness.*`` or ``runtime.connector.status``). Unknown
    (unresolved) keys are intentionally skipped so this diagnostic composes
    cleanly with :func:`validate_metrics` and the envelope helpers. Result order
    matches input order and is deterministic.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, key in enumerate(metric_keys):
        if not isinstance(key, str) or not key:
            raise ValueError(
                "find_report_allowed_violations requires non-empty string metric keys"
            )
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if definition.report_allowed:
            continue
        issues.append(
            MetricValidationIssue(
                code="report_not_allowed",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has "
                    f"report_allowed=False and must not appear in user-facing "
                    f"report output"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def validate_metrics(
    metrics: Iterable[Any],
    *,
    strict: bool = False,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Validate metric keys against the semantic registry.

    Advisory mode (the default) returns deterministic diagnostics for unknown
    metric keys and never mutates the input metric objects. Strict mode raises
    ``UnknownMetricError`` on the first unknown key.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, metric in enumerate(metrics):
        key = _metric_key(metric)
        if active_registry.try_resolve_key(key) is not None:
            continue
        if strict:
            raise UnknownMetricError(key)
        issues.append(
            MetricValidationIssue(
                code="unknown_metric",
                key=key,
                message=f"Metric key '{key}' is not registered in the semantic metric registry",
                severity="warning",
                index=index,
            )
        )
    return issues


__all__ = [
    "CASE_FAMILY_METRICS",
    "CONNECTOR_FAMILY_COMPATIBILITY",
    "DEFAULT_METRIC_DEFINITIONS",
    "MetricDefinition",
    "MetricRegistry",
    "MetricValidationIssue",
    "UnknownMetricError",
    "default_metric_registry",
    "find_evidence_source_violations",
    "find_family_envelope_violations",
    "find_report_allowed_violations",
    "find_source_envelope_violations",
    "find_value_kind_violations",
    "validate_metrics",
]
