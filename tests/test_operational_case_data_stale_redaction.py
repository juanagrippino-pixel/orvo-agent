from __future__ import annotations

from app.brain.operational_cases import InMemoryOperationalCaseStore, make_data_stale_detection


def test_data_stale_detection_redacts_secret_shaped_connector_identifier_in_canonical_case_fields():
    raw_secret = "raw_connector_secret"
    detection = make_data_stale_detection(
        business_id="artemea",
        connector_type=f"tiendanube access_token={raw_secret}",
        run_id="run-redaction",
        error_summary=f"401 Authorization: Basic {raw_secret}",
    )
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(detection)

    serialized_detection = detection.model_dump_json()
    serialized_case = case.model_dump_json()

    assert raw_secret not in serialized_detection
    assert raw_secret not in serialized_case
    assert detection.dedupe_key == "artemea/data_stale/connector/[REDACTED]/runtime.freshness/daily"
    assert case.dedupe_key == detection.dedupe_key
    assert case.entity_scope["id"] == "[REDACTED]"
    assert case.entity_scope["label"] == "[REDACTED]"
