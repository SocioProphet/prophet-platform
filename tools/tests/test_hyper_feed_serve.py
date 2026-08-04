"""Theorems of the mesh SERVE half (tools.hyper_feed.serve) and the FULL 2-node federation: a node
publishes a manifest + serves content-addressed fetch, and a peer discovers-by-Hamming → fetches →
admits (digest + attestation), fail-closed. This is the node-symmetric mesh, end to end."""
from __future__ import annotations

from tools.hyper_feed import fetch as ff
from tools.hyper_feed.attestation import encode_attestation
from tools.hyper_feed.manifest import content_digest
from tools.hyper_feed.serve import MeshNode


def test_publish_manifest_advertises_every_holding():
    node = MeshNode("cloud-A", "t1")
    node.hold("r1", "ff00", b"alpha", op_set="discourse", attestation_ref="att:x")
    node.hold("r2", "00ff", b"beta", op_set="finance")
    m = node.publish_manifest(now="T")
    assert m["node_id"] == "cloud-A" and len(m["entries"]) == 2
    e1 = next(e for e in m["entries"] if e["ref_id"] == "r1")
    assert e1["code"] == "ff00" and e1["op_set"] == "discourse"
    assert e1["digest"] == content_digest(b"alpha") and e1["attestation_ref"] == "att:x"


def test_serve_fetch_is_content_addressed_and_fail_closed():
    node = MeshNode("cloud-A", "t1").hold("r1", "ff00", b"alpha")
    assert node.serve_fetch("r1") == b"alpha"
    assert content_digest(node.serve_fetch("r1")) == content_digest(b"alpha")
    try:
        node.serve_fetch("missing")
        assert False, "unknown ref must raise, never return empty"
    except KeyError:
        pass


# ── The full 2-node mesh: cloud A holds objects; edge B federates against A's manifest ──
def _cloud_A():
    att = encode_attestation("ctx:near", "proofhex", "vkhex")
    return (MeshNode("cloud-A", "t1")
            .hold("r_near", "ff01", b"near-content", op_set="discourse", attestation_ref=att)
            .hold("r_far", "0000", b"far-content", op_set="discourse", attestation_ref=att))


def test_two_node_federation_admits_only_the_near_verified_object():
    # THEOREM: edge B queries A by code, pulls only the Hamming-near ref, and admits it iff the twin
    # attests it — raw content moves only after a verified match. No node trusts the other.
    A = _cloud_A()
    res = ff.federate("ff00", A.publish_manifest(now="T"), fetcher=A.serve_fetch, max_hamming=4,
                      op_set="discourse", attestation_verifier=lambda a: True)
    assert [(r.ref_id, r.admitted) for r in res] == [("r_near", True)]   # r_far (Hamming 8) excluded
    assert res[0].content == b"near-content"


def test_federation_rejects_a_tampering_server():
    # THEOREM: if A serves bytes that don't match the manifest digest, B rejects (content-addressed).
    A = _cloud_A()
    res = ff.federate("ff00", A.publish_manifest(now="T"), fetcher=lambda rid: b"SWAPPED",
                      max_hamming=4, attestation_verifier=lambda a: True)
    assert res[0].reason == "digest-mismatch" and not res[0].admitted


def test_federation_is_fail_closed_on_provenance():
    # THEOREM: an attested object is rejected when the twin does NOT attest it, and (the #1404 hardening)
    # when no verifier is supplied at all — never admitted on the peer's digest alone.
    A = _cloud_A()
    no_attest = ff.federate("ff00", A.publish_manifest(now="T"), fetcher=A.serve_fetch,
                            max_hamming=4, attestation_verifier=lambda a: False)
    assert no_attest[0].reason == "attestation-invalid" and not no_attest[0].admitted
    no_verifier = ff.federate("ff00", A.publish_manifest(now="T"), fetcher=A.serve_fetch, max_hamming=4)
    assert no_verifier[0].reason == "attestation-unverifiable" and not no_verifier[0].admitted
