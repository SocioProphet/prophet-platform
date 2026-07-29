"""The southbound driver interface — ONE interface, N protocol drivers (EdgeX's lesson).

A driver's entire job is to speak a protocol and hand back `Sample`s. It does NOT build
readings, does not know about URNs, units, ranges, provenance, the graph or the receipt
spine, and cannot supply any of the fields that make a reading attributable — those are
copied from the profile by contract.build_reading(). That asymmetry is the whole point:
adding a Zigbee driver must not be able to introduce a second event vocabulary, because
a driver has no way to express one.

REGISTRY, AND WHY IT FAILS CLOSED: build_driver() refuses a profile whose protocol has
no registered driver. A service that started anyway and quietly polled nothing would
present a green pod, a green /healthz and zero readings — the exact "declared but
unenforced" shape the estate keeps finding. Refusing to start is louder and cheaper.

WHAT ACTUALLY SHIPS HERE, PLAINLY: one real driver, `virtual` — a deterministic
simulator with no physical counterpart. Its readings are SIMULATED, and they are marked
as such at every layer that can carry a mark (profile protocol, profile labels, reading
policy/risk labels, a `simulated` property on the graph node, a `simulated_devices`
counter on /healthz). Nothing in this service pretends to have touched a sensor.

The real-BLE seam is `ble.py`: the GATT characteristic DECODERS are real, correct and
unit-tested against the Bluetooth SIG formats, and `BleGattDriver` is complete against
an injected `BleTransport`. No `BleTransport` implementation ships — that one class,
plus a registry line, is the entire distance to a real BLE device.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class DriverError(RuntimeError):
    """The driver could not talk to the device. The caller types this as an absence."""


class DriverUnavailable(RuntimeError):
    """No driver is registered (or buildable) for this protocol. Fail closed at boot."""


@dataclass(frozen=True)
class Sample:
    """One raw observation as the driver saw it.

    A driver reports what it observed and how much it believes it. It does not report
    units, ranges, ontology types or provenance — the profile declares those, and
    contract.build_reading() is the only thing that may put them on a reading.
    """

    metric: str
    value: Any
    quality: str = "ok"
    #: Set only when quality == "unavailable"; must be one of contract.DRIVER_ABSENCE_KINDS.
    absence_kind: str | None = None
    #: The pre-decode payload, kept so a decode bug is provable after the fact.
    raw: Any = None
    flags: list[str] = field(default_factory=list)


class DeviceDriver(Protocol):
    """The one southbound interface. Implement this and a protocol is supported."""

    #: Metric names this driver can produce; must be a subset of the profile's.
    metrics: list[str]

    def poll(self) -> list[Sample]:
        """Read the device once. Raise DriverError if the device could not be reached at
        all; return Samples with quality="unavailable" for per-metric absences."""
        ...


# --------------------------------------------------------------------------- virtual


class VirtualRoomSensorDriver:
    """A deterministic simulated room sensor. NOT a measurement of anything.

    Values are a pure function of (seed, device, metric, tick): the same seed replays the
    same stream on every restart, so a re-emitted batch upserts identical nodes rather
    than minting drifted duplicates. Each metric walks a smooth band strictly INSIDE the
    profile's declared operating range — a simulator that emitted out-of-range values
    would make the must-be-zero `validation_failures` counter nonzero in steady state and
    train everyone to ignore it.

    `drop_every_n` (default 0 = never) makes the driver report a typed absence instead of
    a value on every Nth tick, so the unavailable → NullAbsenceRecord path can be
    exercised end-to-end on a running deployment rather than only in tests.
    """

    def __init__(
        self,
        profile: dict[str, Any],
        device_ref: str,
        seed: int = 42,
        drop_every_n: int = 0,
    ) -> None:
        self.profile = profile
        self.device_ref = device_ref
        self.seed = seed
        self.drop_every_n = max(0, drop_every_n)
        self.metrics = [m["metric"] for m in profile["metrics"]]
        self._declared = {m["metric"]: m for m in profile["metrics"]}
        self._tick = 0

    def _phase(self, metric: str) -> float:
        """A stable per-(seed, device, metric) phase offset, so metrics do not move in
        lockstep. Derived by hash rather than by RNG state so it survives a restart."""
        key = f"{self.seed}:{self.device_ref}:{metric}".encode()
        return int.from_bytes(hashlib.sha256(key).digest()[:4], "big") / 0xFFFFFFFF

    def _value(self, metric: str, tick: int) -> Any:
        declared = self._declared[metric]
        phase = self._phase(metric)
        wave = math.sin(2 * math.pi * (tick / 720.0 + phase))  # ~12 min period at 1 Hz
        if declared["valueType"] == "boolean":
            return wave > 0.5
        lo, hi = float(declared["minimum"]), float(declared["maximum"])
        # Walk the middle 40% of the declared range. Deliberately conservative: a
        # simulator has no business exercising the range boundary, and one that did would
        # make a genuine out-of-range fault indistinguishable from normal synthetic drift.
        centre = (lo + hi) / 2.0
        amplitude = (hi - lo) * 0.20
        value = centre + amplitude * wave
        if declared["valueType"] == "integer":
            return int(round(value))
        resolution = declared.get("resolution") or 0.01
        return round(round(value / resolution) * resolution, 6)

    def poll(self) -> list[Sample]:
        self._tick += 1
        tick = self._tick
        dropping = self.drop_every_n and tick % self.drop_every_n == 0
        samples: list[Sample] = []
        for metric in self.metrics:
            if dropping:
                samples.append(
                    Sample(
                        metric=metric,
                        value=None,
                        quality="unavailable",
                        absence_kind="timeout",
                        raw=None,
                        flags=["simulated_drop"],
                    )
                )
                continue
            samples.append(
                Sample(
                    metric=metric,
                    value=self._value(metric, tick),
                    quality="ok",
                    raw={"driver": "virtual", "tick": tick, "seed": self.seed},
                )
            )
        return samples


# -------------------------------------------------------------------------- registry

DriverFactory = Callable[[dict[str, Any], str, dict[str, Any]], DeviceDriver]


def _virtual_factory(profile: dict[str, Any], device_ref: str, options: dict[str, Any]) -> DeviceDriver:
    return VirtualRoomSensorDriver(
        profile,
        device_ref,
        seed=int(options.get("seed", 42)),
        drop_every_n=int(options.get("drop_every_n", 0)),
    )


#: protocol -> factory. Adding a protocol is adding a line here and a module beside
#: ble.py. Nothing else in the service changes — that is the interface holding.
DRIVERS: dict[str, DriverFactory] = {
    "virtual": _virtual_factory,
}


def build_driver(
    profile: dict[str, Any], device_ref: str, options: dict[str, Any] | None = None
) -> DeviceDriver:
    """Build the driver for a commissioned device, or refuse.

    Refusing is the point. A profile declaring `ble-gatt` on a build with no BLE
    transport must not start a service that silently polls nothing: the operator would
    see a green pod and an empty graph and have no way to tell that from a quiet house.
    """
    protocol = profile["protocol"]
    factory = DRIVERS.get(protocol)
    if factory is None:
        raise DriverUnavailable(
            f"no driver registered for protocol {protocol!r} (device {device_ref}, "
            f"profile {profile['id']}). Registered: {sorted(DRIVERS)}. Refusing to start "
            f"rather than run a service that polls nothing behind a green /healthz — see "
            f"ble.py for the shape a protocol driver takes."
        )
    driver = factory(profile, device_ref, options or {})
    declared = {m["metric"] for m in profile["metrics"]}
    unknown = sorted(set(driver.metrics) - declared)
    if unknown:
        raise DriverUnavailable(
            f"driver for {device_ref} produces metrics the profile does not declare: "
            f"{unknown} — a reading nothing declares is unattributable by construction"
        )
    return driver
