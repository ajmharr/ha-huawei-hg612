"""Tests for integration setup and unloading."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.huawei_hg612 import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)


async def test_setup_creates_coordinator_and_forwards_platforms():
    coordinator = SimpleNamespace(async_config_entry_first_refresh=AsyncMock())
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock())
    )
    entry = SimpleNamespace(
        runtime_data=None,
        async_on_unload=MagicMock(),
        add_update_listener=MagicMock(return_value="remove-listener"),
    )

    with patch(
        "custom_components.huawei_hg612.coordinator.HuaweiHG612DataUpdateCoordinator",
        return_value=coordinator,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is coordinator
    coordinator.async_config_entry_first_refresh.assert_awaited_once_with()
    entry.async_on_unload.assert_called_once_with("remove-listener")
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, PLATFORMS
    )


async def test_unload_forwards_to_home_assistant():
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=True)
        )
    )
    entry = SimpleNamespace()

    assert await async_unload_entry(hass, entry) is True
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
