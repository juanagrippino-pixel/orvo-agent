from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operator_api.projections import run_detail, run_history_item
from app.brain.run_ledger import RunRecord


def _raw_unredacted_run_record() -> RunRecord:
    # Use model_construct intentionally to model a legacy/custom ledger record
    # that reaches the operator API boundary without RunRecord validators having
    # sanitized compiled-runtime connector secret references first.
    return RunRecord.model_construct(
        run_id="run-raw-secret-refs",
        business_id="artemea",
        trigger_type="forced",
        status="running",
        started_at=datetime(2026, 5, 24, 8, tzinfo=timezone.utc),
        finished_at=None,
        config_ref="config://runtime?access_token=raw-run-token",
        config_digest="sha256:safe-digest",
        connector_outcomes=[],
        artifacts=[],
        dispatch_outcomes=[],
        summary_metadata={
            "connector_refs": [
                {
                    "connector_id": "tn-main",
                    "connector_type": "tiendanube",
                    "secret_refs": {
                        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
                    },
                    "secret_param_names": ["access_token"],
                }
            ],
            "note": "Bearer raw-run-token",
        },
        error_summary="connector failed with api_key=raw-error-secret",
    )


def test_run_history_projection_redacts_secret_ref_uri_values_at_api_boundary():
    projection = run_history_item(_raw_unredacted_run_record())
    rendered = str(projection)

    assert projection["summary_metadata"]["connector_refs"][0]["secret_refs"] == {
        "access_token": "[REDACTED]"
    }
    assert projection["summary_metadata"]["connector_refs"][0]["secret_param_names"] == ["access_token"]
    assert "secret://businesses/artemea" not in rendered
    assert "raw-run-token" not in rendered


def test_run_detail_projection_redacts_secret_ref_uri_values_at_api_boundary():
    projection = run_detail(_raw_unredacted_run_record())
    rendered = str(projection)

    assert projection["summary_metadata"]["connector_refs"][0]["secret_refs"] == {
        "access_token": "[REDACTED]"
    }
    assert projection["summary_metadata"]["connector_refs"][0]["secret_param_names"] == ["access_token"]
    assert "secret://businesses/artemea" not in rendered
    assert "raw-run-token" not in rendered
    assert "raw-error-secret" not in rendered
