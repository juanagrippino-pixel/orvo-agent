# Architecture Review — Semantic Registry + Connector Platform

Date: 2026-06-15
Reviewed HEAD: `5d1a947d`
Branch: `feat/orvo-brain-control-plane`
Scope: read-only review of metric semantic ownership and connector platform separation.

## Verdict
**Good foundation, but enforcement needs to become universal.**
The semantic registry is already the right canonical source for metric identity, aliases, source compatibility, freshness, and case/report eligibility. Connector metadata is also moving in the right direction by validating emitted metrics against the registry.

## What is aligned
- `MetricDefinition` is the canonical semantic unit and includes `family`, `unit`, `aggregation`, `freshness_required`, `report_allowed`, `case_allowed`, `evidence_required`, `pii_class`, and `allowed_sources` (`app/brain/semantics/metric_registry.py:62-76`).
- `MetricRegistry` owns canonical key resolution and alias mapping (`app/brain/semantics/metric_registry.py:109-151`).
- Strict validation exists and can fail fast on unknown metric keys (`app/brain/semantics/metric_registry.py:1662-1683`).
- Object-level validators exist for reports, cases, and surfaces (`app/brain/semantics/metric_registry.py:1242-1498`).
- `ConnectorSpec` captures connector metadata and can load report factories (`app/brain/connector_registry.py:275-351`).
- `ConnectorRegistry` validates control-plane config and emitted metrics against the semantic registry (`app/brain/connector_registry.py:479-600`, `app/brain/connector_registry.py:775-819`).
- Connector parameter validation intentionally avoids logging credentials (`app/brain/connector_registry.py:753-772`).

## Gaps / needs work
- **Enforcement is not universal yet.** Some paths still appear advisory or partially enforced, which leaves room for metric drift at the surface layer.
- **Connector platform separation is still emerging.** The registry/spec layer is clear, but adapter/service/storage boundaries are not yet cleanly isolated across the runtime and pipeline.
- **Storage and service responsibilities are still blended.** Connectors currently carry enough responsibility that future platform growth could blur the line between adapter behavior and orchestration.
- **No explicit source-of-truth policy.** The registry is canonical in practice, but the system would benefit from a hard policy that all emitted metrics and surface projections must pass through registry validation before persistence or reporting.

## Branch readiness
- **Merge-ready:** the semantic registry itself is strong and should remain the canonical source of truth.
- **Needs work:** connector-platform branches should be merged only after rebase and after making the adapter/service/storage boundaries more explicit.

## Notes
- No code changes were made.
- `pytest -q` passed on this HEAD.
