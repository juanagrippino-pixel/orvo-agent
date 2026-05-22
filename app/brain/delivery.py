"""WhatsApp delivery layer for Orvo Brain reports.

Design:
    - WhatsAppDeliveryClient: thin wrapper over Meta Cloud API or Twilio.
    - DeliveryTarget: validated phone + business_id.
    - DeliveryResult: structured success/failure output.
    - build_report_delivery_payload: constructs the Meta API JSON body.
    - make_idempotency_key: deterministic key for deduplication.

Runtime credentials are read from env vars via WhatsAppDeliveryClient.from_env().
Tests inject a mock http_client — no real network calls are made.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import requests
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class DeliveryTarget(BaseModel):
    """Validated delivery destination."""

    phone: str = Field(..., min_length=1)
    business_id: str = Field(..., min_length=1)


class DeliveryResult(BaseModel):
    """Outcome of a single WhatsApp message send attempt."""

    success: bool
    message_id: str | None
    error: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_idempotency_key(
    business_id: str,
    report_date: date,
    report_type: str,
) -> str:
    """Return a deterministic idempotency key: <business_id>/<date>/<type>.

    Example:
        make_idempotency_key("artemea", date(2026, 5, 19), "daily")
        => "artemea/2026-05-19/daily"
    """
    return f"{business_id}/{report_date.isoformat()}/{report_type}"


def build_report_delivery_payload(
    report_text: str,
    target: DeliveryTarget,
) -> dict[str, Any]:
    """Build the WhatsApp Cloud API JSON body for a text message.

    Args:
        report_text: The composed report string (e.g. from compose_daily_report_text).
        target: Destination phone number and business metadata.

    Returns:
        dict ready for ``requests.Session.post(..., json=payload)``.

    Raises:
        ValueError: if report_text is empty.
    """
    if not report_text:
        raise ValueError("report_text must not be empty")
    return {
        "messaging_product": "whatsapp",
        "to": target.phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": report_text,
        },
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_GRAPH_API_VERSION = "v19.0"
_BASE_URL = "https://graph.facebook.com"
_TWILIO_BASE_URL = "https://api.twilio.com/2010-04-01"


class WhatsAppDeliveryClient:
    """Sends WhatsApp text messages via the Meta Cloud API.

    Args:
        phone_id: WhatsApp Business phone number ID (from Meta dashboard).
        token:    Permanent or temporary access token.
        http_client: A requests.Session-compatible object. Defaults to a
                     fresh ``requests.Session()``. Inject a mock in tests.
    """

    def __init__(
        self,
        phone_id: str,
        token: str,
        http_client: Any | None = None,
        provider: str = "meta_cloud",
        twilio_account_sid: str | None = None,
        twilio_auth_token: str | None = None,
        twilio_whatsapp_number: str | None = None,
    ) -> None:
        self._phone_id = phone_id
        self._token = token
        self._http = http_client if http_client is not None else requests.Session()
        self._provider = provider
        self._twilio_account_sid = twilio_account_sid
        self._twilio_auth_token = twilio_auth_token
        self._twilio_whatsapp_number = twilio_whatsapp_number

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "WhatsAppDeliveryClient":
        """Construct a client from environment variables.

        Required env vars:
            WHATSAPP_PHONE_ID
            WHATSAPP_TOKEN

        Raises:
            EnvironmentError: if either variable is missing or empty.
        """
        provider = (os.environ.get("WHATSAPP_PROVIDER") or "meta_cloud").strip().lower()
        if provider == "twilio":
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
            whatsapp_number = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
            missing = [
                name
                for name, val in [
                    ("TWILIO_ACCOUNT_SID", account_sid),
                    ("TWILIO_AUTH_TOKEN", auth_token),
                    ("TWILIO_WHATSAPP_NUMBER", whatsapp_number),
                ]
                if not val
            ]
            if missing:
                raise EnvironmentError(
                    f"Missing required environment variable(s): {', '.join(missing)}"
                )
            return cls(
                phone_id="",
                token="",
                provider="twilio",
                twilio_account_sid=account_sid,
                twilio_auth_token=auth_token,
                twilio_whatsapp_number=whatsapp_number,
            )

        phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
        token = os.environ.get("WHATSAPP_TOKEN", "")
        missing = [
            name
            for name, val in [
                ("WHATSAPP_PHONE_ID", phone_id),
                ("WHATSAPP_TOKEN", token),
            ]
            if not val
        ]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )
        return cls(phone_id=phone_id, token=token)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_text(self, phone: str, text: str) -> DeliveryResult:
        """Send a plain-text WhatsApp message.

        Args:
            phone: Destination phone in E.164 format (e.g. "+5491112345678").
            text:  Message body.

        Returns:
            DeliveryResult with success flag, message_id, and optional error.
        """
        if self._provider == "twilio":
            return self._send_text_via_twilio(phone=phone, text=text)

        url = (
            f"{_BASE_URL}/{_GRAPH_API_VERSION}"
            f"/{self._phone_id}/messages"
        )
        target = DeliveryTarget(phone=phone, business_id="runtime")
        payload = build_report_delivery_payload(text, target)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        try:
            response = self._http.post(url, json=payload, headers=headers)
        except Exception as exc:
            return DeliveryResult(success=False, message_id=None, error=str(exc))

        if response.status_code == 200:
            data = response.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            return DeliveryResult(success=True, message_id=message_id, error=None)

        # Non-200: extract error message
        try:
            err_body = response.json()
            error_msg = (
                err_body.get("error", {}).get("message")
                or f"HTTP {response.status_code}"
            )
        except Exception:
            error_msg = f"HTTP {response.status_code}"

        return DeliveryResult(
            success=False,
            message_id=None,
            error=f"HTTP {response.status_code}: {error_msg}",
        )

    def _send_text_via_twilio(self, *, phone: str, text: str) -> DeliveryResult:
        account_sid = self._twilio_account_sid or ""
        auth_token = self._twilio_auth_token or ""
        from_number = self._twilio_whatsapp_number or ""
        url = f"{_TWILIO_BASE_URL}/Accounts/{account_sid}/Messages.json"
        to_phone = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        data = {
            "From": from_number,
            "To": to_phone,
            "Body": text,
        }
        try:
            response = self._http.post(
                url,
                data=data,
                auth=(account_sid, auth_token),
            )
        except Exception as exc:
            return DeliveryResult(success=False, message_id=None, error=str(exc))

        if response.status_code in (200, 201):
            body = response.json()
            return DeliveryResult(success=True, message_id=body.get("sid"), error=None)

        try:
            err_body = response.json()
            error_msg = err_body.get("message") or err_body.get("error_message") or f"HTTP {response.status_code}"
        except Exception:
            error_msg = f"HTTP {response.status_code}"

        return DeliveryResult(
            success=False,
            message_id=None,
            error=f"HTTP {response.status_code}: {error_msg}",
        )
