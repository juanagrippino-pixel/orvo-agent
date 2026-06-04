"""Core Orvo Brain control-plane models."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Evidence(BaseModel):
    """A source citation for any metric or insight."""

    source: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    url: HttpUrl | None = None


class Metric(BaseModel):
    """A cited business metric normalized from any connector."""

    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    value: float | int | str
    unit: str | None = None
    evidence: list[Evidence] = Field(..., min_length=1)


class Insight(BaseModel):
    """A deterministic operational finding with cited evidence."""

    severity: Literal["info", "warning", "critical"]
    title: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    recommended_action: str = Field(..., min_length=1)
    evidence: list[Evidence] = Field(..., min_length=1)

    @field_validator("evidence")
    @classmethod
    def require_evidence(cls, value: list[Evidence]) -> list[Evidence]:
        if not value:
            raise ValueError("insights must include at least one evidence source")
        return value


class InsightThresholds(BaseModel):
    """Per-business tunable thresholds for the insight engine."""

    revenue_drop_threshold: float = 0.15
    stock_threshold: int = 5
    unanswered_threshold: int = 5
    roas_warning_threshold: float = 3.0
    channel_mix_imbalance_threshold: float = 0.40


class DailyReport(BaseModel):
    """WhatsApp-ready operational report payload."""

    business_name: str = Field(..., min_length=1)
    report_date: date
    metrics: list[Metric] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
