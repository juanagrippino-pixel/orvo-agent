# Orvo D2C Control Plane PRD

Status: Draft source-of-truth
Date: 2026-05-24
Last adjusted: 2026-06-11
Related: `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`, `docs/product/d2c-ecommerce-control-plane.md`, `docs/product/2026-06-11-lapyme-category-mvp-scope.md`

## Product thesis

Orvo is the AI-native operating control plane for Argentine commerce PyMEs. The first wedge is D2C ecommerce: it turns scattered business signals into a prioritized queue of evidence-backed operational cases, then helps the owner/operator operate from an app/operator console with WhatsApp as an alert/projection channel.

The first product is not a chatbot, not a BI dashboard, not a generic agent platform, and not an ERP clone. It is a PyME operating-system slice that answers:

1. What needs attention?
2. Why does it matter?
3. What evidence supports it?
4. What should the operator do next?
5. What is still open, resolved, stale, or blocked?

The La Pyme/Tango benchmark raises the MVP bar: the first sellable product should feel like the beginning of an operating system for the business. The canonical control surface should be the app/operator console; WhatsApp should not be asked to control the whole business through one message.

## Initial ICP

Primary buyer/operator:

- Argentine/LatAm D2C store owner, operator, or small team.
- Uses Tiendanube or similar commerce platform.
- Runs business through WhatsApp, spreadsheets, dashboards, agencies, or manual checks.
- Has enough order/ad/support activity that missed signals cost money or time.
- Wants operational clarity, not another analytics login.

Early client fit signals:

- Owner asks daily "qué pasó hoy?" across sales, stock, ads, fulfillment, and chats.
- Data lives in multiple tools and is inspected manually.
- Follow-up is informal and easy to forget.
- WhatsApp is already the operating surface.
- Store has repeated issues: stockouts, ad spend mismatch, stale reports, fulfillment delays, unanswered chats.

## Core value proposition

> Orvo gives ecommerce operators a prioritized operating queue: cases, evidence, next actions, and follow-up history — starting from Tiendanube + WhatsApp.

Buyer-facing promises:

- Daily operating brief, not dashboard noise.
- Evidence-backed alerts and cases.
- Clear degraded-data honesty when Orvo cannot safely advise.
- Lightweight follow-up through WhatsApp/operator workflows.
- A history of unresolved and resolved operational issues.

## MVP scope

### Must have

1. Tiendanube-first commerce ingestion.
2. Deterministic metric extraction with evidence.
3. Compiled runtime path for preview/forced/scheduled execution.
4. Connector registry entry for Tiendanube with params, secret refs, capabilities, and degraded behavior.
5. Run ledger entries for run start/end, connector status, artifacts, errors, and dispatch attempts.
6. Metric registry entries for first D2C case families.
7. OperationalCase creation for at least:
   - `sales_drop`
   - `stockout_risk`
   - `data_stale`
8. WhatsApp/operator brief that cites cases/evidence and does not invent metrics.
9. Internal operator inspection: run history, connector health, open cases, case timeline.
10. Tests/invariants covering deterministic decisions, dedupe, evidence, redaction, and compatibility with existing report paths.

### Should have

1. `spend_without_orders` once Meta Ads + Tiendanube parity is trustworthy.
2. Case comments/actions for manual follow-up.
3. Operator queue filters: open, stale, high priority, source degraded.
4. Example/demo data with redacted credentials.
5. Sales/demo packet generated from the product contract, not hand-written fantasy.
6. OS-style module readiness statuses for sales/orders, stock/fulfillment, customer attention, ARCA/fiscal readiness, and treasury/reporting.
7. Setup-required cases for unconnected or untrusted modules so the product shows the path to a broader PyME OS without inventing data.

### Not yet

- Generic horizontal team OS.
- Developer marketplace as a launch product.
- Fully automated external actions without case/action governance.
- LLM-driven detection, prioritization, or lifecycle mutation.
- Full ERP parity: accounting ledger, HR, full warehouse master, invoice issuance, or payment reconciliation before source/readiness gates exist.

## User journeys

### Journey 1: Morning operator brief

1. Scheduled runtime compiles the business plan.
2. Connectors execute and emit metrics/evidence.
3. Detections create/update cases.
4. Run ledger records health and artifacts.
5. Orvo sends a concise WhatsApp brief:
   - top new/open cases,
   - evidence/source lines,
   - degraded caveats,
   - suggested next action.
6. Operator can inspect the case/run internally.

### Journey 2: Forced/manual check

1. Operator requests a forced run.
2. Same compiled runtime path executes.
3. Duplicate dispatch is prevented by idempotency policy.
4. The run and cases are inspectable.
5. The output says whether anything changed since the scheduled run.

### Journey 3: Follow-up loop

1. Operator acknowledges or comments on a case.
2. Case timeline stores the action/comment.
3. Next report references open/resolved/reopened state instead of repeating the same alert as if it were new.

## Success metrics

Product/trust metrics:

- % runs with complete connector health and no silent degraded state.
- % owner-facing claims with evidence refs.
- case dedupe rate: repeated issue updates existing case instead of spam.
- time from signal to operator visibility.
- number of manual follow-ups captured as case comments/actions.

Business metrics:

- first owner receives daily useful brief without manual intervention.
- repeated daily usage or reply behavior.
- willingness to pay for operational monitoring/follow-up.
- reduced manual checking across Tiendanube/ads/WhatsApp.

## Launch readiness checklist

- [ ] Tiendanube runtime is reliable with typed degraded states.
- [ ] Run ledger can explain every delivered/skipped/degraded brief.
- [ ] At least 3 case families are deterministic and deduped.
- [ ] WhatsApp output references evidence and open/resolved state.
- [ ] Operator can inspect runs and cases internally.
- [ ] Redaction tests cover tokens, URLs, OAuth values, and service-account content.
- [ ] Existing Hito0/report flows still pass.
- [ ] Sales/demo claims map to implemented or explicitly planned capabilities.
