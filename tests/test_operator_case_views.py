from __future__ import annotations

import csv
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

from app.brain import operator_views
from app.brain.operational_cases import SQLiteOperationalCaseStore
from app.brain.operator_api import OperatorAPIError, export_case_queue_csv
from app.brain.operator_views import parse_case_jql
from app.brain.storage import init_schema
from tests.test_internal_operator_api import AUTH, _case_detection, _client, _seed_case, _utc


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


def _resolve_case(db_path: Path, case_id: str, *, acknowledged_at: datetime, resolved_at: datetime) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        store = SQLiteOperationalCaseStore(conn)
        store.transition_case(
            case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator:juan",
            transitioned_at=acknowledged_at,
        )
        store.transition_case(
            case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="operator:juan",
            reason="Fixture resolution",
            transitioned_at=resolved_at,
        )


def _acknowledge_case(db_path: Path, case_id: str, *, acknowledged_at: datetime) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        store = SQLiteOperationalCaseStore(conn)
        store.transition_case(
            case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator:juan",
            transitioned_at=acknowledged_at,
        )


def test_parse_case_jql_uses_canonical_work_item_field_registry():
    assert not hasattr(operator_views, "_FIELD_SPECS")
    assert parse_case_jql("priority_score >= 80 ORDER BY priority_score DESC").normalized == (
        "priority_score >= 80 ORDER BY priority_score DESC"
    )
    assert parse_case_jql("priority_bracket = high").normalized == (
        "priority_bracket = high ORDER BY priority_score DESC, opened_at ASC"
    )


def test_parse_case_jql_supports_resolved_at_sort_for_recently_resolved_views():
    assert parse_case_jql("status = resolved ORDER BY resolved_at DESC").normalized == (
        "status = resolved ORDER BY resolved_at DESC"
    )
    assert parse_case_jql("resolved_at >= 2026-05-24T10:00:00+00:00").normalized == (
        "resolved_at >= 2026-05-24T10:00:00+00:00 ORDER BY priority_score DESC, opened_at ASC"
    )


def test_parse_case_jql_supports_acknowledged_at_sort_for_acknowledged_case_views():
    assert parse_case_jql("status = acknowledged ORDER BY acknowledged_at DESC").normalized == (
        "status = acknowledged ORDER BY acknowledged_at DESC"
    )
    assert parse_case_jql("acknowledged_at >= 2026-05-24T10:00:00+00:00").normalized == (
        "acknowledged_at >= 2026-05-24T10:00:00+00:00 ORDER BY priority_score DESC, opened_at ASC"
    )


def test_internal_case_view_acknowledged_cases_orders_by_acknowledged_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    client, db_path = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "operator.sqlite3"
    old = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-ack-old",
            priority=20,
            dedupe_suffix="run-ack-old/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-ack-old", "label": "Run ack old"},
        ),
    )
    middle = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-ack-middle",
            priority=20,
            dedupe_suffix="run-ack-middle/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-ack-middle", "label": "Run ack middle"},
        ),
    )
    new = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-ack-new",
            priority=20,
            dedupe_suffix="run-ack-new/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-ack-new", "label": "Run ack new"},
        ),
    )
    resolved = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-ack-resolved",
            priority=20,
            dedupe_suffix="run-ack-resolved/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-ack-resolved", "label": "Run ack resolved"},
        ),
    )
    other = _seed_case(
        db_path,
        _case_detection_with_source(source="tiendanube", run_id="run-ack-other", business_id="other", priority=20),
    )
    _acknowledge_case(db_path, old.case_id, acknowledged_at=_utc(10))
    _acknowledge_case(db_path, middle.case_id, acknowledged_at=_utc(12))
    _acknowledge_case(db_path, new.case_id, acknowledged_at=_utc(14))
    _resolve_case(db_path, resolved.case_id, acknowledged_at=_utc(16), resolved_at=_utc(17))
    _acknowledge_case(db_path, other.case_id, acknowledged_at=_utc(18))

    response = client.get(
        "/internal/brain/businesses/artemea/case-views/acknowledged_cases/cases",
        headers=AUTH,
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["view_id"] == "acknowledged_cases"
    assert payload["normalized_jql"] == "status = acknowledged ORDER BY acknowledged_at DESC"
    assert payload["count"] == 3
    assert payload["total"] == 3
    assert [case["case_id"] for case in payload["cases"]] == [new.case_id, middle.case_id, old.case_id]
    assert payload["cases"][0]["acknowledged_at"] == _utc(14).isoformat().replace("+00:00", "Z")


def test_internal_case_view_recently_resolved_orders_by_resolved_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client, db_path = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "operator.sqlite3"
    old = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-old",
            priority=20,
            dedupe_suffix="run-old/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-old", "label": "Run old"},
        ),
    )
    middle = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-middle",
            priority=20,
            dedupe_suffix="run-middle/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-middle", "label": "Run middle"},
        ),
    )
    new = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-new",
            priority=20,
            dedupe_suffix="run-new/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-new", "label": "Run new"},
        ),
    )
    other = _seed_case(
        db_path,
        _case_detection_with_source(source="tiendanube", run_id="run-other", business_id="other", priority=20),
    )
    _resolve_case(db_path, old.case_id, acknowledged_at=_utc(9), resolved_at=_utc(10))
    _resolve_case(db_path, middle.case_id, acknowledged_at=_utc(11), resolved_at=_utc(12))
    _resolve_case(db_path, new.case_id, acknowledged_at=_utc(13), resolved_at=_utc(14))
    _resolve_case(db_path, other.case_id, acknowledged_at=_utc(15), resolved_at=_utc(16))

    response = client.get("/internal/brain/businesses/artemea/case-views/recently_resolved/cases", headers=AUTH)

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["view_id"] == "recently_resolved"
    assert payload["normalized_jql"] == "status = resolved ORDER BY resolved_at DESC"
    assert payload["count"] == 3
    assert payload["total"] == 3
    assert [case["case_id"] for case in payload["cases"]] == [new.case_id, middle.case_id, old.case_id]
    assert payload["cases"][0]["resolved_at"] == _utc(14).isoformat().replace("+00:00", "Z")


def test_internal_case_view_recently_resolved_excludes_non_resolved_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client, db_path = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "operator.sqlite3"
    opened = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-open",
            priority=20,
            dedupe_suffix="run-open/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-open", "label": "Run open"},
        ),
    )
    acknowledged = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-ack",
            priority=20,
            dedupe_suffix="run-ack/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-ack", "label": "Run acknowledged"},
        ),
    )
    resolved = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-resolved",
            priority=20,
            dedupe_suffix="run-resolved/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-resolved", "label": "Run resolved"},
        ),
    )
    _resolve_case(db_path, resolved.case_id, acknowledged_at=_utc(11), resolved_at=_utc(12))

    response = client.get("/internal/brain/businesses/artemea/case-views/recently_resolved/cases", headers=AUTH)

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["count"] == 1
    assert payload["total"] == 1
    assert [case["case_id"] for case in payload["cases"]] == [resolved.case_id]


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

    with pytest.raises(OperatorAPIError) as unsupported_category:
        parse_case_jql("status_category = waiting")
    assert unsupported_category.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as unsupported_release_state:
        parse_case_jql("release_state = experimental")
    assert unsupported_release_state.value.code == "unsupported_jql_value"


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


def test_internal_case_queue_project_jql_cannot_override_route_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-artemea", priority=80))
    other_case = _seed_case(db_path, _case_detection(business_id="other", run_id="run-other", priority=99))

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "project = OTHER"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert other_case.case_id not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["normalized_jql"] == "project = OTHER ORDER BY priority_score DESC, opened_at ASC"
    assert body["data"]["cases"] == []
    assert body["data"]["count"] == 0
    assert body["data"]["total"] == 0


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


def test_internal_case_views_list_readonly_builtin_views(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-views", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    views = {view["view_id"]: view for view in body["data"]["views"]}
    assert {
        "open_cases",
        "acknowledged_cases",
        "in_progress_cases",
        "high_priority",
        "critical_open",
        "data_stale",
        "stockout_risk",
        "connector_degraded",
    }.issubset(views)
    assert views["acknowledged_cases"]["jql"] == "status = acknowledged ORDER BY acknowledged_at DESC"
    assert views["high_priority"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND priority_bracket = high ORDER BY priority_score DESC"
    )
    assert views["connector_degraded"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND degraded = true ORDER BY updated_at DESC"
    )
    assert all(view["readonly"] is True for view in views.values())
    assert "business_id" not in " ".join(view["jql"] for view in views.values())
    assert body["redaction_applied"] is True


def test_internal_case_query_fields_expose_canonical_metadata(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-query-fields", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["readonly"] is True
    assert "business_id" not in body["data"]["fields_by_name"]
    assert "business_id" not in body["data"]["sort_fields"]
    assert "business_id" not in body["data"]["facet_fields"]
    assert body["data"]["fields_by_name"]["priority_score"] == {
        "field": "priority_score",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert body["data"]["fields_by_name"]["source_connector"] == {
        "field": "source_connector",
        "value_type": "string",
        "allowed_values": None,
        "allowed_operators": ["!=", "=", "IN"],
        "sortable": False,
        "facetable": True,
    }
    assert body["data"]["fields_by_name"]["degraded"]["value_type"] == "bool"
    assert body["data"]["fields_by_name"]["acknowledged_at"] == {
        "field": "acknowledged_at",
        "value_type": "datetime",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert "acknowledged_at" in body["data"]["sort_fields"]
    assert "priority_score" in body["data"]["sort_fields"]
    assert "updated_at" in body["data"]["sort_fields"]
    assert "source_connector" in body["data"]["facet_fields"]
    assert "degraded" in body["data"]["facet_fields"]
    assert body["redaction_applied"] is True


def test_internal_case_query_fields_can_return_single_field(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/case-query-fields",
        headers=AUTH,
        query_string={"field": "priority_score"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"] == {
        "field": "priority_score",
        "value_type": "int",
        "allowed_values": None,
        "allowed_operators": ["!=", "<", "<=", "=", ">", ">="],
        "sortable": True,
        "facetable": False,
    }
    assert body["redaction_applied"] is True


def test_internal_case_query_fields_rejects_unsupported_field_without_secret_echo(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/case-query-fields",
        headers=AUTH,
        query_string={"field": "access_token=token_raw_query_field_secret"},
    )

    raw_body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "token_raw_query_field_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "unsupported_jql_field"
    assert body["error"]["message"] == "Unsupported case query field: access_token=[REDACTED]"


def test_internal_case_query_fields_route_scope_and_request_id_redaction(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/token:raw_query_fields_secret/case-query-fields",
        headers={**AUTH, "X-Request-ID": "req access_token=raw_request_id_secret"},
    )

    raw_body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "raw_query_fields_secret" not in raw_body
    assert "raw_request_id_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "[REDACTED]"
    assert body["request_id"] == "[REDACTED]"
    assert "fields_by_name" in body["data"]


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


def test_internal_high_priority_case_view_matches_equivalent_jql(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    high_open = _seed_case(db_path, _case_detection(run_id="run-high-open", priority=95))
    high_acknowledged = _seed_case(
        db_path,
        _case_detection(
            run_id="run-high-ack",
            priority=82,
            dedupe_suffix="run-high-ack/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-high-ack", "label": "Run high acknowledged"},
        ),
    )
    medium_open = _seed_case(
        db_path,
        _case_detection(
            run_id="run-medium-open",
            priority=79,
            dedupe_suffix="run-medium-open/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-medium-open", "label": "Run medium open"},
        ),
    )
    resolved_high = _seed_case(
        db_path,
        _case_detection(
            run_id="run-resolved-high",
            priority=92,
            dedupe_suffix="run-resolved-high/commerce.inventory/daily",
            entity_scope={"kind": "business", "id": "run-resolved-high", "label": "Run resolved high"},
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other-high", priority=99))
    _acknowledge_case(db_path, high_acknowledged.case_id, acknowledged_at=_utc(12))
    _resolve_case(db_path, resolved_high.case_id, acknowledged_at=_utc(13), resolved_at=_utc(14))

    view_response = client.get("/internal/brain/businesses/artemea/case-views/high_priority/cases", headers=AUTH)
    direct_response = client.get(
        "/internal/brain/businesses/artemea/cases?jql=status%20IN%20(open,%20acknowledged,%20in_progress)%20AND%20priority_bracket%20%3D%20high%20ORDER%20BY%20priority_score%20DESC",
        headers=AUTH,
    )

    assert view_response.status_code == 200
    assert direct_response.status_code == 200
    view_body = view_response.get_json()
    direct_body = direct_response.get_json()
    assert view_body["data"]["view"]["view_id"] == "high_priority"
    assert view_body["data"]["normalized_jql"] == (
        "status IN (open, acknowledged, in_progress) AND priority_bracket = high ORDER BY priority_score DESC"
    )
    assert view_body["data"]["cases"] == direct_body["data"]["cases"]
    assert [case["case_id"] for case in view_body["data"]["cases"]] == [high_open.case_id, high_acknowledged.case_id]
    assert medium_open.case_id not in [case["case_id"] for case in view_body["data"]["cases"]]
    assert resolved_high.case_id not in [case["case_id"] for case in view_body["data"]["cases"]]


def test_internal_case_view_execution_keeps_route_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    artema_case = _seed_case(db_path, _case_detection(run_id="run-artemea-critical", priority=95))
    _seed_case(
        db_path,
        _case_detection(
            business_id="other",
            run_id="run-other-critical",
            priority=100,
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/case-views/critical_open/cases",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["data"]["view"]["view_id"] == "critical_open"
    assert body["data"]["view"]["readonly"] is True
    assert [case["case_id"] for case in body["data"]["cases"]] == [artema_case.case_id]
    assert body["data"]["total"] == 1
    assert body["data"]["count"] == 1
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


def test_internal_case_view_unknown_view_returns_enveloped_404(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-views/missing/cases", headers=AUTH)

    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "case_view_not_found"
    assert body["redaction_applied"] is True


def test_case_queue_csv_export_uses_jql_scope_and_redacts_projection(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    critical = _seed_case(
        db_path,
        _case_detection(
            run_id="run-export-critical",
            title="Stock crítico access_token=raw_export_secret",
            priority=95,
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=80,
            title="Ventas bajaron",
            run_id="run-export-warning",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-export-other", priority=99))

    with closing(sqlite3.connect(db_path)) as conn:
        export = export_case_queue_csv(
            SQLiteOperationalCaseStore(conn),
            business_id="artemea",
            jql="status = open AND severity = critical",
            limit="10",
        )

    assert export["content_type"] == "text/csv; charset=utf-8"
    assert export["filename"] == "artemea_cases.csv"
    rows = list(csv.DictReader(export["body"].splitlines()))
    assert len(rows) == 1
    assert rows[0]["case_id"] == critical.case_id
    assert rows[0]["business_id"] == "artemea"
    assert rows[0]["source_connectors"] == "tiendanube"
    assert "raw_export_secret" not in export["body"]
    assert "Stock crítico access_token=[REDACTED]" in export["body"]

    response = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"jql": "status = open AND severity = critical"},
    )
    assert response.status_code == 200
    assert response.content_type.startswith("text/csv")
    raw_body = response.get_data(as_text=True)
    assert "raw_export_secret" not in raw_body
    assert "Stock crítico access_token=[REDACTED]" in raw_body
    assert "other" not in raw_body
    assert critical.case_id in raw_body


def test_case_queue_csv_export_supports_builtin_view_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    critical = _seed_case(
        db_path,
        _case_detection(
            run_id="run-export-view-critical",
            priority=95,
            title="Critical export view case",
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=80,
            title="Warning export view case",
            run_id="run-export-view-warning",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-export-view-other", priority=99))

    with closing(sqlite3.connect(db_path)) as conn:
        export = export_case_queue_csv(
            SQLiteOperationalCaseStore(conn),
            business_id="artemea",
            view_id="critical_open",
            limit="10",
        )

    rows = list(csv.DictReader(export["body"].splitlines()))
    assert len(rows) == 1
    assert rows[0]["case_id"] == critical.case_id
    assert rows[0]["business_id"] == "artemea"

    response = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"view_id": "critical_open"},
    )
    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert critical.case_id in raw_body
    assert "Warning export view case" not in raw_body
    assert "other" not in raw_body



def test_case_queue_csv_export_rejects_conflicting_filters_and_invalid_format(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-export-conflict"))

    conflict = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"status": "open", "jql": "severity = critical"},
    )
    view_conflict = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"view_id": "critical_open", "jql": "severity = critical"},
    )
    missing_view = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"view_id": "missing"},
    )
    invalid_format = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"format": "xlsx"},
    )
    unsafe_jql = client.get(
        "/internal/brain/businesses/artemea/cases/export",
        headers=AUTH,
        query_string={"jql": "business_id = other"},
    )

    assert conflict.status_code == 400
    assert conflict.get_json()["error"]["code"] == "conflicting_case_filters"
    assert view_conflict.status_code == 400
    assert view_conflict.get_json()["error"]["code"] == "conflicting_case_filters"
    assert missing_view.status_code == 404
    assert missing_view.get_json()["error"]["code"] == "case_view_not_found"
    assert invalid_format.status_code == 400
    assert invalid_format.get_json()["error"]["code"] == "invalid_export_format"
    assert unsafe_jql.status_code == 400
    assert unsafe_jql.get_json()["error"]["code"] == "unsupported_jql_field"
    assert db_path.exists()
