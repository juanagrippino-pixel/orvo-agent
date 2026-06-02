# ADR 0006 — Conversation/Brain bounded-context boundary

Status: Accepted  
Date: 2026-06-02

## Context

Orvo currently contains two products that share deployment wiring but should not share domain logic:

1. **Commercial WhatsApp conversation agent** — lead-facing chat flow, prompts, LLM wiring, outbound sales notification, and conversation memory.
2. **Orvo Brain control plane** — operational D2C ecommerce runtime, connector registry, metric/case contracts, run ledger, operator API, and report dispatch.

The structural hardening plan requires this boundary to be explicit before decomposing `server.py` and `app/brain/operator_api.py`.

## Decision

- The WhatsApp commercial conversation domain lives under `app/conversation/`:
  - `app/conversation/graph.py`
  - `app/conversation/prompts.py`
  - `app/conversation/models.py`
  - `app/conversation/db.py`
- The operational control plane remains under `app/brain/`.
- `server.py` may wire HTTP routes for both domains, but should delegate to domain entrypoints and avoid owning business logic.
- `app/brain/*` must not import `app.conversation.*`.
- Legacy imports (`app.graph`, `app.prompts`, `app.models`, top-level `db`) remain thin compatibility shims while tests and external scripts migrate.

## DB boundary

The databases remain intentionally separate:

- Conversation domain: `DB_PATH` / `conversations.db`, lead messages and commercial notification state.
- Brain domain: `ORVO_BRAIN_DB_PATH` / `orvo_brain.sqlite3`, connector runtime state, reports, runs, operational cases, delivery status, and operator projections.

They must not be merged as part of this refactor. Cross-domain product features should communicate through explicit service calls or public projections, not by sharing tables.

## Consequences

- The conversation agent can evolve without creating dependencies inside the control-plane core.
- The Brain control plane remains a deterministic source of truth for operational cases and metrics.
- Future cleanup can remove compatibility shims only after imports are fully migrated and tests prove no external reliance remains.
