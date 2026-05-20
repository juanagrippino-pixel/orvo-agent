"""Orvo Brain — Business config and report-schedule models with in-memory storage.

Design notes
------------
* Pure Pydantic v2 models — no external DB dependency.
* All required fields are enforced by Pydantic (no Optional sentinel tricks).
* JSON serialisation helpers (config_to_json / config_from_json, schedule_to_json /
  schedule_from_json) make it trivial to persist to SQLite, Redis, or a file later.
* InMemoryConfigStore is the canonical store for tests and lightweight deployments.
  Swap with a SQLiteConfigStore or any duck-typed replacement without changing callers.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.brain.models import InsightThresholds


# ---------------------------------------------------------------------------
# ConnectorConfig
# ---------------------------------------------------------------------------


class ConnectorConfig(BaseModel):
    """Configuration for one data-source connector attached to a business."""

    connector_id: str = Field(..., min_length=1)
    connector_type: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)
    enabled: bool = True


# ---------------------------------------------------------------------------
# BusinessConfig
# ---------------------------------------------------------------------------


class BusinessConfig(BaseModel):
    """Top-level configuration record for an Orvo-managed business."""

    business_id: str = Field(..., min_length=1)
    business_name: str = Field(..., min_length=1)
    owner_phone: str = Field(..., min_length=1)
    timezone: str = Field(..., min_length=1)
    currency: str = Field(..., min_length=1)
    connectors: list[ConnectorConfig] = Field(default_factory=list)
    insight_thresholds: InsightThresholds = Field(default_factory=InsightThresholds)

    @field_validator("owner_phone")
    @classmethod
    def phone_must_start_with_plus(cls, value: str) -> str:
        if not value.startswith("+"):
            raise ValueError("owner_phone must start with '+' (E.164 format)")
        return value

    @model_validator(mode="after")
    def connector_ids_must_be_unique(self) -> "BusinessConfig":
        seen: set[str] = set()
        for conn in self.connectors:
            if conn.connector_id in seen:
                raise ValueError(
                    f"Duplicate connector_id '{conn.connector_id}' in connectors list"
                )
            seen.add(conn.connector_id)
        return self


# ---------------------------------------------------------------------------
# ReportSchedule
# ---------------------------------------------------------------------------

ReportType = Literal["daily", "weekly", "monthly"]


class ReportSchedule(BaseModel):
    """Cron-based schedule that triggers report generation for a business."""

    schedule_id: str = Field(..., min_length=1)
    business_id: str = Field(..., min_length=1)
    cron_expression: str = Field(..., min_length=1)
    report_type: ReportType
    enabled: bool = True


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------


def config_to_json(cfg: BusinessConfig) -> str:
    """Serialise a BusinessConfig to a JSON string."""
    return cfg.model_dump_json()


def config_from_json(raw: str) -> BusinessConfig:
    """Deserialise a BusinessConfig from a JSON string."""
    return BusinessConfig.model_validate(json.loads(raw))


def schedule_to_json(sched: ReportSchedule) -> str:
    """Serialise a ReportSchedule to a JSON string."""
    return sched.model_dump_json()


def schedule_from_json(raw: str) -> ReportSchedule:
    """Deserialise a ReportSchedule from a JSON string."""
    return ReportSchedule.model_validate(json.loads(raw))


# ---------------------------------------------------------------------------
# InMemoryConfigStore
# ---------------------------------------------------------------------------


class InMemoryConfigStore:
    """Thread-unsafe but dependency-free store for unit tests and prototyping.

    Replace with a SQLite- or Redis-backed implementation for production.
    All methods mirror each other (save/load/delete/list) so callers can be
    written against the same interface regardless of backend.
    """

    def __init__(self) -> None:
        self._configs: dict[str, BusinessConfig] = {}
        self._schedules: dict[str, ReportSchedule] = {}

    # -- BusinessConfig CRUD -------------------------------------------------

    def save_business_config(self, cfg: BusinessConfig) -> None:
        self._configs[cfg.business_id] = cfg

    def load_business_config(self, business_id: str) -> BusinessConfig | None:
        return self._configs.get(business_id)

    def delete_business_config(self, business_id: str) -> None:
        self._configs.pop(business_id, None)

    def list_business_configs(self) -> list[BusinessConfig]:
        return list(self._configs.values())

    # -- ReportSchedule CRUD -------------------------------------------------

    def save_schedule(self, sched: ReportSchedule) -> None:
        self._schedules[sched.schedule_id] = sched

    def load_schedule(self, schedule_id: str) -> ReportSchedule | None:
        return self._schedules.get(schedule_id)

    def delete_schedule(self, schedule_id: str) -> None:
        self._schedules.pop(schedule_id, None)

    def list_schedules(self, business_id: str) -> list[ReportSchedule]:
        return [s for s in self._schedules.values() if s.business_id == business_id]
