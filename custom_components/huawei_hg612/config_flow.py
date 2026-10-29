"""Config flow for the Huawei HG612 integration."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import HuaweiHG612Client
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .exceptions import AuthenticationError, HuaweiHG612Error


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=values.get(CONF_HOST, "192.168.50.2")): vol.All(
                cv.string, vol.Strip, vol.Length(min=1)
            ),
            vol.Required(CONF_USERNAME, default=values.get(CONF_USERNAME, "")): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
        }
    )


class HuaweiHG612ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Huawei HG612 config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial user configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            client = HuaweiHG612Client(
                host,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                logout_commands=(),
            )
            try:
                await client.get_statistics()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (HuaweiHG612Error, OSError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flows must remain usable
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(host.casefold())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=host, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return HuaweiHG612OptionsFlow()


class HuaweiHG612OptionsFlow(config_entries.OptionsFlow):
    """Manage Huawei HG612 options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage polling interval options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
