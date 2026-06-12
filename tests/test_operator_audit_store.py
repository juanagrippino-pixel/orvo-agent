import json
import sqlite3
from datetime import datetime, timezone

from app.brain.operator_audit import SQLiteOperatorAuditStore
from app.brain.storage import init_schema


def test_list_events_queries_secret_shaped_business_id_using_persisted_redacted_scope():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    store = SQLiteOperatorAuditStore(conn)
    business_id = "tenant?access_" + "token=raw-business-secret"

    event_id = store.append_event(
        business_id=business_id,
        actor_ref="operator:admin",
        event_type="operator.authorization.denied",
        target_type="case",
        target_id="case-1",
        request_id="req-1",
        data={"reason": "missing_permission"},
        created_at=datetime(2026, 6, 4, 12, tzinfo=timezone.utc),
    )

    events = store.list_events(
        business_id=business_id,
        retention_days=90,
        limit=10,
    )

    assert [event["event_id"] for event in events] == [event_id]
    assert events[0]["business_id"] == "[REDACTED]"
    serialized = json.dumps(events[0], sort_keys=True)
    assert "raw-business-secret" not in serialized
    assert "access_token" not in serialized
    assert "audit_business_scope_sha256_v1:" not in serialized


def test_list_events_does_not_cross_tenant_when_secret_shaped_business_ids_redact_similarly():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    store = SQLiteOperatorAuditStore(conn)
    first_business_id = "tenant?access_" + "token=first-secret"
    second_business_id = "tenant?access_" + "token=second-secret"

    store.append_event(
        business_id=first_business_id,
        actor_ref="operator:first",
        event_type="operator.authorization.denied",
        target_type="case",
        data={"reason": "first"},
        created_at=datetime(2026, 6, 4, 12, tzinfo=timezone.utc),
    )
    store.append_event(
        business_id=second_business_id,
        actor_ref="operator:second",
        event_type="operator.authorization.denied",
        target_type="case",
        data={"reason": "second"},
        created_at=datetime(2026, 6, 4, 12, 1, tzinfo=timezone.utc),
    )

    events = store.list_events(
        business_id=first_business_id,
        retention_days=90,
        limit=10,
    )

    assert [event["data"]["reason"] for event in events] == ["first"]


def test_init_schema_migrates_legacy_operator_audit_table_without_scope_key():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE operator_audit_events (
            event_id     TEXT PRIMARY KEY,
            business_id  TEXT NOT NULL,
            actor_ref    TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            target_type  TEXT NOT NULL,
            target_id    TEXT,
            request_id   TEXT,
            created_at   TEXT NOT NULL,
            data         TEXT NOT NULL
        );
        INSERT INTO operator_audit_events (
            event_id, business_id, actor_ref, event_type, target_type,
            target_id, request_id, created_at, data
        ) VALUES (
            'audit_legacy', 'artemea', 'operator:legacy', 'operator.authorization.denied',
            'case', NULL, NULL, '2026-06-04T12:00:00Z', '{"reason":"legacy"}'
        );
        """
    )
    conn.commit()

    init_schema(conn)

    events = SQLiteOperatorAuditStore(conn).list_events(
        business_id="artemea",
        retention_days=90,
        limit=10,
    )

    assert [event["event_id"] for event in events] == ["audit_legacy"]
    assert events[0]["business_id"] == "artemea"
    assert events[0]["data"] == {"reason": "legacy"}
