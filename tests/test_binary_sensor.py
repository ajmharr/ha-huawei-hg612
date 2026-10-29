"""Tests for the physical DSL synchronization sensor."""

from dataclasses import replace

from custom_components.huawei_hg612.binary_sensor import (
    HuaweiHG612SynchronizationSensor,
)


def test_showtime_means_dsl_synchronized(fake_coordinator):
    sensor = HuaweiHG612SynchronizationSensor(fake_coordinator)

    assert sensor.is_on is True
    assert sensor.unique_id == "192.168.50.2_dsl_synchronized"
    assert sensor.device_class is None


def test_non_showtime_is_not_synchronized(fake_coordinator):
    sensor = HuaweiHG612SynchronizationSensor(fake_coordinator)
    fake_coordinator.data = replace(fake_coordinator.data, status="Idle")

    assert sensor.is_on is False


def test_missing_status_or_failed_poll_is_unavailable(fake_coordinator):
    sensor = HuaweiHG612SynchronizationSensor(fake_coordinator)
    fake_coordinator.data = replace(fake_coordinator.data, status=None)
    assert sensor.available is False

    fake_coordinator.data = replace(fake_coordinator.data, status="Showtime")
    fake_coordinator.last_update_success = False
    assert sensor.available is False
