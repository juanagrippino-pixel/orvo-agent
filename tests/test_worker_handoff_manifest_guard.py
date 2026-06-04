from pathlib import Path

from scripts.check_worker_handoff_manifests import (
    REQUIRED_FIELDS,
    WorkerHandoffManifest,
    discover_manifest_paths,
    parse_manifest,
    validate_manifest,
    validate_manifest_paths,
)


VALID_MANIFEST = """# Worker handoff manifest — sample

- task_id: sample-task
- objective: Prove the manifest validator accepts the documented shape.
- bounded_context: Engineering Factory / Release Integration
- worktree_path: /root/orvo-agent-worktrees/sample-task
- branch: codex/sample-task
- base_sha: 3f768883d3fc41cc19fab36acf63a23794324540
- head_sha: uncommitted
- status: dirty-blocked
- files_changed:
  - scripts/check_worker_handoff_manifests.py
  - tests/test_worker_handoff_manifest_guard.py
- tests_run:
  - `pytest tests/test_worker_handoff_manifest_guard.py -q` => pass
- docs_updated:
  - none
- risks:
  - none
- secrets_checked: yes; no secrets in synthetic manifest
- integration_notes: Merge after focused and full tests pass.
- recommended_next_action: review
"""


def test_parse_manifest_extracts_scalars_and_required_lists(tmp_path: Path) -> None:
    manifest_path = tmp_path / "worker.md"
    manifest_path.write_text(VALID_MANIFEST, encoding="utf-8")

    manifest = parse_manifest(manifest_path)

    assert manifest == WorkerHandoffManifest(
        path=manifest_path,
        fields={
            "task_id": "sample-task",
            "objective": "Prove the manifest validator accepts the documented shape.",
            "bounded_context": "Engineering Factory / Release Integration",
            "worktree_path": "/root/orvo-agent-worktrees/sample-task",
            "branch": "codex/sample-task",
            "base_sha": "3f768883d3fc41cc19fab36acf63a23794324540",
            "head_sha": "uncommitted",
            "status": "dirty-blocked",
            "secrets_checked": "yes; no secrets in synthetic manifest",
            "integration_notes": "Merge after focused and full tests pass.",
            "recommended_next_action": "review",
        },
        lists={
            "files_changed": [
                "scripts/check_worker_handoff_manifests.py",
                "tests/test_worker_handoff_manifest_guard.py",
            ],
            "tests_run": ["`pytest tests/test_worker_handoff_manifest_guard.py -q` => pass"],
            "docs_updated": ["none"],
            "risks": ["none"],
        },
    )


def test_validate_manifest_reports_all_missing_required_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "worker.md"
    manifest_path.write_text("# Worker handoff manifest\n\n- task_id: sample-task\n", encoding="utf-8")

    result = validate_manifest(parse_manifest(manifest_path))

    assert result.passed is False
    assert result.missing_fields == tuple(field for field in REQUIRED_FIELDS if field != "task_id")


def test_validate_manifest_rejects_empty_required_list(tmp_path: Path) -> None:
    manifest_path = tmp_path / "worker.md"
    manifest_path.write_text(VALID_MANIFEST.replace("  - scripts/check_worker_handoff_manifests.py\n  - tests/test_worker_handoff_manifest_guard.py\n", ""), encoding="utf-8")

    result = validate_manifest(parse_manifest(manifest_path))

    assert result.passed is False
    assert result.empty_list_fields == ("files_changed",)


def test_validate_manifest_rejects_unknown_status(tmp_path: Path) -> None:
    manifest_path = tmp_path / "worker.md"
    manifest_path.write_text(VALID_MANIFEST.replace("- status: dirty-blocked", "- status: almost-done"), encoding="utf-8")

    result = validate_manifest(parse_manifest(manifest_path))

    assert result.passed is False
    assert result.invalid_status == "almost-done"


def test_validate_manifest_paths_accepts_current_committed_worker_manifests() -> None:
    paths = discover_manifest_paths(Path("docs/workers"))

    assert paths, "expected committed docs/workers manifests to be discoverable"
    assert validate_manifest_paths(paths) == []
