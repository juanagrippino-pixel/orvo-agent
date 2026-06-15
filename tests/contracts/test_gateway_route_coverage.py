from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from app.brain.gateway_contracts import default_gateway_service_catalog


@dataclass(frozen=True)
class InternalBrainRouteSpec:
    method: str
    path_pattern: str
    function_name: str


def _iter_registered_internal_brain_routes() -> list[InternalBrainRouteSpec]:
    route_specs: list[InternalBrainRouteSpec] = []
    routes_dir = Path(__file__).parents[2] / "app" / "http" / "internal_brain"

    for route_file in sorted(routes_dir.glob("*.py")):
        if route_file.name in {"__init__.py", "common.py"}:
            continue

        tree = ast.parse(
            route_file.read_text(encoding="utf-8"), filename=str(route_file)
        )
        for statement in ast.walk(tree):
            if not isinstance(statement, ast.FunctionDef):
                continue
            if not statement.decorator_list:
                continue

            for decorator in statement.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    continue

                path_pattern = decorator.args[0].value
                if not isinstance(path_pattern, str) or not path_pattern.startswith(
                    "/internal/brain"
                ):
                    continue

                route_specs.append(
                    InternalBrainRouteSpec(
                        method=decorator.func.attr.upper(),
                        path_pattern=path_pattern,
                        function_name=statement.name,
                    )
                )

    return route_specs


def test_default_gateway_service_catalog_covers_registered_internal_brain_routes():
    catalog = default_gateway_service_catalog()
    missing = []

    for route_spec in _iter_registered_internal_brain_routes():
        if not any(
            entry.method == route_spec.method
            and entry.path_pattern == route_spec.path_pattern
            for entry in catalog.entries
        ):
            missing.append(
                f"{route_spec.method} {route_spec.path_pattern} ({route_spec.function_name})"
            )

    assert missing == []
