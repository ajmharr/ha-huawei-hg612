"""Binary sensor for Huawei HG612 DSL synchronization."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HuaweiHG612ConfigEntry
from .entity import HuaweiHG612Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HuaweiHG612ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DSL synchronization binary sensor."""
    async_add_entities([HuaweiHG612SynchronizationSensor(entry.runtime_data)])


class HuaweiHG612SynchronizationSensor(HuaweiHG612Entity, BinarySensorEntity):
    """Report modem DSL synchronization, not internet connectivity."""

    _attr_translation_key = "dsl_synchronized"

    def __init__(self, coordinator) -> None:
        """Initialize the synchronization sensor."""
        super().__init__(coordinator, "dsl_synchronized")

    @property
    def is_on(self) -> bool | None:
        """Return whether the physical DSL line reports Showtime."""
        return self.coordinator.data.is_synchronized

    @property
    def available(self) -> bool:
        """Require a successful poll containing a DSL status."""
        return super().available and self.is_on is not None

