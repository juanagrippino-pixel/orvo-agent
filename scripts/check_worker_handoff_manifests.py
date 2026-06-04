#!/usr/bin/env python3
"""Validate autonomous worker handoff manifest Markdown files.

The autonomous build-loop contract requires every implementation worker to leave a
stable handoff manifest. This guard intentionally validates the documented
Markdown shape without depending on a heavy parser or adding dependencies.
"""

from __future__ import annotations

import argparse
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

    failures = validate_manifest_paths(manifest_paths)
    if failures:
        for failure in failures:
            print(failure.describe())
        return 1

    print(f"Worker handoff manifest guard passed: {len(manifest_paths)} manifest(s) checked")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
