"""The emitter: validate-then-write, fail-closed, gapless retry, seal-then-count.

These are the semantics that make the difference between a service that streams and a
service that appears to. Each is proven on fakes, so the failure modes are reachable.
"""
from __future__ import annotations

import pytest

from device_service import contract
from device_service.clients import EmitError, GatewayError, READING_LABEL
from device_service.drivers import DriverError, Sample, VirtualRoomSensorDriver
from device_service.emitter import CommissionedDevice, Emitter

from conftest import FakeGateway, FakeWriter

DEVICE = "urn:srcos:device:room_sensor_01"


def make_emitter(virtual_profile, writer=None, gateway=None, driver=None, devices=None):
    writer = writer or FakeWriter()
    gateway = gateway or FakeGateway()
    if devices is None:
        devices = [
            CommissionedDevice(
                device_ref=DEVICE,
                profile=virtual_profile,
                driver=driver or VirtualRoomSensorDriver(virtual_profile, DEVICE, seed=42),
            )
        ]
    return Emitter(
        devices, writer, gateway,
        workspace_ref="urn:srcos:workspace:citizen_home_demo",
        branch_ref="urn:srcos:branch:home_main",
    ), writer, gateway


class ScriptedDriver:
    def __init__(self, profile, script):
        self.metrics = [m["metric"] for m in profile["metrics"]]
        self.script = list(script)
        self.calls = 0

    def poll(self):
        self.calls += 1
        if not self.script:
            return []
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


# ---------------------------------------------------------------------- happy path
def test_a_clean_interval_emits_seals_and_counts(virtual_profile):
    em, writer, gateway = make_emitter(virtual_profile)
    result = em.run_once()
    assert result.polled == 1
    assert result.emitted == 3          # three metrics on the virtual profile
    assert result.validation_failures == 0
    assert result.receipts == 1
    assert result.pending == 0
    assert result.hellgraph_ok and result.gateway_ok
    assert len(gateway.calls) == 1
    assert gateway.calls[0]["row_count"] == 3
    assert gateway.calls[0]["batch_hash"].startswith("sha256:")


def test_the_graph_shape_is_the_contract_made_walkable(virtual_profile):
    em, writer, _ = make_emitter(virtual_profile)
    em.run_once()
    labels = {node[0]: node[1] for node in writer.nodes}
    # profile, device and kko type nodes exist
    assert virtual_profile["id"] in labels
    assert DEVICE in labels
    assert any("KkoType" in v for v in labels.values())
    # readings carry a quality LABEL, so "not a measurement" is a label query
    reading_nodes = [n for n in writer.nodes if READING_LABEL in n[1]]
    assert len(reading_nodes) == 3
    assert all(any(lbl.startswith("quality:") for lbl in n[1]) for n in reading_nodes)
    edges = {(e[0], e[2]) for e in writer.edges}
    assert ("conformsTo", virtual_profile["id"]) in edges
    assert ("fromDevice", DEVICE) in edges
    assert ("declaredBy", virtual_profile["id"]) in edges
    assert any(label == "kkoType" for label, _ in edges)


def test_nodes_precede_the_edges_that_reference_them(virtual_profile):
    em, writer, _ = make_emitter(virtual_profile)
    em.run_once()
    seen: set[str] = set()
    order = []
    for node in writer.nodes:
        order.append(("node", node[0]))
    # Reconstruct true interleaving by replaying the plan through a recording writer.
    class Recorder:
        def __init__(self):
            self.seq = []

        def post_node(self, node_id, labels, properties):
            self.seq.append(("node", node_id))

        def post_edge(self, label, from_id, to_id):
            self.seq.append(("edge", from_id, to_id))

    rec = Recorder()
    em2, _, _ = make_emitter(virtual_profile, writer=rec)
    em2.run_once()
    for entry in rec.seq:
        if entry[0] == "node":
            seen.add(entry[1])
        else:
            assert entry[1] in seen, f"edge from {entry[1]} before its node"
            assert entry[2] in seen, f"edge to {entry[2]} before its node"


def test_the_full_validated_reading_lands_on_the_node(virtual_profile):
    import json

    em, writer, _ = make_emitter(virtual_profile)
    em.run_once()
    node = next(n for n in writer.nodes if READING_LABEL in n[1])
    payload = json.loads(node[2]["reading"])
    contract.validate_reading(payload, virtual_profile)
    assert node[2]["simulated"] is True


# ------------------------------------------------------------------- fail-closed
def test_a_nonconformant_reading_is_counted_and_NOT_emitted(virtual_profile):
    """A driver reporting a value outside the declared range must not reach the log."""
    bad = ScriptedDriver(virtual_profile, [[
        Sample(metric="temperature", value=999.0),
        Sample(metric="humidity.relative", value=50.0),
    ]])
    em, writer, gateway = make_emitter(virtual_profile, driver=bad)
    result = em.run_once()
    assert result.validation_failures == 1
    assert result.emitted == 1                      # the good one still emits
    emitted_metrics = {
        n[2]["metric"] for n in writer.nodes if READING_LABEL in n[1]
    }
    assert emitted_metrics == {"humidity.relative"}
    # the seal covers exactly what landed
    assert gateway.calls[0]["row_count"] == 1


def test_a_whole_bad_poll_seals_nothing(virtual_profile):
    bad = ScriptedDriver(virtual_profile, [[Sample(metric="temperature", value=999.0)]])
    em, writer, gateway = make_emitter(virtual_profile, driver=bad)
    result = em.run_once()
    assert result.validation_failures == 1
    assert result.emitted == 0
    assert gateway.calls == []
    assert writer.nodes == []


def test_a_driver_failure_skips_the_device_without_a_partial_batch(virtual_profile):
    dead = ScriptedDriver(virtual_profile, [DriverError("radio gone")])
    em, writer, gateway = make_emitter(virtual_profile, driver=dead)
    result = em.run_once()
    assert result.driver_failures == 1
    assert result.emitted == 0
    assert result.pending == 0
    assert writer.nodes == [] and gateway.calls == []


# --------------------------------------------------------------- gapless retry
def _one_shot(profile):
    """A driver that yields exactly one poll, so a retry test observes the retry and not
    a fresh batch arriving behind it."""
    return ScriptedDriver(profile, [[
        Sample(metric="temperature", value=21.5),
        Sample(metric="humidity.relative", value=48.0),
    ]])


def test_a_hellgraph_outage_keeps_the_batch_pending_and_resumes_at_the_same_op(virtual_profile):
    writer = FakeWriter(fail_after=4)
    em, _, gateway = make_emitter(virtual_profile, writer=writer, driver=_one_shot(virtual_profile))
    result = em.run_once()
    assert result.hellgraph_ok is False
    assert result.emitted == 0
    assert result.pending == 2
    assert gateway.calls == []          # nothing sealed: nothing fully landed
    landed = writer.ops
    assert landed == 4

    writer.fail_after = None
    result2 = em.run_once()
    assert result2.emitted == 2
    assert result2.pending == 0
    assert len(gateway.calls) == 1
    # The half that landed was NOT re-sent: every recorded write is a distinct op, so the
    # totals match exactly rather than double-counting the four that already landed.
    assert writer.ops > landed
    assert len(writer.nodes) + len(writer.edges) == writer.ops


def test_no_new_polling_while_a_batch_is_pending(virtual_profile):
    """Gapless: the sequence never skips, and memory stays bounded."""
    driver = VirtualRoomSensorDriver(virtual_profile, DEVICE, seed=42)
    writer = FakeWriter(fail_after=2)
    em, _, _ = make_emitter(virtual_profile, writer=writer, driver=driver)
    em.run_once()
    assert em.devices[0].seq == 3
    for _ in range(5):
        em.run_once()
    assert em.devices[0].seq == 3, "polled again while a batch was outstanding"
    assert em.pending_readings == 3


def test_the_sequence_is_gapless_across_an_outage(virtual_profile):
    """No sequence number is skipped and none is emitted twice, across a failure and a
    recovery. This is the property that lets a consumer detect a genuine gap."""
    writer = FakeWriter(fail_after=5)
    em, _, _ = make_emitter(virtual_profile, writer=writer)
    em.run_once()
    writer.fail_after = None
    em.run_once()
    em.run_once()
    seqs = sorted(n[2]["sequenceRef"] for n in writer.nodes if READING_LABEL in n[1])
    assert seqs == sorted(set(seqs)), f"a sequence number was emitted twice: {seqs}"
    assert seqs == list(range(1, len(seqs) + 1)), f"sequence skipped: {seqs}"
    assert len(seqs) == em.devices[0].seq


def test_a_gateway_refusal_keeps_the_batch_pending_at_the_receipt_step(virtual_profile):
    """Graph writes cannot be un-written, so only the receipt is retried — and nothing is
    counted as emitted until it is both on the graph and attested."""
    gateway = FakeGateway(refuse=True)
    em, writer, _ = make_emitter(
        virtual_profile, gateway=gateway, driver=_one_shot(virtual_profile)
    )
    result = em.run_once()
    assert result.gateway_ok is False
    assert result.emitted == 0
    assert result.pending == 2
    writes_after_first = writer.ops
    assert writes_after_first > 0            # the graph writes DID land

    gateway.refuse = False
    result2 = em.run_once()
    assert result2.emitted == 2
    assert result2.receipts == 1
    # the graph writes were not replayed — only the receipt was retried
    assert writer.ops == writes_after_first


def test_a_retried_receipt_is_idempotent(virtual_profile):
    """An identical spec re-POSTed after a crash hits the gateway memo and returns the
    same receipt id rather than minting a duplicate on the chain."""
    gateway = FakeGateway()
    em, _, _ = make_emitter(virtual_profile, gateway=gateway)
    em.run_once()
    first = gateway.calls[0]
    assert gateway.mint(**{
        "device_ref": first["device_ref"], "from_cursor": first["from_cursor"],
        "to_cursor": first["to_cursor"], "row_count": first["row_count"],
        "batch_hash": first["batch_hash"],
    })["id"] == "sha256:receipt0000"


def test_the_loop_survives_and_recovers(virtual_profile):
    writer = FakeWriter(fail_after=0)
    em, _, gateway = make_emitter(virtual_profile, writer=writer, driver=_one_shot(virtual_profile))
    for _ in range(3):
        result = em.run_once()
        assert result.hellgraph_ok is False
        assert result.emitted == 0
    writer.fail_after = None
    result = em.run_once()
    assert result.emitted == 2 and result.hellgraph_ok


def test_recovery_catches_up_within_one_interval(virtual_profile):
    """Deliberate, not accidental: an interval drains what is outstanding, then polls the
    devices that are now clear, then drains again. A recovered device therefore lands its
    stuck batch AND a fresh one in the same tick, instead of staying one interval behind
    forever after a single outage."""
    writer = FakeWriter(fail_after=0)
    em, _, gateway = make_emitter(virtual_profile, writer=writer)
    em.run_once()
    assert em.pending_readings == 3
    writer.fail_after = None
    result = em.run_once()
    assert result.emitted == 6
    assert result.receipts == 2
    assert em.pending_readings == 0


# ------------------------------------------------------------------ typed absence
def test_an_absence_lands_as_a_typed_record_wired_to_its_reading(virtual_profile):
    driver = VirtualRoomSensorDriver(virtual_profile, DEVICE, seed=42, drop_every_n=1)
    em, writer, _ = make_emitter(virtual_profile, driver=driver)
    result = em.run_once()
    assert result.emitted == 3
    assert result.quality_counts == {"unavailable": 3}
    absence_nodes = [n for n in writer.nodes if "NullAbsenceRecord" in n[1]]
    assert len(absence_nodes) == 3
    assert all(n[2]["kind"] == "timeout" for n in absence_nodes)
    absence_edges = [e for e in writer.edges if e[0] == "absenceTypedBy"]
    assert len(absence_edges) == 3
    reading_nodes = [n for n in writer.nodes if READING_LABEL in n[1]]
    assert all("quality:unavailable" in n[1] for n in reading_nodes)
    assert all(n[2]["valueNum"] is None for n in reading_nodes)


# --------------------------------------------------------------- multiple devices
def test_devices_are_independent(virtual_profile):
    d1 = CommissionedDevice(
        device_ref="urn:srcos:device:room_sensor_01", profile=virtual_profile,
        driver=VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_01", seed=42),
    )
    d2 = CommissionedDevice(
        device_ref="urn:srcos:device:room_sensor_02", profile=virtual_profile,
        driver=VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:room_sensor_02", seed=42),
    )
    em, writer, gateway = make_emitter(virtual_profile, devices=[d1, d2])
    result = em.run_once()
    assert result.polled == 2
    assert result.emitted == 6
    assert result.receipts == 2, "one receipt per device batch"
    assert {c["device_ref"] for c in gateway.calls} == {d1.device_ref, d2.device_ref}


def test_a_stuck_device_does_not_block_a_healthy_one(virtual_profile):
    stuck = CommissionedDevice(
        device_ref="urn:srcos:device:stuck", profile=virtual_profile,
        driver=ScriptedDriver(virtual_profile, [DriverError("gone")] * 5),
    )
    healthy = CommissionedDevice(
        device_ref="urn:srcos:device:healthy", profile=virtual_profile,
        driver=VirtualRoomSensorDriver(virtual_profile, "urn:srcos:device:healthy", seed=7),
    )
    em, _, gateway = make_emitter(virtual_profile, devices=[stuck, healthy])
    result = em.run_once()
    assert result.driver_failures == 1
    assert result.emitted == 3
    assert {c["device_ref"] for c in gateway.calls} == {"urn:srcos:device:healthy"}


# --------------------------------------------------------------- honest liveness
def test_an_idle_drain_reports_no_evidence_rather_than_green(virtual_profile):
    """A drain with nothing pending contacts NOTHING. Reporting both dependencies green
    without having asked is exactly the lie /healthz must not tell."""
    em, _, _ = make_emitter(virtual_profile, devices=[])
    result = em.run_once()
    assert result.attempted is False
    assert result.polled == 0


def test_startup_check_runs_the_real_gate(virtual_profile):
    em, _, _ = make_emitter(virtual_profile)
    em.startup_check()
    em.devices[0].profile = {**virtual_profile, "definitionDigest": "sha256:" + "0" * 64}
    with pytest.raises(contract.ContractError):
        em.startup_check()
