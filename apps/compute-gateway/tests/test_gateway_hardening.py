"""Tier-1 security hardening — pins the two Copilot findings on merged main:

* #958 — `_parse` used to trust caller-supplied `sha256` verbatim, breaking
  content-addressing for every downstream consumer that reads the output.
* #1006 — `_exhaust` from an adapter was stored verbatim in the artifact
  store, turning `/v1/artifacts/{exhaust_sha}` into an exfil path for any
  token holder if an adapter packed raw content into the discard ledger.

Both fixes are guards at the trust boundary between adapter output and
receipt/artifact storage. These tests exercise the guards directly rather
than through HTTP, so they run fast and are readable.
"""
import asyncio
import base64
import hashlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from compute_gateway import adapters, engine


# ── #958: sha256 recompute + mismatch refusal ─────────────────────────────

def _text_pack(text: str) -> dict:
    raw = text.encode("utf-8")
    return {"document_b64": base64.b64encode(raw).decode(),
            "filename": "note.txt", "media_type": "text/plain"}


def test_parse_recomputes_sha256_ignoring_caller_supplied():
    """Caller-supplied sha256 that mismatches the parsed bytes must fail-closed."""
    pack = _text_pack("hello world")
    pack["sha256"] = "sha256:" + "0" * 64
    out = asyncio.run(adapters._parse(pack, project="p", session=None))
    assert out["status"] == "error"
    assert "does not match" in out["error"]


def test_parse_computes_sha256_when_caller_omits_it():
    """Caller omits sha256 entirely; parse computes it over the actual bytes."""
    pack = _text_pack("hello world")
    pack.pop("sha256", None)
    out = asyncio.run(adapters._parse(pack, project="p", session=None))
    assert out["status"] == "ok"
    assert out["outputs"][0].data["sha256"] == hashlib.sha256(b"hello world").hexdigest()


def test_parse_accepts_matching_caller_sha256():
    """Caller supplies the correct sha256; parse verifies and passes it through."""
    pack = _text_pack("hello world")
    pack["sha256"] = hashlib.sha256(b"hello world").hexdigest()
    out = asyncio.run(adapters._parse(pack, project="p", session=None))
    assert out["status"] == "ok"
    assert out["outputs"][0].data["sha256"] == pack["sha256"]


# ── #1006: exhaust shape guard ────────────────────────────────────────────

def test_exhaust_guard_passes_a_well_formed_exhaust_record():
    # Shape matches the canonical ExhaustRecord in
    # tests/test_exhaust_accounting.py:28.
    good = {
        "type": "ExhaustRecord", "specVersion": "2.0", "source": "compute",
        "counts": {"candidatesRejected": 2},
        "bytesIn": 100, "bytesOut": 10,
        "items": [{"kind": "candidate", "sha256": "a" * 64, "size": 90}],
    }
    out = engine._guard_exhaust(good)
    assert out == good


def test_exhaust_guard_strips_raw_payload_dumps():
    """The exact failure mode Copilot flagged: an adapter dumps arbitrary
    strings into _exhaust; without the guard, they'd be retrievable via
    /v1/artifacts/{exhaust_sha}."""
    smuggled = {
        "type": "ExhaustRecord", "counts": {"candidatesRejected": 1},
        "raw_content": "SSN 123-45-6789 and email alice@example.com",
    }
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert "raw_content" not in out
    assert out["reason"].startswith("exhaust rejected")
    assert out["stage"] == "engine._guard_exhaust"


def test_exhaust_guard_strips_free_text_smuggled_as_an_item_ref():
    """An item.sha256 that isn't actually a digest — string content sneaking
    past the top-level shape by riding in an allowlisted sub-field."""
    smuggled = {
        "type": "ExhaustRecord",
        "items": [{"kind": "candidate", "sha256": "totally not a digest — raw content"}],
    }
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert "items" not in out
    assert "exhaust rejected" in out["reason"]


def test_exhaust_guard_caps_free_text_reason_length():
    """A bounded string field like `reason` must not become an unbounded blob."""
    smuggled = {"type": "ExhaustRecord", "reason": "x" * 10_000}
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    # Rejected because the reason is > 512 chars.
    assert "exhaust rejected" in out["reason"]


def test_exhaust_guard_rejects_negative_counts():
    out = engine._guard_exhaust({"type": "ExhaustRecord", "counts": {"x": -3}})
    assert "exhaust rejected" in out["reason"]


def test_exhaust_guard_caps_items_length_to_prevent_dos():
    """A pathologically long items list is a DoS surface on the artifact store."""
    huge = {"type": "ExhaustRecord",
            "items": [{"sha256": "a" * 64} for _ in range(10_001)]}
    out = engine._guard_exhaust(huge)
    assert "exhaust rejected" in out["reason"]


def test_exhaust_guard_returns_none_for_none_and_non_dict():
    assert engine._guard_exhaust(None) is None
    assert engine._guard_exhaust("some string") is None
    assert engine._guard_exhaust(["a", "b"]) is None


# ── Copilot round-1 follow-up: bypass hardening ───────────────────────────

def test_parse_accepts_matching_caller_sha256_with_sha256_prefix():
    """Copilot round-1: strict-string compare rejected caller's 'sha256:<hex>'
    form even when correct. Normalise before comparing."""
    pack = _text_pack("hello world")
    pack["sha256"] = "sha256:" + hashlib.sha256(b"hello world").hexdigest()
    out = asyncio.run(adapters._parse(pack, project="p", session=None))
    assert out["status"] == "ok"


def test_parse_accepts_matching_caller_sha256_in_uppercase():
    """Same: hex is case-insensitive. UPPERCASE must not be treated as mismatch."""
    pack = _text_pack("hello world")
    pack["sha256"] = hashlib.sha256(b"hello world").hexdigest().upper()
    out = asyncio.run(adapters._parse(pack, project="p", session=None))
    assert out["status"] == "ok"


def test_exhaust_guard_rejects_a_huge_urn_as_a_ref():
    """Copilot round-1: an adapter could smuggle payload as a huge urn: string
    in items[].sha256. Ref length is now capped at 512."""
    huge_urn = "urn:x:" + "a" * 10_000
    smuggled = {
        "type": "ExhaustRecord",
        "items": [{"sha256": huge_urn}],
    }
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert "items" not in out
    assert "exhaust rejected" in out["reason"]


def test_exhaust_guard_still_accepts_reasonable_urn_refs():
    """The cap must not break legitimate URN refs."""
    good = {
        "type": "ExhaustRecord",
        "items": [{"kind": "candidate", "sha256": "urn:srcos:evidence:atom_x_2026"}],
    }
    out = engine._guard_exhaust(good)
    assert out == good


# ── Copilot round-2 follow-up: the two dimensions still unbounded ─────────
#
# These were verified as LIVE bypasses against the round-1 guard before the
# fix: each smuggled >10 MB of verbatim text through `_guard_exhaust` intact
# and into the artifact store, retrievable at /v1/artifacts/{exhaust_sha} —
# the exact exfil path this guard exists to close. Literal sizes below are
# written out rather than derived from engine._MAX_* on purpose: a test that
# reads the same constant as the implementation cannot detect the constant
# being widened.
#
# Each test also pins WHICH check rejected the record, via the reason string.
# That is not decoration. First draft of these tests asserted only "rejected",
# and stayed green with the per-field bound deleted — because the aggregate
# backstop caught the same payload. Two guards where the test cannot tell them
# apart is one guard that can be removed without any test going red.


def test_exhaust_guard_rejects_payload_smuggled_as_specversion():
    """`specVersion` was type-checked but not length-bounded — a string field
    on the top-level allowlist with no ceiling is an open exfil door."""
    payload = "SSN 123-45-6789 alice@example.com " * 300_000  # ~10 MB
    smuggled = {"type": "ExhaustRecord", "specVersion": payload, "counts": {"x": 1}}
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert "specVersion" not in out, "raw payload survived the guard via specVersion"
    assert "exhaust rejected" in out["reason"]
    assert "specVersion must be a version string" in out["reason"], (
        "must be rejected BY THE specVersion BOUND, not incidentally by the "
        f"aggregate backstop; got: {out['reason']}")


def test_specversion_bound_fires_below_the_aggregate_backstop():
    """The discriminating case: a specVersion too long to be a version but far
    too small to trip the 2 MiB backstop. Only the per-field bound can catch
    this, so it proves the bound exists rather than being shadowed."""
    smuggled = {"type": "ExhaustRecord", "specVersion": "v" * 5_000}
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert "specVersion" not in out
    assert "specVersion must be a version string" in out["reason"]


def test_exhaust_guard_accepts_a_real_spec_version_string():
    """The bound must not break the actual field it is bounding."""
    good = {"type": "ExhaustRecord", "specVersion": "2.0", "counts": {"dropped": 3}}
    assert engine._guard_exhaust(good) == good


def test_exhaust_guard_rejects_payload_smuggled_as_counts_keys():
    """`counts` bounded each key to 256 chars but never bounded how MANY keys.
    50 000 x 246-char keys = ~12 MB of attacker-chosen text, all label."""
    smuggled = {"type": "ExhaustRecord",
                "counts": {f"k{i:06d}" + "x" * 240: 1 for i in range(50_000)}}
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert len(out.get("counts", {})) <= 1, "counts payload survived the guard"
    assert "exhaust rejected" in out["reason"]
    assert "counts has" in out["reason"], (
        "must be rejected BY THE counts-key bound, not incidentally by the "
        f"aggregate backstop; got: {out['reason']}")


def test_counts_key_bound_fires_below_the_aggregate_backstop():
    """Discriminating case: 2 000 short count keys is only ~26 KB — nowhere
    near the 2 MiB backstop — but is still a key-value store, not a tally."""
    smuggled = {"type": "ExhaustRecord", "counts": {f"k{i}": 1 for i in range(2_000)}}
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert len(out.get("counts", {})) <= 1
    assert "counts has" in out["reason"]


def test_exhaust_guard_accepts_an_ordinary_counts_tally():
    good = {"type": "ExhaustRecord",
            "counts": {f"bucket{i}": i for i in range(64)}}
    assert engine._guard_exhaust(good) == good


def test_exhaust_guard_total_size_backstop_catches_unenumerated_dimensions():
    """The aggregate cap is the check that closes dimensions nobody enumerated.
    Every field here is individually legal — 10 000 items each carrying a
    512-char URN ref clears every per-field bound, yet totals ~5 MB."""
    ref = "urn:x:" + "a" * 500
    assert not engine._bad_ref(ref), "each ref must be individually LEGAL for this test to mean anything"
    smuggled = {"type": "ExhaustRecord",
                "items": [{"kind": "candidate", "sha256": ref, "ref": ref} for _ in range(10_000)]}
    out = engine._guard_exhaust(smuggled)
    assert out is not None
    assert "items" not in out, "per-field-legal payload still totalling megabytes survived"
    assert "exhaust rejected" in out["reason"]


def test_exhaust_guard_accepts_a_large_but_legitimate_ref_ledger():
    """A real 10 000-entry discard ledger of bare digests must still pass —
    the backstop bounds bytes, not usefulness."""
    good = {"type": "ExhaustRecord", "source": "compute",
            "items": [{"kind": "candidate", "sha256": "a" * 64} for _ in range(10_000)]}
    assert engine._guard_exhaust(good) == good
