"""Shared entity support for Huawei HG612."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HuaweiHG612DataUpdateCoordinator


class HuaweiHG612Entity(CoordinatorEntity[HuaweiHG612DataUpdateCoordinator]):
    """Base class for Huawei HG612 coordinator entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HuaweiHG612DataUpdateCoordinator, entity_key: str
    ) -> None:
        """Initialize a stable modem entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        identity = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{identity}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=MODEL,
        )

