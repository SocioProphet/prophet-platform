"""RO-Crate 1.1 export — every governed run as a portable, signed research object."""
import base64
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"
os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(b"0" * 32).decode()   # signed receipts

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, engine, receipts, rocrate, server, zerotrust  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"

    async def fake_forge(spec, project, session):
        return {"outputs": [ComputeOutput(type="result", text="ok")],
                "runtime": "python3", "status": "ok", "error": None, "degraded": None}
    adapters.set_backend("forge", fake_forge)


def _run():
    return client.post("/v1/compute",
                       json={"kind": "notebook", "project": "demo", "spec": {"code": "1+1"}},
                       headers=AUTH).json()


def _ids(crate):
    return {e["@id"]: e for e in crate["@graph"]}


def test_ro_crate_is_valid_1_1():
    rid = _run()["receipt"]["id"]
    crate = client.get(f"/v1/receipts/{rid}/ro-crate", params={"project": "demo"}, headers=AUTH).json()
    assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
    ids = _ids(crate)
    # required descriptor + root data entity
    meta = ids["ro-crate-metadata.json"]
    assert meta["conformsTo"]["@id"] == "https://w3id.org/ro/crate/1.1"
    assert meta["about"]["@id"] == "./"
    root = ids["./"]
    assert root["@type"] == "Dataset" and root["mainEntity"]["@id"] == "#run"


def test_run_is_createaction_with_prov_and_content_hashes():
    rid = _run()["receipt"]["id"]
    crate = client.get(f"/v1/receipts/{rid}/ro-crate", params={"project": "demo"}, headers=AUTH).json()
    ids = _ids(crate)
    run = ids["#run"]
    assert "CreateAction" in run["@type"] and "prov:Activity" in run["@type"]
    out = ids["#output"]
    assert out["prov:wasGeneratedBy"]["@id"] == "#run"
    assert len(out["sha256"]) == 64                      # content-addressed, no prefix
    assert len(ids["#input"]["sha256"]) == 64


def test_ro_crate_embeds_signed_attestation():
    rid = _run()["receipt"]["id"]
    crate = client.get(f"/v1/receipts/{rid}/ro-crate", params={"project": "demo"}, headers=AUTH).json()
    ids = _ids(crate)
    assert "#attestation" in ids
    att = ids["#attestation"]
    assert att["encodingFormat"] == "application/vnd.in-toto+json"
    props = {p["name"]: p["value"] for p in att["additionalProperty"]}
    assert props["algorithm"] == "Ed25519" and props["signature"]  # the proof travels with the object


def test_ro_crate_404_for_unknown_receipt():
    _run()
    assert client.get("/v1/receipts/sha256:nope/ro-crate", params={"project": "demo"},
                      headers=AUTH).status_code == 404


def test_ro_crate_requires_auth():
    assert client.get("/v1/receipts/x/ro-crate").status_code == 401


def test_build_unsigned_has_no_attestation():
    # a receipt with no signature → crate omits the attestation node (never faked)
    from compute_gateway.contract import Receipt
    r = Receipt(id="sha256:" + "a" * 64, project="p", kind="notebook", backend="forge",
                runtime="python3", inputs_sha="sha256:" + "b" * 64, outputs_sha="sha256:" + "c" * 64,
                status="ok", actor="user", epistemic_status="derived", prev=None, ts=0.0)
    crate = rocrate.build(r)
    assert "#attestation" not in {e["@id"] for e in crate["@graph"]}
