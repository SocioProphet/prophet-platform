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


def _run_workflow():
    return client.post("/v1/compute", json={"kind": "workflow", "project": "demo", "spec": {"steps": [
        {"id": "a", "kind": "notebook", "spec": {"code": "1"}},
        {"id": "b", "kind": "notebook", "spec": {"code": "2"}, "needs": ["a"]},
    ]}}, headers=AUTH).json()


def test_workflow_ro_crate_aggregates_every_step_with_proof():
    rid = _run_workflow()["receipt"]["id"]
    crate = client.get(f"/v1/workflows/{rid}/ro-crate", params={"project": "demo"}, headers=AUTH).json()
    ids = _ids(crate)
    assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
    # one research object, the composite run as its main entity, referencing both steps in order
    assert ids["./"]["mainEntity"]["@id"] == "#run"
    assert [s["@id"] for s in ids["#run"]["step"]] == ["#step0", "#step1"]
    # each step is its own CreateAction, chained by prov:wasInformedBy (pipeline lineage)
    assert "CreateAction" in ids["#step0"]["@type"] and "CreateAction" in ids["#step1"]["@type"]
    assert ids["#step1"]["prov:wasInformedBy"][0]["@id"] == "#step0"
    # every step carries its own content-addressed receipt + a signed attestation
    for i in (0, 1):
        assert len(ids[f"#step{i}-receipt"]["identifier"]) > 0
        assert ids[f"#step{i}-output"]["prov:wasGeneratedBy"]["@id"] == f"#step{i}"
        assert f"#step{i}-attestation" in ids
    # ...and so does the composite
    assert "#attestation" in ids and ids["#receipt"]["identifier"] == rid


def test_workflow_ro_crate_422_on_a_plain_run():
    rid = _run()["receipt"]["id"]   # a notebook, not a workflow
    r = client.get(f"/v1/workflows/{rid}/ro-crate", params={"project": "demo"}, headers=AUTH)
    assert r.status_code == 422 and "not a workflow" in r.json()["detail"]


def test_workflow_ro_crate_404_for_unknown():
    _run()
    assert client.get("/v1/workflows/sha256:nope/ro-crate", params={"project": "demo"},
                      headers=AUTH).status_code == 404


def test_build_unsigned_has_no_attestation():
    # a receipt with no signature → crate omits the attestation node (never faked)
    from compute_gateway.contract import Receipt
    r = Receipt(id="sha256:" + "a" * 64, project="p", kind="notebook", backend="forge",
                runtime="python3", inputs_sha="sha256:" + "b" * 64, outputs_sha="sha256:" + "c" * 64,
                status="ok", actor="user", epistemic_status="derived", prev=None, ts=0.0)
    crate = rocrate.build(r)
    assert "#attestation" not in {e["@id"] for e in crate["@graph"]}
