"""Data update coordinator for the Huawei HG612 integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HuaweiHG612Client
from .const import CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .exceptions import AuthenticationError, HuaweiHG612Error
from .models import DslStatistics
from .parser import parse_xdsl_stats

_LOGGER = logging.getLogger(__name__)


class HuaweiHG612DataUpdateCoordinator(DataUpdateCoordinator[DslStatistics]):
    """Coordinate one efficient modem poll for all HG612 entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = HuaweiHG612Client(
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            port=DEFAULT_PORT,
            # A transport close avoids sending any command beyond the two
            # read-only commands validated against the modem.
            logout_commands=(),
        )

    async def _async_update_data(self) -> DslStatistics:
        """Fetch and parse one complete modem response."""
        try:
            response = await self.client.get_statistics()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("HG612 authentication failed") from err
        except (HuaweiHG612Error, OSError) as err:
            raise UpdateFailed(f"Unable to retrieve HG612 statistics: {err}") from err

        return parse_xdsl_stats(response)

