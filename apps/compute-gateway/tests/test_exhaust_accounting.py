"""W6.1 exhaust accounting (design-register: exhaust-accounting).

Every receipt now carries bytes_in/bytes_out (v1 entropy proxy = compression ratio),
and an adapter that discards things reports them as an `_exhaust` ExhaustRecord —
content-addressed into the artifact store and bound to the receipt via exhaust_sha.
Back-compat is a law, not a hope: receipts persisted BEFORE these fields existed
must keep verifying (the fields ride outside the id-hash body, like the attestation)."""
import contextlib
import importlib
import os
import tempfile

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, artifacts, engine, persistence, receipts, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}

EXHAUST = {
    "type": "ExhaustRecord", "specVersion": "2.0", "source": "compute",
    "counts": {"candidatesRejected": 2},
    "bytesIn": 100, "bytesOut": 10,
    "items": [{"kind": "candidate", "sha256": "a" * 64, "size": 90}],
}


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    artifacts._reset()

    async def plain(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text="ok")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}

    async def discarding(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text="kept")],
                "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None,
                "_exhaust": EXHAUST}

    adapters.set_backend("forge", plain)
    adapters.set_backend("hellgraph:graph-query", discarding)


def _run(kind, spec):
    return client.post("/v1/compute", json={"kind": kind, "project": "demo", "spec": spec},
                       headers=AUTH).json()


def test_every_receipt_carries_bytes_accounting():
    r = _run("notebook", {"code": "1+1"})
    rc = r["receipt"]
    assert rc["bytes_in"] == receipts.canonical_size({"code": "1+1"})
    assert rc["bytes_out"] == receipts.canonical_size(r["outputs"])
    assert rc["exhaust_sha"] is None      # nothing was discarded → no ledger, never faked


def test_exhaust_record_is_bound_and_retrievable():
    r = _run("graph-query", {"label": "demo"})
    sha = r["receipt"]["exhaust_sha"]
    assert sha == artifacts.digest(EXHAUST)   # the binding IS the retrieval address
    blob = client.get(f"/v1/artifacts/{sha}", headers=AUTH).json()["blob"]
    assert blob == EXHAUST                     # discard ledger retrievable, hash-addressed
    # and the chain (with the new fields riding along) still verifies
    assert client.get("/v1/receipts/verify", params={"project": "demo"}, headers=AUTH).json()["valid"]


def test_workflow_composite_carries_bytes_too():
    r = client.post("/v1/compute", json={"kind": "workflow", "project": "demo", "spec": {"steps": [
        {"id": "a", "kind": "notebook", "spec": {"code": "1"}},
        {"id": "b", "kind": "graph-query", "spec": {"label": "demo"}, "needs": ["a"]},
    ]}, "no_cache": True}, headers=AUTH).json()
    assert r["receipt"]["bytes_in"] is not None and r["receipt"]["bytes_out"] is not None
    # the discarding STEP carries its exhaust on its own receipt
    step_ids = [s["receipt"] for s in r["outputs"][0]["data"]["steps"]]
    chain = {c["id"]: c for c in client.get("/v1/receipts", params={"project": "demo"},
                                            headers=AUTH).json()["receipts"]}
    assert chain[step_ids[1]]["exhaust_sha"] == artifacts.digest(EXHAUST)


def test_pre_fields_persisted_receipts_still_verify():
    """The back-compat law: a receipt persisted BEFORE W6.1 (no exhaust fields in its
    stored JSON) must rehydrate and verify unchanged — the fields are outside the id-hash."""
    prev_env = os.environ.get("GATEWAY_STORE_DIR")
    with tempfile.TemporaryDirectory() as d:
        os.environ["GATEWAY_STORE_DIR"] = d
        persistence._reset_connection()
        try:
            receipts._CHAINS.clear()
            r = receipts.seal("compat", kind="notebook", backend="forge", runtime="py",
                              inputs={"x": 1}, outputs=[{"y": 2}], status="ok",
                              actor="t", epistemic_status="derived")
            # simulate a pre-W6.1 stored row: strip the new fields from the persisted JSON
            import json as _json
            con = persistence._conn()
            (body_json,) = con.execute("SELECT body FROM receipts WHERE id=?", (r.id,)).fetchone()
            body = _json.loads(body_json)
            for k in ("bytes_in", "bytes_out", "exhaust_sha"):
                body.pop(k, None)
            con.execute("UPDATE receipts SET body=? WHERE id=?", (_json.dumps(body), r.id))
            con.commit()
            # restart: rehydrate from the stripped (old-format) row
            receipts._CHAINS.clear()
            persistence._reset_connection()
            receipts.hydrate()
            v = receipts.verify("compat")
            assert v["valid"] and v["count"] == 1          # old-format receipt verifies
            assert receipts.chain("compat")[0].bytes_in is None   # honestly absent, not faked
        finally:
            if prev_env is None:
                os.environ.pop("GATEWAY_STORE_DIR", None)
            else:
                os.environ["GATEWAY_STORE_DIR"] = prev_env
            persistence._reset_connection()
            receipts._CHAINS.clear()
