def test_daily_brain_report_endpoint_returns_text_metrics_and_insights():
    from server import app

    client = app.test_client()
    response = client.post(
        "/brain/reports/daily",
        json={
            "business_name": "Artemea",
            "report_date": "2026-05-19",
            "source_label": "Sheet Artemea mayo",
            "metrics": {
                "revenue_today": 70000,
                "revenue_baseline": 100000,
                "stock_units": 3,
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "ARTEMEA · 2026-05-19" in body["text"]
    assert "Orvo Brain" not in body["text"]
    assert body["report"]["business_name"] == "Artemea"
    assert len(body["report"]["metrics"]) == 3
    assert len(body["report"]["insights"]) == 2


def test_daily_brain_report_endpoint_rejects_empty_payload():
    from server import app

    client = app.test_client()
    response = client.post("/brain/reports/daily", json={})

    assert response.status_code == 400
    assert "error" in response.get_json()
