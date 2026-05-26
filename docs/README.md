# Orvo Brain / Orvo Control Plane Docs

This is the navigation layer for current Orvo Brain / Orvo Control Plane work.

## Current strategic source of truth

The accepted direction is:

```text
First sellable product: D2C ecommerce control plane, Tiendanube/WhatsApp-first.
Internal architecture: Atlassian-like platform/control-plane core.
```

Start here:

1. [`docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`](adr/0005-d2c-ecommerce-wedge-platform-core.md)
2. [`docs/product/d2c-ecommerce-control-plane.md`](product/d2c-ecommerce-control-plane.md)
3. [`docs/product/d2c-control-plane-prd.md`](product/d2c-control-plane-prd.md)
4. [`docs/roadmap/d2c-control-plane-roadmap.md`](roadmap/d2c-control-plane-roadmap.md)
5. [`docs/plans/2026-05-24-d2c-control-plane-first-product.md`](plans/2026-05-24-d2c-control-plane-first-product.md)

## Architecture and contracts

- [`docs/architecture/phase-a-control-plane-contract.md`](architecture/phase-a-control-plane-contract.md)
- [`docs/adr/README.md`](adr/README.md)
- [`docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`](adr/0001-control-plane-bounded-contexts-and-module-ownership.md)
- [`docs/adr/0002-operational-case-native-issue-object.md`](adr/0002-operational-case-native-issue-object.md)
- [`docs/adr/0003-deterministic-detection-llm-explanation-boundary.md`](adr/0003-deterministic-detection-llm-explanation-boundary.md)
- [`docs/specs/compiled-runtime-contract.md`](specs/compiled-runtime-contract.md)
- [`docs/specs/connector-registry-contract.md`](specs/connector-registry-contract.md)
- [`docs/specs/metric-registry-contract.md`](specs/metric-registry-contract.md)
- [`docs/specs/operational-case-engine-contract.md`](specs/operational-case-engine-contract.md)
- [`docs/specs/d2c-case-family-catalog.md`](specs/d2c-case-family-catalog.md)
- [`docs/specs/d2c-action-key-catalog.md`](specs/d2c-action-key-catalog.md)
- [`docs/specs/d2c-operator-surface-contract.md`](specs/d2c-operator-surface-contract.md)
- [`docs/specs/internal-operator-api-contract.md`](specs/internal-operator-api-contract.md)
- [`docs/specs/run-ledger-foundation.md`](specs/run-ledger-foundation.md)
- [`docs/specs/storage-migration-contract.md`](specs/storage-migration-contract.md)
- [`docs/specs/tenant-secret-redaction-contract.md`](specs/tenant-secret-redaction-contract.md)
- [`docs/specs/testing-invariant-matrix.md`](specs/testing-invariant-matrix.md)
- [`docs/specs/integration-train-contract.md`](specs/integration-train-contract.md)

## Product and GTM

- [`docs/product/report-design.md`](product/report-design.md)
- [`docs/product/feedback-design.md`](product/feedback-design.md)
- [`docs/gtm/d2c-packaging-and-messaging.md`](gtm/d2c-packaging-and-messaging.md)
- [`docs/research/2026-05-26-product-market-intel-tiendanube-control-plane.md`](research/2026-05-26-product-market-intel-tiendanube-control-plane.md)

## Operations and autonomous workers

- [`docs/organization/d2c-autonomous-worker-addendum.md`](organization/d2c-autonomous-worker-addendum.md)
- [`docs/organization/d2c-worker-task-packets.md`](organization/d2c-worker-task-packets.md)
- [`docs/ops/d2c-pilot-readiness-checklist.md`](ops/d2c-pilot-readiness-checklist.md)
- [`docs/ops/d2c-pilot-runbook.md`](ops/d2c-pilot-runbook.md)
- [`docs/operability/worktree-hygiene.md`](operability/worktree-hygiene.md)
- [`docs/orvo-brain-runtime.md`](orvo-brain-runtime.md)

## Worker rule

If older docs conflict with the D2C wedge/platform-core decision, ADR-0005 and the Phase A architecture contract win unless a later ADR supersedes them.
