import pytest

from scripts.check_test_collection_regression import (
    CollectionRegression,
    evaluate_collection_regression,
    parse_collected_test_count,
    validate_git_ref_arg,
)


def test_parse_collected_test_count_from_pytest_quiet_summary() -> None:
    output = """
    tests/test_example.py::test_one
    tests/test_example.py::test_two

    2 tests collected in 0.03s
    """

    assert parse_collected_test_count(output) == 2


def test_parse_collected_test_count_rejects_missing_summary() -> None:
    with pytest.raises(ValueError, match="Could not determine pytest collection count"):
        parse_collected_test_count("tests/test_example.py::test_one\n")


def test_evaluate_collection_regression_blocks_deleted_tests_by_default() -> None:
    result = evaluate_collection_regression(base_count=100, current_count=99)

    assert result == CollectionRegression(
        base_count=100,
        current_count=99,
        max_drop=0,
        min_current=None,
        passed=False,
        message="Test collection regressed by 1 test(s): base=100 current=99 max_drop=0",
    )


def test_evaluate_collection_regression_allows_explicit_drop_budget() -> None:
    result = evaluate_collection_regression(base_count=100, current_count=99, max_drop=1)

    assert result.passed is True
    assert result.message == "Test collection guard passed: base=100 current=99 max_drop=1"


def test_evaluate_collection_regression_enforces_minimum_current_count() -> None:
    result = evaluate_collection_regression(base_count=None, current_count=980, min_current=981)

    assert result.passed is False
    assert result.message == "Test collection below minimum: current=980 min_current=981"


def test_validate_git_ref_arg_rejects_option_shaped_refs() -> None:
    with pytest.raises(ValueError, match="must not start"):
        validate_git_ref_arg("--upload-pack=/tmp/evil")


def test_validate_git_ref_arg_rejects_control_characters() -> None:
    with pytest.raises(ValueError, match="control characters"):
        validate_git_ref_arg("main\nother")


def test_validate_git_ref_arg_accepts_normal_branch_names() -> None:
    branch_name = "origin/feat/orvo-brain-control-plane"

    assert validate_git_ref_arg(branch_name) == branch_name
