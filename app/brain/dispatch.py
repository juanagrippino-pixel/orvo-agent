"""Dispatch Orvo Brain reports to delivery channels with idempotency."""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal, Protocol, Sequence

from pydantic import BaseModel

from app.brain.config import BusinessConfig
from app.brain.delivery import DeliveryResult, WhatsAppDeliveryClient, make_idempotency_key
from app.brain.models import DailyReport
from app.brain.operational_cases import OperationalCase
from app.brain.reporting import compose_daily_report_text, compose_owner_case_brief, truncate_for_whatsapp

_log = logging.getLogger(__name__)


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


def _send_text_once(
    *,
    key: str,
    business: BusinessConfig,
    text: str,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
) -> ReportDispatchResult:
    if idempotency_store.has(key):
        _log.info("dispatch skipped_duplicate key=%s business_id=%s", key, business.business_id)
        return ReportDispatchResult(status="skipped_duplicate", idempotency_key=key)

    delivery = delivery_client.send_text(business.owner_phone, truncate_for_whatsapp(text))
    if not delivery.success:
        _log.warning(
            "dispatch failed key=%s business_id=%s error=%s",
            key,
            business.business_id,
            delivery.error,
        )
        return ReportDispatchResult(
            status="failed",
            idempotency_key=key,
            delivery=delivery,
            error=delivery.error,
        )

    idempotency_store.mark(key)
    _log.info("dispatch sent key=%s business_id=%s message_id=%s", key, business.business_id, delivery.message_id)
    return ReportDispatchResult(status="sent", idempotency_key=key, delivery=delivery)


def _actionable_cases(cases: Sequence[OperationalCase]) -> list[OperationalCase]:
    return [case for case in cases if case.status in {"open", "acknowledged"}]


def dispatch_owner_case_brief(
    cases: Sequence[OperationalCase],
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    *,
    max_cases: int = 3,
) -> ReportDispatchResult | None:
    """Send an owner-facing WhatsApp brief from canonical actionable cases."""

    if not _actionable_cases(cases):
        _log.info("dispatch owner_case_brief skipped_no_cases business_id=%s", business.business_id)
        return None
    key = make_idempotency_key(business.business_id, report_date, "owner_case_brief")
    text = compose_owner_case_brief(
        business.business_name,
        cases,
        report_date=report_date,
        max_cases=max_cases,
    )
    return _send_text_once(
        key=key,
        business=business,
        text=text,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )


def dispatch_daily_report(
    report: DailyReport,
    business: BusinessConfig,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
) -> ReportDispatchResult:
    """Send a daily report to the business owner exactly once per key."""

    key = make_idempotency_key(business.business_id, report.report_date, "daily")
    text = compose_daily_report_text(report)
    return _send_text_once(
        key=key,
        business=business,
        text=text,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
