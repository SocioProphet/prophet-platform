"""Identity thread — DID → cap_token → signed receipt, and tamper-evidence."""

from __future__ import annotations

import pytest

from tools import membrane_identity as mid
from tools.capability_membrane import CapabilityRequest, TENSION_REQUIRED, resolve_capability

pytestmark = pytest.mark.skipif(not mid.HAVE_CRYPTO, reason="cryptography not installed")

SEED = bytes(range(32))
FULL_TENSION = TENSION_REQUIRED["R5"]


def owned_req(**over):
    base = dict(surface="filesystem", action="filesystem.read", access_level="readOnly",
                subject_ref="urn:srcos:agent:test", tension_members=FULL_TENSION)
    base.update(over)
    return CapabilityRequest(**base)


def test_did_key_roundtrip():
    ident = mid.IdentityRoot.from_seed(SEED)
    assert ident.did.startswith("did:key:z")
    assert mid.pubkey_from_did_key(ident.did) == ident.public_key_bytes


def test_from_seed_is_deterministic():
    assert mid.IdentityRoot.from_seed(SEED).did == mid.IdentityRoot.from_seed(SEED).did


def test_sign_and_verify_sealed():
    ident = mid.IdentityRoot.from_seed(SEED, svid_ref="urn:srcos:svid:twin-node-1")
    r = resolve_capability(owned_req(), signer=ident)
    assert r.sealed["signature"].startswith("ed25519:")
    assert r.sealed["signerDid"] == ident.did
    assert r.sealed["svidRef"] == "urn:srcos:svid:twin-node-1"
    assert mid.verify_sealed(r.sealed) is True


def test_tampered_receipt_fails_verification():
    ident = mid.IdentityRoot.from_seed(SEED)
    r = resolve_capability(owned_req(), signer=ident)
    tampered = dict(r.sealed)
    tampered["sealHash"] = "sha256:" + "0" * 64        # forge the seal
    assert mid.verify_sealed(tampered) is False


def test_wrong_identity_fails_verification():
    a = mid.IdentityRoot.from_seed(SEED)
    r = resolve_capability(owned_req(), signer=a)
    forged = dict(r.sealed, signerDid=mid.IdentityRoot.from_seed(bytes(range(1, 33))).did)
    assert mid.verify_sealed(forged) is False


def test_unsigned_receipt_still_valid_and_verify_false():
    # No signer → kernel stays pure; receipt is valid but carries no signature.
    r = resolve_capability(owned_req())
    assert "signature" not in r.sealed
    assert mid.verify_sealed(r.sealed) is False


def test_mint_cap_token_is_scoped_signed_and_short_lived():
    import time
    ident = mid.IdentityRoot.from_seed(SEED)
    tok = ident.mint_cap_token(subject_id="urn:srcos:agent:worker", operations=["read", "write"], ttl_seconds=300)
    assert tok["iss"] == ident.did
    assert tok["scope"]["operations"] == ["read", "write"]
    assert tok["signature"].startswith("ed25519:")
    assert 0 < tok["exp"] - int(time.time()) <= 300


def test_identity_chain_contract_shape():
    ident = mid.IdentityRoot.from_seed(SEED, svid_ref="urn:srcos:svid:twin-node-1")
    chain = mid.IdentityChain(did=ident.did, svid_ref=ident.svid_ref,
                              approved_hashes_ref="urn:srcos:approved-hashes:merkle-root")
    d = chain.to_dict()
    assert d["did"] == ident.did
    assert d["roles"] == {"issuer": True, "receiptSigner": True}
    assert d["approvedHashesRef"] == "urn:srcos:approved-hashes:merkle-root"
