"""Validate the runtime-docs example fixtures.

These tests are intentionally narrow: they only assert that the bundled
example files are well-formed inputs for the public adapters/config models.
They do NOT exercise live network calls.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.brain.adapters.csv_file import build_daily_report_from_csv_file
from app.brain.config import BusinessConfig

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
DOCS_FILE = Path(__file__).resolve().parents[1] / "docs" / "orvo-brain-runtime.md"


# ---------------------------------------------------------------------------
# JSON BusinessConfig examples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected_connector_type",
    [
        ("google_sheets_business_config.json", "google_sheets"),
        ("tiendanube_business_config.json", "tiendanube"),
    ],
)
def test_business_config_example_parses(filename: str, expected_connector_type: str) -> None:
    raw = (EXAMPLES_DIR / filename).read_text(encoding="utf-8")
    payload = json.loads(raw)
    cfg = BusinessConfig.model_validate(payload)

    assert cfg.business_id
    assert cfg.owner_phone.startswith("+"), "owner_phone must be E.164"
    assert cfg.connectors, "example must declare at least one connector"
    assert cfg.connectors[0].connector_type == expected_connector_type
    assert cfg.connectors[0].enabled is True


def test_tiendanube_example_uses_placeholder_token() -> None:
    """Guard against accidentally committing real Tiendanube tokens."""
    raw = (EXAMPLES_DIR / "tiendanube_business_config.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    token = payload["connectors"][0]["params"]["access_token"]
    assert token in {"[REDACTED]", "tn_test_token"}, (
        "tiendanube example must use a placeholder token, not a real one"
    )


# ---------------------------------------------------------------------------
# CSV example
# ---------------------------------------------------------------------------


def test_artemea_daily_csv_example_drives_csv_adapter() -> None:
    csv_path = EXAMPLES_DIR / "artemea_daily.csv"
    report = build_daily_report_from_csv_file(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        csv_path=str(csv_path),
    )

    by_key = {metric.key: metric for metric in report.metrics}
    assert "revenue_today" in by_key
    assert "revenue_baseline" in by_key, (
        "CSV example should provide >=7 prior days so a baseline can be computed"
    )
    assert by_key["revenue_today"].value == 260000
    assert by_key["orders_today"].value == 18

    # All metrics must carry CSV-sourced evidence pointing at the example file.
    for metric in report.metrics:
        assert metric.evidence, f"metric {metric.key} missing evidence"
        assert metric.evidence[0].source == "csv"
        assert "artemea_daily.csv" in metric.evidence[0].label


# ---------------------------------------------------------------------------
# Docs file sanity
# ---------------------------------------------------------------------------


def test_runtime_doc_links_resolve_to_existing_examples() -> None:
    """Every relative `examples/...` link in the docs must point at a real file."""
    docs = DOCS_FILE.read_text(encoding="utf-8")
    # Look for `../examples/<file>` references used inside docs/.
    referenced = {
        line.split("(../examples/", 1)[1].split(")", 1)[0]
        for line in docs.splitlines()
        if "(../examples/" in line
    }
    assert referenced, "docs should reference at least one example"
    for name in referenced:
        assert (EXAMPLES_DIR / name).exists(), f"missing example referenced from docs: {name}"
