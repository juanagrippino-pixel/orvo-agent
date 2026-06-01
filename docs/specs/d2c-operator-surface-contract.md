# D2C Operator Surface Contract

Status: Draft contract
Date: 2026-05-24
Related: `docs/product/d2c-control-plane-prd.md`, `docs/specs/d2c-case-family-catalog.md`, `docs/specs/d2c-action-key-catalog.md`

## Purpose

This document defines what the first WhatsApp and internal operator surfaces must show once Orvo is treated as a D2C ecommerce control plane. Surfaces are projections of runtime/case state; they are not sources of truth.

## Source-of-truth hierarchy

```text
External systems -> connector execution -> metrics/evidence -> detections -> Operational Cases -> projections/surfaces
```

Surfaces may render and route. They must not calculate metrics, create unsupported cases, or mutate lifecycle without going through case/action contracts.

Suggested actions must use registered action keys from `docs/specs/d2c-action-key-catalog.md`. LLM/copy layers may rephrase registered actions, but must not invent new actions or imply execution without case/action governance.

## Surface 1: WhatsApp owner/operator brief

### Required content

A delivered brief should include:

1. business/date context;
2. run health/degraded caveat when relevant;
3. top new/open/resolved cases;
4. evidence/source lines;
5. one or more suggested next actions from allowed action keys;
6. concise language in direct Spanish.

### Example shape

```text
Orvo — resumen operativo de hoy

Prioridad: Riesgo de stock en Campera X.
Evidencia: 3 unidades disponibles; vendió 8 en los últimos 7 días. Fuente: Tiendanube.
Acción sugerida: confirmar stock o pausar promoción hasta reponer.

Abierto: ventas debajo del mínimo esperado.
Evidencia: 4 órdenes vs mínimo configurado de 8. Fuente: Tiendanube.

Datos: Meta Ads no se usó para recomendaciones hoy porque la fuente está stale desde 06:10.
```

### Forbidden content

- numbers not present in allowed claims/evidence;
- root-cause certainty without evidence;
- irreversible automation claims;
- generic motivational filler;
- presenting stale/missing data as normal;
- hiding an open critical case because the text would be inconvenient.

## Surface 2: Internal operator case queue

Minimum fields:

```json
{
  "case_id": "case_...",
  "business_id": "artemea",
  "case_type": "stockout_risk",
  "title": "Stock risk: Campera X",
  "status": "open",
  "severity": "high",
  "priority_score": 87,
  "entity_scope": {"kind": "sku", "id": "SKU-123", "label": "Campera X"},
  "opened_at": "2026-05-24T08:00:00-03:00",
  "updated_at": "2026-05-24T08:00:00-03:00",
  "acknowledged_at": null,
  "assigned_at": null,
  "assignee_ref": null,
  "evidence_count": 2,
  "latest_run_id": "run_...",
  "degraded": false
}
```

Queue filters:

- open;
- acknowledged;
- in progress;
- resolved recently;
- reopened;
- high priority;
- connector degraded;
- case type;
- source connector;
- entity scope.

### Service-management projection

The internal endpoint `GET /internal/brain/businesses/{business_id}/service-management/cases` returns a read-only service-management projection over canonical `OperationalCase` rows. It must remain a projection only: `OperationalCase.status`, timeline events, run ledger records, and evidence snapshots remain the source of truth.

Minimum additional fields per case:

```json
{
  "service_record_type": {"code": "incident", "label": "Incident", "label_es": "Incidente"},
  "owner_status": {
    "code": "waiting_external",
    "label_es": "Esperando a un tercero",
    "status_category": "waiting",
    "source_status": "acknowledged"
  },
  "dismissed_at": null,
  "needs_escalation": true,
  "escalation_reasons": [
    {
      "code": "waiting_external",
      "label_es": "Bloqueado por un tercero",
      "source": "owner_status"
    }
  ],
  "sla": {
    "first_response": {
      "policy_key": "first_response_warning_240m",
      "target_seconds": 14400,
      "elapsed_seconds": 3600,
      "remaining_seconds": 10800,
      "breached": false,
      "completed": true,
      "started_at": "2026-05-24T08:00:00Z",
      "stopped_at": "2026-05-24T09:00:00Z",
      "due_at": "2026-05-24T12:00:00Z"
    }
  }
}
```

Projection rules:

- map case families to Atlassian-like record labels (`incident`, `service_request`, `problem`, `change`) deterministically;
- derive `waiting_owner` and `waiting_external` from case metadata only for active `acknowledged`/`in_progress` cases;
- include first-response and resolution SLA clocks as deterministic UTC timers; terminal `resolved` and `dismissed` cases must stop open SLA clocks at their terminal timestamp;
- expose deterministic `escalation_reasons` for unacknowledged critical cases, active SLA breaches, and active waiting-on-owner/external blockers without changing priority or lifecycle state;
- redact secret-shaped values at the projection boundary;
- preserve explicit tenant scope and stable internal response envelopes.

## Surface 3: Case timeline

Minimum events:

- case opened;
- evidence attached;
- priority updated;
- status transition;
- owner/operator assignment;
- operator comment;
- action requested/approved/completed/failed;
- run/degraded-state reference;
- resolved/reopened/dismissed.

Timeline event shape:

```json
{
  "event_id": "evt_...",
  "case_id": "case_...",
  "event_type": "evidence_attached",
  "actor_type": "system",
  "actor_ref": "orvo_runtime",
  "run_id": "run_...",
  "created_at": "2026-05-24T08:00:02-03:00",
  "summary": "Attached Tiendanube stock metric snapshot",
  "artifact_ref": "artifact_..."
}
```

## Surface 4: Run history / inspection

Minimum run fields:

```json
{
  "run_id": "run_...",
  "business_id": "artemea",
  "mode": "scheduled",
  "status": "completed_degraded",
  "started_at": "2026-05-24T08:00:00-03:00",
  "finished_at": "2026-05-24T08:00:05-03:00",
  "compiled_runtime_hash": "sha256:...",
  "connectors": [
    {"type": "tiendanube", "status": "ok", "artifact_ref": "artifact_..."},
    {"type": "meta_ads", "status": "stale", "reason": "last_success_too_old"}
  ],
  "cases_opened": 1,
  "cases_updated": 2,
  "dispatch_status": "sent"
}
```

Inspection must answer:

- What ran?
- Which runtime/config version ran?
- Which connectors succeeded/failed/degraded?
- Which cases changed?
- What was sent or skipped?
- What evidence backed owner-facing claims?
- Were any secrets redacted?

## Surface 5: Manual follow-up actions

Initial actions should be case-scoped:

- `acknowledge_case` — acknowledge case;
- `assign_owner` — assign owner/operator;
- `add_comment` — add comment;
- `request_follow_up` — request follow-up;
- `mark_in_progress` — mark in progress;
- `resolve_case` — resolve with reason;
- `dismiss_case` — dismiss with reason;
- `request_external_action` — request external action, behind explicit approval.

Every action must append audit/timeline state. Do not mutate state invisibly.

## Auth/tenant/audit minimums before live use

Before an internal operator surface is live beyond local/dev usage:

- tenant/business scope must be explicit;
- operator identity must be attached to mutations;
- request logs must avoid secrets;
- case/action mutations must emit audit/timeline events;
- rate-limit/retry semantics must be documented for edges;
- unsafe actions must require approval or remain disabled.
