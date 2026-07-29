"""device-service — FOG & CITIZEN PLANE W8.7: the estate's southbound device plane.

ONE southbound interface (sourceos-spec DeviceProfile/DeviceReading v0.1.0, VENDORED and
sha256-asserted at import), N protocol drivers. Readings are validated fail-closed
against BOTH the schema and the profile they cite, written to the platform log as
hellgraph-service graph writes (KKO-typed, quality-labelled), and sealed one receipt per
batch on the estate spine via compute-gateway POST /v1/compute kind=materialize. Never a
fifth receipt lineage.

/healthz always answers 200 with the truth. Failures are counted and surfaced, never
emitted. Liveness is "the process and loop are up", not "every dependency is green" — a
producer has no traffic to gate, and restarting it cannot fix a down hellgraph.

`validation_failures` MUST be 0 in steady state. It counts readings that failed the
schema OR failed attribution against their profile; nonzero means a device disagrees
with its own declaration, which is a fault or a wrong profile, and either way is the
alarm this service exists to raise.

`simulated_devices` is reported next to `devices` on purpose. This deployment ships ONE
driver, `virtual`, and its readings are simulated. Anything that reads /healthz can tell
at a glance how much of this stream is a measurement and how much is not.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from importlib import resources
from typing import Any

from fastapi import FastAPI

from . import contract
from .clients import GatewayClient, HellGraphWriter
from .drivers import DriverUnavailable, build_driver
from .emitter import CommissionedDevice, Emitter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("device_service")

HELLGRAPH_URL = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")
COMPUTE_GATEWAY_URL = os.getenv("COMPUTE_GATEWAY_URL", "http://compute-gateway:8080")
GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")
DEVICE_PROJECT = os.getenv("DEVICE_PROJECT", "default")

POLL_ENABLED = os.getenv("DEVICE_POLL_ENABLED", "on").lower() in ("on", "true", "1", "yes")
POLL_INTERVAL = float(os.getenv("DEVICE_POLL_INTERVAL_SECONDS", "5"))
WORKSPACE_REF = os.getenv("DEVICE_WORKSPACE_REF", "urn:srcos:workspace:citizen_home_demo")
BRANCH_REF = os.getenv("DEVICE_BRANCH_REF", "urn:srcos:branch:home_main")

#: Commissioned devices: "<deviceRef>=<profile-name>" pairs, comma-separated. The profile
#: name resolves to src/device_service/profiles/<name>.json. In v0.1 the instance ->
#: profile binding lives here; every reading carries both refs plus the profile digest so
#: the binding is auditable from the graph (see specs/device-service-contract.md §11).
DEVICES = os.getenv(
    "DEVICE_COMMISSIONED",
    "urn:srcos:device:room_sensor_01=virtual-room-sensor,"
    "urn:srcos:device:room_sensor_02=virtual-room-sensor",
)
VIRTUAL_SEED = int(os.getenv("DEVICE_VIRTUAL_SEED", "42"))
#: 0 = never. Non-zero makes the virtual driver report a TYPED absence every Nth tick, so
#: the unavailable -> NullAbsenceRecord path is exercisable on a live deployment.
VIRTUAL_DROP_EVERY_N = int(os.getenv("DEVICE_VIRTUAL_DROP_EVERY_N", "0"))

STATE: dict[str, Any] = {
    "enabled": POLL_ENABLED,
    "poll_interval_seconds": POLL_INTERVAL,
    "devices": 0,
    "simulated_devices": 0,
    "protocols": {},
    "polled": 0,
    "emitted": 0,
    "validation_failures": 0,   # steady-state MUST be 0 — nonzero is the alarm
    "driver_failures": 0,
    "pending": 0,
    "receipts": 0,
    "last_receipt_id": None,
    "quality_counts": {},
    "hellgraph_ok": None,       # None = never asked, not "green"
    "gateway_ok": None,
    "last_emit_at": None,
    "last_error": None,
    "last_error_at": None,
    "loop_running": False,
}
_STATE_LOCK = threading.Lock()
_EMITTER: Emitter | None = None


def load_profile_file(name: str) -> dict[str, Any]:
    raw = (resources.files("device_service") / "profiles" / f"{name}.json").read_text("utf-8")
    return contract.load_profile(json.loads(raw))


def build_emitter() -> Emitter:
    devices: list[CommissionedDevice] = []
    for spec in (s.strip() for s in DEVICES.split(",") if s.strip()):
        if "=" not in spec:
            raise ValueError(
                f"DEVICE_COMMISSIONED entry {spec!r} is not <deviceRef>=<profile-name>"
            )
        device_ref, profile_name = (part.strip() for part in spec.split("=", 1))
        profile = load_profile_file(profile_name)
        driver = build_driver(
            profile,
            device_ref,
            {"seed": VIRTUAL_SEED, "drop_every_n": VIRTUAL_DROP_EVERY_N},
        )
        devices.append(CommissionedDevice(device_ref=device_ref, profile=profile, driver=driver))
    if not devices:
        raise ValueError("no devices commissioned — refusing to run a device plane with no devices")
    return Emitter(
        devices,
        HellGraphWriter(HELLGRAPH_URL),
        GatewayClient(COMPUTE_GATEWAY_URL, GATEWAY_TOKEN, project=DEVICE_PROJECT),
        workspace_ref=WORKSPACE_REF,
        branch_ref=BRANCH_REF,
    )


def _apply(result: Any) -> None:
    with _STATE_LOCK:
        STATE["polled"] += result.polled
        STATE["emitted"] += result.emitted
        STATE["validation_failures"] += result.validation_failures
        STATE["driver_failures"] += result.driver_failures
        STATE["receipts"] += result.receipts
        STATE["pending"] = result.pending
        if result.last_receipt_id:
            STATE["last_receipt_id"] = result.last_receipt_id
        for quality, count in result.quality_counts.items():
            STATE["quality_counts"][quality] = STATE["quality_counts"].get(quality, 0) + count
        # An unchecked dependency is never reported up: only a drain that actually
        # contacted something may move these flags off None.
        if result.attempted:
            STATE["hellgraph_ok"] = result.hellgraph_ok
            STATE["gateway_ok"] = result.gateway_ok
        if result.emitted:
            STATE["last_emit_at"] = time.time()


def _loop(emitter: Emitter) -> None:
    with _STATE_LOCK:
        STATE["loop_running"] = True
    while True:
        try:
            _apply(emitter.run_once())
        except Exception as e:  # noqa: BLE001 — the loop must survive any dependency outage
            with _STATE_LOCK:
                STATE["hellgraph_ok"] = False
                STATE["last_error"] = f"{type(e).__name__}: {e}"
                STATE["last_error_at"] = time.time()
            log.exception("poll interval failed, retrying after the interval")
        time.sleep(POLL_INTERVAL)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    global _EMITTER
    if POLL_ENABLED:
        _EMITTER = build_emitter()
        # Fail-closed boot gate IN THE MAIN THREAD: schema drift (the vendored sha256 is
        # already asserted at import), a profile whose digest is not its own, or a probe
        # reading that does not validate aborts uvicorn startup — a visible crash, never
        # a silently dead loop behind a green pod. build_emitter() has already refused
        # any profile whose protocol has no registered driver.
        _EMITTER.startup_check()
        with _STATE_LOCK:
            STATE["devices"] = len(_EMITTER.devices)
            STATE["simulated_devices"] = _EMITTER.simulated_devices
            STATE["protocols"] = _EMITTER.protocols
        threading.Thread(target=_loop, args=(_EMITTER,), name="device-poll-loop",
                         daemon=True).start()
    yield


app = FastAPI(
    title="device-service",
    version="0.1.0",
    description="W8.7 southbound device plane: one interface, N protocol drivers",
    lifespan=_lifespan,
)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    with _STATE_LOCK:
        snapshot = dict(STATE)
        snapshot["quality_counts"] = dict(STATE["quality_counts"])
    if _EMITTER is not None:
        snapshot["pending"] = _EMITTER.pending_readings
    return {
        "ok": True,
        "service": "device-service",
        "spec_version": contract.SPEC_VERSION,
        "profile_schema_sha256": contract.PROFILE_SCHEMA_SHA256,
        "reading_schema_sha256": contract.READING_SCHEMA_SHA256,
        "receipt_kind": "materialize",
        **snapshot,
    }


@app.get("/v1/profiles")
def profiles() -> dict[str, Any]:
    """The declared capability of every commissioned device, with its RECOMPUTED digest.

    Exposed because a reading's whole meaning is the profile it pins: a consumer holding
    a reading must be able to fetch the declaration it names and check the digest itself,
    rather than taking this service's word for it.
    """
    if _EMITTER is None:
        return {"devices": []}
    return {
        "devices": [
            {
                "deviceRef": d.device_ref,
                "deviceProfileRef": d.profile["id"],
                "protocol": d.profile["protocol"],
                "simulated": contract.is_simulated(d.profile),
                "definitionDigest": d.profile["definitionDigest"],
                "recomputedDigest": contract.definition_digest(d.profile),
                "metrics": [
                    {
                        "metric": m["metric"],
                        "unit": m["unit"],
                        "valueType": m["valueType"],
                        "minimum": m.get("minimum"),
                        "maximum": m.get("maximum"),
                        "sourceAddress": m["sourceAddress"],
                        "kkoTypeRef": m.get("kkoTypeRef"),
                    }
                    for m in d.profile["metrics"]
                ],
                "sequence": d.seq,
            }
            for d in _EMITTER.devices
        ]
    }
