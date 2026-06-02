# Architecture Review Board — Post-Merge Deep Review

**Reviewer:** Architecture Review Board (automated cron)
**Date:** Saturday, May 30, 2026 (evening cycle)
**Scope:** Full control-plane codebase post-merge of three worker branches
**Base commit:** `8ca987b` (`feat/orvo-brain-control-plane` HEAD)
**Test suite:** **913 passed, 0 failed** (5.81s)

---

## 1. Merge Status Summary

All three worker branches have been **successfully merged** into `feat/orvo-brain-control-plane`:

| Merge | Commit | Contributed By | Status |
|-------|--------|----------------|--------|
| `claude/case-workflow` | `b537978` | Operator API projections | ✅ Merged |
| `claude/runtime-semantics` | `d77b456` | Metric registry validation | ✅ Merged |
| `claude/qa-review` | `9c86c6d` | QA/delivery/redaction | ✅ Merged |

Post-merge additions:
- `c4fa8a7` — Freshness-companion metric validation diagnostic
- `b3f31cd` / `ce4ae92` — Priority-bracket-split latency histogram projections
- `eecd254` — Dispatch transient-failure locks owner brief
- `a75b229` — Surface metric object validator composition
- `8ca987b` — Top-by-priority cases HTTP endpoint with auth/tenant scoping

---

## 2. OperationalCase / WorkItem — Atlassian Pattern Deep Dive

### 2.1 Model Assessment (operational_cases.py, 971 lines)

**Architecturally sound elements:**

- **Pydantic v2 with strict validation.** `OperationalCase` uses `@model_validator(mode="after")` to enforce temporal invariants: `updated_at >= opened_at`, `acknowledged_at >= opened_at`, `resolved_at >= opened_at`, and `resolved` status requires `resolved_at`. These are the right guardrails.

- **Evidence chain is first-class.** `OperationalCaseEvidenceSnapshot` captures metric_key, value, unit, currency, window, observed_at, freshness_state, entity_scope, and run/artifact references. This is richer than what most Jira-issue implementations provide — it's closer to how ServiceNow or PagerDuty model incident evidence.

- **Dedupe via stable key.** `find_by_dedupe_key(business_id, dedupe_key)` enables idempotent upsert: same issue → update; resolved case → reopen. The key shape `<business_id>/<case_type>/<entity_kind>/<entity_id>/<metric_family>/<time_grain>` follows the spec faithfully.

- **Deep copy discipline.** Every store method returns `case.model_copy(deep=True)`, preventing aliasing bugs across callers. This is important for a multi-tenant system.

**Critical defects found:**

#### 2.1.1 🔴 Dedupe keys collapse distinct issues (P1)

```python
# operational_cases.py:731-740
def _dedupe_key(business_id: str, case_type: OperationalCaseType) -> str:
    suffix_by_type = {
        "sales_drop": "sales_drop/channel/all/commerce.revenue/daily",
        "stockout_risk": "stockout_risk/business/monitored/commerce.inventory/daily",
        "data_stale": "data_stale/connector/unknown/runtime.freshness/daily",
        ...
    }
    return f"{business_id}/{suffix_by_type[case_type]}"
```

The entity_id segment is **hardcoded** to `"all"`, `"monitored"`, `"unknown"`. This means:
- If a business has 50 SKUs at risk of stockout, they all share one dedupe key and one case.
- If 3 different connectors go stale, they also share one case (via the `make_data_stale_detection` function, which uses `connector_type` correctly per-connector but feeds into a different dedupe path).
- The `_case_type_for_insight()` function (line 714) routes insight → case_type by string-matching the Spanish title: `"stock" in title`, `"sin ventas" in title`, `"conversaciones" in title`. This is fragile.

**Recommendation:** Pass `entity_scope` through to `_dedupe_key()` so the entity kind/id actually differentiates cases. Replace title-based case-type dispatch with a structured `insight.case_type` or `insight.detection_rule_id` field.

#### 2.1.2 🟡 Simplified lifecycle vs spec (P2)

The contract (`operational-case-engine-contract.md`) defines **5 states**: `open`, `acknowledged`, `in_progress`, `resolved`, `dismissed`. Implementation only has **3**: `open`, `acknowledged`, `resolved`.

The transition table is correspondingly limited:
```python
_CASE_STATUS_TRANSITIONS = {
    "open": {"acknowledged"},         # Only one forward path
    "acknowledged": {"resolved"},     # No in_progress, no dismiss
    "resolved": set(),                # No reopen via transition (only via upsert)
}
```

The spec allows `open → resolved`, `acknowledged → dismissed`, `resolved → open` (reopen), none of which are implemented. Reopen currently only works through `upsert_detection()` on resolved cases, which is a separate code path.

**Recommendation:** Add `in_progress` and `dismissed` states. Wire transition-based reopen alongside upsert-based reopen. This is a schema-level migration that will grow more expensive as the timeline/event system matures.

#### 2.1.3 🟡 No assignee/owner_ref field (P2)

The spec calls for `owner_ref` / `assignee_ref` on cases. The `ActorType` enum only has `"system"` and `"operator"`. There's no field for who is actively working a case. This blocks:
- Per-operator workload views
- Routing/notification logic
- SLA breach attribution

#### 2.1.4 ✅ JQL-lite is architecturally correct (No action needed)

`operator_views.py` (333 lines) implements:
- **Safe parsing**: Regex-based tokenizer, no SQL translation, clause limit (8), max query length (512), SQL injection keywords blocked.
- **Field specs**: Enum fields with `allowed_values`, int fields with comparison operators, datetime fields with ISO parsing, string fields with equality.
- **Built-in views** with `readonly` flag for standard dashboards.
- **Deterministic ordering**: Stable sort with `case_id` tie-break.
- **Tenant scoping**: `query_case_queue()` always receives `business_id` — no path to cross-tenant leaks.

This is a clean, well-bounded JQL analog suitable for the D2C control plane.

---

## 3. Semantic Registry — Canonical Source of Truth

### 3.1 Assessment (metric_registry.py, 1268 lines)

**Rating: 9.5/10 — Best-in-class for Phase A**

The metric registry is the architectural anchor of the entire system. Every other layer (adapters, insights, cases, reports, operator views) should derive its metric semantics from this registry.

#### Strengths (detailed)

1. **Frozen MetricDefinition with 12 validation dimensions**: key, family, label, unit (6 types), allowed_sources, aliases, aggregation (7 types), freshness_required, report_allowed, case_allowed, evidence_required, pii_class (3 levels). All validated in `__post_init__`.

2. **Alias safety**: Aliases cannot shadow canonical keys, cannot be duplicated within a definition, cannot collide across definitions. `resolve_key()` distinguishes strict (raises `UnknownMetricError`) from lenient (`try_resolve_key()` returns None).

3. **10 deterministic diagnostic functions**: Each one is independently composable, skips unknown keys (delegates to `validate_metrics`), and preserves input order. The composition order is documented:
   - `validate_metrics` → unknown keys
   - `find_source_envelope_violations` → unauthorized sources
   - `find_family_envelope_violations` → undeclared families
   - `find_evidence_required_violations` → missing evidence
   - `find_evidence_source_violations` → wrong-source evidence
   - `find_value_kind_violations` → type mismatches
   - `find_pii_class_violations` → PII exceedance
   - `find_freshness_companion_violations` → freshness companion missing
   - `find_report_allowed_violations` → report-only enforcement
   - `find_case_allowed_violations` → case-only enforcement

4. **Surface-level composition**: `validate_report_metric_keys()`, `validate_case_metric_keys()`, `validate_surface_metric_keys()` each pick the relevant subset of diagnostics for their enforcement boundary.

5. **CASE_FAMILY_METRICS mapping**: Ties each case type to its required metric keys, enabling `detect_cases_from_report()` to filter report metrics for evidence.

6. **Freshness-companion diagnostic** (new in `c4fa8a7`): Ensures metrics with `freshness_required=True` are always accompanied by a `runtime.freshness` companion metric in the same payload. This catches silent data-staleness at the adapter emission boundary.

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| No runtime registration API | Low | All 17 metrics are hardcoded. This is fine for Phase A but blocks self-service metric onboarding. |
| No metric versioning | Low | Breaking changes (rename, unit change) would need careful migration. |
| Insights still use legacy metric keys | Medium | `insights.py` uses `revenue_today`, `stock_units`, `ad_spend_today` as internal keys. These resolve via aliases, so functionally correct, but the insight engine should migrate to canonical keys to reduce alias dependency. |
| `channel_mix_shift` is not in CASE_FAMILY_METRICS | Medium | The case type `channel_mix_shift` is defined in the `OperationalCaseType` literal and in `CASE_FAMILY_METRICS`... wait, it's not. Looking at the mapping, I see only `sales_drop`, `stockout_risk`, `data_stale`, `fulfillment_backlog`, `unanswered_conversations`, `spend_without_orders`. `channel_mix_shift` is missing from `CASE_FAMILY_METRICS`. The detection path won't be blocked, but the evidence chain will be empty for this case type. |

---

## 4. Connector Platform — Adapter/Service/Storage Separation

### 4.1 Assessment (connector_registry.py, 673 lines + 6 adapters)

**Rating: 7/10**

#### Architecture

```
ConnectorSpec (metadata) ─── ConnectorRegistry (lookup)
     │                              │
     ├── capabilities               ├── validate_control_plane_config()
     ├── emitted_metric_families    ├── validate_emitted_metrics()
     ├── required_secret_refs       └── validate_emitted_metric_objects()
     ├── executor metadata
     ├── health metadata
     ├── rate_limit metadata
     └── lifecycle metadata
```

#### Strengths

1. **Secret boundary is explicit**: `SecretRequirement` separates the control-plane secret reference (handle/ID) from the legacy inline execution parameter. `validate_control_plane_config()` warns on inline secrets but doesn't reject them — correct migration posture.

2. **Envelope validation is three-layered**: `validate_emitted_metric_objects()` composes 6 diagnostic functions, validating keys → sources → families → evidence presence → evidence sources → value types. This catches adapter drift at the emission boundary.

3. **Registry is immutable after construction**: `ConnectorRegistry.register()` rejects duplicates. `specs()` and `as_mapping()` return read-only views.

#### Critical Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **Execution not registry-driven** | 🔴 P1 | `server.py` calls adapters directly: `build_daily_report_from_tiendanube(...)`, `build_daily_report_from_mercadolibre(...)`. The registry's `executor_factory_path` metadata is unused. This means adding a new connector requires editing `server.py`, not just registering a spec. |
| **No normalizer layer** | 🟡 P2 | Each adapter handles both API client and metric transformation. There's no separate normalizer that converts raw API responses into canonical metrics. This couples adapter protocol changes to metric emission semantics. |
| **Inline secrets still accepted on public endpoints** | 🟡 P2 | `server.py:432-462` (Tiendanube endpoint) accepts `access_token` as a raw JSON field. Same for MercadoLibre (line 465). The control-plane validation path is separate from these public endpoints. |
| **No connector health probing** | Low | `ConnectorHealthMetadata.supports_health_check` is `False` for all connectors. |

---

## 5. Workflow Automation — Idempotency, Approval Gates, Audit

### 5.1 Assessment

**Rating: 6.5/10**

#### What exists

1. **Idempotent dispatch** (`dispatch.py`): `_send_text_once()` checks `idempotency_store.has(key)` before sending, marks after success. Keys are deterministic: `<business_id>/<date>/<type>`. SQLite-backed via `SQLiteIdempotencyStore`.

2. **Run ledger** (`run_ledger.py`, 423 lines): `RunRecord` tracks connector outcomes, artifact refs, dispatch outcomes, summary metadata. Enforces terminal-state immutability and time-ordering invariants. SQLite-backed via `SQLiteRunLedger`.

3. **Case audit trail**: Every lifecycle mutation appends a `OperationalCaseTimelineEvent` with event_type, actor_type, actor_ref, run_id, evidence_snapshot_ids, and summary.

4. **Dispatch hardening** (new in `eecd254`): Transient dispatch failures no longer skip the owner case brief. Previously a failed WhatsApp delivery could suppress the case brief; now the brief is locked behind the dispatch attempt.

#### What's missing (Phase B)

| Gap | Severity | Notes |
|-----|----------|-------|
| **No approval gates** | 🔴 P1 | ADR-0002 envisions `CaseAction` with states `queued → approved → running → succeeded/failed/cancelled`. No approval workflow exists. Critical before automated actions (auto-pause ads, auto-restock). |
| **No automation rules engine** | 🔴 P1 | No rule registry, no condition/action definitions, no dry-run mode. All current "automation" is detection → case creation. |
| **No retry/backoff in execution** | 🟡 P2 | `ConnectorRateLimitMetadata` exists but no execution-layer retry uses it. |
| **No workflow scheme per business** | Low | Atlassian projects have workflow schemes. Orvo businesses share one lifecycle. |

---

## 6. Trust / Admin / Security — RBAC, Audit Trail, Secret Boundaries

### 6.1 Assessment

**Rating: 7.5/10**

#### Defense-in-depth secret architecture

The redaction layer (`security/redaction.py`, 147 lines) is comprehensive:
- **14 secret key patterns** detected: access_token, refresh_token, api_key, authorization, password, private_key, credential, cookie, session, signature, secret, token, oauth_code, auth_header.
- **6 regex patterns**: Bearer tokens, Basic auth headers, quoted/unquoted key-value pairs with secret keys, private key blocks, OAuth code in context.
- **URL query parameter redaction**: `redact_uri()` parses URLs and replaces secret-shaped query params.
- **Recursive traversal**: `redact_secrets()` walks dicts, lists, tuples, and strings.
- **Applied everywhere**: Evidence metrics, timeline events, run ledger, case storage, API projections, dispatch text.

#### Tenant isolation

- All case queries require `business_id` scope.
- `get_scoped_case()` rejects cross-tenant access with 404 (not 403 — prevents information leakage).
- Server-side: `_authorize_internal_operator()` uses `hmac.compare_digest` with Bearer token.
- Internal endpoints route through `_with_internal_stores()` which creates per-request SQLite connections.

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No RBAC** | 🔴 P1 | Any authenticated internal token can transition any case, comment on any case, or read any business's data. Acceptable for internal-only Phase A. Blocks multi-tenant SaaS. |
| **No authentication middleware** | 🔴 P1 | Flask server has per-route auth (`_authorize_internal_operator`), no session management, no JWT, no OAuth. Public endpoints accept inline secrets. |
| **No centralized audit event store** | 🟡 P2 | Audit events are embedded in case timelines and run ledger records. No standalone log answering "what did operator X do across all cases?" |
| **`business_id` is the only boundary** | 🟡 P2 | No workspace, team, or organizational hierarchy. |
| **Meta signature validation is optional** | Low | `_verify_meta_signature()` returns `True` if `WHATSAPP_APP_SECRET` is empty. This is acceptable for development but should be enforceable in production. |

---

## 7. Strategic Alignment & Architectural Risks

### What's working well

1. **Platform contracts ahead of implementation.** ADRs, specs, and catalogs define the target architecture. The implementation follows these contracts faithfully, with documented deviations.

2. **Deterministic core is uncompromised.** No LLM-driven metrics, detections, priorities, or lifecycle transitions anywhere in the codebase. Every finding has cited evidence.

3. **Test discipline is exceptional.** 913 tests covering contracts, invariants, adapters, projections, operator APIs, and integration paths. The TDD discipline is visible in test naming and granular coverage.

4. **Worker isolation is principled.** Each branch adds one well-scoped capability without touching central models. The merge history shows clean fast-forward integration.

5. **Control-plane/data-plane separation is emerging.** The compiled runtime (`runtime.py`) separates business configuration (control plane) from execution runtime. Secret refs bridge the gap.

### Risks to address before Phase B

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **operator_api.py monolith** (2692 lines) | High | Split into domain modules: `latency.py`, `throughput.py`, `queue.py`, `timeline.py`, `actions.py`, `dashboard.py` |
| 2 | **Execution bypasses registry** | High | Wire `ConnectorSpec.executor.factory_path` into a compiled-runtime execution engine that replaces direct adapter calls |
| 3 | **Inline secrets on public endpoints** | High | Move Tiendanube/MercadoLibre endpoints behind control-plane secret resolution |
| 4 | **Coarse dedupe keys** | Medium | Pass entity_scope through to `_dedupe_key()` for per-entity cases |
| 5 | **Title-based case type routing** | Medium | Add `case_type` or `detection_rule_id` to `Insight` model; use structured routing |
| 6 | **Missing `channel_mix_shift` in CASE_FAMILY_METRICS** | Medium | Add entry and required metric keys, or remove from OperationalCaseType if not yet implemented |

---

## 8. Prioritized Action Items for Phase B

| Priority | Action | Effort | Dependencies |
|----------|--------|--------|--------------|
| **P1** | Close dedupe gap: pass `entity_scope` to `_dedupe_key()` | S | None |
| **P1** | Replace `_case_type_for_insight()` with structured detection metadata | S | Insight model change |
| **P1** | Split `operator_api.py` into domain modules | M | API route refactoring |
| **P1** | Wire connector execution through registry executor | L | Compiled runtime integration |
| **P1** | Add RBAC permission scheme design | M | Security architecture |
| **P2** | Add `in_progress` and `dismissed` lifecycle states | M | Schema migration |
| **P2** | Add `assignee_ref` / `owner_ref` to OperationalCase | S | Schema migration |
| **P2** | Add CaseAction model with approval gate states | L | Workflow engine design |
| **P2** | Migrate `insights.py` to canonical metric keys | S | Alias removal |
| **P2** | Add missing `channel_mix_shift` to CASE_FAMILY_METRICS | S | Define required metrics |
| **P2** | Add centralized audit event store | M | Schema design |
| **P3** | Move public endpoints behind control-plane secret resolution | M | Auth middleware |
| **P3** | Implement connector health probing | S | Adapter contracts |
| **P3** | Add metric registry runtime registration API | L | Versioning design |
| **P3** | Add connector normalizer/service layer separation | L | Adapter refactoring |

---

## 9. File Inventory (Updated)

| Module | Lines | Role | Changes Since Last Review |
|--------|-------|------|--------------------------|
| `app/brain/operator_api.py` | 2692 | API projections, histograms, queue, timeline | +260 lines: priority-bracket splits, handling latency by connector, top-by-priority endpoint |
| `app/brain/operational_cases.py` | 971 | Case model, lifecycle, detection, stores | Unchanged |
| `app/brain/operator_views.py` | 333 | JQL-lite parser, built-in views | Unchanged |
| `app/brain/semantics/metric_registry.py` | 1268 | Metric definitions, 10 validation functions | +216 lines: freshness companion, surface object validator, PII class diagnostics |
| `app/brain/connector_registry.py` | 673 | Connector specs, validation, registry | Unchanged |
| `app/brain/runtime.py` | 385 | Compiled business runtime | Unchanged |
| `app/brain/run_ledger.py` | 423 | Run records, outcomes, artifacts | Unchanged |
| `app/brain/storage.py` | 229 | SQLite schema and stores | Unchanged |
| `app/brain/security/redaction.py` | 147 | Secret/PII redaction | Unchanged |
| `app/brain/dispatch.py` | 127 | WhatsApp dispatch with idempotency | Transient-failure lock for owner brief |
| `app/brain/insights.py` | 268 | Deterministic insight engine | Unchanged |
| `app/brain/models.py` | 60 | Core Pydantic models | Unchanged |
| `server.py` | 673 | Flask HTTP layer | +33 lines: top-by-priority endpoint |

**Total test count: 913** (up from pre-merge, all passing)

---

## Verdict

The control-plane codebase is **architecturally sound for Phase A** and ready for pilot operations. The three worker branches have been cleanly integrated. The semantic registry is the strongest architectural element — it anchors all downstream contracts. The main technical debt is in execution-layer integration (connectors bypass the registry) and in the OperationalCase dedupe/lifecycle completeness, both of which are acknowledged Phase B work.

**No merge blockers. No regressions detected post-merge.**

---

*Next review: 2026-05-31. The Architecture Review Board runs as a scheduled cron job.*
