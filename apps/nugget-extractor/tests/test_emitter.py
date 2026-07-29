"""Emitter semantics on fakes: the fail-closed gate, resumable retry with no duplicate
edges, and "no receipt ⇒ nothing counted as emitted"."""
from __future__ import annotations

import pytest

from nugget_extractor import contract, emitter as em, extract as ex
from nugget_extractor.clients import EmitError, GatewayError

TEXT = b"Network sales grew 22.6% to AUD 1,138.9 million.\n\nStore rollout continued."
DOC = "urn:srcos:document:test"
RUN = "urn:srcos:run:test"


class FakeGraph:
    def __init__(self, fail_after: int | None = None) -> None:
        self.nodes: list[tuple] = []
        self.edges: list[tuple] = []
        self.fail_after = fail_after
        self.calls = 0

    def _tick(self) -> None:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise EmitError("hellgraph down")

    def post_node(self, node_id, labels, properties):
        self._tick()
        self.nodes.append((node_id, tuple(labels), properties))

    def post_edge(self, label, from_id, to_id):
        self._tick()
        self.edges.append((label, from_id, to_id))


class FakeGateway:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def mint(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise GatewayError("gateway down")
        return {"receipt_id": f"rcpt-{len(self.calls):04d}"}


def build(fail_after=None, gateway_fail=False):
    graph, gw = FakeGraph(fail_after), FakeGateway(gateway_fail)
    return em.NuggetEmitter(writer=graph, gateway=gw,
                            clock=lambda: "2026-07-29T00:00:00.000Z"), graph, gw


def extraction():
    return ex.extract(TEXT, filename="a.txt")


def test_happy_path_writes_nodes_then_edges_and_seals_one_receipt():
    e, graph, gw = build()
    r = e.submit(extraction(), doc_ref=DOC, run_ref=RUN)

    assert r.extracted == r.emitted > 0 and r.validation_failures == 0
    assert r.pending == 0 and r.hellgraph_ok and r.gateway_ok
    assert len(gw.calls) == 1 and r.last_receipt_id == "rcpt-0001"

    node_ids = [n[0] for n in graph.nodes]
    assert DOC in node_ids                                     # the document node
    assert contract.KKO_WRITTEN_INFO in node_ids               # KKO type nodes
    assert contract.KKO_QUANTITY in node_ids
    labels = {n[0]: n[1] for n in graph.nodes}
    nugget_nodes = [i for i in node_ids if i.startswith(contract.URN_PREFIX)]
    assert nugget_nodes
    for nid in nugget_nodes:
        assert labels[nid][0] == em.NUGGET_LABEL
        assert labels[nid][1].startswith("warrant:")           # warrant is a LABEL


def test_every_nugget_has_a_document_edge_and_a_kko_type_edge():
    e, graph, _ = build()
    e.submit(extraction(), doc_ref=DOC, run_ref=RUN)
    nuggets = [n[0] for n in graph.nodes if n[0].startswith(contract.URN_PREFIX)]
    doc_edges = {f for lbl, f, t in graph.edges if lbl == em.EDGE_FROM_DOCUMENT and t == DOC}
    assert doc_edges == set(nuggets)
    typed = {f for lbl, f, _t in graph.edges if lbl == em.EDGE_KKO_TYPE}
    assert typed == set(nuggets)


def test_warranted_by_edges_make_the_derivation_chain_walkable():
    e, graph, _ = build()
    e.submit(extraction(), doc_ref=DOC, run_ref=RUN)
    warrant_edges = [(f, t) for lbl, f, t in graph.edges if lbl == em.EDGE_WARRANTED_BY]
    assert warrant_edges, "a computed nugget must point at the quote it came from"
    props = {n[0]: n[2] for n in graph.nodes}
    for child, parent in warrant_edges:
        assert props[child]["warrantType"] == "computed"
        assert props[parent]["warrantType"] == "direct-quote"


def test_a_nugget_that_fails_validation_is_counted_and_never_emitted(monkeypatch):
    """The fail-closed gate. One poisoned nugget is dropped; the rest of the document
    still lands, and the drop is counted AND bound into the receipt."""
    e, graph, gw = build()
    real = contract.validate_nugget
    seen: list[str] = []

    def poisoned(nugget, source_text=None):
        seen.append(nugget["id"])
        if len(seen) == 2:
            raise contract.NuggetError("synthetic non-conformance")
        return real(nugget, source_text=source_text)

    monkeypatch.setattr(em.contract, "validate_nugget", poisoned)
    r = e.submit(extraction(), doc_ref=DOC, run_ref=RUN)

    assert r.validation_failures == 1
    assert r.emitted == r.extracted - 1
    rejected = seen[1]
    written = {n[0] for n in graph.nodes}
    assert rejected not in written                           # NEVER emitted
    assert not any(rejected in (f, t) for _l, f, t in graph.edges)
    assert gw.calls[0]["validation_failures"] == 1           # and the receipt says so
    assert gw.calls[0]["nugget_count"] == r.emitted


def test_hellgraph_outage_leaves_the_batch_pending_and_mints_no_receipt():
    e, graph, gw = build(fail_after=3)
    r = e.submit(extraction(), doc_ref=DOC, run_ref=RUN)
    assert r.emitted == 0 and r.pending > 0
    assert r.hellgraph_ok is False
    assert gw.calls == []                                    # never seal an unlanded batch


def test_retry_resumes_at_the_failed_write_and_never_duplicates_an_edge():
    """addNode is an upsert; addEdge is not — a replayed edge would mint a second log
    event and a duplicate downstream row. The write cursor is what prevents that."""
    e, graph, gw = build(fail_after=4)
    e.submit(extraction(), doc_ref=DOC, run_ref=RUN)
    landed_nodes, landed_edges = list(graph.nodes), list(graph.edges)
    assert graph.calls == 5                                  # 4 landed, the 5th raised

    graph.fail_after = None                                  # hellgraph comes back
    r = e.drain()

    assert r.emitted > 0 and r.pending == 0 and r.hellgraph_ok
    assert graph.nodes[:len(landed_nodes)] == landed_nodes   # nothing re-sent
    assert graph.edges[:len(landed_edges)] == landed_edges
    assert len(graph.edges) == len(set(graph.edges)), "duplicate edge write"
    assert len(gw.calls) == 1


def test_gateway_outage_holds_the_batch_at_the_receipt_step_then_seals_once():
    """Graph writes cannot be un-written, so the batch waits AT THE RECEIPT and retries
    only the receipt — the graph is never rewritten, and nothing counts as emitted until
    it is attested (the materializer's 'no receipt ⇒ no checkpoint' rule)."""
    e, graph, gw = build(gateway_fail=True)
    r = e.submit(extraction(), doc_ref=DOC, run_ref=RUN)
    assert r.emitted == 0 and r.gateway_ok is False and r.pending > 0
    writes = (len(graph.nodes), len(graph.edges))

    gw.fail = False
    r2 = e.drain()
    assert r2.emitted > 0 and r2.pending == 0 and r2.gateway_ok
    assert (len(graph.nodes), len(graph.edges)) == writes    # no rewrite on retry
    assert len(gw.calls) == 2                                # one failed, one sealed


def test_receipt_binds_the_batch_coordinates():
    e, _graph, gw = build()
    extr = extraction()
    e.submit(extr, doc_ref=DOC, run_ref=RUN)
    call = gw.calls[0]
    assert call["doc_ref"] == DOC
    assert call["content_hash"] == contract.content_hash(extr.source_text)
    assert call["raw_sha256"] == extr.raw_sha256
    assert call["media_type"] == "text/plain"
    assert call["warrant_counts"] == {"direct-quote": 2, "computed": 2}
    assert len(call["batch_hash"]) == 64


def test_resubmitting_the_same_document_mints_the_same_identities():
    e1, g1, _ = build()
    e2, g2, _ = build()
    e1.submit(extraction(), doc_ref=DOC, run_ref=RUN)
    e2.submit(extraction(), doc_ref=DOC, run_ref="urn:srcos:run:different")
    ids1 = [n[0] for n in g1.nodes if n[0].startswith(contract.URN_PREFIX)]
    ids2 = [n[0] for n in g2.nodes if n[0].startswith(contract.URN_PREFIX)]
    assert ids1 == ids2 and ids1


def test_concurrent_submit_and_drain_never_replay_a_write_or_double_seal():
    """The regression this lock exists for. The drain loop runs on a daemon thread while
    requests arrive on another; unserialized, both drain the SAME batch — replaying edges
    (each a new log event and a duplicate downstream row), minting two receipts for one
    document, and popping an already-empty queue. Reproduced on the first end-to-end run.

    The fake writer sleeps mid-write to widen the window, so an unlocked emitter fails
    this reliably rather than one run in twenty."""
    import threading
    import time

    class SlowGraph(FakeGraph):
        def post_node(self, *a):
            time.sleep(0.002)
            super().post_node(*a)

        def post_edge(self, *a):
            time.sleep(0.002)
            super().post_edge(*a)

    graph, gw = SlowGraph(), FakeGateway()
    e = em.NuggetEmitter(writer=graph, gateway=gw,
                         clock=lambda: "2026-07-29T00:00:00.000Z")
    errors: list[BaseException] = []

    def drainer():
        try:
            for _ in range(40):
                e.drain()
                time.sleep(0.001)
        except BaseException as exc:  # noqa: BLE001 — the failure mode IS an exception
            errors.append(exc)

    t = threading.Thread(target=drainer, daemon=True)
    t.start()
    for i in range(4):
        e.submit(ex.extract(TEXT + f"\n\nDoc {i} tail paragraph.".encode(),
                            filename=f"{i}.txt"),
                 doc_ref=f"urn:srcos:document:d{i}", run_ref=RUN)
    t.join(timeout=10)

    assert errors == []
    assert len(graph.edges) == len(set(graph.edges)), "an edge was written twice"
    assert len(gw.calls) == 4, f"one receipt per document, got {len(gw.calls)}"
    assert e.pending_nuggets == 0


def test_startup_check_is_the_boot_gate():
    e, _g, _gw = build()
    e.startup_check()          # must not raise


def test_pdf_document_emits_page_attributed_nuggets(pdf_bytes):
    e, graph, _gw = build()
    r = e.submit(ex.extract(pdf_bytes, filename="report.pdf"), doc_ref=DOC, run_ref=RUN)
    assert r.emitted > 0 and r.validation_failures == 0
    pages = {n[2]["page"] for n in graph.nodes if n[0].startswith(contract.URN_PREFIX)}
    assert pages == {1, 2}


def test_scanned_pdf_never_reaches_the_emitter(scanned_pdf_bytes):
    with pytest.raises(ex.OcrRequired):
        ex.extract(scanned_pdf_bytes, filename="scan.pdf")
