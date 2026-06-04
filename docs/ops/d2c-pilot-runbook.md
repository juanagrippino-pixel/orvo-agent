# D2C Pilot Runbook

Status: Draft operational runbook
Date: 2026-05-24
Related: `docs/ops/d2c-pilot-readiness-checklist.md`, `docs/specs/internal-operator-api-contract.md`

## Purpose

This runbook defines how an operator should run and inspect the first Tiendanube/WhatsApp pilot once Milestones 1-4 are implemented.

## Preflight

Before enabling daily operation:

1. Confirm pilot scope is Tiendanube/WhatsApp-first.
2. Confirm business config and timezone.
3. Confirm Tiendanube secret refs exist and are not raw in docs/config output.
4. Run compile preview.
5. Run connector readiness check.
6. Run dry run.
7. Inspect run ledger.
8. Inspect generated cases/projections.
9. Confirm WhatsApp destination and dispatch policy.
10. Confirm no-go checklist is clear.

## Daily run inspection

For each daily run, operator should answer:

- Did runtime compile successfully?
- Which connector specs ran?
- Were sources fresh, degraded, stale, unauthorized, or failed?
- Which metrics/evidence were emitted?
- Which cases opened/updated/resolved/reopened?
- What WhatsApp brief was sent or skipped?
- Were all artifacts redacted?

## Common incidents

### Tiendanube unauthorized

Expected state:

- connector health: `unauthorized`;
- `data_stale` case opened/updated;
- downstream commerce claims suppressed;
- suggested action: `refresh_credentials`.

Operator action:

1. Verify business/store scope.
2. Refresh credentials through safe secret flow.
3. Re-run readiness.
4. Run dry run before dispatch.

### Tiendanube stale

Expected state:

- connector health: `stale`;
- `data_stale` case opened/updated;
- owner-facing brief says Orvo cannot safely advise from stale source.

Operator action:

1. Check last success timestamp.
2. Retry only within rate-limit policy.
3. If still stale, notify owner with caveat rather than fabricated advice.

### Duplicate case spam

Expected state:

- repeated issue updates same case via dedupe key.

Operator action:

1. Inspect case dedupe key.
2. Verify case family policy.
3. Do not patch report copy to hide duplicates; fix case engine/dedupe.

### Unsupported owner-facing claim

Expected state:

- projection tests should reject claim.

Operator action:

1. Trace number to metric/evidence.
2. If no evidence exists, remove/suppress projection.
3. Add test so it cannot recur.

## Pilot closeout

At the end of each pilot week record:

- number of runs;
- runs degraded/stale/failed;
- cases opened/updated/resolved;
- owner replies/actions;
- unsupported-claim incidents;
- connector/credential incidents;
- product gaps blocking paid conversion.

Do not promise automation expansion until detection/evidence/follow-up loop is trusted.
