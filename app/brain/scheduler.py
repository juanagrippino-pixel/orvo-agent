"""Orvo Brain — Scheduler planning layer.

Pure-Python, stdlib-only (datetime + zoneinfo).
No external dependencies required.

Public API
----------
- ScheduledReportRun   dataclass holding a resolved run record
- should_run_schedule  decide whether a schedule is due right now
- next_daily_run       compute the next UTC fire time for a daily cron
- due_schedules        batch-filter a list of schedules to those currently due
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.brain.config import BusinessConfig, ReportSchedule

UTC = timezone.utc


# ---------------------------------------------------------------------------
# ScheduledReportRun
# ---------------------------------------------------------------------------


@dataclass
class ScheduledReportRun:
    """A resolved record indicating that a report should be produced now."""

    schedule_id: str
    business_id: str
    report_type: str
    run_at: datetime  # always UTC-aware


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_cron(cron_expression: str) -> tuple[int, int]:
    """Parse 'M H * * *' and return (minute, hour) as ints."""
    parts = cron_expression.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid cron expression: {cron_expression!r}")
    minute = int(parts[0])
    hour = int(parts[1])
    return minute, hour


# ---------------------------------------------------------------------------
# should_run_schedule
# ---------------------------------------------------------------------------


def should_run_schedule(
    schedule: ReportSchedule,
    now: datetime,
    timezone: str,
) -> bool:
    """Return True if *schedule* is due at *now* (UTC-aware) in *timezone*.

    Matching rule: the local time (in *timezone*) has the same hour and minute
    as specified in the cron expression, AND we are within the current minute
    tick (seconds < 60 — always true for a valid datetime, but the spec
    explicitly documents this as the window guard).

    Returns False immediately if schedule.enabled is False.
    """
    if not schedule.enabled:
        return False

    cron_minute, cron_hour = _parse_cron(schedule.cron_expression)

    tz = ZoneInfo(timezone)
    local_now = now.astimezone(tz)

    return local_now.hour == cron_hour and local_now.minute == cron_minute


# ---------------------------------------------------------------------------
# next_daily_run
# ---------------------------------------------------------------------------


def next_daily_run(
    schedule: ReportSchedule,
    after: datetime,
    timezone: str,
) -> datetime:
    """Return the next UTC datetime (after *after*) when *schedule* fires.

    *after* must be UTC-aware.  The result is also UTC-aware.

    Algorithm:
    1. Convert *after* to local time in *timezone*.
    2. Build today's candidate fire time (same calendar date, cron H:M).
    3. If that candidate is strictly after *after* (in UTC), return it.
    4. Otherwise add one day and return tomorrow's fire time.
    """
    cron_minute, cron_hour = _parse_cron(schedule.cron_expression)

    tz = ZoneInfo(timezone)
    local_after = after.astimezone(tz)

    # Today's candidate in local time
    today_local = local_after.replace(
        hour=cron_hour,
        minute=cron_minute,
        second=0,
        microsecond=0,
    )

    # Convert candidate to UTC for comparison
    today_utc = today_local.astimezone(UTC)

    if today_utc > after:
        return today_utc

    # Tomorrow
    tomorrow_local = today_local + timedelta(days=1)
    return tomorrow_local.astimezone(UTC)


# ---------------------------------------------------------------------------
# due_schedules
# ---------------------------------------------------------------------------


def due_schedules(
    schedules: list[ReportSchedule],
    now: datetime,
    business_configs: dict[str, BusinessConfig],
) -> list[ScheduledReportRun]:
    """Return a list of ScheduledReportRun for every schedule that is due now.

    Rules:
    - Disabled schedules are skipped.
    - Schedules whose business_id is absent from *business_configs* are skipped
      (no KeyError raised).
    - *now* must be UTC-aware; run_at in each ScheduledReportRun is set to *now*.
    """
    runs: list[ScheduledReportRun] = []

    for sched in schedules:
        if not sched.enabled:
            continue

        biz = business_configs.get(sched.business_id)
        if biz is None:
            continue

        if should_run_schedule(sched, now, biz.timezone):
            runs.append(
                ScheduledReportRun(
                    schedule_id=sched.schedule_id,
                    business_id=sched.business_id,
                    report_type=sched.report_type,
                    run_at=now,
                )
            )

    return runs
