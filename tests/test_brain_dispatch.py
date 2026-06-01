import logging
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from app.brain.config import BusinessConfig
from app.brain.models import DailyReport, Evidence, Insight, Metric
from app.brain.operational_cases import OperationalCase, OperationalCaseEvidenceMetric, OperationalCaseEvidenceSnapshot


def make_report():
    source = Evidence(source="google_sheets", label="Sheet test")
    return DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        metrics=[Metric(key="revenue_today", label="Ventas de hoy", value=70000, unit="ARS", evidence=[source])],
        insights=[],
    )


def make_owner_case(case_id: str = "case-1", *, status: str = "open") -> OperationalCase:
    return OperationalCase(
        case_id=case_id,
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key=f"artemea/stockout/{case_id}",
        title="Stock crítico access_token=raw_dispatch_secret",
        status=status,  # type: ignore[arg-type]
        severity="critical",
        priority_score=95,
        entity_scope={"kind": "product", "id": "sku-1"},
        opened_at=datetime(2026, 5, 19, 9, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 19, 10, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 5, 19, 11, tzinfo=timezone.utc) if status == "resolved" else None,
        evidence_snapshots=[
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"run-1/evidence/{case_id}",
                captured_at=datetime(2026, 5, 19, 9, tzinfo=timezone.utc),
                run_id="run-1",
                evidence_ref="evidence://tiendanube/stock?access_token=raw_dispatch_secret",
                source="tiendanube",
                source_label="Tiendanube",
                case_type="stockout_risk",
                summary="Quedan pocas unidades Bearer raw_dispatch_secret",
                freshness_state="fresh",
                metrics=[
                    OperationalCaseEvidenceMetric(
                        metric_key="commerce.inventory.available_units",
                        label="Stock disponible",
                        value=2,
                        unit="units",
                    )
                ],
            )
        ],
        metadata={"recommended_action": "Reponer stock hoy.", "token": "raw_dispatch_secret"},
    )


def make_business():
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
    )


def test_dispatch_owner_case_brief_sends_case_backed_text_with_separate_idempotency_key():
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.case", error=None)
    idempotency = InMemoryIdempotencyStore()

    result = dispatch_owner_case_brief(
        cases=[make_owner_case(), make_owner_case("resolved", status="resolved")],
        business=make_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=idempotency,
    )

    assert result is not None
    assert result.status == "sent"
    assert result.idempotency_key == "artemea/2026-05-19/owner_case_brief"
    assert idempotency.has(result.idempotency_key)
    phone, text = delivery_client.send_text.call_args.args
    assert phone == "+5491112345678"
    assert "Stock crítico" in text
    assert "case-1" in text
    assert "resolved" not in text
    assert "raw_dispatch_secret" not in text


def test_dispatch_owner_case_brief_delivers_in_progress_cases_as_actionable():
    """Owner briefs must use the same actionable status set as operator queues.

    In-progress cases still require owner attention/projection until they are
    terminal, so they must not be hidden by the delivery prefilter or by the
    composed WhatsApp brief.
    """
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.case", error=None)

    result = dispatch_owner_case_brief(
        cases=[make_owner_case("work-1", status="in_progress")],
        business=make_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
    )

    assert result is not None
    assert result.status == "sent"
    phone, text = delivery_client.send_text.call_args.args
    assert phone == "+5491112345678"
    assert "Stock crítico" in text
    assert "work-1" in text
    assert "raw_dispatch_secret" not in text


def test_dispatch_owner_case_brief_skips_without_actionable_cases():
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief

    delivery_client = MagicMock()

    result = dispatch_owner_case_brief(
        cases=[make_owner_case("resolved", status="resolved")],
        business=make_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
    )

    assert result is None
    delivery_client.send_text.assert_not_called()


def test_dispatch_owner_case_brief_skips_duplicate_key():
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.case", error=None)
    idempotency = InMemoryIdempotencyStore()
    cases = [make_owner_case()]

    first = dispatch_owner_case_brief(cases, make_business(), date(2026, 5, 19), delivery_client, idempotency)
    second = dispatch_owner_case_brief(cases, make_business(), date(2026, 5, 19), delivery_client, idempotency)

    assert first is not None and first.status == "sent"
    assert second is not None and second.status == "skipped_duplicate"
    assert delivery_client.send_text.call_count == 1


def test_dispatch_owner_case_brief_failed_send_does_not_mark_key_and_allows_retry():
    """A failed owner case brief send must surface the error, leave the idempotency
    key unmarked, and allow a subsequent attempt to succeed.

    This locks the parity with dispatch_daily_report's failure contract so the
    operator-facing case brief is not silently dropped after a transient delivery
    error.
    """
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief

    delivery_client = MagicMock()
    delivery_client.send_text.side_effect = [
        DeliveryResult(success=False, message_id=None, error="HTTP 502"),
        DeliveryResult(success=True, message_id="wamid.case-retry", error=None),
    ]
    idempotency = InMemoryIdempotencyStore()
    cases = [make_owner_case()]

    first = dispatch_owner_case_brief(
        cases=cases,
        business=make_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=idempotency,
    )

    assert first is not None
    assert first.status == "failed"
    assert first.error == "HTTP 502"
    assert first.idempotency_key == "artemea/2026-05-19/owner_case_brief"
    assert not idempotency.has(first.idempotency_key)

    second = dispatch_owner_case_brief(
        cases=cases,
        business=make_business(),
        report_date=date(2026, 5, 19),
        delivery_client=delivery_client,
        idempotency_store=idempotency,
    )

    assert second is not None
    assert second.status == "sent"
    assert idempotency.has(second.idempotency_key)
    assert delivery_client.send_text.call_count == 2


def test_dispatch_owner_case_brief_failed_emits_warning_log(caplog):
    """Failed owner case brief sends must emit a warning-level structured log so
    operators can see why the brief was not delivered.
    """
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_owner_case_brief

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(
        success=False, message_id=None, error="HTTP 502"
    )

    with caplog.at_level(logging.WARNING, logger="app.brain.dispatch"):
        dispatch_owner_case_brief(
            cases=[make_owner_case()],
            business=make_business(),
            report_date=date(2026, 5, 19),
            delivery_client=delivery_client,
            idempotency_store=InMemoryIdempotencyStore(),
        )

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "failed" in r.getMessage() and "artemea/2026-05-19/owner_case_brief" in r.getMessage()
        for r in warnings
    )


def test_dispatch_daily_report_sends_composed_text_once():
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)
    idempotency = InMemoryIdempotencyStore()

    result = dispatch_daily_report(
        report=make_report(),
        business=make_business(),
        delivery_client=delivery_client,
        idempotency_store=idempotency,
    )

    assert result.status == "sent"
    assert result.idempotency_key == "artemea/2026-05-19/daily"
    delivery_client.send_text.assert_called_once()
    phone, text = delivery_client.send_text.call_args.args
    assert phone == "+5491112345678"
    assert "Orvo Brain" in text
    assert idempotency.has(result.idempotency_key)


def test_dispatch_daily_report_sends_whatsapp_budgeted_text_for_long_report():
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    source = Evidence(source="manual", label="Manual")
    long_report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        metrics=[
            Metric(
                key=f"metric_{i}",
                label=f"Métrica larga {i}",
                value=i * 1000,
                unit="ARS",
                evidence=[source],
            )
            for i in range(80)
        ],
        insights=[
            Insight(
                severity="warning",
                title="Reporte muy largo",
                explanation="Detalle " * 80,
                recommended_action="Revisar el reporte completo.",
                evidence=[source],
            )
        ],
    )
    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)

    result = dispatch_daily_report(
        report=long_report,
        business=make_business(),
        delivery_client=delivery_client,
        idempotency_store=InMemoryIdempotencyStore(),
    )

    assert result.status == "sent"
    _phone, text = delivery_client.send_text.call_args.args
    assert len(text) <= 1000
    assert text.endswith("... (ver reporte completo)")


def test_dispatch_daily_report_skips_duplicate_key():
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.1", error=None)
    idempotency = InMemoryIdempotencyStore()

    first = dispatch_daily_report(make_report(), make_business(), delivery_client, idempotency)
    second = dispatch_daily_report(make_report(), make_business(), delivery_client, idempotency)

    assert first.status == "sent"
    assert second.status == "skipped_duplicate"
    assert delivery_client.send_text.call_count == 1


def test_dispatch_daily_report_does_not_mark_failed_send_as_delivered():
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=False, message_id=None, error="HTTP 500")
    idempotency = InMemoryIdempotencyStore()

    result = dispatch_daily_report(make_report(), make_business(), delivery_client, idempotency)

    assert result.status == "failed"
    assert result.error == "HTTP 500"
    assert not idempotency.has(result.idempotency_key)


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


def test_dispatch_sent_emits_structured_log(caplog):
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.log1", error=None)

    with caplog.at_level(logging.INFO, logger="app.brain.dispatch"):
        dispatch_daily_report(make_report(), make_business(), delivery_client, InMemoryIdempotencyStore())

    messages = [r.getMessage() for r in caplog.records]
    assert any("sent" in m and "artemea/2026-05-19/daily" in m for m in messages)


def test_dispatch_skipped_duplicate_emits_structured_log(caplog):
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=True, message_id="wamid.log2", error=None)
    idempotency = InMemoryIdempotencyStore()
    dispatch_daily_report(make_report(), make_business(), delivery_client, idempotency)  # mark as sent

    with caplog.at_level(logging.INFO, logger="app.brain.dispatch"):
        dispatch_daily_report(make_report(), make_business(), delivery_client, idempotency)

    messages = [r.getMessage() for r in caplog.records]
    assert any("skipped_duplicate" in m and "artemea/2026-05-19/daily" in m for m in messages)


def test_dispatch_failed_emits_warning_log(caplog):
    from app.brain.delivery import DeliveryResult
    from app.brain.dispatch import InMemoryIdempotencyStore, dispatch_daily_report

    delivery_client = MagicMock()
    delivery_client.send_text.return_value = DeliveryResult(success=False, message_id=None, error="HTTP 500")

    with caplog.at_level(logging.WARNING, logger="app.brain.dispatch"):
        dispatch_daily_report(make_report(), make_business(), delivery_client, InMemoryIdempotencyStore())

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("failed" in r.getMessage() and "artemea/2026-05-19/daily" in r.getMessage() for r in warnings)
