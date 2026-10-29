"""Diagnostics support for Huawei HG612."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import HuaweiHG612ConfigEntry

_TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HuaweiHG612ConfigEntry
) -> dict[str, Any]:
    """Return redacted config and normalized modem diagnostics."""
    stats = asdict(entry.runtime_data.data)
    stats.pop("raw_output", None)
    stats["ignored_detail_line_count"] = len(stats.pop("ignored_detail_lines", ()))
    return {
        "config_entry": async_redact_data(dict(entry.data), _TO_REDACT),
        "options": dict(entry.options),
        "last_update_success": entry.runtime_data.last_update_success,
        "statistics": stats,
    }
