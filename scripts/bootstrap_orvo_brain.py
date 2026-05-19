"""Bootstrap the local Orvo Brain config database."""

from __future__ import annotations

import argparse
import json
import os

from app.brain.bootstrap import open_brain_sqlite_store, upsert_artemea_google_sheets_config

DEFAULT_SHEET_ID = "1OO5fEVKraXKkiofZ0EtHpEOUPgHMxym-Y82VPwtRtG0"
DEFAULT_RANGE = "Daily!A1:G1000"
DEFAULT_OWNER_PHONE = "+5491149724933"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Orvo Brain runtime config")
    parser.add_argument("--db", default=os.environ.get("ORVO_BRAIN_DB_PATH", "orvo_brain.sqlite3"))
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SHEET_ID)
    parser.add_argument("--range-name", default=DEFAULT_RANGE)
    parser.add_argument("--owner-phone", default=os.environ.get("ORVO_BRAIN_OWNER_PHONE", DEFAULT_OWNER_PHONE))
    args = parser.parse_args()

    conn, store = open_brain_sqlite_store(args.db)
    try:
        business, schedule = upsert_artemea_google_sheets_config(
            store,
            spreadsheet_id=args.spreadsheet_id,
            range_name=args.range_name,
            owner_phone=args.owner_phone,
        )
        print(
            json.dumps(
                {
                    "db": args.db,
                    "business": business.model_dump(mode="json"),
                    "schedule": schedule.model_dump(mode="json"),
                },
                ensure_ascii=False,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
