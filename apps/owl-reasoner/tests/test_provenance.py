"""Vendored-artifact integrity for the KKO TBox — the ASSERTION, not the record.

The estate's recurring failure is a correct artifact with no connection to anything that checks
it: a PROVENANCE.md nothing verifies is decoration. So the load-bearing test here is not
"the recorded digest matches the file" (that only proves the two were written by the same hand);
it is "a TAMPERED file actually stops the service", proven by tampering with a real copy of the
package and watching a real interpreter refuse to import it.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from owl_reasoner import reasoner

SRC_ROOT = Path(reasoner.__file__).resolve().parents[1]     # .../src
PKG_ROOT = SRC_ROOT / "owl_reasoner"


def _reparent(blob: bytes) -> bytes:
    """The realistic tamper: silently re-parent a class in the Peircean typology.

    `:Monads` -> `:Places` are both real KKO superclasses of the same byte length, so the result
    is still valid Turtle, still parses without complaint, and is still exactly 327,797 bytes —
    it defeats a size check and a parse check. What it changes is the ENTAILMENTS. This is the
    precise failure this gate exists for: an artifact that does not fail, it answers differently.
    """
    out = blob.replace(b"rdfs:subClassOf :Monads", b"rdfs:subClassOf :Places", 1)
    assert out != blob, "tamper fixture is stale — the anchor string is no longer in the TBox"
    return out


def test_vendored_kko_matches_the_pinned_sha256():
    """The recorded digest IS the file's digest. Necessary, nowhere near sufficient."""
    blob = (PKG_ROOT / "data" / "kko-2.10.n3").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == reasoner.KKO_SHA256
    assert len(blob) == 327_797


def test_pinned_digest_is_asserted_at_import_not_merely_recorded():
    """Import already ran the gate — KKO_INTEGRITY is its verdict, not a lazy flag."""
    assert reasoner.KKO_INTEGRITY == "verified"


def test_provenance_md_records_the_same_digest_as_the_code():
    """The doc and the constant cannot drift apart silently."""
    doc = (PKG_ROOT / "data" / "PROVENANCE.md").read_text()
    assert reasoner.KKO_SHA256 in doc
    assert "CC-BY-4.0" in doc                                    # licence recorded
    assert "3f888b397255b69d1439fd95823e97011ed9440b" in doc     # pinned, not a branch name


def test_verify_kko_integrity_rejects_a_tampered_file(tmp_path: Path):
    """NEGATIVE: one flipped byte and the gate refuses, naming both digests."""
    good = (PKG_ROOT / "data" / "kko-2.10.n3").read_bytes()
    tampered = tmp_path / "kko-2.10.n3"
    tampered.write_bytes(_reparent(good))
    assert tampered.read_bytes() != good
    assert len(tampered.read_bytes()) == len(good), "the tamper must defeat a size check too"

    with pytest.raises(RuntimeError) as exc:
        reasoner.verify_kko_integrity(tampered)
    msg = str(exc.value)
    assert "drifted" in msg and reasoner.KKO_SHA256 in msg
    assert "SocioProphet/kbpedia" in msg     # the error tells you where to re-vendor from


def test_verify_kko_integrity_degrades_on_an_absent_file(tmp_path: Path):
    """Absent is NOT drifted: a packaging gap degrades honestly, it does not raise."""
    assert reasoner.verify_kko_integrity(tmp_path / "nope.n3") == "absent"
    assert reasoner.kko_file_digest(tmp_path / "nope.n3") is None


def test_kko_tbox_status_binds_entailments_to_the_ontology_digest():
    """A loaded TBox reports WHICH bytes produced the closure."""
    status = reasoner.kko_tbox_status(requested=True, triples=1234)
    assert status["loaded"] is True
    assert status["sha256"] == reasoner.KKO_SHA256
    assert "SocioProphet/kbpedia" in status["source"]

    degraded = reasoner.kko_tbox_status(requested=True, triples=0)
    assert degraded["loaded"] is False and "unavailable_reason" in degraded
    assert "sha256" not in degraded          # never claim a digest for a TBox that wasn't used


def test_with_kko_actually_loads_the_verified_tbox():
    """End-to-end: the verified bytes are the ones reasoning runs over."""
    ttl = ('@prefix kko: <http://kbpedia.org/ontologies/kko#> .\n'
           '@prefix ex: <http://ex/> .\nex:a a kko:Monads .')
    out = reasoner.reason(ttl, inference="rdfs", with_kko=True)
    assert out["kko_tbox"]["loaded"] is True
    assert out["kko_tbox"]["triples"] > 1000
    assert out["kko_tbox"]["sha256"] == reasoner.KKO_SHA256


def test_tampered_kko_tbox_kills_import_in_a_real_process(tmp_path: Path):
    """THE test. A drifted TBox must stop the service, not quietly change its answers.

    Copies the package, tampers the vendored .n3, and imports it in a FRESH interpreter. If the
    gate were only a recorded digest (or a function nobody calls), this import would succeed and
    the process would go on reasoning over an ontology it did not declare.
    """
    fake_src = tmp_path / "src"
    shutil.copytree(SRC_ROOT, fake_src, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    n3 = fake_src / "owl_reasoner" / "data" / "kko-2.10.n3"
    n3.write_bytes(_reparent(n3.read_bytes()))

    proc = subprocess.run(
        [sys.executable, "-c", "import owl_reasoner.reasoner"],
        cwd=fake_src, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(fake_src)},
    )
    assert proc.returncode != 0, (
        "a TAMPERED KKO TBox imported cleanly — the digest is recorded but NOT enforced.\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}")
    assert "RuntimeError" in proc.stderr
    assert "vendored KKO TBox drifted" in proc.stderr


def test_untampered_copy_still_imports(tmp_path: Path):
    """Control for the test above: the same procedure with UNMODIFIED bytes must succeed, so a
    green negative result cannot be an artefact of the copy/subprocess machinery."""
    fake_src = tmp_path / "src"
    shutil.copytree(SRC_ROOT, fake_src, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    proc = subprocess.run(
        [sys.executable, "-c", "import owl_reasoner.reasoner as r; print(r.KKO_INTEGRITY)"],
        cwd=fake_src, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(fake_src)},
    )
    assert proc.returncode == 0, proc.stderr
    assert "verified" in proc.stdout
