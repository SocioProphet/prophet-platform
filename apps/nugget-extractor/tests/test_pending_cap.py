"""Back-pressure — the pending-queue ceiling that turns a hellgraph outage
from an OOM crash into a 503.

Pre-fix: `self._pending.append(_PendingBatch(...))` had no ceiling. Once
hellgraph stopped answering, drain() stalled at the first failing op
(batch.cursor never advanced) while POST /v1/extract kept admitting new
documents — MAX_PENDING batches later the pod was OOM'd. The cap makes
that surface as status='degraded' at the API and a 503 at the HTTP layer,
matching the device-service run_once skip-with-reason posture.
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

from nugget_extractor import emitter as em, extract as ex
from nugget_extractor.clients import EmitError, GatewayError

TEXT = b"Network sales grew 22.6% to AUD 1,138.9 million.\n\nStore rollout continued."
DOC = "urn:srcos:document:cap-test"
RUN = "urn:srcos:run:cap-test"


class WedgedGraph:
    """hellgraph is down — every write raises EmitError, cursor never advances."""
    def post_node(self, *_a, **_kw): raise EmitError("hellgraph down")
    def post_edge(self, *_a, **_kw): raise EmitError("hellgraph down")


class UnusedGateway:
    """The gateway is never reached when the graph writes fail first."""
    def mint(self, **_kw): raise AssertionError("gateway must not be called when hellgraph is down")


def _extraction() -> ex.Extraction:
    return ex.extract(TEXT, filename="a.txt")


def test_submit_refuses_with_degraded_status_when_pending_at_ceiling():
    """Discriminating case: with a tiny MAX_PENDING (2) and a wedged hellgraph,
    the FIRST two submits fill _pending (drain fails, batch stays), and the
    THIRD submit is refused with status='degraded' and an explanatory reason.
    Pre-fix, the third submit appended anyway — _pending would grow unbounded."""
    with mock.patch.object(em, "MAX_PENDING", 2):
        e = em.NuggetEmitter(writer=WedgedGraph(), gateway=UnusedGateway(),
                             clock=lambda: "2026-07-29T00:00:00.000Z")
        # First 2 admitted (drain fails, batch stays pending).
        r1 = e.submit(_extraction(), doc_ref=DOC + "-1", run_ref=RUN)
        r2 = e.submit(_extraction(), doc_ref=DOC + "-2", run_ref=RUN)
        assert r1.status == "ok" and r2.status == "ok"
        assert r1.hellgraph_ok is False  # drain saw the outage
        assert len(e._pending) == 2

        # Third submit — cap engaged. This is the load-bearing assertion.
        r3 = e.submit(_extraction(), doc_ref=DOC + "-3", run_ref=RUN)
        assert r3.status == "degraded"
        assert r3.reason is not None
        assert "pending queue full" in r3.reason
        # Attribution comes from the LAST observed drain, not a hardcoded guess: here the
        # wedged dependency really is hellgraph, so it is named — and the gateway, never
        # reached, is NOT falsely reported down.
        assert "hellgraph is not keeping up" in r3.reason
        # No work was counted — a degraded submit is a pure no-op that contacted nothing.
        assert r3.documents == 0 and r3.extracted == 0 and r3.emitted == 0
        assert r3.attempted is False
        assert r3.hellgraph_ok is False and r3.gateway_ok is True
        # _pending did NOT grow past the cap.
        assert len(e._pending) == 2


def test_submit_admits_again_after_drain_frees_the_queue():
    """After the queue drains (e.g. hellgraph recovers), submits succeed again —
    the cap is a back-pressure signal, not a permanent kill-switch."""
    with mock.patch.object(em, "MAX_PENDING", 1):
        # Start wedged: fill the one slot.
        e = em.NuggetEmitter(writer=WedgedGraph(), gateway=UnusedGateway(),
                             clock=lambda: "2026-07-29T00:00:00.000Z")
        r1 = e.submit(_extraction(), doc_ref=DOC + "-a", run_ref=RUN)
        assert r1.status == "ok"
        # Next one is refused.
        r2 = e.submit(_extraction(), doc_ref=DOC + "-b", run_ref=RUN)
        assert r2.status == "degraded"

        # Simulate hellgraph recovery: swap in a healthy graph + gateway and drain.
        class HealthyGraph:
            def post_node(self, *_a, **_kw): pass
            def post_edge(self, *_a, **_kw): pass

        class HealthyGateway:
            def __init__(self): self.calls = 0
            def mint(self, **_kw):
                self.calls += 1
                return {"receipt_id": f"rcpt-{self.calls:04d}"}

        e.writer = HealthyGraph()
        e.gateway = HealthyGateway()
        drained = e.drain()
        assert drained.emitted > 0
        assert len(e._pending) == 0

        # Now new work is admitted again.
        r3 = e.submit(_extraction(), doc_ref=DOC + "-c", run_ref=RUN)
        assert r3.status == "ok"
        assert r3.emitted > 0


def test_max_pending_default_is_1000():
    """Guard against silent tuning drift — the default is contracted."""
    # Read the current module value, but also verify the env-driven default.
    from importlib import reload
    prev = os.environ.pop("NUGGET_EXTRACTOR_MAX_PENDING", None)
    try:
        reload(em)
        assert em.MAX_PENDING == 1000
    finally:
        if prev is not None:
            os.environ["NUGGET_EXTRACTOR_MAX_PENDING"] = prev
        reload(em)


def test_max_pending_env_override_is_respected():
    prev = os.environ.get("NUGGET_EXTRACTOR_MAX_PENDING")
    try:
        os.environ["NUGGET_EXTRACTOR_MAX_PENDING"] = "5"
        from importlib import reload
        reload(em)
        assert em.MAX_PENDING == 5
    finally:
        if prev is None:
            os.environ.pop("NUGGET_EXTRACTOR_MAX_PENDING", None)
        else:
            os.environ["NUGGET_EXTRACTOR_MAX_PENDING"] = prev
        from importlib import reload
        reload(em)


class _HealthyGraph:
    def post_node(self, *_a, **_kw):
        pass

    def post_edge(self, *_a, **_kw):
        pass


class _WedgedGateway:
    """Graph writes land, but the receipt step is down — the OTHER way the queue fills."""

    def mint(self, **_kw):
        raise GatewayError("gateway receipt refused")


def test_degraded_refusal_attributes_the_gateway_when_it_is_the_stalled_side():
    """The misattribution fix. When the queue fills because the compute-gateway receipt
    step is wedged (graph writes succeed), the refusal must name the GATEWAY and report
    gateway_ok False / hellgraph_ok True — from the last real drain observation. Pre-fix
    every degraded refusal hardcoded a hellgraph-centric reason and both deps False, so an
    operator chasing a gateway outage was pointed at hellgraph."""
    with mock.patch.object(em, "MAX_PENDING", 2):
        e = em.NuggetEmitter(writer=_HealthyGraph(), gateway=_WedgedGateway(),
                             clock=lambda: "2026-07-29T00:00:00.000Z")
        r1 = e.submit(_extraction(), doc_ref=DOC + "-g1", run_ref=RUN)
        r2 = e.submit(_extraction(), doc_ref=DOC + "-g2", run_ref=RUN)
        assert r1.status == "ok" and r2.status == "ok"
        # The drain reached the gateway and it failed; hellgraph was fine.
        assert r1.gateway_ok is False and r1.hellgraph_ok is True
        assert len(e._pending) == 2

        r3 = e.submit(_extraction(), doc_ref=DOC + "-g3", run_ref=RUN)
        assert r3.status == "degraded"
        assert "compute-gateway receipt step" in r3.reason, r3.reason
        assert "hellgraph is not keeping up" not in r3.reason  # NOT misattributed to hellgraph
        assert r3.gateway_ok is False and r3.hellgraph_ok is True
        assert r3.attempted is False  # a refusal observed nothing this call


def test_max_pending_rejects_non_int_and_clamps_negative():
    """The OOM guard must not itself become a boot-time outage or a permanent kill.
    A non-int env falls back to the default; a negative env clamps to 0 (never a
    negative cap, which would refuse every submit forever)."""
    assert em._parse_max_pending("off", default=1000) == 1000      # non-int -> default
    assert em._parse_max_pending("", default=1000) == 1000         # empty -> default
    assert em._parse_max_pending(None, default=1000) == 1000       # unset -> default
    assert em._parse_max_pending("-5", default=1000) == 0          # negative -> clamped
    assert em._parse_max_pending("42", default=1000) == 42         # valid honoured
