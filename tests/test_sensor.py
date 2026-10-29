"""Tests for Huawei HG612 sensors."""

from dataclasses import replace

from homeassistant.components.sensor import SensorStateClass

from custom_components.huawei_hg612.sensor import HuaweiHG612Sensor, SENSORS


def _sensor(coordinator, key):
    description = next(item for item in SENSORS if item.key == key)
    return HuaweiHG612Sensor(coordinator, description)


def test_all_required_sensors_are_declared():
    keys = {description.key for description in SENSORS}

    assert len(keys) == 27
    assert {
        "downstream_sync_speed",
        "upstream_sync_speed",
        "downstream_attainable_speed",
        "upstream_attainable_speed",
        "downstream_snr_margin",
        "upstream_snr_margin",
        "downstream_line_attenuation",
        "upstream_line_attenuation",
        "downstream_transmit_power",
        "upstream_transmit_power",
        "dsl_uptime",
        "downstream_fec",
        "upstream_fec",
        "downstream_crc",
        "upstream_crc",
        "downstream_es",
        "upstream_es",
        "downstream_ses",
        "upstream_ses",
        "downstream_uas",
        "upstream_uas",
        "downstream_los",
        "upstream_los",
        "downstream_lof",
        "upstream_lof",
        "dsl_mode",
        "vdsl_profile",
    } == keys


def test_sensor_values_and_stable_unique_ids(fake_coordinator):
    speed = _sensor(fake_coordinator, "downstream_sync_speed")
    snr = _sensor(fake_coordinator, "upstream_snr_margin")
    fec = _sensor(fake_coordinator, "downstream_fec")

    assert speed.native_value == 15713
    assert snr.native_value == 6.4
    assert fec.native_value == 14634
    assert speed.unique_id == "192.168.50.2_downstream_sync_speed"
    assert fec.entity_description.state_class is SensorStateClass.TOTAL_INCREASING


def test_firmware_placeholder_upstream_attenuation_is_unavailable(fake_coordinator):
    sensor = _sensor(fake_coordinator, "upstream_line_attenuation")

    assert sensor.native_value is None
    assert sensor.available is False


def test_counter_reset_is_exposed_without_inventing_continuity(fake_coordinator):
    sensor = _sensor(fake_coordinator, "downstream_fec")
    total = fake_coordinator.data.counter_sections["total"]
    counters = dict(total.counters)
    counters["FEC"] = replace(counters["FEC"], downstream=2)
    fake_coordinator.data = replace(
        fake_coordinator.data,
        counter_sections={
            **fake_coordinator.data.counter_sections,
            "total": replace(total, counters=counters),
        },
    )

    assert sensor.native_value == 2


def test_missing_value_and_failed_poll_make_sensor_unavailable(fake_coordinator):
    sensor = _sensor(fake_coordinator, "downstream_sync_speed")
    fake_coordinator.data = replace(fake_coordinator.data, sync_rate_kbps=None)
    assert sensor.available is False

    fake_coordinator.data = replace(fake_coordinator.data, sync_rate_kbps=(10, 5))
    fake_coordinator.last_update_success = False
    assert sensor.available is False
