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


def _case_detection_with_evidence_count(*, evidence_count: int, run_id: str, **kwargs):
    detection = _case_detection(run_id=run_id, **kwargs)
    evidence_refs = [
        f"evidence://{detection.business_id}/{run_id}/{detection.case_type}/{index}"
        for index in range(evidence_count)
    ]
    return detection.model_copy(update={"evidence_refs": evidence_refs, "evidence_snapshots": []})


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

    with pytest.raises(OperatorAPIError) as empty_in_list:
        parse_case_jql("source_connector IN ()")
    assert empty_in_list.value.code == "invalid_jql"

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


def test_parse_case_jql_supports_evidence_freshness_state_filter():
    assert parse_case_jql("freshness_state IN (stale, missing)").normalized == (
        "freshness_state IN (stale, missing) ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("freshness_state != fresh").normalized == (
        "freshness_state != fresh ORDER BY priority_score DESC, opened_at ASC"
    )

    with pytest.raises(OperatorAPIError) as unsupported_operator:
        parse_case_jql("freshness_state > stale")
    assert unsupported_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as unsupported_value:
        parse_case_jql("freshness_state = expired")
    assert unsupported_value.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("freshness_state = stale OR 1 = 1")
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
    assert parse_case_jql("release_state = readiness_gated").normalized == (
        "release_state = readiness_gated ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("work_item_id = ARTEMEA:case-123").normalized == (
        "work_item_id = ARTEMEA:case-123 ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("priority_bracket IN (high, medium)").normalized == (
        "priority_bracket IN (high, medium) ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql('entity.label = "Campera Azul XL"').normalized == (
        'entity.label = "Campera Azul XL" ORDER BY priority_score DESC, opened_at ASC'
    )

    with pytest.raises(OperatorAPIError) as unsupported_category:
        parse_case_jql("status_category = waiting")
    assert unsupported_category.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as unsupported_release_state:
        parse_case_jql("release_state = experimental")
    assert unsupported_release_state.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as unsupported_priority_bracket:
        parse_case_jql("priority_bracket = urgent")
    assert unsupported_priority_bracket.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as unsupported_work_item_operator:
        parse_case_jql("work_item_id > ARTEMEA:case-123")
    assert unsupported_work_item_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("priority_bracket = high OR status = resolved")
    assert sql_shape.value.code == "invalid_jql"

    with pytest.raises(OperatorAPIError) as quoted_sql_shape:
        parse_case_jql('entity.label = "Campera Azul XL; DROP TABLE operational_cases"')
    assert quoted_sql_shape.value.code == "invalid_jql"


def test_internal_case_queue_filters_by_release_state(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    promoted = _seed_case(db_path, _case_detection(run_id="run-promoted", priority=95))
    readiness_gated = _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            title="Conversaciones sin responder",
            run_id="run-readiness-gated",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "release_state = readiness_gated"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "release_state = readiness_gated ORDER BY priority_score DESC, opened_at ASC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [readiness_gated.case_id]
    assert body["data"]["cases"][0]["release_state"] == "readiness_gated"
    assert body["data"]["cases"][0]["work_item"]["release_state"] == "readiness_gated"
    assert promoted.case_id not in [case["case_id"] for case in body["data"]["cases"]]


def test_parse_case_jql_supports_assigned_boolean_filter():
    assert parse_case_jql("assigned = false").normalized == "assigned = false ORDER BY priority_score DESC, opened_at ASC"
    assert parse_case_jql("assigned != true").normalized == "assigned != true ORDER BY priority_score DESC, opened_at ASC"

    with pytest.raises(OperatorAPIError) as unsupported_operator:
        parse_case_jql("assigned > false")
    assert unsupported_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as unsupported_value:
        parse_case_jql("assigned = maybe")
    assert unsupported_value.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("assigned = false OR assignee_ref = admin")
    assert sql_shape.value.code == "invalid_jql"


def test_parse_case_jql_supports_actionable_boolean_filter():
    assert parse_case_jql("actionable = true").normalized == "actionable = true ORDER BY priority_score DESC, opened_at ASC"
    assert parse_case_jql("actionable != false").normalized == "actionable != false ORDER BY priority_score DESC, opened_at ASC"

    with pytest.raises(OperatorAPIError) as unsupported_operator:
        parse_case_jql("actionable > true")
    assert unsupported_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as unsupported_value:
        parse_case_jql("actionable = probably")
    assert unsupported_value.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("actionable = true OR status = resolved")
    assert sql_shape.value.code == "invalid_jql"


def test_parse_case_jql_supports_evidence_count_filter():
    assert parse_case_jql("evidence_count >= 2").normalized == (
        "evidence_count >= 2 ORDER BY priority_score DESC, opened_at ASC"
    )

    with pytest.raises(OperatorAPIError) as unsupported_operator:
        parse_case_jql("evidence_count IN (1, 2)")
    assert unsupported_operator.value.code == "unsupported_jql_operator"

    with pytest.raises(OperatorAPIError) as unsupported_value:
        parse_case_jql("evidence_count = two")
    assert unsupported_value.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as sql_shape:
        parse_case_jql("evidence_count >= 1 OR 1 = 1")
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


def test_internal_case_queue_filters_by_evidence_freshness_state_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection_with_source(source="tiendanube", run_id="run-fresh", freshness_state="fresh"))
    stale_case = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-stale-filter",
            freshness_state="stale",
            dedupe_suffix="stockout_risk/sku/STALE_FILTER/inventory.on_hand/daily",
            priority=95,
        ),
    )
    missing_case = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-missing-filter",
            freshness_state="missing",
            dedupe_suffix="stockout_risk/sku/MISSING_FILTER/inventory.on_hand/daily",
            priority=90,
        ),
    )
    _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-other-stale-filter",
            freshness_state="stale",
            business_id="other",
            priority=99,
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=freshness_state%20IN%20(stale%2C%20missing)",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        "freshness_state IN (stale, missing) ORDER BY priority_score DESC, opened_at ASC"
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [stale_case.case_id, missing_case.case_id]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])

    not_fresh_response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=freshness_state%20!%3D%20fresh",
        headers=AUTH,
    )
    assert not_fresh_response.status_code == 200
    not_fresh_body = not_fresh_response.get_json()
    assert [case["case_id"] for case in not_fresh_body["data"]["cases"]] == [stale_case.case_id, missing_case.case_id]


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

    work_item_response = client.get(
        f"/internal/brain/businesses/artemea/cases?jql=work_item_id%20%3D%20ARTEMEA:{assigned.case_id}",
        headers=AUTH,
    )

    assert work_item_response.status_code == 200
    work_item_body = work_item_response.get_json()
    assert work_item_body["data"]["normalized_jql"] == (
        f"work_item_id = ARTEMEA:{assigned.case_id} ORDER BY priority_score DESC, opened_at ASC"
    )
    assert [case["case_id"] for case in work_item_body["data"]["cases"]] == [assigned.case_id]

    cross_project_response = client.get(
        f"/internal/brain/businesses/artemea/cases?jql=work_item_id%20%3D%20OTHER:{assigned.case_id}",
        headers=AUTH,
    )

    assert cross_project_response.status_code == 200
    cross_project_body = cross_project_response.get_json()
    assert cross_project_body["data"]["cases"] == []
    assert cross_project_body["data"]["total"] == 0


def test_internal_case_queue_filters_by_quoted_entity_label_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    matching = _seed_case(
        db_path,
        _case_detection(
            run_id="run-entity-label-quoted",
            dedupe_suffix="stockout_risk/sku/CAMPERA_AZUL_XL/commerce.inventory/daily",
            entity_scope={"kind": "sku", "id": "CAMPERA_AZUL_XL", "label": "Campera Azul XL"},
            priority=90,
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-entity-label-other",
            dedupe_suffix="stockout_risk/sku/CAMPERA_ROJA_M/commerce.inventory/daily",
            entity_scope={"kind": "sku", "id": "CAMPERA_ROJA_M", "label": "Campera Roja M"},
            priority=100,
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            business_id="other",
            run_id="run-entity-label-cross-tenant",
            entity_scope={"kind": "sku", "id": "CAMPERA_AZUL_XL", "label": "Campera Azul XL"},
            priority=99,
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": 'entity.label = "Campera Azul XL"'},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        'entity.label = "Campera Azul XL" ORDER BY priority_score DESC, opened_at ASC'
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [matching.case_id]
    assert body["data"]["cases"][0]["entity_scope"]["label"] == "Campera Azul XL"
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])

    injection_response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": 'entity.label = "Campera Azul XL; DROP TABLE operational_cases"'},
    )
    assert injection_response.status_code == 400
    assert injection_response.get_json()["error"]["code"] == "invalid_jql"


def test_internal_case_queue_filters_unassigned_actionable_cases_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    unassigned = _seed_case(
        db_path,
        _case_detection(
            run_id="run-unassigned",
            dedupe_suffix="stockout_risk/sku/UNASSIGNED/commerce.inventory/daily",
            priority=90,
        ),
    )
    assigned = _seed_case(
        db_path,
        _case_detection(
            run_id="run-assigned-unassigned-filter",
            dedupe_suffix="stockout_risk/sku/ASSIGNED_FILTER/commerce.inventory/daily",
            priority=100,
            title="Riesgo de stock asignado",
        ),
    )
    _seed_case(db_path, _case_detection(run_id="run-other", business_id="other", priority=99))

    assign_response = client.post(
        f"/internal/brain/businesses/artemea/cases/{assigned.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "assign-unassigned-filter"},
        json={"action_key": "assign_owner", "assignee_ref": "operator:ana"},
    )
    assert assign_response.status_code == 200

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=status%20IN%20(open%2C%20acknowledged%2C%20in_progress)%20AND%20assigned%20%3D%20false",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        "status IN (open, acknowledged, in_progress) AND assigned = false ORDER BY priority_score DESC, opened_at ASC"
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [unassigned.case_id]
    assert body["data"]["cases"][0]["assignee_ref"] is None
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])

    view_response = client.get(
        "/internal/brain/businesses/artemea/case-views/unassigned_actionable/cases",
        headers=AUTH,
    )
    assert view_response.status_code == 200
    view_body = view_response.get_json()
    assert view_body["data"]["view"]["view_id"] == "unassigned_actionable"
    assert view_body["data"]["cases"] == body["data"]["cases"]


def test_internal_case_queue_filters_actionable_cases_and_builtin_view_matches_direct_jql(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    open_case = _seed_case(db_path, _case_detection(run_id="run-open", priority=90))
    acknowledged = _seed_case(
        db_path,
        _case_detection(
            run_id="run-ack",
            dedupe_suffix="stockout_risk/sku/ACK/inventory.on_hand/daily",
            priority=80,
            title="Riesgo de stock reconocido",
        ),
    )
    in_progress = _seed_case(
        db_path,
        _case_detection(
            run_id="run-progress",
            dedupe_suffix="stockout_risk/sku/PROGRESS/inventory.on_hand/daily",
            priority=95,
            title="Riesgo de stock en progreso",
        ),
    )
    resolved = _seed_case(
        db_path,
        _case_detection(
            run_id="run-resolved",
            dedupe_suffix="stockout_risk/sku/RESOLVED/inventory.on_hand/daily",
            priority=100,
            title="Riesgo de stock resuelto",
        ),
    )
    dismissed = _seed_case(
        db_path,
        _case_detection(
            run_id="run-dismissed",
            dedupe_suffix="stockout_risk/sku/DISMISSED/inventory.on_hand/daily",
            priority=99,
            title="Riesgo de stock descartado",
        ),
    )
    _seed_case(db_path, _case_detection(run_id="run-other", business_id="other", priority=98))

    ack_response = client.post(
        f"/internal/brain/businesses/artemea/cases/{acknowledged.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "ack-actionable-filter"},
        json={"action_key": "acknowledge_case", "reason": "En revisión"},
    )
    assert ack_response.status_code == 200
    progress_response = client.post(
        f"/internal/brain/businesses/artemea/cases/{in_progress.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "progress-actionable-filter"},
        json={"action_key": "mark_in_progress", "reason": "Tomado"},
    )
    assert progress_response.status_code == 200
    resolved_ack = client.post(
        f"/internal/brain/businesses/artemea/cases/{resolved.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "ack-resolved-actionable-filter"},
        json={"action_key": "acknowledge_case", "reason": "En revisión"},
    )
    assert resolved_ack.status_code == 200
    resolved_response = client.post(
        f"/internal/brain/businesses/artemea/cases/{resolved.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "resolve-actionable-filter"},
        json={"action_key": "resolve_case", "reason": "Resuelto"},
    )
    assert resolved_response.status_code == 200
    dismissed_response = client.post(
        f"/internal/brain/businesses/artemea/cases/{dismissed.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "dismiss-actionable-filter"},
        json={"action_key": "dismiss_case", "reason": "No aplica"},
    )
    assert dismissed_response.status_code == 200

    direct_response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=actionable%20%3D%20true",
        headers=AUTH,
    )
    view_response = client.get(
        "/internal/brain/businesses/artemea/case-views/actionable_cases/cases",
        headers=AUTH,
    )

    assert direct_response.status_code == 200
    assert view_response.status_code == 200
    direct_body = direct_response.get_json()
    view_body = view_response.get_json()
    expected_case_ids = [in_progress.case_id, open_case.case_id, acknowledged.case_id]
    assert direct_body["data"]["normalized_jql"] == "actionable = true ORDER BY priority_score DESC, opened_at ASC"
    assert [case["case_id"] for case in direct_body["data"]["cases"]] == expected_case_ids
    assert all(case["status"] in {"open", "acknowledged", "in_progress"} for case in direct_body["data"]["cases"])
    assert all(case["business_id"] == "artemea" for case in direct_body["data"]["cases"])
    assert view_body["data"]["view"]["view_id"] == "actionable_cases"
    assert view_body["data"]["cases"] == direct_body["data"]["cases"]


def test_internal_case_queue_filters_by_priority_bracket_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    high_case = _seed_case(
        db_path,
        _case_detection(
            run_id="run-priority-high-query",
            dedupe_suffix="stockout_risk/sku/HIGH/query.priority/daily",
            priority=90,
        ),
    )
    medium_case = _seed_case(
        db_path,
        _case_detection(
            run_id="run-priority-medium-query",
            dedupe_suffix="stockout_risk/sku/MEDIUM/query.priority/daily",
            priority=65,
            title="Riesgo de stock medio",
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-priority-low-query",
            dedupe_suffix="stockout_risk/sku/LOW/query.priority/daily",
            priority=10,
            title="Riesgo de stock bajo",
        ),
    )
    _seed_case(db_path, _case_detection(run_id="run-other-priority-query", business_id="other", priority=95))

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "priority_bracket IN (high, medium)"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        "priority_bracket IN (high, medium) ORDER BY priority_score DESC, opened_at ASC"
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [high_case.case_id, medium_case.case_id]
    assert [case["work_item"]["priority_bracket"] for case in body["data"]["cases"]] == ["high", "medium"]
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


def test_internal_case_queue_filters_by_evidence_count_and_keeps_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection_with_evidence_count(evidence_count=1, run_id="run-one", priority=100))
    rich_evidence = _seed_case(
        db_path,
        _case_detection_with_evidence_count(
            evidence_count=2,
            run_id="run-two",
            dedupe_suffix="stockout_risk/sku/TWO_EVIDENCE/inventory.on_hand/daily",
            priority=90,
        ),
    )
    _seed_case(
        db_path,
        _case_detection_with_evidence_count(
            evidence_count=3,
            run_id="run-other-evidence",
            business_id="other",
            priority=99,
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=evidence_count%20%3E%3D%202",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "evidence_count >= 2 ORDER BY priority_score DESC, opened_at ASC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [rich_evidence.case_id]
    assert body["data"]["cases"][0]["evidence_count"] == 2
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])

    invalid = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "evidence_count = token:raw_evidence_secret"},
    )

    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "unsupported_jql_value"
    assert "raw_evidence_secret" not in invalid.get_data(as_text=True)


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


def test_internal_case_facets_group_by_work_item_registry_field_with_jql(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-high", priority=95))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            title="Ventas bajaron",
            run_id="run-medium",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other", priority=99))

    response = client.get(
        "/internal/brain/businesses/artemea/cases/facets",
        headers=AUTH,
        query_string={"field": "priority_bracket", "jql": "status = open"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["field"] == "priority_bracket"
    assert body["data"]["normalized_jql"] == "status = open ORDER BY priority_score DESC, opened_at ASC"
    assert body["data"]["total_cases"] == 2
    assert body["data"]["buckets"] == [
        {"value": "high", "count": 1},
        {"value": "medium", "count": 1},
    ]
    assert body["data"]["truncated"] is False
    assert body["redaction_applied"] is True


def test_internal_case_facets_support_source_connector_and_bucket_limit(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection_with_source(source="tiendanube", run_id="run-tn"))
    _seed_case(
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

    response = client.get(
        "/internal/brain/businesses/artemea/cases/facets",
        headers=AUTH,
        query_string={"field": "source_connector", "limit": "1"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["field"] == "source_connector"
    assert body["data"]["total_cases"] == 2
    assert body["data"]["returned"] == 1
    assert body["data"]["truncated"] is True
    assert body["data"]["buckets"] == [{"value": "meta_ads", "count": 1}]


def test_internal_case_facets_group_by_release_state(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-promoted"))
    _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            title="Conversaciones sin responder",
            run_id="run-readiness-gated",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases/facets",
        headers=AUTH,
        query_string={"field": "release_state", "jql": "status = open"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["field"] == "release_state"
    assert body["data"]["total_cases"] == 2
    assert body["data"]["buckets"] == [
        {"value": "promoted", "count": 1},
        {"value": "readiness_gated", "count": 1},
    ]


def test_internal_case_facets_reject_business_scope_and_redact_bad_field(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-facet-error"))

    business_scope = client.get(
        "/internal/brain/businesses/artemea/cases/facets",
        headers=AUTH,
        query_string={"field": "business_id"},
    )
    secret_field = client.get(
        "/internal/brain/businesses/artemea/cases/facets",
        headers=AUTH,
        query_string={"field": "token=raw_facet_secret"},
    )

    assert business_scope.status_code == 400
    assert business_scope.get_json()["error"]["code"] == "unsupported_facet_field"
    assert secret_field.status_code == 400
    assert secret_field.get_json()["error"]["code"] == "unsupported_facet_field"
    assert "raw_facet_secret" not in secret_field.get_data(as_text=True)


def test_internal_case_query_fields_exposes_canonical_registry_without_business_scope(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-query-fields", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["readonly"] is True
    assert body["data"]["scope"] == {
        "business_scope_source": "route",
        "query_controlled_business_scope": False,
    }
    fields = {field["field"]: field for field in body["data"]["fields"]}
    assert "business_id" not in fields
    assert fields["status"]["allowed_values"] == ["acknowledged", "dismissed", "in_progress", "open", "resolved"]
    assert fields["status"]["facetable"] is True
    assert fields["priority_score"]["operators"] == ["=", "!=", ">", ">=", "<", "<="]
    assert fields["priority_score"]["sortable"] is True
    assert fields["priority_score"]["facetable"] is False
    assert fields["source_connector"]["source"] == "evidence_projection"
    assert body["data"]["sort_fields"] == ["opened_at", "priority_score", "updated_at"]
    assert body["data"]["facet_fields"] == [
        "assigned",
        "assignee_ref",
        "case_type",
        "degraded",
        "entity.kind",
        "freshness_state",
        "priority_bracket",
        "severity",
        "source_connector",
        "status",
        "status_category",
    ]
    assert body["redaction_applied"] is True


def test_internal_case_query_fields_enforces_business_grants_without_echoing_secret_header(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/case-query-fields",
        headers={**AUTH, "X-Orvo-Businesses": "other,access_token=raw_query_field_secret"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"
    assert "raw_query_field_secret" not in response.get_data(as_text=True)


def test_internal_case_views_list_readonly_builtin_views(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-views", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    views = {view["view_id"]: view for view in body["data"]["views"]}
    assert {
        "open_cases",
        "in_progress_cases",
        "critical_open",
        "data_stale",
        "stockout_risk",
        "connector_degraded",
        "unassigned_actionable",
        "actionable_cases",
        "high_priority_actionable",
        "readiness_gated_actionable",
    }.issubset(views)
    assert views["actionable_cases"]["jql"] == "actionable = true ORDER BY priority_score DESC"
    assert views["high_priority_actionable"]["jql"] == (
        "actionable = true AND priority_bracket = high ORDER BY priority_score DESC"
    )
    assert views["readiness_gated_actionable"]["jql"] == (
        "release_state = readiness_gated AND actionable = true ORDER BY updated_at DESC"
    )
    assert views["connector_degraded"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND degraded = true ORDER BY updated_at DESC"
    )
    assert views["unassigned_actionable"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND assigned = false ORDER BY priority_score DESC"
    )
    assert all(view["readonly"] is True for view in views.values())
    assert all("total" not in view for view in views.values())
    assert "business_id" not in " ".join(view["jql"] for view in views.values())
    assert body["redaction_applied"] is True


def test_internal_high_priority_actionable_view_matches_jql_and_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    high = _seed_case(db_path, _case_detection(run_id="run-high-actionable", priority=95))
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-medium-actionable",
            priority=70,
            dedupe_suffix="stockout_risk/sku/MEDIUM_ACTIONABLE/inventory.on_hand/daily",
        ),
    )
    _seed_case(db_path, _case_detection(run_id="run-other-high", business_id="other", priority=99))

    view_response = client.get(
        "/internal/brain/businesses/artemea/case-views/high_priority_actionable/cases",
        headers=AUTH,
    )
    direct_response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "actionable = true AND priority_bracket = high ORDER BY priority_score DESC"},
    )

    assert view_response.status_code == 200
    assert direct_response.status_code == 200
    view_body = view_response.get_json()
    direct_body = direct_response.get_json()
    assert view_body["data"]["view"] == {
        "view_id": "high_priority_actionable",
        "label": "High-priority actionable cases",
        "readonly": True,
    }
    assert view_body["data"]["cases"] == direct_body["data"]["cases"]
    assert [case["case_id"] for case in view_body["data"]["cases"]] == [high.case_id]
    assert all(case["business_id"] == "artemea" for case in view_body["data"]["cases"])


def test_internal_readiness_gated_actionable_view_matches_jql_and_excludes_resolved(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-promoted", priority=95))
    readiness = _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            title="Conversaciones sin responder",
            run_id="run-readiness-open",
        ),
    )
    resolved_readiness = _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/resolved.conversations/daily",
            severity="warning",
            priority=80,
            title="Conversaciones resueltas",
            run_id="run-readiness-resolved",
        ),
    )
    _seed_case(db_path, _case_detection(run_id="run-other-readiness", business_id="other", priority=99))

    with sqlite3.connect(db_path) as conn:
        init_schema(conn)
        store = SQLiteOperationalCaseStore(conn)
        store.transition_case(
            resolved_readiness.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator:juan",
        )
        store.transition_case(
            resolved_readiness.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="operator:juan",
            reason="fixture resolved",
        )

    view_response = client.get(
        "/internal/brain/businesses/artemea/case-views/readiness_gated_actionable/cases",
        headers=AUTH,
    )
    direct_response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "release_state = readiness_gated AND actionable = true ORDER BY updated_at DESC"},
    )

    assert view_response.status_code == 200
    assert direct_response.status_code == 200
    view_body = view_response.get_json()
    direct_body = direct_response.get_json()
    assert view_body["data"]["view"] == {
        "view_id": "readiness_gated_actionable",
        "label": "Readiness-gated actionable cases",
        "readonly": True,
    }
    assert view_body["data"]["cases"] == direct_body["data"]["cases"]
    assert [case["case_id"] for case in view_body["data"]["cases"]] == [readiness.case_id]
    assert view_body["data"]["cases"][0]["release_state"] == "readiness_gated"
    assert all(case["business_id"] == "artemea" for case in view_body["data"]["cases"])



def test_internal_case_views_can_include_scoped_totals_without_returning_cases(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-open", priority=90))
    _seed_case(db_path, _case_detection(run_id="run-other", business_id="other", priority=100))

    response = client.get("/internal/brain/businesses/artemea/case-views?include_totals=true", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    views = {view["view_id"]: view for view in body["data"]["views"]}
    assert views["open_cases"]["total"] == 1
    assert views["stockout_risk"]["total"] == 1
    assert views["unassigned_actionable"]["total"] == 1
    assert views["actionable_cases"]["total"] == 1
    assert all(view["readonly"] is True for view in views.values())
    assert all("cases" not in view for view in views.values())
    assert body["data"]["include_totals"] is True
    assert body["redaction_applied"] is True



def test_internal_case_views_reject_invalid_include_totals_without_echoing_secrets(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/case-views?include_totals=access_token%3Draw_view_secret",
        headers=AUTH,
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_include_totals"
    assert "raw_view_secret" not in response.get_data(as_text=True)


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


def test_internal_case_view_export_returns_scoped_redacted_rows(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    exported = _seed_case(
        db_path,
        _case_detection(
            run_id="run-export",
            title="Stock crítico access_token=raw_export_secret",
            priority=95,
            entity_scope={"kind": "sku", "id": "SKU-1", "label": "Campera"},
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-lower",
            dedupe_suffix="stockout_risk/sku/LOW/inventory.on_hand/daily",
            title="Stock menor",
            priority=80,
        ),
    )
    _seed_case(db_path, _case_detection(run_id="run-other", business_id="other", priority=100))

    response = client.get(
        "/internal/brain/businesses/artemea/case-views/open_cases/export?limit=1",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["view"] == {"view_id": "open_cases", "label": "Open cases", "readonly": True}
    assert body["data"]["export"]["format"] == "case_view_rows_v1"
    assert body["data"]["export"]["jql"] == "status = open ORDER BY priority_score DESC"
    assert body["data"]["export"]["normalized_jql"] == "status = open ORDER BY priority_score DESC"
    assert body["data"]["export"]["limit"] == 1
    assert body["data"]["export"]["count"] == 1
    assert body["data"]["export"]["total"] == 2
    assert body["data"]["export"]["truncated"] is True
    assert body["data"]["export"]["columns"] == [
        "case_id",
        "business_id",
        "case_type",
        "status",
        "status_category",
        "project_key",
        "issue_type",
        "work_item_id",
        "severity",
        "priority_score",
        "title",
        "entity_kind",
        "entity_id",
        "entity_label",
        "assignee_ref",
        "opened_at",
        "updated_at",
        "latest_run_id",
        "source_connectors",
        "degraded",
    ]
    assert body["data"]["rows"] == [
        {
            "case_id": exported.case_id,
            "business_id": "artemea",
            "case_type": "stockout_risk",
            "status": "open",
            "status_category": "to_do",
            "project_key": "ARTEMEA",
            "issue_type": "stockout_risk",
            "work_item_id": f"ARTEMEA:{exported.case_id}",
            "severity": "critical",
            "priority_score": 95,
            "title": "Stock crítico access_token=[REDACTED]",
            "entity_kind": "sku",
            "entity_id": "SKU-1",
            "entity_label": "Campera",
            "assignee_ref": None,
            "opened_at": exported.opened_at.isoformat(),
            "updated_at": exported.updated_at.isoformat(),
            "latest_run_id": "run-export",
            "source_connectors": ["tiendanube"],
            "degraded": False,
        }
    ]
    raw_response = response.get_data(as_text=True)
    assert "raw_export_secret" not in raw_response
    assert "other" not in {row["business_id"] for row in body["data"]["rows"]}
    assert body["redaction_applied"] is True


def test_internal_case_view_export_rejects_unknown_view_without_echoing_secret(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/case-views/access_token=raw_export_secret/export",
        headers=AUTH,
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "case_view_not_found"
    assert "raw_export_secret" not in response.get_data(as_text=True)


def test_internal_case_view_summary_returns_scoped_facets_without_cases(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    open_detection = _case_detection_with_source(source="tiendanube", run_id="run-open", priority=90)
    _seed_case(
        db_path,
        open_detection.model_copy(
            update={
                "evidence_refs": [
                    "evidence://tiendanube/run-open/stockout_risk/0",
                    "evidence://tiendanube/run-open/stockout_risk/1",
                    "evidence://tiendanube/run-open/stockout_risk/2",
                ]
            }
        ),
    )
    acknowledged = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-ack-stale",
            freshness_state="stale",
            dedupe_suffix="stockout_risk/sku/ACK_STALE/inventory.on_hand/daily",
            priority=70,
        ),
    )
    resolved = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-resolved",
            dedupe_suffix="stockout_risk/sku/RESOLVED_SUMMARY/inventory.on_hand/daily",
            priority=100,
        ),
    )
    _seed_case(db_path, _case_detection_with_source(source="meta_ads", run_id="run-other", business_id="other"))

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.assign_case(
        acknowledged.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        assignee_ref="operator:ana",
    )
    store.transition_case(
        acknowledged.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
    )
    store.transition_case(
        resolved.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator:ana",
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="fixture complete",
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/case-views/stockout_risk/summary",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["view"] == {"view_id": "stockout_risk", "label": "Stock risks", "readonly": True}
    assert body["data"]["normalized_jql"] == (
        "case_type = stockout_risk AND status IN (open, acknowledged, in_progress) ORDER BY priority_score DESC"
    )
    assert body["data"]["summary"] == {
        "total": 2,
        "status_counts": {"acknowledged": 1, "open": 1},
        "status_category_counts": {"in_progress": 1, "to_do": 1},
        "severity_counts": {"critical": 2},
        "case_type_counts": {"stockout_risk": 2},
        "priority_bracket_counts": {"high": 1, "medium": 1},
        "evidence_count_total": 4,
        "evidence_count_distribution": {"1": 1, "3": 1},
        "source_connector_counts": {"meta_ads": 1, "tiendanube": 1},
        "freshness_state_counts": {"fresh": 1, "stale": 1},
        "degraded_total": 1,
        "assigned_total": 1,
        "unassigned_total": 1,
        "assignee_counts": [
            {"assignee_ref": "operator:ana", "total": 1},
            {"assignee_ref": None, "total": 1},
        ],
    }
    assert "cases" not in body["data"]
    assert body["redaction_applied"] is True


def test_internal_case_view_summary_rejects_unknown_view_without_echoing_secret(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/case-views/access_token=raw_summary_secret/summary",
        headers=AUTH,
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "case_view_not_found"
    assert "raw_summary_secret" not in response.get_data(as_text=True)


def test_internal_case_query_summary_returns_scoped_facets_without_cases(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    open_case = _seed_case(
        db_path,
        _case_detection_with_source(source="tiendanube", run_id="run-query-open", priority=95),
    )
    acknowledged = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-query-ack-stale",
            freshness_state="stale",
            dedupe_suffix="stockout_risk/sku/QUERY_ACK/inventory.on_hand/daily",
            priority=70,
        ),
    )
    resolved = _seed_case(
        db_path,
        _case_detection_with_source(
            source="meta_ads",
            run_id="run-query-resolved",
            dedupe_suffix="stockout_risk/sku/QUERY_RESOLVED/inventory.on_hand/daily",
            priority=80,
        ),
    )
    _seed_case(db_path, _case_detection_with_source(source="meta_ads", run_id="run-query-other", business_id="other"))

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.assign_case(
        acknowledged.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        assignee_ref="operator:ana",
    )
    store.transition_case(
        acknowledged.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
    )
    store.transition_case(
        resolved.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator:ana",
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:ana",
        reason="fixture complete",
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/query-summary",
        query_string={"jql": "status IN (open, acknowledged) AND case_type = stockout_risk"},
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["jql"] == "status IN (open, acknowledged) AND case_type = stockout_risk"
    assert body["data"]["normalized_jql"] == (
        "status IN (open, acknowledged) AND case_type = stockout_risk "
        "ORDER BY priority_score DESC, opened_at ASC"
    )
    assert body["data"]["summary"] == {
        "total": 2,
        "status_counts": {"acknowledged": 1, "open": 1},
        "status_category_counts": {"in_progress": 1, "to_do": 1},
        "severity_counts": {"critical": 2},
        "case_type_counts": {"stockout_risk": 2},
        "priority_bracket_counts": {"high": 1, "medium": 1},
        "evidence_count_total": 2,
        "evidence_count_distribution": {"1": 2},
        "source_connector_counts": {"meta_ads": 1, "tiendanube": 1},
        "freshness_state_counts": {"fresh": 1, "stale": 1},
        "degraded_total": 1,
        "assigned_total": 1,
        "unassigned_total": 1,
        "assignee_counts": [
            {"assignee_ref": "operator:ana", "total": 1},
            {"assignee_ref": None, "total": 1},
        ],
    }
    assert "cases" not in body["data"]
    raw_response = response.get_data(as_text=True)
    assert open_case.case_id not in raw_response
    assert acknowledged.case_id not in raw_response
    assert resolved.case_id not in raw_response
    assert body["redaction_applied"] is True


def test_internal_case_query_summary_rejects_unsafe_jql_without_echoing_secret(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/cases/query-summary",
        query_string={"jql": "status = open OR access_token=raw_query_summary_secret"},
        headers=AUTH,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_jql"
    assert "raw_query_summary_secret" not in response.get_data(as_text=True)


def test_internal_case_query_summary_redacts_secret_shaped_assignee_facets(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    assigned = _seed_case(db_path, _case_detection(run_id="run-query-assignee-secret", priority=90))

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.assign_case(
        assigned.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        assignee_ref="operator:access_token=raw_assignee_summary_secret",
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/query-summary",
        query_string={"jql": "status = open"},
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_response = response.get_data(as_text=True)
    assert "raw_assignee_summary_secret" not in raw_response
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["summary"]["assigned_total"] == 1
    assert body["data"]["summary"]["unassigned_total"] == 0
    assert body["data"]["summary"]["assignee_counts"] == [
        {"assignee_ref": "operator:access_token=[REDACTED]", "total": 1}
    ]
    assert "cases" not in body["data"]
