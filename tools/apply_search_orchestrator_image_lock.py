"""Apply a Wave-0 image build's DIGEST EVIDENCE to the search-orchestrator image-lock + patch.

INV-DEP-7 — a lock digest is ONLY EVER a real push output. This tool is the SOLE writer of
``releases/images/search-orchestrator.image-lock.json``, and it writes only from the evidence
artifact that ``search-orchestrator-image.yml`` uploads AFTER a successful
``docker buildx …--push`` (``steps.build.outputs.digest`` — the registry's own content digest).
A lock digest is never hand-authored and never *computed*; the wave-deploy incident
(``sha256:bbfea6e4…`` frozen + promoted but never pushed) is exactly a lock digest that did not
come from a push. So this refuses evidence whose digest is empty or a placeholder sentinel, and
it carries the build's ``source_content_digest`` through so the cost-guard's next skip decision
compares against the SAME real build (never a hand-entered content-digest divorced from a push).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from render_search_orchestrator_image_patch import IMAGE, validate_lock, render_patch

LOCK_PATH = Path("releases/images/search-orchestrator.image-lock.json")
PATCH_PATH = Path("infra/k8s/search-orchestrator/overlays/policy/image-patch.yaml")

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def build_lock(evidence: dict) -> dict:
    digest = str(evidence.get("digest", ""))
    source_sha = str(evidence.get("source_sha", ""))
    pinned_ref = str(evidence.get("pinned_ref", ""))
    source_content_digest = str(evidence.get("source_content_digest", "") or "")

    # INV-DEP-7 writer discipline: the evidence MUST carry a real registry digest produced by
    # the push. A blank or placeholder digest (REPLACE_…, a bare tag, anything not sha256:<64hex>)
    # means this evidence did not come from a real buildx --push — refuse to mint a lock from it.
    if not _DIGEST_RE.match(digest):
        raise SystemExit(
            f"::error::INV-DEP-7: image-build evidence digest {digest!r} is not a real push output "
            f"(want sha256:<64hex> from steps.build.outputs.digest). Refusing to write a lock — a "
            f"lock digest is only ever a real docker buildx --push output, never computed/placeholder."
        )
    if source_sha in ("", "REPLACE_WITH_GIT_SHA"):
        raise SystemExit("::error::INV-DEP-7: evidence has no source_sha — not a real build")

    lock = {
        "image_lock_id": "search-orchestrator-image-lock",
        "component": "services/search-orchestrator",
        "image": IMAGE,
        "source_sha": source_sha,
        "digest": digest,
        "pinned_ref": pinned_ref,
        # Carried from the SAME build that pushed the digest, so the cost-guard's next skip
        # decision compares against the content that produced this exact pushed image.
        "source_content_digest": source_content_digest or None,
        "workflow": ".github/workflows/search-orchestrator-image.yml",
        # Provenance marker: this digest came from a real push, applied by this tool. Nothing
        # else writes the lock; a lock without this marker is a hand-authored placeholder.
        "digest_provenance": "buildx-push",
        "status": "pinned",
    }
    if lock["source_content_digest"] is None:
        # A real push always emits it; if absent, drop the key rather than record a null so the
        # cost-guard treats it as "no recorded content-digest" => BUILD (fail-closed), not a match.
        del lock["source_content_digest"]
    validate_lock(lock)
    return lock


def write_outputs(lock: dict, lock_path: Path, patch_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    patch_path.write_text(render_patch(str(lock["pinned_ref"])), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Search Orchestrator image digest evidence to release lock and Kustomize patch")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--lock-output", type=Path, default=LOCK_PATH)
    parser.add_argument("--patch-output", type=Path, default=PATCH_PATH)
    args = parser.parse_args()

    lock = build_lock(load_json(args.evidence))
    write_outputs(lock, args.lock_output, args.patch_output)
    print(f"wrote image lock to {args.lock_output}")
    print(f"wrote image patch to {args.patch_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
