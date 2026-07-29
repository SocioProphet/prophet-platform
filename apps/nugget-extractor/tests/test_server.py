"""The HTTP shell: the door is authenticated and fail-closed, the errors are honest, and
/healthz reports the truth (validation_failures is a must-be-0 gauge)."""
from __future__ import annotations

import base64
import importlib
import os

import pytest
from fastapi.testclient import TestClient

os.environ["NUGGET_LOOP"] = "off"            # no background thread under test
os.environ["NUGGET_INGEST_TOKEN"] = "t"

from nugget_extractor import server as srv  # noqa: E402
from nugget_extractor.clients import EmitError, GatewayError  # noqa: E402
from nugget_extractor.emitter import NuggetEmitter  # noqa: E402

importlib.reload(srv)
AUTH = {"Authorization": "Bearer t"}
TEXT = b"Network sales grew 22.6% to AUD 1,138.9 million.\n\nStore rollout continued."


class FakeGraph:
    def __init__(self, fail=False):
        self.fail, self.nodes, self.edges = fail, [], []

    def post_node(self, node_id, labels, properties):
        if self.fail:
            raise EmitError("down")
        self.nodes.append(node_id)

    def post_edge(self, label, from_id, to_id):
        if self.fail:
            raise EmitError("down")
        self.edges.append((label, from_id, to_id))


class FakeGateway:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def mint(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise GatewayError("down")
        return {"receipt_id": "rcpt-0001"}


@pytest.fixture
def client(monkeypatch):
    graph, gw = FakeGraph(), FakeGateway()
    srv._EMITTER = NuggetEmitter(writer=graph, gateway=gw,
                                 clock=lambda: "2026-07-29T00:00:00.000Z")
    for key in ("documents", "extracted", "emitted", "validation_failures", "pending",
                "receipts", "ocr_required", "unsupported_media", "extract_errors"):
        srv.STATE[key] = 0
    srv.STATE["warrant_counts"] = {}
    srv.STATE["hellgraph_ok"] = srv.STATE["gateway_ok"] = None   # "nothing tried yet"
    with TestClient(srv.app) as c:
        yield c, graph, gw


def post(client, body, auth=AUTH):
    return client.post("/v1/extract", json=body, headers=auth)


def doc(raw=TEXT, **kw):
    return {"document_b64": base64.b64encode(raw).decode(), "filename": "a.txt", **kw}


def test_healthz_reports_the_contract_pin_and_the_honest_counters(client):
    c, _g, _gw = client
    body = c.get("/healthz").json()
    assert body["ok"] and body["service"] == "nugget-extractor"
    assert body["spec_version"] == "0.1.0" and len(body["schema_sha256"]) == 64
    for counter in ("extracted", "emitted", "validation_failures", "pending"):
        assert counter in body
    assert body["validation_failures"] == 0        # the must-be-0 gauge
    assert body["gateway_ok"] is None              # honest: nothing tried yet
    assert body["ocr_backend"] == "none"           # honest: no OCR is shipped


def test_an_idle_drain_never_reports_an_unchecked_dependency_as_green(client):
    """A drain with nothing pending contacts NOTHING. If its default-true flags were
    folded into /healthz, the probe would claim hellgraph and the gateway are healthy
    without ever having asked — a green light nobody earned."""
    c, graph, gw = client
    graph.fail = True                       # both dependencies would fail if contacted
    gw.fail = True
    for _ in range(3):
        srv._drain_step()
    body = c.get("/healthz").json()
    assert body["hellgraph_ok"] is None and body["gateway_ok"] is None


def test_extract_emits_and_seals(client):
    c, graph, gw = client
    r = post(c, doc())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["emitted"] == body["extracted"] > 0
    assert body["validation_failures"] == 0 and body["pending"] == 0
    assert body["receipt_id"] == "rcpt-0001" and len(gw.calls) == 1
    assert body["content_hash"].startswith("sha256-")
    assert body["doc_ref"].startswith("urn:srcos:document:")
    assert body["warrant_counts"] == {"direct-quote": 2, "computed": 2}

    health = c.get("/healthz").json()
    assert health["documents"] == 1 and health["emitted"] == body["emitted"]
    assert health["validation_failures"] == 0 and health["gateway_ok"] is True


def test_dry_run_returns_validated_nuggets_and_writes_nothing(client):
    c, graph, gw = client
    r = post(c, doc(dry_run=True))
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] and body["extracted"] == len(body["nuggets"]) > 0
    assert body["validation_failures"] == 0
    assert graph.nodes == [] and graph.edges == [] and gw.calls == []
    assert {n["type"] for n in body["nuggets"]} == {"KnowledgeNugget"}
    assert {n["specVersion"] for n in body["nuggets"]} == {"0.1.0"}


def test_caller_supplied_doc_ref_and_labels_are_carried(client):
    c, _g, _gw = client
    body = post(c, doc(doc_ref="urn:srcos:dataset:gyg_fy2025",
                       policy_labels=["source:public-filing"],
                       kko_type_refs=["https://schemas.srcos.ai/ont/ifm/Filing"],
                       dry_run=True)).json()
    assert body["doc_ref"] == "urn:srcos:dataset:gyg_fy2025"
    assert all(n["policyLabels"] == ["source:public-filing"] for n in body["nuggets"])
    assert all("https://schemas.srcos.ai/ont/ifm/Filing" in n["kkoTypeRefs"]
               for n in body["nuggets"])


def test_the_door_is_closed_without_a_token(client):
    c, _g, _gw = client
    assert post(c, doc(), auth={}).status_code == 401
    assert post(c, doc(), auth={"Authorization": "Bearer wrong"}).status_code == 401


def test_the_door_fails_closed_when_no_token_is_configured(monkeypatch, client):
    c, _g, _gw = client
    monkeypatch.setattr(srv, "INGEST_TOKEN", "")
    r = post(c, doc())
    assert r.status_code == 503 and "fail-closed" in r.json()["detail"]


def test_scanned_pdf_is_a_422_that_names_the_gap(client, scanned_pdf_bytes):
    c, _g, _gw = client
    r = post(c, doc(scanned_pdf_bytes, filename="scan.pdf"))
    assert r.status_code == 422 and "OCR" in r.json()["detail"]
    assert c.get("/healthz").json()["ocr_required"] == 1


def test_image_is_a_422_not_a_silent_empty_extraction(client):
    c, _g, _gw = client
    r = post(c, doc(b"\x89PNG\r\n\x1a\n", filename="scan.png", media_type="image/png"))
    assert r.status_code == 422
    assert c.get("/healthz").json()["unsupported_media"] == 1


def test_bad_base64_and_oversize_documents_are_refused(client, monkeypatch):
    c, _g, _gw = client
    assert c.post("/v1/extract", json={"document_b64": "not base64!!"},
                  headers=AUTH).status_code == 422
    monkeypatch.setattr(srv, "MAX_BYTES", 8)
    assert post(c, doc()).status_code == 413


def test_pdf_round_trip_through_the_http_door(client, pdf_bytes):
    c, _g, _gw = client
    body = post(c, doc(pdf_bytes, filename="report.pdf")).json()
    assert body["pages"] == 2 and body["emitted"] > 0
    assert body["raw_sha256"] and body["validation_failures"] == 0


def test_unattested_nuggets_are_a_503_not_a_200(client):
    """Valid nuggets exist but the receipt was refused: the response must be retryable,
    never a 200 that would read as 'landed'."""
    c, _g, gw = client
    gw.fail = True
    r = post(c, doc())
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["emitted"] == 0 and detail["pending"] > 0 and detail["gateway_ok"] is False
    assert c.get("/healthz").json()["emitted"] == 0

    gw.fail = False
    srv._drain_step()
    health = c.get("/healthz").json()
    assert health["emitted"] > 0 and health["pending"] == 0 and health["gateway_ok"] is True


def test_hellgraph_outage_is_a_503_and_nothing_is_counted_emitted(client):
    c, graph, gw = client
    graph.fail = True
    r = post(c, doc())
    assert r.status_code == 503
    assert r.json()["detail"]["hellgraph_ok"] is False
    assert gw.calls == []
    assert c.get("/healthz").json()["emitted"] == 0
