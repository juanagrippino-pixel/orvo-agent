# Gateway middleware contract

Status: first Python-runtime slice for `N2-Pro/edge-developer-platform`.

## Purpose

Orvo's operator and internal HTTP surfaces already authenticate callers and
redact secrets at route boundaries. This contract extracts the reusable
gateway-boundary rules into `app.brain.gateway_contracts` so future middleware
can enforce the same conventions without duplicating logic in Flask handlers,
connector adapters, or run-ledger code.

This slice does **not** introduce heavy infrastructure. It defines deterministic
contracts that can be wired to Flask middleware, Redis counters, SQLite audit
rows, or connector dispatch checks later.

## Contracts

### Request context

`GatewayRequestContext` is the only gateway metadata object that should be
persisted into audit, ledger, or case provenance data.

- `request_id` is generated when absent.
- Request IDs longer than 128 characters or containing secret-shaped text become
  `[REDACTED]`.
- `actor_ref` uses the existing internal operator safe-principal helper.
- `auth_scheme` returns only a safe scheme (`Bearer`, `Basic`, `Token`,
  `ApiKey`, `Api-Key`) and never stores credential tails.
- `idempotency_key` is optional for read-only paths but, when present, must be a
  short allowlisted identifier.

### Idempotency keys

Idempotency keys are not durable state yet. This contract defines their syntax so
future storage can safely key replay caches.

Allowed pattern:

```text
^[A-Za-z0-9_.:-]{1,128}$
```

Invalid keys fail closed with `GatewayContractError(code="invalid_idempotency_key")`.
Error messages are redacted and never echo the caller-supplied key.

### Authorization scheme inspection

`authorization_scheme()` is safe for audit logging only. It must not be used as
proof of authentication. Route handlers must continue to require authenticated
operator context before using the gateway context.

Credential tails such as `Bearer <token>` are discarded. If the tail is itself
secret-shaped, for example `Bearer access_token=...`, the whole header is treated
as `[REDACTED]`.

### Rate-limit decisions

`GatewayRateLimitPolicy` is allowlisted:

- `scope`: `business`, `operator`, or `connector`
- `requests_per_minute`: optional positive integer
- `retry_after_seconds`: positive integer, default `60`

`evaluate_gateway_rate_limit()` is deterministic and storage-agnostic. It accepts
a counter snapshot and returns `GatewayRateLimitDecision(allowed,
retry_after_seconds)`.

### Route policies

`GatewayRoutePolicy` ties one normalized route/method pair to gateway
expectations before a future Flask middleware delegates to business handlers:

- `idempotency_mode`: `optional`, `required`, or `forbidden`;
- `requires_business_id`: whether the normalized context must carry a business
  routing label;
- `rate_limit_policy`: optional `GatewayRateLimitPolicy` evaluated from a
  deterministic counter snapshot.

`validate_gateway_route_policy()` returns `GatewayRouteDecision(allowed,
reason, retry_after_seconds)`. Denial reasons are stable strings such as
`idempotency_key_required`, `rate_limited`, or `business_id_required`; they never
echo caller-controlled route keys or idempotency values.

### Audit provenance

`build_gateway_audit_event()` builds a redacted event envelope for gateway
boundaries. It preserves canonical route/request identifiers and redacts mutable
payload data through the existing secret redaction layer.

## Tests

- `tests/contracts/test_gateway_contracts.py`

The test suite verifies:

- request ID generation and redaction;
- idempotency key validation without echoing invalid values;
- safe authorization scheme extraction;
- redacted audit event envelopes;
- deterministic rate-limit decisions;
- route-policy enforcement for idempotency, business scoping, rate limits, and
  unsafe route-key material.

## Integration notes

Future Flask middleware should stay thin:

1. authenticate the request;
2. build `GatewayRequestContext`;
3. evaluate policy/rate-limit decisions;
4. pass only safe context fields to route handlers;
5. persist audit events through `build_gateway_audit_event()`.

Do not let transport code own connector, metric, case, or ledger business rules.
Those remain in their existing service layers.
