"""Seal-the-Walls W1.3 — receipt unification: engine sealed() receipts chained on THE
spine, ONE verify walk end-to-end, tampering attributed to the step that owns it.

Golden fixtures are REAL engine output: captured from the vendored
@socioprophet/hellgraph 0.4.40 dist (node), hashes minted by V8's JSON.stringify —
so the Python recomputation is anchored against actual engine bytes, not against
itself. The number battery likewise carries V8 ground truth (`JSON.stringify(v)`
outputs generated in node), covering every formatting divergence between Python
repr and ECMAScript Number::toString (integral floats, 1e-5/1e-6 plain forms,
e-7/e+21 exponent forms, unpadded exponents, subnormals).
"""
import base64
import importlib
import json
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo,engine-seal"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"
# deterministic Ed25519 key: the signature step must be REAL in these tests
os.environ["GATEWAY_SIGNING_KEY"] = base64.b64encode(bytes(range(32))).decode()

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import artifacts, engine, engine_receipts, receipts, server  # noqa: E402

importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}

# ── golden fixtures: REAL sealed receipts from the vendored engine (0.4.40) ──
ENRICH_JSON = (
    '{"label":"FxClass","method":"rrf(consistency,trust,probabilistic)","peers":7,'
    '"snapshot":{"seq":58,"nodes":10,"edges":8},"recommendations":[{"key":"extraA","kind":"property",'
    '"fusedScore":0.04918032786885246,"rank":1,"peerCoverage":1,"ownCoverage":0,'
    '"signals":{"consistency":1,"trust":1,"probabilistic":0.875}},'
    '{"key":"fx_rel","kind":"relation-out","fusedScore":0.04838709677419355,"rank":2,'
    '"peerCoverage":0.8571428571428571,"ownCoverage":0,"signals":{"consistency":0.8571428571428571,'
    '"trust":0.8571428571428572,"probabilistic":0.7346938775510203}},'
    '{"key":"extraB","kind":"property","fusedScore":0.047619047619047616,"rank":3,'
    '"peerCoverage":0.42857142857142855,"ownCoverage":0,"signals":{"consistency":0.42857142857142855,'
    '"trust":0.42857142857142866,"probabilistic":0.3214285714285714}}],'
    '"hash":"sha256:018f2febf0c76f91752ba9726c9a32a4a8d3ca03895a5d877b780c312d34cc71"}'
)
EXPLORE_JSON = (
    '{"seeds":["fx:c0"],"method":"rrf(personalized-pagerank,seed-adjacency)",'
    '"snapshot":{"seq":58,"nodes":10,"edges":8},"suggestions":[{"id":"fx:c1","labels":["FxClass"],'
    '"score":0.03278688524590164,"rank":1},{"id":"fx:c2","labels":["FxClass"],'
    '"score":0.03225806451612903,"rank":2}],'
    '"hash":"sha256:35a9df2dd74a25fcbb966a41d2949cd7646912d743aeec730a36fa1a1d3a00af"}'
)

# (value-as-parsed-from-JS, V8 JSON.stringify output) — generated in node
V8_NUMBERS = [
    (0, "0"), (1, "1"), (-1, "-1"), (0.5, "0.5"), (1.5, "1.5"), (2, "2"),
    (1e-5, "0.00001"), (1e-6, "0.000001"), (1e-7, "1e-7"), (1.5e-7, "1.5e-7"),
    (0.0001, "0.0001"), (1e21, "1e+21"), (1e20, "100000000000000000000"),
    (1.2345678901234567e20, "123456789012345670000"),
    (0.30000000000000004, "0.30000000000000004"), (0.3333333333333333, "0.3333333333333333"),
    (0.03278688524590164, "0.03278688524590164"), (0.8571428571428572, "0.8571428571428572"),
    (1e-323, "1e-323"), (5e-324, "5e-324"),
    (1.7976931348623157e308, "1.7976931348623157e+308"),
    (123456789.12345679, "123456789.12345679"), (-2.5e-9, "-2.5e-9"),
    (3.0, "3"), (100.0, "100"), (2e64, "2e+64"), (6.02e23, "6.02e+23"),
    (-0.000015, "-0.000015"), (7.006492321624085e-46, "7.006492321624085e-46"),
]


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo,engine-seal"   # pin: sibling modules mutate the shared env
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    artifacts._reset()


def _enrich_receipt():
    return json.loads(ENRICH_JSON)


def _explore_receipt():
    return json.loads(EXPLORE_JSON)


def _seal(kind, er, subject=None, project="demo"):
    return client.post("/v1/engine-receipts", headers=AUTH, json={
        "kind": kind, "engineReceipt": er,
        "subject": subject or {"service": "hellgraph-service", "endpoint": f"/api/graph/{kind}"},
        "project": project})


def _verify(receipt_id, project="demo"):
    return client.get(f"/v1/engine-receipts/{receipt_id}/verify",
                      params={"project": project}, headers=AUTH).json()


def _statuses(walk):
    return [(s["step"], s["status"]) for s in walk["steps"]]


# ── the byte-exact recomputation, anchored on REAL V8 output ──
def test_js_stringify_matches_v8_number_formatting():
    for v, expected in V8_NUMBERS:
        assert engine_receipts.js_stringify(v) == expected, f"{v!r} → {expected}"
    # strings, escapes, nesting, key order (V8 ground truth from node)
    assert engine_receipts.js_stringify("quote\"q") == '"quote\\"q"'
    assert engine_receipts.js_stringify("ctrl\x01\x1f") == '"ctrl\\u0001\\u001f"'
    assert engine_receipts.js_stringify("unicodé ☃") == '"unicodé ☃"'
    assert engine_receipts.js_stringify({"b": 1, "a": [True, False, None, {"z": 0.875, "y": "x"}]}) \
        == '{"b":1,"a":[true,false,null,{"z":0.875,"y":"x"}]}'


def test_sealed_hash_recomputes_real_engine_receipts():
    er, xr = _enrich_receipt(), _explore_receipt()
    assert engine_receipts.sealed_hash("enrich", er) == er["hash"]
    assert engine_receipts.sealed_hash("explore", xr) == xr["hash"]
    # and the recomputation is over CANONICAL order, not wire order: scrambling
    # the received key order (what the durable blob store's sort_keys does) must
    # not change the recomputed seal.
    scrambled = {k: er[k] for k in sorted(er)}
    scrambled["snapshot"] = {k: er["snapshot"][k] for k in sorted(er["snapshot"])}
    assert engine_receipts.sealed_hash("enrich", scrambled) == er["hash"]


# ── sealing onto the spine ──
def test_engine_seal_chains_a_signed_envelope_and_one_verify_walks_it():
    r = _seal("enrich", _enrich_receipt())
    assert r.status_code == 200
    body = r.json()
    rc = body["envelope"]["receipt"]
    assert body["receiptId"] == rc["id"]
    assert rc["kind"] == "engine-seal" and rc["backend"] == "gateway"
    assert rc["epistemic_status"] == "verified"       # the seal was RECOMPUTED, not trusted
    assert rc["signature"] and rc["public_key"] and rc["statement"]
    assert body["envelope"]["attestation"]["results"]["cosign_valid"] is True
    # on THE one chain
    chain = receipts.chain("demo")
    assert [c.id for c in chain] == [body["receiptId"]]
    assert receipts.verify("demo")["valid"] is True
    # ONE verify() walks it end-to-end, every step typed and ok, in walk order
    walk = _verify(body["receiptId"])
    assert walk["valid"] is True
    assert _statuses(walk) == [("gateway-signature", "ok"), ("engine-seal-hash", "ok"),
                               ("snapshot-seq-binding", "ok")]


def test_engine_seal_explore_receipt_verifies_too():
    r = _seal("explore", _explore_receipt())
    assert r.status_code == 200
    walk = _verify(r.json()["receiptId"])
    assert walk["valid"] is True and len(walk["steps"]) == 3


def test_engine_seal_retry_returns_the_same_receipt():
    # hellgraph-service retrying the identical POST (timeout, restart) must not
    # grow the chain — the memo returns the SAME receipt (materialize precedent).
    first = _seal("enrich", _enrich_receipt()).json()
    again = _seal("enrich", _enrich_receipt()).json()
    assert again["receiptId"] == first["receiptId"] and again["memoized"] is True
    assert len(receipts.chain("demo")) == 1


def test_engine_seal_shape_validation_fails_loud():
    er = _enrich_receipt()
    del er["snapshot"]
    r = _seal("enrich", er)
    assert r.status_code == 422 and "snapshot" in r.json()["detail"]
    # unknown keys are refused, never silently mis-hashed
    er2 = _enrich_receipt()
    er2["surprise"] = 1
    r2 = _seal("enrich", er2)
    assert r2.status_code == 422 and "surprise" in r2.json()["detail"]
    # wrong kind literal is a 422 at the contract edge
    assert client.post("/v1/engine-receipts", headers=AUTH, json={
        "kind": "bogus", "engineReceipt": _enrich_receipt()}).status_code == 422


def test_engine_seal_refuses_a_hash_that_does_not_recompute():
    er = _enrich_receipt()
    er["hash"] = "sha256:" + "0" * 64
    r = _seal("enrich", er)
    assert r.status_code == 422
    assert "does not recompute" in r.json()["detail"]
    # the refusal is an honest error receipt on the chain, typed unknown — the
    # spine records the refusal without claiming verification.
    chain = receipts.chain("demo")
    assert len(chain) == 1 and chain[0].status == "error"
    assert chain[0].epistemic_status == "unknown"


# ── the three tamper cases: each fails at the RIGHT step ──
def test_tamper_output_byte_fails_at_engine_seal_hash():
    rid = _seal("explore", _explore_receipt()).json()["receiptId"]
    # flip a byte in the STORED engine output (a suggestion id) — seal untouched
    blob = artifacts.get(artifacts.for_receipt(rid)[0])
    blob["data"]["engine_receipt"]["suggestions"][0]["id"] = "fx:cX"
    walk = _verify(rid)
    assert walk["valid"] is False
    assert _statuses(walk) == [("gateway-signature", "ok"), ("engine-seal-hash", "fail"),
                               ("snapshot-seq-binding", "skipped")]
    assert "does not recompute" in walk["steps"][1]["detail"]


def test_tamper_seq_and_reseal_fails_at_snapshot_seq_binding():
    rid = _seal("enrich", _enrich_receipt()).json()["receiptId"]
    # a SELF-CONSISTENT forgery: bump seq inside the engine receipt AND re-seal its
    # hash. Step 2 must pass (the forged receipt recomputes) — only the signed
    # seal-time binding can catch that the graph state moved.
    blob = artifacts.get(artifacts.for_receipt(rid)[0])
    er = blob["data"]["engine_receipt"]
    er["snapshot"]["seq"] += 1
    er["hash"] = engine_receipts.sealed_hash("enrich", er)
    walk = _verify(rid)
    assert walk["valid"] is False
    assert _statuses(walk) == [("gateway-signature", "ok"), ("engine-seal-hash", "ok"),
                               ("snapshot-seq-binding", "fail")]
    assert "snapshot.seq" in walk["steps"][2]["detail"]


def test_tamper_signature_fails_at_gateway_signature():
    rid = _seal("enrich", _enrich_receipt()).json()["receiptId"]
    r = receipts.chain("demo")[0]
    sig = bytearray(base64.b64decode(r.signature))
    sig[0] ^= 0xFF                                     # flip a byte in the Ed25519 signature
    r.signature = base64.b64encode(bytes(sig)).decode()
    walk = _verify(rid)
    assert walk["valid"] is False
    assert _statuses(walk) == [("gateway-signature", "fail"), ("engine-seal-hash", "skipped"),
                               ("snapshot-seq-binding", "skipped")]
    assert "signature" in walk["steps"][0]["detail"]


def test_tamper_whole_envelope_cannot_outrun_the_signed_outputs_sha():
    # the strongest forgery: rewrite the stored binding AND the engine receipt,
    # both self-consistent. The signed outputs_sha still pins the envelope.
    rid = _seal("explore", _explore_receipt()).json()["receiptId"]
    blob = artifacts.get(artifacts.for_receipt(rid)[0])
    er = blob["data"]["engine_receipt"]
    er["snapshot"]["seq"] += 7
    er["hash"] = engine_receipts.sealed_hash("explore", er)
    blob["data"]["snapshot"]["seq"] += 7               # binding rewritten to match
    walk = _verify(rid)
    assert walk["valid"] is False
    assert walk["steps"][2]["step"] == "snapshot-seq-binding"
    assert walk["steps"][2]["status"] == "fail"
    assert "outputs_sha" in walk["steps"][2]["detail"]


def test_reordered_chain_fails_at_gateway_signature():
    # "on the chain" is a claim about ORDER. Membership + own-hash said ok even when
    # the chain had been shuffled underneath the receipt — so a receipt could be
    # moved to a different position in history and still verify. It cannot now.
    first = _seal("enrich", _enrich_receipt()).json()["receiptId"]
    second = _seal("explore", _explore_receipt()).json()["receiptId"]
    chain = receipts._CHAINS["demo"]
    assert [c.id for c in chain] == [first, second]

    chain.reverse()                                    # same receipts, forged order
    walk = _verify(second)                             # now sitting at position 0
    assert walk["valid"] is False
    assert _statuses(walk) == [("gateway-signature", "fail"), ("engine-seal-hash", "skipped"),
                               ("snapshot-seq-binding", "skipped")]
    assert "prev-link" in walk["steps"][0]["detail"]


def test_broken_earlier_prev_link_fails_the_receipt_that_depends_on_it():
    # Tamper with a PREDECESSOR, not the target. The target's own body still
    # re-hashes perfectly — the old step 1 passed it and attested a receipt whose
    # history had been rewritten beneath it.
    first = _seal("enrich", _enrich_receipt()).json()["receiptId"]
    second = _seal("explore", _explore_receipt()).json()["receiptId"]
    chain = receipts._CHAINS["demo"]

    chain[0].actor = "someone-else"                    # predecessor body altered
    assert engine_receipts._receipt_body_hash_ok(chain[1]) is True   # target itself intact
    walk = _verify(second)
    assert walk["valid"] is False
    assert walk["steps"][0]["step"] == "gateway-signature"
    assert walk["steps"][0]["status"] == "fail"
    detail = walk["steps"][0]["detail"]
    assert "predecessor #0" in detail and first in detail
    assert "id-hash does not recompute" in detail

    # a receipt EARLIER than the tampering is unaffected — the walk verifies the
    # prefix each receipt actually depends on, not the whole chain indiscriminately.
    receipts._CHAINS["demo"] = [chain[0]]
    chain[0].actor = "hellgraph-service"               # restore: genesis is sound again
    assert _verify(first)["steps"][0]["status"] == "ok"


def test_verify_walk_missing_receipt_is_invalid_at_step_one():
    walk = _verify("sha256:" + "ee" * 32)
    assert walk["valid"] is False
    assert walk["steps"][0]["step"] == "gateway-signature"
    assert walk["steps"][0]["status"] == "fail"


def test_verify_walk_refuses_non_engine_seal_kinds():
    # seal a materialize receipt, then ask the engine walk to verify it — the walk
    # must refuse at step 1 rather than "verify" a receipt with no engine seal.
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo,engine-seal,materialize"
    m = client.post("/v1/compute", headers=AUTH, json={
        "kind": "materialize", "project": "demo",
        "spec": {"sink": "clickhouse", "table": "hellgraph.events", "to_cursor": 9,
                 "row_count": 1, "batch_hash": "sha256:" + "ab" * 32}}).json()
    walk = _verify(m["receipt"]["id"])
    assert walk["valid"] is False and "not engine-seal" in walk["steps"][0]["detail"]


def test_unsigned_seal_is_honestly_unverifiable():
    # without a signing key the envelope is sealed UNSIGNED (never faked) — and the
    # verify walk must then refuse step 1: no claimed authenticity without a signature.
    key = os.environ.pop("GATEWAY_SIGNING_KEY")
    try:
        rid = _seal("enrich", _enrich_receipt()).json()["receiptId"]
        walk = _verify(rid)
        assert walk["valid"] is False
        assert walk["steps"][0]["step"] == "gateway-signature"
        assert "unsigned" in walk["steps"][0]["detail"]
    finally:
        os.environ["GATEWAY_SIGNING_KEY"] = key
