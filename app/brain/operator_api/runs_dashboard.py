from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403
from .histograms_handling import *  # noqa: F401,F403


def list_run_history(ledger: RunLedger, *, business_id: str, status: str | None, limit: str | None) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(business_id=business_id, status=parsed_status, limit=parsed_limit)
    return {"runs": [run_history_item(run) for run in runs], "limit": parsed_limit}

def get_scoped_run(ledger: RunLedger, *, business_id: str, run_id: str) -> RunRecord:
    run = ledger.get_run(run_id)
    if run is None or run.business_id != business_id:
        raise OperatorAPIError("run_not_found", "run not found", status_code=404)
    return run

def get_run_projection(ledger: RunLedger, *, business_id: str, run_id: str) -> dict[str, Any]:
    return {"run": run_detail(get_scoped_run(ledger, business_id=business_id, run_id=run_id))}

def _case_type_label(case_type: Any) -> str:
    return str(case_type or "caso")


def _severity_label(severity: Any) -> str:
    labels = {
        "critical": "crítico",
        "warning": "advertencia",
        "info": "informativo",
    }
    return labels.get(str(severity or "").lower(), str(severity or "sin severidad"))


def _owner_ready_message(
    *,
    actionable_total: int,
    degraded_total: int,
    next_actions: list[dict[str, Any]],
    evidence_actions: list[dict[str, Any]],
) -> str:
    lines = ["Orvo — resumen operativo"]
    if actionable_total == 0:
        lines.append("No hay casos accionables para revisar ahora.")
        return "\n".join(lines)

    lines.append(f"Tenés {actionable_total} casos accionables; {degraded_total} necesitan revalidar datos.")
    if next_actions:
        top = next_actions[0]
        lines.append(
            "Prioridad: "
            f"{_case_type_label(top.get('case_type'))} {_severity_label(top.get('severity'))}, "
            f"prioridad {top.get('priority_score')}."
        )
        lines.append("Acción sugerida: acknowledge_case para tomar el caso y definir próximo paso.")
    if evidence_actions:
        evidence = evidence_actions[0]
        connectors = ", ".join(str(connector) for connector in evidence.get("source_connectors", []) if connector)
        connector_text = connectors or "la fuente"
        lines.append(
            "Datos: "
            f"revalidar {connector_text} por evidencia {evidence.get('freshness_state')} antes de decidir."
        )
    return "\n".join(lines)


def _mvp_operator_brief(
    *,
    business_id: str,
    case_queue_summary: dict[str, Any],
    top_actionable_cases: dict[str, Any],
    top_degraded_cases: dict[str, Any],
) -> dict[str, Any]:
    """Compact owner/operator brief for the MVP dashboard.

    This is intentionally derived from existing projections so it stays a thin,
    redacted product surface: one headline plus the first few actions an operator
    can take today.
    """

    actionable_total = int(case_queue_summary.get("actionable_total", 0) or 0)
    degraded_total = int(case_queue_summary.get("actionable_degraded", 0) or 0)
    status = "clear" if actionable_total == 0 else "needs_attention"
    headline = (
        "No actionable cases"
        if actionable_total == 0
        else f"{actionable_total} actionable cases; {degraded_total} with degraded evidence"
    )
    next_actions = [
        {
            "case_id": case.get("case_id"),
            "case_type": case.get("case_type"),
            "severity": case.get("severity"),
            "priority_score": case.get("priority_score"),
            "reason": "highest_priority_actionable_case",
            "suggested_action_key": "acknowledge_case",
        }
        for case in top_actionable_cases.get("cases", [])[:3]
    ]
    evidence_actions = [
        {
            "case_id": case.get("case_id"),
            "case_type": case.get("case_type"),
            "freshness_state": case.get("freshness_state"),
            "source_connectors": case.get("source_connectors", []),
            "reason": "refresh_degraded_evidence",
            "suggested_action_key": "request_follow_up",
        }
        for case in top_degraded_cases.get("cases", [])[:3]
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "status": status,
            "headline": headline,
            "message_channel": "whatsapp",
            "message_locale": "es-AR",
            "owner_message": _owner_ready_message(
                actionable_total=actionable_total,
                degraded_total=degraded_total,
                next_actions=next_actions,
                evidence_actions=evidence_actions,
            ),
            "next_actions": next_actions,
            "evidence_actions": evidence_actions,
        }
    )


def get_mvp_operator_brief(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime,
    limit: int = 3,
) -> dict[str, Any]:
    """Return the compact owner/operator action queue for the MVP surface."""

    case_queue_summary = summarize_case_queue(store, business_id=business_id)
    top_actionable_cases = list_top_actionable_cases_by_priority(
        store, business_id=business_id, now=now, limit=str(limit)
    )
    top_degraded_cases = list_top_actionable_degraded_cases(
        store, business_id=business_id, now=now, limit=str(limit)
    )
    return _mvp_operator_brief(
        business_id=business_id,
        case_queue_summary=case_queue_summary,
        top_actionable_cases=top_actionable_cases,
        top_degraded_cases=top_degraded_cases,
    )


def get_operator_dashboard(
    store: OperationalCaseStore,
    ledger: RunLedger,
    *,
    business_id: str,
    now: datetime,
    limit: int = 10,
) -> dict[str, Any]:
    """Aggregate all key operator views for a business in one call."""

    case_queue_summary = summarize_case_queue(store, business_id=business_id)
    top_actionable_cases = list_top_actionable_cases_by_priority(
        store, business_id=business_id, now=now, limit=str(limit)
    )
    top_degraded_cases = list_top_actionable_degraded_cases(
        store, business_id=business_id, now=now, limit=str(limit)
    )
    run_history = list_run_history(ledger, business_id=business_id, status=None, limit=str(limit))
    return {
        "business_id": business_id,
        "now": _iso(now),
        "mvp_operator_brief": _mvp_operator_brief(
            business_id=business_id,
            case_queue_summary=case_queue_summary,
            top_actionable_cases=top_actionable_cases,
            top_degraded_cases=top_degraded_cases,
        ),
        "case_queue_summary": case_queue_summary,
        "top_actionable_cases": top_actionable_cases,
        "top_degraded_cases": top_degraded_cases,
        "workflow_throughput": summarize_case_workflow_throughput(store, business_id=business_id),
        "resolution_latency_histogram": summarize_case_resolution_latency_histogram(
            store, business_id=business_id
        ),
        "acknowledgment_latency_histogram": summarize_case_acknowledgment_latency_histogram(
            store, business_id=business_id
        ),
        "run_history": run_history,
    }

__all__ = [name for name in globals() if not name.startswith("__")]
