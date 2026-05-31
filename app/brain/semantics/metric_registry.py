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


def _metric_evidence_count(metric: Any) -> int:
    if isinstance(metric, Mapping):
        if "evidence" not in metric:
            raise ValueError(
                "Metrics passed to evidence-required validation must expose an evidence collection"
            )
        evidence = metric.get("evidence")
    else:
        if not hasattr(metric, "evidence"):
            raise ValueError(
                "Metrics passed to evidence-required validation must expose an evidence collection"
            )
        evidence = getattr(metric, "evidence")
    if evidence is None:
        return 0
    return sum(1 for _ in evidence)


def find_evidence_required_violations(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric objects whose canonical
    definition requires evidence but whose evidence collection is empty.

    An ``evidence_missing`` violation means a metric key resolved to a canonical
    definition whose ``evidence_required`` flag is ``True`` but the runtime
    object exposed zero evidence entries. ``None`` and empty iterables are
    treated the same so transitional draft envelopes do not crash the sweep.
    Each metric must expose a non-empty string ``key`` and an ``evidence``
    attribute (or mapping field); a missing field raises ``ValueError``.
    Unknown (unresolved) keys are intentionally skipped so this diagnostic
    composes cleanly with :func:`validate_metrics` and the existing envelope
    helpers. Result order matches input order and is deterministic.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, metric in enumerate(metrics):
        key = _metric_key(metric)
        count = _metric_evidence_count(metric)
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if not definition.evidence_required:
            continue
        if count > 0:
            continue
        issues.append(
            MetricValidationIssue(
                code="evidence_missing",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has "
                    f"evidence_required=True but received zero evidence "
                    f"entries"
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


def find_pii_class_violations(
    metric_keys: Iterable[str],
    *,
    allowed_pii_classes: Iterable[str],
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric keys whose canonical ``pii_class``
    is not in the surface's ``allowed_pii_classes`` set.

    A ``pii_class_disallowed`` violation means a metric key resolved to a
    canonical definition whose ``pii_class`` is not declared as allowed for the
    target surface (for example, a report or operator view that only accepts
    ``pii_class="none"`` metrics). ``allowed_pii_classes`` is validated against
    :data:`_PII_CLASSES` so caller typos surface as ``ValueError`` rather than
    silently passing. Unknown (unresolved) keys are intentionally skipped so
    this diagnostic composes cleanly with :func:`validate_metrics` and the
    other envelope helpers. Result order matches input order and is
    deterministic.
    """

    allowed = tuple(allowed_pii_classes)
    if not allowed:
        raise ValueError(
            "find_pii_class_violations requires non-empty allowed_pii_classes"
        )
    allowed_set: set[str] = set()
    for value in allowed:
        if not isinstance(value, str) or not value:
            raise ValueError(
                "find_pii_class_violations requires non-empty string allowed_pii_classes entries"
            )
        if value not in _PII_CLASSES:
            raise ValueError(
                f"find_pii_class_violations received unsupported pii_class {value!r}; "
                f"allowed values are {sorted(_PII_CLASSES)}"
            )
        allowed_set.add(value)

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, key in enumerate(metric_keys):
        if not isinstance(key, str) or not key:
            raise ValueError(
                "find_pii_class_violations requires non-empty string metric keys"
            )
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if definition.pii_class in allowed_set:
            continue
        issues.append(
            MetricValidationIssue(
                code="pii_class_disallowed",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has "
                    f"pii_class '{definition.pii_class}' which is not in the "
                    f"surface's allowed_pii_classes={list(allowed)}"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def _metric_unit(metric: Any) -> Any:
    """Return the runtime currency/unit string a metric exposes.

    The runtime ``Metric`` model carries an optional ``unit`` (currency code or
    label) that is distinct from ``MetricDefinition.unit`` (the canonical unit
    kind). Money diagnostics inspect this field, so missing access must raise
    explicitly instead of silently treating absence as ``None``.
    """

    if isinstance(metric, Mapping):
        if "unit" not in metric:
            raise ValueError(
                "Metrics passed to money-currency validation must expose a unit field"
            )
        return metric.get("unit")
    if not hasattr(metric, "unit"):
        raise ValueError(
            "Metrics passed to money-currency validation must expose a unit field"
        )
    return getattr(metric, "unit")


def find_money_currency_violations(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for money metrics emitted without a
    non-empty currency/unit string on the runtime metric object.

    The metric registry contract requires money metrics to carry currency
    context so reports can render values unambiguously. A
    ``money_currency_missing`` violation means a metric key resolved to a
    canonical definition whose ``unit`` is ``"money"`` but whose runtime
    object's ``unit`` field is missing, ``None``, or whitespace-only. Unknown
    (unresolved) keys are intentionally skipped so this diagnostic composes
    cleanly with :func:`validate_metrics` and the other envelope helpers. A
    non-string ``unit`` raises ``ValueError`` so caller bugs surface loudly
    instead of being silently coerced. Result order matches input order and is
    deterministic.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, metric in enumerate(metrics):
        key = _metric_key(metric)
        unit = _metric_unit(metric)
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if definition.unit != "money":
            continue
        if unit is None:
            missing = True
        elif isinstance(unit, str):
            missing = not unit.strip()
        else:
            raise ValueError(
                f"Metric key '{key}' must expose a string unit field for "
                f"money-currency validation; received {type(unit).__name__}"
            )
        if not missing:
            continue
        issues.append(
            MetricValidationIssue(
                code="money_currency_missing",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has "
                    f"canonical unit 'money' but runtime metric carries no "
                    f"currency context (unit field is missing or blank)"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def find_freshness_companion_violations(
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for freshness_required metric keys emitted
    without a ``runtime.freshness`` family companion metric in the same payload.

    A ``freshness_companion_missing`` violation means a metric key resolved to a
    canonical definition whose ``freshness_required`` flag is ``True`` while no
    other key in the same input resolves to the ``runtime.freshness`` family
    (canonical ``runtime.freshness.last_success_at`` or
    ``runtime.freshness.age_seconds``, or any alias of theirs). When at least
    one ``runtime.freshness`` companion is present the diagnostic is suppressed
    for every freshness_required key in the input. Unknown (unresolved) keys
    are intentionally skipped so this diagnostic composes cleanly with
    :func:`validate_metrics` and the existing envelope/pii helpers. Result
    order matches input order and is deterministic.
    """

    active_registry = registry or default_metric_registry()
    materialized = list(metric_keys)
    for key in materialized:
        if not isinstance(key, str) or not key:
            raise ValueError(
                "find_freshness_companion_violations requires non-empty string metric keys"
            )

    for key in materialized:
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        if active_registry.get(canonical).family == "runtime.freshness":
            return []

    issues: list[MetricValidationIssue] = []
    for index, key in enumerate(materialized):
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if not definition.freshness_required:
            continue
        issues.append(
            MetricValidationIssue(
                code="freshness_companion_missing",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has "
                    f"freshness_required=True but no runtime.freshness metric "
                    f"accompanies it in the payload"
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


def find_case_allowed_violations(
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Return advisory diagnostics for metric keys whose canonical definition
    is not allowed to back Operational Case detections.

    A ``case_not_allowed`` violation means a metric key resolved to a canonical
    definition whose ``case_allowed`` flag is ``False`` (analytical signals such
    as ``commerce.average_order_value`` or ``ads.delivery.*`` that may inform
    reports but must not drive case lifecycle). Unknown (unresolved) keys are
    intentionally skipped so this diagnostic composes cleanly with
    :func:`validate_metrics` and the envelope helpers. Result order matches
    input order and is deterministic.
    """

    active_registry = registry or default_metric_registry()
    issues: list[MetricValidationIssue] = []
    for index, key in enumerate(metric_keys):
        if not isinstance(key, str) or not key:
            raise ValueError(
                "find_case_allowed_violations requires non-empty string metric keys"
            )
        canonical = active_registry.try_resolve_key(key)
        if canonical is None:
            continue
        definition = active_registry.get(canonical)
        if definition.case_allowed:
            continue
        issues.append(
            MetricValidationIssue(
                code="case_not_allowed",
                key=key,
                message=(
                    f"Metric key '{key}' (canonical '{canonical}') has "
                    f"case_allowed=False and must not back Operational Case "
                    f"detections"
                ),
                severity="warning",
                index=index,
            )
        )
    return issues


def validate_case_metric_keys(
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown-metric + case-not-allowed diagnostics for keys destined
    for an Operational Case detection stage.

    Parallel to :func:`validate_report_metric_keys` but on the case side:
    detection inputs must be both registered and case-allowed. The fixed
    concatenation order ``unknown_metric`` -> ``case_not_allowed`` keeps the
    result deterministic and free of overlap because
    :func:`find_case_allowed_violations` already skips unknown keys.
    """

    materialized = list(metric_keys)
    unknown_issues = validate_metrics(
        [{"key": key} for key in materialized],
        registry=registry,
    )
    case_issues = find_case_allowed_violations(
        materialized, registry=registry
    )
    return [*unknown_issues, *case_issues]


def validate_report_metric_objects(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown_metric + report_not_allowed + evidence_missing +
    evidence_source_mismatch + value_kind_mismatch + money_currency_missing
    diagnostics for metric-shaped objects bound for a user-facing report stage.

    Parallel to :meth:`ConnectorSpec.validate_emitted_metric_objects` but on the
    report-rendering side: the report renderer must reject report_not_allowed
    canonical metrics and surface evidence/value-kind/currency mismatches that
    the key-only :func:`validate_report_metric_keys` cannot see. The fixed
    concatenation order ``unknown_metric`` -> ``report_not_allowed`` ->
    ``evidence_missing`` -> ``evidence_source_mismatch`` ->
    ``value_kind_mismatch`` -> ``money_currency_missing`` keeps the result
    deterministic and free of overlap because each downstream helper skips
    unknown keys, the two evidence diagnostics are mutually exclusive
    (evidence_missing fires only on zero entries, evidence_source_mismatch only
    on non-empty collections), and money_currency_missing is scoped to a
    disjoint canonical population (only ``unit="money"`` metrics) from
    value_kind_mismatch (any unit kind). Money-currency lands last so
    structural and value-type diagnostics surface before the rendering-metadata
    diagnostic that money metrics must carry a currency string for reports to
    render unambiguously.
    """

    materialized = list(metrics)
    unknown_issues = validate_metrics(materialized, registry=registry)
    keys = [_metric_key(metric) for metric in materialized]
    report_issues = find_report_allowed_violations(keys, registry=registry)
    evidence_missing_issues = find_evidence_required_violations(
        materialized, registry=registry
    )
    evidence_issues = find_evidence_source_violations(
        materialized, registry=registry
    )
    value_kind_issues = find_value_kind_violations(
        materialized, registry=registry
    )
    money_currency_issues = find_money_currency_violations(
        materialized, registry=registry
    )
    return [
        *unknown_issues,
        *report_issues,
        *evidence_missing_issues,
        *evidence_issues,
        *value_kind_issues,
        *money_currency_issues,
    ]


def validate_case_metric_objects(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown_metric + case_not_allowed + evidence_missing +
    evidence_source_mismatch + value_kind_mismatch + money_currency_missing
    diagnostics for metric-shaped objects bound for an Operational Case
    detection stage.

    Parallel to :func:`validate_report_metric_objects` but on the case side:
    detection inputs must be both registered and case-allowed, and they must
    also pass evidence/value-kind/currency sanity checks. The fixed
    concatenation order ``unknown_metric`` -> ``case_not_allowed`` ->
    ``evidence_missing`` -> ``evidence_source_mismatch`` ->
    ``value_kind_mismatch`` -> ``money_currency_missing`` keeps the result
    deterministic and free of overlap because each downstream helper skips
    unknown keys, the two evidence diagnostics are mutually exclusive
    (evidence_missing fires only on zero entries, evidence_source_mismatch only
    on non-empty collections), and money_currency_missing is scoped to a
    disjoint canonical population (only ``unit="money"`` metrics) from
    value_kind_mismatch (any unit kind). Money-currency lands last so
    structural and value-type diagnostics surface before the rendering-metadata
    diagnostic that money metrics must carry a currency string for case
    detections to compare values unambiguously, mirroring the slot reserved by
    :func:`validate_report_metric_objects`.
    """

    materialized = list(metrics)
    unknown_issues = validate_metrics(materialized, registry=registry)
    keys = [_metric_key(metric) for metric in materialized]
    case_issues = find_case_allowed_violations(keys, registry=registry)
    evidence_missing_issues = find_evidence_required_violations(
        materialized, registry=registry
    )
    evidence_issues = find_evidence_source_violations(
        materialized, registry=registry
    )
    value_kind_issues = find_value_kind_violations(
        materialized, registry=registry
    )
    money_currency_issues = find_money_currency_violations(
        materialized, registry=registry
    )
    return [
        *unknown_issues,
        *case_issues,
        *evidence_missing_issues,
        *evidence_issues,
        *value_kind_issues,
        *money_currency_issues,
    ]


def validate_report_metric_keys(
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown-metric + report-not-allowed diagnostics for keys
    destined for a user-facing report stage.

    Parallel to ``ConnectorSpec.validate_emitted_metrics`` but on the report
    side: connector emission may legitimately surface ``report_allowed=False``
    runtime keys (e.g. ``runtime.freshness.*``); the report renderer must not.
    The fixed concatenation order ``unknown_metric`` -> ``report_not_allowed``
    keeps the result deterministic and free of overlap because
    :func:`find_report_allowed_violations` already skips unknown keys.
    """

    materialized = list(metric_keys)
    unknown_issues = validate_metrics(
        [{"key": key} for key in materialized],
        registry=registry,
    )
    report_issues = find_report_allowed_violations(
        materialized, registry=registry
    )
    return [*unknown_issues, *report_issues]


def validate_surface_metric_objects(
    metrics: Iterable[Any],
    *,
    allowed_pii_classes: Iterable[str],
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown_metric + pii_class_disallowed + evidence_missing +
    evidence_source_mismatch + value_kind_mismatch + money_currency_missing
    diagnostics for metric-shaped objects bound for a surface (WhatsApp
    dispatch, owner brief) that enforces a PII allowlist.

    Parallel to :func:`validate_report_metric_objects` and
    :func:`validate_case_metric_objects` but on the surface side: dispatch
    paths must reject metrics whose canonical ``pii_class`` is not in
    ``allowed_pii_classes`` and must also surface evidence/value-kind
    mismatches that the key-only :func:`validate_surface_metric_keys` cannot
    see. The fixed concatenation order ``unknown_metric`` ->
    ``pii_class_disallowed`` -> ``evidence_missing`` ->
    ``evidence_source_mismatch`` -> ``value_kind_mismatch`` ->
    ``money_currency_missing`` keeps the result deterministic and free of
    overlap because each downstream helper skips unknown keys, the two
    evidence diagnostics are mutually exclusive (evidence_missing fires only
    on zero entries, evidence_source_mismatch only on non-empty collections),
    and money_currency_missing is scoped to a disjoint canonical population
    (only ``unit="money"`` metrics) from value_kind_mismatch (any unit kind).
    Money-currency lands last so structural and value-type diagnostics surface
    before the rendering-metadata diagnostic that money metrics must carry a
    currency string for surfaces to render unambiguously, mirroring the slot
    reserved by :func:`validate_report_metric_objects`.
    ``allowed_pii_classes`` is validated by :func:`find_pii_class_violations`,
    so unsupported classes surface as ``ValueError`` rather than silently
    passing.
    """

    materialized = list(metrics)
    unknown_issues = validate_metrics(materialized, registry=registry)
    keys = [_metric_key(metric) for metric in materialized]
    pii_issues = find_pii_class_violations(
        keys,
        allowed_pii_classes=allowed_pii_classes,
        registry=registry,
    )
    evidence_missing_issues = find_evidence_required_violations(
        materialized, registry=registry
    )
    evidence_issues = find_evidence_source_violations(
        materialized, registry=registry
    )
    value_kind_issues = find_value_kind_violations(
        materialized, registry=registry
    )
    money_currency_issues = find_money_currency_violations(
        materialized, registry=registry
    )
    return [
        *unknown_issues,
        *pii_issues,
        *evidence_missing_issues,
        *evidence_issues,
        *value_kind_issues,
        *money_currency_issues,
    ]


def validate_surface_metric_keys(
    metric_keys: Iterable[str],
    *,
    allowed_pii_classes: Iterable[str],
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown_metric + pii_class_disallowed diagnostics for keys
    bound for a surface that enforces a PII allowlist.

    Parallel to :func:`validate_report_metric_keys` and
    :func:`validate_case_metric_keys` but on the surface side: dispatch paths
    (WhatsApp, owner brief) must reject metrics whose canonical ``pii_class`` is
    not in ``allowed_pii_classes``. The fixed concatenation order
    ``unknown_metric`` -> ``pii_class_disallowed`` keeps the result
    deterministic and free of overlap because :func:`find_pii_class_violations`
    already skips unknown keys. ``allowed_pii_classes`` is validated by
    :func:`find_pii_class_violations`, so unsupported classes surface as
    ``ValueError`` rather than silently passing.
    """

    materialized = list(metric_keys)
    unknown_issues = validate_metrics(
        [{"key": key} for key in materialized],
        registry=registry,
    )
    pii_issues = find_pii_class_violations(
        materialized,
        allowed_pii_classes=allowed_pii_classes,
        registry=registry,
    )
    return [*unknown_issues, *pii_issues]


def validate_freshness_envelope_metric_objects(
    metrics: Iterable[Any],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown_metric + freshness_companion_missing + evidence_missing +
    evidence_source_mismatch + value_kind_mismatch diagnostics for
    metric-shaped objects whose freshness envelope must be inspected together.

    Parallel to :func:`validate_freshness_envelope_metric_keys` but on the
    object side: scheduled runners, connector emitters, and ledger checks that
    already pass metric objects (with values and evidence) can rely on a single
    entry point that surfaces the keys-only freshness diagnostic plus the
    structural evidence/value-kind diagnostics that the keys-only validator
    cannot see. The fixed concatenation order ``unknown_metric`` ->
    ``freshness_companion_missing`` -> ``evidence_missing`` ->
    ``evidence_source_mismatch`` -> ``value_kind_mismatch`` keeps the result
    deterministic and free of overlap because each downstream helper skips
    unknown keys and the two evidence diagnostics are mutually exclusive
    (evidence_missing fires only on zero entries, evidence_source_mismatch only
    on non-empty collections).
    """

    materialized = list(metrics)
    unknown_issues = validate_metrics(materialized, registry=registry)
    keys = [_metric_key(metric) for metric in materialized]
    freshness_issues = find_freshness_companion_violations(
        keys, registry=registry
    )
    evidence_missing_issues = find_evidence_required_violations(
        materialized, registry=registry
    )
    evidence_issues = find_evidence_source_violations(
        materialized, registry=registry
    )
    value_kind_issues = find_value_kind_violations(
        materialized, registry=registry
    )
    return [
        *unknown_issues,
        *freshness_issues,
        *evidence_missing_issues,
        *evidence_issues,
        *value_kind_issues,
    ]


def validate_freshness_envelope_metric_keys(
    metric_keys: Iterable[str],
    *,
    registry: MetricRegistry | None = None,
) -> list[MetricValidationIssue]:
    """Compose unknown_metric + freshness_companion_missing diagnostics for a
    batch of keys whose freshness envelope must be inspected together.

    Parallel to :func:`validate_report_metric_keys`,
    :func:`validate_case_metric_keys`, and :func:`validate_surface_metric_keys`
    but on the freshness-envelope side: callers (connector emitters, scheduled
    runners, ledger checks) can rely on one entry point to flag both
    unregistered keys and freshness_required keys that are missing a
    ``runtime.freshness`` family companion in the same payload. The fixed
    concatenation order ``unknown_metric`` -> ``freshness_companion_missing``
    keeps the result deterministic and free of overlap because
    :func:`find_freshness_companion_violations` already skips unknown keys.
    """

    materialized = list(metric_keys)
    unknown_issues = validate_metrics(
        [{"key": key} for key in materialized],
        registry=registry,
    )
    freshness_issues = find_freshness_companion_violations(
        materialized, registry=registry
    )
    return [*unknown_issues, *freshness_issues]


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
    "find_case_allowed_violations",
    "find_evidence_required_violations",
    "find_evidence_source_violations",
    "find_family_envelope_violations",
    "find_freshness_companion_violations",
    "find_money_currency_violations",
    "find_pii_class_violations",
    "find_report_allowed_violations",
    "find_source_envelope_violations",
    "find_value_kind_violations",
    "validate_case_metric_keys",
    "validate_case_metric_objects",
    "validate_freshness_envelope_metric_keys",
    "validate_freshness_envelope_metric_objects",
    "validate_metrics",
    "validate_report_metric_keys",
    "validate_report_metric_objects",
    "validate_surface_metric_keys",
    "validate_surface_metric_objects",
]
