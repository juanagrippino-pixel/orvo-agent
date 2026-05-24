# ADR-0004: Autonomous operating toolchain and artifact contract

Status: Proposed  
Date: 2026-05-24

## Context

Orvo is being built by an autonomous organization of agents/workers. Without a durable operating/toolchain contract, capacity turns into disconnected branches, duplicate docs, stale prompts, and unverified summaries.

The product direction is now Atlassian-like: Orvo must become a sellable ecommerce operations control plane, with `OperationalCase` / `WorkItem` as the native product object. The same principle should govern the autonomous organization: work should be represented by durable issue-like artifacts, not transient chat memory.

Public Vasilios/Atlassian platform references also point to a useful pattern: self-service broker, validated control plane, narrow data plane, centralized gateway concerns, observability, and reproducible operations.

## Decision

Orvo will use a formal autonomous operating toolchain:

1. All nontrivial work must be represented by a task packet with owner, bounded context, acceptance criteria, worktree/branch, and expected tests.
2. Implementation happens in external worktrees under `/root/orvo-agent-worktrees/*`; the parent checkout remains clean.
3. Workers must leave a handoff manifest or equivalent durable review artifact following `docs/specs/worker-handoff-manifest.md`.
4. Cross-boundary work requires an ADR/spec/contract diff before broad implementation.
5. Review and integration are separate gates. Worker success summaries are untrusted until files, commits, tests, and manifests are verified.
6. Cron-run agents must not recursively create, update, pause, resume, remove, or schedule Hermes cron jobs. They may propose org changes; the controller/human applies them.
7. Atlassian/Vasilios-inspired platform mechanics should be translated into Orvo as product architecture: broker/control-plane/runtime/gateway/observability patterns, not premature infrastructure sprawl.

## Consequences

- Product capacity becomes auditable artifacts: ADRs, specs, commits, tests, manifests, review reports, integration notes.
- Duplicate or overlapping workers can be detected by bounded context and manifest ownership.
- Release/integration can prepare one branch at a time with known risks and rollback notes.
- Orvo's own autonomous organization becomes a prototype of the sellable control-plane product: work object, workflow, permissions, audit, search, and reporting.

## References

- `docs/organization/orvo-operating-toolchain-blueprint.md`
- `docs/architecture/vasilios-atlassian-platform-patterns.md`
- `docs/specs/worker-handoff-manifest.md`
- `docs/operability/worktree-hygiene.md`
- `docs/architecture/phase-a-control-plane-contract.md`
- `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- `docs/adr/0002-operational-case-native-issue-object.md`
- `docs/adr/0003-deterministic-detection-llm-explanation-boundary.md`
