# Orvo Next-Level Program Plan

> **For Hermes:** run this as a multi-lane execution program, not as one feature queue. Keep Kanban as the source of truth, preserve parent repo hygiene, and prefer narrow deliverables with explicit review gates.

**Goal:** Turn Orvo Brain from a promising control-plane MVP into a credible internal operating product with operator surfaces, runtime safety, auditability, and pilot-readiness — while also upgrading the autonomous delivery system itself.

**Architecture:** Execute across parallel tracks. Keep the deterministic control-plane core moving forward, but in parallel build the operator APIs, security/secret guardrails, delivery/report visibility, and agent-operability layer that make the product scalable. Avoid giant rewrites; collapse drift through small canonical surfaces.

**Operating principle:** We are currently using only a fraction of available execution capacity. The right move is not random fan-out, but a deliberate 10x program with independent lanes, explicit dependencies, review capacity, and watchdog coverage.

---

## Program tracks

### Track A — Control-plane completion
Close the MVP loop so config -> compile -> inspect -> run -> audit is real end-to-end.

**In flight already**
- runner compiled-runtime boundary fix
- business-config CRUD + compile-preview endpoints
- audit-history inspection endpoint
- integration chain for compiled-runtime migration

**Definition of done**
- internal API can read/write business config
- compile preview works from the same contract as runtime
- scheduled and forced/manual paths both use compiled runtime
- audit history is inspectable without shell access

### Track B — Operator surface
Build the narrow internal product surface that lets a human operate Orvo without editing SQLite or Python helpers.

**Next deliverables**
1. Internal operator API surface inventory and contract doc
2. onboarding flow spec for a new business
3. report artifact/detail-view design for long WhatsApp outputs

**Why it matters**
This is what starts making Orvo feel like an internal platform instead of a dev script bundle.

### Track C — Security and tenant safety
Make the control plane safe enough to onboard real customer data and secrets.

**Next deliverables**
1. secret-reference wiring plan (`ConnectorSecretRef` -> runtime resolution)
2. minimal auth/tenant scoping design for internal control-plane/report endpoints
3. conservative rollout path that does not force a full IAM system

**Why it matters**
This is the main boundary between “interesting engineering artifact” and “system safe to operate for paying customers.”

### Track D — Runtime contract hardening
Reduce drift without broad rewrites.

**Next deliverables**
1. connector runtime registry plan
2. compiled-runtime-first execution consolidation plan
3. canonical metric registry plan
4. shared HTTP policy layer plan

**Why it matters**
This collapses the current multi-file branching drift and lowers future connector cost.

### Track E — Product readiness and sellability
Package the system so it is explainable, demoable, and ready for pilots once the core is trustworthy.

**Next deliverables**
1. pilot-readiness gap brief
2. product packaging narrative for internal + customer-facing explanation
3. evidence-backed run visibility story (what ran, what failed, what was sent, why)

**Why it matters**
The product becomes easier to communicate and sell once the operator story is legible.

### Track F — Autonomous execution infrastructure
Upgrade the agent system itself so it can sustain more throughput with less oversight and lower Codex burn.

**In flight already**
- watchdogs for repo hygiene, review queue, gateway liveness
- Claude-backed worker lane design
- worktree hygiene cleanup/policy
- dedicated integrator lane

**Next deliverables**
1. decide which lanes should move to Claude-backed execution first
2. add durable integration/release workflow for reviewed branches
3. codify repo/worktree lifecycle rules for all workers
4. expand review capacity before backend capacity becomes idle

---

## Immediate 10x operating model

### Lane 1 — Ship the current control-plane slice
- finish compiled-runtime boundary fix
- finish CRUD + compile-preview
- finish audit-history inspection
- review and integrate each cleanly

### Lane 2 — Design the next product slice in parallel
- operator API surface inventory
- onboarding flow spec
- report artifact/detail-view spec

### Lane 3 — Prepare the security slice in parallel
- secret-reference wiring design
- endpoint auth/tenant guardrails design

### Lane 4 — Prepare the maintainability slice in parallel
- connector registry plan
- metric registry plan
- shared HTTP policy plan

### Lane 5 — Improve the machine that builds the product
- Claude-backed execution lane
- worktree cleanup and durability policy
- watchdog validation and expansion
- integration/release discipline

---

## Sequencing rules

1. **Never block the whole program on one backend task.**
   If implementation is running, use free capacity for specs, reviews, ops hardening, and next-wave decomposition.

2. **Every implementation lane gets a review lane and an integration lane.**
   No more single-step “code done” thinking.

3. **Prefer spec-first for high-blast-radius changes.**
   Security, auth, secrets, and runtime-contract cleanup should be designed before coding.

4. **Use Claude capacity where it actually lowers cost and increases throughput.**
   Best first targets: read-heavy review, bounded worktree workers, isolated cleanup/inventory tasks.

5. **Do not create broad rewrites.**
   Program scale should come from many narrow, composable lanes — not one giant branch.

---

## Concrete next-wave task graph

### Already active
- compiled-runtime boundary fix -> review -> integrate
- business-config CRUD + compile-preview -> review
- audit-history endpoint -> review
- worktree hygiene cleanup -> review
- Claude-backed worker lane design -> review

### Ready to add immediately
1. operator API inventory + next-step contract
2. onboarding flow spec
3. secret-reference + tenant/auth hardening spec
4. report artifact/detail-view spec
5. runtime hardening decomposition into connector registry / metrics / HTTP policy
6. master execution brief that merges all current findings into a single prioritized board-facing program

---

## Success metric for this program

Within the next wave, Orvo should have:
- a real internal control-plane slice
- a legible operator surface
- an explicit path to secure secret handling and endpoint scoping
- a cleaner runtime contract roadmap
- a more durable autonomous delivery machine

That is a much larger and more compounding outcome than just “finish one more feature.”
