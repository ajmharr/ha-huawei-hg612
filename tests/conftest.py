"""Shared fixture loaders."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    """Return a named synthetic fixture without its explanatory comment."""

    def load(name: str) -> str:
        lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
        return "\n".join(line for line in lines if not line.startswith("# Synthetic"))

    return load

