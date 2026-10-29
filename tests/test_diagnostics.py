"""Tests for redacted Huawei HG612 diagnostics."""

from types import SimpleNamespace

from custom_components.huawei_hg612.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redact_connection_data_and_raw_output(fake_coordinator):
    entry = SimpleNamespace(
        data={
            "host": "192.168.50.2",
            "username": "admin",
            "password": "secret",
            "scan_interval": 60,
        },
        options={"scan_interval": 120},
        runtime_data=fake_coordinator,
    )

    result = await async_get_config_entry_diagnostics(None, entry)
    rendered = repr(result)

    assert "192.168.50.2" not in rendered
    assert "admin" not in rendered
    assert "secret" not in rendered
    assert "raw_output" not in result["statistics"]
    assert result["statistics"]["status"] == "Showtime"
    assert result["statistics"]["ignored_detail_line_count"] == 6
