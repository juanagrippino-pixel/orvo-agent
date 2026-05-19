"""Dispatch Orvo Brain reports to delivery channels with idempotency."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

from app.brain.config import BusinessConfig
from app.brain.delivery import DeliveryResult, WhatsAppDeliveryClient, make_idempotency_key
from app.brain.models import DailyReport
from app.brain.reporting import compose_daily_report_text


class IdempotencyStore(Protocol):
    def has(self, key: str) -> bool: ...
    def mark(self, key: str) -> None: ...


class InMemoryIdempotencyStore:
    """Small dependency-free idempotency store for tests and first deployments."""

    def __init__(self) -> None:
        self._keys: set[str] = set()

    def has(self, key: str) -> bool:
        return key in self._keys

    def mark(self, key: str) -> None:
        self._keys.add(key)


class ReportDispatchResult(BaseModel):
    status: Literal["sent", "failed", "skipped_duplicate"]
    idempotency_key: str
    delivery: DeliveryResult | None = None
    error: str | None = None


def dispatch_daily_report(
    report: DailyReport,
    business: BusinessConfig,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
) -> ReportDispatchResult:
    """Send a daily report to the business owner exactly once per key."""

    key = make_idempotency_key(business.business_id, report.report_date, "daily")
    if idempotency_store.has(key):
        return ReportDispatchResult(status="skipped_duplicate", idempotency_key=key)

    text = compose_daily_report_text(report)
    delivery = delivery_client.send_text(business.owner_phone, text)
    if not delivery.success:
        return ReportDispatchResult(
            status="failed",
            idempotency_key=key,
            delivery=delivery,
            error=delivery.error,
        )

    idempotency_store.mark(key)
    return ReportDispatchResult(status="sent", idempotency_key=key, delivery=delivery)
