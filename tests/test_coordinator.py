"""Tests for coordinator polling and error conversion."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.huawei_hg612.const import CONF_SCAN_INTERVAL
from custom_components.huawei_hg612.coordinator import HuaweiHG612DataUpdateCoordinator
from custom_components.huawei_hg612.exceptions import (
    AuthenticationError,
    IncompleteResponseError,
)
from custom_components.huawei_hg612.models import CommandResponse


def _coordinator_with_client(client):
    coordinator = object.__new__(HuaweiHG612DataUpdateCoordinator)
    coordinator.client = client
    return coordinator


async def test_coordinator_parses_successful_response(fixture_text):
    client = SimpleNamespace(
        get_statistics=AsyncMock(
            return_value=CommandResponse(fixture_text("stats_showtime_synthetic.txt"))
        )
    )
    coordinator = _coordinator_with_client(client)

    data = await coordinator._async_update_data()

    assert data.status == "Showtime"
    assert data.sync_rate_kbps == (15713, 1177)


async def test_coordinator_converts_authentication_failure():
    coordinator = _coordinator_with_client(
        SimpleNamespace(
            get_statistics=AsyncMock(side_effect=AuthenticationError("rejected"))
        )
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_converts_incomplete_response_to_update_failure():
    coordinator = _coordinator_with_client(
        SimpleNamespace(
            get_statistics=AsyncMock(
                side_effect=IncompleteResponseError("truncated", "Status: Showtime")
            )
        )
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


def test_coordinator_uses_configured_interval_and_read_only_client():
    hass = MagicMock()
    entry = SimpleNamespace(
        options={CONF_SCAN_INTERVAL: 120},
        async_on_unload=MagicMock(),
        data={
            CONF_HOST: "192.168.50.2",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
            CONF_SCAN_INTERVAL: 60,
        },
    )

    coordinator = HuaweiHG612DataUpdateCoordinator(hass, entry)

    assert coordinator.update_interval.total_seconds() == 120
    assert coordinator.client.host == "192.168.50.2"
    assert coordinator.client._logout_commands == ()
