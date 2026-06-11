from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.brain.connector_registry import ConnectorRegistry, default_connector_registry
from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseStore,
)
from app.brain.operator_case_projections import source_connectors
from app.brain.run_ledger import ConnectorRunOutcome, RunLedger, RunRecord
from app.brain.security.redaction import redact_secrets

ModuleStatus = Literal["ready", "attention_required", "data_stale", "setup_required"]


@dataclass(frozen=True, slots=True)
class _OSModuleDefinition:
    module_id: str
    label: str
    description: str
    case_types: tuple[str, ...]
    connector_types: tuple[str, ...]
    required_setup: str
    readiness_gated: bool = False


_COMMERCE_ORDER_FAMILIES = frozenset({"commerce.orders", "commerce.revenue"})
_INVENTORY_FAMILIES = frozenset({"commerce.inventory"})


def _connector_types_for_metric_families(
    registry: ConnectorRegistry,
    families: frozenset[str],
) -> tuple[str, ...]:
    connector_types: list[str] = []
    for spec in registry.specs():
        if families.intersection(spec.emitted_metric_families):
            connector_types.append(spec.connector_type)
    return tuple(sorted(connector_types))


def _module_definitions(registry: ConnectorRegistry) -> tuple[_OSModuleDefinition, ...]:
    commerce_connector_types = _connector_types_for_metric_families(registry, _COMMERCE_ORDER_FAMILIES)
    inventory_connector_types = _connector_types_for_metric_families(registry, _INVENTORY_FAMILIES)
    return (
        _OSModuleDefinition(
            module_id="sales_orders",
            label="Sales/orders operating truth",
            description="Tiendanube/orders/revenue evidence and sales-drop cases.",
            case_types=("sales_drop",),
            connector_types=commerce_connector_types,
            required_setup="Connect an order/sales source through the connector registry.",
        ),
        _OSModuleDefinition(
            module_id="stock_fulfillment",
            label="Stock/fulfillment attention",
            description="Inventory evidence, stockout-risk cases, and readiness-gated fulfillment backlog.",
            case_types=("stockout_risk", "fulfillment_backlog"),
            connector_types=inventory_connector_types,
            required_setup="Connect an inventory/fulfillment source before making stock or backlog claims.",
            readiness_gated=True,
        ),
        _OSModuleDefinition(
            module_id="whatsapp_attention",
            label="WhatsApp/customer attention",
            description="Readiness-gated unanswered-conversation lane; no message bodies or phone numbers.",
            case_types=("unanswered_conversations",),
            connector_types=(),
            required_setup="Qualify and connect a WhatsApp/customer-attention source.",
            readiness_gated=True,
        ),
        _OSModuleDefinition(
            module_id="arca_fiscal_readiness",
            label="ARCA/fiscal readiness",
            description="Operator-only fiscal readiness lane until ARCA/facturación source gates exist.",
            case_types=(),
            connector_types=(),
            required_setup="Complete ARCA/facturación source and credential readiness checks.",
            readiness_gated=True,
        ),
        _OSModuleDefinition(
            module_id="treasury_reporting",
            label="Treasury/reporting",
            description="Payment/collection/reporting readiness lane; no reconciliation claims without source truth.",
            case_types=(),
            connector_types=(),
            required_setup="Connect payment/collection/reporting evidence before treasury claims.",
            readiness_gated=True,
        ),
    )


def _latest_runs_by_connector(runs: list[RunRecord]) -> dict[str, tuple[RunRecord, ConnectorRunOutcome]]:
    latest: dict[str, tuple[RunRecord, ConnectorRunOutcome]] = {}
    for run in sorted(runs, key=lambda candidate: candidate.started_at, reverse=True):
        for outcome in sorted(run.connector_outcomes, key=lambda item: item.started_at, reverse=True):
            if outcome.connector_type not in latest:
                latest[outcome.connector_type] = (run, outcome)
    return latest


def _case_sources(case: OperationalCase) -> set[str]:
    sources = set(source_connectors(case))
    entity_id = case.entity_scope.get("id")
    if isinstance(entity_id, str) and entity_id:
        sources.add(entity_id)
    return sources


def _case_belongs_to_module(case: OperationalCase, definition: _OSModuleDefinition) -> bool:
    if case.case_type in definition.case_types:
        return True
    if case.case_type != "data_stale":
        return False
    module_connectors = set(definition.connector_types)
    if not module_connectors:
        return False
    return bool(_case_sources(case).intersection(module_connectors))


def _sort_cases(cases: list[OperationalCase]) -> list[OperationalCase]:
    return sorted(cases, key=lambda case: (-case.priority_score, case.updated_at, case.case_id))


def _module_status(
    *,
    definition: _OSModuleDefinition,
    actionable_cases: list[OperationalCase],
    latest_connector_runs: dict[str, tuple[RunRecord, ConnectorRunOutcome]],
) -> tuple[ModuleStatus, str]:
    stale_cases = [case for case in actionable_cases if case.case_type == "data_stale"]
    if stale_cases:
        return "data_stale", "actionable_data_stale_case"

    latest_outcomes = [latest_connector_runs[connector] for connector in definition.connector_types if connector in latest_connector_runs]
    failed_outcomes = [outcome for _run, outcome in latest_outcomes if outcome.status != "succeeded"]
    if failed_outcomes:
        return "data_stale", "latest_connector_outcome_not_succeeded"

    non_stale_cases = [case for case in actionable_cases if case.case_type != "data_stale"]
    if non_stale_cases:
        return "attention_required", "actionable_operational_cases"

    succeeded_outcomes = [outcome for _run, outcome in latest_outcomes if outcome.status == "succeeded"]
    if succeeded_outcomes:
        return "ready", "latest_connector_outcome_succeeded"

    return "setup_required", "missing_source_or_readiness_gate"


def _latest_module_run(
    definition: _OSModuleDefinition,
    latest_connector_runs: dict[str, tuple[RunRecord, ConnectorRunOutcome]],
) -> tuple[RunRecord, ConnectorRunOutcome] | None:
    candidates = [latest_connector_runs[connector] for connector in definition.connector_types if connector in latest_connector_runs]
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0].started_at)


def _source_connectors_for_module(
    *,
    definition: _OSModuleDefinition,
    actionable_cases: list[OperationalCase],
    latest_connector_runs: dict[str, tuple[RunRecord, ConnectorRunOutcome]],
) -> list[str]:
    sources: set[str] = set()
    for connector_type in definition.connector_types:
        if connector_type in latest_connector_runs:
            sources.add(connector_type)
    for case in actionable_cases:
        sources.update(source_connectors(case))
    return sorted(sources)


def _module_projection(
    *,
    definition: _OSModuleDefinition,
    actionable_cases: list[OperationalCase],
    latest_connector_runs: dict[str, tuple[RunRecord, ConnectorRunOutcome]],
) -> dict[str, Any]:
    actionable_cases = _sort_cases(actionable_cases)
    status, reason = _module_status(
        definition=definition,
        actionable_cases=actionable_cases,
        latest_connector_runs=latest_connector_runs,
    )
    latest = _latest_module_run(definition, latest_connector_runs)
    latest_run, latest_outcome = latest if latest is not None else (None, None)
    return {
        "module_id": definition.module_id,
        "label": definition.label,
        "description": definition.description,
        "status": status,
        "status_reason": reason,
        "readiness_gated": definition.readiness_gated,
        "setup_required": status == "setup_required",
        "required_setup": definition.required_setup if status == "setup_required" else None,
        "registered_connector_types": list(definition.connector_types),
        "source_connectors": _source_connectors_for_module(
            definition=definition,
            actionable_cases=actionable_cases,
            latest_connector_runs=latest_connector_runs,
        ),
        "case_types": list(definition.case_types),
        "actionable_case_count": len(actionable_cases),
        "top_case_ids": [case.case_id for case in actionable_cases[:3]],
        "latest_run_id": latest_run.run_id if latest_run is not None else None,
        "latest_run_status": latest_run.status if latest_run is not None else None,
        "latest_connector_status": latest_outcome.status if latest_outcome is not None else None,
    }


def _summary(modules: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"ready": 0, "attention_required": 0, "data_stale": 0, "setup_required": 0}
    for module in modules:
        status = module["status"]
        summary[status] = summary.get(status, 0) + 1
    return summary


def get_lapyme_os_snapshot(
    store: OperationalCaseStore,
    ledger: RunLedger,
    *,
    business_id: str,
    now: datetime,
    registry: ConnectorRegistry | None = None,
) -> dict[str, Any]:
    """Return the read-only La PyME-category OS module snapshot.

    This projection is deliberately derived from platform state: connector
    registry metadata, run-ledger connector outcomes, and actionable Operational
    Cases. It never fabricates metrics for unconnected modules; missing sources
    remain explicit ``setup_required`` lanes.
    """

    active_registry = registry or default_connector_registry()
    runs = ledger.list_runs(business_id=business_id, limit=None)
    latest_connector_runs = _latest_runs_by_connector(runs)
    cases = store.list_cases(business_id=business_id, limit=None)
    actionable = [case for case in cases if case.status in ACTIONABLE_OPERATIONAL_CASE_STATUSES]
    modules = [
        _module_projection(
            definition=definition,
            actionable_cases=[case for case in actionable if _case_belongs_to_module(case, definition)],
            latest_connector_runs=latest_connector_runs,
        )
        for definition in _module_definitions(active_registry)
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "snapshot_key": "lapyme_category_os_snapshot",
            "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_of_truth": [
                "connector_registry",
                "run_ledger",
                "operational_cases",
            ],
            "modules": modules,
            "summary": _summary(modules),
        }
    )


__all__ = ["get_lapyme_os_snapshot"]
