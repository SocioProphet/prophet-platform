"""The driver layer: the virtual simulator, and the registry that refuses to pretend."""
from __future__ import annotations

import copy

import pytest

from device_service import contract
from device_service.drivers import (
    DRIVERS,
    DriverUnavailable,
    VirtualRoomSensorDriver,
    build_driver,
)


def test_only_the_virtual_driver_ships():
    """Stated plainly rather than implied: this build has ONE driver, and it simulates.
    If a real protocol driver is ever added, this test is what makes that a deliberate,
    reviewed change instead of a quiet one."""
    assert sorted(DRIVERS) == ["virtual"]


def test_a_profile_with_no_registered_driver_is_refused(ble_profile):
    """A ble-gatt profile on a build with no BLE transport must not start a service that
    polls nothing behind a green /healthz."""
    with pytest.raises(DriverUnavailable, match="no driver registered for protocol 'ble-gatt'"):
        build_driver(ble_profile, "urn:srcos:device:th100_bed2")


def test_the_refusal_names_the_seam(ble_profile):
    with pytest.raises(DriverUnavailable, match="ble.py"):
        build_driver(ble_profile, "urn:srcos:device:th100_bed2")


def test_a_driver_producing_undeclared_metrics_is_refused(virtual_profile):
    class Rogue:
        metrics = ["temperature", "smugness"]

        def poll(self):  # pragma: no cover - never reached
            return []

    DRIVERS["rogue-test"] = lambda profile, device_ref, options: Rogue()
    rogue_profile = copy.deepcopy(virtual_profile)
    rogue_profile["protocol"] = "virtual"
    try:
        DRIVERS["virtual-rogue"] = lambda profile, device_ref, options: Rogue()
        with pytest.raises(DriverUnavailable, match="unattributable by construction"):
            build_driver({**rogue_profile, "protocol": "virtual-rogue"}, "urn:srcos:device:x")
    finally:
        DRIVERS.pop("rogue-test", None)
        DRIVERS.pop("virtual-rogue", None)


# ------------------------------------------------------------------ the simulator
def test_the_virtual_driver_is_deterministic(virtual_profile):
    a = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    b = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    for _ in range(10):
        assert [(s.metric, s.value) for s in a.poll()] == [(s.metric, s.value) for s in b.poll()]


def test_a_different_seed_gives_a_different_stream(virtual_profile):
    a = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    b = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=99)
    assert [s.value for s in a.poll()] != [s.value for s in b.poll()]


def test_two_devices_on_one_profile_do_not_move_in_lockstep(virtual_profile):
    a = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    b = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_02", seed=42)
    assert [s.value for s in a.poll()] != [s.value for s in b.poll()]


def test_simulated_values_stay_well_inside_the_declared_range(virtual_profile):
    """A simulator that touched the range boundary would make the must-be-zero
    validation_failures counter flap and train everyone to ignore it."""
    driver = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    declared = {m["metric"]: m for m in virtual_profile["metrics"]}
    for _ in range(2000):
        for sample in driver.poll():
            spec = declared[sample.metric]
            if spec["valueType"] == "boolean":
                assert isinstance(sample.value, bool)
                continue
            assert spec["minimum"] < sample.value < spec["maximum"]


def test_simulated_values_are_of_the_declared_type(virtual_profile):
    driver = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    declared = {m["metric"]: m for m in virtual_profile["metrics"]}
    for sample in driver.poll():
        expected = declared[sample.metric]["valueType"]
        if expected == "boolean":
            assert isinstance(sample.value, bool)
        elif expected == "integer":
            assert isinstance(sample.value, int) and not isinstance(sample.value, bool)
        else:
            assert isinstance(sample.value, float)


def test_every_simulated_sample_survives_the_contract_gate(virtual_profile):
    """The end-to-end claim: what this driver produces is admissible. 3000 samples, and
    validation_failures must be exactly zero — the same bar /healthz reports."""
    driver = VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42)
    failures = 0
    checked = 0
    for tick in range(1, 1001):
        for sample in driver.poll():
            reading = contract.build_reading(
                profile=virtual_profile,
                device_ref="urn:srcos:device:room_sensor_01",
                metric=sample.metric,
                value=sample.value,
                quality=sample.quality,
                observed_at="2026-07-29T09:15:00.000Z",
                received_at="2026-07-29T09:15:00.042Z",
                wall_time="2026-07-29T09:15:00.042Z",
                logical_time=tick,
                sequence_ref=tick,
                workspace_ref="urn:srcos:workspace:citizen_home_demo",
                branch_ref="urn:srcos:branch:home_main",
                actor_ref="urn:srcos:agent:device_service",
                raw_payload=sample.raw,
            )
            try:
                contract.validate_reading(reading, virtual_profile)
                checked += 1
            except contract.ContractError:
                failures += 1
    assert checked == 3000
    assert failures == 0


def test_drop_every_n_produces_typed_absences(virtual_profile):
    driver = VirtualRoomSensorDriver(
        virtual_profile, "urn:srcos:device:room_sensor_01", seed=42, drop_every_n=3
    )
    qualities = []
    for _ in range(6):
        qualities.append({s.quality for s in driver.poll()})
    assert qualities[2] == {"unavailable"}
    assert qualities[5] == {"unavailable"}
    assert qualities[0] == {"ok"}
    dropped = [s for _ in range(1) for s in driver.poll()]  # tick 7 — not a drop
    assert all(s.quality == "ok" for s in dropped)


def test_absences_carry_a_kind_a_driver_can_actually_attribute(virtual_profile):
    driver = VirtualRoomSensorDriver(
        virtual_profile, "urn:srcos:device:room_sensor_01", seed=42, drop_every_n=1
    )
    for sample in driver.poll():
        assert sample.absence_kind in contract.DRIVER_ABSENCE_KINDS
