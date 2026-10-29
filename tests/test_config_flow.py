"""Tests for the Huawei HG612 config and options flows."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.huawei_hg612.config_flow import (
    HuaweiHG612ConfigFlow,
    HuaweiHG612OptionsFlow,
)
from custom_components.huawei_hg612.const import CONF_SCAN_INTERVAL
from custom_components.huawei_hg612.exceptions import AuthenticationError
from custom_components.huawei_hg612.models import CommandResponse


def _input():
    return {
        CONF_HOST: "192.168.50.2",
        CONF_USERNAME: "runtime-user",
        CONF_PASSWORD: "runtime-password",
        CONF_SCAN_INTERVAL: 60,
    }


async def test_user_form_defaults():
    flow = HuaweiHG612ConfigFlow()

    result = await flow.async_step_user()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_successful_user_flow_validates_and_creates_entry():
    flow = HuaweiHG612ConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()

    with patch(
        "custom_components.huawei_hg612.config_flow.HuaweiHG612Client.get_statistics",
        AsyncMock(return_value=CommandResponse("Status: Showtime")),
    ) as get_statistics:
        result = await flow.async_step_user(_input())

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.50.2"
    assert result["data"] == _input()
    get_statistics.assert_awaited_once()
    flow.async_set_unique_id.assert_awaited_once_with("192.168.50.2")
    flow._abort_if_unique_id_configured.assert_called_once_with()


async def test_invalid_credentials_are_reported():
    flow = HuaweiHG612ConfigFlow()
    with patch(
        "custom_components.huawei_hg612.config_flow.HuaweiHG612Client.get_statistics",
        AsyncMock(side_effect=AuthenticationError("rejected")),
    ):
        result = await flow.async_step_user(_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert "runtime-password" not in repr(result)


async def test_connection_error_is_reported():
    flow = HuaweiHG612ConfigFlow()
    with patch(
        "custom_components.huawei_hg612.config_flow.HuaweiHG612Client.get_statistics",
        AsyncMock(side_effect=OSError("offline")),
    ):
        result = await flow.async_step_user(_input())

    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_updates_poll_interval():
    flow = HuaweiHG612OptionsFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_get_known_entry=lambda _: SimpleNamespace(
                options={}, data={CONF_SCAN_INTERVAL: 60}
            )
        )
    )
    flow.handler = "entry-id"

    form = await flow.async_step_init()
    result = await flow.async_step_init({CONF_SCAN_INTERVAL: 120})

    assert form["type"] is FlowResultType.FORM
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 120}
