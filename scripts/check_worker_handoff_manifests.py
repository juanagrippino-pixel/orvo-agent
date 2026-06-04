#!/usr/bin/env python3
"""Validate autonomous worker handoff manifest Markdown files.

The autonomous build-loop contract requires every implementation worker to leave a
stable handoff manifest. This guard intentionally validates the documented
Markdown shape without depending on a heavy parser or adding dependencies.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REQUIRED_FIELDS: tuple[str, ...] = (
    "task_id",
    "objective",
    "bounded_context",
    "worktree_path",
    "branch",
    "base_sha",
    "head_sha",
    "status",
    "files_changed",
    "tests_run",
    "docs_updated",
    "risks",
    "secrets_checked",
    "integration_notes",
    "recommended_next_action",
)

LIST_FIELDS: frozenset[str] = frozenset(
    {
        "files_changed",
        "tests_run",
        "docs_updated",
        "risks",
    }
)

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "clean",
        "dirty-blocked",
        "review-ready",
        "merged",
        "abandoned",
    }
)


@dataclass(frozen=True)
class WorkerHandoffManifest:
    path: Path
    fields: dict[str, str]
    lists: dict[str, list[str]]


@dataclass(frozen=True)
class WorkerHandoffManifestValidation:
    path: Path
    missing_fields: tuple[str, ...] = ()
    empty_list_fields: tuple[str, ...] = ()
    invalid_status: str | None = None

    @property
    def passed(self) -> bool:
        return not self.missing_fields and not self.empty_list_fields and self.invalid_status is None

    def describe(self) -> str:
        problems: list[str] = []
        if self.missing_fields:
            problems.append(f"missing fields: {', '.join(self.missing_fields)}")
        if self.empty_list_fields:
            problems.append(f"empty list fields: {', '.join(self.empty_list_fields)}")
        if self.invalid_status is not None:
            valid = ", ".join(sorted(VALID_STATUSES))
            problems.append(f"invalid status {self.invalid_status!r}; expected one of: {valid}")
        if not problems:
            return f"{self.path}: ok"
        return f"{self.path}: " + "; ".join(problems)


@dataclass(frozen=True)
class WorkerHandoffManifestGitValidation:
    path: Path
    problems: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.problems

    def describe(self) -> str:
        if not self.problems:
            return f"{self.path}: git claims ok"
        return f"{self.path}: " + "; ".join(self.problems)


def _split_manifest_field(line: str) -> tuple[str, str] | None:
    """Return ``(field, value)`` for a top-level ``- field: value`` line."""

    if not line.startswith("- ") or ":" not in line:
        return None
    raw_field, raw_value = line[2:].split(":", 1)
    field = raw_field.strip()
    if not field:
        return None
    return field, raw_value.strip()


def parse_manifest(path: Path) -> WorkerHandoffManifest:
    """Parse a worker handoff manifest Markdown file.

    The parser recognizes the documented manifest block shape:

    ``- field: scalar`` for scalar fields, and ``- field:`` followed by
    indented ``- item`` entries for list fields.
    """

    fields: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current_list_field: str | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        field_value = _split_manifest_field(line)
        if field_value is not None:
            field, value = field_value
            current_list_field = field if field in LIST_FIELDS else None
            if field in LIST_FIELDS:
                lists.setdefault(field, [])
                if value:
                    lists[field].append(value)
            else:
                fields[field] = value
            continue

        if current_list_field and line.startswith("  - "):
            item = line[4:].strip()
            if item:
                lists[current_list_field].append(item)
            continue

        if line and not line.startswith(" "):
            current_list_field = None

    return WorkerHandoffManifest(path=path, fields=fields, lists=lists)


def _has_required_field(manifest: WorkerHandoffManifest, field: str) -> bool:
    if field in LIST_FIELDS:
        return field in manifest.lists
    return bool(manifest.fields.get(field))


def validate_manifest(manifest: WorkerHandoffManifest) -> WorkerHandoffManifestValidation:
    """Validate one parsed manifest against the required handoff contract."""

    missing_fields = tuple(field for field in REQUIRED_FIELDS if not _has_required_field(manifest, field))
    empty_list_fields = tuple(
        field for field in LIST_FIELDS if field in manifest.lists and not manifest.lists[field]
    )
    status = manifest.fields.get("status")
    invalid_status = status if status and status not in VALID_STATUSES else None

    return WorkerHandoffManifestValidation(
        path=manifest.path,
        missing_fields=missing_fields,
        empty_list_fields=empty_list_fields,
        invalid_status=invalid_status,
    )


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_commit_exists(repo_root: Path, revision: str) -> bool:
    if not revision:
        return False
    return _git(repo_root, "cat-file", "-e", f"{revision}^{{commit}}").returncode == 0


def _git_branch_exists(repo_root: Path, branch: str) -> bool:
    if not branch:
        return False
    local = _git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    if local.returncode == 0:
        return True
    remote = _git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
    return remote.returncode == 0


def _git_status_short(worktree_path: Path) -> tuple[bool, str]:
    result = _git(worktree_path, "status", "--short")
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, result.stdout.strip()


def _changed_files_between(repo_root: Path, base_sha: str, head_sha: str) -> tuple[str, ...] | None:
    result = _git(repo_root, "diff", "--name-only", f"{base_sha}...{head_sha}")
    if result.returncode != 0:
        return None
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def verify_manifest_git_claims(
    manifest: WorkerHandoffManifest,
    *,
    repo_root: Path = Path("."),
) -> WorkerHandoffManifestGitValidation:
    """Verify optional git-backed handoff claims for a parsed manifest.

    This stricter check is intentionally opt-in for the CLI because old durable
    manifests can contain human placeholders. It verifies claims that can be
    proven from the local repository without trusting chat summaries: branch or
    worktree presence, commit existence, and exact ``files_changed`` membership
    for committed manifests.
    """

    problems: list[str] = []
    repo_root = repo_root.resolve()
    worktree_path = manifest.fields.get("worktree_path", "")
    branch = manifest.fields.get("branch", "")
    worktree = Path(worktree_path) if worktree_path else None
    if worktree is not None and not worktree.exists() and not _git_branch_exists(repo_root, branch):
        problems.append(
            "worktree_path does not exist and branch cannot be found locally or under origin: "
            f"{worktree_path} / {branch}"
        )

    status = manifest.fields.get("status", "")
    if worktree is not None and worktree.exists() and status:
        status_read, status_output = _git_status_short(worktree)
        if not status_read:
            problems.append(f"could not read worktree git status: {status_output}")
        elif status in {"clean", "review-ready", "merged"} and status_output:
            problems.append(
                f"status {status!r} claims a clean handoff but worktree has uncommitted changes"
            )
        elif status == "dirty-blocked" and not status_output:
            problems.append("status 'dirty-blocked' claims uncommitted work but worktree is clean")

    base_sha = manifest.fields.get("base_sha", "")
    head_sha = manifest.fields.get("head_sha", "")
    base_exists = _git_commit_exists(repo_root, base_sha)
    if not base_exists:
        problems.append(f"base_sha does not resolve to a commit: {base_sha}")

    if head_sha == "uncommitted":
        return WorkerHandoffManifestGitValidation(path=manifest.path, problems=tuple(problems))

    head_exists = _git_commit_exists(repo_root, head_sha)
    if not head_exists:
        problems.append(f"head_sha does not resolve to a commit: {head_sha}")

    if base_exists and head_exists:
        changed_files = _changed_files_between(repo_root, base_sha, head_sha)
        if changed_files is None:
            problems.append("could not compute git diff base_sha...head_sha")
        else:
            manifest_files = tuple(
                item for item in manifest.lists.get("files_changed", []) if item and item != "none"
            )
            changed_set = set(changed_files)
            manifest_set = set(manifest_files)
            missing = tuple(sorted(changed_set - manifest_set))
            extra = tuple(sorted(manifest_set - changed_set))
            if missing or extra:
                parts: list[str] = ["files_changed does not match git diff base_sha...head_sha"]
                if missing:
                    parts.append(f"missing from manifest: {', '.join(missing)}")
                if extra:
                    parts.append(f"not present in diff: {', '.join(extra)}")
                problems.append("; ".join(parts))

    return WorkerHandoffManifestGitValidation(path=manifest.path, problems=tuple(problems))


def discover_manifest_paths(root: Path) -> list[Path]:
    """Return committed-style worker manifest paths in deterministic order."""

    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return sorted(path for path in root.glob("*.md") if path.is_file())


def validate_manifest_paths(paths: Iterable[Path]) -> list[WorkerHandoffManifestValidation]:
    """Validate all manifest paths and return only failures."""

    failures: list[WorkerHandoffManifestValidation] = []
    for path in paths:
        result = validate_manifest(parse_manifest(path))
        if not result.passed:
            failures.append(result)
    return failures


def verify_manifest_git_claim_paths(
    paths: Iterable[Path],
    *,
    repo_root: Path = Path("."),
) -> list[WorkerHandoffManifestGitValidation]:
    """Verify git-backed claims for all manifest paths and return failures."""

    failures: list[WorkerHandoffManifestGitValidation] = []
    for path in paths:
        result = verify_manifest_git_claims(parse_manifest(path), repo_root=repo_root)
        if not result.passed:
            failures.append(result)
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate docs/workers handoff manifests against the autonomous worker contract.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Manifest files or directories to validate; defaults to docs/workers.",
    )
    parser.add_argument(
        "--verify-git",
        action="store_true",
        help="Also verify branch/worktree, commit, and files_changed claims against the local git repository.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root for --verify-git; defaults to the current directory.",
    )
    return parser


def _expand_paths(paths: Sequence[Path]) -> list[Path]:
    roots = list(paths) or [Path("docs/workers")]
    manifest_paths: list[Path] = []
    for root in roots:
        manifest_paths.extend(discover_manifest_paths(root))
    return sorted(dict.fromkeys(manifest_paths))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest_paths = _expand_paths(args.paths)
    if not manifest_paths:
        parser.error("no worker handoff manifests found")

    shape_failures = validate_manifest_paths(manifest_paths)
    git_failures = (
        verify_manifest_git_claim_paths(manifest_paths, repo_root=args.repo_root) if args.verify_git else []
    )
    if shape_failures or git_failures:
        for failure in [*shape_failures, *git_failures]:
            print(failure.describe())
        return 1

    suffix = " with git claims verified" if args.verify_git else ""
    print(f"Worker handoff manifest guard passed: {len(manifest_paths)} manifest(s) checked{suffix}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
