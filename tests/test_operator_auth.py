from app.brain.operator_auth import (
    build_internal_operator_principal,
    parse_allowed_businesses,
    project_internal_operator_session,
)


def test_parse_allowed_businesses_collapses_wildcard_and_ignores_following_entries():
    assert parse_allowed_businesses("artemea, *, other access_token=raw_scope_secret") == ("*",)



def test_parse_allowed_businesses_deduplicates_explicit_business_entries():
    assert parse_allowed_businesses("artemea, other, artemea, other") == ("artemea", "other")



def test_project_internal_operator_session_uses_minimal_global_scope_projection():
    principal = build_internal_operator_principal(
        actor_ref="admin:sol",
        role="admin",
        allowed_businesses_header="*, other access_token=raw_scope_secret",
    )

    assert project_internal_operator_session(principal)["business_scope"] == {
        "legacy_token_scoped": False,
        "all_businesses": True,
        "allowed_businesses": ["*"],
    }


def test_project_internal_operator_session_collapses_secret_shaped_grant_labels():
    secret_grant = "tenant access_" + "token=raw_grant_secret"
    principal = build_internal_operator_principal(
        actor_ref="admin:sol",
        role="admin",
        allowed_businesses_header=f"artemea, {secret_grant}",
    )

    session = project_internal_operator_session(principal)["business_scope"]

    assert session["legacy_token_scoped"] is False
    assert session["all_businesses"] is False
    assert session["allowed_businesses"] == ["artemea", "[REDACTED]"]
    assert secret_grant not in str(session)
    assert "access_token" not in str(session)


def test_project_internal_operator_session_collapses_partially_redacted_grant_labels():
    partially_redacted_grant = "tenant access_" + "token=[REDACTED]"
    principal = build_internal_operator_principal(
        actor_ref="admin:sol",
        role="admin",
        allowed_businesses_header=partially_redacted_grant,
    )

    session = project_internal_operator_session(principal)["business_scope"]

    assert session["allowed_businesses"] == ["[REDACTED]"]
    assert partially_redacted_grant not in str(session)
    assert "access_token" not in str(session)
