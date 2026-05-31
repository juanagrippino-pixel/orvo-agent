from __future__ import annotations

import pytest

from app.brain.operator_api import OperatorAPIError
from app.brain.operator_views import parse_case_jql
from tests.test_internal_operator_api import AUTH, _case_detection, _client, _seed_case


def _case_detection_with_source(*, source: str, run_id: str, freshness_state: str = "fresh", **kwargs):
    detection = _case_detection(run_id=run_id, **kwargs)
    snapshot = detection.evidence_snapshots[0].model_copy(
        update={
            "snapshot_key": f"{run_id}/evidence://{source}/{run_id}/{detection.case_type}/{detection.case_type}/business/monitored",
            "source": source,
            "source_label": source,
            "evidence_ref": f"evidence://{source}/{run_id}/{detection.case_type}",
            "freshness_state": freshness_state,
        }
    )
    return detection.model_copy(
        update={
            "evidence_refs": [f"evidence://{source}/{run_id}/{detection.case_type}"],
            "evidence_snapshots": [snapshot],
        }
    )


def test_parse_case_jql_rejects_business_scope_and_unsupported_values():
    with pytest.raises(OperatorAPIError) as business_scope:
        parse_case_jql("business_id = other")
    assert business_scope.value.code == "unsupported_jql_field"

    assert parse_case_jql("status = in_progress").normalized == (
        "status = in_progress ORDER BY priority_score DESC, opened_at ASC"
    )

    with pytest.raises(OperatorAPIError) as unsupported_status:
        parse_case_jql("status = blocked")
    assert unsupported_status.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("status = open; DROP TABLE operational_cases")
    assert sql_shape.value.code == "invalid_jql"


def test_parse_case_jql_supports_source_connector_allowlist_filter():
    assert parse_case_jql("source_connector IN (tiendanube, meta_ads)").normalized == (
        "source_connector IN (tiendanube, meta_ads) ORDER BY priority_score DESC, opened_at ASC"
    )

    with pytest.raises(OperatorAPIError) as unsupported_operator:
        parse_case_jql("source_connector > tiendanube")
    assert unsupported_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("source_connector = meta_ads; DROP TABLE operational_cases")
    assert sql_shape.value.code == "invalid_jql"


def test_parse_case_jql_supports_degraded_boolean_filter():
    assert parse_case_jql("degraded = true").normalized == "degraded = true ORDER BY priority_score DESC, opened_at ASC"
    assert parse_case_jql("degraded != false").normalized == "degraded != false ORDER BY priority_score DESC, opened_at ASC"

    with pytest.raises(OperatorAPIError) as unsupported_operator:
        parse_case_jql("degraded > true")
    assert unsupported_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as unsupported_value:
        parse_case_jql("degraded = yes")
    assert unsupported_value.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("degraded = true OR 1 = 1")
    assert sql_shape.value.code == "invalid_jql"


def test_internal_case_queue_filters_by_source_connector_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection_with_source(source="tiendanube", run_id="run-tn"))
    meta_case = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-meta",
            case_type="spend_without_orders",
            dedupe_suffix="spend_without_orders/channel/meta_ads/marketing.spend/daily",
            severity="warning",
            priority=75,
            title="Meta Ads sin ventas",
        ),
    )
    _seed_case(db_path, _case_detection_with_source(source="meta_ads", run_id="run-other", business_id="other"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=source_connector%20%3D%20meta_ads",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "source_connector = meta_ads ORDER BY priority_score DESC, opened_at ASC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [meta_case.case_id]
    assert body["data"]["cases"][0]["source_connectors"] == ["meta_ads"]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


def test_internal_case_queue_filters_degraded_cases_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection_with_source(source="tiendanube", run_id="run-fresh"))
    degraded_case = _seed_case(
        db_path,
        _case_detection_with_source(source="meta_ads", run_id="run-stale", freshness_state="stale"),
    )
    _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-other",
            freshness_state="missing",
            business_id="other",
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=degraded%20%3D%20true",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "degraded = true ORDER BY priority_score DESC, opened_at ASC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [degraded_case.case_id]
    assert body["data"]["cases"][0]["degraded"] is True
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


def test_internal_case_queue_accepts_safe_jql_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    critical = _seed_case(db_path, _case_detection(run_id="run-critical"))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=80,
            title="Ventas bajaron",
            run_id="run-warning",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=status%20%3D%20open%20AND%20severity%20%3D%20critical",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["jql"] == "status = open AND severity = critical"
    assert body["data"]["normalized_jql"] == "status = open AND severity = critical ORDER BY priority_score DESC, opened_at ASC"
    assert body["data"]["count"] == 1
    assert [case["case_id"] for case in body["data"]["cases"]] == [critical.case_id]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])
    assert body["redaction_applied"] is True


def test_internal_case_queue_rejects_conflicting_filters_and_invalid_jql(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())

    conflict = client.get(
        "/internal/brain/businesses/artemea/cases?status=open&jql=status%20%3D%20open",
        headers=AUTH,
    )
    invalid = client.get(
        "/internal/brain/businesses/artemea/cases?jql=business_id%20%3D%20other%20AND%20access_token%3Draw_jql_secret",
        headers=AUTH,
    )

    assert conflict.status_code == 400
    assert conflict.get_json()["error"]["code"] == "conflicting_case_filters"
    assert invalid.status_code == 400
    raw_invalid = invalid.get_data(as_text=True)
    assert "raw_jql_secret" not in raw_invalid
    assert invalid.get_json()["error"]["code"] == "unsupported_jql_field"


def test_internal_case_views_list_readonly_builtin_views(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-views", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    views = {view["view_id"]: view for view in body["data"]["views"]}
    assert {"open_cases", "in_progress_cases", "critical_open", "data_stale", "stockout_risk", "connector_degraded"}.issubset(
        views
    )
    assert views["connector_degraded"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND degraded = true ORDER BY updated_at DESC"
    )
    assert all(view["readonly"] is True for view in views.values())
    assert "business_id" not in " ".join(view["jql"] for view in views.values())
    assert body["redaction_applied"] is True


def test_internal_case_view_execution_matches_equivalent_jql(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    critical = _seed_case(db_path, _case_detection(run_id="run-critical"))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=80,
            title="Ventas bajaron",
            run_id="run-warning",
        ),
    )

    view_response = client.get("/internal/brain/businesses/artemea/case-views/critical_open/cases", headers=AUTH)
    direct_response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=status%20%3D%20open%20AND%20severity%20%3D%20critical%20ORDER%20BY%20priority_score%20DESC",
        headers=AUTH,
    )

    assert view_response.status_code == 200
    assert direct_response.status_code == 200
    view_body = view_response.get_json()
    direct_body = direct_response.get_json()
    assert view_body["data"]["view"]["view_id"] == "critical_open"
    assert view_body["data"]["cases"] == direct_body["data"]["cases"]
    assert [case["case_id"] for case in view_body["data"]["cases"]] == [critical.case_id]


def test_internal_case_view_unknown_view_returns_enveloped_404(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-views/missing/cases", headers=AUTH)

    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "case_view_not_found"
    assert body["redaction_applied"] is True
