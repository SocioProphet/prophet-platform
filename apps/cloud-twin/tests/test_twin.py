from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SEED = {
    "type": "GenesisSeed",
    "seed_id": "seed:operator/deploy-v1",
    "archetype": "deployment_twin",
    "ontology_slice": ["Artifact", "Host", "Policy"],
    "goal_schema": "schema:deployment_goal:v1",
    "organs_allowed": ["graph_retrieval", "policy_check"],
    "policy_profile": ["policy:deploy/base"],
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_seed_becomes_verified_twin_end_to_end():
    r = client.post("/twins", json=SEED)
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "verified"
    # lifecycle reconstructs: created -> authorized -> verified
    types = [e["event_type"] for e in body["events"]]
    assert types == ["twin.created", "twin.authorized", "twin.verified"]
    # every event is a valid TwinEventEnvelope with provenance (replayable)
    for e in body["events"]:
        assert e["type"] == "TwinEventEnvelope"
        assert e["provenance_refs"]


def test_replay_stream():
    twin_id = client.post("/twins", json=SEED).json()["twin_id"]
    r = client.get(f"/twins/{twin_id}/events")
    assert r.status_code == 200
    assert r.json()["count"] == 3


def test_bad_seed_fails_closed():
    bad = {"type": "GenesisSeed", "seed_id": "x"}  # missing archetype/ontology_slice/...
    r = client.post("/twins", json=bad)
    assert r.status_code == 422


def test_unknown_twin_404():
    assert client.get("/twins/twin:nope/xyz").status_code == 404
