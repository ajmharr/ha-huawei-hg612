"""Sensor entities for Huawei HG612 DSL statistics."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HuaweiHG612ConfigEntry
from .entity import HuaweiHG612Entity
from .models import DslStatistics


def _rate(direction: int, attainable: bool = False) -> Callable[[DslStatistics], Any]:
    def value(stats: DslStatistics) -> Any:
        pair = stats.attainable_rate_kbps if attainable else stats.sync_rate_kbps
        return None if pair is None else pair[direction]

    return value


def _directional(attribute: str, direction: str) -> Callable[[DslStatistics], Any]:
    def value(stats: DslStatistics) -> Any:
        pair = getattr(stats, attribute)
        return None if pair is None else getattr(pair, direction)

    return value


def _counter(name: str, direction: str) -> Callable[[DslStatistics], Any]:
    def value(stats: DslStatistics) -> Any:
        section = stats.counter_sections.get("total")
        if section is None or (pair := section.counters.get(name)) is None:
            return None
        return getattr(pair, direction)

    return value


def _upstream_attenuation(stats: DslStatistics) -> float | None:
    """Return upstream attenuation only when the modem reports a valid value."""
    if stats.attenuation_db is None:
        return None
    value = stats.attenuation_db.upstream
    # B030SP08 reports 0.0 as a placeholder rather than a measurement.
    return None if value in (None, 0.0) else value


@dataclass(frozen=True, kw_only=True)
class HuaweiHG612SensorEntityDescription(SensorEntityDescription):
    """Describe a Huawei HG612 sensor."""

    value_fn: Callable[[DslStatistics], Any]


SENSORS: tuple[HuaweiHG612SensorEntityDescription, ...] = (
    HuaweiHG612SensorEntityDescription(
        key="downstream_sync_speed",
        translation_key="downstream_sync_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_rate(0),
    ),
    HuaweiHG612SensorEntityDescription(
        key="upstream_sync_speed",
        translation_key="upstream_sync_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_rate(1),
    ),
    HuaweiHG612SensorEntityDescription(
        key="downstream_attainable_speed",
        translation_key="downstream_attainable_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_rate(0, attainable=True),
    ),
    HuaweiHG612SensorEntityDescription(
        key="upstream_attainable_speed",
        translation_key="upstream_attainable_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_rate(1, attainable=True),
    ),
    *(
        HuaweiHG612SensorEntityDescription(
            key=f"{direction}_snr_margin",
            translation_key=f"{direction}_snr_margin",
            native_unit_of_measurement="dB",
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=_directional("snr_db", direction),
        )
        for direction in ("downstream", "upstream")
    ),
    HuaweiHG612SensorEntityDescription(
        key="downstream_line_attenuation",
        translation_key="downstream_line_attenuation",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_directional("attenuation_db", "downstream"),
    ),
    HuaweiHG612SensorEntityDescription(
        key="upstream_line_attenuation",
        translation_key="upstream_line_attenuation",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_upstream_attenuation,
    ),
    *(
        HuaweiHG612SensorEntityDescription(
            key=f"{direction}_transmit_power",
            translation_key=f"{direction}_transmit_power",
            native_unit_of_measurement="dBm",
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=_directional("power_dbm", direction),
        )
        for direction in ("downstream", "upstream")
    ),
    HuaweiHG612SensorEntityDescription(
        key="dsl_uptime",
        translation_key="dsl_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.link_duration_seconds,
    ),
    *(
        HuaweiHG612SensorEntityDescription(
            key=f"{direction}_{counter.casefold()}",
            translation_key=f"{direction}_{counter.casefold()}",
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=_counter(counter, direction),
        )
        for counter, unit in (("FEC", "corrections"), ("CRC", "errors"))
        for direction in ("downstream", "upstream")
    ),
    *(
        HuaweiHG612SensorEntityDescription(
            key=f"{direction}_{counter.casefold()}",
            translation_key=f"{direction}_{counter.casefold()}",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=_counter(counter, direction),
        )
        for counter in ("ES", "SES", "UAS", "LOS", "LOF")
        for direction in ("downstream", "upstream")
    ),
    HuaweiHG612SensorEntityDescription(
        key="dsl_mode",
        translation_key="dsl_mode",
        value_fn=lambda stats: stats.mode,
    ),
    HuaweiHG612SensorEntityDescription(
        key="vdsl_profile",
        translation_key="vdsl_profile",
        value_fn=lambda stats: stats.profile,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HuaweiHG612ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Huawei HG612 sensors."""
    async_add_entities(
        HuaweiHG612Sensor(entry.runtime_data, description) for description in SENSORS
    )


class HuaweiHG612Sensor(HuaweiHG612Entity, SensorEntity):
    """A Huawei HG612 DSL statistic."""

    entity_description: HuaweiHG612SensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: HuaweiHG612SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the current parsed value without counter adjustment."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Require a successful poll and a value supported by the modem."""
        return super().available and self.native_value is not None

