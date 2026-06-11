"""Internal service catalog for Orvo Brain control-plane components.

The catalog is intentionally static and dependency-free: it gives operators,
reviewers, and future gateway/broker code one typed place to discover component
ownership, source-of-truth modules, docs, tests, and runtime surfaces before
Orvo introduces heavier infrastructure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.brain.security.redaction import redact_text

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
SERVICE_CATALOG_CERTIFICATION_SCHEMA_VERSION = "2026-06-11.service-catalog-certification.v1"


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
    runbooks: tuple[str, ...] = Field(default_factory=tuple)
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
            "runbooks": list(self.runbooks),
            "dependencies": list(self.dependencies),
            "runtime_surfaces": list(self.runtime_surfaces),
            "observability_signals": list(self.observability_signals),
        }


class ServiceCatalogCertificationFinding(BaseModel):
    """Safe certification finding for catalog owners and integration reviewers."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["error"] = "error"
    code: str
    component_id: str
    field: str
    message: str


class ServiceCatalogCertificationReport(BaseModel):
    """Deterministic self-service certification report for catalog metadata."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = SERVICE_CATALOG_CERTIFICATION_SCHEMA_VERSION
    ok: bool
    checked_component_count: int
    checked_path_count: int
    findings: tuple[ServiceCatalogCertificationFinding, ...] = Field(default_factory=tuple)


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
                code_paths=("app/brain/operator_api/",),
                test_paths=("tests/test_internal_operator_api.py",),
                dependencies=("operational_cases", "run_ledger"),
                runtime_surfaces=("operator_api",),
                observability_signals=("business_id", "actor", "action_key"),
            ),
            ServiceComponent(
                component_id="gateway_policy",
                display_name="Gateway Policy Contract",
                owner_department="Edge / Developer Platform",
                source_of_truth="app.brain.gateway_policy",
                status="draft",
                tier="platform",
                docs=("docs/specs/gateway-policy-contract.md",),
                code_paths=("app/brain/gateway_policy.py",),
                test_paths=("tests/contracts/test_gateway_policy_contract.py",),
                runbooks=("docs/operability/gateway-policy-telemetry-runbook.md",),
                dependencies=("operator_api", "run_ledger"),
                runtime_surfaces=("operator_api", "developer_platform"),
                observability_signals=(
                    "route_key",
                    "actor_id_redacted",
                    "decision_code",
                    "rate_limit_key_redacted",
                    "idempotency_key_present",
                    "request_id_redacted",
                    "trace_id_redacted",
                    "gateway_telemetry_schema",
                    "provenance_ref",
                ),
            ),
            ServiceComponent(
                component_id="connector_provisioning",
                display_name="Connector Provisioning Contract",
                owner_department="Edge / Developer Platform",
                source_of_truth="app.brain.connector_provisioning",
                status="draft",
                tier="platform",
                docs=("docs/specs/connector-provisioning-contract.md",),
                code_paths=("app/brain/connector_provisioning.py",),
                test_paths=("tests/contracts/test_connector_provisioning_contract.py",),
                dependencies=("connector_registry", "compiled_runtime", "run_ledger"),
                runtime_surfaces=("developer_platform",),
                observability_signals=(
                    "operation_ref",
                    "business_id",
                    "connector_id",
                    "connector_type",
                    "provisioning_issue_code",
                    "provisioning_telemetry_schema",
                    "provenance_ref",
                    "secret_ref_names",
                ),
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


def certify_service_catalog(
    catalog: ServiceCatalog,
    *,
    repo_root: str | Path,
) -> ServiceCatalogCertificationReport:
    """Certify catalog metadata is path-backed and safe for public projection.

    This is a lightweight Python-runtime analogue to platform catalog checks:
    every declared durable artifact should exist in the repo, and catalog text
    must not include secret-shaped material. It deliberately validates metadata
    only; it does not import component modules or execute component code.
    """

    root = Path(repo_root)
    findings: list[ServiceCatalogCertificationFinding] = []
    checked_path_count = 0
    for component in catalog.components:
        findings.extend(_unsafe_metadata_findings(component))
        for field, paths in _component_path_fields(component).items():
            for path in paths:
                checked_path_count += 1
                if not _catalog_path_exists(root, path):
                    findings.append(
                        _certification_finding(
                            component,
                            code="missing_catalog_path",
                            field=field,
                            message="Catalog path must point at an existing repository file or directory.",
                        )
                    )
    return ServiceCatalogCertificationReport(
        ok=not findings,
        checked_component_count=len(catalog.components),
        checked_path_count=checked_path_count,
        findings=tuple(findings),
    )


def _component_path_fields(component: ServiceComponent) -> dict[str, tuple[str, ...]]:
    return {
        "docs": component.docs,
        "code_paths": component.code_paths,
        "test_paths": component.test_paths,
        "runbooks": component.runbooks,
    }


def _catalog_path_exists(repo_root: Path, relative_path: str) -> bool:
    if not relative_path.strip() or Path(relative_path).is_absolute():
        return False
    return (repo_root / relative_path).exists()


def _unsafe_metadata_findings(component: ServiceComponent) -> list[ServiceCatalogCertificationFinding]:
    findings: list[ServiceCatalogCertificationFinding] = []
    scalar_fields = {
        "component_id": component.component_id,
        "display_name": component.display_name,
        "owner_department": component.owner_department,
        "source_of_truth": component.source_of_truth,
    }
    for field, value in scalar_fields.items():
        if _is_unsafe_catalog_text(value):
            findings.append(
                _certification_finding(
                    component,
                    code="unsafe_component_metadata",
                    field=field,
                    message="Catalog metadata must not include secret-shaped material.",
                )
            )

    iterable_fields = {
        "docs": component.docs,
        "code_paths": component.code_paths,
        "test_paths": component.test_paths,
        "runbooks": component.runbooks,
        "dependencies": component.dependencies,
        "runtime_surfaces": component.runtime_surfaces,
        "observability_signals": component.observability_signals,
    }
    for field, values in iterable_fields.items():
        if any(_is_unsafe_catalog_text(value) for value in values):
            findings.append(
                _certification_finding(
                    component,
                    code="unsafe_component_metadata",
                    field=field,
                    message="Catalog metadata must not include secret-shaped material.",
                )
            )
    return findings


def _is_unsafe_catalog_text(value: str) -> bool:
    return redact_text(value) != value


def _certification_finding(
    component: ServiceComponent,
    *,
    code: str,
    field: str,
    message: str,
) -> ServiceCatalogCertificationFinding:
    return ServiceCatalogCertificationFinding(
        code=code,
        component_id=redact_text(component.component_id) or "[REDACTED]",
        field=field,
        message=message,
    )
