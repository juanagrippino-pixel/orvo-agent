# D2C Ecommerce Control Plane First Product Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Keep implementation additive and preserve existing Hito0/report behavior.

**Goal:** Make Orvo's first sellable product a D2C ecommerce control plane while preserving the internal platform/control-plane architecture.

**Architecture:** The buyer-facing wedge is Tiendanube/WhatsApp-first ecommerce operations. The implementation remains platform-grade: connector registry, compiled runtime, run ledger, metric registry, Operational Cases, deterministic projections, and operator surfaces.

**Tech Stack:** Python, FastAPI-style existing server surface, Pydantic v2 models, SQLite storage, existing Orvo Brain modules under `app/brain/*`, pytest.

**Companion specs:** `docs/product/d2c-control-plane-prd.md`, `docs/specs/d2c-case-family-catalog.md`, `docs/specs/d2c-operator-surface-contract.md`, `docs/roadmap/d2c-control-plane-roadmap.md`, `docs/organization/d2c-autonomous-worker-addendum.md`.

---

## Priority rule

If a task conflicts between "generic platform" and "first sellable D2C wedge", choose the path that ships trustworthy D2C operational cases without violating platform contracts.

```text
Sell narrow: D2C ecommerce control plane.
Build deep: platform/control-plane core.
```

## Phase 0 — Product-direction lock

### Task 0.1: Treat ADR-0005 as binding input

**Objective:** Ensure all future worker prompts reference the accepted product wedge decision.

**Files:**
- Read: `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- Read: `docs/product/d2c-ecommerce-control-plane.md`
- Modify when dispatching work: worker prompts, plans, and lane briefs

**Verification:** Every new product/architecture worker prompt should include: "first sellable product = D2C ecommerce control plane; internals = platform/control-plane core."

## Phase 1 — Platform primitives that unlock the wedge

### Task 1.1: Runtime parity before new surfaces

**Objective:** Preview, forced, and scheduled runs should converge on `CompiledBusinessRuntime` before new owner-facing surfaces depend on runtime output.

**Files:**
- Modify: `app/brain/runtime/compiled.py`
- Modify: `app/brain/runtime/compiler.py`
- Modify: `app/brain/runtime/execution.py`
- Modify cautiously: `app/brain/runner.py`, `app/brain/scheduler.py`, `scripts/run_orvo_brain_reports.py`
- Test: `tests/test_brain_runtime_*.py`, `tests/test_run_orvo_brain_reports_script.py`

**Acceptance criteria:**
- One compiled runtime shape is used by preview/forced/scheduled paths, or compatibility shims prove the same plan shape.
- Existing report tests remain green.
- Runtime artifacts never include raw secrets.

### Task 1.2: Connector registry as the Tiendanube expansion gate

**Objective:** Stop adding connector behavior through scattered connector-type branches.

**Files:**
- Modify: `app/brain/connectors/contracts.py`
- Modify: `app/brain/connectors/registry.py`
- Modify: `app/brain/connectors/policies.py`
- Adapter paths stay thin under `app/brain/adapters/`

**Acceptance criteria:**
- Tiendanube capabilities, required params, required secret refs, degraded modes, and executor are registry-described.
- New D2C connector work must register capabilities before runtime use.

### Task 1.3: Run ledger visible enough for operators

**Objective:** Give operators and future surfaces a durable answer to "what happened in this run?"

**Files:**
- Modify: `app/brain/runtime/ledger.py`
- Modify/additive: `app/brain/storage.py`
- Modify/additive: operator API routes when available

**Acceptance criteria:**
- Run start/end, connector result, artifact refs, errors/degraded states, and dispatch attempts are persisted or contract-tested.
- Redaction tests prove no raw tokens/secrets land in ledger artifacts.

## Phase 2 — D2C semantic and case foundation

### Task 2.1: Register D2C metric families first

**Objective:** Make ecommerce cases depend on formal metric definitions, not ad hoc strings.

**Files:**
- Modify: `app/brain/semantics/metric_registry.py`
- Test: `tests/test_brain_metric_registry*.py`

**Initial families:**
- `commerce.orders`
- `commerce.revenue`
- `commerce.inventory`
- `commerce.fulfillment`
- `ads.spend`
- `ads.delivery`
- `ads.roas`
- `support.conversations`
- `runtime.freshness`
- `runtime.data_quality`

**Acceptance criteria:**
- D2C case families can reference registered metric keys/aliases.
- Legacy metric keys remain compatible during migration.

### Task 2.2: Create first `OperationalCase` slice from deterministic insights

**Objective:** Add the durable workflow object without breaking existing `DailyReport` behavior.

**Files:**
- Create/modify: `app/brain/cases/models.py`
- Create/modify: `app/brain/cases/engine.py`
- Create/modify: `app/brain/cases/storage.py`
- Test: `tests/test_brain_cases*.py`

**First case types:**
- `sales_drop`
- `stockout_risk`
- `data_stale`

**Acceptance criteria:**
- Case creation is deterministic from metrics/insights/runtime events.
- Dedupe key is stable.
- Cases include evidence.
- Existing report rendering still works directly from `DailyReport` during migration.

### Task 2.3: Add D2C case projections for WhatsApp/operator surfaces

**Objective:** Begin moving owner-facing output from raw insight paragraphs toward case-backed summaries.

**Files:**
- Create/modify: `app/brain/cases/projections.py`
- Modify carefully: `app/brain/reporting.py`
- Modify carefully: operator API routes when available

**Acceptance criteria:**
- WhatsApp/operator summaries can cite case IDs/evidence refs.
- Missing/stale connector data narrows advice instead of being filled in by language.
- LLMs, if later added, only rephrase allowed facts.

## Phase 3 — First sellable wedge readiness

### Task 3.1: Tiendanube-first operating brief

**Objective:** Produce a concise owner brief that feels like ecommerce operations, not generic reporting.

**Acceptance criteria:**
- Names the top case or top reason no action is recommended.
- Shows evidence/source lines.
- Shows degraded-data caveats.
- Uses direct Argentine Spanish without scammy sales phrasing.

### Task 3.2: Operator inspection loop

**Objective:** Let an internal operator inspect the run and case state before/after owner delivery.

**Acceptance criteria:**
- Operator can inspect connector status, run artifacts, open cases, and dispatch outcome.
- Manual follow-up can be attached as a case comment/action record.

### Task 3.3: Wedge demo/sales pack only after state is trustworthy

**Objective:** Avoid demo-only drift by generating sales material from the actual product contract.

**Acceptance criteria:**
- Sales language matches `docs/product/d2c-ecommerce-control-plane.md`.
- Demo output uses redacted/example data only.
- No claim implies unsupported automation or guaranteed revenue lift.

## Non-goals

- No generic developer platform launch before the D2C wedge is sellable.
- No horizontal team OS positioning before D2C cases/workflows work.
- No broad rewrite of existing reporting, adapters, or storage.
- No LLM-created business truth.

## Verification checklist

- [ ] `pytest -q` passes after code changes.
- [ ] `git diff --check` passes.
- [ ] New docs link ADR-0005 and product direction.
- [ ] Worker prompts include the wedge/platform split.
- [ ] Existing Hito0/runtime docs remain compatible.
