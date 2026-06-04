# Orvo Hito 0 + Deep Platform Program

> **For Hermes:** run this as a multi-track program with Hito 0 as strict priority. Use Kanban as the source of truth, keep parent-repo hygiene clean, and commit agreed documentation immediately.

**Goal:** Deliver Hito 0 for ARTEMEA/client-zero while using spare weekly capacity to build the platform systems that will make Orvo faster, safer, and more scalable over the next months.

**North star:** A trustworthy 08:00 Argentina WhatsApp report for ARTEMEA comes first. Parallel tracks must not compete with Hito 0 for critical coding capacity, must avoid touching the production daily-report path until Hito 0 lands, and must produce reusable platform systems rather than customer-facing feature sprawl.

---

## Operating rules

1. **Hito 0 always wins.** Any conflict for coder, tester, integrator, or review capacity is resolved in favor of Hito 0.
2. **Most parallel work stays research/design/architecture-heavy.** Heavy coding remains capped to 2 concurrent workers.
3. **No feature sprawl.** Parallel tracks build platform layers, contracts, evals, generators, observability, and reusable report/insight infrastructure.
4. **Every major artifact gets triple validation.** Technical reviewer, adversarial reviewer, and product/north-star reviewer.
5. **Cut weak tracks early.** If a track stops producing reusable architecture or compounding leverage, stop it.
6. **Commit docs immediately.** No agreed documentation stays untracked.

---

## Active program tracks

### H0 — Hito 0 maximum legitimate DAG
Deliver the first trustworthy ARTEMEA/client-zero report path:
- connector audit fanout
- runtime parity / forced-vs-scheduled audit
- insight engine v1 refinement
- report v0 fanout + selection
- validation and integration

### P1 — Massive evals platform
Build the evaluation substrate Orvo will use continuously:
- large synthetic test catalog for insights
- golden outputs per insight family
- automated engine-version comparison
- product-quality metrics: precision, recall, actionability, noise
- quality dashboard / reporting surface

### P2 — Synthetic D2C data generator
Design and eventually build a generator for realistic physical-goods ecommerce scenarios:
- normal operations
- stock crises
- ads underperformance
- returns spikes
- launches, dead days, peak periods
- configurable parameters and pipeline-compatible outputs

### P3 — Self-improving Insight Engine
Design-only until the eval/audit substrate is in place:
- compare engine predictions vs later outcomes
- drift detection
- bounded improvement proposals
- internal A/B testing architecture

### P4 — Multi-LLM ensemble research
Research and design when multiple models are worth using:
- consensus strategies
- disagreement handling
- critical-path only usage
- benchmark and cost-benefit analysis

### P5 — Per-client memory and learning
Design how Orvo learns business-specific context over time:
- vocabulary and business semantics
- recurring cycles and exceptions
- key products and channel dependencies
- memory evolution as context changes

### P6 — Scenario simulation architecture
Design-only and sequenced behind synthetic-data and memory foundations:
- “what happens if X?” architecture
- priority D2C use cases
- historical + modeled + LLM hybrid approach
- safe presentation for operators

### P7 — Report surface framework
Reduce the original “catalog of reports” idea into platform primitives:
- taxonomy of report surfaces
- reusable report blocks / layouts
- insight-family-to-surface mapping
- gating rules for when a surface exists

### P8 — Observability and audit platform
Build the production-grade evidence layer:
- tracing for every emitted insight
- audit trail from source metrics to conclusion
- replay of historical runs
- visual diffs between engine versions
- real-time quality monitoring

### P9 — Canonical semantic layer / metric registry
Foundational track supporting evals, synthetic data, observability, and future engines:
- canonical business entities
- metric definitions and versioning
- time-window semantics
- source-to-metric lineage
- confidence semantics by metric family
- report and insight contracts

---

## Sequencing

### Start immediately in parallel
- H0
- P1
- P2
- P4
- P5
- P8
- P9

### Start as design-only, gated by upstream platform outputs
- P3 depends materially on P1 + P8 + P9
- P6 depends materially on P2 + P5 + P9
- P7 depends materially on H0 + P1 + P9 and should stay framework-level, not become report-feature sprawl

---

## Capacity target

This program is intentionally designed for very high token usage without busywork. Expected full-blast burn is in the hundreds of millions of tokens per week, with most volume justified by:
- independent specialist fanout
- synthesis/reconciliation work
- triple validation on important artifacts
- deep reusable platform design
- large evaluation and synthetic-data design surfaces

---

## Definition of success

Within this wave, Orvo should have:
- a real Hito 0 delivery path for ARTEMEA/client-zero
- a reusable eval platform design with an initial build plan
- a reusable synthetic-data architecture
- a clear self-improving engine roadmap grounded in evals and auditability
- a serious observability and evidence platform design
- a canonical semantic layer for metrics and contracts
- a repeatable multi-track execution machine that can scale without drowning in drift
