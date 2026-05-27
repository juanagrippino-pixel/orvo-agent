"""Contract tests for adapter-emitted metrics.

These tests pin two invariants that the existing TDD adapter tests do not
cover directly:

1. Every metric key emitted by the Tiendanube and MercadoLibre adapters resolves
   to a canonical key in the semantic metric registry (either as a canonical
   key or via a registered alias). This protects against an adapter quietly
   introducing a metric key that has no registry-side meaning.
2. The canonical family of each emitted metric is declared in the connector
   spec's ``emitted_metric_families``. This keeps connector-registry metadata
   honest about what the runtime actually receives.

The tests use stub HTTP clients only, so no network access or secrets are
required. Hito 0 / WhatsApp report behavior is intentionally unchanged: these
contracts only observe adapter output.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable
from unittest.mock import MagicMock

from app.brain.adapters.mercadolibre import build_daily_report_from_mercadolibre
from app.brain.adapters.meta_ads import build_daily_report_from_meta_ads
from app.brain.adapters.tiendanube import build_daily_report_from_tiendanube
from app.brain.connector_registry import get_connector_spec
from app.brain.semantics.metric_registry import (
    default_metric_registry,
    find_source_envelope_violations,
    validate_metrics,
)


def _response(data, status: int = 200, link: str = ""):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = data
    response.headers = {"Link": link} if link else {}
    return response


def _tiendanube_session() -> MagicMock:
    orders = [
        {"id": 1, "status": "paid", "total": "5000.00"},
        {"id": 2, "status": "open", "total": "3200.50"},
    ]
    products = [
        {"id": 10, "variants": [{"stock": 5}, {"stock": 3}]},
        {"id": 11, "variants": [{"stock": None}, {"stock": 10}]},
    ]
    session = MagicMock()

    def fake_get(url, **_kwargs):
        if "/orders" in url:
            return _response(orders)
        if "/products" in url:
            return _response(products)
        raise AssertionError(f"unexpected URL in contract test: {url}")

    session.get.side_effect = fake_get
    return session


def _meta_ads_session() -> MagicMock:
    body = {
        "data": [
            {
                "spend": "1500.75",
                "impressions": "20000",
                "clicks": "350",
                "purchase_roas": [{"action_type": "omni_purchase", "value": "3.20"}],
            }
        ]
    }
    session = MagicMock()
    session.get.return_value = _response(body)
    return session


def _mercadolibre_session() -> MagicMock:
    body = {
        "results": [
            {"id": 1, "status": "paid", "total_amount": 5000.0},
            {"id": 2, "status": "confirmed", "total_amount": 3200.5},
        ],
        "paging": {"total": 2, "limit": 50, "offset": 0},
    }
    session = MagicMock()
    session.get.return_value = _response(body)
    return session


def _assert_metrics_match_connector_envelope(
    metric_keys: Iterable[str], connector_type: str
) -> None:
    registry = default_metric_registry()
    spec = get_connector_spec(connector_type)
    declared_families = set(spec.emitted_metric_families)

    materialized_keys = list(metric_keys)
    unresolved: list[str] = []
    family_mismatches: list[str] = []
    for key in materialized_keys:
        canonical = registry.try_resolve_key(key)
        if canonical is None:
            unresolved.append(key)
            continue
        family = registry.get(canonical).family
        if family not in declared_families:
            family_mismatches.append(f"{key}->{family}")

    assert unresolved == [], (
        f"{connector_type} adapter emitted unknown metric keys: {unresolved}"
    )
    assert family_mismatches == [], (
        f"{connector_type} adapter emits metric families not declared in "
        f"connector spec emitted_metric_families: {family_mismatches}"
    )

    source_violations = find_source_envelope_violations(
        materialized_keys, connector_type=connector_type
    )
    assert source_violations == [], (
        f"{connector_type} adapter emitted metrics whose canonical "
        f"allowed_sources excludes '{connector_type}': "
        f"{[issue.message for issue in source_violations]}"
    )


def test_tiendanube_adapter_emits_only_registry_resolvable_metrics_inside_connector_envelope():
    report = build_daily_report_from_tiendanube(
        business_name="Contract Store",
        store_id="123",
        access_token="tn_test_token",
        report_date=date(2025, 1, 15),
        http_client=_tiendanube_session(),
        include_stock=True,
    )

    assert report.metrics, "Tiendanube adapter must emit at least one metric for the contract test"
    _assert_metrics_match_connector_envelope(
        (metric.key for metric in report.metrics), "tiendanube"
    )
    assert validate_metrics(report.metrics) == []


def test_meta_ads_adapter_emits_only_registry_resolvable_metrics_inside_connector_envelope():
    report = build_daily_report_from_meta_ads(
        business_name="Contract Store",
        report_date=date(2025, 1, 15),
        ad_account_id="act_12345",
        access_token="meta_test_token",
        http_client=_meta_ads_session(),
    )

    assert report.metrics, "Meta Ads adapter must emit at least one metric for the contract test"
    _assert_metrics_match_connector_envelope(
        (metric.key for metric in report.metrics), "meta_ads"
    )
    assert validate_metrics(report.metrics) == []


def test_mercadolibre_adapter_emits_only_registry_resolvable_metrics_inside_connector_envelope():
    report = build_daily_report_from_mercadolibre(
        business_name="Contract Store",
        report_date=date(2025, 1, 15),
        seller_id="42",
        access_token="ml_test_token",
        http_client=_mercadolibre_session(),
    )

    assert report.metrics, "MercadoLibre adapter must emit at least one metric for the contract test"
    _assert_metrics_match_connector_envelope(
        (metric.key for metric in report.metrics), "mercadolibre"
    )
    assert validate_metrics(report.metrics) == []
