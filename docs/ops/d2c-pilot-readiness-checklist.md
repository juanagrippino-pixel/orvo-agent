# D2C Pilot Readiness Checklist

Status: Operational checklist
Date: 2026-05-24
Related: `docs/product/d2c-control-plane-prd.md`, `docs/roadmap/d2c-control-plane-roadmap.md`

## Purpose

Use this checklist before telling a real D2C store owner that Orvo is ready to operate daily.

## Data readiness

- [ ] Business config exists and is tenant-scoped.
- [ ] Tiendanube connector credentials are configured through safe secret handling.
- [ ] Connector freshness policy is configured.
- [ ] Runtime can distinguish ok, degraded, stale, unauthorized, rate-limited, and malformed states.
- [ ] Example/demo files use `[REDACTED]` or `tn_test_token`, never real tokens.

## Runtime readiness

- [ ] Preview, forced, and scheduled runs converge on compiled runtime or tested compatibility shim.
- [ ] Run ledger records run start/end.
- [ ] Connector results are recorded.
- [ ] Dispatch attempts are recorded/skipped idempotently.
- [ ] Artifacts are inspectable and redacted.
- [ ] Failures are typed and owner/operator safe.

## Case readiness

- [ ] `sales_drop` deterministic tests pass.
- [ ] `stockout_risk` deterministic tests pass.
- [ ] `data_stale` deterministic tests pass.
- [ ] Dedupe prevents daily spam.
- [ ] Evidence exists for every case.
- [ ] Case timeline records opens/updates/resolution.
- [ ] Missing/stale data suppresses or narrows downstream advice.

## Surface readiness

- [ ] WhatsApp brief uses case/evidence data, not hidden state.
- [ ] Every number in the brief is traceable.
- [ ] Degraded-source caveats are visible.
- [ ] Internal operator can inspect run history.
- [ ] Internal operator can inspect case queue/timeline.
- [ ] Manual comments/actions are audit logged if enabled.

## QA readiness

- [ ] Focused tests pass.
- [ ] `pytest -q` passes.
- [ ] `git diff --check` passes.
- [ ] Redaction tests cover credentials and URL tokens.
- [ ] Unsupported-claim tests reject LLM/projection hallucinations if any LLM projection is enabled.
- [ ] Existing Hito0/runtime behavior remains compatible.

## Customer readiness

- [ ] Pilot scope is explicitly Tiendanube/WhatsApp-first.
- [ ] Owner understands which sources are connected.
- [ ] Owner understands Orvo may say "no puedo recomendar por datos stale".
- [ ] Follow-up workflow is agreed: who receives briefs, who acts, who resolves cases.
- [ ] Pricing/trial/concierge terms are stated without unsupported guarantees.

## No-go conditions

Do not launch a live pilot if:

- raw secrets appear in artifacts/logs/docs;
- owner-facing brief can include unsupported numbers;
- stale data is silently treated as good data;
- same case repeats daily as new spam;
- operator cannot inspect why a recommendation was made;
- current scheduled/forced behavior is broken.
