import json

import pytest

from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule


def _business_with_tiendanube_token(token: str) -> BusinessConfig:
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="Tiendanube principal",
                params={"store_id": "12345", "access_token": token, "include_stock": True},
            )
        ],
    )


def _daily_schedule() -> ReportSchedule:
    return ReportSchedule(
        schedule_id="daily-08",
        business_id="artemea",
        cron_expression="0 8 * * *",
        report_type="daily",
    )


def test_compiled_runtime_serializes_secret_refs_not_legacy_raw_secret_values():
    from app.brain.runtime import compile_business_runtime

    runtime = compile_business_runtime(
        _business_with_tiendanube_token("tn_super_secret_live_token"),
        schedules=[_daily_schedule()],
        run_mode="forced",
    )

    serialized = runtime.model_dump_json()
    connector = runtime.connectors[0]

    assert runtime.run_mode == "forced"
    assert runtime.runtime_id.startswith("runtime:artemea:")
    assert runtime.compiled_from_hash.startswith("sha256:")
    assert "tn_super_secret_live_token" not in serialized
    assert "access_token" not in connector.params
    assert connector.secret_refs == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
    }
    assert connector.legacy_secret_param_names == ["access_token"]


def test_compiled_runtime_rejects_inline_secret_values_in_secret_refs():
    from app.brain.runtime import RuntimeCompileError, compile_business_runtime

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id="tn-main",
                connector_type="tiendanube",
                label="Tiendanube principal",
                params={"store_id": "12345"},
                secret_refs={"access_token": "raw-token-value"},
            )
        ],
    )

    with pytest.raises(RuntimeCompileError) as exc_info:
        compile_business_runtime(business, schedules=[_daily_schedule()], run_mode="forced")

    assert any(
        "tn-main (tiendanube) has invalid secret_refs.access_token" in error
        for error in exc_info.value.errors
    )
    assert "raw-token-value" not in str(exc_info.value)


def test_runtime_metadata_redacts_secret_shaped_connector_identifiers():
    from app.brain.models import InsightThresholds
    from app.brain.runtime import (
        CompiledBusinessRuntime,
        CompiledConnectorRuntime,
        CompiledDeliverySettings,
        CompiledExecutionPlan,
        CompiledReportSettings,
        runtime_run_metadata,
    )

    runtime = CompiledBusinessRuntime(
        runtime_id="runtime:artemea:test",
        compiled_from_hash="sha256:test",
        run_mode="forced",
        business_id="artemea",
        business_name="Artemea",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            CompiledConnectorRuntime(
                connector_id="tn?access_token=raw_identifier_secret",
                connector_type="tiendanube?api_key=raw_type_secret",
                label="Connector token=raw_label_secret",
                params={},
                secret_refs={
                    "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
                },
                required_params=[],
                secret_param_names=["access_token"],
                legacy_secret_param_names=["access_token"],
                capabilities=["daily_report"],
                emitted_metric_families=["commerce.revenue"],
                emitted_event_families=["connector.execution"],
                supported_runtime_modes=["forced"],
                executor_factory_path="app.brain.adapters.tiendanube.build_daily_report_from_tiendanube",
                health_policy={"readiness_check": "metadata_only"},
                required_scopes=["orders.read"],
                rate_limit_policy={"default_timeout_seconds": 30},
                lifecycle={"status": "active"},
            )
        ],
        report_schedules=[],
        report_settings=CompiledReportSettings(insight_thresholds=InsightThresholds()),
        delivery=CompiledDeliverySettings(owner_phone="+5491100000000"),
        execution_plan=CompiledExecutionPlan(daily_connector_types=[], report_types=[]),
    )

    metadata = runtime_run_metadata(runtime)
    serialized = json.dumps(metadata, sort_keys=True)

    assert "raw_identifier_secret" not in serialized
    assert "raw_type_secret" not in serialized
    assert "raw_label_secret" not in serialized
    connector = metadata["connector_refs"][0]
    assert connector["connector_id"] == "[REDACTED]"
    assert connector["connector_type"] == "[REDACTED]"
    assert connector["label"] == "Connector token=[REDACTED]"
    assert connector["secret_refs"] == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
    }


def test_compiled_runtime_hash_is_stable_when_only_raw_legacy_secret_value_changes():
    from app.brain.runtime import compile_business_runtime

    first = compile_business_runtime(
        _business_with_tiendanube_token("tn_first_secret"),
        schedules=[_daily_schedule()],
        run_mode="scheduled",
    )
    second = compile_business_runtime(
        _business_with_tiendanube_token("tn_rotated_secret"),
        schedules=[_daily_schedule()],
        run_mode="scheduled",
    )

    assert first.compiled_from_hash == second.compiled_from_hash
    assert first.runtime_id == second.runtime_id
    assert "tn_first_secret" not in first.model_dump_json()
    assert "tn_rotated_secret" not in second.model_dump_json()


def test_compile_business_runtime_does_not_mutate_source_business_config():
    """Runtime compilation must not silently rewrite durable control-plane config."""

    from app.brain.runtime import compile_business_runtime

    business = _business_with_tiendanube_token("tn_original_runtime_boundary_token")
    before = business.model_dump(mode="json")

    runtime = compile_business_runtime(business, schedules=[_daily_schedule()], run_mode="forced")

    assert business.model_dump(mode="json") == before
    assert business.connectors[0].params == {
        "store_id": "12345",
        "access_token": "tn_original_runtime_boundary_token",
        "include_stock": True,
    }
    assert runtime.connectors[0].params == {"store_id": "12345", "include_stock": True}
    assert runtime.connectors[0].secret_refs == {
        "access_token": "secret://businesses/artemea/connectors/tn-main/access_token"
    }


@pytest.mark.parametrize(
    ("connector_type", "connector_id", "public_params", "secret_refs"),
    [
        (
            "tiendanube",
            "tn-main",
            {"store_id": "12345", "include_stock": True},
            {"access_token": "secret://businesses/artemea/connectors/tn-main/access_token"},
        ),
        (
            "mercadolibre",
            "ml-main",
            {"seller_id": "123", "site_id": "MLA"},
            {"access_token": "secret://businesses/artemea/connectors/ml-main/access_token"},
        ),
        (
            "meta_ads",
            "meta-main",
            {"ad_account_id": "act_123"},
            {"access_token": "secret://businesses/artemea/connectors/meta-main/access_token"},
        ),
    ],
)
def test_compiled_runtime_accepts_registered_secret_refs_without_legacy_inline_tokens(
    connector_type, connector_id, public_params, secret_refs
):
    from app.brain.runtime import compile_business_runtime

    business = BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491100000000",
        timezone="America/Argentina/Buenos_Aires",
        currency="ARS",
        connectors=[
            ConnectorConfig(
                connector_id=connector_id,
                connector_type=connector_type,
                label=connector_type,
                params=public_params,
                secret_refs=secret_refs,
            )
        ],
    )

    runtime = compile_business_runtime(business, schedules=[_daily_schedule()], run_mode="forced")
    serialized = runtime.model_dump_json()
    connector = runtime.connectors[0]

    assert connector.params == public_params
    assert connector.secret_refs == secret_refs
    assert connector.legacy_secret_param_names == ["access_token"]
    assert "access_token" not in connector.params
    assert "raw" not in serialized.lower()
    for ref in secret_refs.values():
        assert ref in serialized
