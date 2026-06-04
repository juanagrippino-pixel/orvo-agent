from __future__ import annotations

from datetime import date
from typing import Any

from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseStore,
)
from app.brain.reporting import compose_owner_case_brief, order_owner_case_brief_cases
from app.brain.security.redaction import redact_secrets, redact_text

from .common import OperatorAPIError, parse_limit


def _parse_report_date(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise OperatorAPIError("invalid_report_date", "report_date must be YYYY-MM-DD", status_code=400) from exc


def _owner_brief_cases(store: OperationalCaseStore, business_id: str) -> list[OperationalCase]:
    cases: list[OperationalCase] = []
    for status in ACTIONABLE_OPERATIONAL_CASE_STATUSES:
        cases.extend(store.list_cases(business_id=business_id, status=status, limit=None))
    return order_owner_case_brief_cases(cases)


def preview_owner_case_brief(
    store: OperationalCaseStore,
    *,
    business_id: str,
    business_name: str | None = None,
    report_date: str | None = None,
    max_cases: str | None = None,
) -> dict[str, Any]:
    """Read-only owner WhatsApp brief projection from canonical Operational Cases.

    This helper intentionally returns projection metadata plus composed text only;
    it does not dispatch, mutate case state, or treat WhatsApp copy as source of
    truth. Case selection comes from the canonical case store and is tenant
    scoped before text composition.
    """

    parsed_max_cases = parse_limit(max_cases, default=3, max_limit=10)
    parsed_report_date = _parse_report_date(report_date)
    safe_business_name = redact_text((business_name or business_id).strip() or business_id) or "[REDACTED]"
    actionable = _owner_brief_cases(store, business_id)
    visible = actionable[:parsed_max_cases]
    text = compose_owner_case_brief(
        safe_business_name,
        actionable,
        report_date=parsed_report_date,
        max_cases=parsed_max_cases,
    )
    payload = {
        "business_id": business_id,
        "business_name": safe_business_name,
        "projection_type": "owner_case_brief",
        "channel": "whatsapp",
        "report_date": parsed_report_date.isoformat() if parsed_report_date is not None else None,
        "max_cases": parsed_max_cases,
        "total_actionable_cases": len(actionable),
        "displayed_case_count": len(visible),
        "truncated": len(actionable) > len(visible),
        "case_ids": [case.case_id for case in visible],
        "text": text,
    }
    return redact_secrets(payload)


__all__ = [name for name in globals() if not name.startswith("__")]
