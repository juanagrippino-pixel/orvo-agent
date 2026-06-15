from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

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
    assert parse_case_jql("timeline_event_count >= 2").normalized == (
        "timeline_event_count >= 2 ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("comment_count >= 1 ORDER BY last_comment_at DESC").normalized == (
        "comment_count >= 1 ORDER BY last_comment_at DESC"
    )
    assert parse_case_jql("last_comment_at >= 2026-05-24T09:00:00Z").normalized == (
        "last_comment_at >= 2026-05-24T09:00:00+00:00 ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("last_event_at >= 2026-05-24T09:00:00Z").normalized == (
        "last_event_at >= 2026-05-24T09:00:00+00:00 ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("last_event_type IN (case_opened, evidence_attached)").normalized == (
        "last_event_type IN (case_opened, evidence_attached) ORDER BY priority_score DESC, opened_at ASC"
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
    assert parse_case_jql("assigned_at >= 2026-05-24T09:00:00Z ORDER BY assigned_at DESC").normalized == (
        "assigned_at >= 2026-05-24T09:00:00+00:00 ORDER BY assigned_at DESC"
    )
    assert parse_case_jql("due_at < 2026-05-24T10:00:00Z").normalized == (
        "due_at < 2026-05-24T10:00:00+00:00 ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql(
        "latest_evidence_at >= 2026-05-24T08:00:00Z ORDER BY latest_evidence_at DESC"
    ).normalized == "latest_evidence_at >= 2026-05-24T08:00:00+00:00 ORDER BY latest_evidence_at DESC"
    assert parse_case_jql("reopen_count >= 2 ORDER BY reopen_count DESC").normalized == (
        "reopen_count >= 2 ORDER BY reopen_count DESC"
    )
    assert parse_case_jql("latest_reopened_at >= 2026-05-24T09:00:00Z ORDER BY latest_reopened_at DESC").normalized == (
        "latest_reopened_at >= 2026-05-24T09:00:00+00:00 ORDER BY latest_reopened_at DESC"
    )
    assert parse_case_jql("sla_status = breached").normalized == (
        "sla_status = breached ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("status_category IN (to_do, done)").normalized == (
        "status_category IN (to_do, done) ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("release_state = readiness_gated").normalized == (
        "release_state = readiness_gated ORDER BY priority_score DESC, opened_at ASC"
    )
    assert parse_case_jql("owner_visible = true").normalized == (
        "owner_visible = true ORDER BY priority_score DESC, opened_at ASC"
    )

    with pytest.raises(OperatorAPIError) as unsupported_category:
        parse_case_jql("status_category = waiting")
    assert unsupported_category.value.code == "unsupported_jql_value"

    with pytest.raises(OperatorAPIError) as unsupported_release_state:
        parse_case_jql("release_state = experimental")
    assert unsupported_release_state.value.code == "unsupported_jql_value"


def test_internal_case_queue_filters_and_sorts_by_reopen_stats(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    recurring = _seed_case(
        db_path,
        _case_detection(
            run_id="run-recurring-top",
            priority=95,
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/recurring-top",
        ),
    )
    single = _seed_case(
        db_path,
        _case_detection(
            run_id="run-recurring-single",
            priority=80,
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/recurring-single",
        ),
    )
    untouched = _seed_case(
        db_path,
        _case_detection(
            run_id="run-recurring-none",
            priority=70,
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/recurring-none",
        ),
    )

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)

    def reopen(case_id: str, *, reopened_at: datetime) -> None:
        store.transition_case(
            case_id,
            status="in_progress",
            actor_type="operator",
            actor_ref="operator:juan",
            transitioned_at=reopened_at - timedelta(minutes=30),
        )
        store.transition_case(
            case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="operator:juan",
            reason="fixture resolution",
            transitioned_at=reopened_at - timedelta(minutes=15),
        )
        store.reopen_case(
            case_id,
            actor_type="operator",
            actor_ref="operator:juan",
            reason="fixture recurrence",
            reopened_at=reopened_at,
        )

    reopen(recurring.case_id, reopened_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc))
    reopen(recurring.case_id, reopened_at=datetime(2026, 5, 24, 11, 0, tzinfo=timezone.utc))
    reopen(single.case_id, reopened_at=datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc))
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "reopen_count >= 1 ORDER BY latest_reopened_at DESC"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "reopen_count >= 1 ORDER BY latest_reopened_at DESC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [recurring.case_id, single.case_id]
    assert untouched.case_id not in [case["case_id"] for case in body["data"]["cases"]]
    assert body["data"]["cases"][0]["work_item"]["reopen_count"] == 2
    assert body["data"]["cases"][0]["work_item"]["latest_reopened_at"] == "2026-05-24T11:00:00Z"
    assert body["data"]["cases"][1]["work_item"]["reopen_count"] == 1
    assert body["data"]["cases"][1]["work_item"]["latest_reopened_at"] == "2026-05-24T10:00:00Z"

    mixed_sort = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "status = open ORDER BY latest_reopened_at DESC"},
    )

    assert mixed_sort.status_code == 200
    mixed_body = mixed_sort.get_json()
    assert mixed_body["ok"] is True
    assert [case["case_id"] for case in mixed_body["data"]["cases"][:3]] == [
        recurring.case_id,
        single.case_id,
        untouched.case_id,
    ]
    assert mixed_body["data"]["cases"][2]["work_item"]["latest_reopened_at"] is None


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


def test_internal_case_queue_filters_by_owner_visible_policy(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    promoted = _seed_case(db_path, _case_detection(run_id="run-owner-visible", priority=95))
    readiness_gated = _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            title="Conversaciones sin responder",
            run_id="run-owner-hidden",
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "owner_visible = false"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "owner_visible = false ORDER BY priority_score DESC, opened_at ASC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [readiness_gated.case_id]
    assert body["data"]["cases"][0]["owner_visible"] is False
    assert body["data"]["cases"][0]["work_item"]["owner_visible"] is False
    assert promoted.case_id not in [case["case_id"] for case in body["data"]["cases"]]


def test_builtin_case_views_expose_owner_facing_policy_views(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    promoted = _seed_case(db_path, _case_detection(run_id="run-owner-visible-view", priority=95))
    hidden = _seed_case(
        db_path,
        _case_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=90,
            title="Conversaciones sin responder",
            run_id="run-owner-hidden-view",
        ),
    )

    views_response = client.get("/internal/brain/businesses/artemea/case-views", headers=AUTH)

    assert views_response.status_code == 200
    views = {view["view_id"]: view for view in views_response.get_json()["data"]["views"]}
    assert views["owner_visible_actionable"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND owner_visible = true "
        "ORDER BY priority_score DESC, opened_at ASC"
    )
    assert views["internal_only_actionable"]["jql"] == (
        "status IN (open, acknowledged, in_progress) AND owner_visible = false "
        "ORDER BY priority_score DESC, opened_at ASC"
    )

    owner_response = client.get(
        "/internal/brain/businesses/artemea/case-views/owner_visible_actionable/cases",
        headers=AUTH,
    )
    internal_response = client.get(
        "/internal/brain/businesses/artemea/case-views/internal_only_actionable/cases",
        headers=AUTH,
    )

    assert owner_response.status_code == 200
    assert internal_response.status_code == 200
    assert [case["case_id"] for case in owner_response.get_json()["data"]["cases"]] == [promoted.case_id]
    assert owner_response.get_json()["data"]["cases"][0]["owner_visible"] is True
    assert [case["case_id"] for case in internal_response.get_json()["data"]["cases"]] == [hidden.case_id]
    assert internal_response.get_json()["data"]["cases"][0]["owner_visible"] is False


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


def test_internal_case_queue_filters_and_sorts_by_comment_activity(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    earlier_case = _seed_case(
        db_path,
        _case_detection(run_id="run-comment-earlier", priority=50, dedupe_suffix="stockout_risk/business/comment-earlier/daily"),
    )
    later_case = _seed_case(
        db_path,
        _case_detection(run_id="run-comment-later", priority=50, dedupe_suffix="stockout_risk/business/comment-later/daily"),
    )
    _seed_case(
        db_path,
        _case_detection(
            business_id="other",
            run_id="run-comment-other",
            priority=50,
            dedupe_suffix="stockout_risk/business/comment-other/daily",
        ),
    )

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.add_comment(
        earlier_case.case_id,
        actor_type="operator",
        actor_ref="operator:ana",
        comment="Revisar stock físico.",
        commented_at=datetime(2026, 5, 24, 9, 15, tzinfo=timezone.utc),
    )
    store.add_comment(
        later_case.case_id,
        actor_type="operator",
        actor_ref="operator:juan",
        comment="Cliente esperando confirmación.",
        commented_at=datetime(2026, 5, 24, 9, 45, tzinfo=timezone.utc),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "comment_count >= 1 ORDER BY last_comment_at DESC"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "comment_count >= 1 ORDER BY last_comment_at DESC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [later_case.case_id, earlier_case.case_id]
    assert [case["work_item"]["comment_count"] for case in body["data"]["cases"]] == [1, 1]
    assert [case["work_item"]["last_comment_at"] for case in body["data"]["cases"]] == [
        "2026-05-24T09:45:00Z",
        "2026-05-24T09:15:00Z",
    ]
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


def test_internal_case_queue_sorts_by_latest_evidence_at(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    older_case = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-older",
            priority=50,
            dedupe_suffix="stockout_risk/business/monitored/older/daily",
        ),
    )
    newer_case = _seed_case(db_path, _case_detection_with_source(source="tiendanube", run_id="run-newer", priority=50))
    later_snapshot = newer_case.evidence_snapshots[0].model_copy(
        update={
            "snapshot_id": "snapshot-newer-later",
            "captured_at": datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
            "source": "google_sheets",
            "source_label": "Google Sheets",
            "evidence_ref": "evidence://google_sheets/run-newer-google/stockout_risk",
            "snapshot_key": "run-newer-google/evidence://google_sheets/run-newer-google/stockout_risk/stockout_risk/business/monitored",
        }
    )

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.attach_evidence(
        newer_case.case_id,
        snapshots=[later_snapshot],
        run_id="run-newer-google",
        artifact_ref="ledger://runs/run-newer-google/daily-report",
        summary="Attached later Google Sheets evidence.",
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "status = open ORDER BY latest_evidence_at DESC"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "status = open ORDER BY latest_evidence_at DESC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [newer_case.case_id, older_case.case_id]
    assert body["data"]["cases"][0]["work_item"]["latest_evidence_at"] == "2026-05-24T09:30:00Z"


def test_internal_case_queue_sorts_by_last_case_event(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    older_case = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-older-event",
            priority=50,
            dedupe_suffix="stockout_risk/business/monitored/older-event/daily",
        ),
    )
    newer_case = _seed_case(
        db_path,
        _case_detection_with_source(
            source="tiendanube",
            run_id="run-newer-event",
            priority=50,
            dedupe_suffix="stockout_risk/business/monitored/newer-event/daily",
        ),
    )
    later_snapshot = newer_case.evidence_snapshots[0].model_copy(
        update={
            "snapshot_id": "snapshot-newer-event-later",
            "captured_at": datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
            "run_id": "run-newer-event-google",
            "artifact_ref": "ledger://runs/run-newer-event-google/daily-report",
            "source": "google_sheets",
            "source_label": "Google Sheets",
            "evidence_ref": "evidence://google_sheets/run-newer-event-google/stockout_risk",
            "snapshot_key": "run-newer-event-google/evidence://google_sheets/run-newer-event-google/stockout_risk/stockout_risk/business/monitored",
        }
    )

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.attach_evidence(
        newer_case.case_id,
        snapshots=[later_snapshot],
        run_id="run-newer-event-google",
        artifact_ref="ledger://runs/run-newer-event-google/daily-report",
        summary="Attached later Google Sheets evidence.",
        attached_at=datetime(2026, 5, 24, 9, 35, tzinfo=timezone.utc),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers=AUTH,
        query_string={"jql": "status = open ORDER BY last_event_at DESC"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == "status = open ORDER BY last_event_at DESC"
    assert [case["case_id"] for case in body["data"]["cases"]] == [newer_case.case_id, older_case.case_id]
    assert body["data"]["cases"][0]["work_item"]["timeline_event_count"] == 2
    assert body["data"]["cases"][0]["work_item"]["last_event_at"] == "2026-05-24T09:35:00Z"
    assert body["data"]["cases"][0]["work_item"]["last_event_type"] == "evidence_attached"


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
        assigned_at=datetime(2026, 5, 24, 9, tzinfo=timezone.utc),
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
        "/internal/brain/businesses/artemea/cases?as_of=2026-05-24T10:00:00Z&jql="
        "project%20%3D%20ARTEMEA%20AND%20issue_type%20%3D%20stockout_risk%20AND%20"
        "status_category%20%3D%20in_progress%20AND%20priority_bracket%20%3D%20high%20AND%20"
        "sla_status%20%3D%20breached%20AND%20assignee_ref%20%3D%20operator:juan",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["normalized_jql"] == (
        "project = ARTEMEA AND issue_type = stockout_risk AND status_category = in_progress "
        "AND priority_bracket = high AND sla_status = breached AND assignee_ref = operator:juan ORDER BY priority_score DESC, opened_at ASC"
    )
    assert [case["case_id"] for case in body["data"]["cases"]] == [assigned.case_id]
    case = body["data"]["cases"][0]
    assert case["project_key"] == "ARTEMEA"
    assert case["issue_type"] == "stockout_risk"
    assert case["status_category"] == "in_progress"
    assert case["work_item"]["case_id"] == assigned.case_id
    assert case["work_item"]["work_item_id"] == f"ARTEMEA:{assigned.case_id}"
    assert case["sla_target_seconds"] == 2 * 60 * 60
    assert case["due_at"] == "2026-05-24T10:00:00+00:00"
    assert case["sla_status"] == "breached"
    assert case["sla_elapsed_seconds"] == 2 * 60 * 60
    assert case["sla_remaining_seconds"] == 0
    assert case["assigned_at"] == "2026-05-24T09:00:00Z"
    assert case["work_item"]["sla_target_seconds"] == 2 * 60 * 60
    assert case["work_item"]["assigned_at"] == "2026-05-24T09:00:00Z"
    assert case["work_item"]["due_at"] == "2026-05-24T10:00:00Z"
    assert case["work_item"]["sla_status"] == "breached"
    assert case["work_item"]["sla_elapsed_seconds"] == 2 * 60 * 60
    assert case["work_item"]["sla_remaining_seconds"] == 0
    assert all(case["business_id"] == "artemea" for case in body["data"]["cases"])


def test_query_case_queue_uses_supplied_sla_clock(monkeypatch, tmp_path):
    db_path = tmp_path / "queue.sqlite3"
    case = _seed_case(db_path, _case_detection(run_id="run-sla-clock"))

    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    try:
        pending = operator_views.query_case_queue(
            store,
            business_id="artemea",
            jql="status = open",
            limit=None,
            now=datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
        )
        breached = operator_views.query_case_queue(
            store,
            business_id="artemea",
            jql="sla_status = breached",
            limit=None,
            now=datetime(2026, 5, 24, 10, 30, tzinfo=timezone.utc),
        )
    finally:
        conn.close()

    assert pending["cases"][0]["case_id"] == case.case_id
    assert pending["cases"][0]["sla_status"] == "pending"
    assert pending["cases"][0]["work_item"]["sla_status"] == "pending"
    assert breached["cases"][0]["case_id"] == case.case_id
    assert breached["cases"][0]["sla_status"] == "breached"
    assert breached["cases"][0]["work_item"]["sla_status"] == "breached"


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


def test_internal_case_facets_reject_sqlish_jql_without_echoing_input(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-facet-sqlish"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases/facets",
        headers=AUTH,
        query_string={
            "field": "source_connector",
            "jql": "status = open UNION SELECT business_id FROM operational_cases WHERE access_token=raw_facet_jql_secret",
        },
    )

    raw_body = response.get_data(as_text=True)
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "invalid_jql"
    assert body["redaction_applied"] is True
    assert "UNION SELECT" not in raw_body
    assert "operational_cases" not in raw_body
    assert "raw_facet_jql_secret" not in raw_body


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
