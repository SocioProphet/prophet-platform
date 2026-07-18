"""Content-addressed artifact store — dedup + data-level lineage/diff."""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "*"          # entitle every project (dedup across projects)
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, artifacts, engine, receipts, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    artifacts._reset()
    os.environ["COMPUTE_ENTITLEMENTS"] = "*"

    async def fake(spec, project, session):
        # output depends on spec.code → different code ⇒ different content digest
        return {"outputs": [ComputeOutput(type="result", text=f"out:{spec.get('code')}")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}
    adapters.set_backend("forge", fake)


def _run(code, project="demo"):
    return client.post("/v1/compute",
                       json={"kind": "notebook", "project": project, "spec": {"code": code}},
                       headers=AUTH).json()


def test_output_is_content_addressed_on_the_result():
    r = _run("1+1")
    assert len(r["artifacts"]) == 1 and r["artifacts"][0].startswith("sha256:")
    # the blob is retrievable by its content address
    got = client.get(f"/v1/artifacts/{r['artifacts'][0]}", headers=AUTH).json()
    assert got["blob"]["text"] == "out:1+1"


def test_identical_output_dedupes_across_runs():
    # same output content from two DIFFERENT projects (distinct memo keys → both execute)
    a = _run("SAME", project="demo")
    b = _run("SAME", project="demo2")
    assert a["artifacts"] == b["artifacts"]                 # same content ⇒ same digest
    st = client.get("/v1/artifacts/stats", headers=AUTH).json()
    assert st["puts"] == 2 and st["dedup_hits"] == 1 and st["unique_blobs"] == 1


def test_receipt_artifacts_index():
    r = _run("x")
    idx = client.get(f"/v1/receipts/{r['receipt']['id']}/artifacts", headers=AUTH).json()
    assert idx["artifacts"] == r["artifacts"]


def test_diff_identical_and_changed():
    a = _run("SAME", project="demo")
    b = _run("SAME", project="demo2")
    d = client.get("/v1/diff", params={"a": a["receipt"]["id"], "b": b["receipt"]["id"]}, headers=AUTH).json()
    assert d["identical"] is True and d["shared"] and not d["added"] and not d["removed"]

    c = _run("DIFFERENT", project="demo3")
    d2 = client.get("/v1/diff", params={"a": a["receipt"]["id"], "b": c["receipt"]["id"]}, headers=AUTH).json()
    assert d2["identical"] is False and d2["added"] and d2["removed"]


def test_artifact_404_and_auth():
    _run("x")
    assert client.get("/v1/artifacts/sha256:nope", headers=AUTH).status_code == 404
    assert client.get("/v1/artifacts/stats").status_code == 401
    assert client.get("/v1/diff", params={"a": "x", "b": "y"}).status_code == 401
