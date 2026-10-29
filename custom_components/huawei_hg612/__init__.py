"""Huawei HG612 Home Assistant integration."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import HuaweiHG612DataUpdateCoordinator

    HuaweiHG612ConfigEntry = ConfigEntry[HuaweiHG612DataUpdateCoordinator]
else:
    HomeAssistant = Any
    HuaweiHG612ConfigEntry = Any

PLATFORMS: tuple[str, ...] = ("sensor", "binary_sensor")


async def async_setup_entry(
    hass: HomeAssistant, entry: HuaweiHG612ConfigEntry
) -> bool:
    """Set up Huawei HG612 from a config entry."""
    from .coordinator import HuaweiHG612DataUpdateCoordinator  # noqa: PLC0415

    coordinator = HuaweiHG612DataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HuaweiHG612ConfigEntry
) -> bool:
    """Unload a Huawei HG612 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: HuaweiHG612ConfigEntry
) -> None:
    """Reload after the polling interval option changes."""
    await hass.config_entries.async_reload(entry.entry_id)

