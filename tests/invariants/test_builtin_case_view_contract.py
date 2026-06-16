from app.brain.operator_views import builtin_case_views, parse_case_jql


def test_builtin_case_views_stay_readonly_route_scoped_and_parser_compatible():
    """Built-in case views must remain thin projections over canonical JQL.

    This locks three safety properties for every shipped built-in view:
    - tenant scope stays route-owned rather than embedded in JQL text,
    - the view remains read-only metadata rather than a second source of truth,
    - the same allowlisted parser used by direct case queries can compile it.
    """

    views = builtin_case_views()

    assert views
    assert len({view["view_id"] for view in views}) == len(views)

    for view in views:
        assert view["readonly"] is True
        assert "business_id" not in view["jql"]

        parsed = parse_case_jql(view["jql"])

        assert parsed.raw == view["jql"]
        assert parsed.clauses
        assert parsed.normalized == view["jql"]
