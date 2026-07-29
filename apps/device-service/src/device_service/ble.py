"""The real-BLE seam — typed, and honest about exactly what is missing.

WHAT IS REAL HERE: the GATT characteristic decoders. They implement the Bluetooth SIG
formats byte-for-byte and are unit-tested against vectors taken from the specifications,
because decoding is where the interesting bugs live — a sint16 read as uint16 turns
-5.00 degC into +650.31 degC, and nothing downstream can tell. `BleGattDriver` is a
complete DeviceDriver against an injected transport.

WHAT IS MISSING: `BleTransport` has no implementation in this build. There is no radio,
no `bleak`, no pairing, no bonding. One class implementing three methods, plus one line
in drivers.DRIVERS, is the entire remaining distance — and `build_driver()` refuses a
ble-gatt profile until that line exists, so nothing can quietly pretend otherwise.

WHY IT IS NOT SHIPPED: a BLE transport needs a radio on the node, host DBus/Bluetooth
access from a container that currently runs unprivileged with a read-only rootfs, and a
pairing/bonding story that is a security review of its own (securityMode is a declared
field on the profile precisely so that review has something to bite on). Shipping a
transport stub that returned plausible bytes would be worse than shipping none: it would
make simulated data indistinguishable from measured data at the one layer where the
distinction is still recoverable.

Characteristic formats implemented (Bluetooth SIG, Environmental Sensing + Battery):
  0x2A6E Temperature        sint16, little-endian, 0.01 degC        -> Cel
  0x2A6F Humidity           uint16, little-endian, 0.01 %           -> %
  0x2A19 Battery Level      uint8, 0..100 %                         -> %
"""
from __future__ import annotations

import struct
from typing import Any, Protocol

TEMPERATURE_UUID = "00002a6e-0000-1000-8000-00805f9b34fb"
HUMIDITY_UUID = "00002a6f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

ENVIRONMENTAL_SENSING_SERVICE = "0000181a-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"


class DecodeError(ValueError):
    """The characteristic payload is not the shape the format requires."""


def decode_temperature(payload: bytes) -> float:
    """0x2A6E: sint16 little-endian, unit 0.01 degC.

    SIGNEDNESS IS THE BUG THAT MATTERS. Read as uint16, -5.00 degC (0xFE0C) decodes to
    +650.36 degC — a plausible-looking number that no range check on a -40..85 profile
    would ever pass, which is the only reason it would be caught at all. Explicit '<h'.
    """
    if len(payload) != 2:
        raise DecodeError(f"temperature (0x2A6E) needs exactly 2 bytes, got {len(payload)}")
    (raw,) = struct.unpack("<h", payload)
    return round(raw * 0.01, 2)


def decode_humidity(payload: bytes) -> float:
    """0x2A6F: uint16 little-endian, unit 0.01 %. Unsigned — humidity has no negatives."""
    if len(payload) != 2:
        raise DecodeError(f"humidity (0x2A6F) needs exactly 2 bytes, got {len(payload)}")
    (raw,) = struct.unpack("<H", payload)
    return round(raw * 0.01, 2)


def decode_battery_level(payload: bytes) -> int:
    """0x2A19: uint8 percent. The spec bounds it 0..100; a device reporting 255 is
    faulty, and passing that through as 'the battery is at 255%' is precisely the kind of
    quiet nonsense the range declaration exists to stop. Rejected at the decoder."""
    if len(payload) != 1:
        raise DecodeError(f"battery level (0x2A19) needs exactly 1 byte, got {len(payload)}")
    value = payload[0]
    if value > 100:
        raise DecodeError(f"battery level {value} is outside the spec's 0..100 percent")
    return value


#: characteristic UUID -> decoder. A profile's metrics[].sourceAddress ends in the UUID.
DECODERS = {
    TEMPERATURE_UUID: decode_temperature,
    HUMIDITY_UUID: decode_humidity,
    BATTERY_LEVEL_UUID: decode_battery_level,
}


def characteristic_of(source_address: str) -> str:
    """Extract the characteristic UUID from a profile sourceAddress of the form
    gatt://<service-uuid>/<characteristic-uuid>."""
    if not source_address.startswith("gatt://"):
        raise DecodeError(f"not a GATT source address: {source_address!r}")
    parts = source_address[len("gatt://"):].split("/")
    if len(parts) != 2 or not parts[1]:
        raise DecodeError(
            f"GATT source address must be gatt://<service>/<characteristic>: {source_address!r}"
        )
    return parts[1].lower()


class BleTransport(Protocol):
    """The one thing this build does not have. Implement it and BLE is live.

    An implementation owns connection, pairing/bonding per the profile's securityMode,
    and notification handling. It hands back raw characteristic bytes and nothing else —
    decoding stays here so it is testable without a radio.
    """

    def connect(self) -> None: ...

    def read_characteristic(self, uuid: str) -> bytes:
        """Raise TimeoutError if the peripheral did not answer within the window."""
        ...

    def disconnect(self) -> None: ...


class BleGattDriver:
    """A complete DeviceDriver for BLE GATT devices, against an injected transport.

    Nothing here is a placeholder: given a BleTransport, this polls a real Acme TH-100 (or
    any Environmental-Sensing peripheral whose profile names the right characteristics).
    A per-metric timeout becomes a typed absence rather than a re-reported stale value —
    the distinction the contract's `stale` vs `unavailable` split exists to preserve.
    """

    def __init__(self, profile: dict[str, Any], device_ref: str, transport: BleTransport) -> None:
        self.profile = profile
        self.device_ref = device_ref
        self.transport = transport
        self.metrics = [m["metric"] for m in profile["metrics"]]
        self._declared = {m["metric"]: m for m in profile["metrics"]}
        self._connected = False

    def poll(self) -> list[Any]:
        from .drivers import DriverError, Sample  # local import: keeps drivers.py the entry point

        if not self._connected:
            try:
                self.transport.connect()
                self._connected = True
            except Exception as exc:  # noqa: BLE001 - any transport failure is one failure
                raise DriverError(f"BLE connect failed for {self.device_ref}: {exc}") from exc

        samples: list[Any] = []
        for metric in self.metrics:
            declared = self._declared[metric]
            uuid = characteristic_of(declared["sourceAddress"])
            decoder = DECODERS.get(uuid)
            if decoder is None:
                raise DriverError(
                    f"no decoder for characteristic {uuid} ({metric}) — a profile may not "
                    f"declare a channel this driver cannot actually read"
                )
            try:
                payload = self.transport.read_characteristic(uuid)
            except TimeoutError:
                samples.append(
                    Sample(metric=metric, value=None, quality="unavailable",
                           absence_kind="timeout", raw=None, flags=["notify_window_missed"])
                )
                continue
            except Exception as exc:  # noqa: BLE001
                samples.append(
                    Sample(metric=metric, value=None, quality="unavailable",
                           absence_kind="transport_failure", raw=None,
                           flags=[f"transport:{type(exc).__name__}"])
                )
                continue
            try:
                value = decoder(payload)
            except DecodeError:
                # A payload that does not decode is NOT an absence — the device answered.
                # It is a fault, and re-reporting it as "no data" would hide a broken
                # device behind the same counter as a quiet one.
                raise DriverError(
                    f"{self.device_ref}/{metric}: undecodable payload {payload.hex()}"
                ) from None
            samples.append(
                Sample(metric=metric, value=value, quality="ok", raw={"hex": payload.hex()})
            )
        return samples
