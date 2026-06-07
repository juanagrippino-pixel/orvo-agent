from __future__ import annotations

import sqlite3

import pytest

from app.brain import operator_views
from app.brain.operational_cases import SQLiteOperationalCaseStore
from app.brain.operator_api import OperatorAPIError
from app.brain.operator_views import parse_case_jql
from app.brain.storage import init_schema
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


def test_parse_case_jql_uses_canonical_work_item_field_registry():
    assert not hasattr(operator_views, "_FIELD_SPECS")
    assert parse_case_jql("priority_score >= 80 ORDER BY priority_score DESC").normalized == (
        "priority_score >= 80 ORDER BY priority_score DESC"
    )
    assert parse_case_jql("priority_bracket = high").normalized == (
        "priority_bracket = high ORDER BY priority_score DESC, opened_at ASC"
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


def test_parse_case_jql_supports_work_item_projection_fields():
    assert parse_case_jql("project = ARTEMEA AND issue_type = stockout_risk AND status_category = to_do").normalized == (
        "project = ARTEMEA AND issue_type = stockout_risk AND status_category = to_do "
        "ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("assignee_ref = operator:juan").normalized == (
        "assignee_ref = operator:juan ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("status_category IN (to_do, done)").normalized == (
        "status_category IN (to_do, done) ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql(
        "acknowledgment_due_at <= 2026-05-24T09:00:00+00:00 ORDER BY acknowledgment_due_at ASC"
    ).normalized == (
        "acknowledgment_due_at <= 2026-05-24T09:00:00+00:00 ORDER BY acknowledgment_due_at ASC"
    )
    assert parse_case_jql("resolution_due_at > 2026-05-25T08:00:00Z ORDER BY resolution_due_at DESC").normalized == (
        "resolution_due_at > 2026-05-25T08:00:00+00:00 ORDER BY resolution_due_at DESC"
    )

    with pytest.raises(OperatorAPIError) as unsupported_category:
        parse_case_jql("status_category = waiting")
    assert unsupported_category.value.code == "unsupported_jql_value"


def test_internal_case_queue_filters_and_sorts_by_sla_due_fields(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    high = _seed_case(db_path, _case_detection(run_id="run-high", priority=95))
    medium = _seed_case(
        db_path,
        _case_detection(
            run_id="run-medium",
            dedupe_suffix="stockout_risk/sku/MEDIUM/commerce.inventory/daily",
            priority=70,
            severity="warning",
            title="Riesgo de stock medio",
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-other",
            dedupe_suffix="stockout_risk/sku/OTHER/commerce.inventory/daily",
            business_id="other",
            priority=95,
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={
            "jql": "acknowledgment_due_at <= 2026-05-24T11:00:00Z ORDER BY acknowledgment_due_at DESC"
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        "acknowledgment_due_at <= 2026-05-24T11:00:00+00:00 ORDER BY acknowledgment_due_at DESC"
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [medium.case_id, high.case_id]
    due_times = [case["work_item"]["acknowledgment_due_at"] for case in body["data"]["cases"]]
    assert due_times == ["2026-05-24T11:00:00Z", "2026-05-24T09:00:00Z"]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


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


def test_internal_case_queue_redacts_secret_shaped_jql_echo(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-jql-redaction"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "assignee_ref = token:raw_jql_secret"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_jql_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["redaction_applied"] is True
    assert body["data"]["jql"] == "assignee_ref = token:[REDACTED]"
    assert body["data"]["normalized_jql"] == "assignee_ref = token:[REDACTED] ORDER BY priority_score DESC, opened_at ASC"
    assert body["data"]["cases"] == []


def test_internal_case_queue_redacts_secret_shaped_jql_error_messages(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-jql-error-redaction"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "status = token:raw_jql_error_secret"},
    )

    assert response.status_code == 400
    raw_body = response.get_data(as_text=True)
    assert "raw_jql_error_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["redaction_applied"] is True
    assert body["error"]["code"] == "unsupported_jql_value"
    assert body["error"]["safe_to_show_owner"] is False
    assert "[REDACTED]" in body["error"]["message"]


def test_internal_case_queue_filters_by_work_item_fields_and_projects_work_item(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-open", priority=95))
    assigned = _seed_case(
        db_path,
        _case_detection(
            run_id="run-assigned",
            dedupe_suffix="stockout_risk/sku/ASSIGNED/commerce.inventory/daily",
            priority=90,
        ),
    )
    resolved = _seed_case(
        db_path,
        _case_detection(
            run_id="run-resolved",
            dedupe_suffix="stockout_risk/sku/RESOLVED/commerce.inventory/daily",
            priority=100,
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other", priority=99))

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.assign_case(
        assigned.case_id,
        actor_type="operator",
        actor_ref="operator:juan",
        assignee_ref="operator:juan",
    )
    store.transition_case(
        assigned.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator:juan",
    )
    store.transition_case(
        resolved.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator:juan",
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:juan",
        reason="fixture complete",
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql="
        "project%20%3D%20ARTEMEA%20AND%20issue_type%20%3D%20stockout_risk%20AND%20"
        "status_category%20%3D%20in_progress%20AND%20priority_bracket%20%3D%20high%20AND%20"
        "assignee_ref%20%3D%20operator:juan",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        "project = ARTEMEA AND issue_type = stockout_risk AND status_category = in_progress "
        "AND priority_bracket = high AND assignee_ref = operator:juan ORDER BY priority_score DESC, opened_at ASC"
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [assigned.case_id]
    case = body["data"]["cases"][0]
    assert case["project_key"] == "ARTEMEA"
    assert case["issue_type"] == "stockout_risk"
    assert case["status_category"] == "in_progress"
    assert case["work_item"]["case_id"] == assigned.case_id
    assert case["work_item"]["work_item_id"] == f"ARTEMEA:{assigned.case_id}"
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
    assert body["data"]["total"] == 1
    assert body["data"]["truncated"] is False
    assert [case["case_id"] for case in body["data"]["cases"]] == [critical.case_id]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])
    assert body["redaction_applied"] is True


def test_internal_case_queue_jql_reports_scoped_total_and_truncation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    top_case = _seed_case(db_path, _case_detection(run_id="run-top", priority=95))
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-lower",
            dedupe_suffix="stockout_risk/sku/LOW/inventory.on_hand/daily",
            priority=80,
            title="Riesgo de stock menor",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other", priority=99))

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=status%20%3D%20open&limit=1",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["count"] == 1
    assert body["data"]["total"] == 2
    assert body["data"]["truncated"] is True
    assert body["data"]["limit"] == 1
    assert [case["case_id"] for case in body["data"]["cases"]] == [top_case.case_id]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


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
