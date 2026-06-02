# GUARDRAILS — Orvo Brain control plane refactor Phase 0

Status: **Phase 0 only; no refactor started**  
Repo: `/root/orvo-agent`  
Branch: `feat/orvo-brain-control-plane`  
Baseline commit inspected: `0c2cbd0`  
Baseline local runtime: `Python 3.11.15`  
Baseline verification before this file: repo clean, branch tracking `origin/feat/orvo-brain-control-plane`.

This file is the stop-point requested before any Phase 1+ refactor. Treat it as the safety net for separating `conversation/` from `brain/`, decomposing `server.py`/`operator_api.py`, and moving worker/observability structure without changing public contracts.

## Non-negotiable guardrails

1. **`docs/specs/` are the contract source of truth.** If a refactor requires changing a spec contract, stop and ask Juan.
2. **The `/internal/brain/*` HTTP surface must remain behaviorally identical** unless explicitly approved.
3. **No Phase 1 module move may start before this file is reviewed.**
4. **Do not touch Packet Q, Packet U, or Packet O scope in this refactor.** Mark adjacent issues as follow-ups only:
   - Packet Q: connector secret-ref runtime hardening.
   - Packet U: workflow/action ledger and approval object foundation.
   - Packet O: durable audit / least-privilege security closure.
5. **Run `pytest -q` after each phase and after risky module moves.** The current green baseline is expected to be `1154+` tests.
6. **No module introduced by the refactor should exceed ~400 lines** without a written justification in the PR/commit notes.
7. **Keep DB boundaries separate:** `conversations.db` / `DB_PATH` for commercial conversation memory; `orvo_brain.sqlite3` / `ORVO_BRAIN_DB_PATH` for Orvo Brain operational state.
8. **No public response shape changes:** top-level envelopes, redaction flags, route paths, auth behavior, and data keys listed below are contract snapshots.

## Python target decision

Current mismatch:

- Local/test runtime verified here: `Python 3.11.15`.
- Docker runtime in `Dockerfile`: `python:3.13-slim`.

**Phase 0 decision:** use **Python 3.11 as the refactor target baseline** because the full suite is currently green and repeatedly validated there. Before any production/deploy confidence claim under Docker, either:

1. align Docker to `python:3.11-slim`, or
2. add/execute a full 3.13 suite gate and document its result.

Until one of those happens, any Phase 1+ result should report: “tests green under Python 3.11 local; Docker 3.13 parity not proven in this phase.”

## Contract-to-test matrix

The tests do not generally cite spec filenames inline; this matrix maps spec contracts to the tests that currently pin their behavior by module, route, and naming convention.

| Spec source of truth | Contract area | Primary tests guarding it | Notes for refactor |
|---|---|---|---|
| `docs/specs/compiled-runtime-contract.md` | Compiled runtime, execution plan, runtime hash, config compatibility. | `tests/contracts/test_compiled_runtime_contract.py`, `tests/test_brain_runtime.py`, `tests/test_brain_runtime_env.py`, `tests/test_brain_bootstrap.py`, `tests/test_run_orvo_brain_reports_script.py`, `tests/test_runtime_docs_examples.py` | Do not change runtime shape/hash semantics during module moves. Keep legacy bootstrap compatibility. |
| `docs/specs/connector-registry-contract.md` | `ConnectorSpec`, connector registry capabilities, connector factory/static import behavior, enabled connectors. | `tests/contracts/test_connector_registry_contract.py`, `tests/test_brain_connector_registry.py`, `tests/test_brain_pipeline.py`, adapter tests for CSV/Sheets/Tiendanube/MercadoLibre/Meta Ads, `tests/contracts/test_adapter_metric_emission_contract.py` | Runtime worker pattern stays `ConnectorSpec + adapter + report_factory + BusinessConfig.connectors`; no forced base-class rewrite. |
| `docs/specs/metric-registry-contract.md` | Metric family vocabulary, validation modes, metric refs and diagnostics. | `tests/contracts/test_metric_registry_contract.py`, `tests/contracts/test_metric_validation_contract.py`, `tests/contracts/test_adapter_metric_emission_contract.py`, `tests/test_brain_operational_cases.py`, `tests/test_brain_pipeline.py` | Phase 3 may centralize merge policy here, but must not silently change emitted owner-facing cases. |
| `docs/specs/d2c-case-family-catalog.md` | Allowed D2C case families and owner-facing/deferred families. | `tests/test_brain_operational_cases.py`, `tests/contracts/test_metric_registry_contract.py`, `tests/test_brain_reporting.py`, `tests/test_brain_dispatch.py` | Keep deferred/internal families hidden unless their acceptance gate is explicitly completed. |
| `docs/specs/operational-case-engine-contract.md` | `OperationalCase` lifecycle, dedupe, evidence, timeline, status transitions, projections. | `tests/test_brain_operational_cases.py`, `tests/test_operator_case_actions.py`, `tests/test_operator_case_timeline.py`, `tests/test_internal_operator_api.py`, operator case projection/view tests | `OperationalCase` remains source of truth; owner briefs and WhatsApp are projections. |
| `docs/specs/internal-operator-api-contract.md` | `/internal/brain/*` routes, envelopes, auth, scoping, redaction, action keys. | `tests/test_internal_operator_api.py`, `tests/test_operator_case_views.py`, `tests/test_operator_dashboard.py`, `tests/test_operator_case_*`, `tests/test_server_internal_brain_*.py`, `tests/test_server_whatsapp_delivery_status.py` | This is the main guardrail for decomposing `operator_api.py` and thinning `server.py`. Snapshot table below must remain stable. |
| `docs/specs/d2c-operator-surface-contract.md` | Operator dashboard/views/summaries and read-only surfaces. | `tests/test_operator_dashboard.py`, `tests/test_operator_case_views.py`, queue summary/aging/stagnation/throughput/histogram tests | Split by projection family only after preserving exact output data keys. |
| `docs/specs/d2c-action-key-catalog.md` | Case action catalog, executable action keys, disabled reasons, role-aware mutation. | `tests/test_operator_case_actions.py`, `tests/test_internal_operator_api.py`, `tests/test_workflow_automation_simulation.py` | Do not add new action behavior in structural refactor. |
| `docs/specs/run-ledger-foundation.md` | Run ledger records, artifacts, dispatch outcomes, redacted run projections. | `tests/test_brain_run_ledger.py`, `tests/test_brain_runner.py`, `tests/test_internal_operator_api.py`, `tests/test_run_orvo_brain_reports_script.py` | Correlation ID work in Phase 4 should attach to existing ledger semantics without changing run projection shape. |
| `docs/specs/storage-migration-contract.md` | SQLite schema initialization/migrations/backward compatibility. | `tests/test_brain_storage.py`, `tests/test_brain_run_ledger.py`, `tests/test_brain_whatsapp_delivery_status.py`, `tests/test_db.py`, API tests using temp SQLite stores | No DB merge between conversation and brain domains. |
| `docs/specs/tenant-secret-redaction-contract.md` | Secret redaction in stored data, API responses, errors, titles, evidence and delivery metadata. | `tests/invariants/test_secret_redaction.py`, `tests/test_internal_operator_api.py`, `tests/test_operator_case_views.py`, `tests/test_server_whatsapp_delivery_status.py`, `tests/test_brain_delivery.py` | Any moved boundary must redact before HTTP response and before durable stores where current tests require it. |
| `docs/specs/testing-invariant-matrix.md` | Cross-contract invariant coverage and regression matrix. | `tests/test_test_collection_regression_guard.py`, all `tests/contracts/*`, `tests/invariants/*` | Update only if moving tests changes collection; never weaken to make refactor pass. |
| `docs/specs/integration-train-contract.md` | Packet sequencing, dependency gates, integration train expectations. | `docs/organization/d2c-worker-task-packets.md` acceptance references, `tests/test_runtime_docs_examples.py` | Structural refactor should not claim Packet Q/O/U completion. |
| `docs/specs/worker-handoff-manifest.md` | Autonomous worker reporting format. | Docs/process guardrail; no direct runtime tests found. | Use in commits/handoffs; include worktree, branch, SHA, tests, risks. |

## Public `/internal/brain/*` envelope snapshot

Snapshot method: imported `server.app`, created a temporary SQLite brain DB, seeded one redacted Operational Case and one run ledger record with canary secret-like strings, called every `/internal/brain/*` route with internal auth headers, and summarized the JSON shapes.

Canary redaction check: the snapshot used synthetic secret-shaped values and the output did **not** contain any of those raw canary values. Raw canary strings are intentionally omitted from this document.

### Success envelope

Every successful internal response uses this top-level shape:

```json
{
  "ok": true,
  "business_id": "<business_id or whatsapp>",
  "request_id": "<X-Request-ID or generated req_...>",
  "data": {},
  "warnings": [],
  "redaction_applied": true
}
```

### Error envelope

Internal errors use this top-level shape:

```json
{
  "ok": false,
  "business_id": "<business_id or whatsapp>",
  "request_id": "<X-Request-ID or generated req_...>",
  "error": {
    "code": "<stable code>",
    "message": "<redacted safe message>",
    "safe_to_show_owner": false
  },
  "redaction_applied": true
}
```

Auth/permission guardrails observed in `server.py`:

- Missing `ORVO_INTERNAL_OPERATOR_TOKEN` => `503 internal_auth_not_configured`.
- Wrong/missing `Authorization: Bearer ...` => `401 unauthorized`.
- Unknown/insufficient role via `X-Orvo-Role`/`X-Orvo-Operator` => forbidden envelope through `InternalOperatorAuthorizationError`.
- Read routes require `INTERNAL_READ_PERMISSION`.
- Case action mutation route additionally requires `CASE_ACTION_PERMISSION`.

## `/internal/brain/*` route surface snapshot

All listed routes returned `200` in the seeded snapshot unless otherwise noted. The `data` column lists current top-level keys under `data`; refactor must preserve these keys and redaction behavior.

| Method | Route | Flask endpoint | Current `data` keys |
|---|---|---|---|
| GET | `/internal/brain/businesses/<business_id>/operator-session` | `internal_brain_operator_session` | `operator` |
| GET | `/internal/brain/businesses/<business_id>/cases` | `internal_brain_cases` | `cases`, `limit` |
| GET | `/internal/brain/businesses/<business_id>/case-actions` | `internal_brain_case_actions` | `actions`, `api_enabled_action_keys`, `business_id`, `operator_executable_action_keys` |
| GET | `/internal/brain/businesses/<business_id>/cases/summary` | `internal_brain_cases_summary` | `actionable_by_severity`, `actionable_degraded`, `actionable_total`, `business_id`, `by_case_type`, `by_severity`, `by_status`, `total` |
| GET | `/internal/brain/businesses/<business_id>/cases/summary/by-priority-bracket` | `internal_brain_cases_summary_by_priority_bracket` | `actionable_by_priority_bracket`, `actionable_degraded_by_priority_bracket`, `actionable_total`, `business_id`, `total`, `totals_by_priority_bracket` |
| GET | `/internal/brain/businesses/<business_id>/cases/summary/by-case-type` | `internal_brain_cases_summary_by_case_type` | `actionable_by_case_type`, `actionable_degraded_by_case_type`, `actionable_total`, `business_id`, `total`, `totals_by_case_type` |
| GET | `/internal/brain/businesses/<business_id>/cases/summary/by-entity-kind` | `internal_brain_cases_summary_by_entity_kind` | `actionable_by_entity_kind`, `actionable_degraded_by_entity_kind`, `actionable_total`, `business_id`, `total`, `totals_by_entity_kind` |
| GET | `/internal/brain/businesses/<business_id>/cases/summary/by-source-connector` | `internal_brain_cases_summary_by_source_connector` | `actionable_by_source_connector`, `actionable_degraded_by_source_connector`, `actionable_total`, `business_id`, `total`, `totals_by_source_connector` |
| GET | `/internal/brain/businesses/<business_id>/cases/aging` | `internal_brain_cases_aging` | `actionable_total`, `business_id`, `by_age_bucket`, `by_age_bucket_severity`, `now`, `oldest_actionable` |
| GET | `/internal/brain/businesses/<business_id>/cases/aging/by-priority-bracket` | `internal_brain_cases_aging_by_priority_bracket` | `actionable_total`, `business_id`, `by_age_bucket`, `by_age_bucket_priority_bracket`, `now`, `oldest_actionable` |
| GET | `/internal/brain/businesses/<business_id>/cases/aging/by-case-type` | `internal_brain_cases_aging_by_case_type` | `actionable_total`, `business_id`, `by_age_bucket`, `by_age_bucket_case_type`, `now`, `oldest_actionable` |
| GET | `/internal/brain/businesses/<business_id>/cases/aging/by-severity` | `internal_brain_cases_aging_by_severity` | `actionable_total`, `business_id`, `by_age_bucket`, `by_age_bucket_severity`, `now`, `oldest_actionable` |
| GET | `/internal/brain/businesses/<business_id>/cases/stagnation` | `internal_brain_cases_stagnation` | `actionable_total`, `business_id`, `by_idle_bucket`, `by_idle_bucket_severity`, `most_stalled_actionable`, `now` |
| GET | `/internal/brain/businesses/<business_id>/cases/stagnation/by-priority-bracket` | `internal_brain_cases_stagnation_by_priority_bracket` | `actionable_total`, `business_id`, `by_idle_bucket`, `by_idle_bucket_priority_bracket`, `most_stalled_actionable`, `now` |
| GET | `/internal/brain/businesses/<business_id>/workflow/throughput` | `internal_brain_workflow_throughput` | `acknowledged_count`, `business_id`, `resolved_count`, `time_to_acknowledge_seconds`, `time_to_resolve_seconds`, `total` |
| GET | `/internal/brain/businesses/<business_id>/workflow/throughput/by-priority-bracket` | `internal_brain_workflow_throughput_by_priority_bracket` | `acknowledged_by_priority_bracket`, `business_id`, `resolved_by_priority_bracket`, `time_to_acknowledge_seconds_by_priority_bracket`, `time_to_resolve_seconds_by_priority_bracket`, `total`, `totals_by_priority_bracket` |
| GET | `/internal/brain/businesses/<business_id>/workflow/throughput/by-case-type` | `internal_brain_workflow_throughput_by_case_type` | `acknowledged_by_case_type`, `business_id`, `resolved_by_case_type`, `time_to_acknowledge_seconds_by_case_type`, `time_to_resolve_seconds_by_case_type`, `total`, `totals_by_case_type` |
| GET | `/internal/brain/businesses/<business_id>/cases/top-by-age` | `internal_brain_cases_top_by_age` | `actionable_total`, `business_id`, `cases`, `count`, `limit`, `now` |
| GET | `/internal/brain/businesses/<business_id>/cases/top-by-priority` | `internal_brain_cases_top_by_priority` | `actionable_total`, `business_id`, `cases`, `count`, `limit`, `now` |
| GET | `/internal/brain/businesses/<business_id>/cases/top-degraded` | `internal_brain_cases_top_degraded` | `actionable_degraded_total`, `business_id`, `cases`, `count`, `limit`, `now` |
| GET | `/internal/brain/businesses/<business_id>/cases/top-stalled` | `internal_brain_cases_top_stalled` | `actionable_total`, `business_id`, `cases`, `count`, `limit`, `now` |
| GET | `/internal/brain/businesses/<business_id>/cases/recently-opened` | `internal_brain_cases_recently_opened` | `business_id`, `cases`, `count`, `limit`, `open_total` |
| GET | `/internal/brain/businesses/<business_id>/cases/recently-acknowledged` | `internal_brain_cases_recently_acknowledged` | `acknowledged_total`, `business_id`, `cases`, `count`, `limit` |
| GET | `/internal/brain/businesses/<business_id>/cases/recently-resolved` | `internal_brain_cases_recently_resolved` | `business_id`, `cases`, `count`, `limit`, `resolved_total` |
| GET | `/internal/brain/businesses/<business_id>/dashboard` | `internal_brain_dashboard` | `acknowledgment_latency_histogram`, `business_id`, `case_queue_summary`, `now`, `resolution_latency_histogram`, `run_history`, `top_actionable_cases`, `top_degraded_cases`, `workflow_throughput` |
| GET | `/internal/brain/businesses/<business_id>/case-views` | `internal_brain_case_views` | `views` |
| GET | `/internal/brain/businesses/<business_id>/case-views/<view_id>/cases` | `internal_brain_case_view_cases` | `cases`, `count`, `jql`, `limit`, `normalized_jql`, `total`, `truncated`, `view` |
| GET | `/internal/brain/businesses/<business_id>/cases/<case_id>` | `internal_brain_case_detail` | `case` |
| GET | `/internal/brain/businesses/<business_id>/cases/<case_id>/timeline` | `internal_brain_case_timeline` | `case_id`, `case_status`, `count`, `events`, `filters`, `limit`, `total` |
| POST | `/internal/brain/businesses/<business_id>/cases/<case_id>/actions` | `internal_brain_case_action` | `case` |
| GET | `/internal/brain/businesses/<business_id>/runs` | `internal_brain_runs` | `limit`, `runs` |
| GET | `/internal/brain/businesses/<business_id>/runs/<run_id>` | `internal_brain_run_detail` | `run` |
| GET | `/internal/brain/whatsapp/delivery-statuses` | `internal_brain_whatsapp_delivery_statuses` | `events` |

## Route-order guardrail

`server.py` currently registers collection/static case routes before the dynamic `cases/<case_id>` catch-all. Preserve this order during extraction:

1. `/cases`
2. `/case-actions`
3. `/cases/summary...`
4. `/cases/aging...`
5. `/cases/stagnation...`
6. `/workflow/throughput...`
7. `/cases/top...`
8. `/cases/recently...`
9. `/dashboard`
10. `/case-views...`
11. `/cases/<case_id>`
12. `/cases/<case_id>/timeline`
13. `/cases/<case_id>/actions`
14. `/runs...`
15. `/whatsapp/delivery-statuses`

## Domain boundary snapshot before Phase 1

Current mixed imports in `server.py` prove the two domains are still coupled at the HTTP wiring layer:

- Conversation/commercial WhatsApp domain:
  - `app.graph.orvo_app`, `OrvoState`
  - `db.init_db`, `load_messages`, `save_messages`, `load_lead`, `save_lead`, `is_juan_notified`, `mark_juan_notified`
  - `app.models` indirectly through `app.graph`
  - `app.prompts` indirectly through `app.graph`
- Orvo Brain/control-plane domain:
  - `app.brain.adapters.*`
  - `app.brain.reporting`
  - `app.brain.operator_api`
  - `app.brain.storage`
  - `app.brain.operator_auth`
  - `app.brain.delivery_status`

Phase 1 success criteria:

- `app/conversation/` owns commercial WhatsApp graph/prompts/model/conversation DB.
- `app/brain/` owns operational control plane only.
- `server.py` delegates to thin domain entrypoints and contains no business/domain logic beyond HTTP concerns.
- `app/brain/*` must not import `app.conversation.*`.
- Conversation DB and Brain DB remain separate.
- Add an ADR documenting the boundary and DB split.

## Follow-ups explicitly not in scope for this structural refactor

- Packet Q: remove legacy inline connector secrets / secret-ref runtime hardening.
- Packet U: durable workflow action ledger and approval objects.
- Packet O: durable audit store / broader trust-admin-security closure.
- Changing owner-facing copy, delivery semantics, case family eligibility, or metric meaning.
- Adding new connectors/features while decomposing structure.

## Required closeout for each later phase

For every phase after Phase 0, report:

- Files moved/changed.
- Tests run and exact result.
- Public contracts affected: expected value is “none” unless explicitly approved.
- Whether `/internal/brain/*` route table and data keys are unchanged.
- Whether redaction canaries still disappear from API responses.
- Follow-ups/blockers.
- Git status and commit SHA if committed.
