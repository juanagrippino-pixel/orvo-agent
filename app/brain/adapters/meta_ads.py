"""Meta Ads adapter for Orvo Brain.

Fetches daily ad spend, impressions, clicks and ROAS from the Meta Marketing
API (v19+) for a given ad account and returns a DailyReport with normalized
Metric objects, each backed by an Evidence record.

No env vars are read here — callers supply ad_account_id and access_token
directly.

TOKEN REFRESH FLOW
------------------
Meta user access tokens expire after ~60 days (system user tokens can be
long-lived). To refresh:

1.  Exchange a short-lived token for a long-lived token (60-day):
      GET https://graph.facebook.com/oauth/access_token
          ?grant_type=fb_exchange_token
          &client_id={app_id}
          &client_secret={app_secret}
          &fb_exchange_token={short_lived_token}

2.  For server-side automation, create a System User in Meta Business Manager
    and generate a non-expiring system-user access token. See:
    https://developers.facebook.com/docs/marketing-api/system-users

3.  Store the token in your secret manager and rotate before expiry.

ROAS AGGREGATION
----------------
The Meta API returns `purchase_roas` as a list of per-action-type dicts:
  [{"action_type": "omni_purchase", "value": "3.45"}]

We sum values across all action types present. When no purchase actions are
reported (e.g. awareness campaigns), ROAS defaults to 0.0.

CURRENCY
--------
Spend is returned in the ad account's billing currency. Confirm
business.currency matches the ad account currency in Meta Business Manager
before cross-channel comparisons.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.brain.models import DailyReport, Evidence, Metric


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MetaAdsAuthError(Exception):
    """Raised on HTTP 401/403 from Meta Graph API."""


class MetaAdsAPIError(Exception):
    """Raised on HTTP 5xx from Meta Graph API."""


class MetaAdsConnectionError(Exception):
    """Raised on unexpected non-success HTTP responses from Meta Graph API."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GRAPH_BASE = "https://graph.facebook.com"
_API_VERSION = "v19.0"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _insights_url(ad_account_id: str) -> str:
    """Return the insights endpoint URL for the given ad account."""
    account = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    return f"{_GRAPH_BASE}/{_API_VERSION}/{account}/insights"


def _check_response(resp: Any) -> None:
    status = resp.status_code
    if status in (401, 403):
        raise MetaAdsAuthError(f"Meta Ads auth failed: HTTP {status}")
    if 500 <= status < 600:
        raise MetaAdsAPIError(f"Meta Ads server error: HTTP {status}")
    if status >= 400:
        raise MetaAdsConnectionError(f"Meta Ads error: HTTP {status}")


def _parse_roas(purchase_roas: Any) -> float:
    """Aggregate purchase_roas across all action types.

    The API returns a list like:
      [{"action_type": "omni_purchase", "value": "3.45"}]
    We sum all values to get a total ROAS.
    """
    if not purchase_roas:
        return 0.0
    total = 0.0
    for item in (purchase_roas or []):
        try:
            total += float(item.get("value", 0) or 0)
        except (TypeError, ValueError):
            pass
    return total


def _aggregate_insights(data: list[dict]) -> dict:
    """Aggregate a list of insight rows (one per campaign/adset) into totals."""
    total_spend = 0.0
    total_impressions = 0
    total_clicks = 0
    roas_sum = 0.0
    roas_count = 0

    for row in data:
        try:
            total_spend += float(row.get("spend", 0) or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_impressions += int(row.get("impressions", 0) or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_clicks += int(row.get("clicks", 0) or 0)
        except (TypeError, ValueError):
            pass
        row_roas = _parse_roas(row.get("purchase_roas"))
        if row_roas:
            roas_sum += row_roas
            roas_count += 1

    # Average ROAS across campaigns that reported it; 0 if none
    avg_roas = (roas_sum / roas_count) if roas_count else 0.0

    return {
        "spend": total_spend,
        "impressions": total_impressions,
        "clicks": total_clicks,
        "roas": avg_roas,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_daily_report_from_meta_ads(
    business_name: str,
    report_date: date,
    ad_account_id: str,
    access_token: str,
    source_label: str = "Meta Ads",
    http_client: Optional[Any] = None,
) -> DailyReport:
    """Return a DailyReport populated from Meta Marketing API insights.

    Args:
        business_name: Human-readable store name.
        report_date: Date to report on (no default — be explicit).
        ad_account_id: Meta ad account ID (with or without 'act_' prefix).
        access_token: Meta user or system-user access token.
                      Tokens expire every ~60 days for user tokens; use
                      a system-user token for production. See module docstring
                      for the refresh flow.
        source_label: Human-readable label for Evidence records.
        http_client: Injectable session (must support .get(url, **kw)).
                     Defaults to a new requests.Session() if None.
    """
    if http_client is None:
        import requests
        http_client = requests.Session()

    url = _insights_url(ad_account_id)
    params = {
        "time_range": {"since": report_date.isoformat(), "until": report_date.isoformat()},
        "fields": "spend,impressions,clicks,purchase_roas",
        "level": "account",
        "access_token": access_token,
    }

    resp = http_client.get(url, params=params)
    _check_response(resp)
    body = resp.json() or {}
    data = body.get("data") or []

    totals = _aggregate_insights(data)

    evidence = Evidence(
        source="meta_ads",
        label=f"{source_label} · insights",
    )

    metrics: list[Metric] = [
        Metric(
            key="ad_spend_today",
            label="Inversión publicitaria del día",
            value=totals["spend"],
            unit="ARS",
            evidence=[evidence],
        ),
        Metric(
            key="ad_impressions_today",
            label="Impresiones del día",
            value=totals["impressions"],
            unit="impressions",
            evidence=[evidence],
        ),
        Metric(
            key="ad_clicks_today",
            label="Clicks del día",
            value=totals["clicks"],
            unit="clicks",
            evidence=[evidence],
        ),
        Metric(
            key="ad_roas_today",
            label="ROAS del día",
            value=totals["roas"],
            unit="x",
            evidence=[evidence],
        ),
    ]

    return DailyReport(
        business_name=business_name,
        report_date=report_date,
        metrics=metrics,
    )
