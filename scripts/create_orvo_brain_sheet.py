"""Create a native Google Sheet with seed data for Orvo Brain."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = Path.home() / ".hermes" / "google_token.json"
CLIENT_SECRET_PATH = Path.home() / ".hermes" / "google_client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def load_credentials() -> Credentials:
    client = json.loads(CLIENT_SECRET_PATH.read_text())
    client_info = client.get("installed") or client.get("web") or client
    token = json.loads(TOKEN_PATH.read_text())
    return Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=client_info["client_id"],
        client_secret=client_info["client_secret"],
        scopes=token.get("scopes") or SCOPES,
    )


def main() -> None:
    service = build("sheets", "v4", credentials=load_credentials())
    title = "Orvo Brain - Artemea Control Plane"
    spreadsheet = {
        "properties": {"title": title, "locale": "es_AR", "timeZone": "America/Argentina/Buenos_Aires"},
        "sheets": [{"properties": {"title": "Daily", "gridProperties": {"rowCount": 1000, "columnCount": 8}}}],
    }
    created = service.spreadsheets().create(body=spreadsheet, fields="spreadsheetId,spreadsheetUrl,sheets.properties.sheetId").execute()
    spreadsheet_id = created["spreadsheetId"]
    sheet_id = created["sheets"][0]["properties"]["sheetId"]

    today = date.today()
    rows: list[list[object]] = [["fecha", "ventas", "ordenes", "stock", "conversaciones_sin_responder", "gasto_ads", "notas"]]
    seed = [
        (today - timedelta(days=7), 104000, 14, 22, 1, 18000, "baseline semana anterior"),
        (today - timedelta(days=6), 98000, 13, 19, 1, 17500, "baseline semana anterior"),
        (today - timedelta(days=5), 112000, 16, 17, 2, 19000, "baseline semana anterior"),
        (today - timedelta(days=4), 106000, 14, 16, 1, 18000, "baseline semana anterior"),
        (today - timedelta(days=3), 101000, 13, 12, 3, 18500, "baseline semana anterior"),
        (today - timedelta(days=2), 99000, 12, 10, 2, 18200, "baseline semana anterior"),
        (today - timedelta(days=1), 95000, 11, 9, 3, 17600, "baseline ayer"),
        (today, 70000, 8, 3, 8, 18500, "día actual: dispara caída ventas, stock bajo y mensajes pendientes"),
    ]
    rows.extend([[d.isoformat(), revenue, orders, stock, unanswered, ads, notes] for d, revenue, orders, stock, unanswered, ads, notes in seed])

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Daily!A1:G9",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1}, "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.95, "blue": 1.0}}}, "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
                {"autoResizeDimensions": {"dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 7}}},
                {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
            ]
        },
    ).execute()

    print(json.dumps({"spreadsheet_id": spreadsheet_id, "url": created["spreadsheetUrl"], "range_name": "Daily!A1:G1000"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
