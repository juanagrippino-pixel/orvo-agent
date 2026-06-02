# WhatsApp Report Design v0

## Purpose

This document defines the Hito-0/Hito-1 owner-facing WhatsApp report for Orvo.

North star:

> Each morning, Orvo should tell Juan what happened yesterday and what to prioritize today, in under 30 seconds of reading.

The report is not a dashboard export and not a chatty assistant message. It should read like a dry operator who checked the systems early, found the important thing, and wrote the minimum necessary.

## Surface constraints

- Delivery surface: WhatsApp only.
- Reader: owner/operator, often on mobile, often between other tasks.
- Reading budget: ~400–700 characters on normal days, ~700–1100 on critical days.
- Interaction budget: minimal. Most days should require no reply.
- No dependency on buttons for v0. Plain text must stand on its own.

## Report goals

Every report should make these clear in order:

1. Is there a real problem or not?
2. What is the first thing to do?
3. What facts justify that?
4. Is the data complete enough to trust this?

## Core formatting rules

1. Put the most important line near the top.
2. Use short sections and hard line breaks.
3. Avoid decorative fluff and brand slogans.
4. Avoid more than 3 substantive bullets.
5. If the report is partial, say that before giving advice.
6. Use numbers sparingly; include only those that change action.
7. Show one priority, not a ranked list of six tasks.

---

## Tone guidelines

The voice should sound like a dry, direct operator. It should not sound like a coach, consultant, dashboard, or AI assistant.

### Tone characteristics

- direct
- restrained
- specific
- unemotional
- minimally interpretive
- action-oriented
- not motivational

### Good tone examples

- "Sales were 24% below the 7-day baseline. Check checkout and pending payments first."
- "Top seller is near zero stock. Stop pushing it until stock is confirmed."
- "Mercado Libre held steady. Tiendanube dropped. Review the storefront before changing spend."
- "Inventory sync is stale. Stock advice omitted today."

### Bad tone examples

- "Good morning Juan! Here are your exciting insights for today ✨"
- "I noticed an incredible opportunity to optimize your business performance."
- "It seems customers may be feeling less engaged with your brand story."
- "Based on my analysis, I would recommend a holistic review of your funnel."

### Preferred language patterns

- "Check"
- "Review"
- "Pause"
- "Reply first"
- "Hold"
- "Likely"
- "Omitted"
- "No urgent issue"

### Avoid

- anthropomorphic phrases like "I think" / "I noticed"
- hype like "huge opportunity"
- hedging filler like "it may be worth considering"
- generic consultant language like "optimize", unless tied to a concrete action
- false certainty on causes

---

## Report content model

Every report should be assembled from these blocks.

### Block 1: header

Purpose: orient quickly without wasting space.

Recommended shape:

- `ARTEMEA · 2026-05-21`
- optional state tag if degraded: `ARTEMEA · 2026-05-21 · partial`

Avoid heavy branding at the top. In the owner flow, the sender identity already tells Juan this is Orvo.

### Block 2: top line / primary priority

This is the single most important line in the report.

Examples:

- `Priority: check checkout first.`
- `Priority: pause ads to low-stock products.`
- `Priority: clear aged orders before pushing more volume.`
- `Priority: no urgent issue today.`

This line should answer "what do I do first?" even if Juan only reads one line.

### Block 3: critical finding or daily summary

One or two lines that explain what changed.

Examples:

- `Sales were 31% below the recent baseline while ad spend stayed active.`
- `Top seller moved 11 units yesterday and has 3 left.`
- `No critical issue. Revenue was flat vs baseline and backlog stayed normal.`

### Block 4: supporting facts

Short bullet list with only action-relevant numbers.

Examples:

- `- Revenue: ARS 418k vs ARS 603k baseline`
- `- Pending payments: 14 vs 5 baseline`
- `- Stock, Vestido Lino Negro: 3 units`

### Block 5: optional secondary item

Used only if there is a clearly distinct second issue.

Examples:

- `Secondary: 9 unanswered purchase chats.`
- `Secondary: ML held steady while TN fell.`

### Block 6: source/data health footer

Very short.

Examples:

- `Sources: Tiendanube, Meta Ads`
- `Sources: Tiendanube only`
- `Inventory stale since 06:10. Stock advice omitted.`

---

## Report design options

v0 should test multiple formatting shapes. All options below assume the same underlying insight selection logic.

## Option A — Priority-first operator brief (recommended default)

This is the strongest default for Hito-0.

### Format

```text
ARTEMEA · 2026-05-21
Priority: check checkout first.

Sales were 31% below the 7-day baseline while ad spend stayed active.
- Revenue: ARS 418k vs ARS 603k
- Orders: 7 vs 12 baseline
- Pending payments: 14 vs 5

Secondary: 8 unanswered chats.
Sources: Tiendanube, Meta Ads, WhatsApp
```

### Why it works

- Priority is visible immediately.
- Reads like an operator note, not a report dump.
- Facts support the action without overloading.
- Easy to adapt for normal and critical days.

### Weaknesses

- Less explicit structure for multiple issues.
- Some owners may want a clearer split between "what happened" and "what to do."

## Option B — Situation / action split

Useful if Juan responds better to a more procedural format.

### Format

```text
ARTEMEA · 2026-05-21
Situation:
Sales were 31% below baseline. Spend stayed active and pending payments jumped.

Action:
Check checkout and payment methods first. Hold ad changes until checkout is tested.

Facts:
- Revenue: ARS 418k vs ARS 603k
- Orders: 7 vs 12
- Pending payments: 14 vs 5
```

### Why it works

- Very clear separation between diagnosis and action.
- Reduces risk that Juan sees numbers but misses the recommendation.

### Weaknesses

- Slightly more verbose.
- Feels a bit more templated and less like a terse morning brief.

## Option C — Alert ledger

This is useful on rougher days with two or three serious items.

### Format

```text
ARTEMEA · 2026-05-21
Main issue: top seller low on stock.

1) Vestido Lino Negro sold 11 units yesterday and has 3 left.
   Action: stop pushing it until stock is confirmed.

2) 9 purchase chats are unanswered.
   Action: reply to those first.

Sources: Tiendanube, WhatsApp
```

### Why it works

- Handles multiple issues cleanly.
- Easy for scanning.

### Weaknesses

- Less elegant on normal days.
- Risks feeling like a ticket list.

## Option D — Narrative mini-brief

This is the most natural-language option, but should be used carefully.

### Format

```text
ARTEMEA · 2026-05-21
Yesterday was soft. Sales fell below the recent baseline and the clearest problem is pending payments. Check checkout before changing campaigns.

Facts: revenue ARS 418k vs 603k baseline; orders 7 vs 12; pending payments 14 vs 5.
```

### Why it works

- Extremely compact.
- Feels human.

### Weaknesses

- Harder to scan.
- Easier to slip into AI-sounding prose.
- Less robust in degraded mode.

## Recommendation

Start with **Option A** as the default. Keep **Option C** as a fallback when there are two distinct actionable issues. Use **Option B** if early user feedback says Juan wants more explicit separation between facts and action.

---

## Critical-alert vs normal-day formatting

The visual shape should change depending on urgency.

## Critical day

Characteristics:

- problem likely requires action now
- top line must be imperative
- supporting facts should be narrow and operational
- omit nonessential positive context

### Critical-day example

```text
ARTEMEA · 2026-05-21
Priority: pause ads to the low-stock top seller.

Vestido Lino Negro sold 11 units yesterday and has 3 left.
- Stock: 3 units
- Yesterday sales: 11 units
- Ad spend still active

Secondary: TN sales were 24% below baseline.
Sources: Tiendanube, Meta Ads
```

### Critical-day rules

- lead with action, not summary
- use direct verbs
- maximum 2 issues
- no cheerful language
- if confidence is medium, use "check/review" instead of hard commands unless safety demands otherwise

## Normal day

Characteristics:

- no urgent failure
- main value is quick reassurance plus one useful observation
- should be shorter than a critical-day report

### Normal-day example

```text
ARTEMEA · 2026-05-21
Priority: no urgent issue today.

Revenue was flat vs the recent baseline and backlog stayed normal.
- Revenue: ARS 612k vs ARS 598k baseline
- Orders: 13 vs 12 baseline

Watch: 6 chats are still unanswered.
Sources: Tiendanube, WhatsApp
```

### Normal-day rules

- explicitly say no urgent issue when true
- include at most one watch item
- avoid manufacturing an action if the correct action is simply normal operation

---

## Degraded-mode variants

The report format must remain useful even when data is partial.

## Degraded mode 1 — one source missing, report still actionable

Example: ad spend missing, but Tiendanube and inventory are healthy.

```text
ARTEMEA · 2026-05-21 · partial
Priority: review low stock on the top seller.

Vestido Lino Negro has 4 units left after 9 units sold yesterday.
- Stock: 4 units
- Yesterday sales: 9 units

Ad data missing. Spend/ROAS advice omitted.
```

Rule:

- keep the report
- explicitly state what advice was omitted
- do not apologize excessively

## Degraded mode 2 — core source partial, summary-only

Example: order data incomplete or stale.

```text
ARTEMEA · 2026-05-21 · partial
Priority: no recommendation yet.

Tiendanube data is incomplete this morning, so performance comparisons are on hold.
Inventory sync is current. No stock risk flagged from available data.

Waiting on: complete order sync.
```

Rule:

- do not force comparative insights
- switch from action mode to status mode

## Degraded mode 3 — owner-safe failure message

Example: main connector failed entirely.

```text
ARTEMEA · 2026-05-21 · partial
Today’s report is on hold. Tiendanube did not sync completely, so I’m not sending recommendations on partial data.
```

Rule:

- short
- honest
- no fake analysis
- internal operator should receive fuller failure details separately

---

## What should be included vs omitted

## Include

- yesterday performance vs baseline if it changes action
- counts and amounts tied to the main issue
- channel comparison if it clarifies likely root cause
- one secondary issue at most
- source or data-health note

## Omit

- every available metric
- vanity traffic stats unless tied to diagnosis
- more than one alternative action path
- internal confidence scores
- long source citation lists
- generic advice like "optimize funnel"

---

## Character budget guidance

### Normal day target

- 350–550 chars ideal
- hard cap around 700

### Critical day target

- 500–850 chars ideal
- hard cap around 1100

### Summary-only / degraded

- 180–450 chars ideal

The product should optimize for reading completion, not completeness.

---

## Formatting micro-rules

### Dates

Use ISO or short local date style consistently. Example:

- `2026-05-21`

### Currency

Use `ARS` plus rounded whole number unless cents matter, which they usually do not here.

### Baseline references

Prefer explicit comparison wording:

- `vs 7-day baseline`
- `vs recent baseline`

Not:

- `down a lot`

### Product naming

If a SKU/product name is long, shorten safely.

Example:

- `Vestido Lino Negro` instead of full verbose catalog title

### Emoji policy

Keep near-zero emoji usage. If any are used, they should encode status only and never add personality.

Preferred approach for v0:

- no emoji, or
- one status marker only in critical cases if testing shows it improves scan speed

Given the dry tone goal, the default should be **no emoji**.

---

## Feedback affordances inside WhatsApp

The report should make feedback possible without turning the report into a chat UI.

### v0 low-friction footer option

Append only on some reports or during evaluation period:

- `Reply U / N / I on any line: useful / noisy / incorrect.`

Example:

```text
Sources: Tiendanube, Meta Ads
Reply U / N / I on any line: useful / noisy / incorrect.
```

### Alternative even lighter version

- No footer on every report.
- Teach Juan once that he can reply:
  - `useful 1`
  - `noisy 2`
  - `incorrect 1`

See dedicated feedback design doc for the full system.

---

## Recommended v0 templates

## Template: critical operational issue

```text
ARTEMEA · {{date}}
Priority: {{primary_action}}.

{{main_finding_sentence}}
- {{fact_1}}
- {{fact_2}}
- {{fact_3}}

{{secondary_block_optional}}
{{sources_or_data_health}}
```

## Template: normal day

```text
ARTEMEA · {{date}}
Priority: no urgent issue today.

{{summary_sentence}}
- {{fact_1}}
- {{fact_2}}

{{watch_item_optional}}
{{sources_or_data_health}}
```

## Template: degraded partial day

```text
ARTEMEA · {{date}} · partial
Priority: {{limited_action_or_none}}.

{{partial_data_statement}}
{{safe_observation_optional}}

{{omitted_advice_statement}}
```

---

## Open questions

1. Should the owner-facing message include the word `Priority`, or is `First:` even tighter and more natural?
2. Will Juan prefer an explicit `Secondary:` line, or should secondary items be folded into one `Watch:` line?
3. Is a persistent feedback footer too noisy for a premium-feeling product, requiring onboarding/training instead?
4. Should channel names be abbreviated (`TN`, `ML`) after onboarding, or kept fully spelled out for clarity?
5. Do we want a single consistent template always, or a dynamic formatter that chooses between Option A and C based on issue count?

## Recommendation

For v0, use **Option A, no emoji, priority-first structure, explicit degraded-mode language, and a direct operator voice**. This best matches the product promise: short, useful, calm, and trustworthy.
