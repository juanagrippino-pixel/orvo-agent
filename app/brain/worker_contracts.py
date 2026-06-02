"""Explicit worker/adapter contracts for Orvo Brain connector execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.brain.models import DailyReport

ADAPTER_WORKER_STAGES = (
    "validate",
    "fetch",
    "build_report",
    "emit_metrics",
    "record_freshness",
)


@runtime_checkable
class DailyReportAdapter(Protocol):
    """Callable protocol every daily-report adapter factory must satisfy.

    Concrete adapters keep their connector-specific keyword signatures, but the
    worker boundary treats them as allowlisted kwargs -> ``DailyReport``.
    """

    def __call__(self, **kwargs: Any) -> DailyReport: ...


class AdapterWorkerContext(BaseModel):
    """Correlation-safe context passed through one connector worker run."""

    model_config = ConfigDict(frozen=True)

    business_id: str
    connector_id: str
    connector_type: str
    report_date: date
    run_id: str | None = None

    @property
    def correlation_id(self) -> str:
        if self.run_id:
            return f"{self.run_id}:{self.connector_id}"
        return f"{self.business_id}:{self.connector_id}:{self.report_date.isoformat()}"


class AdapterWorkerResult(BaseModel):
    """Normalized result emitted by connector workers after adapter execution."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    context: AdapterWorkerContext
    report: DailyReport
    merge_policy_version: str
    emitted_metric_keys: list[str] = Field(default_factory=list)
    freshness_state: str = "unknown"
    data_quality_warnings: list[str] = Field(default_factory=list)


AdapterFactoryT = TypeVar("AdapterFactoryT", bound=Callable[..., DailyReport])


def validate_daily_report_adapter(factory: AdapterFactoryT) -> AdapterFactoryT:
    """Return ``factory`` after checking the minimum adapter worker contract."""

    if not callable(factory):
        raise TypeError("daily report adapter factory is not callable")
    return factory
