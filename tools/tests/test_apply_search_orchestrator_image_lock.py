from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "apply_search_orchestrator_image_lock.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("apply_search_orchestrator_image_lock", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

IMAGE = MODULE.IMAGE
main = MODULE.main


def test_image_lock_applier_writes_lock_and_patch(tmp_path, monkeypatch) -> None:
    digest = "sha256:" + ("b" * 64)
    evidence = {
        "image": IMAGE,
        "source_sha": "abc123",
        "digest": digest,
        "pinned_ref": IMAGE + "@" + digest,
    }
    evidence_path = tmp_path / "evidence.json"
    lock_path = tmp_path / "image-lock.json"
    patch_path = tmp_path / "image-patch.yaml"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["tool", "--evidence", str(evidence_path), "--lock-output", str(lock_path), "--patch-output", str(patch_path)],
    )
    assert main() == 0

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["digest"] == digest
    assert lock["pinned_ref"] == IMAGE + "@" + digest
    rendered = patch_path.read_text(encoding="utf-8")
    assert "image: " + IMAGE + "@" + digest in rendered
    assert "name: search-orchestrator" in rendered
    # INV-DEP-7: a lock minted from a real push output is stamped with its provenance.
    assert lock["digest_provenance"] == "buildx-push"


# ── INV-DEP-7: the lock digest is ONLY EVER a real push output ─────────────────────────────

def test_build_lock_refuses_placeholder_digest() -> None:
    for bad in ("", "sha256:REPLACE_WITH_IMAGE_DIGEST", "ghcr.io/x:latest", "sha256:" + ("z" * 64)):
        try:
            MODULE.build_lock({"digest": bad, "source_sha": "abc", "pinned_ref": "x"})
        except SystemExit as exc:
            assert "INV-DEP-7" in str(exc)
        else:
            raise AssertionError(f"a non-push digest {bad!r} must be refused (INV-DEP-7)")


def test_build_lock_refuses_placeholder_source_sha() -> None:
    digest = "sha256:" + ("b" * 64)
    try:
        MODULE.build_lock({"digest": digest, "source_sha": "REPLACE_WITH_GIT_SHA",
                           "pinned_ref": IMAGE + "@" + digest})
    except SystemExit as exc:
        assert "INV-DEP-7" in str(exc)
    else:
        raise AssertionError("a placeholder source_sha must be refused (INV-DEP-7)")


def test_build_lock_carries_source_content_digest_from_the_same_build() -> None:
    digest = "sha256:" + ("b" * 64)
    scd = "sha256:" + ("c" * 64)
    lock = MODULE.build_lock({"digest": digest, "source_sha": "abc",
                              "pinned_ref": IMAGE + "@" + digest,
                              "source_content_digest": scd})
    assert lock["source_content_digest"] == scd, "the content-digest must ride the real build"
    assert lock["digest_provenance"] == "buildx-push"
