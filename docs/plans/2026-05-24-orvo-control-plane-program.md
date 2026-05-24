# Orvo Control Plane Program

> **For Hermes:** treat this as the serious project-start document for the Atlassian-style Orvo pivot. Use it as the source of truth for decomposition, worker assignment, ADRs, and implementation sequencing. Optimize for long-term architecture, not demo speed.

**Goal:** Turn Orvo from a deterministic WhatsApp reporting path into a true operational control plane for SMB ecommerce: a system that ingests multi-channel business signals, compiles them into a canonical operational model, creates actionable Operational Cases, tracks workflow state, and safely coordinates humans + automations.

**North star:** Orvo becomes the place where a business sees, prioritizes, and resolves operational issues/opportunities across sales, conversations, fulfillment, inventory, and marketing — with WhatsApp as the first interface, not the whole product.

**Why now:** The current repo already has the hard nucleus: connectors, deterministic insights, reporting, dispatch, scheduler, storage, and 340 passing tests. The bottleneck is no longer “can we generate a report?” but “can we build the control-plane architecture and execution machine fast enough to become a real platform?”

---

## Product thesis

### Native object
The central product object is an **Operational Case**.

An Operational Case represents a business-worthy unit of attention:
- a risk
- a deviation
- a blockage
- an opportunity
- a follow-up
- an approval or decision point

Reports, alerts, WhatsApp messages, and automations all become projections or actions around Operational Cases.

### Source-of-truth split
- **External systems** remain source of truth for their domains:
  - Tiendanube / MercadoLibre -> commerce truth
  - Meta Ads -> ad-delivery truth
  - WhatsApp -> transport truth
  - Sheets/CSV/manual -> onboarding/concierge truth
- **Orvo** becomes source of truth for:
  - normalized operational state
  - case lifecycle
  - evidence trail
  - cross-system coordination
  - operator decisions
  - automations and audit history

### Product stance
Do **not** build a mini-ERP.
Do build a control plane with:
- canonical models
- case workflows
- eventing
- evidence and auditability
- safe operator APIs
- reusable automation primitives

---

## Architecture v1.5 -> v2 target

```text
External systems
  -> connector adapters
  -> connector runtime policy layer
  -> canonical semantic layer / metric registry
  -> compiled business runtime
  -> deterministic detection engine
  -> operational case engine
  -> report / queue / timeline projections
  -> WhatsApp + internal operator API + future web UI
  -> automation/actions
```

### Canonical modules
1. **Connector adapters**
   - thin translation from external APIs/files into canonical records
2. **Connector runtime policy layer**
   - retries, rate limits, auth failure mapping, freshness/degraded semantics
3. **Canonical semantic layer**
   - metric definitions, entity contracts, lineage, units, versioning
4. **Compiled runtime**
   - one executable business plan reused by preview, forced run, scheduled run
5. **Deterministic detection engine**
   - evidence-backed signals only; LLM never invents metrics
6. **Operational Case engine**
   - create, dedupe, score, assign, transition, resolve, reopen
7. **Projection layer**
   - WhatsApp report, queue views, case timelines, latest risk/opportunity summaries
8. **Action layer**
   - send message, mark follow-up, create task, request approval, trigger external action
9. **Governance layer**
   - auth, tenancy, secrets indirection, audit, run ledger, permissions

---

## Current repo assets we preserve

Keep and evolve; do not rewrite:
- `app/brain/models.py`
- `app/brain/config.py`
- `app/brain/storage.py`
- `app/brain/insights.py`
- `app/brain/reporting.py`
- `app/brain/dispatch.py`
- `app/brain/delivery.py`
- `app/brain/runner.py`
- `app/brain/scheduler.py`
- current adapters under `app/brain/adapters/`
- current test suite

Interpretation: we are not starting from zero. We are wrapping the existing deterministic reporting engine in a stronger platform architecture.

---

## Critical architectural gaps to close first

### G1. Compiled runtime
Create a single runtime artifact, e.g. `CompiledBusinessRuntime`, containing:
- business metadata
- enabled connectors
- secret refs resolved at execution time
- normalized thresholds/policies
- report and case emission settings
- delivery settings
- execution plan

This becomes the only input for:
- scheduled runs
- forced/manual runs
- preview/compile endpoints

### G2. Connector registry
Replace scattered `if connector_type == ...` logic with a typed registry:
- required params
- required secret refs
- capabilities
- executor
- validation hooks

### G3. Run ledger + artifact history
Add durable storage for:
- runs
- connector executions
- output artifacts
- dispatch attempts
- errors
- evidence lineage references

### G4. Metric registry / semantic layer
Create a formal registry for:
- metric keys
- labels
- units
- families
- channel namespace rules
- allowed evidence forms
- insight/report participation

### G5. Operational Case engine
Add first-class case models:
- `OperationalCase`
- `CaseEvidence`
- `CaseTransition`
- `CaseComment`
- `CaseAction`

### G6. Secrets indirection + operator API
Stop treating inline config params as the final runtime secret source. Add secret references and internal operator endpoints for config, schedules, compile preview, run history, and case inspection.

---

## Bounded contexts

### C1. Runtime & Orchestration
Owns:
- compiled runtime
- runner/scheduler parity
- execution DAG
- run ledger

### C2. Semantics & Insights
Owns:
- canonical entities
- metric registry
- deterministic detections
- case creation rules

### C3. Connectors & Ingestion
Owns:
- adapter contracts
- connector registry
- runtime policies
- channel capability matrix

### C4. Cases & Workflow
Owns:
- Operational Case model
- lifecycle/state machine
- dedupe, ownership, priority, reopen rules

### C5. Delivery & Surfaces
Owns:
- report composer
- queue projections
- timelines
- WhatsApp output
- internal operator API

### C6. Trust, Security & Observability
Owns:
- tenant boundaries
- auth
- secret refs
- audit trail
- permission model
- replay/inspection support

---

## Worker topology

### Level 0 — Program controller
1 lead orchestrator (Hermes + user direction)
- owns sequencing
- resolves dependencies
- runs synthesis
- protects architecture

### Level 1 — Domain leads
One lead per bounded context above.
They approve contracts and stop drift.

### Level 2 — Execution pods
Per domain:
- 2–4 implementer workers
- 1 verifier/reviewer worker
- optional docs/test worker

### Level 3 — Verification pod
Independent workers for:
- contract tests
- invariants
- audit/security review
- migration/replay review

### Non-negotiable worker rule
No two implementer workers touch the same files unless one is explicitly review-only.

---

## Token/capacity policy

Use large context for:
- architecture synthesis
- contradiction detection
- cross-domain integration planning
- review of ADRs/specs
- release and migration risk analysis

Do **not** waste large context on:
- routine one-file edits
- raw log dumps
- whole-repo prompts for local tasks

### Capacity shape
- controller sessions: high-context, synthesis-heavy
- domain lead sessions: medium/high context, contract-heavy
- implementer workers: low/medium context, tightly scoped
- verifier workers: medium context, adversarial checks

The right way to “use more tokens” is not random concurrency. It is **deep analysis + strong decomposition + independent verification**.

---

## Gates

### Gate 0 — Intake
Every substantial task needs:
- objective
- scope/non-scope
- touched bounded context
- acceptance criteria

### Gate 1 — Design
Required for cross-boundary changes:
- short spec
- ADR if architectural
- contract diff
- migration note

### Gate 2 — Local green
- focused tests
- `pytest -q`
- lint/static checks where applicable

### Gate 3 — Contract/invariant
- schema compatibility
- event compatibility
- tenant/audit invariants
- replay/idempotency expectations

### Gate 4 — Integration
- merged vertical slice works end-to-end
- artifacts visible in run ledger
- observability and rollback path exist

---

## Phase plan

### Phase A — Foundation hardening (immediate)
Build the platform layer that unlocks real scaling without rewriting current Brain.

Deliverables:
1. ADR set for control-plane pivot
2. domain ownership map
3. contract registry scaffold
4. `CompiledBusinessRuntime`
5. connector registry
6. run ledger schema
7. operator API skeleton

### Phase B — Case-native core
Deliverables:
1. `OperationalCase` models and storage
2. deterministic case creation from current reports/insights
3. case timeline and transition history
4. queue projection for “open cases”
5. WhatsApp summaries sourced from open/new/resolved cases

### Phase C — Trust + operability
Deliverables:
1. secret refs
2. auth/tenant scoping for operator endpoints
3. audit trail and replay surfaces
4. connector health / degraded-mode surfacing

### Phase D — Controlled automation
Deliverables:
1. workflow states and transitions
2. action layer
3. simple automation rules
4. execution log and loop protection

---

## First 10 implementation tracks

1. **ADR + repo structure track**
   - add `/docs/adr`, `/docs/specs`, `/contracts`, `/tests/contracts`, `/tests/invariants`
2. **Compiled runtime track**
   - create canonical runtime artifact and unify forced/scheduled paths
3. **Connector registry track**
   - centralize connector contracts/capabilities/executors
4. **Run ledger track**
   - persist run history, connector results, artifacts, dispatch attempts
5. **Metric registry track**
   - centralize metric definitions and migrate insights/reporting to it
6. **Operational Case model track**
   - add storage + models + dedupe/priority basics
7. **Case projection track**
   - queue/timeline/report projections from cases
8. **Operator API track**
   - config/schedule/compile/history/cases endpoints
9. **Secrets & tenancy track**
   - secret refs and basic auth boundary
10. **Verification platform track**
   - contract tests, invariants, replay tests

---

## Definition of success for the new start

Within the first serious wave, Orvo must have:
- one canonical compiled runtime used everywhere
- one connector registry rather than scattered connector branching
- one durable run/audit ledger
- one formal metric registry
- one first-class Operational Case model
- one internal operator API for config/history/case inspection
- strong invariants + contract tests
- preserved current deterministic report path and current test health

If we achieve that, Orvo stops being “a report generator with adapters” and becomes a true control-plane base capable of carrying a much larger product.
