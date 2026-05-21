"""TDD tests for Orvo Brain business config and report schedule models/storage."""

import json

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# BusinessConfig model
# ---------------------------------------------------------------------------

class TestBusinessConfigModel:
    def test_create_minimal_config(self):
        from app.brain.config import BusinessConfig

        cfg = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
        )
        assert cfg.business_id == "artemea-001"
        assert cfg.business_name == "Artemea"
        assert cfg.owner_phone == "+5491112345678"
        assert cfg.timezone == "America/Argentina/Buenos_Aires"
        assert cfg.currency == "ARS"
        assert cfg.connectors == []

    def test_business_id_required(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_name="Artemea",
                owner_phone="+5491112345678",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
            )

    def test_business_name_required(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                owner_phone="+5491112345678",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
            )

    def test_owner_phone_required(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                business_name="Artemea",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
            )

    def test_owner_phone_must_start_with_plus(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                business_name="Artemea",
                owner_phone="5491112345678",  # missing leading +
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
            )

    def test_timezone_required(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                business_name="Artemea",
                owner_phone="+5491112345678",
                currency="ARS",
            )

    def test_currency_required(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                business_name="Artemea",
                owner_phone="+5491112345678",
                timezone="America/Argentina/Buenos_Aires",
            )

    def test_empty_business_name_rejected(self):
        from app.brain.config import BusinessConfig

        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                business_name="",
                owner_phone="+5491112345678",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
            )


# ---------------------------------------------------------------------------
# ConnectorConfig model
# ---------------------------------------------------------------------------

class TestConnectorConfigModel:
    def test_create_connector(self):
        from app.brain.config import ConnectorConfig

        conn = ConnectorConfig(
            connector_id="gs-sales",
            connector_type="google_sheets",
            label="Ventas Artemea",
            params={"spreadsheet_id": "abc123", "range_name": "Ventas!A1:F1000"},
        )
        assert conn.connector_id == "gs-sales"
        assert conn.connector_type == "google_sheets"
        assert conn.params["spreadsheet_id"] == "abc123"
        assert conn.enabled is True  # default

    def test_connector_disabled_by_default_is_enabled(self):
        from app.brain.config import ConnectorConfig

        conn = ConnectorConfig(
            connector_id="gs-sales",
            connector_type="google_sheets",
            label="Ventas",
            params={},
            enabled=False,
        )
        assert conn.enabled is False

    def test_connector_id_required(self):
        from app.brain.config import ConnectorConfig

        with pytest.raises(ValidationError):
            ConnectorConfig(
                connector_type="google_sheets",
                label="Ventas",
                params={},
            )

    def test_connector_type_required(self):
        from app.brain.config import ConnectorConfig

        with pytest.raises(ValidationError):
            ConnectorConfig(
                connector_id="gs-sales",
                label="Ventas",
                params={},
            )

    def test_known_connectors_validate_required_params(self):
        from app.brain.config import ConnectorConfig

        required = {
            "google_sheets": ("spreadsheet_id", "range_name"),
            "csv": ("csv_path",),
            "tiendanube": ("store_id", "access_token"),
            "mercadolibre": ("seller_id", "access_token"),
            "meta_ads": ("ad_account_id", "access_token"),
        }

        for connector_type, keys in required.items():
            params = {key: f"demo-{key}" for key in keys}
            conn = ConnectorConfig(
                connector_id=f"demo-{connector_type}",
                connector_type=connector_type,
                label=f"Demo {connector_type}",
                params=params,
            )
            assert conn.params == params

    def test_missing_known_connector_params_raise_actionable_error(self):
        from app.brain.config import ConnectorConfig

        with pytest.raises(ValidationError) as excinfo:
            ConnectorConfig(
                connector_id="bad-meta",
                connector_type="meta_ads",
                label="Meta Ads",
                params={"access_token": "meta_test_token"},
            )

        message = str(excinfo.value)
        assert "meta_ads connector params must include ad_account_id" in message
        assert "examples/meta_ads_business_config.json" in message

    def test_unknown_connector_type_is_preserved_for_runtime_error(self):
        from app.brain.config import ConnectorConfig

        conn = ConnectorConfig(
            connector_id="future",
            connector_type="shopify",
            label="Future connector",
            params={},
        )
        assert conn.connector_type == "shopify"


# ---------------------------------------------------------------------------
# BusinessConfig with connectors
# ---------------------------------------------------------------------------

class TestBusinessConfigWithConnectors:
    def test_config_accepts_connector_list(self):
        from app.brain.config import BusinessConfig, ConnectorConfig

        conn = ConnectorConfig(
            connector_id="gs-sales",
            connector_type="google_sheets",
            label="Ventas",
            params={"spreadsheet_id": "abc", "range_name": "Ventas!A1:F1000"},
        )
        cfg = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[conn],
        )
        assert len(cfg.connectors) == 1
        assert cfg.connectors[0].connector_type == "google_sheets"

    def test_connector_ids_must_be_unique(self):
        from app.brain.config import BusinessConfig, ConnectorConfig

        conn1 = ConnectorConfig(
            connector_id="dup",
            connector_type="google_sheets",
            label="A",
            params={"spreadsheet_id": "abc", "range_name": "Ventas!A1:F1000"},
        )
        conn2 = ConnectorConfig(
            connector_id="dup",
            connector_type="sample",
            label="B",
            params={},
        )
        with pytest.raises(ValidationError):
            BusinessConfig(
                business_id="artemea-001",
                business_name="Artemea",
                owner_phone="+5491112345678",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
                connectors=[conn1, conn2],
            )


# ---------------------------------------------------------------------------
# ReportSchedule model
# ---------------------------------------------------------------------------

class TestReportScheduleModel:
    def test_create_daily_schedule(self):
        from app.brain.config import ReportSchedule

        sched = ReportSchedule(
            schedule_id="daily-morning",
            business_id="artemea-001",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
        assert sched.schedule_id == "daily-morning"
        assert sched.cron_expression == "0 9 * * *"
        assert sched.enabled is True
        assert sched.report_type == "daily"

    def test_schedule_id_required(self):
        from app.brain.config import ReportSchedule

        with pytest.raises(ValidationError):
            ReportSchedule(
                business_id="artemea-001",
                cron_expression="0 9 * * *",
                report_type="daily",
            )

    def test_business_id_required_on_schedule(self):
        from app.brain.config import ReportSchedule

        with pytest.raises(ValidationError):
            ReportSchedule(
                schedule_id="s1",
                cron_expression="0 9 * * *",
                report_type="daily",
            )

    def test_cron_expression_required(self):
        from app.brain.config import ReportSchedule

        with pytest.raises(ValidationError):
            ReportSchedule(
                schedule_id="s1",
                business_id="artemea-001",
                report_type="daily",
            )

    def test_report_type_must_be_valid(self):
        from app.brain.config import ReportSchedule

        with pytest.raises(ValidationError):
            ReportSchedule(
                schedule_id="s1",
                business_id="artemea-001",
                cron_expression="0 9 * * *",
                report_type="unknown_type",
            )

    def test_report_type_weekly_accepted(self):
        from app.brain.config import ReportSchedule

        sched = ReportSchedule(
            schedule_id="weekly",
            business_id="artemea-001",
            cron_expression="0 9 * * 1",
            report_type="weekly",
        )
        assert sched.report_type == "weekly"


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------

class TestJSONSerialisation:
    def test_business_config_to_json_round_trip(self):
        from app.brain.config import BusinessConfig, ConnectorConfig, config_to_json, config_from_json

        conn = ConnectorConfig(
            connector_id="gs-1",
            connector_type="google_sheets",
            label="Ventas",
            params={"spreadsheet_id": "xyz", "range_name": "Ventas!A1:F1000"},
        )
        cfg = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            connectors=[conn],
        )
        raw = config_to_json(cfg)
        data = json.loads(raw)
        assert data["business_id"] == "artemea-001"
        assert data["connectors"][0]["connector_id"] == "gs-1"

        restored = config_from_json(raw)
        assert restored.business_name == "Artemea"
        assert restored.connectors[0].params["spreadsheet_id"] == "xyz"

    def test_schedule_to_json_round_trip(self):
        from app.brain.config import ReportSchedule, schedule_to_json, schedule_from_json

        sched = ReportSchedule(
            schedule_id="daily-morning",
            business_id="artemea-001",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
        raw = schedule_to_json(sched)
        data = json.loads(raw)
        assert data["schedule_id"] == "daily-morning"

        restored = schedule_from_json(raw)
        assert restored.cron_expression == "0 9 * * *"


# ---------------------------------------------------------------------------
# In-memory config store
# ---------------------------------------------------------------------------

class TestInMemoryConfigStore:
    def test_save_and_load_business_config(self):
        from app.brain.config import BusinessConfig, InMemoryConfigStore

        store = InMemoryConfigStore()
        cfg = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
        )
        store.save_business_config(cfg)
        loaded = store.load_business_config("artemea-001")
        assert loaded is not None
        assert loaded.business_name == "Artemea"

    def test_load_nonexistent_config_returns_none(self):
        from app.brain.config import InMemoryConfigStore

        store = InMemoryConfigStore()
        assert store.load_business_config("does-not-exist") is None

    def test_save_and_load_schedule(self):
        from app.brain.config import ReportSchedule, InMemoryConfigStore

        store = InMemoryConfigStore()
        sched = ReportSchedule(
            schedule_id="daily-morning",
            business_id="artemea-001",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
        store.save_schedule(sched)
        loaded = store.load_schedule("daily-morning")
        assert loaded is not None
        assert loaded.business_id == "artemea-001"

    def test_list_schedules_for_business(self):
        from app.brain.config import ReportSchedule, InMemoryConfigStore

        store = InMemoryConfigStore()
        for i, sch in enumerate(["0 9 * * *", "0 18 * * *"]):
            store.save_schedule(ReportSchedule(
                schedule_id=f"sched-{i}",
                business_id="artemea-001",
                cron_expression=sch,
                report_type="daily",
            ))
        # different business
        store.save_schedule(ReportSchedule(
            schedule_id="other-sched",
            business_id="other-biz",
            cron_expression="0 8 * * *",
            report_type="daily",
        ))
        schedules = store.list_schedules("artemea-001")
        assert len(schedules) == 2
        assert all(s.business_id == "artemea-001" for s in schedules)

    def test_overwrite_existing_config(self):
        from app.brain.config import BusinessConfig, InMemoryConfigStore

        store = InMemoryConfigStore()
        cfg1 = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea Old",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
        )
        cfg2 = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea New",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
        )
        store.save_business_config(cfg1)
        store.save_business_config(cfg2)
        loaded = store.load_business_config("artemea-001")
        assert loaded.business_name == "Artemea New"

    def test_delete_business_config(self):
        from app.brain.config import BusinessConfig, InMemoryConfigStore

        store = InMemoryConfigStore()
        cfg = BusinessConfig(
            business_id="artemea-001",
            business_name="Artemea",
            owner_phone="+5491112345678",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
        )
        store.save_business_config(cfg)
        store.delete_business_config("artemea-001")
        assert store.load_business_config("artemea-001") is None

    def test_delete_schedule(self):
        from app.brain.config import ReportSchedule, InMemoryConfigStore

        store = InMemoryConfigStore()
        sched = ReportSchedule(
            schedule_id="s1",
            business_id="artemea-001",
            cron_expression="0 9 * * *",
            report_type="daily",
        )
        store.save_schedule(sched)
        store.delete_schedule("s1")
        assert store.load_schedule("s1") is None

    def test_list_all_business_configs(self):
        from app.brain.config import BusinessConfig, InMemoryConfigStore

        store = InMemoryConfigStore()
        for bid, name in [("biz-1", "Alpha"), ("biz-2", "Beta")]:
            store.save_business_config(BusinessConfig(
                business_id=bid,
                business_name=name,
                owner_phone="+5491112345678",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
            ))
        all_cfgs = store.list_business_configs()
        assert len(all_cfgs) == 2
        ids = {c.business_id for c in all_cfgs}
        assert ids == {"biz-1", "biz-2"}
