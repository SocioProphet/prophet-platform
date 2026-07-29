"""Vendored zero-trust kernel schemas — provenance ASSERTED, not just written down.

The W12 finding was that six schemas were described as "vendored" with no source repo named:
real files, real validation, and no way to answer "vendored from WHERE?". The origin has since
been established (SocioProphet/mcp-a2a-zero-trust@0399e8ae, all six byte-identical), but a
recorded origin that nothing checks decays into the same state the moment someone edits a file.

So the load-bearing tests here are the ones that TAMPER: each of the three refusals (drifted,
missing, unpinned) is proven by mutating a real copy of the package and watching a real
interpreter refuse to import it.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from compute_gateway import zerotrust

SRC_ROOT = Path(zerotrust.__file__).resolve().parents[1]        # .../src
PKG_ROOT = SRC_ROOT / "compute_gateway"
SCHEMA_DIR = PKG_ROOT / "schemas"


def _import_copy(tmp_path: Path, mutate) -> subprocess.CompletedProcess[str]:
    """Copy the package, mutate its vendored schemas, import it in a FRESH interpreter."""
    fake_src = tmp_path / "src"
    shutil.copytree(SRC_ROOT, fake_src, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    mutate(fake_src / "compute_gateway" / "schemas")
    return subprocess.run(
        [sys.executable, "-c", "import compute_gateway.zerotrust"],
        cwd=fake_src, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(fake_src)},
    )


# ── the provenance itself ────────────────────────────────────────────────────

def test_every_vendored_schema_is_pinned_with_an_upstream_path_and_digest():
    """Six files, six rows — a named source for each, not a directory-level hand-wave."""
    assert len(zerotrust.SCHEMA_PROVENANCE) == 6
    on_disk = {p.name for p in SCHEMA_DIR.glob("*.schema.json")}
    assert on_disk == set(zerotrust.SCHEMA_PROVENANCE), "the pinned set must BE the shipped set"

    for name, (upstream_path, digest) in zerotrust.SCHEMA_PROVENANCE.items():
        assert upstream_path.endswith(name), f"{name}: upstream path must name the same file"
        assert upstream_path.count("/") >= 1, f"{name}: upstream path must be a real repo path"
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
        assert hashlib.sha256((SCHEMA_DIR / name).read_bytes()).hexdigest() == digest


def test_the_source_repo_is_NAMED_and_the_commit_PINNED():
    """The finding in one assertion: these came from somewhere identifiable."""
    assert zerotrust.KERNEL_REPO == "SocioProphet/mcp-a2a-zero-trust"
    assert len(zerotrust.KERNEL_COMMIT) == 40                       # a commit, not a branch
    assert all(c in "0123456789abcdef" for c in zerotrust.KERNEL_COMMIT)
    assert zerotrust.KERNEL_REF == f"{zerotrust.KERNEL_REPO}@{zerotrust.KERNEL_COMMIT}"


def test_digests_are_asserted_at_import_not_merely_recorded():
    """SCHEMA_DIGESTS exists only because the gate ran during import."""
    assert set(zerotrust.SCHEMA_DIGESTS) == set(zerotrust.SCHEMA_PROVENANCE)
    for name, digest in zerotrust.SCHEMA_DIGESTS.items():
        assert digest == zerotrust.SCHEMA_PROVENANCE[name][1]


def test_provenance_md_records_what_the_code_enforces():
    doc = (SCHEMA_DIR / "PROVENANCE.md").read_text()
    assert zerotrust.KERNEL_REPO in doc
    assert zerotrust.KERNEL_COMMIT in doc
    for name, (upstream_path, digest) in zerotrust.SCHEMA_PROVENANCE.items():
        assert digest in doc, f"{name}: digest missing from PROVENANCE.md"
        assert upstream_path in doc, f"{name}: upstream path missing from PROVENANCE.md"


def test_every_vendored_schema_is_still_valid_json_with_an_id():
    """$id is what _registry() keys on — a schema without one silently fails to resolve refs."""
    for name in zerotrust.SCHEMA_PROVENANCE:
        doc = json.loads((SCHEMA_DIR / name).read_text())
        assert "$id" in doc, f"{name} has no $id"


# ── the three refusals, each proven by tampering ─────────────────────────────

def test_verify_rejects_a_drifted_schema(tmp_path: Path):
    """NEGATIVE (unit): a loosened contract is refused, and the error names the re-vendor source."""
    shutil.copytree(SCHEMA_DIR, tmp_path / "schemas")
    target = tmp_path / "schemas" / "tool_grant_check.schema.json"
    doc = json.loads(target.read_text())
    # the realistic drift: weaken the contract rather than corrupt the file. Dropping `required`
    # keeps it valid JSON Schema and would silently admit evidence the kernel rejects.
    doc.pop("required", None)
    target.write_text(json.dumps(doc, indent=2))

    with pytest.raises(RuntimeError) as exc:
        zerotrust.verify_vendored_schemas(tmp_path / "schemas")
    msg = str(exc.value)
    assert "DRIFTED" in msg and "tool_grant_check.schema.json" in msg
    assert zerotrust.KERNEL_REF in msg
    assert "schemas/interop/tool_grant_check.schema.json" in msg   # the upstream path to re-copy


def test_verify_rejects_a_missing_schema(tmp_path: Path):
    shutil.copytree(SCHEMA_DIR, tmp_path / "schemas")
    (tmp_path / "schemas" / "quorum_proof.schema.json").unlink()
    with pytest.raises(RuntimeError) as exc:
        zerotrust.verify_vendored_schemas(tmp_path / "schemas")
    assert "MISSING" in str(exc.value) and "quorum_proof.schema.json" in str(exc.value)


def test_verify_rejects_an_UNPINNED_schema_smuggled_into_the_directory(tmp_path: Path):
    """The subtle one: _registry() globs this directory and registers by $id, so an extra file
    can satisfy a canonical $ref and become the contract without anyone vendoring it."""
    shutil.copytree(SCHEMA_DIR, tmp_path / "schemas")
    (tmp_path / "schemas" / "rogue.schema.json").write_text(json.dumps({
        "$id": "https://socioprophet.dev/schemas/canonical/grant.schema.json",   # shadows a real $id
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",                                                        # permits anything
    }))
    with pytest.raises(RuntimeError) as exc:
        zerotrust.verify_vendored_schemas(tmp_path / "schemas")
    msg = str(exc.value)
    assert "UNPINNED" in msg and "rogue.schema.json" in msg
    assert "$id" in msg or "canonical $ref" in msg


def test_the_untampered_directory_verifies(tmp_path: Path):
    """Control: the same procedure on unmodified bytes passes, so the refusals above are real."""
    shutil.copytree(SCHEMA_DIR, tmp_path / "schemas")
    digests = zerotrust.verify_vendored_schemas(tmp_path / "schemas")
    assert len(digests) == 6


# ── and the same three, proven to actually stop a process ────────────────────

@pytest.mark.parametrize("case,mutate,needle", [
    ("drifted",
     lambda d: (d / "grant.schema.json").write_bytes(
         (d / "grant.schema.json").read_bytes().replace(b'"required"', b'"reqiured"', 1)),
     "DRIFTED"),
    ("missing",
     lambda d: (d / "attestation_bundle.schema.json").unlink(),
     "MISSING"),
    ("unpinned",
     lambda d: (d / "smuggled.schema.json").write_text('{"$id":"x","type":"object"}'),
     "UNPINNED"),
])
def test_tampered_schemas_kill_import_in_a_real_process(tmp_path: Path, case, mutate, needle):
    """THE tests. If the digest table were merely recorded, every one of these would import fine
    and the gateway would go on enforcing a contract it cannot name."""
    proc = _import_copy(tmp_path, mutate)
    assert proc.returncode != 0, (
        f"a {case.upper()} vendored schema imported cleanly — provenance is recorded but NOT "
        f"enforced.\nstdout={proc.stdout}\nstderr={proc.stderr}")
    assert "RuntimeError" in proc.stderr
    assert needle in proc.stderr


def test_untampered_copy_still_imports(tmp_path: Path):
    """Control for the subprocess machinery itself."""
    proc = _import_copy(tmp_path, lambda d: None)
    assert proc.returncode == 0, proc.stderr
