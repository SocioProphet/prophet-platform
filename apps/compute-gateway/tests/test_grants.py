"""The grant lifecycle — request → decision → quorum → issue → ledger → revoke.
Conforms to the vendored kernel schemas (grant / policy_decision / quorum_proof)."""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import grants, server, zerotrust  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    grants._reset()


def _validate_schema(payload, name):
    zerotrust.validate(payload, name)


def test_low_danger_grant_issues_without_quorum():
    r = client.post("/v1/grants", json={"kind": "graph-query", "project": "demo"}, headers=AUTH).json()
    assert r["decision"]["danger_class"] == "LOW" and r["decision"]["required_quorum"] == 0
    g = r["grant"]
    assert g is not None and g["grant_id"].startswith("grant-")
    _validate_schema(r["decision"], "policy_decision")
    _validate_schema(g, "grant")
    assert g["capability"]["operation"] == "graph-query:hellgraph"


def test_high_danger_requires_quorum_then_issues():
    # notebook = user code = HIGH → no signatures ⇒ no grant, decision returned
    denied = client.post("/v1/grants", json={"kind": "notebook", "project": "demo"}, headers=AUTH).json()
    assert denied["grant"] is None and denied["quorum_required"] == 1
    assert denied["decision"]["danger_class"] == "HIGH"
    # with a human quorum signature ⇒ grant issues, carrying a conforming quorum_proof
    ok = client.post("/v1/grants", json={"kind": "notebook", "project": "demo",
                     "quorum_signatures": [{"spiffe_id": "spiffe://ops/alice", "sig": "s" * 24}]},
                     headers=AUTH).json()
    g = ok["grant"]
    assert g is not None
    _validate_schema(g, "grant")
    _validate_schema(g["quorum_proof"], "quorum_proof")
    assert g["quorum_proof"]["rule"] == "1-of-N-human"


def test_validate_revoke_and_ledger():
    gid = client.post("/v1/grants", json={"kind": "graph-stats", "project": "demo"},
                      headers=AUTH).json()["grant"]["grant_id"]
    v = client.get(f"/v1/grants/{gid}", headers=AUTH).json()
    assert v["validity"]["valid"] is True
    assert client.post(f"/v1/grants/{gid}/revoke", headers=AUTH).json()["revoked"] is True
    assert client.get(f"/v1/grants/{gid}", headers=AUTH).json()["validity"]["revoked"] is True
    # the ledger recorded issue → validate → revoke
    ops = [e["op"] for e in client.get("/v1/grants/ledger", headers=AUTH).json()["events"]]
    assert "OP_GRANT_ISSUE" in ops and "OP_GRANT_REVOKE" in ops


def test_revoke_unknown_404_and_auth():
    assert client.post("/v1/grants/nope/revoke", headers=AUTH).status_code == 404
    assert client.post("/v1/grants", json={"kind": "graph-query"}).status_code == 401
    assert client.get("/v1/grants/ledger").status_code == 401


# --- quorum independence: counting signatures is not counting voices -------------------------

def test_the_requester_cannot_approve_their_own_high_danger_grant():
    """The hole this closes: `len(sigs) >= need` accepted a signature from the actor themselves."""
    r = grants.request_grant(
        kind="notebook", backend="local", project="p", actor="alice", session=None,
        quorum_signatures=[{"spiffe_id": f"{grants.ISSUER}/p/alice", "sig": "s" * 24}])
    assert r["grant"] is None, "a self-signed quorum must not issue a HIGH-danger grant"
    assert "is not a quorum" in r["reason"]


def test_an_independent_human_still_satisfies_the_quorum():
    r = grants.request_grant(
        kind="notebook", backend="local", project="p", actor="alice", session=None,
        quorum_signatures=[{"spiffe_id": "spiffe://ops/bob", "sig": "s" * 24}])
    assert r["grant"] is not None
    assert r["grant"]["quorum_proof"]["rule"] == "1-of-N-human"


def test_the_same_signer_twice_is_one_voice():
    """Guards the N-of-M case: required_quorum > 1 must not be satisfied by one repeated signer."""
    reason = grants._check_quorum_independence(
        [{"spiffe_id": "spiffe://ops/bob", "sig": "x"}, {"spiffe_id": "spiffe://ops/bob", "sig": "y"}],
        actor="alice", project="p")
    assert reason and "one voice" in reason


def test_an_unidentified_signer_is_refused_not_skipped():
    reason = grants._check_quorum_independence([{"sig": "x"}], actor="alice", project="p")
    assert reason and "cannot be shown independent" in reason


def test_two_distinct_humans_pass():
    assert grants._check_quorum_independence(
        [{"spiffe_id": "spiffe://ops/bob", "sig": "x"}, {"spiffe_id": "spiffe://ops/carol", "sig": "y"}],
        actor="alice", project="p") is None
