"""ER spine tests: opt-in entitlement gate, spine end-to-end, and schema-conformant emission.

The schema-validation tests are the strong fitness signal — emitted graph_delta / proof-certificate
envelopes are validated against the vendored regis-entity-graph domain schemas.
"""
import json
import pathlib

import jsonschema
from fastapi.testclient import TestClient

from regis_acr_api.main import app

client = TestClient(app)
SCHEMAS = pathlib.Path(__file__).resolve().parents[1] / "schemas"
ENT = {"X-Regis-Entitlement": "sub-test-token"}


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


# --- opt-in / subscription gate -------------------------------------------------------------
def test_plane_info_readable_without_entitlement():
    r = client.get("/v1/plane-info")
    assert r.status_code == 200
    body = r.json()
    assert body["activation"] == "opt-in-subscription"
    assert body["local_first_core"] == "Noetica"


def test_spine_gated_without_entitlement():
    # every spine endpoint is inert (402) until the subscription is opted-in
    assert client.post("/v1/event-ir/ingest", json={}).status_code == 402
    assert client.post("/v1/resolve/entities", json={}).status_code == 402
    assert client.post("/v1/policy/check", json={}).status_code == 402
    r = client.post("/v1/resolve/entities", json={})
    assert "opt-in subscription" in r.json()["detail"]


def test_spine_active_with_entitlement():
    r = client.post("/v1/event-ir/ingest", json={"scope": "CITIZEN_FOG"}, headers=ENT)
    assert r.status_code == 200 and r.json()["accepted"] is True


# --- spine end-to-end + schema conformance --------------------------------------------------
def test_resolve_emits_conformant_delta_and_proof():
    r = client.post(
        "/v1/resolve/entities",
        json={"scope": "CITIZEN_FOG", "mentions": [{"text": "a"}, {"text": "b"}]},
        headers=ENT,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"] == "VERIFIED"  # >=2 evidence
    # graph_delta validates against the domain schema
    jsonschema.validate(body["graph_delta"], _schema("graph_delta.schema.json"))
    # the upserted node validates too
    node = body["graph_delta"]["operations"][0]["node"]
    jsonschema.validate(node, _schema("node.schema.json"))
    # proof-certificate is retrievable and conformant
    proof = client.get(f"/v1/proof/{body['proof_ref']}", headers=ENT).json()
    jsonschema.validate(proof, _schema("proof-certificate.schema.json"))
    assert proof["claim_type"] == "ProveLinkage"
    assert proof["certificate_hash"].startswith("sha256:")


def test_single_mention_requires_review():
    r = client.post("/v1/resolve/entities", json={"mentions": [{"text": "a"}]}, headers=ENT)
    assert r.json()["result"] == "REQUIRES_REVIEW"


def test_policy_vetoes_cross_scope_merge():
    r = client.post(
        "/v1/policy/check",
        json={"action": "MERGE", "src_scope": "CITIZEN_FOG", "dst_scope": "ADTECH"},
        headers=ENT,
    )
    body = r.json()
    assert body["vetoed"] is True and body["decision"] == "VETOED"
    proof = client.get(f"/v1/proof/{body['proof_ref']}", headers=ENT).json()
    assert proof["result"] == "REFUTED"


def test_graph_upsert_roundtrip():
    delta = client.post(
        "/v1/resolve/entities", json={"mentions": [{"text": "x"}, {"text": "y"}]}, headers=ENT
    ).json()["graph_delta"]
    node_id = delta["operations"][0]["node"]["node_id"]
    up = client.post("/v1/graph/upsert", json=delta, headers=ENT)
    assert up.status_code == 200 and up.json()["applied"] == 1
    got = client.get(f"/v1/graph/entity/{node_id}", headers=ENT)
    assert got.status_code == 200 and got.json()["node_id"] == node_id
