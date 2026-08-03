"""Teeth for the FIPS conformance check (Build 1).

Proves the check goes red on (a) a banned-algorithm CALL in the boundary and (b) a
`require_fips_validated_crypto: true` deployment with the check un-wired — and that a
bare mention in a comment does NOT trip it. Plus: the shipped repo is conformant.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_fips_conformance as fips  # noqa: E402

_BOUNDARY = {
    "version": 0.1,
    "scope": ["tools/x.py"],
    "banned_algorithms": [
        {"id": "blake2", "pattern": r"(?:hashlib\.)?blake2[bs]\s*\(", "why": "BLAKE2 not FIPS"},
    ],
    "allowlist": [],
    "fips_modules": {  # Build 2 — the CMVP-validated module allowlist per runtime
        "python": ["openssl-3-fips-provider"],
        "node": ["openssl-3-fips-provider"],
        "rust": ["aws-lc-rs"],
    },
}


def _mkroot(tmp_path: Path, *, scope_body: str, wired: bool = True, fed_flag: bool = True, modules: str = "valid") -> Path:
    (tmp_path / "security").mkdir(parents=True, exist_ok=True)
    (tmp_path / "security/fips-boundary.yaml").write_text(yaml.safe_dump(_BOUNDARY), encoding="utf-8")
    (tmp_path / "tools").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools/x.py").write_text(scope_body, encoding="utf-8")
    wf = tmp_path / ".github/workflows"
    wf.mkdir(parents=True, exist_ok=True)
    target = "fips-conformance-check" if wired else "something-else"
    (wf / "validate-target-diagnostics.yml").write_text(
        f"jobs:\n  v:\n    steps:\n      - run: make {target}\n", encoding="utf-8"
    )
    if fed_flag:
        inv = tmp_path / "apps/cloudshell-fog"
        inv.mkdir(parents=True, exist_ok=True)
        controls: dict = {"require_fips_validated_crypto": True}
        if modules == "valid":
            controls["fips_crypto_modules"] = {"python": "openssl-3-fips-provider", "rust": "aws-lc-rs"}
        elif modules == "placeholder":
            controls["fips_crypto_modules"] = {"python": "REPLACE_ME"}
        # modules == "none" ⇒ omit fips_crypto_modules entirely (a flag with no warrant)
        (inv / "deployment-inventory.federal.example.yaml").write_text(
            yaml.safe_dump({"profile": "federal", "federal_controls": controls}), encoding="utf-8"
        )
    return tmp_path


def _run(root: Path):
    b = fips.load_boundary(root)
    return fips.check_flag_enforced(root, b) + fips.scan_scope(root, b) + fips.check_module_warrant(root, b)


def test_clean_boundary_passes(tmp_path):
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n")
    assert _run(root) == []


def test_banned_algo_call_in_boundary_is_rejected(tmp_path):
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.blake2b(digest_size=32)\n")
    v = _run(root)
    assert any("non-FIPS algorithm 'blake2'" in x for x in v), v


def test_comment_mention_is_not_a_call(tmp_path):
    root = _mkroot(tmp_path, scope_body="# FIPS 180-4 (was BLAKE2b — not FIPS)\nimport hashlib\nh = hashlib.sha256()\n")
    assert _run(root) == []


def test_declared_flag_but_check_unwired_fails(tmp_path):
    # The keystone: the federal flag is true but the check is not in the CI gate.
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n", wired=False)
    v = _run(root)
    assert any("not wired into" in x for x in v), v


def test_no_federal_flag_needs_no_enforcement(tmp_path):
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n", wired=False, fed_flag=False)
    assert _run(root) == []


def test_inline_comment_with_a_call_is_not_flagged(tmp_path):
    # Copilot #1204: an inline comment mentioning a banned call must not false-positive.
    root = _mkroot(tmp_path, scope_body="import hashlib\nx = hashlib.sha256()  # replaces hashlib.blake2b(x)\n")
    assert _run(root) == []


def test_missing_boundary_with_federal_flag_fails(tmp_path):
    # Copilot #1204: a missing boundary must fail-closed when a deployment requires FIPS.
    root = _mkroot(tmp_path, scope_body="x = 1\n")
    (root / "security/fips-boundary.yaml").unlink()
    assert fips.main(["--root", str(root)]) == 1


def test_missing_boundary_without_flag_is_ok(tmp_path):
    root = _mkroot(tmp_path, scope_body="x = 1\n", fed_flag=False)
    (root / "security/fips-boundary.yaml").unlink()
    assert fips.main(["--root", str(root)]) == 0


def test_malformed_boundary_fails_closed(tmp_path):
    root = _mkroot(tmp_path, scope_body="x = 1\n")
    (root / "security/fips-boundary.yaml").write_text("{ this: : not yaml :\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        fips.load_boundary(root)


def test_shipped_repo_boundary_is_conformant():
    root = Path(fips.ROOT)
    b = fips.load_boundary(root)
    assert fips.scan_scope(root, b) == [], "shipped boundary must have no non-FIPS algorithm calls"
    assert fips.check_flag_enforced(root, b) == [], "federal FIPS flag must be enforced + wired"
    assert fips.check_module_warrant(root, b) == [], "federal deployments must name FIPS-validated modules"


# --- Build 2: module CMVP warrant ---

def test_federal_flag_without_named_modules_fails(tmp_path):
    # require_fips_validated_crypto: true but no fips_crypto_modules — a claim with no warrant.
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n", modules="none")
    assert any("claim without a warrant" in v for v in _run(root)), _run(root)


def test_federal_placeholder_module_is_rejected(tmp_path):
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n", modules="placeholder")
    assert any("not a FIPS-validated module" in v for v in _run(root)), _run(root)


def test_federal_with_valid_named_modules_passes(tmp_path):
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n", modules="valid")
    assert _run(root) == []


def test_malformed_inventory_fails_closed(tmp_path):
    # A federal inventory that will not parse must NOT silently escape the module warrant.
    root = _mkroot(tmp_path, scope_body="import hashlib\nh = hashlib.sha256()\n")
    (root / "apps/cloudshell-fog/deployment-inventory.federal.example.yaml").write_text(
        "{ this: : not yaml :\n", encoding="utf-8"
    )
    assert any("not valid YAML" in v for v in _run(root)), _run(root)
