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

The executable Phase A contract that ties these ADRs to migration order, module structure, and invariants lives in:

- [Phase A Control Plane Architecture Contract](../architecture/phase-a-control-plane-contract.md)
