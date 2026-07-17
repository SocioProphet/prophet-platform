"""GRL-mesh — aggregation core + the token-gated opt-in envelope."""
import os

os.environ["GRL_MESH_TOKEN"] = "test-token"  # set before importing the app (module-level read)

from fastapi.testclient import TestClient  # noqa: E402
from grl_mesh.aggregator import MeshAggregator  # noqa: E402
from grl_mesh.server import app  # noqa: E402

client = TestClient(app)
AUTH = {"authorization": "Bearer test-token", "x-sovereign-id": "node-A"}


def test_aggregator_means_and_contributors():
    agg = MeshAggregator()
    agg.publish("retrieval-mode", [{"action": "kb", "context_bucket": "hi-trust", "reward": 1.0},
                                    {"action": "kb", "context_bucket": "hi-trust", "reward": 0.5}], "node-A")
    agg.publish("retrieval-mode", [{"action": "kb", "context_bucket": "hi-trust", "reward": 0.9}], "node-B")
    p = agg.prior("retrieval-mode")
    kb = next(x for x in p["priors"] if x["action"] == "kb" and x["context_bucket"] == "hi-trust")
    assert kb["n"] == 3
    assert abs(kb["mean_reward"] - (1.0 + 0.5 + 0.9) / 3) < 1e-6
    assert p["contributors"] == 2  # two sovereign-ids contributed


def test_aggregator_skips_malformed_and_clamps():
    agg = MeshAggregator()
    n = agg.publish("p", [
        {"action": "a", "context_bucket": "b", "reward": 2.0},   # clamped to 1
        {"action": "", "context_bucket": "b", "reward": 0.5},    # no action → skip
        {"action": "a", "context_bucket": "b"},                  # no reward → skip
    ], "n1")
    assert n == 1
    assert agg.prior("p")["priors"][0]["mean_reward"] == 1.0


def test_healthz_reports_gated():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["publish_gated"] is True


def test_publish_requires_token():
    r = client.post("/grl/publish", json={"policy": "retrieval-mode", "observations": []})  # no auth header
    assert r.status_code == 401


def test_publish_then_prior_roundtrip():
    body = {"policy": "retrieval-mode", "observations": [
        {"action": "vector-rag", "context_bucket": "sparse", "reward": 0.8},
        {"action": "vector-rag", "context_bucket": "sparse", "reward": 0.6},
    ]}
    r = client.post("/grl/publish", json=body, headers=AUTH)
    assert r.status_code == 200 and r.json()["accepted"] == 2
    p = client.get("/grl/prior?policy=retrieval-mode").json()
    vr = next(x for x in p["priors"] if x["action"] == "vector-rag")
    assert abs(vr["mean_reward"] - 0.7) < 1e-6 and vr["n"] == 2
    assert p["contributors"] >= 1
