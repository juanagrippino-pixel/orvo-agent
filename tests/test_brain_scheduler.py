"""Tests for app.brain.scheduler — TDD cycle: RED → GREEN → REFACTOR.

All 12 required test cases are covered:
 1. ScheduledReportRun has correct fields
 2. should_run_schedule returns True when now matches cron hour:minute in business tz
 3. should_run_schedule returns False when hour doesn't match
 4. should_run_schedule returns False when schedule.enabled=False
 5. should_run_schedule handles timezone correctly (UTC vs America/Argentina/Buenos_Aires)
 6. next_daily_run returns today's fire time if after is before it
 7. next_daily_run returns tomorrow's fire time if after is past today's fire time
 8. next_daily_run result is UTC-aware
 9. due_schedules returns ScheduledReportRun for matching schedules
10. due_schedules skips disabled schedules
11. due_schedules skips unknown business_id (no KeyError)
12. due_schedules returns empty list when nothing due
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.brain.config import BusinessConfig, ReportSchedule
from app.brain.scheduler import (
    ScheduledReportRun,
    should_run_schedule,
    next_daily_run,
    due_schedules,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

UTC = timezone.utc

def make_schedule(
    schedule_id: str = "sched-1",
    business_id: str = "biz-1",
    cron_expression: str = "30 8 * * *",
    report_type: str = "daily",
    enabled: bool = True,
) -> ReportSchedule:
    return ReportSchedule(
        schedule_id=schedule_id,
        business_id=business_id,
        cron_expression=cron_expression,
        report_type=report_type,
        enabled=enabled,
    )


def make_business_config(
    business_id: str = "biz-1",
    timezone: str = "UTC",
) -> BusinessConfig:
    return BusinessConfig(
        business_id=business_id,
        business_name="Test Biz",
        owner_phone="+1234567890",
        timezone=timezone,
        currency="USD",
    )


# ---------------------------------------------------------------------------
# Test 1: ScheduledReportRun has correct fields
# ---------------------------------------------------------------------------

def test_scheduled_report_run_fields():
    run_at = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    run = ScheduledReportRun(
        schedule_id="sched-1",
        business_id="biz-1",
        report_type="daily",
        run_at=run_at,
    )
    assert run.schedule_id == "sched-1"
    assert run.business_id == "biz-1"
    assert run.report_type == "daily"
    assert run.run_at == run_at


# ---------------------------------------------------------------------------
# Test 2: should_run_schedule returns True when now matches cron hour:minute
# ---------------------------------------------------------------------------

def test_should_run_schedule_true_when_matches():
    # cron "30 8 * * *" => fire at 08:30 UTC
    sched = make_schedule(cron_expression="30 8 * * *")
    # now is 08:30:00 UTC — within the minute tick (seconds=0 < 60)
    now = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now, "UTC") is True


# ---------------------------------------------------------------------------
# Test 3: should_run_schedule returns False when hour doesn't match
# ---------------------------------------------------------------------------

def test_should_run_schedule_false_wrong_hour():
    sched = make_schedule(cron_expression="30 8 * * *")
    # now is 09:30 UTC — hour doesn't match
    now = datetime(2026, 5, 19, 9, 30, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now, "UTC") is False


# ---------------------------------------------------------------------------
# Test 4: should_run_schedule returns False when enabled=False
# ---------------------------------------------------------------------------

def test_should_run_schedule_false_when_disabled():
    sched = make_schedule(cron_expression="30 8 * * *", enabled=False)
    now = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now, "UTC") is False


# ---------------------------------------------------------------------------
# Test 5: should_run_schedule handles timezone correctly
# America/Argentina/Buenos_Aires is UTC-3 (no DST)
# If cron is "00 9 * * *" (09:00 Buenos Aires), that's 12:00 UTC
# ---------------------------------------------------------------------------

def test_should_run_schedule_timezone_offset():
    sched = make_schedule(cron_expression="0 9 * * *")
    tz = "America/Argentina/Buenos_Aires"  # UTC-3, no DST
    # 12:00 UTC == 09:00 Buenos Aires => should fire
    now_utc = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now_utc, tz) is True

    # 09:00 UTC == 06:00 Buenos Aires => should NOT fire
    now_utc_wrong = datetime(2026, 5, 19, 9, 0, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now_utc_wrong, tz) is False


# ---------------------------------------------------------------------------
# Test 6: next_daily_run returns today's fire time if after is before it
# ---------------------------------------------------------------------------

def test_next_daily_run_today_if_before():
    sched = make_schedule(cron_expression="30 8 * * *")
    # after is 07:00 UTC on 2026-05-19 — before today's 08:30 UTC fire
    after = datetime(2026, 5, 19, 7, 0, 0, tzinfo=UTC)
    result = next_daily_run(sched, after, "UTC")
    expected = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    assert result == expected


# ---------------------------------------------------------------------------
# Test 7: next_daily_run returns tomorrow's fire time if after is past today
# ---------------------------------------------------------------------------

def test_next_daily_run_tomorrow_if_past():
    sched = make_schedule(cron_expression="30 8 * * *")
    # after is 09:00 UTC on 2026-05-19 — past today's 08:30 UTC fire
    after = datetime(2026, 5, 19, 9, 0, 0, tzinfo=UTC)
    result = next_daily_run(sched, after, "UTC")
    expected = datetime(2026, 5, 20, 8, 30, 0, tzinfo=UTC)
    assert result == expected


# ---------------------------------------------------------------------------
# Test 8: next_daily_run result is UTC-aware
# ---------------------------------------------------------------------------

def test_next_daily_run_result_is_utc_aware():
    sched = make_schedule(cron_expression="0 6 * * *")
    after = datetime(2026, 5, 19, 0, 0, 0, tzinfo=UTC)
    result = next_daily_run(sched, after, "UTC")
    assert result.tzinfo is not None
    # Confirm it's UTC by checking offset is zero
    assert result.utcoffset() == timedelta(0)


# ---------------------------------------------------------------------------
# Test 9: due_schedules returns ScheduledReportRun for matching schedules
# ---------------------------------------------------------------------------

def test_due_schedules_returns_runs_for_matching():
    sched = make_schedule(cron_expression="30 8 * * *")
    biz = make_business_config(timezone="UTC")
    now = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    result = due_schedules([sched], now, {"biz-1": biz})
    assert len(result) == 1
    run = result[0]
    assert isinstance(run, ScheduledReportRun)
    assert run.schedule_id == "sched-1"
    assert run.business_id == "biz-1"
    assert run.report_type == "daily"
    assert run.run_at == now


# ---------------------------------------------------------------------------
# Test 10: due_schedules skips disabled schedules
# ---------------------------------------------------------------------------

def test_due_schedules_skips_disabled():
    sched = make_schedule(cron_expression="30 8 * * *", enabled=False)
    biz = make_business_config(timezone="UTC")
    now = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    result = due_schedules([sched], now, {"biz-1": biz})
    assert result == []


# ---------------------------------------------------------------------------
# Test 11: due_schedules skips unknown business_id (no KeyError)
# ---------------------------------------------------------------------------

def test_due_schedules_skips_unknown_business_id():
    sched = make_schedule(business_id="unknown-biz", cron_expression="30 8 * * *")
    now = datetime(2026, 5, 19, 8, 30, 0, tzinfo=UTC)
    # business_configs has no entry for "unknown-biz" — must not raise
    result = due_schedules([sched], now, {})
    assert result == []


# ---------------------------------------------------------------------------
# Test 12: due_schedules returns empty list when nothing due
# ---------------------------------------------------------------------------

def test_due_schedules_empty_when_nothing_due():
    sched = make_schedule(cron_expression="30 8 * * *")
    biz = make_business_config(timezone="UTC")
    # now is 09:00 — not 08:30
    now = datetime(2026, 5, 19, 9, 0, 0, tzinfo=UTC)
    result = due_schedules([sched], now, {"biz-1": biz})
    assert result == []


# ---------------------------------------------------------------------------
# Test 13: ARTEMEA production contract — "0 8 * * *" fires at 11:00 UTC
# America/Argentina/Buenos_Aires is UTC-3, so 08:00 local == 11:00 UTC.
# ---------------------------------------------------------------------------

def test_artemea_08h00_schedule_fires_at_11h00_utc():
    """Production contract: 08:00 Buenos Aires = 11:00 UTC, no DST."""
    sched = make_schedule(cron_expression="0 8 * * *")
    tz = "America/Argentina/Buenos_Aires"

    # 11:00 UTC == 08:00 Buenos Aires => should fire
    now_match = datetime(2026, 5, 19, 11, 0, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now_match, tz) is True

    # 12:00 UTC == 09:00 Buenos Aires => should NOT fire
    now_miss = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    assert should_run_schedule(sched, now_miss, tz) is False

    # next_daily_run from 10:00 UTC returns today's 11:00 UTC fire
    after_before = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
    nxt = next_daily_run(sched, after_before, tz)
    assert nxt == datetime(2026, 5, 19, 11, 0, 0, tzinfo=UTC)
