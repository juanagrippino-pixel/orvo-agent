import subprocess
from pathlib import Path

from scripts.check_worker_handoff_manifests import (
    REQUIRED_FIELDS,
    WorkerHandoffManifest,
    discover_manifest_paths,
    parse_manifest,
    validate_manifest,
    validate_manifest_paths,
    verify_manifest_git_claims,
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


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _make_git_repo_with_manifest(tmp_path: Path, omitted_file: str | None = None) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "orvo-tests@example.invalid")
    _run_git(repo, "config", "user.name", "Orvo Tests")

    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "base")
    base_sha = _run_git(repo, "rev-parse", "HEAD")

    (repo / "scripts").mkdir()
    (repo / "scripts" / "guard.py").write_text("print('guard')\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_guard.py").write_text("def test_guard():\n    assert True\n", encoding="utf-8")
    _run_git(repo, "checkout", "-b", "codex/sample-guard")
    _run_git(repo, "add", "scripts/guard.py", "tests/test_guard.py")
    _run_git(repo, "commit", "-m", "add guard")
    head_sha = _run_git(repo, "rev-parse", "HEAD")

    changed_files = ["scripts/guard.py", "tests/test_guard.py"]
    if omitted_file is not None:
        changed_files.remove(omitted_file)
    files_changed_block = "\n".join(f"  - {path}" for path in changed_files)
    manifest_path = repo / "worker.md"
    manifest_path.write_text(
        VALID_MANIFEST.replace("/root/orvo-agent-worktrees/sample-task", str(repo))
        .replace("codex/sample-task", "codex/sample-guard")
        .replace("3f768883d3fc41cc19fab36acf63a23794324540", base_sha)
        .replace("uncommitted", head_sha)
        .replace("dirty-blocked", "review-ready")
        .replace(
            "  - scripts/check_worker_handoff_manifests.py\n  - tests/test_worker_handoff_manifest_guard.py",
            files_changed_block,
        ),
        encoding="utf-8",
    )
    return repo, manifest_path


def test_verify_manifest_git_claims_accepts_existing_head_and_exact_diff(tmp_path: Path) -> None:
    repo, manifest_path = _make_git_repo_with_manifest(tmp_path)

    result = verify_manifest_git_claims(parse_manifest(manifest_path), repo_root=repo)

    assert result.passed is True
    assert result.problems == ()


def test_verify_manifest_git_claims_rejects_head_sha_that_is_not_branch_head(tmp_path: Path) -> None:
    repo, manifest_path = _make_git_repo_with_manifest(tmp_path)
    stale_head = _run_git(repo, "rev-parse", "HEAD")
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("newer branch head\n", encoding="utf-8")
    _run_git(repo, "add", "docs/note.md")
    _run_git(repo, "commit", "-m", "advance branch head")

    result = verify_manifest_git_claims(parse_manifest(manifest_path), repo_root=repo)

    assert result.passed is False
    assert result.problems == (
        "head_sha does not match branch head for codex/sample-guard: "
        f"manifest {stale_head}, branch {_run_git(repo, 'rev-parse', 'HEAD')}",
    )


def test_verify_manifest_git_claims_allows_manifest_only_branch_head_advance(tmp_path: Path) -> None:
    repo, manifest_path = _make_git_repo_with_manifest(tmp_path)
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8") + "\nManifest bookkeeping note.\n",
        encoding="utf-8",
    )
    _run_git(repo, "add", "worker.md")
    _run_git(repo, "commit", "-m", "add manifest bookkeeping")

    result = verify_manifest_git_claims(parse_manifest(manifest_path), repo_root=repo)

    assert result.passed is True
    assert result.problems == ()


def test_verify_manifest_git_claims_rejects_files_changed_that_do_not_match_diff(tmp_path: Path) -> None:
    repo, manifest_path = _make_git_repo_with_manifest(tmp_path, omitted_file="tests/test_guard.py")

    result = verify_manifest_git_claims(parse_manifest(manifest_path), repo_root=repo)

    assert result.passed is False
    assert result.problems == (
        "files_changed does not match git diff base_sha...head_sha; missing from manifest: tests/test_guard.py",
    )


def test_verify_manifest_git_claims_allows_uncommitted_head_when_worktree_exists(tmp_path: Path) -> None:
    repo, manifest_path = _make_git_repo_with_manifest(tmp_path)
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            _run_git(repo, "rev-parse", "HEAD"),
            "uncommitted",
        ),
        encoding="utf-8",
    )

    result = verify_manifest_git_claims(parse_manifest(manifest_path), repo_root=repo)

    assert result.passed is True
    assert result.problems == ()
