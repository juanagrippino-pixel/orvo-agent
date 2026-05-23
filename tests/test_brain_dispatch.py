from datetime import date
from unittest.mock import MagicMock

from app.brain.config import BusinessConfig
from app.brain.models import DailyReport, Evidence, Insight, Metric


def make_report():
    source = Evidence(source="google_sheets", label="Sheet test")
    return DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        metrics=[Metric(key="revenue_today", label="Ventas de hoy", value=70000, unit="ARS", evidence=[source])],
        insights=[],
    )


def make_business():
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
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
    assert "ARTEMEA · 2026-05-19" in text
    assert "Orvo Brain" not in text
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
    assert "Prioridad: Revisar el reporte completo." in text


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
