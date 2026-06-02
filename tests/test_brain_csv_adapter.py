from datetime import date


def test_build_daily_report_from_csv_file_generates_cited_report(tmp_path):
    from app.brain.adapters.csv_file import build_daily_report_from_csv_file

    csv_path = tmp_path / "artemea.csv"
    csv_path.write_text(
        "fecha,ventas,ordenes,stock,conversaciones_sin_responder,gasto_ads\n"
        "2026-05-18,100000,10,10,1,17000\n"
        "2026-05-19,70000,8,3,8,18500\n"
    )

    report = build_daily_report_from_csv_file(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        csv_path=str(csv_path),
    )

    by_key = {metric.key: metric for metric in report.metrics}
    assert by_key["revenue_today"].value == 70000
    assert by_key["revenue_baseline"].value == 100000
    assert by_key["orders_today"].value == 8
    assert by_key["stock_units"].value == 3
    assert by_key["unanswered_conversations"].value == 8
    assert by_key["ad_spend_today"].value == 18500
    assert report.insights
    assert report.metrics[0].evidence[0].source == "csv"
    assert str(csv_path) in report.metrics[0].evidence[0].label


def test_build_daily_report_from_csv_file_rejects_missing_file(tmp_path):
    import pytest
    from app.brain.adapters.csv_file import build_daily_report_from_csv_file

    with pytest.raises(FileNotFoundError):
        build_daily_report_from_csv_file(
            business_name="Artemea",
            report_date=date(2026, 5, 19),
            csv_path=str(tmp_path / "missing.csv"),
        )
