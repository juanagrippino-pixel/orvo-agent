from __future__ import annotations

from pathlib import Path


def _line_count(path: Path) -> int:
    return sum(1 for _ in path.open())


def test_operator_api_and_server_god_files_are_decomposed():
    root = Path(__file__).resolve().parents[1]
    operator_api_entrypoint = root / "app" / "brain" / "operator_api" / "__init__.py"
    assert operator_api_entrypoint.exists()
    assert _line_count(operator_api_entrypoint) <= 400
    assert _line_count(root / "server.py") <= 400


def test_new_python_modules_stay_below_structural_line_budget():
    root = Path(__file__).resolve().parents[1]
    oversized: dict[str, int] = {}
    for module_path in [root / "server.py", root / "app" / "brain" / "operator_api.py"]:
        if module_path.exists():
            count = _line_count(module_path)
            if count > 400:
                oversized[str(module_path.relative_to(root))] = count
    for package in [root / "app" / "brain" / "operator_api", root / "app" / "http"]:
        if not package.exists():
            continue
        for module_path in sorted(package.rglob("*.py")):
            count = _line_count(module_path)
            if count > 400:
                oversized[str(module_path.relative_to(root))] = count
    assert oversized == {}
