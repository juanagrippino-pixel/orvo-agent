"""Tests for SQLite-backed config and idempotency stores.

TDD: tests written BEFORE implementation — verified RED first.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.brain.storage import SQLiteConfigStore, SQLiteIdempotencyStore, init_schema
from app.brain.config import BusinessConfig, ReportSchedule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    yield c
    c.close()


@pytest.fixture
def store(conn):
    return SQLiteConfigStore(conn)


@pytest.fixture
def idempotency(conn):
    return SQLiteIdempotencyStore(conn)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(business_id: str = "biz1") -> BusinessConfig:
    return BusinessConfig(
        business_id=business_id,
        business_name="Tienda Test",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
    )


def make_schedule(schedule_id: str = "sched1", business_id: str = "biz1") -> ReportSchedule:
    return ReportSchedule(
        schedule_id=schedule_id,
        business_id=business_id,
        cron_expression="0 8 * * *",
        report_type="daily",
    )


# ---------------------------------------------------------------------------
# init_schema tests
# ---------------------------------------------------------------------------


def test_init_schema_creates_tables_idempotently():
    """Calling init_schema twice must not raise and tables must exist."""
    c = sqlite3.connect(":memory:")
    init_schema(c)
    init_schema(c)  # second call — must be a no-op, not raise

    # Verify all three tables exist
    cursor = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert "business_configs" in tables
    assert "report_schedules" in tables
    assert "idempotency_keys" in tables
    c.close()


# ---------------------------------------------------------------------------
# SQLiteConfigStore — BusinessConfig tests
# ---------------------------------------------------------------------------


def test_sqlite_config_store_save_and_load_business_config(store):
    cfg = make_config("biz1")
    store.save_business_config(cfg)
    loaded = store.load_business_config("biz1")
    assert loaded is not None
    assert loaded.business_id == "biz1"
    assert loaded.business_name == "Tienda Test"
    assert loaded.owner_phone == "+5491112345678"
    assert loaded.timezone == "America/Argentina/Buenos_Aires"
    assert loaded.currency == "ARS"


def test_sqlite_config_store_load_missing_returns_none(store):
    result = store.load_business_config("nonexistent")
    assert result is None


def test_sqlite_config_store_save_overwrites_existing(store):
    cfg1 = make_config("biz1")
    store.save_business_config(cfg1)

    # Build a second BusinessConfig with same id but different name
    cfg2 = BusinessConfig(
        business_id="biz1",
        business_name="Tienda Actualizada",
        owner_phone="+5491112345678",
        timezone="America/Argentina/Buenos_Aires",
        currency="USD",
    )
    store.save_business_config(cfg2)

    loaded = store.load_business_config("biz1")
    assert loaded is not None
    assert loaded.business_name == "Tienda Actualizada"
    assert loaded.currency == "USD"


def test_sqlite_config_store_delete_business_config(store):
    cfg = make_config("biz1")
    store.save_business_config(cfg)
    store.delete_business_config("biz1")
    assert store.load_business_config("biz1") is None


def test_sqlite_config_store_delete_nonexistent_is_noop(store):
    # Must not raise even if key does not exist
    store.delete_business_config("ghost")


def test_sqlite_config_store_list_business_configs_empty(store):
    result = store.list_business_configs()
    assert result == []


def test_sqlite_config_store_list_business_configs_returns_all(store):
    store.save_business_config(make_config("biz1"))
    store.save_business_config(make_config("biz2"))
    store.save_business_config(make_config("biz3"))

    result = store.list_business_configs()
    assert len(result) == 3
    ids = {c.business_id for c in result}
    assert ids == {"biz1", "biz2", "biz3"}


# ---------------------------------------------------------------------------
# SQLiteConfigStore — ReportSchedule tests
# ---------------------------------------------------------------------------


def test_sqlite_config_store_save_and_load_schedule(store):
    sched = make_schedule("sched1", "biz1")
    store.save_schedule(sched)
    loaded = store.load_schedule("sched1")
    assert loaded is not None
    assert loaded.schedule_id == "sched1"
    assert loaded.business_id == "biz1"
    assert loaded.cron_expression == "0 8 * * *"
    assert loaded.report_type == "daily"


def test_sqlite_config_store_load_missing_schedule_returns_none(store):
    result = store.load_schedule("no-such-schedule")
    assert result is None


def test_sqlite_config_store_delete_schedule(store):
    sched = make_schedule("sched1", "biz1")
    store.save_schedule(sched)
    store.delete_schedule("sched1")
    assert store.load_schedule("sched1") is None


def test_sqlite_config_store_list_schedules_filters_by_business_id(store):
    store.save_schedule(make_schedule("s1", "biz1"))
    store.save_schedule(make_schedule("s2", "biz1"))
    store.save_schedule(make_schedule("s3", "biz2"))

    biz1_scheds = store.list_schedules("biz1")
    biz2_scheds = store.list_schedules("biz2")
    biz3_scheds = store.list_schedules("biz3")

    assert len(biz1_scheds) == 2
    assert all(s.business_id == "biz1" for s in biz1_scheds)
    assert len(biz2_scheds) == 1
    assert biz2_scheds[0].schedule_id == "s3"
    assert biz3_scheds == []


# ---------------------------------------------------------------------------
# SQLiteIdempotencyStore tests
# ---------------------------------------------------------------------------


def test_sqlite_idempotency_store_has_returns_false_for_new_key(idempotency):
    assert idempotency.has("brand-new-key") is False


def test_sqlite_idempotency_store_mark_and_has(idempotency):
    idempotency.mark("my-key")
    assert idempotency.has("my-key") is True


def test_sqlite_idempotency_store_mark_twice_is_idempotent(idempotency):
    """Marking the same key twice must not raise (INSERT OR IGNORE)."""
    idempotency.mark("dup-key")
    idempotency.mark("dup-key")  # second call — no error
    assert idempotency.has("dup-key") is True


def test_sqlite_idempotency_store_different_keys_independent(idempotency):
    idempotency.mark("key-a")
    assert idempotency.has("key-a") is True
    assert idempotency.has("key-b") is False
    idempotency.mark("key-b")
    assert idempotency.has("key-b") is True
    assert idempotency.has("key-a") is True  # key-a still present
