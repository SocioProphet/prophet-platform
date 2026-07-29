"""The emitter core — poll, validate-then-write, seal, and only then count.

Write path (W8.7 — the estate's first southbound sensor stream on the platform log):

    driver.poll() -> Samples -> build_reading() from the PROFILE -> VALIDATE EVERY ONE
    (fail-closed, schema + attribution) ->
        POST /api/graph/node  {id: <profileUrn>,  labels: [DeviceProfile]}
        POST /api/graph/node  {id: <deviceUrn>,   labels: [Device]}
        POST /api/graph/edge  {label: conformsTo,    from: device,  to: profile}
        POST /api/graph/node  {id: <kkoTypeUri>,  labels: [KkoType]}          (per type)
        POST /api/graph/node  {id: <absenceUrn>,  labels: [NullAbsenceRecord]} (per absence)
        POST /api/graph/node  {id: <readingUrn>,  labels: [DeviceReading, quality:<q>]}
        POST /api/graph/edge  {label: fromDevice,    from: reading, to: device}
        POST /api/graph/edge  {label: declaredBy,    from: reading, to: profile}
        POST /api/graph/edge  {label: kkoType,       from: reading, to: <kkoTypeUri>}
        POST /api/graph/edge  {label: absenceTypedBy, from: reading, to: <absenceUrn>}
    -> POST /v1/compute kind=materialize (compute-gateway)  ⇒ sealed receipt
    -> only THEN is the batch counted as emitted.

The graph shape is the contract made walkable: `quality:<q>` is a LABEL, so "give me
everything that is not a measurement" is a label query rather than a JSON scan, and the
normative stale/substituted/unavailable distinction survives into every downstream
surface. `kkoType` edges are what make readings KKO-typed IN THE GRAPH rather than only
in a JSON field, and `declaredBy` makes the attribution chain traversable from a value
back to the declaration that gave it meaning.

FAIL-CLOSED RULES, in order of severity:
- VALIDATION failure ⇒ that reading is NOT emitted, counted, and logged loudly. The rest
  of the poll still emits (one bad metric must not cost the whole device), and the count
  on /healthz is the alarm — its steady state MUST be 0. The sealed receipt covers the
  batch that DID emit, so the graph and the chain never disagree.
- DRIVER failure ⇒ the device is skipped this interval and recorded; no partial batch is
  queued. A device that cannot be reached produces nothing, not a stale value wearing an
  ok quality.
- HELLGRAPH failure ⇒ the batch stays PENDING with a per-WRITE cursor and resumes exactly
  where it stopped. No new polling happens for a device with a pending batch, so the
  reading sequence never skips and memory is bounded. Node writes are upserts and safe to
  repeat; an edge write is not, so a half-written batch never re-sends the half that
  landed.
- GATEWAY failure ⇒ the graph writes have already landed (they cannot be un-written), so
  the batch stays pending AT THE RECEIPT STEP and retries the receipt only. Nothing is
  counted as emitted until it is both on the graph and attested — the materializer's
  "no receipt ⇒ no checkpoint" rule.
- The loop never dies: any error is recorded in state and retried after the interval.

CONCURRENCY: the drain loop and the /healthz reader both touch this object, so every
mutation of the pending queue, the write cursor and the logical clock is under one
reentrant lock (nugget-extractor observed the two-thread double-drain bug for real).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from . import contract
from .clients import (
    ABSENCE_LABEL,
    DEVICE_LABEL,
    EDGE_ABSENCE,
    EDGE_CONFORMS_TO,
    EDGE_DECLARED_BY,
    EDGE_FROM_DEVICE,
    EDGE_KKO_TYPE,
    KKO_TYPE_LABEL,
    PROFILE_LABEL,
    READING_LABEL,
    EmitError,
    GatewayError,
)
from .drivers import DeviceDriver, DriverError, Sample

log = logging.getLogger("device_service.emitter")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class CommissionedDevice:
    """One physical (or virtual) thing, bound to the profile it conforms to.

    In v0.1 this binding lives here, in the service's commissioned-device table. Every
    reading carries both refs plus the profile digest, so the binding is auditable from
    the graph even though a typed `Device` registry contract does not exist yet (named as
    the first follow-on in specs/device-service-contract.md §11).
    """

    device_ref: str
    profile: dict[str, Any]
    driver: DeviceDriver
    seq: int = 0


@dataclass
class _Op:
    kind: str  # "node" | "edge"
    args: tuple


@dataclass
class _Batch:
    device_ref: str
    readings: list[dict[str, Any]]
    ops: list[_Op]
    from_cursor: int
    to_cursor: int
    cursor: int = 0  # index into ops; advanced ONLY after a write lands
    receipt_pending: bool = True


@dataclass
class PollResult:
    polled: int = 0
    emitted: int = 0
    validation_failures: int = 0
    driver_failures: int = 0
    receipts: int = 0
    pending: int = 0
    last_receipt_id: str | None = None
    quality_counts: dict[str, int] = field(default_factory=dict)
    # False means "no evidence either way" — a drain with nothing pending contacts
    # NOTHING, so folding default-true flags into /healthz would report both dependencies
    # green without ever having asked.
    attempted: bool = False
    hellgraph_ok: bool = True
    gateway_ok: bool = True


class Emitter:
    def __init__(
        self,
        devices: list[CommissionedDevice],
        writer: Any,
        gateway: Any,
        *,
        workspace_ref: str,
        branch_ref: str,
        actor_ref: str = "urn:srcos:agent:device_service",
        clock: Callable[[], str] = utcnow,
    ) -> None:
        self.devices = devices
        self.writer = writer
        self.gateway = gateway
        self.workspace_ref = workspace_ref
        self.branch_ref = branch_ref
        self.actor_ref = actor_ref
        self.clock = clock
        self._lock = threading.RLock()
        self._pending: list[_Batch] = []
        self._logical_time = 0
        self._types_ensured: set[str] = set()
        self._devices_ensured: set[str] = set()

    # ------------------------------------------------------------------ properties
    @property
    def pending_readings(self) -> int:
        with self._lock:
            return sum(len(b.readings) for b in self._pending)

    @property
    def simulated_devices(self) -> int:
        return sum(1 for d in self.devices if contract.is_simulated(d.profile))

    @property
    def protocols(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.devices:
            counts[d.profile["protocol"]] = counts.get(d.profile["protocol"], 0) + 1
        return counts

    def startup_check(self) -> None:
        contract.startup_check([d.profile for d in self.devices])

    # ------------------------------------------------------------------- the loop
    @staticmethod
    def _merge(into: PollResult, other: PollResult) -> None:
        into.emitted += other.emitted
        into.receipts += other.receipts
        into.last_receipt_id = other.last_receipt_id or into.last_receipt_id
        for k, v in other.quality_counts.items():
            into.quality_counts[k] = into.quality_counts.get(k, 0) + v
        if other.attempted:
            into.attempted = True
            into.hellgraph_ok = other.hellgraph_ok
            into.gateway_ok = other.gateway_ok

    def run_once(self) -> PollResult:
        """One interval: resume anything outstanding first, then poll only the devices
        that have nothing pending, then drain what was just built."""
        with self._lock:
            result = PollResult()
            self._merge(result, self._drain())
            pending_devices = {b.device_ref for b in self._pending}

            for device in self.devices:
                if device.device_ref in pending_devices:
                    # Gapless: no new samples for a device whose last batch has not
                    # fully landed. Bounded memory, and the seq stream never skips.
                    continue
                result.polled += 1
                try:
                    samples = device.driver.poll()
                except DriverError as e:
                    result.driver_failures += 1
                    log.warning("driver failure for %s, skipping this interval: %s",
                                device.device_ref, e)
                    continue
                batch = self._build_batch(device, samples, result)
                if batch is not None:
                    self._pending.append(batch)

            self._merge(result, self._drain())
            result.pending = sum(len(b.readings) for b in self._pending)
            return result

    # ------------------------------------------------------------------- building
    def _build_batch(
        self, device: CommissionedDevice, samples: list[Sample], result: PollResult
    ) -> _Batch | None:
        profile = device.profile
        from_cursor = device.seq
        readings: list[dict[str, Any]] = []
        absences: list[dict[str, Any]] = []

        for sample in samples:
            device.seq += 1
            self._logical_time += 1
            now = self.clock()
            reading_id = (
                "urn:srcos:device-reading:"
                + contract.reading_local_id(device.device_ref, sample.metric, device.seq)
            )
            absence = None
            if sample.quality == "unavailable":
                try:
                    absence = contract.build_absence_record(
                        reading_id=reading_id,
                        kind=sample.absence_kind or "no_event_observed",
                        observed_at=now,
                        workspace_ref=self.workspace_ref,
                        branch_ref=self.branch_ref,
                        device_ref=device.device_ref,
                        metric=sample.metric,
                        expected_next_sequence=device.seq + 1,
                        causal_notes=(
                            f"{device.device_ref}/{sample.metric} produced no value at "
                            f"sequence {device.seq}. Typed as an absence rather than "
                            f"re-reporting the prior value, which would have been "
                            f"substituted data wearing an ok quality."
                        ),
                    )
                except contract.ContractError as e:
                    result.validation_failures += 1
                    log.error("VALIDATION FAILURE — absence NOT emitted (%s/%s seq=%s): %s",
                              device.device_ref, sample.metric, device.seq, e)
                    continue

            try:
                reading = contract.build_reading(
                    profile=profile,
                    device_ref=device.device_ref,
                    metric=sample.metric,
                    value=sample.value,
                    quality=sample.quality,
                    observed_at=now,
                    received_at=now,
                    wall_time=now,
                    logical_time=self._logical_time,
                    sequence_ref=device.seq,
                    workspace_ref=self.workspace_ref,
                    branch_ref=self.branch_ref,
                    actor_ref=self.actor_ref,
                    raw_payload=sample.raw,
                    quality_flags=list(sample.flags),
                    null_absence_ref=absence["id"] if absence else None,
                )
                # THE fail-closed gate: nothing non-conformant, and nothing
                # unattributable, may reach the log.
                contract.validate_reading(reading, profile)
                if absence is not None:
                    contract.validate_absence_record(absence, reading)
            except contract.ContractError as e:
                result.validation_failures += 1
                log.error("VALIDATION FAILURE — reading NOT emitted (%s/%s seq=%s): %s",
                          device.device_ref, sample.metric, device.seq, e)
                continue

            readings.append(reading)
            if absence is not None:
                absences.append(absence)

        if not readings:
            return None
        return _Batch(
            device_ref=device.device_ref,
            readings=readings,
            ops=self._plan(device, readings, absences),
            from_cursor=from_cursor,
            to_cursor=device.seq,
        )

    def _plan(
        self,
        device: CommissionedDevice,
        readings: list[dict[str, Any]],
        absences: list[dict[str, Any]],
    ) -> list[_Op]:
        """The ordered write plan. Nodes before the edges that reference them, so an edge
        never points at a node the log has not seen yet."""
        profile = device.profile
        ops: list[_Op] = []
        ingest = self.clock()

        if device.device_ref not in self._devices_ensured:
            ops.append(_Op("node", (profile["id"], [PROFILE_LABEL], {
                "profileRef": profile["id"],
                "deviceClass": profile["deviceClass"],
                "protocol": profile["protocol"],
                "definitionDigest": profile["definitionDigest"],
                "metricCount": len(profile["metrics"]),
                "simulated": contract.is_simulated(profile),
                "declaredAt": profile["declaredAt"],
                "specVersion": profile["specVersion"],
            })))
            ops.append(_Op("node", (device.device_ref, [DEVICE_LABEL], {
                "deviceRef": device.device_ref,
                "deviceProfileRef": profile["id"],
                "protocol": profile["protocol"],
                "simulated": contract.is_simulated(profile),
                "commissionedAt": ingest,
            })))
            ops.append(_Op("edge", (EDGE_CONFORMS_TO, device.device_ref, profile["id"])))

        types = sorted({r["kkoTypeRef"] for r in readings if r.get("kkoTypeRef")})
        for uri in types:
            if uri not in self._types_ensured:
                ops.append(_Op("node", (uri, [KKO_TYPE_LABEL], {"uri": uri, "vocab": "kko"})))

        by_reading = {a["relatedEventRef"]: a for a in absences}
        for reading in readings:
            absence = by_reading.get(reading["id"])
            if absence is not None:
                ops.append(_Op("node", (absence["id"], [ABSENCE_LABEL], {
                    "absenceId": absence["id"],
                    "kind": absence["kind"],
                    "observedAt": absence["observedAt"],
                    "relatedEventRef": absence["relatedEventRef"],
                    "causalNotes": absence["causalNotes"],
                    "specVersion": absence["specVersion"],
                })))
            ops.append(_Op("node", (
                reading["id"],
                [READING_LABEL, f"quality:{reading['quality']}"],
                contract.flatten(reading, ingest_time=ingest),
            )))
            ops.append(_Op("edge", (EDGE_FROM_DEVICE, reading["id"], device.device_ref)))
            ops.append(_Op("edge", (EDGE_DECLARED_BY, reading["id"], profile["id"])))
            if reading.get("kkoTypeRef"):
                ops.append(_Op("edge", (EDGE_KKO_TYPE, reading["id"], reading["kkoTypeRef"])))
            if absence is not None:
                ops.append(_Op("edge", (EDGE_ABSENCE, reading["id"], absence["id"])))
        return ops

    # -------------------------------------------------------------------- draining
    def _drain(self) -> PollResult:
        result = PollResult()
        while self._pending:
            batch = self._pending[0]
            result.attempted = True
            try:
                while batch.cursor < len(batch.ops):
                    op = batch.ops[batch.cursor]
                    if op.kind == "node":
                        self.writer.post_node(*op.args)
                    else:
                        self.writer.post_edge(*op.args)
                    batch.cursor += 1  # advance ONLY after the write lands
            except EmitError as e:
                log.warning("hellgraph write failed at op %d/%d (device=%s), batch stays "
                            "pending: %s", batch.cursor, len(batch.ops), batch.device_ref, e)
                result.hellgraph_ok = False
                break

            try:
                receipt = self.gateway.mint(
                    device_ref=batch.device_ref,
                    from_cursor=batch.from_cursor,
                    to_cursor=batch.to_cursor,
                    row_count=len(batch.readings),
                    batch_hash=contract.batch_hash(batch.readings),
                )
            except GatewayError as e:
                log.warning("receipt refused for device=%s — graph writes landed, batch stays "
                            "pending at the receipt step: %s", batch.device_ref, e)
                result.gateway_ok = False
                break

            batch.receipt_pending = False
            result.emitted += len(batch.readings)
            result.receipts += 1
            result.last_receipt_id = receipt.get("id") or receipt.get("receipt_id")
            for reading in batch.readings:
                result.quality_counts[reading["quality"]] = (
                    result.quality_counts.get(reading["quality"], 0) + 1
                )
            self._devices_ensured.add(batch.device_ref)
            self._types_ensured.update(
                r["kkoTypeRef"] for r in batch.readings if r.get("kkoTypeRef")
            )
            self._pending.pop(0)

        result.pending = sum(len(b.readings) for b in self._pending)
        return result
