"""Shared pytest fixtures (pytest loads this file automatically)."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def jobicy_page() -> dict:
    """A small Jobicy API response (one real job, trimmed, and one made-up job)."""
    return json.loads((FIXTURES_DIR / "jobicy_page.json").read_text(encoding="utf-8"))
