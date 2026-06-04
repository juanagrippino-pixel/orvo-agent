from datetime import date
from unittest.mock import MagicMock

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.pipeline import run_meta_ads_daily_report_pipeline


class FakeMetaAdsHTTPClient:
    def __init__(self):
        self.requests = []

    def get(self, url, params=None):
        self.requests.append({"url": url, "params": params or {}})
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {
                    "spend": "321.50",
                    "impressions": "1200",
                    "clicks": "45",
                    "purchase_roas": [{"action_type": "omni_purchase", "value": "2.25"}],
                }
            ]
        }
        return response


def make_meta_ads_business(params=None):
    return BusinessConfig(
        business_id="demo-meta",
        business_name="Demo Meta",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="demo-meta-conn",
                connector_type="meta_ads",
                label="Meta Ads Demo",
                params={"ad_account_id": "act_123", "access_token": "meta_test_token"} if params is None else params,
            )
        ],
    )


def test_meta_ads_pipeline_builds_and_dispatches_report_with_injected_http_client():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    http_client = FakeMetaAdsHTTPClient()

    result = run_meta_ads_daily_report_pipeline(
        business=make_meta_ads_business(),
        report_date=date(2026, 5, 17),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=http_client,
    )

    metrics = {metric.key: metric.value for metric in result.report.metrics}
    assert result.report.business_name == "Demo Meta"
    assert metrics["ad_spend_today"] == pytest.approx(321.50)
    assert metrics["ad_impressions_today"] == 1200
    assert result.dispatch.status == "sent"
    delivery.send_text.assert_called_once()
    assert http_client.requests[0]["params"]["time_range"] == '{"since": "2026-05-17", "until": "2026-05-17"}'


def test_meta_ads_pipeline_serializes_time_range_as_json_string_for_live_api_compat():
    delivery = MagicMock()
    delivery.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    http_client = FakeMetaAdsHTTPClient()

    run_meta_ads_daily_report_pipeline(
        business=make_meta_ads_business(),
        report_date=date(2026, 5, 17),
        delivery_client=delivery,
        idempotency_store=InMemoryIdempotencyStore(),
        http_client=http_client,
    )

    assert http_client.requests[0]["params"]["time_range"] == '{"since": "2026-05-17", "until": "2026-05-17"}'


def test_meta_ads_pipeline_requires_ad_account_id_and_access_token():
    with pytest.raises(ValueError, match="ad_account_id and access_token"):
        run_meta_ads_daily_report_pipeline(
            business=make_meta_ads_business(params={}),
            report_date=date(2026, 5, 17),
            delivery_client=MagicMock(),
            idempotency_store=InMemoryIdempotencyStore(),
            http_client=FakeMetaAdsHTTPClient(),
        )
