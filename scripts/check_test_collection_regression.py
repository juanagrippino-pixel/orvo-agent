#!/usr/bin/env python3
"""Guard against accidental pytest coverage/test-collection regressions.

This script is intentionally lightweight: it uses the local Python interpreter and
pytest's collection phase, then compares the current tree's collected test count
against either a baseline Git ref or an explicit minimum. It is designed for
worker/integration gates where a branch must not get green by deleting tests.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


_COLLECTION_PATTERNS = (
    re.compile(r"(?m)^\s*(\d+)\s+tests?\s+collected\b"),
    re.compile(r"(?m)^\s*collected\s+(\d+)\s+items?\b"),
)

_UNSAFE_GIT_REF_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class CollectionRegression:
    base_count: int | None
    current_count: int
    max_drop: int
    min_current: int | None
    passed: bool
    message: str


def parse_collected_test_count(output: str) -> int:
    """Extract pytest's collected-test count from collect-only output."""

    for pattern in _COLLECTION_PATTERNS:
        match = pattern.search(output)
        if match:
            return int(match.group(1))
    raise ValueError("Could not determine pytest collection count from pytest output")


def evaluate_collection_regression(
    *,
    base_count: int | None,
    current_count: int,
    max_drop: int = 0,
    min_current: int | None = None,
) -> CollectionRegression:
    """Evaluate whether the current collection count is acceptable."""

    if max_drop < 0:
        raise ValueError("max_drop must be non-negative")
    if current_count < 0:
        raise ValueError("current_count must be non-negative")
    if base_count is not None and base_count < 0:
        raise ValueError("base_count must be non-negative")
    if min_current is not None and min_current < 0:
        raise ValueError("min_current must be non-negative")

    if min_current is not None and current_count < min_current:
        return CollectionRegression(
            base_count=base_count,
            current_count=current_count,
            max_drop=max_drop,
            min_current=min_current,
            passed=False,
            message=f"Test collection below minimum: current={current_count} min_current={min_current}",
        )

    if base_count is not None:
        drop = base_count - current_count
        if drop > max_drop:
            return CollectionRegression(
                base_count=base_count,
                current_count=current_count,
                max_drop=max_drop,
                min_current=min_current,
                passed=False,
                message=(
                    f"Test collection regressed by {drop} test(s): "
                    f"base={base_count} current={current_count} max_drop={max_drop}"
                ),
            )
        return CollectionRegression(
            base_count=base_count,
            current_count=current_count,
            max_drop=max_drop,
            min_current=min_current,
            passed=True,
            message=f"Test collection guard passed: base={base_count} current={current_count} max_drop={max_drop}",
        )

    return CollectionRegression(
        base_count=None,
        current_count=current_count,
        max_drop=max_drop,
        min_current=min_current,
        passed=True,
        message=f"Test collection guard passed: current={current_count}",
    )


def _run_command(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def validate_git_ref_arg(ref: str) -> str:
    """Validate a user-supplied Git ref before passing it to ``git``.

    The command runner never uses a shell, so shell injection is not possible here.
    This validation instead prevents option-style refs and control characters from
    being forwarded to Git's argument parser.
    """

    if not ref:
        raise ValueError("base_ref must not be empty")
    if ref.startswith("-"):
        raise ValueError("base_ref must not start with '-'")
    if _UNSAFE_GIT_REF_CHARS.search(ref):
        raise ValueError("base_ref must not contain control characters")
    return ref


def collect_pytest_count(*, cwd: Path, pytest_args: Sequence[str]) -> int:
    """Run pytest collection in ``cwd`` and return the collected test count."""

    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", *pytest_args]
    result = _run_command(command, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            "pytest collection failed with exit code "
            f"{result.returncode} in {cwd}:\n{result.stdout}"
        )
    return parse_collected_test_count(result.stdout)


def collect_base_ref_count(*, repo_root: Path, base_ref: str, pytest_args: Sequence[str]) -> int:
    """Collect pytest count for a Git ref in a temporary detached worktree."""

    safe_base_ref = validate_git_ref_arg(base_ref)
    with tempfile.TemporaryDirectory(prefix="orvo-test-collection-base-") as temp_dir:
        base_worktree = Path(temp_dir) / "base"
        add_result = _run_command(
            ["git", "worktree", "add", "--detach", str(base_worktree), safe_base_ref],
            cwd=repo_root,
        )
        try:
            if add_result.returncode != 0:
                raise RuntimeError(
                    f"Could not create temporary base worktree for {safe_base_ref}:\n{add_result.stdout}"
                )
            return collect_pytest_count(cwd=base_worktree, pytest_args=pytest_args)
        finally:
            _run_command(["git", "worktree", "remove", "--force", str(base_worktree)], cwd=repo_root)


def _normalise_pytest_args(pytest_args: Sequence[str]) -> list[str]:
    args = list(pytest_args)
    if args and args[0] == "--":
        args = args[1:]
    return args or ["tests"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail if pytest collection drops below a base ref or explicit minimum.",
    )
    parser.add_argument(
        "--base-ref",
        help="Optional Git ref to compare against using a temporary detached worktree.",
    )
    parser.add_argument(
        "--max-drop",
        type=int,
        default=0,
        help="Allowed test-count drop versus --base-ref (default: 0).",
    )
    parser.add_argument(
        "--min-current",
        type=int,
        help="Optional absolute minimum collected test count for the current tree.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed after -- to pytest collection; defaults to tests.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_drop < 0:
        parser.error("--max-drop must be non-negative")
    if args.min_current is not None and args.min_current < 0:
        parser.error("--min-current must be non-negative")
    pytest_args = _normalise_pytest_args(args.pytest_args)
    repo_root = Path.cwd()

    try:
        current_count = collect_pytest_count(cwd=repo_root, pytest_args=pytest_args)
        base_count = None
        if args.base_ref:
            base_count = collect_base_ref_count(
                repo_root=repo_root,
                base_ref=args.base_ref,
                pytest_args=pytest_args,
            )
        result = evaluate_collection_regression(
            base_count=base_count,
            current_count=current_count,
            max_drop=args.max_drop,
            min_current=args.min_current,
        )
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(result.message)
    return 0 if result.passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
