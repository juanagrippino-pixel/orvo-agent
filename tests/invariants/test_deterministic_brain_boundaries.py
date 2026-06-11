"""Invariant tests for Orvo Brain deterministic-core boundaries.

The D2C control plane may use LLM-backed conversation surfaces elsewhere in the
application, but app.brain owns metrics, detections, cases, workflow decisions,
run ledgers, and operator projections. Those modules must not import LLM/chat
SDKs or the conversational graph, otherwise copy-generation code can drift into
canonical control-plane state creation.
"""

from __future__ import annotations

import ast
from pathlib import Path


_FORBIDDEN_IMPORT_PREFIXES = (
    "app.conversation",
    "langchain",
    "langgraph",
    "openai",
    "anthropic",
    "langchain_anthropic",
    "langchain_core",
)


def _imported_module_names(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(), filename=str(module_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_brain_control_plane_modules_do_not_import_llm_or_conversation_boundaries():
    repo_root = Path(__file__).resolve().parents[2]
    brain_root = repo_root / "app" / "brain"

    violations: dict[str, list[str]] = {}
    for module_path in sorted(brain_root.rglob("*.py")):
        imports = _imported_module_names(module_path)
        forbidden = sorted(
            imported
            for imported in imports
            if any(
                imported == prefix or imported.startswith(f"{prefix}.")
                for prefix in _FORBIDDEN_IMPORT_PREFIXES
            )
        )
        if forbidden:
            violations[str(module_path.relative_to(repo_root))] = forbidden

    assert violations == {}
