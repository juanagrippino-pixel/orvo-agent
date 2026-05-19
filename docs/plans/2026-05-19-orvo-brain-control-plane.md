# Orvo Brain Control Plane Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build Orvo Brain as a real operations assistant for Argentine PyMEs/ecommerce: a WhatsApp-first control plane that normalizes business data, detects operational signals, and generates source-cited daily recommendations.

**Architecture:** Copy the useful Atlassian idea: central control plane + adapters. Orvo Brain should not be “a chatbot with tools”; it should be a system where connectors ingest data into a normalized operational model, an insight engine produces deterministic findings, and the LLM only explains/recommends with citations. Push reports are the main habit; pull questions come later.

**Tech Stack:** Python, Flask, LangGraph/LangChain already present, pytest, Pydantic models, future adapters for Google Sheets, Tiendanube, MercadoLibre, Meta Ads, WhatsApp Cloud/Twilio.

---

## Product Principles

1. **Trust before intelligence:** every number in a report must have a source citation.
2. **Push > Pull:** the first valuable product is a daily WhatsApp report, not a dashboard.
3. **Control plane, not scripts:** connectors are replaceable; the normalized business model is the product core.
4. **Assisted first:** first clients can be configured manually, but the internal architecture must be real.
5. **No hallucinated business data:** LLM can phrase insights, but calculations come from deterministic code.

---

## Target Architecture

```text
External systems
  ├─ Google Sheets
  ├─ Tiendanube
  ├─ MercadoLibre
  ├─ Meta Ads
  └─ WhatsApp conversations
        ↓
Connectors / adapters
        ↓
Canonical Operational Store
  ├─ Orders
  ├─ Products / stock
  ├─ Customers
  ├─ Conversations
  └─ Ad spend
        ↓
Insight Engine
  ├─ sales_delta
  ├─ stock_risk
  ├─ unanswered_messages
  ├─ margin / cash warnings
  └─ campaign anomalies
        ↓
Report Composer
  ├─ daily owner report
  ├─ cited evidence
  └─ recommended actions
        ↓
Delivery
  └─ WhatsApp push + future web settings
```

---

## Phase 1 — Core Brain Foundation

### Task 1: Create canonical domain models

**Objective:** Add typed models for metrics, evidence, insights, and daily reports.

**Files:**
- Create: `app/brain/__init__.py`
- Create: `app/brain/models.py`
- Test: `tests/test_brain_models.py`

**Behavior:**
- `Evidence` stores `source`, `label`, and optional `url`.
- `Metric` stores key/value/unit/evidence.
- `Insight` stores severity, title, explanation, action, evidence.
- `DailyReport` stores business name, date, metrics, insights.

**Verification:** `pytest tests/test_brain_models.py -q`

### Task 2: Create deterministic insight engine

**Objective:** Generate first useful insights without LLM dependency.

**Files:**
- Create: `app/brain/insights.py`
- Test: `tests/test_brain_insights.py`

**Behavior:**
- Detect revenue drop when today revenue is below baseline by threshold.
- Detect stock risk when stock units are below threshold.
- Detect unanswered conversations when pending count is high.
- Every insight must carry evidence.

**Verification:** `pytest tests/test_brain_insights.py -q`

### Task 3: Create daily report composer

**Objective:** Convert metrics + insights into a WhatsApp-ready report.

**Files:**
- Create: `app/brain/reporting.py`
- Test: `tests/test_brain_reporting.py`

**Behavior:**
- Output is short, owner-friendly Spanish.
- Includes metrics, alerts, recommended actions, and source lines.
- Does not invent data.

**Verification:** `pytest tests/test_brain_reporting.py -q`

### Task 4: Add local sample data adapter

**Objective:** Support manual/concierge onboarding from CSV/JSON before full APIs.

**Files:**
- Create: `app/brain/adapters/sample.py`
- Test: `tests/test_brain_sample_adapter.py`

**Behavior:**
- Load a simple dictionary/JSON-like payload into canonical metrics.
- Adapter emits cited metrics.

**Verification:** `pytest tests/test_brain_sample_adapter.py -q`

### Task 5: Add internal API endpoint for daily report

**Objective:** Let the current Flask server generate a report from payload.

**Files:**
- Modify: `server.py`
- Test: `tests/test_server_brain.py`

**Behavior:**
- POST `/brain/reports/daily` accepts sample payload.
- Returns JSON with `text`, `metrics`, `insights`.
- No WhatsApp send yet; this is internal control-plane endpoint.

**Verification:** `pytest tests/test_server_brain.py -q`

---

## Phase 2 — Real Connectors

1. Google Sheets connector for first concierge clients.
2. Tiendanube API connector.
3. MercadoLibre connector.
4. Meta Ads spend connector.
5. WhatsApp push scheduler.

---

## Phase 3 — Pull Questions

1. Question router: report question vs source lookup vs human handoff.
2. Retrieval over cited operational facts.
3. WhatsApp answers with citations.

---

## First Milestone Acceptance Criteria

- `pytest -q` passes.
- Daily report can be generated without external credentials.
- Every reported number has evidence.
- The architecture supports replacing sample adapter with real APIs.
- Existing WhatsApp sales bot remains working.
