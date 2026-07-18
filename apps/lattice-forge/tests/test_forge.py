"""lattice-forge tests — no live kernel needed (executor is injected)."""
import importlib
import os

os.environ["FORGE_TOKEN"] = "test-token"  # set before server import (fail-closed gate)

from fastapi.testclient import TestClient  # noqa: E402

from lattice_forge import execn, server  # noqa: E402

importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer test-token"}


def setup_function():
    # deterministic fake executor with per-session state — proves the session_id
    # is threaded so cells share a kernel (a real notebook, not one-shot cells).
    _state: dict[str, list[str]] = {}
    def fake(code, lang, to, session_id):
        hist = _state.setdefault(session_id, [])
        hist.append(code)
        return {"status": "ok",
                "outputs": [{"type": "stream", "name": "stdout", "text": f"ran:{code}|hist={len(hist)}|sid={session_id}"}],
                "error": None}
    execn.set_executor(fake)


def test_healthz_open():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["service"] == "lattice-forge"


def test_token_fail_closed():
    assert client.get("/v1/adapters").status_code == 401          # no token
    assert client.get("/v1/adapters", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_adapters_default_jupyterlab():
    d = client.get("/v1/adapters", headers=AUTH).json()
    assert d["default"] == "jupyterlab" and "quarto" in d["adapters"]


def test_session_lifecycle():
    s = client.post("/v1/session", json={"project": "p1", "adapter": "jupyterlab"}, headers=AUTH).json()
    assert s["adapter"] == "jupyterlab" and s["status"] == "ready"
    lst = client.get("/v1/sessions", params={"project": "p1"}, headers=AUTH).json()
    assert len(lst["sessions"]) == 1
    client.delete(f"/v1/session/{s['id']}", params={"project": "p1"}, headers=AUTH)
    assert client.get("/v1/sessions", params={"project": "p1"}, headers=AUTH).json()["sessions"] == []


def test_unknown_adapter_422():
    assert client.post("/v1/session", json={"project": "p", "adapter": "excel"}, headers=AUTH).status_code == 422


def test_execute_seals_receipt():
    r = client.post("/v1/execute", json={"project": "p2", "code": "1+1", "language": "python"}, headers=AUTH).json()
    assert r["status"] == "ok"
    assert r["outputs"][0]["text"].startswith("ran:1+1")
    rc = r["receipt"]
    assert rc["id"].startswith("sha256:") and rc["code_sha"].startswith("sha256:")
    assert rc["prev"] is None                      # first in chain


def test_session_state_carries_across_cells():
    # two cells in the SAME session share kernel history (persistent), a third in
    # a different session does not — the fix for stateless one-shot cells.
    a = client.post("/v1/execute", json={"project": "s", "session_id": "nbA", "code": "x=1"}, headers=AUTH).json()
    b = client.post("/v1/execute", json={"project": "s", "session_id": "nbA", "code": "x+1"}, headers=AUTH).json()
    c = client.post("/v1/execute", json={"project": "s", "session_id": "nbB", "code": "y=9"}, headers=AUTH).json()
    assert "hist=1" in a["outputs"][0]["text"] and "sid=nbA" in a["outputs"][0]["text"]
    assert "hist=2" in b["outputs"][0]["text"]     # same session → state accumulates
    assert "hist=1" in c["outputs"][0]["text"]     # different session → isolated


def test_receipt_chain_links():
    for code in ["a=1", "b=2", "c=3"]:
        client.post("/v1/execute", json={"project": "chain", "code": code}, headers=AUTH)
    ch = client.get("/v1/receipts", params={"project": "chain"}, headers=AUTH).json()
    assert ch["count"] == 3
    ids = [r["id"] for r in ch["receipts"]]
    assert ch["receipts"][1]["prev"] == ids[0]      # tamper-evident chain
    assert ch["receipts"][2]["prev"] == ids[1]


def test_degrades_when_kernel_unavailable():
    def boom(code, lang, to):
        raise execn.ForgeUnavailable("no kernel")
    execn.set_executor(boom)
    r = client.post("/v1/execute", json={"project": "p3", "code": "x"}, headers=AUTH).json()
    assert r["status"] == "degraded" and r["degraded"] == "no kernel"
    assert r["receipt"]["status"] == "degraded"      # still sealed — honest, not faked
