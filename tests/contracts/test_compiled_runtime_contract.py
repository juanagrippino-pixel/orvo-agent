from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule


def _business_with_tiendanube_token(token: str) -> BusinessConfig:
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
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
