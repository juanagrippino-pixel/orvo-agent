"""Internal service catalog for Orvo Brain control-plane components.

The catalog is intentionally static and dependency-free: it gives operators,
reviewers, and future gateway/broker code one typed place to discover component
ownership, source-of-truth modules, docs, tests, and runtime surfaces before
Orvo introduces heavier infrastructure.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ComponentStatus = Literal["active", "draft", "planned"]
ComponentTier = Literal["control_plane", "runtime", "surface", "platform"]
RuntimeSurface = Literal[
    "compiled_runtime",
    "connector_execution",
    "semantic_validation",
    "run_ledger",
    "case_engine",
    "operator_api",
    "dispatch",
    "developer_platform",
]

SERVICE_CATALOG_SCHEMA_VERSION = "2026-05-31.service-catalog.v1"


class ServiceComponent(BaseModel):
    """Typed ownership record for one Orvo control-plane component."""

    model_config = ConfigDict(frozen=True)

    component_id: str
    display_name: str
    owner_department: str
    source_of_truth: str
    status: ComponentStatus
    tier: ComponentTier
    docs: tuple[str, ...] = Field(default_factory=tuple)
    code_paths: tuple[str, ...] = Field(default_factory=tuple)
    test_paths: tuple[str, ...] = Field(default_factory=tuple)
    dependencies: tuple[str, ...] = Field(default_factory=tuple)
    runtime_surfaces: tuple[RuntimeSurface, ...] = Field(default_factory=tuple)
    observability_signals: tuple[str, ...] = Field(default_factory=tuple)

    def public_manifest(self) -> dict[str, Any]:
        """Return deterministic, public metadata safe for docs/API projection."""

        return {
            "component_id": self.component_id,
            "display_name": self.display_name,
            "owner_department": self.owner_department,
            "source_of_truth": self.source_of_truth,
            "status": self.status,
            "tier": self.tier,
            "docs": list(self.docs),
            "code_paths": list(self.code_paths),
            "test_paths": list(self.test_paths),
            "dependencies": list(self.dependencies),
            "runtime_surfaces": list(self.runtime_surfaces),
            "observability_signals": list(self.observability_signals),
        }


class ServiceCatalog:
    """Immutable service/component catalog with dependency validation."""

    def __init__(self, components: tuple[ServiceComponent, ...]) -> None:
        ids = [component.component_id for component in components]
        duplicates = sorted({component_id for component_id in ids if ids.count(component_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate service component id: {duplicates[0]}")

        known_ids = set(ids)
        for component in components:
            for dependency in component.dependencies:
                if dependency not in known_ids:
                    raise ValueError(
                        f"unknown service dependency: {component.component_id} -> {dependency}"
                    )

        self._components = components
        self._by_id = {component.component_id: component for component in components}

    @property
    def components(self) -> tuple[ServiceComponent, ...]:
        return self._components

    def get(self, component_id: str) -> ServiceComponent:
        try:
            return self._by_id[component_id]
        except KeyError as exc:
            raise KeyError(f"unknown service component: {component_id}") from exc

    def by_owner(self, owner_department: str) -> list[ServiceComponent]:
        return [
            component
            for component in self._components
            if component.owner_department == owner_department
        ]

    def by_runtime_surface(self, runtime_surface: RuntimeSurface) -> list[ServiceComponent]:
        return [
            component
            for component in self._components
            if runtime_surface in component.runtime_surfaces
        ]

    def public_manifest(self) -> dict[str, Any]:
        return {
            "schema_version": SERVICE_CATALOG_SCHEMA_VERSION,
            "components": [component.public_manifest() for component in self._components],
        }


def default_service_catalog() -> ServiceCatalog:
    """Return the static catalog for current Orvo Brain Python-runtime components."""

    return ServiceCatalog(
        (
            ServiceComponent(
                component_id="compiled_runtime",
                display_name="Compiled Business Runtime",
                owner_department="Edge / Developer Platform",
                source_of_truth="app.brain.runtime",
                status="active",
                tier="control_plane",
                docs=("docs/specs/compiled-runtime-contract.md",),
                code_paths=("app/brain/runtime.py",),
                test_paths=(
                    "tests/test_brain_runtime.py",
                    "tests/contracts/test_compiled_runtime_contract.py",
                ),
                runtime_surfaces=("compiled_runtime",),
                observability_signals=("runtime_id", "compiled_from_hash"),
            ),
            ServiceComponent(
                component_id="connector_registry",
                display_name="Connector Registry",
                owner_department="Connector / Ecosystem Platform",
                source_of_truth="app.brain.connector_registry",
                status="active",
                tier="control_plane",
                docs=("docs/specs/connector-registry-contract.md",),
                code_paths=("app/brain/connector_registry.py", "app/brain/adapters/"),
                test_paths=(
                    "tests/test_brain_connector_registry.py",
                    "tests/contracts/test_connector_registry_contract.py",
                ),
                runtime_surfaces=("connector_execution",),
                observability_signals=("connector_type", "connector_id", "health_state"),
            ),
            ServiceComponent(
                component_id="metric_registry",
                display_name="Metric Registry",
                owner_department="Semantic Intelligence Platform",
                source_of_truth="app.brain.semantics.metric_registry",
                status="active",
                tier="control_plane",
                docs=("docs/specs/metric-registry-contract.md",),
                code_paths=("app/brain/semantics/metric_registry.py",),
                test_paths=(
                    "tests/contracts/test_metric_registry_contract.py",
                    "tests/contracts/test_metric_validation_contract.py",
                ),
                runtime_surfaces=("semantic_validation",),
                observability_signals=("metric_key", "metric_family", "evidence_source"),
            ),
            ServiceComponent(
                component_id="run_ledger",
                display_name="Run Ledger",
                owner_department="SRE / Operations",
                source_of_truth="app.brain.run_ledger",
                status="active",
                tier="runtime",
                docs=("docs/specs/compiled-runtime-contract.md",),
                code_paths=("app/brain/run_ledger.py", "app/brain/execution_ledger.py"),
                test_paths=("tests/test_brain_run_ledger.py",),
                dependencies=("compiled_runtime",),
                runtime_surfaces=("run_ledger",),
                observability_signals=("run_id", "run_status", "started_at", "finished_at"),
            ),
            ServiceComponent(
                component_id="operational_cases",
                display_name="Operational Cases",
                owner_department="Work Management Core",
                source_of_truth="app.brain.operational_cases",
                status="active",
                tier="control_plane",
                docs=("docs/specs/d2c-case-family-catalog.md",),
                code_paths=("app/brain/operational_cases.py", "app/brain/operator_views.py"),
                test_paths=(
                    "tests/test_brain_operational_cases.py",
                    "tests/test_operator_case_views.py",
                ),
                dependencies=("metric_registry", "run_ledger"),
                runtime_surfaces=("case_engine",),
                observability_signals=("case_id", "case_type", "status", "priority"),
            ),
            ServiceComponent(
                component_id="operator_api",
                display_name="Internal Operator API",
                owner_department="Operator Surfaces",
                source_of_truth="app.brain.operator_api",
                status="active",
                tier="surface",
                docs=("docs/specs/d2c-operator-surface-contract.md",),
                code_paths=("app/brain/operator_api.py",),
                test_paths=("tests/test_internal_operator_api.py",),
                dependencies=("operational_cases", "run_ledger"),
                runtime_surfaces=("operator_api",),
                observability_signals=("business_id", "actor", "action_key"),
            ),
            ServiceComponent(
                component_id="delivery_dispatch",
                display_name="Delivery Dispatch",
                owner_department="Operator Surfaces",
                source_of_truth="app.brain.dispatch",
                status="active",
                tier="runtime",
                docs=("docs/orvo-brain-runtime.md",),
                code_paths=("app/brain/dispatch.py", "app/brain/delivery.py"),
                test_paths=("tests/test_brain_dispatch.py", "tests/test_brain_delivery.py"),
                dependencies=("compiled_runtime", "operational_cases"),
                runtime_surfaces=("dispatch",),
                observability_signals=("idempotency_key", "delivery_status"),
            ),
            ServiceComponent(
                component_id="edge_developer_platform",
                display_name="Edge / Developer Platform Conventions",
                owner_department="Edge / Developer Platform",
                source_of_truth="app.brain.service_catalog",
                status="draft",
                tier="platform",
                docs=(
                    "docs/architecture/vasilios-atlassian-platform-patterns.md",
                    "docs/specs/service-catalog-contract.md",
                ),
                code_paths=("app/brain/service_catalog.py",),
                test_paths=("tests/contracts/test_service_catalog_contract.py",),
                dependencies=("compiled_runtime", "connector_registry", "run_ledger"),
                runtime_surfaces=("developer_platform",),
                observability_signals=("component_id", "owner_department"),
            ),
        )
    )


def service_catalog_manifest() -> dict[str, Any]:
    """Return the default public service catalog manifest."""

    return default_service_catalog().public_manifest()
