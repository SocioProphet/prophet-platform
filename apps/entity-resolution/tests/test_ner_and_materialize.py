"""NER extraction + live materialize-path teeth.

The materialize test proves the LIVE PATH end to end against a mock transport
(request in -> resolved entity out -> node/edge written to HellGraph -> SHA-256
hash-chained receipt landed), not just the resolver in isolation.
"""
from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from entity_resolution.graph_sink import GraphSink, materialize, sha
from entity_resolution.ner import ENTITY_CLASSES, extract_mentions, mentions_to_records
from entity_resolution.resolver import resolve
from entity_resolution.server import app, get_sink

client = TestClient(app)


# ---------------------------------------------------------------- NER (extract) --

def test_extract_emits_overlapping_multilabel_spans():
    # The ORG gazetteer phrase contains the "pediatric"/"clinic" context cues, so the
    # ORG span and the CHILD_CONTEXT/PATIENT_CONTEXT cue spans overlap the same region.
    text = "Emma visited Mercy Pediatric Clinic today."
    ms = extract_mentions(text, source_id="msg-1", source_type="message",
                          gazetteer={"Emma": "PERSON", "Mercy Pediatric Clinic": "ORG"})
    assert ms["schema_version"] == "regis.ner.mention_set.v0.1"
    assert ms["overlaps_allowed"] is True
    spans = [(m["span"]["start"], m["span"]["end"]) for m in ms["mentions"]]
    # "Mercy General" (ORG) and "pediatric"(CHILD_CONTEXT)/"patient ward" cues overlap the same region
    overlap = any(a is not b and a[0] < b[1] and b[0] < a[1] for i, a in enumerate(spans) for b in spans[i + 1:])
    assert overlap, "extractor must produce overlapping spans"
    classes = {m["entity_class"] for m in ms["mentions"]}
    assert "ORG" in classes and "PATIENT_CONTEXT" in classes and "CHILD_CONTEXT" in classes


def test_all_emitted_classes_are_in_taxonomy():
    text = "contact sk-ABCDEFGH12 track_9f8e7d6c user@example.com pediatric patient consent"
    ms = extract_mentions(text, source_id="doc-1")
    for m in ms["mentions"]:
        assert m["entity_class"] in ENTITY_CLASSES
        for s in m.get("secondary_classes", []):
            assert s in ENTITY_CLASSES


def test_high_risk_surfaces_are_fips_hashed():
    ms = extract_mentions("token sk-DEADBEEF99 and tracker trk_aa11bb22cc",
                          source_id="net-1", source_type="network_event", locality="ADTECH")
    hashed = [m for m in ms["mentions"] if "pii" in m]
    assert hashed, "credential/tracking surfaces must be minimized"
    for m in hashed:
        assert m["pii"]["minimized"] is True
        assert m["pii"]["hash_alg"] == "SHA-256"
        assert len(m["pii"]["value_hash"]) == 64
        # value_hash is the SHA-256 of the surface text (verifiable)
        import hashlib
        assert m["pii"]["value_hash"] == hashlib.sha256(m["span"]["text"].encode()).hexdigest()


def test_extract_endpoint():
    r = client.post("/extract/mentions", json={
        "text": "Acme Corp opted-in to the ad campaign",
        "source_id": "p-1", "source_type": "page",
        "gazetteer": {"Acme Corp": "ORG"},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mentions"] and any(m["entity_class"] == "ORG" for m in body["mentions"])


def test_ner_to_er_bridge():
    ms = extract_mentions("Acme Corp and Acme Corp", source_id="d1",
                          gazetteer={"Acme Corp": "ORG"})
    recs = mentions_to_records(ms)
    assert len(recs) == 2 and all(r["name"] == "Acme Corp" for r in recs)


# ------------------------------------------------------- live materialize path --

def _mock_sink(recorder: list[dict]) -> GraphSink:
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append({"url": str(request.url), "body": json.loads(request.content)})
        if request.url.path == "/api/graph/node":
            return httpx.Response(200, json={"ok": True, "node": json.loads(request.content)})
        if request.url.path == "/api/graph/edge":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/engine-receipts":
            return httpx.Response(200, json={"receiptId": "sha256:sealed", "memoized": False})
        return httpx.Response(404)

    return GraphSink(client=httpx.Client(transport=httpx.MockTransport(handler)),
                     compute_gateway_token="test-token")


def test_materialize_writes_graph_and_seals_receipt_direct():
    recorder: list[dict] = []
    from entity_resolution.resolver import Record
    # two Acme records that merge → one entity + one same_as edge
    res = resolve([Record("a", "Acme Corp", {"city": "NYC"}), Record("b", "Acme Corp", {"city": "NYC"})],
                  as_of="2026-08-03T00:00:00+00:00")
    landed = materialize(res, mention_set=None, sink=_mock_sink(recorder))

    node_calls = [c for c in recorder if c["url"].endswith("/api/graph/node")]
    edge_calls = [c for c in recorder if c["url"].endswith("/api/graph/edge")]
    receipt_calls = [c for c in recorder if c["url"].endswith("/v1/engine-receipts")]
    assert node_calls, "a resolved entity node must be written to HellGraph"
    assert edge_calls, "the merge must be written as a same_as edge"
    assert receipt_calls, "a receipt must be sealed to the gateway"

    receipt = landed["receipt"]
    assert receipt["id"].startswith("sha256:")
    assert receipt["inputs_sha"].startswith("sha256:") and receipt["outputs_sha"].startswith("sha256:")
    assert receipt["outputs_sha"] == sha({"entities": res["entities"], "graph": landed["graph"]})
    assert landed["seal"]["sealed"] is True


def test_materialize_endpoint_live_path_with_text():
    recorder: list[dict] = []
    app.dependency_overrides[get_sink] = lambda: _mock_sink(recorder)
    try:
        r = client.post("/resolve/materialize", json={
            "text": "Acme Corp merged with Acme Corp",
            "source_id": "doc-live-1",
            "gazetteer": {"Acme Corp": "ORG"},
            "as_of": "2026-08-03T00:00:00+00:00",
        })
    finally:
        app.dependency_overrides.pop(get_sink, None)
    assert r.status_code == 200, r.text
    body = r.json()
    # request in -> resolved entity out
    assert body["mention_set"]["schema_version"] == "regis.ner.mention_set.v0.1"
    assert body["resolution"]["entities"], "must resolve at least one entity"
    # -> node landed in HellGraph + receipt landed
    assert body["graph"]["nodes"], "resolved node must land in HellGraph"
    assert body["receipt"]["id"].startswith("sha256:")
    assert any(c["url"].endswith("/api/graph/node") for c in recorder)


def test_receipt_chain_links_prev():
    recorder: list[dict] = []
    sink = _mock_sink(recorder)
    from entity_resolution.resolver import Record
    res = resolve([Record("a", "Acme Corp", {"city": "NYC"}), Record("b", "Acme Corp", {"city": "NYC"})])
    r1 = sink.build_receipt(inputs={"n": 1}, outputs={"n": 1})
    r2 = sink.build_receipt(inputs={"n": 2}, outputs={"n": 2})
    assert r1["prev"] is None
    assert r2["prev"] == r1["id"], "receipts must hash-chain via prev"


def test_seal_degrades_without_token():
    recorder: list[dict] = []
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append({"url": str(request.url)})
        return httpx.Response(200, json={"ok": True})
    sink = GraphSink(client=httpx.Client(transport=httpx.MockTransport(handler)),
                     compute_gateway_token="")  # no token → fail-closed gateway
    receipt = sink.build_receipt(inputs={"n": 1}, outputs={"n": 1})
    seal = sink.emit_receipt(receipt)
    assert seal["sealed"] is False and "token" in seal["reason"]
