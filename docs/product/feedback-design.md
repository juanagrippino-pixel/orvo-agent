# WhatsApp Insight Feedback System Design

## Purpose

This document defines the Hito-1+ feedback loop for owner-facing Orvo reports.

Goal:

- Let Juan quickly mark which insights were useful, noisy, or incorrect from WhatsApp.
- Store feedback at the insight level, not just the report level.
- Turn that signal into weekly internal summaries and bounded tuning inputs.

The feedback loop exists to improve precision and safety, not to create a chat-heavy UX.

---

## Product principles

1. **Low friction beats rich annotation.** Juan should be able to give feedback in a few seconds.
2. **Insight-level feedback is more useful than report-level sentiment.**
3. **Incorrect is a safety signal, not just a preference signal.**
4. **No direct auto-learning from one message.** Feedback should inform bounded tuning and internal review.
5. **The report should remain readable even if Juan never gives feedback.**

---

## User interaction design

There are three feedback classes Juan can send from WhatsApp:

- **Useful**: this was worth seeing
- **Noisy**: not wrong exactly, but not worth the interruption / attention
- **Incorrect**: materially wrong or based on bad assumptions/data

## Interaction model options

### Option A — line-number reply syntax (recommended)

Each actionable line in the report gets a hidden or visible ordinal in the formatter logic.

Visible format example:

```text
ARTEMEA · 2026-05-21
1. Priority: check checkout first.
2. Sales were 31% below baseline while spend stayed active.
3. Secondary: 8 unanswered chats.

Reply: useful 1 / noisy 3 / incorrect 2
```

Juan can reply with simple text:

- `useful 1`
- `noisy 3`
- `incorrect 2`
- `u 1`
- `n 3`
- `i 2`

### Why this is recommended

- specific enough to map to one insight
- easy to parse deterministically
- works in plain text without buttons
- low user education cost

### Drawback

- adds slight visual overhead if line numbers are shown

## Option B — quoted reply to message line

Juan replies to the WhatsApp message and quotes the relevant line, then adds:

- `useful`
- `noisy`
- `incorrect`

### Why it is attractive

- feels natural in WhatsApp
- no need to show indices in the main message

### Why it should not be the only v1 path

- quote parsing is less deterministic
- WhatsApp integrations may expose quoted context inconsistently
- harder to support with clean analytics

## Option C — compact footer codes

Report footer says:

- `Reply U1 / N2 / I1`

This is shortest, but more cryptic.

### Recommendation

Use **Option A** during Hito-1 learning period because it is easiest to operate and analyze. Once usage is habitual, the visible syntax can be shortened.

---

## Which parts of the report are feedback-eligible

Not every line needs feedback.

### Feedback-eligible items

- primary insight / priority
- each secondary insight
- degraded-mode data-health message if owner-facing

### Not feedback-eligible by default

- header/date
- source footer
- raw supporting fact bullets, unless they are bundled into a given insight

A single insight instance may render as multiple lines, but should have one feedback target.

---

## Message design for feedback

The feedback affordance should be light.

### Early rollout version

Append a footer on all reports:

```text
Reply: useful 1 / noisy 2 / incorrect 1
```

### Mature version

Only show footer:

- during onboarding weeks
- when a new insight family appears
- after critical alerts
- on evaluation campaigns

This reduces clutter once Juan already knows the pattern.

---

## Parsing rules

The parser should accept a small set of deterministic forms.

### Accepted labels

- `useful`, `u`
- `noisy`, `n`
- `incorrect`, `i`, `wrong`

### Accepted formats

- `useful 1`
- `u1`
- `u 1`
- `incorrect 2 bad stock data`
- `noisy 3 already knew`
- `u 1, n 3`

### Parser behavior

1. normalize casing and accents
2. split into feedback tokens
3. map token to label + ordinal
4. attach optional trailing note
5. reject ambiguous ordinals
6. send a brief clarification message only if parsing fails

### Example clarification message

- `Couldn’t map that feedback. Reply like: useful 1 / noisy 2 / incorrect 1.`

Keep clarification sparse to avoid turning the owner flow into support.

---

## Feedback storage design

Feedback must be stored against the exact generated insight instance, not just the generic insight type.

## Why instance-level storage matters

Because these are different questions:

- Was `stockout_risk_top_sku` generally useful as a class?
- Was **this** stockout warning on **this day** useful?

We need both.

## Proposed storage layers

### Layer 1: report run

Table: `report_runs`

Suggested fields:

- `id`
- `business_id`
- `report_date`
- `sent_at`
- `report_state` (`full`, `partial`, `summary_only`, `failed`)
- `template_version` (`report_v0_option_a`, etc.)
- `char_count`
- `raw_message_text`
- `data_health_json`

### Layer 2: insight instance

Table: `insight_instances`

Suggested fields:

- `id`
- `report_run_id`
- `business_id`
- `ordinal` (1, 2, 3 in the rendered report)
- `insight_type`
- `severity`
- `priority_score`
- `confidence_level`
- `rendered_title`
- `rendered_body`
- `recommended_action`
- `evidence_json`
- `suppressed` (bool, mainly for internal eval storage)
- `source_metric_snapshot_json`

### Layer 3: owner feedback event

Table: `insight_feedback_events`

Suggested fields:

- `id`
- `business_id`
- `report_run_id`
- `insight_instance_id`
- `channel_message_id`
- `owner_phone`
- `label` (`useful`, `noisy`, `incorrect`)
- `free_text_note`
- `received_at`
- `parse_version`
- `raw_inbound_text`

### Layer 4: internal review / resolution

Table: `insight_feedback_reviews`

Suggested fields:

- `id`
- `feedback_event_id`
- `status` (`new`, `triaged`, `reviewed`, `closed`)
- `reviewer`
- `resolution_type` (`threshold_issue`, `data_issue`, `rule_bug`, `owner_preference`, `no_action`)
- `resolution_note`
- `created_at`
- `updated_at`

---

## Business logic on feedback ingestion

## Useful

What it means:

- owner found this worth seeing

What to do:

- increment usefulness counters for that insight type and business
- optionally reduce suppression pressure for that type
- no urgent internal action needed

## Noisy

What it means:

- owner does not think this crossed the threshold for interruption
- may still be factually correct

What to do:

- increment noise counters
- if repeated for same business and insight type, consider threshold increase or persistence requirement
- include in weekly tuning summary

## Incorrect

What it means:

- factual error, wrong diagnosis, or bad recommendation

What to do:

- create high-priority internal review item
- preserve full evidence snapshot
- avoid automatic threshold-only treatment
- track whether error root cause was data, rule, formatting, or ambiguity

Incorrect feedback should be treated as a product-quality incident, even when small.

---

## Derived aggregates for tuning

The system should periodically compute aggregates at two levels.

## By business + insight type

Example fields:

- `useful_count_28d`
- `noisy_count_28d`
- `incorrect_count_28d`
- `last_feedback_at`
- `suppression_bias`
- `threshold_adjustment_recommendation`

This supports ARTEMEA-specific tuning.

## Global by insight type

Example fields:

- `reports_shown_28d`
- `feedback_rate_28d`
- `useful_rate_28d`
- `noise_rate_28d`
- `incorrect_rate_28d`
- `incorrect_rate_when_confidence_medium`
- `incorrect_rate_by_data_state`

This supports product learning across businesses later.

---

## Weekly internal summary design

The weekly summary is for Orvo internal operators, not Juan.

Goal:

- identify insight classes that are helping
- spot safety issues early
- decide what to tune next week

## Audience

- founder/operator
- product/engineering
- whoever reviews owner feedback and report quality

## Cadence

- weekly, once per business
- optional global rollup across all businesses later

## Weekly summary structure

### Section 1: top-line business feedback stats

Example:

- Reports sent: 7
- Feedback events: 5
- Useful: 3
- Noisy: 1
- Incorrect: 1
- Feedback rate: 71%

### Section 2: useful insights this week

List the insight types and exact instances Juan marked useful.

Example:

- `stockout_risk_top_sku` — marked useful twice
- `support_backlog_high_intent` — marked useful once

Why this matters:

- tells us what is actually earning attention

### Section 3: noisy insights this week

Example:

- `revenue_down_vs_baseline` — noisy on two mild days
- likely issue: threshold too sensitive or not enough persistence

Expected operator question:

- should this insight require a larger drop or 2-day persistence for ARTEMEA?

### Section 4: incorrect insights this week

This is the most important section.

For each incorrect event, include:

- date
- rendered line
- insight type
- evidence snapshot summary
- owner note if present
- suspected root cause
- current status

Example:

- `2026-05-21` — "Pause ads to low-stock products"
- owner note: "stock was already replenished before noon"
- likely root cause: inventory freshness lag
- action: tighten freshness gating for stock-based directives

### Section 5: tuning recommendations

This section should be generated for internal review, not auto-applied blindly.

Examples:

- raise mild revenue-drop alert threshold from 15% to 22% for ARTEMEA
- require 2-day persistence for support backlog warnings unless backlog > 12
- suppress channel-mix notes on days with low absolute order count
- hold stock directives when inventory sync is older than 2 hours

### Section 6: open issues

Track unresolved product problems.

Examples:

- pending-payments field reliability still unclear
- no SKU-level mapping from Meta Ads to product catalog yet
- ML/TN comparison useful but still coarse

---

## Weekly summary output format

This can be stored as both structured data and a human-readable markdown artifact.

### Example markdown skeleton

```text
# ARTEMEA weekly insight feedback summary
Week: 2026-05-18 to 2026-05-24

## Stats
- Reports sent: 7
- Feedback events: 5
- Useful: 3
- Noisy: 1
- Incorrect: 1

## Most useful
- stockout_risk_top_sku (2)
- support_backlog_high_intent (1)

## Noisy
- revenue_down_vs_baseline (1)
  - likely too sensitive on low-volume day

## Incorrect
- 2026-05-21 · stock directive on stale inventory
  - owner note: stock was updated later
  - action: review freshness gating

## Recommended tuning
- Raise revenue-drop threshold for ARTEMEA from 15% to 20%
- Suppress stock directives when inventory sync age > 120 min

## Open review items
- Pending-payment reliability
- Ads-to-SKU mapping gap
```

---

## How feedback should affect the product

## Immediate effects

- useful: analytics only
- noisy: analytics + possible threshold recommendation
- incorrect: create internal review ticket / queue item

## Near-term bounded automation

Safe automations:

- raise threshold slightly after repeated noisy feedback
- add persistence requirement after repeated noisy feedback
- suppress low-value info notes for a specific business

Unsafe automations:

- removing an insight type globally after one noisy mark
- changing recommendation class after one incorrect mark
- lowering safety gating just because useful feedback is high

---

## Review workflow for incorrect feedback

When Juan marks an insight incorrect, internal review should classify root cause into one of these buckets:

1. **Data stale/incomplete**
2. **Metric mapping bug**
3. **Threshold too aggressive**
4. **Diagnosis overreach**
5. **Recommendation too strong**
6. **Owner misunderstood wording**
7. **Feedback itself inconsistent with source truth**

This classification matters because the fix is different in each case.

- data issue → freshness gating / connector fix
- threshold issue → business-specific tuning
- diagnosis overreach → phrasing or rule redesign
- wording issue → report formatter change

---

## Recommended rollout path

### Phase 1

- store every report run and every rendered insight instance
- support `useful/noisy/incorrect + ordinal` parsing
- create weekly markdown summary manually reviewed internally

### Phase 2

- add business-specific aggregate counters
- surface tuning recommendations automatically in internal summaries
- create internal review queue for incorrect items

### Phase 3

- add limited bounded threshold adaptation
- add report-level feedback and follow-up signal correlation
- add insight-family performance dashboards for internal team only

---

## Open questions

1. Will WhatsApp delivery infrastructure expose stable message IDs and quoted-reply metadata cleanly enough to support richer parsing later?
2. Should ordinal numbers be visible in the owner message, or only implied in a footer mapping?
3. Is `noisy` the right word for Juan, or would `not useful` feel clearer in Spanish while preserving the same internal label?
4. How often will Juan realistically send feedback without periodic prompting?
5. Should incorrect feedback immediately pause similar insight classes for that business until reviewed, or only flag them internally?

## Recommendation

For Hito-1, implement **ordinal-based WhatsApp feedback (`useful/noisy/incorrect + number`), instance-level feedback storage, and a weekly internal markdown summary with explicit tuning recommendations and incorrect-insight review items**. This gives Orvo a practical learning loop without adding UI surface area or unsafe auto-learning.
