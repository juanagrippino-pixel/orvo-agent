# Operational Case Engine Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `docs/adr/0002-operational-case-native-issue-object.md`, `docs/specs/d2c-case-family-catalog.md`

## Purpose

`OperationalCase` is the durable work object for Orvo. Reports, WhatsApp messages, queues, dashboards, timelines, and automations are projections/actions around cases. They are not parallel task systems.

## Core entities

```python
class OperationalCase(BaseModel):
    case_id: str
    business_id: str
    tenant_id: str | None = None
    case_type: str
    status: Literal["open", "acknowledged", "in_progress", "resolved", "dismissed"]
    severity: Literal["info", "low", "medium", "high", "critical"]
    priority_score: int
    entity_scope: EntityScope
    dedupe_key: str
    title: str
    opened_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    latest_run_id: str | None = None
    degraded: bool = False
```

```python
class CaseTimelineEvent(BaseModel):
    event_id: str
    case_id: str
    event_type: str
    actor_type: Literal["system", "operator", "owner", "worker"]
    actor_ref: str
    run_id: str | None = None
    artifact_ref: str | None = None
    created_at: datetime
    summary: str
    metadata: dict[str, Any] = {}
```

## Lifecycle rules

Allowed transitions:

```text
open -> acknowledged
open -> in_progress
open -> dismissed
acknowledged -> in_progress
acknowledged -> resolved
acknowledged -> dismissed
in_progress -> resolved
in_progress -> dismissed
resolved -> open       # reopen with recurring deterministic evidence
dismissed -> open      # reopen only with recurring deterministic evidence
```

Rules:

- Every transition appends a timeline event.
- Deterministic detections may open/update/reopen; they may not silently dismiss human decisions.
- LLMs may not create cases, set priority, or transition lifecycle.
- Manual dismiss/resolve requires reason.
- Case updates should preserve history and attach new evidence snapshots.

## Dedupe contract

Dedupe key shape:

```text
<business_id>/<case_type>/<entity_kind>/<entity_id>/<primary_metric_family>/<time_grain>
```

Requirements:

- Same underlying issue updates one case across repeated runs.
- Entity-specific cases do not collapse into one broad business case.
- A resolved case may reopen when deterministic policy says the issue returned.
- The dedupe algorithm is covered by tests per case family.

## Priority contract

Priority score is deterministic. Inputs may include:

- severity base from case family;
- recency;
- business impact metric;
- entity importance flag;
- duration open;
- stale/degraded caveats.

Forbidden:

- LLM priority judgment;
- copying severity from text output;
- changing priority without timeline/audit event.

## Projection contract

Case projections may include:

- WhatsApp brief rows;
- internal case queue;
- timeline view;
- run detail links;
- action suggestions from `docs/specs/d2c-action-key-catalog.md`.

Projection renderers may omit low-priority cases for brevity, but they must not alter underlying case state.

## Required tests

- open/update/dedupe/reopen path for `sales_drop`, `stockout_risk`, `data_stale`;
- lifecycle transition table rejects invalid transitions;
- manual resolve/dismiss requires reason;
- priority is deterministic for same inputs;
- evidence snapshot exists before owner-facing projection;
- report renderer can cite case/evidence refs.
