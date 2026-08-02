"""Sub-tier hardening — the three findings from adversarial review at
main@55fb4c5a. Each test exercises the discriminating case: the ONE outcome
that could only be produced by the missing guard, so a regression to the
pre-fix behaviour would flip the assertion.

  1) receipts.seal race window — concurrent seals for the same project
     could compute the same `prev`, both persist under seq=N, and one
     receipt was silently dropped by INSERT OR REPLACE. Threaded stress
     test asserts chain length == threads and every prev-link is intact.
  2) signing state / /healthz visibility — a MALFORMED
     GATEWAY_SIGNING_KEY used to silently downgrade to unsigned; verify()
     couldn't notice (it only fails on a present-but-invalid signature),
     so an operator lost signatures with a green health check.
"""
from __future__ import annotations

import base64
import importlib
import os
import sys
import threading

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import receipts, server, signing  # noqa: E402

AUTH = {"Authorization": "Bearer t"}


# ── #1: receipts.seal race window ────────────────────────────────────────

def _reset_receipts() -> None:
    receipts._CHAINS.clear()
    # NB: don't clear _LOCKS — the whole point is that per-project locks are stable.


def test_concurrent_seals_for_same_project_never_lose_a_receipt():
    """N threads racing seal() on ONE project must produce N receipts, all
    chained (each `prev` is the previous receipt's id). Pre-fix, two threads
    could read the same `prev`, both append, both persist under the same
    seq — INSERT OR REPLACE dropped one, verify() reported valid:False with
    'prev-link broken', OR the two duplicate rows agreed on prev but the
    chain silently lost a receipt (count < threads)."""
    _reset_receipts()
    N = 32
    barrier = threading.Barrier(N)
    errors: list[BaseException] = []

    def seal_one(i: int) -> None:
        try:
            barrier.wait()                # maximise race window
            receipts.seal(
                "race-project", kind="notebook", backend="forge", runtime="python3",
                inputs={"i": i}, outputs=[{"i": i}], status="ok", actor="tester",
                epistemic_status="derived")
        except BaseException as e:  # noqa: BLE001 — surface racy exceptions
            errors.append(e)

    threads = [threading.Thread(target=seal_one, args=(i,)) for i in range(N)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert not errors, f"seal() raised under contention: {errors[:3]}"
    chain = receipts.chain("race-project")
    assert len(chain) == N, f"lost a receipt: {len(chain)}/{N} (race dropped one)"
    # Every prev-link resolves to the previous receipt's id — the chain integrity
    # check that verify() runs, expressed directly so a failure names the bug.
    prev = None
    for r in chain:
        assert r.prev == prev, f"prev-link broken at {r.id[:16]}: got {r.prev!r} want {prev!r}"
        prev = r.id
    # Full contract: verify() must still pass end-to-end.
    v = receipts.verify("race-project")
    assert v["valid"] is True, v
    assert v["count"] == N


def test_concurrent_seals_across_projects_do_not_serialize_on_each_other():
    """Per-project locks — seals for DIFFERENT projects must not block each
    other, so a slow project cannot starve the rest. This is a shape assert:
    both chains end up complete, independent of interleaving."""
    _reset_receipts()
    N = 8
    barrier = threading.Barrier(2 * N)

    def seal_into(project: str, i: int) -> None:
        barrier.wait()
        receipts.seal(project, kind="notebook", backend="forge", runtime="python3",
                      inputs={"i": i}, outputs=[{"i": i}], status="ok", actor="tester",
                      epistemic_status="derived")

    threads = ([threading.Thread(target=seal_into, args=("a", i)) for i in range(N)]
               + [threading.Thread(target=seal_into, args=("b", i)) for i in range(N)])
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(receipts.chain("a")) == N
    assert len(receipts.chain("b")) == N
    assert receipts.verify("a")["valid"] is True
    assert receipts.verify("b")["valid"] is True


# ── #3: signing state + /healthz visibility ──────────────────────────────

def test_signing_state_reports_signed_when_valid_key_configured():
    prev = os.environ.get("GATEWAY_SIGNING_KEY")
    try:
        os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"0" * 32).decode()
        assert signing.signing_state() == "signed"
    finally:
        if prev is None: os.environ.pop("GATEWAY_SIGNING_KEY", None)
        else: os.environ["GATEWAY_SIGNING_KEY"] = prev


def test_signing_state_reports_unsigned_when_no_key():
    prev = os.environ.get("GATEWAY_SIGNING_KEY")
    try:
        os.environ.pop("GATEWAY_SIGNING_KEY", None)
        assert signing.signing_state() == "unsigned"
    finally:
        if prev is not None: os.environ["GATEWAY_SIGNING_KEY"] = prev


def test_signing_state_reports_error_for_malformed_key():
    """The bug this whole story exists to make loud: a bad key used to be
    silently swallowed to None, receipts rode unsigned, and verify() couldn't
    tell. Now signing_state() returns 'error' — a distinct third value that
    /healthz surfaces so an operator sees the fault."""
    prev = os.environ.get("GATEWAY_SIGNING_KEY")
    try:
        # Set to wrong-length base64 — decodes cleanly, but seed is not 32 bytes.
        os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"too-short").decode()
        assert signing.signing_state() == "error"
        # Set to invalid base64 — decode raises.
        os.environ["GATEWAY_SIGNING_KEY"] = "not-valid-base64!!!!"
        assert signing.signing_state() == "error"
    finally:
        if prev is None: os.environ.pop("GATEWAY_SIGNING_KEY", None)
        else: os.environ["GATEWAY_SIGNING_KEY"] = prev


def test_healthz_reports_signing_error_and_signed_ratio():
    """Integration: with a MALFORMED key, /healthz reports signing.state=='error'
    AND — crucially — receipts sealed under this configuration are NOT
    signature-verified (signed==0). Pre-fix, /healthz reported no signing state
    at all, and verify() cheerfully reported valid:True because it only flags
    a present-but-invalid signature. This test would have caught that failure
    mode: the whole gateway would report signing='error' + zero signed receipts,
    turning a silent misconfiguration into a loud one."""
    prev = os.environ.get("GATEWAY_SIGNING_KEY")
    _reset_receipts()
    try:
        os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"too-short").decode()
        # Re-import server so the signing-state read is fresh (it reads env at
        # call time, but seal captures the key at seal time — mint receipts here).
        importlib.reload(server)
        client = TestClient(server.app)

        # Seal a receipt under the bad-key regime.
        receipts.seal("hp", kind="notebook", backend="forge", runtime="python3",
                      inputs={"x": 1}, outputs=[{"x": 1}], status="ok", actor="op",
                      epistemic_status="derived")

        health = client.get("/healthz").json()
        assert health["signing"]["state"] == "error"
        assert health["signing"]["count"] >= 1
        # The whole point: the receipt is NOT signature-verified. Pre-fix, a caller
        # reading verify() saw valid:True and no signal that signatures were absent.
        assert health["signing"]["signed"] == 0
        assert health["signing"]["signed_ratio"] == 0.0

        # verify() ALSO stays valid:True — chain integrity is unaffected — so /healthz
        # is the ONLY loud surface for the misconfiguration. That's why it matters here.
        v = receipts.verify("hp")
        assert v["valid"] is True and v["signed"] == 0
    finally:
        if prev is None: os.environ.pop("GATEWAY_SIGNING_KEY", None)
        else: os.environ["GATEWAY_SIGNING_KEY"] = prev
        importlib.reload(server)


def test_healthz_reports_signed_ratio_when_key_is_valid():
    """Complement to the error case: with a valid key, /healthz shows the healthy
    signed / count ratio so an operator distinguishes 'no receipts yet' (ratio
    None) from 'receipts sealed and all signed' (ratio 1.0)."""
    prev = os.environ.get("GATEWAY_SIGNING_KEY")
    _reset_receipts()
    try:
        os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"1" * 32).decode()
        importlib.reload(server)
        client = TestClient(server.app)

        receipts.seal("hp2", kind="notebook", backend="forge", runtime="python3",
                      inputs={"x": 1}, outputs=[{"x": 1}], status="ok", actor="op",
                      epistemic_status="derived")

        health = client.get("/healthz").json()
        assert health["signing"]["state"] == "signed"
        assert health["signing"]["signed"] == health["signing"]["count"] >= 1
        assert health["signing"]["signed_ratio"] == 1.0
    finally:
        if prev is None: os.environ.pop("GATEWAY_SIGNING_KEY", None)
        else: os.environ["GATEWAY_SIGNING_KEY"] = prev
        importlib.reload(server)


# ── #4: /healthz signed-ratio aggregation vs concurrent seal() ───────────

def test_healthz_survives_concurrent_seals_on_new_projects():
    """/healthz aggregates signed_ratio over every chain. A concurrent seal() on a NEW
    project runs receipts._CHAINS.setdefault(project, []), mutating the dict — iterating
    it BARE raises `RuntimeError: dictionary changed size during iteration` and 500s the
    health endpoint under load, a liveness probe that flaps exactly when the gateway is
    busiest. server.healthz() now reads receipts.snapshot_all() (snapshot under the locks)
    instead. This drives the race directly: one thread hammers /healthz while another
    seals into ever-new projects. Pre-fix it 500s; post-fix every call is 200."""
    prev_key = os.environ.get("GATEWAY_SIGNING_KEY")
    # A valid key so seeded receipts are SIGNED: /healthz then runs signing.verify_signature
    # (an Ed25519 C call that RELEASES the GIL) once per receipt, which is exactly the
    # window a concurrent _CHAINS mutation needs to land mid-iteration. Unsigned receipts
    # short-circuit that call and the outer loop is too fast to observe the race.
    os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"9" * 32).decode()
    _reset_receipts()
    # Seed a fixed set of signed projects so the aggregation's outer loop has real work.
    for p in range(40):
        receipts.seal(f"seed-{p}", kind="notebook", backend="forge", runtime="python3",
                      inputs={"p": p}, outputs=[{"p": p}], status="ok", actor="t",
                      epistemic_status="derived")

    client = TestClient(server.app, raise_server_exceptions=False)
    errors: list = []
    stop = threading.Event()

    def churner() -> None:
        # Add a NEW project then drop it, so _CHAINS keeps CHANGING SIZE throughout the run
        # while staying bounded (~41 keys) — snapshot_all() stays O(projects) and the test
        # stays fast, but the dict is mutating on every pass, which is what the bare
        # `for chain in _CHAINS.values()` cannot survive.
        i = 0
        while not stop.is_set():
            receipts.seal(f"churn-{i}", kind="notebook", backend="forge", runtime="python3",
                          inputs={"i": i}, outputs=[{"i": i}], status="ok", actor="t",
                          epistemic_status="derived")
            receipts._CHAINS.pop(f"churn-{i}", None)   # size oscillates 40 <-> 41
            i += 1

    def healther() -> None:
        for _ in range(150):
            r = client.get("/healthz")   # raise_server_exceptions=False -> a handler crash is a 500
            if r.status_code != 200:
                errors.append(r.status_code)
                return

    prev_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-5)  # force frequent thread switches to widen the race window
    st = threading.Thread(target=churner)
    ht = threading.Thread(target=healther)
    try:
        st.start(); ht.start()
        ht.join()
    finally:
        stop.set(); st.join()
        sys.setswitchinterval(prev_interval)
        if prev_key is None:
            os.environ.pop("GATEWAY_SIGNING_KEY", None)
        else:
            os.environ["GATEWAY_SIGNING_KEY"] = prev_key

    assert not errors, f"/healthz returned non-200 while _CHAINS was mutating concurrently: {errors[:3]}"
