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
