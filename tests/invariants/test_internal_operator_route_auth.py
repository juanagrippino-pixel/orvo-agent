from __future__ import annotations

import json
import sqlite3

from app.brain.operator_audit import SQLiteOperatorAuditStore
from app.brain.storage import init_schema


_SAMPLE_ROUTE_VALUES = {
    "business_id": "artemea",
    "case_id": "case_missing_auth_probe",
    "run_id": "run_missing_auth_probe",
    "view_id": "builtin:open_cases",
}


def _sample_path(rule) -> str:
    path = rule.rule
    for argument in rule.arguments:
        placeholder = f"<{argument}>"
        if placeholder not in path:
            raise AssertionError(f"unsupported route placeholder shape in {rule.rule!r}")
        try:
            value = _SAMPLE_ROUTE_VALUES[argument]
        except KeyError as exc:
            raise AssertionError(f"no auth-invariant sample value configured for <{argument}>") from exc
        path = path.replace(placeholder, value)
    return path


def _assert_internal_brain_routes_reject_auth(client, app, *, headers: dict[str, str] | None = None) -> None:
    failures: list[dict[str, object]] = []
    checked_routes: list[tuple[str, str]] = []

    for rule in sorted(app.url_map.iter_rules(), key=lambda route: route.rule):
        if not rule.rule.startswith("/internal/brain"):
            continue
        path = _sample_path(rule)
        methods = set(rule.methods or ()) - {"HEAD", "OPTIONS"}
        for method in sorted(methods):
            response = client.open(
                path,
                method=method,
                headers=headers,
                json={} if method in {"POST", "PUT", "PATCH"} else None,
            )
            body = response.get_json(silent=True) or {}
            checked_routes.append((method, rule.rule))
            if response.status_code != 401 or body.get("error", {}).get("code") != "unauthorized":
                failures.append(
                    {
                        "method": method,
                        "rule": rule.rule,
                        "path": path,
                        "status_code": response.status_code,
                        "body": body,
                    }
                )

    assert checked_routes, "expected at least one /internal/brain route to protect"
    assert failures == []


def test_every_internal_brain_route_rejects_missing_bearer_token_before_business_logic(monkeypatch, tmp_path):
    """Gateway/auth invariant: every internal operator route must fail closed.

    This dynamically walks the Flask route map so newly added internal Brain
    endpoints are covered by default. The probe intentionally uses missing case,
    run, and view identifiers; a correct route must return the auth envelope
    before touching storage or surfacing resource-specific errors.
    """

    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(tmp_path / "auth-invariant.sqlite3"))

    from server import app

    _assert_internal_brain_routes_reject_auth(app.test_client(), app)


def test_every_internal_brain_route_rejects_wrong_bearer_token_before_business_logic(monkeypatch, tmp_path):
    """Gateway/auth invariant: invalid internal tokens must fail like missing tokens.

    A stale or mistyped bearer token is more dangerous than a missing header
    because failed-auth audit writes may run. This probe locks the route-wide
    contract that auth still returns the safe unauthorized envelope before any
    resource-specific case/run/view response can leak across operator surfaces.
    """

    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(tmp_path / "wrong-token-auth-invariant.sqlite3"))

    from server import app

    _assert_internal_brain_routes_reject_auth(
        app.test_client(),
        app,
        headers={"Authorization": "Bearer wrong-internal-token"},
    )


def test_failed_internal_basic_auth_audit_records_shape_without_credential_tail(monkeypatch, tmp_path):
    """Durable auth-denial audit must not persist Basic auth credential material.

    Internal operator routes only accept the configured Bearer token, but probes
    often arrive with Basic-style gateway credentials. The durable audit record
    should keep investigable shape metadata while dropping the credential tail so
    admin exports cannot leak base64 user:password material.
    """

    db_path = tmp_path / "basic-auth-audit-redaction.sqlite3"
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))

    from server import app

    credential_tail = "dXNlcj" + "pvcGVyYXRvci1wYXNzd29yZA=="
    response = app.test_client().get(
        "/internal/brain/businesses/artemea/runs",
        headers={"Authorization": "Basic " + credential_tail},
    )

    assert response.status_code == 401
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    events = SQLiteOperatorAuditStore(conn).list_events(
        business_id="artemea",
        retention_days=90,
        limit=10,
    )

    assert [event["event_type"] for event in events] == ["operator.authentication.denied"]
    assert events[0]["data"] == {
        "header_present": True,
        "method": "GET",
        "reason": "invalid_internal_token",
        "scheme": "Basic",
        "status": "denied",
    }
    serialized = json.dumps(events[0], sort_keys=True)
    assert credential_tail not in serialized
    assert "Basic " + credential_tail not in serialized
