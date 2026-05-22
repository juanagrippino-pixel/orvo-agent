# Orvo Insight Engine v1 Design

## Purpose

This document defines the Hito-0 and Hito-1 product-intelligence layer for Orvo Brain.

North star:

> Each morning, Orvo should tell the owner of ARTEMEA what happened yesterday and what to prioritize today, in under 30 seconds of reading, with reliable data and enough judgment to act.

This is not a generic BI system and not an open-ended "AI analyst." It is a narrow operational assistant for a physical-product D2C owner, starting Tiendanube-first, WhatsApp-first, with Mercado Libre added later.

The system should answer four questions every morning:

1. What materially changed yesterday?
2. What is broken or at risk right now?
3. What should Juan do first today?
4. How confident is Orvo in that advice?

## Scope and non-goals

### In scope for Hito-0

- Deterministic daily insights from reliable operational metrics.
- Tiendanube-first metrics and rules.
- WhatsApp report output.
- Clear prioritization between issues.
- Conservative recommended actions.
- Basic feedback capture on whether insights were useful/noisy/incorrect.

### In scope for Hito-1

- Better prioritization across multiple insights.
- Recommendation logic that uses context, not just thresholds.
- Data-quality-aware degraded mode.
- Feedback-informed tuning.
- Weekly internal summaries for Orvo operators.
- Mercado Libre support as an additive channel, not a redesign.

### Explicitly out of scope for now

- A dashboard.
- Free-form exploratory analytics.
- Multi-tenant abstraction-heavy design docs.
- Full causal attribution or MMM.
- Autonomous action-taking like pausing ads or editing listings.
- Financial advice that depends on cost/margin data we do not yet have.

---

## Product principles

1. **Reliable before clever.** A blunter true insight is better than a sophisticated wrong one.
2. **Operational before strategic.** Focus on issues Juan can act on today.
3. **Evidence-backed only.** Every insight must point to concrete source metrics.
4. **Short reading budget.** A normal daily report should be readable in 20–30 seconds.
5. **One priority, not five priorities.** Reports may mention multiple issues, but should identify the first thing to do.
6. **Dry operator tone.** More "checkout likely broken" and less "here’s an exciting opportunity." 
7. **Conservative recommendations.** Never recommend irreversible or high-cost action on weak evidence.
8. **Degrade honestly.** If data is missing or stale, say so and narrow the advice.

---

## Operational model

The insight engine should reason over a canonical operational model, even if v1 implementation still uses flattened metrics.

### Core entities

- **Orders**
  - order count
  - gross revenue
  - AOV
  - cancelled order count
  - pending payment count
  - payment-approved count
  - orders by product / SKU
  - orders by channel
- **Products / inventory**
  - stock on hand
  - stock reserved / committed if available
  - products with zero stock
  - products below threshold
  - top sellers by units / revenue
- **Catalog / storefront health**
  - active products
  - hidden / unpublished products if available
  - price changes if available
  - checkout and payment health proxies
- **Fulfillment / post-purchase**
  - unfulfilled orders
  - aged unfulfilled orders
  - shipment delays if available
  - return / refund proxies if available later
- **Demand / traffic proxies**
  - sessions if available
  - add-to-cart if available later
  - conversation volume
  - unanswered conversations
- **Paid acquisition**
  - ad spend
  - attributed revenue proxy
  - ROAS proxy
- **Channel mix**
  - Tiendanube revenue/orders
  - Mercado Libre revenue/orders
  - share by channel
- **Data health**
  - freshness of each source
  - completeness of required fields
  - confidence by metric family

### Time windows

Every insight should be explicit about time windows:

- **Yesterday**: default reporting window.
- **Recent baseline**: trailing 7 complete comparable days by default.
- **Trend window**: trailing 3-day or 7-day sequence for acceleration / persistence.
- **Urgency horizon**: today / 3 days / this week depending on issue type.

This avoids ambiguous language like "down" without reference period.

---

## Taxonomy of operational insights

The taxonomy should reflect how a physical-product D2C operator actually triages the business. v1 should organize insights into six families.

## 1. Revenue and order-volume anomalies

These answer: are sales materially off-pattern?

### Example insight types

- Revenue down materially vs recent baseline.
- Orders down materially vs recent baseline.
- AOV down materially while order count stable.
- Revenue up sharply but concentrated in one SKU or one channel.
- Conversion proxy failure: traffic/spend present but orders collapse.

### Why it matters

These are high-salience to the owner, but they are not always high-actionability. A generic sales dip often has weaker next actions than a concrete operational failure.

### Likely recommendations

- Check checkout/payment flow.
- Check top-selling SKUs stock.
- Check whether campaigns are active and landing on in-stock products.
- Review unanswered high-intent conversations.

### Evidence minimum

- revenue_yesterday
- revenue_baseline
- ideally orders_yesterday and orders_baseline too

## 2. Stock and catalog availability risks

These answer: are we trying to sell things we cannot fulfill?

### Example insight types

- Best-selling SKU stock below threshold.
- Best-selling SKU stockout.
- Ads active while promoted SKU stock low.
- Revenue concentrated in SKU family with less than N days of cover.
- Large share of yesterday’s demand hit low-stock products.

### Why it matters

This is one of the most operationally valuable classes for physical-product commerce because it directly affects wasted demand, ad efficiency, and customer frustration.

### Likely recommendations

- Replenish or reserve stock.
- Pause campaigns or creatives pointing to low-stock products.
- Push substitute SKUs instead.
- Move low-stock SKUs down in storefront prominence.

### Evidence minimum

- stock_on_hand by SKU
- top-selling SKU list
- yesterday units sold / orders by SKU
- optionally ad-spend or campaign mapping

## 3. Funnel and conversion failure signals

These answer: is demand present but blocked?

### Example insight types

- Ad spend with zero orders.
- Sessions up but orders down.
- Conversations up but conversions down.
- Spike in pending-payment orders.
- Checkout failure proxy: abnormal rise in carts/pending payments without approvals.

### Why it matters

These are often more actionable than a broad revenue dip because they imply a broken step, not merely weaker demand.

### Likely recommendations

- Test checkout manually.
- Verify payment methods and shipping rules.
- Verify product pages / variants / sizes are purchasable.
- Check campaign links and landing pages.

### Evidence minimum

- ad_spend and/or sessions/conversation proxies
- approved orders or placed orders
- pending payments / failed payments if available

## 4. Fulfillment and service load risks

These answer: will customer experience degrade today even if sales are fine?

### Example insight types

- Aged unfulfilled orders above threshold.
- Order backlog growing for 3 consecutive days.
- Unanswered conversations above threshold.
- Support volume spike after shipment or stock problems.
- Cancellation rate spike.

### Why it matters

This protects delivery reliability and repeat purchase health. For a small operator, backlog often becomes the real bottleneck.

### Likely recommendations

- Prioritize packing / dispatch first.
- Reply to high-intent or complaint conversations first.
- Stop pushing volume temporarily if service load is breaking.

### Evidence minimum

- open fulfillment counts with age buckets
- unanswered conversations
- cancellations / complaint proxies if available

## 5. Channel-mix and dependency risks

These answer: is the business getting distorted across channels?

### Example insight types

- Mercado Libre materially outperforming Tiendanube.
- Tiendanube drop while Mercado Libre stable, suggesting storefront-specific issue.
- Revenue concentration in one channel above threshold.
- Orders shifted from owned channel to marketplace.

### Why it matters

For ARTEMEA, Tiendanube is strategically preferable to marketplace dependence, but Mercado Libre can still be operationally useful. The insight engine should detect mix changes without moralizing.

### Likely recommendations

- Check Tiendanube storefront health.
- Compare prices, stock visibility, and shipping promise across channels.
- Redirect spend or merchandising to restore healthy channel mix if desired.

### Evidence minimum

- revenue/orders by channel for yesterday
- recent channel share baseline

## 6. Data-quality and observability insights

These answer: can the rest of the report be trusted?

### Example insight types

- Tiendanube data stale since X.
- Inventory data missing for top-selling products.
- Ad spend source absent; ROAS recommendations suppressed.
- Report based on partial day or incomplete sync.

### Why it matters

Bad data should not silently produce confident advice.

### Likely recommendations

- Treat report as partial.
- Check connector credentials or sync job.
- Avoid channel/ad/stock actions dependent on missing metrics.

### Evidence minimum

- connector sync timestamps
- completeness checks
- source-specific error states

---

## Severity and prioritization model

Severity alone is not enough. v1 should distinguish between **severity**, **priority**, and **confidence**.

## Severity

Severity describes business impact if ignored.

### Critical

Use when the issue likely causes immediate lost sales, customer harm, or wasted spend.

Examples:

- Ads spending against zero orders.
- Best-seller out of stock.
- Checkout/payment likely broken.
- Large aged fulfillment backlog.

### Warning

Use when the issue is meaningful but not obviously urgent within hours.

Examples:

- Revenue 20% below baseline.
- Unanswered conversations elevated.
- ROAS below target but still positive.
- Tiendanube underperforming vs Mercado Libre.

### Info

Use for context and monitored changes, not direct alarm.

Examples:

- Revenue concentration shifted to one channel.
- Strong day driven by one product family.
- Normal day summary observations.

## Priority

Priority decides ordering in the report and the single explicit "do this first" recommendation.

Priority should be scored, not hardcoded by severity.

### Priority score components

For each candidate insight:

`priority_score = impact_score * actionability_score * confidence_score * recency_multiplier`

Where:

- **impact_score (1–5)**: estimated size of business downside/upside.
- **actionability_score (1–5)**: whether Juan can realistically act today.
- **confidence_score (0.4–1.0)**: depends on data completeness and rule specificity.
- **recency_multiplier (0.8–1.2)**: persistent/accelerating issues rank above isolated noise.

### Suggested defaults by insight family

- stockout on top seller: impact 5, actionability 5
- spend without orders: impact 5, actionability 5
- checkout/payment failure proxy: impact 5, actionability 4
- aged fulfillment backlog: impact 4, actionability 5
- unanswered conversations spike: impact 3, actionability 5
- revenue dip alone: impact 4, actionability 2
- channel-mix skew: impact 3, actionability 3
- info trend note: impact 2, actionability 2

### Tie-breaking rules

If multiple insights have similar scores, rank in this order:

1. Prevent waste or failure now.
2. Protect fulfillment / customer experience.
3. Recover conversion bottlenecks.
4. Explain performance changes.
5. Provide context.

This prevents a generic revenue dip from outranking a concrete stockout.

## Confidence

Confidence is not shown as a numeric score to Juan in v0, but it should drive suppression and phrasing.

### High confidence

- Multiple corroborating metrics.
- Fresh data.
- Strong deterministic pattern.
- Recommendation directly tied to evidence.

### Medium confidence

- Pattern is plausible but inferred from proxies.
- One key supporting metric missing.
- Recommendation should be phrased as a check, not a directive.

### Low confidence

- Data stale or partial.
- Causal leap required.
- Recommendation would be expensive or irreversible.

Low-confidence insights should usually be suppressed from owner-facing output, or rewritten as explicit data-health notes.

---

## Recommendation-generation logic

The core rule: recommendations should be generated from a constrained action library, not free-written from scratch.

## Insight object design direction

The current `Insight` model (`severity`, `title`, `explanation`, `recommended_action`, `evidence`) is adequate for Hito-0, but Hito-1 should conceptually attach richer internal fields even if not all are yet exposed:

- `insight_type`
- `entity_scope` (business / channel / SKU / order-flow)
- `severity`
- `priority_score`
- `confidence_level`
- `root_cause_hypotheses[]`
- `recommended_action_primary`
- `recommended_action_alternatives[]`
- `recommendation_rationale`
- `suppressed_reasons[]`

The report formatter can still render only a small subset.

## Recommendation generation pipeline

### Step 1: detect fact pattern

Example:

- `stock_on_hand(top_sku) <= threshold`
- `yesterday_units(top_sku) > 0`
- `ad_spend_active_for_top_sku == true`

### Step 2: assign insight type

Example:

- `stockout_risk_top_sku_with_live_demand`

### Step 3: estimate likely operational consequence

Example:

- wasted paid traffic
- failed conversion attempts
- customer disappointment / support load

### Step 4: choose action template from action library

Example action library entry:

- `pause_promo_for_low_stock_sku`
- `replenish_or_substitute_best_seller`
- `move_available_sku_up`

### Step 5: constrain by safeguards

Example:

- if ad campaign → SKU mapping is weak, do not say "pause all campaigns".
- instead say "review and pause campaigns pushing this SKU first."

### Step 6: phrase in report tone

Example:

- Bad: "A strategic opportunity exists to optimize inventory allocation."
- Good: "Top seller is close to zero stock. Stop pushing it until stock is confirmed."

## Action library design

v1 recommendations should come from a finite action library with classes like:

### Demand protection

- check checkout now
- verify payment methods
- check campaign landing links
- review top-intent unanswered messages

### Inventory protection

- replenish SKU
- pause promotion of SKU
- swap promoted SKU for in-stock substitute
- reduce storefront prominence of low-stock SKU

### Spend protection

- pause specific low-efficiency campaigns
- hold spend until checkout/stock issue is cleared
- redirect spend to in-stock best performers

### Service protection

- clear aged orders first
- reply to complaint/high-intent queue first
- slow promotion until backlog normalizes

### Data quality actions

- verify connector sync
- mark today report as partial
- suppress ad/ROAS advice until spend source is back

## Recommendation phrasing rules

Recommendations should be:

- imperative or check-first
- short
- specific to likely failure mode
- reversible where possible
- proportional to confidence

### High-confidence phrasing

- "Pause campaigns for SKU X until stock is confirmed."
- "Test checkout now. Pending payments spiked and approved orders fell."

### Medium-confidence phrasing

- "Check checkout and payment methods first. Sales dropped while traffic/spend stayed active."
- "Review whether Tiendanube has a storefront issue. Mercado Libre stayed stable."

### Low-confidence phrasing

Prefer suppression. If included:

- "Data is partial. No ad recommendation today."

---

## Safeguards against bad advice

This is the most important part of the system.

## 1. No recommendations without evidence coverage

Every owner-facing recommendation must trace to at least one direct metric and, for stronger claims, usually two or more corroborating metrics.

Examples:

- Saying "stock risk" from stock alone is acceptable.
- Saying "pause ads" should require stock risk plus a signal that ads are active or demand is being pushed.
- Saying "checkout may be broken" should require at least two of: sessions/spend present, orders down, pending payments up, approved orders down.

## 2. Separate observation from diagnosis

The engine should distinguish:

- **Observation:** "Revenue was 28% below recent baseline."
- **Diagnosis hypothesis:** "Checkout or payment flow may be the bottleneck."
- **Action:** "Test checkout first."

The owner-facing text can compress these, but the internal model should keep them distinct.

## 3. Suppress high-cost advice on weak signals

The following actions should have a higher evidence bar:

- pausing all ads
- changing pricing
- changing broad channel strategy
- large restocking recommendations
- any advice framed as root-cause certainty

When evidence is weak, downgrade to a narrower recommendation:

- "check campaigns"
- "review storefront"
- "verify payment flow"

not

- "turn everything off"

## 4. Best-seller weighting

Not all SKUs matter equally. Stock or conversion issues should be weighted by sales concentration.

Example:

- Stockout on SKU generating 25% of last 14 days revenue = likely critical.
- Stockout on long-tail SKU with no recent demand = maybe no owner-facing insight.

This reduces noise.

## 5. Persistence filter

Some anomalies should only alert if they persist or exceed a stronger threshold.

Examples:

- one soft revenue dip day should not always trigger
- one mild ROAS miss should not always trigger
- one slight conversation backlog bump should not outrank harder failures

Use one of:

- persistence across 2 of last 3 days
- stronger threshold for one-day alerts
- dampening when volatility is historically high

## 6. Data freshness gating

Recommendations should be gated by source freshness.

Examples:

- If inventory sync is stale, do not issue stock-based directives.
- If ad spend missing, suppress ROAS and spend efficiency recommendations.
- If only partial-day order data arrived, mark report partial and suppress comparative anomalies.

## 7. Contradiction checks

Before emitting an insight, check for contradictory evidence.

Examples:

- revenue down but orders and AOV stable might mean source mismatch; do not overstate.
- stock low but no recent demand and no active promotion → lower priority.
- Tiendanube down while site sessions also down may be demand-driven, not storefront failure.

## 8. Report budget and anti-spam limits

A morning report should not become a pile of yellow flags.

Default limits:

- max 1 primary priority
- max 3 owner-facing insights on a normal day
- max 1 data-health caveat unless it invalidates the report
- merge related insights into one issue when they point to the same likely action

## 9. No fake precision

Avoid recommendation wording like:

- "Sales fell because customers dislike the new collection"
- "You lost exactly ARS 182,430 due to checkout friction"

unless the system actually has support for that claim.

## 10. Explain degraded mode explicitly

If a key source is stale, the report should say what was withheld.

Example:

- "Inventory sync is stale since 06:10. Stock-based advice omitted."

That preserves trust better than pretending completeness.

---

## Daily insight selection and report assembly

The report should be assembled in this order:

1. Validate source freshness and report completeness.
2. Generate all candidate insights.
3. Score each for severity, priority, confidence.
4. Suppress unsafe or low-value candidates.
5. Merge overlapping candidates.
6. Select:
   - one primary priority
   - up to two secondary items
   - optional one-line normal-day summary if no serious issues
7. Format for WhatsApp reading budget.

## Merge rules

Multiple facts that imply one action should become one insight.

Examples:

- revenue down + top seller low stock + ads active → one stock-demand collision insight
- spend active + zero orders + pending payments spike → one checkout/conversion failure insight
- high unanswered messages + high conversations → one support bottleneck insight

This prevents duplicate advice.

## Normal-day behavior

On a calm day, the engine should still be useful.

A normal-day report should provide:

- compact performance summary
- one notable change if any
- one low-friction priority, or explicit "no urgent action"

Avoid manufacturing drama to seem intelligent.

---

## Degraded mode and confidence-aware behavior

The report engine should classify the run into one of four states.

### State A: full-confidence

All required sources fresh enough; full report allowed.

### State B: partial-confidence

One secondary source missing or stale; report allowed with narrowed insights.

Example:

- orders + stock present, ads missing
- can talk about stock and fulfillment, cannot talk about ROAS

### State C: low-confidence operational summary only

Core source incomplete; anomaly diagnosis suppressed.

Example:

- only order count arrived, revenue missing
- inventory stale

Report should say:

- what data was used
- what was omitted
- only low-risk advice

### State D: failed report / operator attention needed

Too little reliable data for owner-facing intelligence.

In this case, Orvo should either:

- send a brief owner-safe message if product requires a daily send, or
- suppress owner send and notify internal operator

Preferred owner-safe wording:

- "Today’s report is partial because Tiendanube data did not sync completely. I’m holding recommendations until the data is back."

---

## Hito-0 implementation proposal

Hito-0 should not try to solve everything. It should implement a narrow, high-value first set.

## Hito-0 insight pack

### Must-have

- revenue down vs baseline
- top-seller low stock / stockout
- ad spend with zero orders
- unanswered conversations spike
- Tiendanube vs Mercado Libre mix anomaly when both channels exist
- data freshness caveat

### Nice-to-have if data is available

- pending-payment spike
- aged unfulfilled orders
- revenue concentration in one SKU

## Hito-0 prioritization heuristic

Simple but useful:

1. Any spend-without-orders or checkout-failure proxy = top priority.
2. Else any top-seller stock risk with live demand = top priority.
3. Else any aged fulfillment/service backlog = top priority.
4. Else largest revenue-impact warning = top priority.
5. Everything else becomes secondary or suppressed.

This is intentionally not a generic severity sort.

---

## Hito-1 refinement proposal

Hito-1 should make the engine feel less threshold-based and more operationally aware.

## Hito-1 improvements

### 1. Entity-aware insighting

Make insights specific to:

- channel
- SKU / product family
- order funnel step
- service queue

### 2. Comparative diagnosis rules

Use contrasting evidence patterns.

Examples:

- Mercado Libre stable + Tiendanube down → likely storefront/channel issue
- spend stable + sessions stable + orders down → likely conversion issue
- revenue down + stock low on top sellers → likely availability issue

### 3. Recurrence memory

Track repeated noisy findings and suppress them unless they worsen.

### 4. Feedback-weighted suppression

If Juan repeatedly marks a class of insight noisy, raise its threshold for this business until reevaluated.

### 5. Action outcome tracking

Longer term, measure whether a recommended action class tends to precede recovery.

Not for automatic reinforcement yet, but for internal learning.

---

## Evaluation and feedback loop

A useful insight engine is not just one that sounds plausible. It should be judged on whether it helps Juan act with less wasted attention.

## Primary evaluation questions

1. **Precision:** How often are owner-facing insights actually worth reading?
2. **Safety:** How often does the system give materially bad advice?
3. **Actionability:** How often is the top priority something Juan can do immediately?
4. **Brevity:** Does the report stay within the reading budget?
5. **Coverage:** On days with real operational problems, does Orvo catch them?

## Offline eval set design

Build a labeled corpus of daily report scenarios.

### Unit of evaluation

One business-day snapshot with:

- raw normalized metrics
- generated candidate insights
- expected good output
- expected suppressed insights
- severity/priority labels
- notes on ambiguity

### Scenario buckets

- normal day
- sales dip only
- stockout on best seller
- ad spend waste day
- checkout failure proxy
- fulfillment backlog
- support overload
- missing inventory data
- missing ads data
- TN down vs ML stable
- noisy borderline threshold day

### What to label

For each scenario:

- should alert? yes/no
- top priority should be what?
- acceptable recommendation classes
- forbidden recommendation classes
- acceptable tone examples

## Online feedback loop

Three levels of feedback matter.

### Level 1: per-insight owner feedback

Juan marks an insight as:

- useful
- noisy
- incorrect

### Level 2: report-level signal

Implicit or explicit:

- read but no reply
- asked follow-up question
- indicated action taken
- complained about wrongness / spam

### Level 3: outcome signal

Weak but helpful:

- issue disappeared next day
- issue persisted
- repeated same recommendation without progress

## Evaluation metrics

### Core product metrics

- % of owner-facing insights marked useful
- % marked noisy
- % marked incorrect
- % of reports with at least one useful insight
- average number of insights per report
- average character count per report
- share of days where a report was sent in degraded mode

### Safety metrics

- incorrect insight rate by insight type
- incorrect rate by connector/data state
- high-cost recommendation rate under medium/low confidence
- contradiction escape rate

### Intelligence quality metrics

- top-priority agreement with human reviewer
- recommendation appropriateness agreement
- duplicate/overlap rate
- missed-incident rate on labeled scenarios

### Operational metrics

- source freshness SLA hit rate
- report generation success rate
- suppression rate due to missing data

---

## Using feedback to improve the engine

Feedback should not directly rewrite rules in real time. It should first produce business-specific and global learning signals.

## Business-specific tuning

Use feedback to adjust:

- thresholds for noisy insight classes
- suppression rules for low-value recurring insights
- preferred wording/tone constraints
- whether certain families should only appear when severe

Example:

- If Juan marks mild revenue-dip alerts as noisy 4 times, raise threshold or require persistence.

## Global tuning

Use cross-business review internally to learn:

- which insight types over-fire
- which recommendation classes correlate with incorrect feedback
- which source combinations produce false confidence

## Hard safety rule

Useful/noisy feedback can tune thresholds automatically within bounded ranges.

Incorrect feedback should **not** fully auto-change rule behavior without human review, because a single owner may mislabel or data may later be corrected. Incorrect marks should create a higher-priority internal review queue.

---

## Suggested internal data model for insight evaluation

Even if not all fields exist in code yet, the product design should target something like this.

### ReportRun

- `report_run_id`
- `business_id`
- `report_date`
- `generated_at`
- `report_state` (`full`, `partial`, `summary_only`, `failed`)
- `char_count`
- `data_freshness_summary`
- `selected_primary_insight_id`

### InsightInstance

- `insight_instance_id`
- `report_run_id`
- `insight_type`
- `severity`
- `priority_score`
- `confidence_level`
- `title_rendered`
- `recommendation_rendered`
- `evidence_snapshot_json`
- `suppressed` (bool)
- `suppression_reason`

### InsightFeedback

- `feedback_id`
- `insight_instance_id`
- `business_id`
- `source` (`owner_whatsapp`, `internal_review`)
- `label` (`useful`, `noisy`, `incorrect`)
- `free_text_note`
- `created_at`
- `resolved_at`
- `review_status` (`new`, `triaged`, `closed`)

This model supports both owner feedback and internal summaries.

---

## Strong defaults for ARTEMEA

Because ARTEMEA is a physical-product D2C brand, these are the best first high-value defaults:

1. **Stock-demand collisions outrank generic sales dips.**
2. **Spend without orders is a top-priority critical issue.**
3. **Tiendanube-specific failures matter more than abstract channel commentary.**
4. **Support backlog matters if it threatens conversion or post-purchase trust.**
5. **Normal-day brevity matters; do not fill space with trivia.**
6. **Data-health honesty is part of the product, not a technical footnote.**

---

## Open questions

1. Which Tiendanube fields are reliably available for pending payments, fulfillment age, and product-level stock in the current adapter path?
2. Do we have enough mapping between ads and SKUs/products to safely recommend pausing specific campaigns versus broad spend checks?
3. Should normal-day reports always include one explicit priority, or allow "no urgent action today" as the primary line?
4. What freshness window is acceptable for inventory versus orders before suppressing stock-based advice?
5. How much Mercado Libre detail will exist in Hito-1: just revenue/orders by channel, or product-level marketplace signals too?
6. Should certain insight families be hidden entirely until Juan opts in, or start broad and learn through feedback?

## Recommendation

For Hito-0, optimize for precision and trust, not breadth. A small set of highly reliable operational insights will create more product credibility than a wide taxonomy with weak evidence.
