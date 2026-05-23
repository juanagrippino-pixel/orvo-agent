import sqlite3
from datetime import datetime, timezone



def test_upsert_artemea_google_sheets_config_persists_business_and_daily_schedule():
    from app.brain.bootstrap import upsert_artemea_google_sheets_config
    from app.brain.storage import SQLiteConfigStore, init_schema

    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    store = SQLiteConfigStore(conn)

    business, schedule = upsert_artemea_google_sheets_config(
        store,
        spreadsheet_id="sheet123",
        range_name="Daily!A1:G1000",
        owner_phone="+5491149724933",
    )

    loaded = store.load_business_config("artemea")
    schedules = store.list_schedules("artemea")

    assert loaded == business
    assert business.business_name == "Artemea"
    assert business.owner_phone == "+5491149724933"
    assert business.connectors[0].connector_type == "google_sheets"
    assert business.connectors[0].params == {"spreadsheet_id": "sheet123", "range_name": "Daily!A1:G1000"}
    assert schedules == [schedule]
    assert schedule.schedule_id == "artemea-daily-report"
    assert schedule.report_type == "daily"
    assert schedule.cron_expression == "0 8 * * *"

    from app.brain.scheduler import next_daily_run

    next_run = next_daily_run(schedule, datetime(2026, 5, 22, 10, 55, tzinfo=timezone.utc), business.timezone)
    assert next_run == datetime(2026, 5, 22, 11, 0, tzinfo=timezone.utc)


def test_open_brain_sqlite_store_initializes_schema(tmp_path):
    from app.brain.bootstrap import open_brain_sqlite_store

    db_path = tmp_path / "brain.sqlite3"
    conn, store = open_brain_sqlite_store(str(db_path))

    assert db_path.exists()
    assert store.list_business_configs() == []
    conn.close()
