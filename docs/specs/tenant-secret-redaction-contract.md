# Tenant, Secret Reference, and Redaction Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `CLAUDE.md`, `docs/specs/compiled-runtime-contract.md`, `docs/specs/internal-operator-api-contract.md`

## Purpose

This contract prevents Orvo from leaking credentials, confusing tenants/businesses, or exposing unsafe runtime artifacts while building the D2C control plane.

## Tenant/business scope

Minimum scoping fields for new platform records:

- `tenant_id` when multi-tenant context exists;
- `business_id` always;
- `actor_ref` for mutating operator actions;
- `run_id` for runtime artifacts;
- `case_id` for case/action/timeline state.

Until full multi-tenant auth exists, internal tools must still pass explicit `business_id` and avoid global mutations by default.

## Secret refs

Raw secrets may live only in configured secret storage/environment, never in compiled runtime artifacts, run ledger payloads, docs, examples, HTTP responses, or case evidence.

Secret reference shape:

```python
class SecretRef(BaseModel):
    ref: str                 # e.g. secret://business/artemea/tiendanube/access_token
    kind: str                # access_token, refresh_token, api_key, webhook_secret
    owner_scope: str         # business or platform
    connector_type: str | None = None
    display_hint: str | None = None  # redacted suffix/label only
```

Allowed display:

```text
secret://business/artemea/tiendanube/access_token (...7f2a)
```

Forbidden display:

```text
access_token=real_value
https://api.example.com?token=real_value
[REDACTED_PRIVATE_KEY_BLOCK]
```

## Legacy connector config migration

Existing `ConnectorConfig.params` may temporarily contain legacy secret keys such as `access_token` while the repo migrates to secret refs. New runtime/compiler/ledger code must treat those values as secret-resolution inputs only.

Rules:

- compiled runtimes, run ledgers, artifacts, operator API responses, docs, examples, worker summaries, and test golden output must never serialize raw legacy secret param values;
- compiler/registry code must convert legacy secret params to stable `SecretRef` labels, or fail closed when a live secret is required and no safe ref/resolution path exists;
- runtime hashes may include the secret ref identity/version, not the raw secret value;
- new examples/config docs should prefer `secret_ref` fields; compatibility tests may use fake values such as `tn_test_token`;
- a follow-up migration must move persisted legacy raw tokens out of business config into configured secret storage.

## Redaction policy

All artifacts exposed to operators/workers must be sanitized for:

- access tokens;
- refresh tokens;
- API keys;
- OAuth codes;
- service-account private keys;
- bearer headers;
- URL query tokens;
- phone numbers beyond safe display when not operationally required;
- customer names/emails/addresses unless explicitly needed and scoped.

Replacement markers:

- `[REDACTED_SECRET]`
- `[REDACTED_TOKEN]`
- `[REDACTED_URL_TOKEN]`
- `[REDACTED_PII]`

## Operator API response rules

Operator/API/runtime-preview responses must:

- include connector health state;
- include secret ref labels only;
- include artifact refs, not raw private payloads by default;
- include degraded caveats;
- never include raw credential material.

## Logging rules

- Structured logs must log IDs/status/classes, not secret values.
- Exception messages from third-party clients must be sanitized before persistence.
- Failed HTTP URLs must strip query strings unless allowlisted.
- Debug mode must not bypass redaction in persisted artifacts.

## Required tests

- compiled runtime serialization contains no test secret values;
- run ledger artifacts redact bearer tokens and URL token params;
- connector error redaction handles common exception strings;
- operator API preview response exposes secret refs but no raw values;
- docs/examples contain only `[REDACTED]`, `tn_test_token`, or fake values;
- business-scoped operations cannot read another business's run/case by default.
