# Architecture Decision Records

This directory holds architecture decisions for Orvo Brain / Orvo Control Plane.

ADR status values:

- `Proposed`: intended direction, not yet fully implemented.
- `Accepted`: decision is binding for future work.
- `Superseded`: replaced by a later ADR.

Current Phase A ADR set:

- [ADR-0001: Control Plane bounded contexts and module ownership](0001-control-plane-bounded-contexts-and-module-ownership.md)
- [ADR-0002: Operational Case as the native issue object](0002-operational-case-native-issue-object.md)
- [ADR-0003: Deterministic detection vs LLM explanation boundary](0003-deterministic-detection-llm-explanation-boundary.md)
- [ADR-0005: D2C ecommerce wedge with platform/control-plane core](0005-d2c-ecommerce-wedge-platform-core.md)

The executable Phase A contract that ties these ADRs to migration order, module structure, and invariants lives in:

- [Phase A Control Plane Architecture Contract](../architecture/phase-a-control-plane-contract.md)

The accepted first-product direction and buyer-facing language live in:

- [Orvo D2C Ecommerce Control Plane](../product/d2c-ecommerce-control-plane.md)
- [Orvo D2C Control Plane PRD](../product/d2c-control-plane-prd.md)
- [D2C Case Family Catalog](../specs/d2c-case-family-catalog.md)
- [D2C Action Key Catalog](../specs/d2c-action-key-catalog.md)
- [D2C Operator Surface Contract](../specs/d2c-operator-surface-contract.md)
- [D2C Control Plane Roadmap](../roadmap/d2c-control-plane-roadmap.md)
- [D2C Packaging and Messaging](../gtm/d2c-packaging-and-messaging.md)
- [D2C Pilot Readiness Checklist](../ops/d2c-pilot-readiness-checklist.md)
- [D2C Autonomous Worker Addendum](../organization/d2c-autonomous-worker-addendum.md)
- [D2C Ecommerce Control Plane First Product Plan](../plans/2026-05-24-d2c-control-plane-first-product.md)
