# Tiendanube Exception Desk Technical Truth Gates Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make Orvo's first sellable Tiendanube Exception Desk technically honest by adding SKU-level stockout cases, stale-data suppression, and an explicit fulfillment-backlog gate before owner-facing claims.

**Architecture:** Keep adapters/runners thin and put deterministic case-building policy in a service module. `OperationalCase` remains the source of truth; WhatsApp/report/operator views are projections only. No LLM decides case existence, priority, lifecycle, or action keys.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, SQLite-backed `OperationalCaseStore`, existing `app/brain` runtime/case modules.

---

## Priority rule

Milestone lane wins conflicts for coding, testing, integration, and review capacity. This plan strengthens the sellable Tiendanube/WhatsApp wedge without bypassing compiled runtime, connector registry, run ledger, metric/evidence snapshots, case lifecycle, action-key catalog, or redaction contracts.

## Current repo facts to preserve

- `app/brain/operational_cases.py` currently defines `OperationalCaseStatus = Literal["open", "acknowledged", "resolved"]`.
- `OperationalCaseType` currently does not include `fulfillment_backlog`.
- Current report-derived `stockout_risk` dedupe is broad: `stockout_risk/business/monitored/commerce.inventory/daily`.
- Catalog target for stockout is SKU-level: `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.
- `make_data_stale_detection()` already exists and should be reused.
- `app/brain/operator_api.py` currently implements only `acknowledge_case` and `resolve_case`; action keys such as `add_comment`, `assign_owner`, `confirm_stock`, `inspect_pending_orders`, `mark_in_progress`, and `dismiss_case` remain catalog/roadmap unless a later plan adds handlers and tests.
- Do not replace report-derived compatibility behavior in this plan; add deterministic D2C policy helpers first.

---

### Task 1: Add D2C stockout signal model and SKU-level detection builder

**Objective:** Create a deterministic helper that converts one fresh SKU inventory signal into a SKU-scoped `stockout_risk` detection.

**Files:**
- Create: `app/brain/d2c_case_policies.py`
- Test: `tests/test_brain_d2c_case_policies.py`

**Step 1: Write failing test**

Create `tests/test_brain_d2c_case_policies.py` with:

```python
from app.brain.d2c_case_policies import D2CStockoutSignal, make_stockout_risk_detection


def test_make_stockout_detection_uses_sku_level_dedupe_and_evidence():
    signal = D2CStockoutSignal(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-123",
        sku_id="sku-42",
        product_label="Remera negra M",
        stock_units=2,
        threshold_units=3,
        recent_units_sold=5,
        freshness_state="fresh",
    )

    detection = make_stockout_risk_detection(signal)

    assert detection is not None
    assert detection.case_type == "stockout_risk"
    assert detection.dedupe_key == "artemea/stockout_risk/sku/sku-42/commerce.inventory/daily"
    assert detection.entity_scope == {"kind": "sku", "id": "sku-42", "label": "Remera negra M"}
    assert detection.run_id == "run-123"
    assert detection.evidence_refs == ["evidence://tiendanube/run-123/stockout_risk/sku/sku-42"]
    assert detection.evidence_snapshots[0].metrics[0].metric_key == "commerce.inventory.available_units"
    assert detection.evidence_snapshots[0].freshness_state == "fresh"
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_brain_d2c_case_policies.py::test_make_stockout_detection_uses_sku_level_dedupe_and_evidence -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.brain.d2c_case_policies'`

**Step 3: Write minimal implementation**

Create `app/brain/d2c_case_policies.py`:

```python
"""Deterministic D2C case policy helpers.

These helpers convert canonical ecommerce signals into OperationalCaseDetection
objects. They must not call LLMs or parse report prose.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.brain.operational_cases import (
    OperationalCaseDetection,
    OperationalCaseEvidenceMetric,
    OperationalCaseEvidenceSnapshot,
)

FreshnessState = Literal["fresh", "stale", "degraded", "missing", "unknown"]


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class D2CStockoutSignal(BaseModel):
    business_id: str = Field(..., min_length=1)
    connector_type: str = Field(..., min_length=1)
    run_id: str | None = None
    sku_id: str = Field(..., min_length=1)
    product_label: str = Field(..., min_length=1)
    stock_units: int = Field(..., ge=0)
    threshold_units: int = Field(..., ge=0)
    recent_units_sold: int = Field(default=0, ge=0)
    important: bool = False
    freshness_state: FreshnessState = "unknown"


def make_stockout_risk_detection(signal: D2CStockoutSignal) -> OperationalCaseDetection | None:
    if signal.freshness_state != "fresh":
        return None
    if signal.stock_units > signal.threshold_units:
        return None
    if signal.recent_units_sold <= 0 and not signal.important:
        return None

    run_part = signal.run_id or "unknown-run"
    evidence_ref = f"evidence://{signal.connector_type}/{run_part}/stockout_risk/sku/{signal.sku_id}"
    artifact_ref = f"ledger://runs/{signal.run_id}/stockout_risk/sku/{signal.sku_id}" if signal.run_id else None
    entity_scope = {"kind": "sku", "id": signal.sku_id, "label": signal.product_label}
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_part}/{evidence_ref}/stockout_risk/sku/{signal.sku_id}",
        captured_at=_now_utc(),
        run_id=signal.run_id,
        artifact_ref=artifact_ref,
        evidence_ref=evidence_ref,
        source=signal.connector_type,
        source_label="Tiendanube" if signal.connector_type == "tiendanube" else signal.connector_type,
        case_type="stockout_risk",
        entity_scope=entity_scope,
        summary=f"{signal.product_label}: stock {signal.stock_units} <= threshold {signal.threshold_units}",
        freshness_state=signal.freshness_state,
        metrics=[
            OperationalCaseEvidenceMetric(
                metric_key="commerce.inventory.available_units",
                label="Stock disponible",
                value=signal.stock_units,
                unit="units",
                window="current",
            ),
            OperationalCaseEvidenceMetric(
                metric_key="commerce.inventory.threshold_units",
                label="Umbral de stock",
                value=signal.threshold_units,
                unit="units",
                window="current",
            ),
            OperationalCaseEvidenceMetric(
                metric_key="commerce.units_sold.recent",
                label="Unidades vendidas recientes",
                value=signal.recent_units_sold,
                unit="units",
                window="recent",
            ),
        ],
        metadata={"important": signal.important},
    )
    return OperationalCaseDetection(
        business_id=signal.business_id,
        case_type="stockout_risk",
        dedupe_key=f"{signal.business_id}/stockout_risk/sku/{signal.sku_id}/commerce.inventory/daily",
        title=f"Stock en riesgo: {signal.product_label}",
        severity="critical" if signal.stock_units == 0 else "warning",
        priority_score=100 if signal.stock_units == 0 else 85,
        entity_scope=entity_scope,
        evidence_refs=[evidence_ref],
        run_id=signal.run_id,
        artifact_refs=[artifact_ref] if artifact_ref else [],
        evidence_snapshots=[snapshot],
        metadata={
            "connector_type": signal.connector_type,
            "sku_id": signal.sku_id,
            "stock_units": signal.stock_units,
            "threshold_units": signal.threshold_units,
            "recent_units_sold": signal.recent_units_sold,
            "important": signal.important,
        },
    )
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_brain_d2c_case_policies.py::test_make_stockout_detection_uses_sku_level_dedupe_and_evidence -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/brain/d2c_case_policies.py tests/test_brain_d2c_case_policies.py
git commit -m "feat: add SKU-level D2C stockout case policy"
```

---

### Task 2: Suppress stockout detection when inventory data is stale

**Objective:** Prove stale inventory does not open `stockout_risk`; instead it can be represented by existing `data_stale` helper.

**Files:**
- Modify: `tests/test_brain_d2c_case_policies.py`
- Modify: `app/brain/d2c_case_policies.py`

**Step 1: Write failing test**

Append:

```python
from app.brain.operational_cases import make_data_stale_detection


def test_stale_stock_signal_is_suppressed_and_data_stale_helper_remains_catalog_backed():
    signal = D2CStockoutSignal(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-stale",
        sku_id="sku-42",
        product_label="Remera negra M",
        stock_units=0,
        threshold_units=3,
        recent_units_sold=5,
        freshness_state="stale",
    )

    detection = make_stockout_risk_detection(signal)
    stale = make_data_stale_detection(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-stale",
        error_summary="inventory data stale",
    )

    assert detection is None
    assert stale.case_type == "data_stale"
    assert stale.dedupe_key == "artemea/data_stale/connector/tiendanube/runtime.freshness/daily"
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_brain_d2c_case_policies.py::test_stale_stock_signal_is_suppressed_and_data_stale_helper_remains_catalog_backed -v`

Expected: PASS if Task 1 already implemented suppression; if it unexpectedly opens a stockout case, FAIL and fix.

**Step 3: Write minimal implementation if needed**

Ensure `make_stockout_risk_detection()` contains:

```python
if signal.freshness_state != "fresh":
    return None
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_brain_d2c_case_policies.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/brain/d2c_case_policies.py tests/test_brain_d2c_case_policies.py
git commit -m "test: cover stale inventory suppression for stockout cases"
```

---

### Task 3: Add separate cases for different SKUs and update repeated runs for the same SKU

**Objective:** Verify SKU-level dedupe opens distinct cases per SKU and updates recurring detections for the same SKU.

**Files:**
- Modify: `tests/test_brain_d2c_case_policies.py`
- Test support: existing `app/brain/operational_cases.py`

**Step 1: Write failing test**

Append:

```python
from app.brain.operational_cases import InMemoryOperationalCaseStore


def test_sku_level_stockout_dedupe_opens_distinct_cases_per_sku_and_updates_same_sku():
    store = InMemoryOperationalCaseStore()
    sku_1 = D2CStockoutSignal(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-1",
        sku_id="sku-1",
        product_label="Remera negra M",
        stock_units=1,
        threshold_units=3,
        recent_units_sold=2,
        freshness_state="fresh",
    )
    sku_2 = sku_1.model_copy(update={"sku_id": "sku-2", "product_label": "Remera blanca S"})
    sku_1_next = sku_1.model_copy(update={"run_id": "run-2", "stock_units": 0})

    first = store.upsert_detection(make_stockout_risk_detection(sku_1))
    second = store.upsert_detection(make_stockout_risk_detection(sku_2))
    updated = store.upsert_detection(make_stockout_risk_detection(sku_1_next))

    assert first.case_id != second.case_id
    assert updated.case_id == first.case_id
    assert len(store.list_cases(business_id="artemea")) == 2
    assert updated.latest_run_id == "run-2"
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_brain_d2c_case_policies.py::test_sku_level_stockout_dedupe_opens_distinct_cases_per_sku_and_updates_same_sku -v`

Expected: PASS if Task 1 used SKU-level dedupe; if not, FAIL because only one broad case exists.

**Step 3: Write minimal implementation if needed**

Use this dedupe shape in `make_stockout_risk_detection()`:

```python
dedupe_key=f"{signal.business_id}/stockout_risk/sku/{signal.sku_id}/commerce.inventory/daily"
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_brain_d2c_case_policies.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/brain/d2c_case_policies.py tests/test_brain_d2c_case_policies.py
git commit -m "test: verify SKU-level stockout case dedupe"
```

---

### Task 4: Add owner-facing case brief projection gate before new internal case families

**Objective:** Prevent internal-only or unverified cases from reaching WhatsApp owner briefs by filtering cases before `case_brief_dispatcher` receives them.

**Files:**
- Modify: `app/brain/execution_ledger.py:90-94`
- Create: `tests/test_brain_execution_ledger.py`

**Step 1: Write failing test**

Create `tests/test_brain_execution_ledger.py` with:

```python
from datetime import datetime, timezone

from app.brain.execution_ledger import _owner_brief_cases
from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)


def _case_detection(case_type: str, dedupe: str, metadata: dict | None = None) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id="artemea",
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"artemea/{dedupe}",
        title=f"Case {dedupe}",
        severity="warning",
        priority_score=80,
        entity_scope={"kind": "store", "id": "artemea"},
        evidence_refs=[f"evidence://tiendanube/run-1/{dedupe}"],
        run_id="run-1",
        artifact_refs=[f"ledger://runs/run-1/{dedupe}"],
        metadata=metadata or {},
    )


def test_owner_brief_cases_excludes_internal_only_cases_by_default():
    store = InMemoryOperationalCaseStore()
    now = datetime(2026, 5, 25, 8, tzinfo=timezone.utc)
    store.upsert_detection(
        _case_detection("stockout_risk", "stockout", {"owner_facing_ready": True}),
        detected_at=now,
    )
    store.upsert_detection(
        _case_detection(
            "data_stale",
            "stale",
            {"owner_facing_ready": True, "freshness_state": "stale"},
        ),
        detected_at=now,
    )
    store.upsert_detection(
        _case_detection(
            "channel_mix_shift",
            "internal-channel",
            {
                "owner_facing_ready": False,
                "owner_facing_gate": "internal_only_until_source_truth_passes",
            },
        ),
        detected_at=now,
    )

    cases = _owner_brief_cases(store, "artemea")

    assert {case.case_type for case in cases} == {"stockout_risk", "data_stale"}
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_brain_execution_ledger.py::test_owner_brief_cases_excludes_internal_only_cases_by_default -v`

Expected: FAIL — `_owner_brief_cases()` currently returns every open/acknowledged case, including the internal `channel_mix_shift` case.

**Step 3: Write minimal implementation**

In `app/brain/execution_ledger.py`, add the allowlist and helper above `_owner_brief_cases()`:

```python
_OWNER_BRIEF_ALLOWED_CASE_TYPES = {"stockout_risk", "data_stale", "sales_drop"}


def _case_is_owner_brief_ready(case: OperationalCase) -> bool:
    if case.status not in {"open", "acknowledged"}:
        return False
    if case.case_type == "fulfillment_backlog":
        return (
            case.metadata.get("owner_facing_ready") is True
            and case.metadata.get("field_confidence") == "verified"
            and case.metadata.get("freshness_state") == "fresh"
            and bool(case.evidence_snapshots)
            and bool(case.metadata.get("redacted_sample_order_refs"))
        )
    if case.case_type not in _OWNER_BRIEF_ALLOWED_CASE_TYPES:
        return bool(case.metadata.get("owner_facing_ready"))
    if case.case_type == "data_stale":
        return True
    if case.case_type == "stockout_risk" and case.entity_scope.get("kind") != "sku":
        return case.metadata.get("owner_facing_ready") is True
    if case.metadata.get("owner_facing_ready") is False:
        return False
    return bool(case.evidence_refs or case.evidence_snapshots)
```

Then replace `_owner_brief_cases()` with:

```python
def _owner_brief_cases(case_store: OperationalCaseStore, business_id: str) -> list[OperationalCase]:
    cases: list[OperationalCase] = []
    for status in ("open", "acknowledged"):
        cases.extend(case_store.list_cases(business_id=business_id, status=status, limit=None))
    return [case for case in cases if _case_is_owner_brief_ready(case)]
```

**Important:** This is a projection gate, not the source of truth. It must not prevent internal cases from being stored or shown in internal operator surfaces.

**Step 4: Run test to verify pass**

Run: `pytest tests/test_brain_execution_ledger.py::test_owner_brief_cases_excludes_internal_only_cases_by_default -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/brain/execution_ledger.py tests/test_brain_execution_ledger.py
git commit -m "feat: gate owner-facing case brief projection"
```

---

### Task 5: Add fulfillment backlog as internal-only case type behind a data-truth gate

**Objective:** Add `fulfillment_backlog` to the case type enum and a policy helper that returns `None` unless order/fulfillment data is fresh and unambiguous; generated cases must default to `owner_facing_ready=False` until field audit passes.

**Files:**
- Modify: `app/brain/operational_cases.py:21-30`
- Modify: `app/brain/d2c_case_policies.py`
- Modify: `tests/test_brain_d2c_case_policies.py`
- Modify: `docs/specs/d2c-case-family-catalog.md`

**Step 1: Write failing test**

Append:

```python
from app.brain.d2c_case_policies import D2CFulfillmentBacklogSignal, make_fulfillment_backlog_detection


def test_fulfillment_backlog_requires_fresh_unambiguous_tiendanube_order_fields():
    ambiguous = D2CFulfillmentBacklogSignal(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-orders",
        pending_order_count=4,
        oldest_pending_hours=30,
        count_threshold=3,
        age_threshold_hours=24,
        freshness_state="fresh",
        fields_verified=False,
        verified_field_names=[],
        field_confidence="unverified",
    )
    verified = ambiguous.model_copy(
        update={
            "fields_verified": True,
            "verified_field_names": ["payment_status", "fulfillment_status", "created_at"],
            "field_confidence": "verified",
        }
    )

    assert make_fulfillment_backlog_detection(ambiguous) is None
    detection = make_fulfillment_backlog_detection(verified)

    assert detection is not None
    assert detection.case_type == "fulfillment_backlog"
    assert detection.dedupe_key == "artemea/fulfillment_backlog/channel/tiendanube/commerce.fulfillment/daily"
    assert detection.entity_scope == {"kind": "channel", "id": "tiendanube", "label": "Tiendanube"}
    assert detection.metadata["owner_facing_ready"] is False
    assert detection.metadata["field_confidence"] == "verified"


def test_fulfillment_backlog_owner_brief_requires_verified_fresh_redacted_evidence():
    from datetime import datetime, timezone

    from app.brain.execution_ledger import _owner_brief_cases
    from app.brain.operational_cases import InMemoryOperationalCaseStore

    signal = D2CFulfillmentBacklogSignal(
        business_id="artemea",
        connector_type="tiendanube",
        run_id="run-orders",
        pending_order_count=4,
        oldest_pending_hours=30,
        count_threshold=3,
        age_threshold_hours=24,
        freshness_state="fresh",
        fields_verified=True,
        verified_field_names=["payment_status", "fulfillment_status", "created_at"],
        field_confidence="verified",
        redacted_sample_order_refs=["TN-1002"],
    )
    default_internal = make_fulfillment_backlog_detection(signal)
    assert default_internal is not None

    store = InMemoryOperationalCaseStore()
    now = datetime(2026, 5, 25, 8, tzinfo=timezone.utc)
    store.upsert_detection(default_internal, detected_at=now)
    store.upsert_detection(
        default_internal.model_copy(
            update={
                "dedupe_key": "artemea/fulfillment_backlog/channel/tiendanube/unverified-owner",
                "metadata": {
                    **default_internal.metadata,
                    "owner_facing_ready": True,
                    "field_confidence": "unverified",
                    "redacted_sample_order_refs": ["TN-1001"],
                },
            }
        ),
        detected_at=now,
    )
    store.upsert_detection(
        default_internal.model_copy(
            update={
                "dedupe_key": "artemea/fulfillment_backlog/channel/tiendanube/verified-owner",
                "metadata": {
                    **default_internal.metadata,
                    "owner_facing_ready": True,
                    "field_confidence": "verified",
                    "freshness_state": "fresh",
                    "redacted_sample_order_refs": ["TN-1002"],
                },
            }
        ),
        detected_at=now,
    )

    cases = _owner_brief_cases(store, "artemea")

    assert [case.dedupe_key for case in cases] == ["artemea/fulfillment_backlog/channel/tiendanube/verified-owner"]
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_brain_d2c_case_policies.py::test_fulfillment_backlog_requires_fresh_unambiguous_tiendanube_order_fields tests/test_brain_d2c_case_policies.py::test_fulfillment_backlog_owner_brief_requires_verified_fresh_redacted_evidence -v`

Expected: FAIL — `ImportError` or Pydantic literal validation error because `fulfillment_backlog` is not yet a valid case type.

**Step 3: Write minimal implementation**

In `app/brain/operational_cases.py`, update `OperationalCaseType`:

```python
OperationalCaseType = Literal[
    "sales_drop",
    "stockout_risk",
    "spend_without_orders",
    "data_stale",
    "fulfillment_backlog",
    "unanswered_conversations",
    "channel_mix_shift",
]
```

In `app/brain/d2c_case_policies.py`, append:

```python
class D2CFulfillmentBacklogSignal(BaseModel):
    business_id: str = Field(..., min_length=1)
    connector_type: str = Field(..., min_length=1)
    run_id: str | None = None
    pending_order_count: int = Field(..., ge=0)
    oldest_pending_hours: int = Field(..., ge=0)
    count_threshold: int = Field(..., ge=0)
    age_threshold_hours: int = Field(..., ge=0)
    freshness_state: FreshnessState = "unknown"
    fields_verified: bool = False
    verified_field_names: list[str] = Field(default_factory=list)
    field_confidence: Literal["unverified", "verified"] = "unverified"
    redacted_sample_order_refs: list[str] = Field(default_factory=list)


def make_fulfillment_backlog_detection(signal: D2CFulfillmentBacklogSignal) -> OperationalCaseDetection | None:
    if signal.freshness_state != "fresh" or not signal.fields_verified or signal.field_confidence != "verified":
        return None
    required_fields = {"payment_status", "fulfillment_status", "created_at"}
    if not required_fields.issubset(set(signal.verified_field_names)):
        return None
    if signal.pending_order_count < signal.count_threshold and signal.oldest_pending_hours < signal.age_threshold_hours:
        return None

    run_part = signal.run_id or "unknown-run"
    evidence_ref = f"evidence://{signal.connector_type}/{run_part}/fulfillment_backlog"
    artifact_ref = f"ledger://runs/{signal.run_id}/fulfillment_backlog" if signal.run_id else None
    entity_scope = {"kind": "channel", "id": signal.connector_type, "label": "Tiendanube" if signal.connector_type == "tiendanube" else signal.connector_type}
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_part}/{evidence_ref}/fulfillment_backlog/channel/{signal.connector_type}",
        run_id=signal.run_id,
        artifact_ref=artifact_ref,
        evidence_ref=evidence_ref,
        source=signal.connector_type,
        source_label=entity_scope["label"],
        case_type="fulfillment_backlog",
        entity_scope=entity_scope,
        summary=f"{signal.pending_order_count} pending paid/unfulfilled orders; oldest {signal.oldest_pending_hours}h",
        freshness_state=signal.freshness_state,
        metrics=[
            OperationalCaseEvidenceMetric(
                metric_key="commerce.fulfillment.pending_order_count",
                label="Pedidos pendientes",
                value=signal.pending_order_count,
                unit="orders",
                window="current",
            ),
            OperationalCaseEvidenceMetric(
                metric_key="commerce.fulfillment.oldest_pending_hours",
                label="Pedido pendiente más antiguo",
                value=signal.oldest_pending_hours,
                unit="hours",
                window="current",
            ),
        ],
        metadata={
            "fields_verified": signal.fields_verified,
            "verified_field_names": signal.verified_field_names,
            "field_confidence": signal.field_confidence,
            "redacted_sample_order_refs": signal.redacted_sample_order_refs,
        },
    )
    return OperationalCaseDetection(
        business_id=signal.business_id,
        case_type="fulfillment_backlog",
        dedupe_key=f"{signal.business_id}/fulfillment_backlog/channel/{signal.connector_type}/commerce.fulfillment/daily",
        title="Pedidos pendientes en Tiendanube",
        severity="critical" if signal.oldest_pending_hours >= signal.age_threshold_hours * 2 else "warning",
        priority_score=90,
        entity_scope=entity_scope,
        evidence_refs=[evidence_ref],
        run_id=signal.run_id,
        artifact_refs=[artifact_ref] if artifact_ref else [],
        evidence_snapshots=[snapshot],
        metadata={
            "connector_type": signal.connector_type,
            "pending_order_count": signal.pending_order_count,
            "oldest_pending_hours": signal.oldest_pending_hours,
            "fields_verified": signal.fields_verified,
            "verified_field_names": signal.verified_field_names,
            "field_confidence": signal.field_confidence,
            "redacted_sample_order_refs": signal.redacted_sample_order_refs,
            "owner_facing_ready": False,
            "owner_facing_gate": "internal_only_until_real_tiendanube_field_audit_passes",
        },
    )
```

**Adapter truth note for a follow-up task:** `fields_verified=True` may only be set after inspecting real Tiendanube payload fields for payment status, order status, fulfillment/shipping status, created/paid/closed/fulfilled timestamps, and cancelled/refunded/test/internal exclusions. If any field is missing or an external ERP/carrier is the actual fulfillment source of truth, suppress this case or keep it internal-only.

In `docs/specs/d2c-case-family-catalog.md`, add the promotion note under `fulfillment_backlog`:

```markdown
**Owner-facing gate:** Do not expose this case to owners until real Tiendanube stores prove that payment and fulfillment fields reliably identify paid/unfulfilled aging orders. Until then, treat it as internal-only or phrase narrowly as “pedidos pendientes en Tiendanube.”
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_brain_d2c_case_policies.py::test_fulfillment_backlog_requires_fresh_unambiguous_tiendanube_order_fields tests/test_brain_d2c_case_policies.py::test_fulfillment_backlog_owner_brief_requires_verified_fresh_redacted_evidence -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/brain/operational_cases.py app/brain/d2c_case_policies.py tests/test_brain_d2c_case_policies.py docs/specs/d2c-case-family-catalog.md
git commit -m "feat: gate fulfillment backlog case policy"
```

---

### Task 6: Add built-in internal operator view for fulfillment backlog after the gated type exists

**Objective:** Let internal operators inspect verified pending-order cases without making a public dashboard product or owner-facing WhatsApp claim.

**Files:**
- Modify: `app/brain/operator_views.py:87-130`
- Modify: `tests/test_operator_case_views.py`

**Step 1: Write failing test**

In `tests/test_operator_case_views.py`, add:

```python
def test_builtin_views_include_fulfillment_backlog_after_case_type_is_registered():
    from app.brain.operator_views import builtin_case_views

    views = {view["view_id"]: view for view in builtin_case_views()}

    assert views["fulfillment_backlog"]["jql"] == "case_type = fulfillment_backlog AND status IN (open, acknowledged) ORDER BY priority_score DESC"
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_operator_case_views.py::test_builtin_views_include_fulfillment_backlog_after_case_type_is_registered -v`

Expected: FAIL — `KeyError: 'fulfillment_backlog'`

**Step 3: Write minimal implementation**

Add to `_BUILTIN_CASE_VIEWS` in `app/brain/operator_views.py`:

```python
    {
        "view_id": "fulfillment_backlog",
        "label": "Pending orders",
        "description": "Open or acknowledged Tiendanube pending-order cases.",
        "jql": "case_type = fulfillment_backlog AND status IN (open, acknowledged) ORDER BY priority_score DESC",
        "readonly": True,
    },
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_operator_case_views.py::test_builtin_views_include_fulfillment_backlog_after_case_type_is_registered -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/brain/operator_views.py tests/test_operator_case_views.py
git commit -m "feat: add fulfillment backlog operator view"
```

---

### Task 7: Run focused and regression tests

**Objective:** Verify the new case-policy slice does not break existing runtime/case/report behavior.

**Files:**
- Test only

**Step 1: Run focused tests**

Run:

```bash
pytest tests/test_brain_d2c_case_policies.py tests/test_brain_execution_ledger.py tests/test_brain_operational_cases.py tests/test_operator_case_views.py -q
```

Expected: PASS

**Step 2: Run runtime regression tests**

Run:

```bash
pytest tests/test_run_orvo_brain_reports_script.py tests/test_brain_runner.py tests/test_brain_reporting.py -q
```

Expected: PASS

**Step 3: Run full suite**

Run:

```bash
pytest -q
```

Expected: PASS

**Step 4: Review diff**

Run:

```bash
git diff --stat
```

Expected: only the planned files changed.

**Step 5: Commit if needed**

If previous tasks were committed separately, do not create an empty commit. Otherwise:

```bash
git add app/brain/d2c_case_policies.py app/brain/operational_cases.py app/brain/operator_views.py tests/test_brain_d2c_case_policies.py tests/test_brain_operational_cases.py tests/test_operator_case_views.py docs/specs/d2c-case-family-catalog.md
git commit -m "feat: add Tiendanube exception desk truth gates"
```

---

## Final acceptance criteria

- `stockout_risk` has a deterministic SKU-level case builder with evidence snapshots.
- Stale inventory data returns no stockout detection and remains represented by `data_stale`.
- Different SKUs open different cases; repeated runs for the same SKU update one case.
- `fulfillment_backlog` is impossible to expose accidentally without an explicit fields-verified gate.
- Owner-facing case brief excludes internal-only cases before fulfillment backlog is added.
- Internal operator view can inspect pending-order cases after the type is registered.
- Existing report-derived cases and runtime tests remain green.
- No LLM-created metrics, case existence, priorities, action keys, or lifecycle transitions are introduced.
- Parent repo remains clean after committed work.
