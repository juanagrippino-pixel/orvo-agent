import pytest

from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule
from app.brain.models import InsightThresholds


def make_business(*, connectors=None, timezone="America/Argentina/Buenos_Aires"):
    return BusinessConfig(
        business_id="artemea",
        business_name="Artemea",
        owner_phone="+5491149724933",
        timezone=timezone,
        currency="ARS",
        connectors=connectors if connectors is not None else [
            ConnectorConfig(
                connector_id="sheet",
                connector_type="google_sheets",
                label="Sheet Artemea",
                params={"spreadsheet_id": "abc123", "range_name": "Daily!A1:G1000"},
            ),
            ConnectorConfig(
                connector_id="tn",
                connector_type="tiendanube",
                label="Tiendanube Artemea",
                params={"store_id": "12345", "access_token": "tn_test_token", "include_stock": True},
            ),
            ConnectorConfig(
                connector_id="disabled-csv",
                connector_type="csv",
                label="Disabled CSV",
                params={"csv_path": "/tmp/report.csv"},
                enabled=False,
            ),
        ],
        insight_thresholds=InsightThresholds(stock_threshold=7, unanswered_threshold=3),
    )


def test_compile_business_runtime_normalizes_business_connectors_schedule_and_settings():
    from app.brain.runtime import compile_business_runtime

    schedule = ReportSchedule(
        schedule_id="daily-08",
        business_id="artemea",
        cron_expression="0 8 * * *",
        report_type="daily",
    )

    runtime = compile_business_runtime(make_business(), schedules=[schedule])

    assert runtime.business_id == "artemea"
    assert runtime.business_name == "Artemea"
    assert runtime.timezone == "America/Argentina/Buenos_Aires"
    assert runtime.currency == "ARS"
    assert runtime.delivery.owner_phone == "+5491149724933"
    assert runtime.report_settings.insight_thresholds.stock_threshold == 7
    assert runtime.report_schedules[0].schedule_id == "daily-08"
    assert runtime.report_schedules[0].timezone == "America/Argentina/Buenos_Aires"
    assert [connector.connector_id for connector in runtime.connectors] == ["sheet", "tn"]
    assert runtime.connectors[0].required_params == ["spreadsheet_id", "range_name"]
    assert runtime.connectors[1].secret_param_names == ["access_token"]
    assert runtime.connectors[1].health_policy == {
        "readiness_check": "metadata_only",
        "supports_health_check": False,
        "degraded_state": "degraded",
    }
    assert runtime.connectors[1].required_scopes == ["orders.read", "products.read"]
    assert runtime.connectors[1].rate_limit_policy == {
        "default_timeout_seconds": 30,
        "requests_per_minute": 120,
        "retry_policy": "adapter_default",
    }
    assert runtime.connectors[1].lifecycle == {
        "status": "active",
        "owner": "orvo-brain",
        "version": "phase-a",
    }
    assert runtime.execution_plan.daily_connector_types == ["google_sheets", "tiendanube"]
    assert runtime.execution_plan.report_types == ["daily"]


def test_compile_business_runtime_rejects_missing_required_connector_params():
    from app.brain.runtime import RuntimeCompileError, compile_business_runtime

    business = make_business(
        connectors=[
            ConnectorConfig(
                connector_id="sheet",
                connector_type="google_sheets",
                label="Sheet Artemea",
                params={"spreadsheet_id": "abc123"},
            )
        ]
    )

    with pytest.raises(RuntimeCompileError) as excinfo:
        compile_business_runtime(business)

    assert excinfo.value.errors == ["connector sheet (google_sheets) missing required params: range_name"]


def test_compile_business_runtime_enforces_registry_supported_runtime_modes():
    from app.brain.runtime import RuntimeCompileError, compile_business_runtime

    business = make_business(
        connectors=[
            ConnectorConfig(
                connector_id="sample",
                connector_type="sample",
                label="Manual sample",
                params={},
            )
        ]
    )

    with pytest.raises(RuntimeCompileError) as excinfo:
        compile_business_runtime(business, run_mode="scheduled")

    assert excinfo.value.errors == [
        "connector sample (sample) does not support runtime mode scheduled; supported modes: preview, operator_triggered"
    ]

    preview_runtime = compile_business_runtime(business, run_mode="preview")
    assert preview_runtime.connectors[0].supported_runtime_modes == ["preview", "operator_triggered"]


def test_compile_business_runtime_rejects_no_enabled_supported_connectors():
    from app.brain.runtime import RuntimeCompileError, compile_business_runtime

    business = make_business(
        connectors=[
            ConnectorConfig(
                connector_id="csv-disabled",
                connector_type="csv",
                label="Disabled CSV",
                params={"csv_path": "/tmp/report.csv"},
                enabled=False,
            )
        ]
    )

    with pytest.raises(RuntimeCompileError) as excinfo:
        compile_business_runtime(business)

    assert excinfo.value.errors == ["business artemea has no enabled connectors"]


def test_compile_business_runtime_rejects_invalid_runtime_timezone_and_schedule_mismatch():
    from app.brain.runtime import RuntimeCompileError, compile_business_runtime

    schedule = ReportSchedule(
        schedule_id="other-business-daily",
        business_id="other-business",
        cron_expression="0 8 * * *",
        report_type="daily",
    )

    with pytest.raises(RuntimeCompileError) as excinfo:
        compile_business_runtime(make_business(timezone="Not/A_Timezone"), schedules=[schedule])

    assert excinfo.value.errors == [
        "business artemea timezone is invalid: Not/A_Timezone",
        "schedule other-business-daily belongs to other-business, expected artemea",
    ]
