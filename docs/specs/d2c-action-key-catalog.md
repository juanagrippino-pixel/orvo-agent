# D2C Action Key Catalog

Status: Draft contract
Date: 2026-05-24
Related: `docs/specs/d2c-operator-surface-contract.md`, `docs/specs/d2c-case-family-catalog.md`

## Purpose

This catalog defines the stable action keys that WhatsApp/operator projections may suggest or request. Copy/LLM layers may rephrase these actions, but must not invent new actions or imply execution without case/action governance.

## Global rule

Owner-facing WhatsApp/operator projections may only render suggested actions from registered action keys attached to the case family or case policy. LLM/copy layers may rephrase allowed actions but must not invent new actions, imply an action was executed, or bypass case/action audit.

## Core action keys

| Action key | Meaning | Initial execution mode |
| --- | --- | --- |
| `acknowledge_case` | Human/operator confirms the case was seen. | Manual/operator mutation |
| `assign_owner` | Assign a human/operator/business owner to follow up. | Manual/operator mutation |
| `add_comment` | Append a note to the case timeline. | Manual/operator mutation |
| `request_follow_up` | Ask an operator or owner to follow up. | Manual/operator action |
| `mark_in_progress` | Mark active investigation or work. | Manual/operator mutation |
| `resolve_case` | Resolve with reason and evidence/status. | Manual/operator mutation or deterministic policy when safe |
| `dismiss_case` | Dismiss as not relevant with reason. | Manual/operator mutation |
| `request_external_action` | Request an external side effect. | Approval-required; disabled by default |

## D2C suggested action keys

| Action key | Case families | Meaning | Notes |
| --- | --- | --- | --- |
| `check_storefront` | `sales_drop`, `spend_without_orders` | Inspect storefront/checkout availability. | Suggestion only until integrations prove status. |
| `review_campaigns` | `spend_without_orders` | Review active ad campaigns/spend. | `channel_mix_shift` remains deferred until registry-backed channel metrics exist. |
| `confirm_stock` | `stockout_risk` | Confirm physical/system stock. | No automatic stock mutation. |
| `pause_promotion` | `stockout_risk`, `spend_without_orders` | Consider pausing promotion/spend. | Must be phrased as recommendation unless approved automation exists. |
| `refresh_credentials` | `data_stale` | Refresh/reconnect credentials. | Do not expose token details. |
| `retry_connector` | `data_stale` | Retry a connector after transient failure. | Runtime-controlled; respect rate limits. |
| `inspect_pending_orders` | `fulfillment_backlog` | Review aging/unfulfilled orders. | Order refs must be safe/redacted. |
| `reply_pending_chats` | `unanswered_conversations` | Reply or route pending chats. | Requires support/WhatsApp data freshness. |

## Projection requirements

A projected action must include:

- `action_key` from this catalog;
- `case_id` or case-family policy allowing it;
- human label;
- whether it is suggestion-only, manual, approval-required, or executable;
- evidence/caveat when the action depends on source freshness.

Example:

```json
{
  "case_id": "case_123",
  "action_key": "confirm_stock",
  "label": "Confirmar stock físico antes de seguir promocionando",
  "mode": "manual",
  "evidence_refs": ["artifact_456:metric:stock_units"]
}
```

## Forbidden action behavior

- Do not auto-execute external actions from owner-facing text.
- Do not present suggestions as completed actions.
- Do not use actions from stale source data without caveat.
- Do not let an LLM invent action keys.
- Do not create one-off action strings in report templates; register them here first.
