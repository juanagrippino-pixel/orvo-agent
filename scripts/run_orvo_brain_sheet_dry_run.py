"""Run Orvo Brain against the live Google Sheet without sending WhatsApp."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import DeliveryResult
from app.brain.dispatch import InMemoryIdempotencyStore
from app.brain.pipeline import run_google_sheets_daily_report_pipeline
from app.brain.reporting import compose_daily_report_text

SPREADSHEET_ID = "1OO5fEVKraXKkiofZ0EtHpEOUPgHMxym-Y82VPwtRtG0"
RANGE_NAME = "Daily!A1:G1000"
TOKEN_PATH = Path.home() / ".hermes" / "google_token.json"
CLIENT_SECRET_PATH = Path.home() / ".hermes" / "google_client_secret.json"


def load_credentials() -> Credentials:
    client = json.loads(CLIENT_SECRET_PATH.read_text())
    client_info = client.get("installed") or client.get("web") or client
    token = json.loads(TOKEN_PATH.read_text())
    return Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=client_info["client_id"],
        client_secret=client_info["client_secret"],
        scopes=token.get("scopes"),
    )


def main() -> None:
    sheets_service = build("sheets", "v4", credentials=load_credentials())
    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="artemea-google-sheets",
                connector_type="google_sheets",
                label="Orvo Brain - Artemea Control Plane",
                params={"spreadsheet_id": SPREADSHEET_ID, "range_name": RANGE_NAME},
            )
        ],
    )
    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="dry-run", error=None)
    result = run_google_sheets_daily_report_pipeline(
        business=business,
        report_date=date.today(),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
        sheets_service=sheets_service,
    )
    print(compose_daily_report_text(result.report))
    print("\n---")
    print(json.dumps({"dispatch_status": result.dispatch.status, "metrics": [m.model_dump(mode="json") for m in result.report.metrics]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
