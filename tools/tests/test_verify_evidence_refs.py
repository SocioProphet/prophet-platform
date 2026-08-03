"""Teeth for the evidence-reference gate (INV-DEP-13).

Proven both ways over the pure scan(manifest_obj, resolver) seam with an in-memory fake resolver
(no filesystem): a ref that resolves passes; a repo-path ref to a missing file fails; a
digest-evidence claim that no longer matches its artifact fails; a fabricated evidence:// URI that
resolves to nothing fails; a malformed target fails; and an explicit REPLACE_WITH placeholder is
NOT treated as a live claim. Prose, registry refs, and org/repo strings must never be flagged.
Finally, the SHIPPED releases/ artifacts must pass end-to-end against the real filesystem — a gate
that has only ever passed proves nothing, so the negative cases carry the weight.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_evidence_refs as chk  # noqa: E402


class FakeResolver:
    """A filesystem-free Resolver: `files` maps repo-relative path -> ('exists', parse_error,
    sha256). A path absent from `files` does not exist. `top` is the set of real top-level
    segments."""

    def __init__(self, files: dict[str, dict], top: set[str]):
        self._files = files
        self._top = top

    def is_top_level(self, segment: str) -> bool:
        return segment in self._top

    def exists(self, relpath: str) -> bool:
        return relpath in self._files

    def parse_error(self, relpath: str):
        return self._files.get(relpath, {}).get("parse_error")

    def sha256(self, relpath: str):
        return self._files.get(relpath, {}).get("sha256")


TOP = {"releases", "tools", "infra", "bundles", "conformance", "docs", "services", ".github"}


# (a) A repo-path ref that resolves to a real, parseable file -> clean.
def test_resolvable_repo_path_ref_passes():
    files = {"releases/images/search-orchestrator.image-lock.json": {}}
    r = FakeResolver(files, TOP)
    manifest = {"lock": "releases/images/search-orchestrator.image-lock.json"}
    assert chk.scan(manifest, r) == []


# (b) A repo-path ref to a MISSING file -> fails, naming the field and the unresolved target.
def test_repo_path_ref_to_missing_file_fails():
    r = FakeResolver({}, TOP)
    manifest = {"artifacts": ["infra/k8s/search-orchestrator/base/pvc.yaml"]}
    violations = chk.scan(manifest, r, where="m.json")
    assert len(violations) == 1, violations
    v = violations[0]
    assert "m.json" in v
    assert ".artifacts[0]" in v
    assert "infra/k8s/search-orchestrator/base/pvc.yaml" in v


# A structured target that exists but does NOT parse -> fail-closed.
def test_malformed_target_fails_closed():
    files = {"releases/manifests/x.json": {"parse_error": "is not valid JSON (JSONDecodeError)"}}
    r = FakeResolver(files, TOP)
    manifest = {"ref": "releases/manifests/x.json"}
    violations = chk.scan(manifest, r)
    assert len(violations) == 1 and "is not valid JSON" in violations[0]


# The whole artifact failing to load is itself a fail-closed violation (integration-level, but the
# same principle): a manifest we cannot even parse cannot be certified. Covered by the real-FS run.


# (c) Digest-evidence: the claimed digest MUST equal sha256(the referenced file).
def test_digest_evidence_match_passes():
    real = "sha256:" + "a" * 64
    files = {"bundles/fogstack.access-v0.1.yaml": {"sha256": real}}
    r = FakeResolver(files, TOP)
    manifest = {"bundle": "bundles/fogstack.access-v0.1.yaml", "bundle_digest": real}
    assert chk.scan(manifest, r) == []


def test_digest_evidence_mismatch_fails():
    files = {"bundles/fogstack.access-v0.1.yaml": {"sha256": "sha256:" + "a" * 64}}
    r = FakeResolver(files, TOP)
    manifest = {"bundle": "bundles/fogstack.access-v0.1.yaml", "bundle_digest": "sha256:" + "b" * 64}
    violations = chk.scan(manifest, r)
    assert len(violations) == 1, violations
    assert "does" not in violations[0] or "no longer matches" in violations[0]
    assert "bundle_digest" in violations[0]


def test_digest_evidence_malformed_digest_fails():
    files = {"bundles/b.yaml": {"sha256": "sha256:" + "a" * 64}}
    r = FakeResolver(files, TOP)
    manifest = {"bundle": "bundles/b.yaml", "bundle_digest": "sha256:deadbeef"}  # truncated
    violations = chk.scan(manifest, r)
    assert len(violations) == 1 and "well-formed sha256" in violations[0]


# An IMAGE digest (no sibling repo file) is NOT a digest-evidence claim and must not be hashed.
def test_image_digest_is_not_treated_as_file_digest():
    r = FakeResolver({}, TOP)
    manifest = {
        "image": "us-central1-docker.pkg.dev/proj/repo/search-orchestrator",
        "digest": "sha256:" + "f" * 64,
        "source_content_digest": "sha256:" + "e" * 64,
    }
    # `digest`/`source_content_digest` have no sibling repo-file path; nothing to verify, no false
    # positive. The registry `image` string is not a repo-path ref either.
    assert chk.scan(manifest, r) == []


# (d) A fabricated evidence:// URI that resolves to nothing -> fails (the agent-registry #56 ghost).
def test_fabricated_evidence_uri_fails():
    r = FakeResolver({}, TOP)
    manifest = {"provenance": "evidence://releases/evidence/does-not-exist.json"}
    violations = chk.scan(manifest, r)
    assert len(violations) == 1 and "evidence/file URI" in violations[0]


def test_evidence_uri_that_resolves_passes():
    files = {"releases/evidence/real.json": {}}
    r = FakeResolver(files, TOP)
    manifest = {"provenance": "evidence://releases/evidence/real.json"}
    assert chk.scan(manifest, r) == []


def test_file_uri_stripped_and_resolved():
    files = {"tools/validate_fogstack.py": {}}
    r = FakeResolver(files, TOP)
    manifest = {"helper": "file:///tools/validate_fogstack.py"}
    assert chk.scan(manifest, r) == []


# An explicit REPLACE_WITH placeholder (template/example) is NOT a live claim -> skipped.
def test_placeholder_is_skipped():
    r = FakeResolver({}, TOP)
    manifest = {
        "evidence": {
            "sbom": "REPLACE_WITH_SBOM_REFERENCE",
            "gatewayDigest": "sha256:REPLACE_WITH_REAL_DIGEST",
        },
        "cluster_ref": "REPLACE_WITH_CLUSTER_REF",
    }
    assert chk.scan(manifest, r) == []


# Prose, registry refs, and org/repo strings are not repo-path refs and must never be flagged.
def test_non_reference_strings_are_not_flagged():
    r = FakeResolver({}, TOP)
    manifest = {
        "evidence": [
            "Kubernetes base includes ServiceAccount/RBAC, PVC-backed storage, network policy",
            "Search Orchestrator image workflow builds/publishes GHCR image and emits evidence",
        ],
        "source": {
            "capabilityRepo": "SocioProphet/cloudshell-fog",
            "substrateRepo": "SocioProphet/prophet-platform",
        },
        "image": "ghcr.io/socioprophet/cloudshell-fog",
        "pinned_ref": "us-central1-docker.pkg.dev/proj/repo/x@sha256:" + "a" * 64,
        "status": "prepared-pending-real-provider-captures",
    }
    assert chk.scan(manifest, r) == []


# A directory reference (trailing content, no extension) that exists is fine — no parse obligation.
def test_directory_ref_that_exists_passes():
    files = {"infra/k8s/search-orchestrator/overlays/policy": {}}  # a dir
    r = FakeResolver(files, TOP)
    manifest = {"kustomize_overlay": "infra/k8s/search-orchestrator/overlays/policy"}
    assert chk.scan(manifest, r) == []


# The SHIPPED releases/ artifacts must pass end-to-end against the real filesystem.
def test_shipped_release_artifacts_all_resolve():
    root = Path(__file__).resolve().parents[2]
    n, violations = chk.check_artifacts(root, chk.DEFAULT_ARTIFACT_GLOBS)
    assert n > 0, "expected to find release artifacts"
    assert violations == [], "shipped release artifacts must have no unresolved references:\n" + "\n".join(violations)


# The digest-evidence claims in the shipped fogstack manifests really match their bundle/rulepack
# files (the strongest real-data teeth): flip one byte of the claim and it must fail.
def test_shipped_digest_evidence_is_content_verified(tmp_path):
    root = Path(__file__).resolve().parents[2]
    resolver = chk.FsResolver(root)
    import json
    m = json.loads((root / "releases/manifests/fogstack.access-v0.1.manifest.json").read_text())
    assert chk.scan(m, resolver) == []  # real digests match
    m["bundle_digest"] = "sha256:" + ("0" * 64)  # fabricate a wrong-but-well-formed digest
    violations = chk.scan(m, resolver)
    assert any("no longer matches" in v for v in violations), violations
