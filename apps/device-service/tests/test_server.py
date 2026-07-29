"""The HTTP surface: an honest /healthz, and the profile endpoint that lets a consumer
check the digest itself instead of trusting this service."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from device_service import contract


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    import device_service.server as mod

    importlib.reload(mod)
    return mod


def test_healthz_answers_200_with_the_counters(server):
    with TestClient(server.app) as client:
        body = client.get("/healthz").json()
    assert body["ok"] is True
    assert body["service"] == "device-service"
    for key in (
        "polled", "emitted", "validation_failures", "driver_failures", "pending",
        "receipts", "last_receipt_id", "quality_counts", "hellgraph_ok", "gateway_ok",
        "loop_running", "last_error", "last_error_at", "last_emit_at",
        "devices", "simulated_devices", "protocols", "poll_interval_seconds",
    ):
        assert key in body, f"/healthz omits {key}"


def test_validation_failures_is_present_and_zero(server):
    """The must-be-0 counter. Its presence is not decoration: it is the alarm for a
    device disagreeing with its own declaration."""
    with TestClient(server.app) as client:
        body = client.get("/healthz").json()
    assert body["validation_failures"] == 0


def test_healthz_publishes_the_contract_pins(server):
    """Contract drift is visible from a probe, without exec'ing into the pod."""
    with TestClient(server.app) as client:
        body = client.get("/healthz").json()
    assert body["spec_version"] == contract.SPEC_VERSION
    assert body["profile_schema_sha256"] == contract.PROFILE_SCHEMA_SHA256
    assert body["reading_schema_sha256"] == contract.READING_SCHEMA_SHA256


def test_healthz_declares_which_receipt_lineage_is_reused(server):
    """Not a fifth lineage — stated where an operator can see it."""
    with TestClient(server.app) as client:
        body = client.get("/healthz").json()
    assert body["receipt_kind"] == "materialize"


def test_unasked_dependencies_report_none_not_green(server):
    """None means 'never asked'. Reporting True before contacting anything is the exact
    lie a health endpoint must not tell."""
    with TestClient(server.app) as client:
        body = client.get("/healthz").json()
    assert body["hellgraph_ok"] is None
    assert body["gateway_ok"] is None


def test_healthz_answers_even_with_polling_disabled(server):
    with TestClient(server.app) as client:
        assert client.get("/healthz").status_code == 200


# ------------------------------------------------------------------ commissioning
def test_the_default_commissioning_builds_and_passes_its_own_boot_gate(monkeypatch):
    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    import device_service.server as mod

    importlib.reload(mod)
    emitter = mod.build_emitter()
    emitter.startup_check()
    assert len(emitter.devices) == 2
    assert emitter.simulated_devices == 2
    assert emitter.protocols == {"virtual": 2}


def test_commissioning_a_ble_device_refuses_to_start(monkeypatch):
    """The fail-closed boot gate: a profile whose protocol has no driver must crash the
    service, not produce a green pod polling nothing."""
    from device_service.drivers import DriverUnavailable

    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    monkeypatch.setenv(
        "DEVICE_COMMISSIONED", "urn:srcos:device:th100_bed2=acme-th100-ble"
    )
    import device_service.server as mod

    importlib.reload(mod)
    with pytest.raises(DriverUnavailable, match="no driver registered for protocol 'ble-gatt'"):
        mod.build_emitter()


def test_an_empty_commissioning_is_refused(monkeypatch):
    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    monkeypatch.setenv("DEVICE_COMMISSIONED", "")
    import device_service.server as mod

    importlib.reload(mod)
    with pytest.raises(ValueError, match="no devices commissioned"):
        mod.build_emitter()


def test_a_malformed_commissioning_entry_is_refused(monkeypatch):
    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    monkeypatch.setenv("DEVICE_COMMISSIONED", "urn:srcos:device:oops")
    import device_service.server as mod

    importlib.reload(mod)
    with pytest.raises(ValueError, match="not <deviceRef>=<profile-name>"):
        mod.build_emitter()


# ---------------------------------------------------------------- /v1/profiles
def test_profiles_endpoint_exposes_the_recomputed_digest(monkeypatch):
    """A consumer holding a reading must be able to fetch the declaration it pins and
    recompute the digest, rather than taking this service's word for it."""
    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    import device_service.server as mod

    importlib.reload(mod)
    mod._EMITTER = mod.build_emitter()
    with TestClient(mod.app) as client:
        body = client.get("/v1/profiles").json()
    assert len(body["devices"]) == 2
    for entry in body["devices"]:
        assert entry["definitionDigest"] == entry["recomputedDigest"]
        assert entry["simulated"] is True
        assert entry["protocol"] == "virtual"
        assert entry["metrics"]
        for metric in entry["metrics"]:
            assert metric["unit"] and metric["sourceAddress"] and metric["valueType"]


# ------------------------------------------------------------------ state plumbing
def test_healthz_reflects_a_real_poll(monkeypatch, virtual_profile):
    from device_service.drivers import VirtualRoomSensorDriver
    from device_service.emitter import CommissionedDevice, Emitter

    from conftest import FakeGateway, FakeWriter

    monkeypatch.setenv("DEVICE_POLL_ENABLED", "off")
    import device_service.server as mod

    importlib.reload(mod)
    device_ref = "urn:srcos:device:room_sensor_01"
    emitter = Emitter(
        [CommissionedDevice(
            device_ref=device_ref, profile=virtual_profile,
            driver=VirtualRoomSensorDriver(virtual_profile, device_ref, seed=42),
        )],
        FakeWriter(), FakeGateway(),
        workspace_ref="urn:srcos:workspace:citizen_home_demo",
        branch_ref="urn:srcos:branch:home_main",
    )
    mod._EMITTER = emitter
    mod._apply(emitter.run_once())
    with TestClient(mod.app) as client:
        body = client.get("/healthz").json()
    assert body["emitted"] == 3
    assert body["receipts"] == 1
    assert body["validation_failures"] == 0
    assert body["quality_counts"] == {"ok": 3}
    assert body["hellgraph_ok"] is True and body["gateway_ok"] is True
    assert body["last_receipt_id"]
