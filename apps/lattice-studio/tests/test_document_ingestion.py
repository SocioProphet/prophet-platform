"""ST024 document→linked-knowledge pipeline: chunk → ie-engine → entity-resolution → hellgraph.

The moat under test: every mention is resolved to a golden record BEFORE the graph write, and lands
under the SAME canonical id scheme (_ent_id) the workbench and /extract use — so "Guzman & Gomez"
and "GYG" become ONE node, not two, and every fact carries doc-level provenance (doc_sha + source).
"""
from fastapi.testclient import TestClient

import lattice_studio.server as srv
from lattice_studio.server import _chunk_text, app

client = TestClient(app)


def test_ingest_write_gate(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "")
    r = client.post("/api/studio/ingest-document", json={"project": "team-x", "text": "GYG opened 12 stores."})
    assert r.status_code == 503  # fail-closed: no token configured → writes refused

    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    r = client.post("/api/studio/ingest-document", json={"project": "team-x", "text": "x"},
                    headers={"authorization": "Bearer nope"})
    assert r.status_code == 401


def test_ingest_empty_document_rejected(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    r = client.post("/api/studio/ingest-document", json={"project": "team-x", "text": "   \n\n  "},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 400


def _fake_req_factory(calls, ie_payload=None, er_payload=None, ie_err=None, er_err=None):
    async def fake_req(client, method, url, json=None):
        calls.append((method, url, json))
        if "/extract" in url and "ie-engine" in url:
            return (None, ie_err) if ie_err else (ie_payload, None)
        if "/resolve" in url:
            return (None, er_err) if er_err else (er_payload, None)
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            return {"ok": True}, None
        return None, f"unexpected url {url}"
    return fake_req


IE_PAYLOAD = {
    "entities": [
        {"text": "Guzman & Gomez", "type": "Organization", "mentions": 2},
        {"text": "GYG", "type": "Organization", "mentions": 3},
        {"text": "Sydney", "type": "Location", "mentions": 1},
        {"text": "the market", "type": "Topic", "count": 2},  # topics must NOT become entities
    ],
    "relations": [
        {"from": "GYG", "relation": "open", "to": "Sydney"},
        {"from": "Guzman & Gomez", "relation": "report", "to": "unmatched span"},  # endpoint unresolvable → skipped
    ],
    "claims": [{"type": "ASSERT", "text": "GYG opened 12 stores in Sydney.", "verifiable": True}],
}

# ER merges the two Organization mentions into one golden record with the long form canonical.
ER_PAYLOAD = {
    "replay_key": "er:2026-07-22",
    "merged": 1,
    "entities": [
        {"entity_id": "ent:m0", "members": ["m0", "m1"], "size": 2,
         "canonical": {"survivor": "m0", "name": "Guzman & Gomez", "attributes": {"type": "Organization"}}},
        {"entity_id": "ent:m2", "members": ["m2"], "size": 1,
         "canonical": {"survivor": "m2", "name": "Sydney", "attributes": {"type": "Location"}}},
    ],
    "review_queue": [],
}


def test_ingest_resolves_mentions_to_one_canonical_node(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    calls = []
    monkeypatch.setattr(srv, "_req", _fake_req_factory(calls, IE_PAYLOAD, ER_PAYLOAD))
    r = client.post("/api/studio/ingest-document",
                    json={"project": "team-x", "text": "GYG opened 12 stores in Sydney.", "filename": "gyg.txt"},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 200
    b = r.json()
    assert b["projectCollection"] == "proj-teamx"

    # ER ran and merged GYG into Guzman & Gomez → 2 canonical entities from 3 mentions
    assert b["resolution"] == {"resolved": True, "merged": 1, "review_queue": 0,
                               "replay_key": "er:2026-07-22", "entities": 2}
    assert b["extracted"]["mentions"] == 3  # topic filtered out

    node_writes = [j for m, u, j in calls if "/api/graph/node" in u]
    ids = {n["id"] for n in node_writes}
    # ONE node for the merged org, under the workbench-compatible id scheme — the whole point
    assert ids == {"proj-teamx:ent:guzman_&_gomez", "proj-teamx:ent:sydney"}
    org = next(n for n in node_writes if "guzman" in n["id"])
    assert org["properties"]["aliases"] == ["GYG"]
    assert "Organization" in org["labels"]

    # provenance: every fact traces to the document
    assert org["properties"]["epistemic_mode"] == "observed"
    assert org["properties"]["doc_sha"] == b["doc_sha"]
    assert org["properties"]["filename"] == "gyg.txt"
    assert org["properties"]["extractor"] == "lattice-studio/ie-pipeline-v1"

    # edges: GYG→Sydney maps through canonicals; the unmatched-span relation is skipped, not minted
    edge_writes = [j for m, u, j in calls if "/api/graph/edge" in u]
    assert len(edge_writes) == 1
    assert edge_writes[0]["from"] == "proj-teamx:ent:guzman_&_gomez"
    assert edge_writes[0]["to"] == "proj-teamx:ent:sydney"
    assert edge_writes[0]["label"] == "open"
    assert b["written"] == {"nodes": 2, "edges": 1, "skipped_relations": 1}
    assert b["claims"][0]["verifiable"] is True


def test_ingest_ie_unreachable_falls_back_deterministic(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    calls = []
    er_identity = {"replay_key": "er:x", "merged": 0, "entities": [], "review_queue": []}
    monkeypatch.setattr(srv, "_req", _fake_req_factory(calls, er_payload=er_identity, ie_err="connect timeout"))
    r = client.post("/api/studio/ingest-document",
                    json={"project": "team-x", "text": "HellGraph beats Neo4j on provenance."},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 200
    b = r.json()
    # degraded, visibly: fallback extractor tagged in provenance, error surfaced, but facts still written
    assert b["provenance"]["extractor"] == "lattice-studio/deterministic-v0-fallback"
    assert any("ie-engine" in e for e in b["errors"])
    assert b["written"]["nodes"] >= 2


def test_ingest_er_unreachable_identity_fallback(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    calls = []
    monkeypatch.setattr(srv, "_req", _fake_req_factory(calls, IE_PAYLOAD, er_err="ER down"))
    r = client.post("/api/studio/ingest-document",
                    json={"project": "team-x", "text": "GYG opened 12 stores in Sydney."},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 200
    b = r.json()
    # identity fallback: no merge, every mention its own node, error surfaced — never silent
    assert b["resolution"]["resolved"] is False
    assert b["written"]["nodes"] == 3
    assert any("entity-resolution" in e for e in b["errors"])


def test_chunker_preserves_paragraphs_and_splits_oversized():
    text = "Para one.\n\nPara two."
    assert _chunk_text(text) == ["Para one.\n\nPara two."]

    many = "\n\n".join(f"Paragraph number {i} talks about entity {i}." for i in range(300))
    chunks = _chunk_text(many)
    assert len(chunks) > 1
    assert all(len(c) <= 4000 for c in chunks)
    assert "".join(chunks).count("Paragraph number") == 300  # nothing dropped

    one_long_sentence = "word " * 2000  # no sentence boundaries at all
    chunks = _chunk_text(one_long_sentence)
    assert all(len(c) <= 4000 for c in chunks)
    assert sum(c.count("word") for c in chunks) == 2000
