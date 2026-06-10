# Connector Provisioning Contract

Status: draft
Owner: Edge / Developer Platform
Source of truth: `app.brain.connector_provisioning`
Contract tests: `tests/contracts/test_connector_provisioning_contract.py`

## Purpose

Self-service connector setup must use the same registry and runtime contracts as
compiled execution. This contract defines the first Python-runtime slice for
turning an operator/developer request into a deterministic, redacted provisioning
plan without introducing a broker, gateway mesh, identity provider, or external
secret service before Orvo's runtime contracts require them.

The contract is inspired by broker/control-plane developer-platform patterns, but
it remains intentionally local and deterministic:

- adapter behavior and requirements come from `app.brain.connector_registry`;
- public connector config lives in `params`;
- credential material is represented only by opaque `secret://` references in
  `secret_refs`;
- the provisioning compiler has no persistence, adapter-execution, or deployment
  side effects;
- the returned manifest is safe to project through internal operator/developer
  surfaces after boundary redaction.

## Schema

`ConnectorProvisioningRequest` accepts:

- `business_id`: scoped business identifier;
- `connector_id`: durable connector identifier to provision;
- `connector_type`: registered connector type, for example `tiendanube`;
- `label`: human-facing connector label;
- `params`: public, non-secret connector configuration;
- `secret_refs`: mapping of required secret names to opaque `secret://` handles;
- `actor_id`: authenticated actor identity from the operator/developer context;
- `strict`: defaults to `true` so unknown config fields are rejected.

`compile_connector_provisioning_plan(...)` returns a `ConnectorProvisioningPlan`
with schema version `2026-06-07.connector-provisioning.v1`, operation
`connector.provision`, a deterministic `operation_ref`, a boolean `ok`, an
explicit `next_step`, a redacted connector manifest, validation issues, and a
redacted audit event that carries the same `operation_ref` for future broker,
ledger, or status polling correlation.

## Validation rules

The provisioning compiler MUST:

1. resolve connector metadata through `default_connector_registry()` or an
   injected `ConnectorRegistry`;
2. reject unknown connector types with `unknown_connector_type`;
3. reuse `ConnectorRegistry.validate_control_plane_config(...)` for required
   public params, required secret refs, and strict unknown-field checks;
4. reject secret-shaped keys in `params` with `secret_param_not_allowed`;
5. reject non-`secret://` values in `secret_refs` with `invalid_secret_ref`;
6. include registry warnings such as `legacy_inline_secret` in the issue stream;
7. treat any issue as blocking for self-service provisioning until the request is
   corrected;
8. compute a stable `connprov_<hash>` `operation_ref` from redacted provisioning
   intent so repeated validation can be correlated without storing raw secrets;
9. never echo raw secret values in the plan, public manifest, validation issues,
   or audit event.

## Redaction and secret boundary

Provisioning manifests may expose secret-reference names and safe opaque
`secret://` handles. They must not expose raw token/password/API-key values.
Non-reference values under `secret_refs` are rendered as `[REDACTED]`. Secret-key
shaped params such as `access_token`, `api_key`, or `password` are rendered as
`[REDACTED]` and are invalid for provisioning even if current legacy adapters
still accept inline execution secrets through compatibility paths.

## Non-goals for this slice

This slice does not:

- persist connector config;
- create or rotate secrets;
- resolve `secret://` handles;
- call connector adapters;
- create run-ledger rows;
- perform RBAC decisions;
- introduce external brokers, service meshes, identity providers, or metrics
  infrastructure.

Those concerns remain future wiring around this contract and must preserve the
compiled-runtime and connector-registry source-of-truth boundaries.

## Service catalog

The component is registered as `connector_provisioning` in the service catalog
with dependencies on `connector_registry`, `compiled_runtime`, and `run_ledger`.
The run-ledger dependency is architectural/audit-facing: this validation slice is
side-effect free, but future config persistence and provisioning execution must
record durable audit/provenance outcomes rather than relying on gateway text or
WhatsApp reports as source of truth.

## Acceptance checks

- A valid Tiendanube provisioning request with `store_id` and
  `secret_refs.access_token = secret://...` returns `ok=true`, a stable
  `connprov_...` `operation_ref`, and `next_step=ready_for_config_save`.
- The same redacted provisioning intent yields the same `operation_ref`; changed
  public config yields a different one.
- Raw inline credential params and non-reference secret values are rejected and
  redacted.
- Missing required params and strict unknown fields are reported by reusing the
  connector registry diagnostics.
- The service catalog includes `connector_provisioning` and points to this spec
  and its contract tests.
