# Gateway policy telemetry runbook

Status: Draft operational runbook  
Owner component: `gateway_policy`  
Related: `docs/specs/gateway-policy-contract.md`, `docs/specs/service-catalog-contract.md`

## Purpose

This runbook explains how to inspect gateway policy decisions emitted by `app.brain.gateway_policy` without introducing external gateway, rate-limit, or telemetry infrastructure. It is the service-catalog runbook for the `gateway_policy` component and covers the current in-process Python runtime boundary.

## What the decision means

Every gateway policy evaluation returns a `GatewayPolicyDecision` with:

- `allowed`: whether the route may continue;
- `code`: deterministic decision code such as `allowed`, `permission_denied`, or `missing_idempotency_key`;
- `status_code`: HTTP status the route should project;
- `audit_event`: safe audit-shaped metadata for operator/API logs;
- `telemetry_event`: schema-versioned gateway provenance for ledgers/log correlation.

The telemetry schema is `2026-06-04.gateway-telemetry.v1`. Treat `provenance_ref` as the short correlation handle for a redacted decision payload; do not reconstruct it from raw request bodies or credential material.

## Safe inspection checklist

1. Confirm the route has a catalog entry in `service_catalog_manifest()["components"]` under `gateway_policy`.
2. Confirm the route policy exists in `default_gateway_policy_registry().route_keys()`.
3. Inspect the decision `code` and `status_code` before looking at route-specific handler behavior.
4. Use `provenance_ref`, `route_key`, `business_id`, redacted `actor_id`, `request_id`, and `trace_id` for correlation.
5. Never log or paste raw idempotency keys, authorization headers, OAuth tokens, connector credentials, or environment values.

Example safe redacted event fields:

```json
{
  "source_component": "gateway_policy",
  "route_key": "operator_api.case_action.mutate",
  "business_id": "artemea",
  "actor_id": "operator access_token=[REDACTED]",
  "decision_code": "allowed",
  "idempotency_key_present": true,
  "trace_id": "[REDACTED]",
  "provenance_ref": "gwprov_0000000000000000"
}
```

## Expected denied decisions

- `unauthenticated` (`401`): no authenticated internal principal reached the policy boundary.
- `business_scope_forbidden` (`403`): the principal is not scoped to the requested business.
- `permission_denied` (`403`): the principal lacks the route's required permission constant.
- `missing_idempotency_key` (`428`): a mutating route did not provide a key.
- `invalid_idempotency_key` (`400`): the supplied key was not business-scoped, was too large, had whitespace, or contained secret-shaped material.

## Escalation notes

- If a route mutates state but has no gateway policy or `idempotency_required=false`, block integration and add a contract test first.
- If telemetry contains an unredacted credential or raw idempotency value, treat it as a Trust/Admin blocker and add a redaction regression test before changing docs.
- If `provenance_ref` changes for identical redacted inputs, inspect `app.brain.gateway_policy._gateway_provenance_ref` and the telemetry schema version before merging.
