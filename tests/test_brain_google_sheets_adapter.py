from datetime import date


def test_rows_to_records_maps_headers_and_values():
    from app.brain.adapters.google_sheets import rows_to_records

    rows = [
        ["Fecha", "Ventas", "Órdenes", "Stock"],
        ["2026-05-19", "70000", "12", "3"],
        ["2026-05-18", "100000"],
    ]

    records = rows_to_records(rows)

    assert records[0] == {
        "date": "2026-05-19",
        "revenue": "70000",
        "orders": "12",
        "stock_units": "3",
    }
    assert records[1]["date"] == "2026-05-18"
    assert records[1]["revenue"] == "100000"


def test_parse_number_supports_argentine_formats():
    from app.brain.adapters.google_sheets import parse_number

    assert parse_number("120000") == 120000
    assert parse_number("120.000") == 120000
    assert parse_number("$ 120.000") == 120000
    assert parse_number("120000,50") == 120000.5
    assert parse_number(15) == 15
    assert parse_number(15.5) == 15.5
    assert parse_number("") is None


def test_build_metrics_from_sheet_records_generates_cited_metrics():
    from app.brain.adapters.google_sheets import build_metrics_from_sheet_records

    records = [
        {"date": "2026-05-19", "revenue": "70000", "orders": "12", "stock_units": "3", "unanswered_conversations": "8"},
        {"date": "2026-05-18", "revenue": "100000"},
        {"date": "2026-05-17", "revenue": "90000"},
    ]

    metrics = build_metrics_from_sheet_records(
        records,
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        source_label="Sheet Artemea",
        spreadsheet_id="abc123",
        range_name="Daily!A1:F1000",
    )
    by_key = {metric.key: metric for metric in metrics}

    assert by_key["revenue_today"].value == 70000
    assert by_key["revenue_baseline"].value == 95000
    assert by_key["orders_today"].value == 12
    assert by_key["stock_units"].value == 3
    assert by_key["unanswered_conversations"].value == 8
    assert all(metric.evidence[0].source == "google_sheets" for metric in metrics)
    assert str(metrics[0].evidence[0].url) == "https://docs.google.com/spreadsheets/d/abc123"


def test_build_daily_report_from_sheet_uses_mock_service():
    from app.brain.adapters.google_sheets import build_daily_report_from_sheet

    class FakeExecute:
        def execute(self):
            return {
                "values": [
                    ["fecha", "ventas", "ordenes", "stock", "conversaciones_sin_responder"],
                    ["2026-05-19", "70000", "12", "3", "8"],
                    ["2026-05-18", "100000", "10", "10", "1"],
                ]
            }

    class FakeValues:
        def get(self, spreadsheetId, range):
            assert spreadsheetId == "abc123"
            assert range == "Daily!A1:F1000"
            return FakeExecute()

    class FakeSpreadsheets:
        def values(self):
            return FakeValues()

    class FakeService:
        def spreadsheets(self):
            return FakeSpreadsheets()

    report = build_daily_report_from_sheet(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        spreadsheet_id="abc123",
        range_name="Daily!A1:F1000",
        service=FakeService(),
    )

    assert report.business_name == "Artemea"
    assert len(report.metrics) == 5
    assert len(report.insights) == 3
