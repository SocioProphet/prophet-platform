"""The BLE GATT layer — decoders against the Bluetooth SIG formats, and the driver.

This is the part of the real-BLE seam that is REAL. The decoders are where the
interesting bugs live, and they are testable without a radio, so they are tested here
rather than deferred along with the transport.
"""
from __future__ import annotations

import struct

import pytest

from device_service import ble
from device_service.drivers import DriverError


# ---------------------------------------------------------------- 0x2A6E temperature
def test_temperature_decodes_sint16_at_hundredths():
    assert ble.decode_temperature(b"\x59\x08") == 21.37   # 2137 * 0.01
    assert ble.decode_temperature(b"\x00\x00") == 0.0


def test_temperature_is_SIGNED_and_that_is_the_whole_point():
    """0x2A6E is sint16. Read as uint16, -5.00 degC decodes to +650.36 — a plausible
    number that a -40..85 profile range would reject only by luck. The explicit '<h' is
    the fix; this test is what stops it silently becoming '<H' again."""
    payload = struct.pack("<h", -500)
    assert ble.decode_temperature(payload) == -5.0
    misread = struct.unpack("<H", payload)[0] * 0.01
    assert misread == pytest.approx(650.36)
    assert ble.decode_temperature(payload) != misread


def test_temperature_rejects_a_wrong_length_payload():
    for bad in (b"", b"\x59", b"\x59\x08\x00"):
        with pytest.raises(ble.DecodeError, match="exactly 2 bytes"):
            ble.decode_temperature(bad)


# ------------------------------------------------------------------- 0x2A6F humidity
def test_humidity_decodes_uint16_at_hundredths():
    assert ble.decode_humidity(b"\x7c\x15") == 55.0       # 5500 * 0.01
    assert ble.decode_humidity(b"\x10\x27") == 100.0      # 10000 * 0.01


def test_humidity_rejects_a_wrong_length_payload():
    with pytest.raises(ble.DecodeError, match="exactly 2 bytes"):
        ble.decode_humidity(b"\x7c")


# --------------------------------------------------------------------- 0x2A19 battery
def test_battery_decodes_uint8_percent():
    assert ble.decode_battery_level(b"\x57") == 87
    assert ble.decode_battery_level(b"\x00") == 0
    assert ble.decode_battery_level(b"\x64") == 100


def test_battery_rejects_out_of_spec_values():
    """A device reporting 255% is faulty. Passing it through would put nonsense in the
    graph with an `ok` quality attached."""
    with pytest.raises(ble.DecodeError, match="0..100 percent"):
        ble.decode_battery_level(b"\xff")


# ------------------------------------------------------------------ source addressing
def test_characteristic_is_extracted_from_the_profile_source_address(ble_profile):
    declared = {m["metric"]: m for m in ble_profile["metrics"]}
    assert ble.characteristic_of(declared["temperature"]["sourceAddress"]) == ble.TEMPERATURE_UUID
    assert ble.characteristic_of(declared["humidity.relative"]["sourceAddress"]) == ble.HUMIDITY_UUID
    assert ble.characteristic_of(declared["battery.level"]["sourceAddress"]) == ble.BATTERY_LEVEL_UUID


def test_a_non_gatt_source_address_is_rejected():
    with pytest.raises(ble.DecodeError, match="not a GATT source address"):
        ble.characteristic_of("virtual://room-sensor/temperature")
    with pytest.raises(ble.DecodeError, match="must be gatt://"):
        ble.characteristic_of("gatt://only-a-service")


def test_every_shipped_ble_profile_metric_has_a_decoder(ble_profile):
    """A profile may not declare a channel this driver cannot actually read."""
    for metric in ble_profile["metrics"]:
        uuid = ble.characteristic_of(metric["sourceAddress"])
        assert uuid in ble.DECODERS, f"{metric['metric']} declares an undecodable channel"


# ------------------------------------------------------------------------ the driver
class FakeTransport:
    """A test double for the ONE class that does not ship. Its existence here is the
    measure of the remaining distance: everything else is already written."""

    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def read_characteristic(self, uuid: str) -> bytes:
        value = self.payloads[uuid]
        if isinstance(value, Exception):
            raise value
        return value

    def disconnect(self) -> None:
        self.connected = False


def test_the_driver_reads_and_decodes_a_whole_device(ble_profile):
    transport = FakeTransport({
        ble.TEMPERATURE_UUID: struct.pack("<h", 2137),
        ble.HUMIDITY_UUID: struct.pack("<H", 5500),
        ble.BATTERY_LEVEL_UUID: b"\x57",
    })
    driver = ble.BleGattDriver(ble_profile, "urn:srcos:device:th100_bed2", transport)
    samples = {s.metric: s for s in driver.poll()}
    assert transport.connected
    assert samples["temperature"].value == 21.37
    assert samples["humidity.relative"].value == 55.0
    assert samples["battery.level"].value == 87
    assert all(s.quality == "ok" for s in samples.values())
    # The pre-decode bytes are kept, so a decode bug stays provable after the fact.
    assert samples["temperature"].raw == {"hex": "5908"}


def test_a_timeout_becomes_a_typed_absence_not_a_stale_value(ble_profile):
    transport = FakeTransport({
        ble.TEMPERATURE_UUID: struct.pack("<h", 2137),
        ble.HUMIDITY_UUID: TimeoutError("notify window elapsed"),
        ble.BATTERY_LEVEL_UUID: b"\x57",
    })
    driver = ble.BleGattDriver(ble_profile, "urn:srcos:device:th100_bed2", transport)
    samples = {s.metric: s for s in driver.poll()}
    absent = samples["humidity.relative"]
    assert absent.quality == "unavailable"
    assert absent.absence_kind == "timeout"
    assert absent.value is None
    # The other metrics still report: one silent characteristic is not a dead device.
    assert samples["temperature"].value == 21.37


def test_a_transport_error_is_typed_distinctly_from_a_timeout(ble_profile):
    transport = FakeTransport({
        ble.TEMPERATURE_UUID: ConnectionResetError("link dropped"),
        ble.HUMIDITY_UUID: struct.pack("<H", 5500),
        ble.BATTERY_LEVEL_UUID: b"\x57",
    })
    driver = ble.BleGattDriver(ble_profile, "urn:srcos:device:th100_bed2", transport)
    samples = {s.metric: s for s in driver.poll()}
    assert samples["temperature"].absence_kind == "transport_failure"


def test_an_undecodable_payload_is_a_FAULT_not_an_absence(ble_profile):
    """The device answered. Reporting that as 'no data' would hide a broken device behind
    the same counter as a quiet one."""
    transport = FakeTransport({
        ble.TEMPERATURE_UUID: b"\x01\x02\x03",
        ble.HUMIDITY_UUID: struct.pack("<H", 5500),
        ble.BATTERY_LEVEL_UUID: b"\x57",
    })
    driver = ble.BleGattDriver(ble_profile, "urn:srcos:device:th100_bed2", transport)
    with pytest.raises(DriverError, match="undecodable payload"):
        driver.poll()


def test_a_failed_connect_is_a_driver_error(ble_profile):
    class Dead:
        def connect(self):
            raise OSError("no adapter")

        def read_characteristic(self, uuid):  # pragma: no cover - never reached
            raise AssertionError

        def disconnect(self):  # pragma: no cover
            pass

    driver = ble.BleGattDriver(ble_profile, "urn:srcos:device:th100_bed2", Dead())
    with pytest.raises(DriverError, match="BLE connect failed"):
        driver.poll()


def test_decoded_values_land_inside_the_profile_declared_ranges(ble_profile):
    """The decoders and the profile must agree, or every real reading fails the gate."""
    transport = FakeTransport({
        ble.TEMPERATURE_UUID: struct.pack("<h", 2137),
        ble.HUMIDITY_UUID: struct.pack("<H", 5500),
        ble.BATTERY_LEVEL_UUID: b"\x57",
    })
    driver = ble.BleGattDriver(ble_profile, "urn:srcos:device:th100_bed2", transport)
    declared = {m["metric"]: m for m in ble_profile["metrics"]}
    for sample in driver.poll():
        spec = declared[sample.metric]
        assert spec["minimum"] <= sample.value <= spec["maximum"]
