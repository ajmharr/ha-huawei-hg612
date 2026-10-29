"""Shared fixture loaders."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.huawei_hg612.models import CommandResponse
from custom_components.huawei_hg612.parser import parse_xdsl_stats

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    """Return a named synthetic fixture without its explanatory comment."""

    def load(name: str) -> str:
        lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
        return "\n".join(line for line in lines if not line.startswith("# Synthetic"))

    return load


@pytest.fixture
def parsed_stats(fixture_text):
    """Return parsed representative HG612 Showtime statistics."""
    return parse_xdsl_stats(CommandResponse(fixture_text("stats_showtime_synthetic.txt")))


@pytest.fixture
def fake_coordinator(parsed_stats):
    """Return the minimum coordinator interface required by entities."""
    entry = SimpleNamespace(unique_id="192.168.50.2", entry_id="entry-id")
    return SimpleNamespace(
        data=parsed_stats,
        last_update_success=True,
        config_entry=entry,
        async_add_listener=lambda *args: lambda: None,
    )

