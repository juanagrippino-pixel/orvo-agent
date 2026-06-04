from __future__ import annotations


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

    client = app.test_client()
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
