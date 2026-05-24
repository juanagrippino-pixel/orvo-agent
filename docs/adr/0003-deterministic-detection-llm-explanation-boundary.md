# ADR-0003: Deterministic detection vs LLM explanation boundary

Status: Proposed
Date: 2026-05-24

## Context

Orvo's trust rule predates the control-plane pivot: calculations must come from deterministic code; LLMs may help explain but must not invent business data.

Current repo grounding:

- `app/brain/adapters/*` convert external systems/files into `DailyReport` metrics with `Evidence`.
- `app/brain/insights.py` generates deterministic insights from metrics and thresholds.
- `app/brain/reporting.py` renders deterministic WhatsApp report text from `DailyReport`.
- `app/brain/pipeline.py` merges connector reports, regenerates insights, and dispatches a report.
- `app/brain/dispatch.py` performs deterministic idempotency and send behavior.
- `app/graph.py`, `app/prompts.py`, and the sales/webhook path can use language-model behavior for conversation, but the Brain reporting path must not depend on LLM-created numbers.
- `docs/insight-engine/v1-design.md` explicitly requires evidence-backed insights, clear separation of observation/diagnosis/action, suppression of weak advice, and degraded-mode honesty.

The Atlassian-style control plane increases the risk of boundary drift: workers may be tempted to use LLMs for ranking, root cause, action selection, report wording, case creation, or operator summaries. The boundary must be explicit before adding case engine and automation.

## Decision

All business-state detection, case creation, case priority, lifecycle transitions, metric calculations, dedupe, degraded-mode decisions, and delivery/idempotency decisions must be deterministic and auditable.

LLMs may only operate in explanation/projection roles after deterministic state exists, and their output must be constrained by cited input data.

## Boundary contract

### Deterministic side

The deterministic side owns:

- Connector execution and error classification.
- Canonical metric extraction and metric key assignment.
- Evidence and artifact lineage.
- Metric registry validation.
- Threshold evaluation.
- Detection rules.
- Case candidate creation.
- Case dedupe/reopen/priority/status transitions.
- Degraded-mode classification.
- Report/case queue selection.
- Dispatch idempotency.
- Audit/run ledger writes.

Examples in current repo:

- `app/brain/adapters/tiendanube.py` must deterministically emit commerce metrics or typed connector failures.
- `app/brain/adapters/meta_ads.py` must deterministically emit ad metrics or typed connector failures.
- `app/brain/insights.py` must deterministically decide whether a revenue, stock, conversation, ROAS, or channel-mix finding exists.
- `app/brain/pipeline.py` must deterministically merge reports and evidence.
- `app/brain/dispatch.py` must deterministically decide whether a message is duplicate or should be sent.

### LLM-permitted side

An LLM may be used only for bounded explanation/projection tasks such as:

- Rephrasing an already-created case into owner-friendly Spanish.
- Drafting an operator-facing summary from a fixed list of cases and evidence.
- Explaining what a metric means in a help surface.
- Producing an alternative tone variant when the input facts and allowed claims are fixed.
- Classifying a free-form user reply into a small set of deterministic commands only if the final mutation is validated by deterministic rules.

LLM output must receive a locked payload containing allowed facts/cases/actions and must be rejected or ignored if it introduces unsupported numbers, sources, actions, or certainty.

### Forbidden LLM uses

Do not use an LLM to:

- Calculate revenue, orders, stock, ROAS, spend, conversion, baselines, deltas, freshness, or confidence.
- Decide that a case exists without a deterministic detection or operator-created event.
- Assign case priority unless the numeric score is computed by deterministic policy.
- Resolve/reopen/dismiss a case without an explicit deterministic trigger or human/operator action.
- Invent evidence, source labels, connector state, or artifact references.
- Rewrite thresholds or registry definitions at runtime.
- Decide to dispatch or suppress a customer message except through deterministic degraded-mode/report policy.
- Generate an external action request that bypasses case/action safety rules.

## Data handoff shape

Any future LLM explanation component should receive a constrained payload, not raw connector data or free-form prompts.

Minimum input shape:

```json
{
  "business_id": "artemea",
  "surface": "whatsapp_daily_summary",
  "allowed_claims": [
    {
      "claim_id": "case-123:summary",
      "text": "Meta Ads spent ARS 1500 and Tiendanube reported 0 orders for 2026-05-19.",
      "evidence_refs": ["run-456:metric:ad_spend_today", "run-456:metric:orders_today"]
    }
  ],
  "allowed_actions": ["check_checkout", "review_campaigns"],
  "forbidden_claims": ["root_cause_certainty", "uncited_numbers", "irreversible_action"],
  "tone": "concise_operator_spanish"
}
```

Minimum output shape:

```json
{
  "text": "...",
  "used_claim_ids": ["case-123:summary"],
  "suggested_action_keys": ["check_checkout"]
}
```

Deterministic validation must check:

- all numbers in `text` are present in allowed claims,
- all cited claim IDs exist,
- action keys are from `allowed_actions`,
- no forbidden claim class appears,
- output length and surface policy are satisfied.

## Migration from current deterministic reporting

Phase A should keep `app/brain/reporting.py` as the default owner-facing renderer. If an LLM explainer is introduced later, it must be additive and behind a feature flag or explicit surface selection.

Recommended order:

1. Keep deterministic report rendering and existing tests green.
2. Add metric registry and case engine contracts.
3. Add run ledger/artifact references so explanations can cite stable facts.
4. Add LLM explanation as optional projection from cases, never as detector.
5. Add validation tests that intentionally feed the explainer unsupported numbers/actions and assert rejection.

## Consequences

### Positive

- Trust remains anchored in source-cited metrics.
- Case lifecycle is reproducible and auditable.
- Operators can inspect why Orvo opened or prioritized a case.
- The product can still use LLMs where they help: concise language and UX, not business truth.

### Negative / costs

- Some natural-language outputs will feel less flexible until a validated explainer exists.
- Detection/ranking improvements require explicit rule/registry work instead of quick prompt edits.
- Explanation validation adds another contract-test surface.

## Invariants for future workers

1. Every owner-facing number must be traceable to `Metric`/registry evidence or a run artifact.
2. Every case must be created by deterministic detection, connector/runtime event, or explicit human/operator action.
3. Every case priority and status transition must be reproducible from stored state and policy.
4. LLM-generated text must be treated as a projection artifact, not source-of-truth state.
5. If deterministic validation cannot prove an LLM claim is supported, the claim must be suppressed.
6. Degraded-mode honesty is mandatory: missing/stale connector data must narrow or suppress advice rather than be filled in by language.
7. Existing non-LLM Hito0 flows remain the compatibility baseline during migration.
