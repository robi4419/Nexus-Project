"""Shared pytest fixtures (pytest loads this file automatically)."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def jobicy_page() -> dict:
    """A small Jobicy API response (one real job, trimmed, and one made-up job)."""
    return json.loads((FIXTURES_DIR / "jobicy_page.json").read_text(encoding="utf-8"))


@pytest.fixture
def arbeitnow_page() -> dict:
    """Page 1 of a real Arbeitnow response, trimmed to two jobs (one on-site, one remote) with short descriptions."""
    return json.loads((FIXTURES_DIR / "arbeitnow_page.json").read_text(encoding="utf-8"))


@pytest.fixture
def himalayas_page() -> dict:
    """A Himalayas response with four made-up jobs: two Tech, one Sales, one without a parent category."""
    return json.loads((FIXTURES_DIR / "himalayas_page.json").read_text(encoding="utf-8"))


@pytest.fixture
def frankfurter_rates() -> dict:
    """A real Frankfurter API response: USD-based ECB rates for 2026-10-14."""
    return json.loads((FIXTURES_DIR / "frankfurter_rates.json").read_text(encoding="utf-8"))
