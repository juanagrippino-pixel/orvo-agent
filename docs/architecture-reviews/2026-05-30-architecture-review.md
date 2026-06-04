# Architecture Review Board — 2026-05-30

**Reviewer:** Architecture Review Board (automated cron)
**Date:** Saturday, May 30, 2026
**Scope:** Three active worktree branches against `feat/orvo-brain-control-plane`
**Base commit (control-plane):** `104f582` (feat/orvo-brain-control-plane HEAD)

---

## Executive Summary

Orvo's control-plane architecture is well-structured and principled. The OperationalCase, Metric Registry, and Connector Registry modules follow the Atlassian/Jira pattern with high fidelity for a Phase A implementation. The three active worker branches (`claude/case-workflow`, `claude/qa-review`, `claude/runtime-semantics`) all add incremental, well-tested, additive projections without introducing structural debt. Two of three are ready to merge; the third (`claude/qa-review`) is already fully integrated.

**Verdict: All branches merge-ready.** Strategic gaps remain in workflow automation, RBAC, and lifecycle completeness — but these are acknowledged future-scope items (Phase B), not regressions.

---

## Branch Reviews

### 1. `claude/case-workflow` — ✅ MERGE-READY

| Field | Value |
|-------|-------|
| Branch | `claude/case-workflow` |
| Head | `bfc0279` |
| Divergence | 3 commits ahead of `feat/orvo-brain-control-plane` |
| Files changed | `app/brain/operator_api.py` (+204 lines), 3 new test files (+1154 lines) |
| Risk | Low |

**What was added:**
- `summarize_case_handling_latency_histogram()` — measures operator working time (resolved_at − acknowledged_at)
- `_by_case_type` split — groups handling latency by case family
- `_by_entity_kind` split — groups handling latency by entity scope kind

**Architectural assessment:**
- Follows existing projection pattern (tenant-scoped, deterministic, redaction-wrapped).
- Complements existing acknowledgment latency and resolution latency histograms — the three together now form a complete **SLA latency triangle**: queue wait (open→ack), working time (ack→resolved), and total lifecycle (open→resolved). This is architecturally sound.
- Buckets reuse `_AGE_BUCKETS` from `operator_api.py` — no new magic constants.
- Fast/slow extremum cases are attached for triage context.
- Tests cover empty stores, mixed statuses, deterministic ordering, and all three split dimensions.

**No concerns. Merge.**

---

### 2. `claude/qa-review` — ✅ ALREADY INTEGRATED

| Field | Value |
|-------|-------|
| Branch | `claude/qa-review` |
| Head | `5d52428` |
| Divergence | 0 commits ahead of `feat/orvo-brain-control-plane` |
| Risk | None |

This branch has been fully merged into the control-plane branch. It contributed:
- WhatsApp delivery status ingestion (Meta Cloud webhook)
- Multi-tenant case isolation tests
- Idempotency contract locks
- Secret redaction hardening (basic auth, public endpoint errors)
- Multi-connector stale-case contracts
- Product market intel docs

**No action needed.**

---

### 3. `claude/runtime-semantics` — ✅ MERGE-READY

| Field | Value |
|-------|-------|
| Branch | `claude/runtime-semantics` |
| Head | `1bb283b` |
| Divergence | 2 commits ahead of `feat/orvo-brain-control-plane` |
| Files changed | `app/brain/semantics/__init__.py` (+4 exports), `metric_registry.py` (+102 lines), new contract test (+259 lines) |
| Risk | Low |

**What was added:**
- `find_pii_class_violations()` — validates that metric keys used on a surface don't exceed the surface's PII tolerance
- `validate_surface_metric_keys()` — composes unknown_metric + pii_class validation for dispatch paths (WhatsApp, owner brief)

**Architectural assessment:**
- Closes a real gap: WhatsApp/operator surfaces that render metrics need to reject metrics with PII they cannot safely display. This is the correct enforcement point — at the surface boundary, not at the adapter.
- Composition pattern matches existing `validate_report_metric_keys()` — parallel API surface, same deterministic ordering guarantees.
- `allowed_pii_classes` is validated against `_PII_CLASSES` set at construction, preventing silent misconfiguration.
- Unknown keys are intentionally skipped (defers to `validate_metrics`) — clean composition without overlap.
- Contract tests cover the full diagnostic lifecycle.

**No concerns. Merge.**

---

## Deep Architecture Review

### 1. OperationalCase / WorkItem — Atlassian Pattern Alignment

**Rating: 7.5/10 (Strong Phase A, gaps for Phase B)**

#### Strengths
- **Issue identity**: `OperationalCase` has stable `case_id`, `dedupe_key`, `business_id` — analogous to Jira issue key with project scope.
- **Status lifecycle**: `open → acknowledged → resolved` with enforced transitions (`_CASE_STATUS_TRANSITIONS`). Transition validation raises `OperationalCaseStatusError`.
- **Timeline audit**: Every lifecycle change appends `OperationalCaseTimelineEvent` with actor tracking (`system`/`operator`), run_id, evidence references.
- **JQL-lite**: `operator_views.py` implements a full query language parser — field specs, `=`, `!=`, `IN`, `>`, `<` operators, `ORDER BY`, clause limits, SQL-injection prevention, built-in views with `readonly` flag.
- **Dedupe**: Dedupe keys follow `<business_id>/<case_type>/<entity_kind>/<entity_id>/<metric_family>/<grain>` shape from the spec.
- **Evidence snapshots**: Cases carry structured evidence with metric values, source labels, freshness state, and run/artifact references.
- **Projection discipline**: `case_queue_item()`, `case_detail()`, `evidence_snapshot_projection()` all pass through `redact_secrets()`.

#### Gaps vs. Spec/Atlassian Model

| Gap | Severity | Notes |
|-----|----------|-------|
| **Simplified lifecycle** | Medium | Spec (ADR-0002, operational-case-engine-contract) defines `in_progress` and `dismissed` states. Implementation only has 3 of 5. Acceptable for Phase A but creates migration cost. |
| **No Project concept** | Low | Atlassian groups issues by project. Orvo uses `business_id` as the equivalent, which is reasonable for the D2C wedge. |
| **No assignee/owner_ref** | Medium | ADR-0002 calls for `owner_ref`/`assignee_ref`. Current implementation has no field for who is working a case. This blocks routing and per-operator views. |
| **Dedupe keys too coarse** | Medium | Several case types use hardcoded entity IDs (`"unknown"`, `"monitored"`, `"all"`). This collapses distinct issues into one case — e.g., all stockout risks for different SKUs would share a dedupe key. |
| **No CaseAction model** | Low | ADR-0002 envisions `CaseAction` (send_message, request_approval, create_task). Not yet implemented — Phase B scope. |
| **No custom fields** | Low | No user-defined field schema or workflow scheme per business/project. Expected for Phase A. |
| **`channel_mix_shift` detection is fragile** | Info | `_case_type_for_insight()` uses title-string matching (`"tiendanube" in title`). This is brittle and not registry-driven. |

---

### 2. Semantic Registry — Canonical Source of Truth

**Rating: 9/10 (Excellent)**

#### Strengths
- **MetricDefinition** is frozen, slotted, with strict validation: key, family, label, unit, allowed_sources, aliases, aggregation, freshness_required, report_allowed, case_allowed, evidence_required, pii_class.
- **Alias resolution** prevents shadowing (aliases can't shadow canonical keys), detects cross-metric alias collisions, and raises typed `UnknownMetricError`.
- **Dual validation modes**: Advisory (returns `MetricValidationIssue` list) and strict (raises on first unknown). This is the right pattern for gradual migration.
- **Surface-level enforcement**: `validate_report_metric_keys()`, `validate_case_metric_keys()`, `validate_surface_metric_keys()` each validate for specific consumer contracts.
- **Family grouping** via `CASE_FAMILY_METRICS` maps case types to allowed metric keys.
- **Source envelope** validation ensures adapters only emit metrics they're registered to produce.
- **Evidence chain**: `find_evidence_required_violations()` and `find_evidence_source_violations()` enforce that evidence references match `allowed_sources`.
- **PII classification** (new): Surfaces can declare allowed PII classes and get deterministic diagnostics.

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **Static definitions** | Low | All metrics are hardcoded in `DEFAULT_METRIC_DEFINITIONS`. No runtime registration API. For Phase A this is fine; self-service metric onboarding requires dynamic registration. |
| **No versioning** | Low | Metric definitions have no version field. Breaking changes (rename, unit change) would need careful migration. |

---

### 3. Connector Platform — Adapter/Service/Storage Separation

**Rating: 7/10 (Strong registry, weak execution separation)**

#### Strengths
- **ConnectorSpec** is comprehensive: capabilities, emitted_metric_families, required/optional config fields, secret requirements with provider/scopes, executor metadata, health metadata, rate-limit metadata, scope metadata, lifecycle metadata.
- **Secret boundary** is explicit: `SecretRequirement` separates reference-based secrets from legacy inline params. `validate_control_plane_config()` treats inline secrets as warnings and prefers `secret_refs`.
- **Dual validation**: `validate_params()` (legacy, inline) vs. `validate_control_plane_config()` (control-plane, ref-based). Clean migration path.
- **Registry pattern**: `ConnectorRegistry` with `register()`, `get()`, `has()`, `specs()`, `as_mapping()`.

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **Execution not registry-driven** | High | `connector_registry.py` itself notes this as TODO: "pipeline execution still contains connector-specific branching." Adapters are called directly by module path, not through the registry executor. This is the biggest architectural gap. |
| **No adapter/service/storage layering** | Medium | All adapters live in `app/brain/adapters/` — they are both the API client and the data transformation layer. No separate normalizer/service layer between raw API response and metric emission. |
| **No health check implementation** | Low | `ConnectorHealthMetadata` exists but `supports_health_check` defaults to `False` for all connectors. |
| **No connector versioning** | Low | `lifecycle.version` defaults to `"phase-a"` for all connectors — not a real version. |

---

### 4. Workflow Automation — Idempotency, Approval Gates, Audit

**Rating: 6/10 (Good idempotency, no automation engine)**

#### Strengths
- **Idempotency**: `SQLiteIdempotencyStore` with `has()`/`mark()` using `INSERT OR IGNORE`. Deterministic keys: `<business_id>/<date>/<type>`.
- **Run ledger**: `RunRecord` tracks trigger type, status, connector outcomes, artifacts, dispatch outcomes, summary metadata. Full redaction on storage.
- **Case audit trail**: Timeline events record every lifecycle change with actor, run_id, evidence references.
- **Compiled runtime**: `runtime.py` compiles business config into frozen, audit-safe execution artifacts with secret references (no raw secrets).

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No approval gates** | High | ADR-0002 envisions `request_approval` as a CaseAction type. No approval workflow exists. This is critical before any automated external action (e.g., auto-pausing ad campaigns). |
| **No automation rules engine** | High | No rule registry, no condition/action definitions, no dry-run/approved/executed states for automated actions. All current "automation" is deterministic detection → case creation. |
| **No CaseAction model** | Medium | The action record concept from ADR-0002 (queued/approved/running/succeeded/failed/cancelled) is not implemented. |
| **No retry/backoff policy** | Medium | Connector rate-limit metadata exists but no execution-layer retry logic uses it. |

---

### 5. Trust / Admin / Security — RBAC, Audit, Secret Boundaries

**Rating: 7/10 (Strong redaction, no RBAC)**

#### Strengths
- **Secret redaction** is thorough and defense-in-depth:
  - Bearer tokens, Basic auth headers, private key blocks, OAuth codes
  - Quoted and unquoted key-value pairs with secret-like keys
  - URL query parameter redaction
  - Recursive dict/list/tuple traversal
  - Applied at every boundary: evidence metrics, timeline events, run ledger, case storage, API projections
- **Tenant isolation**: All case queries are scoped by `business_id`. `get_scoped_case()` rejects cross-tenant access with 404 (not 403 — avoids information leakage).
- **Operator actor tracking**: `transition_case()` and `add_comment()` require `actor_type` + `actor_ref`.
- **Control-plane secret refs**: `SecretRequirement` + `validate_control_plane_config()` enforces the boundary between ref-based and inline secrets.
- **No secrets in storage or projections**: Every `model_dump()` / JSON serialization path goes through redaction.

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No RBAC** | High | No roles, permissions, or permission schemes. Any authenticated user can transition any case. This is acceptable while the operator surface is internal-only but blocks multi-tenant SaaS. |
| **No authentication middleware** | High | The Flask server (`server.py`) uses basic auth for brain endpoints but has no session management, JWT, or OAuth flow. |
| **No centralized audit event store** | Medium | Audit events are embedded in case timelines and run ledger records. There's no standalone audit log that answers "what did operator X do across all cases?" |
| **No secret rotation** | Low | No mechanism to rotate or revoke connector secrets through the control plane. |
| **`business_id` is the only authorization boundary** | Medium | No workspace, team, or organizational hierarchy above business_id. |

---

## Strategic Alignment Assessment

### What's working well
1. **Platform-first discipline**: The codebase consistently routes metrics → detections → cases → projections. WhatsApp is a surface, not the product. This is the correct strategic bet.
2. **Deterministic core**: No LLM-driven metrics, detections, priorities, or lifecycle transitions. Evidence-backed everything.
3. **Test coverage**: 108+ test files cover contracts, invariants, adapters, projections, and operator APIs. TDD discipline is visible.
4. **Documentation depth**: ADRs, specs, catalogs, and research docs are ahead of the implementation — unusual and healthy.
5. **Worker isolation**: Each branch is small, additive, and scoped. No architectural pivots or central model rewrites.

### Strategic risks to monitor
1. **Operator API monolith** (`operator_api.py` is 2432 lines): The projection layer is growing fast. Consider splitting into domain modules (latency, throughput, queue, timeline) before it becomes unmaintainable.
2. **Dedupe key coarseness**: Entity-specific cases (per-SKU, per-channel) are not yet possible. This will matter for `stockout_risk` where 50 SKUs could each have separate risk.
3. **Title-based case type detection**: `_case_type_for_insight()` does string matching on insight titles. This is fragile. Cases should be detected from structured insight metadata, not Spanish text patterns.
4. **No execution-through-registry**: The connector registry is metadata-only. Actual execution bypasses it. This must be closed before self-service connector onboarding works.

---

## Action Items

| # | Priority | Owner | Action |
|---|----------|-------|--------|
| 1 | P1 | Platform | Merge `claude/case-workflow` and `claude/runtime-semantics` into control-plane |
| 2 | P1 | Platform | Close entity-specific dedupe gap (per-SKU/entity_id in `_dedupe_key()`) |
| 3 | P2 | Platform | Add `in_progress` and `dismissed` lifecycle states per spec |
| 4 | P2 | Platform | Add `assignee_ref` / `owner_ref` field to `OperationalCase` |
| 5 | P2 | Platform | Replace `_case_type_for_insight()` string matching with structured detection metadata |
| 6 | P2 | Platform | Split `operator_api.py` into domain modules |
| 7 | P3 | Platform | Implement CaseAction model with approval gate states |
| 8 | P3 | Platform | Wire connector execution through registry executor metadata |
| 9 | P3 | Security | Design RBAC permission scheme for multi-tenant Phase B |
| 10 | P3 | Security | Add centralized audit event store |

---

## File Inventory

Key modules reviewed:

| Module | Lines | Role |
|--------|-------|------|
| `app/brain/operational_cases.py` | 971 | Case model, lifecycle, detection, dedupe, stores |
| `app/brain/operator_api.py` | 2432 | API projection helpers, histograms, queue, timeline |
| `app/brain/operator_views.py` | 333 | JQL-lite parser, built-in views |
| `app/brain/semantics/metric_registry.py` | ~1150 | Metric definitions, validation, envelope checks |
| `app/brain/connector_registry.py` | 501 | Connector specs, validation, registry |
| `app/brain/runtime.py` | 385 | Compiled business runtime |
| `app/brain/run_ledger.py` | 423 | Run records, connector outcomes, artifacts |
| `app/brain/storage.py` | 229 | SQLite schema and stores |
| `app/brain/security/redaction.py` | 147 | Secret/PII redaction |
| `app/brain/models.py` | 60 | Core Pydantic models |
| `app/brain/insights.py` | 268 | Deterministic insight engine |
| `app/brain/delivery.py` | 305 | WhatsApp dispatch |

Architecture docs reviewed:
- `docs/adr/0002-operational-case-native-issue-object.md`
- `docs/architecture/vasilios-atlassian-platform-patterns.md`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/connector-registry-contract.md`

---

*Next review: 2026-05-31. The Architecture Review Board runs daily as a scheduled cron job.*
