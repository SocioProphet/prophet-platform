"""Every vendored copy of a library must be pinned at ONE upstream commit.

Per-app freshness tests already prove each tree matches its own VENDOR.json. Nothing
proved that two apps vendoring the same library agree with each other — so app A could
sit at one commit and app B at another, both "fresh", both green, silently running
different code.

That is not hypothetical here. The vendor-freshness plane records exactly this failure
for the JS engine: lifecycle-warden drifted five releases behind hellgraph-service
unnoticed, because a re-vendor moved one consumer and not the other. Its answer was
"the tarball and the floor move for ALL consumers in one change or not at all." The
Python vendor trees had no equivalent control until this test.

Byte-identity is also checked where two trees vendor the same filename: agreeing on a
commit string while shipping different bytes would be the same failure one level down.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[2]


def _vendor_manifests() -> list[tuple[pathlib.Path, dict]]:
    found = []
    for path in REPO.glob("apps/*/third_party/*/VENDOR.json"):
        found.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return sorted(found)


def test_vendor_manifests_are_discoverable():
    """If this finds nothing the rest of the file is vacuously green."""
    assert _vendor_manifests(), "no VENDOR.json found — this guard would pass on nothing"


def test_one_upstream_commit_per_vendored_library():
    by_library: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for path, manifest in _vendor_manifests():
        library = manifest.get("source_repo", "?") + ":" + manifest.get("source_path", "?")
        commit = manifest.get("source_commit", "?")
        by_library[library][commit].append(str(path.relative_to(REPO)))

    split = {lib: commits for lib, commits in by_library.items() if len(commits) > 1}
    assert not split, (
        "split-brain vendoring — one library pinned at several commits: "
        + json.dumps(split, indent=2, sort_keys=True)
    )


def test_shared_filenames_are_byte_identical_across_trees():
    """Agreeing on a commit while shipping different bytes is the same bug, one level down."""
    digests: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for path, manifest in _vendor_manifests():
        library = manifest.get("source_repo", "?") + ":" + manifest.get("source_path", "?")
        tree = path.parent
        for name in manifest.get("files", {}):
            candidate = tree / "semantic" / name
            if not candidate.exists():
                candidate = tree / name
            if candidate.exists():
                digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
                digests[(library, name)][str(path.relative_to(REPO))] = digest

    divergent = {
        f"{lib} :: {name}": trees
        for (lib, name), trees in digests.items()
        if len(set(trees.values())) > 1
    }
    assert not divergent, (
        "same file, same claimed commit, different bytes: "
        + json.dumps(divergent, indent=2, sort_keys=True)
    )


def test_every_manifest_declares_its_provenance():
    for path, manifest in _vendor_manifests():
        rel = path.relative_to(REPO)
        for field in ("source_repo", "source_path", "source_commit", "files"):
            assert manifest.get(field), f"{rel} is missing {field!r} — an unattributable vendor"
        assert manifest["files"], f"{rel} pins no files, so its freshness test checks nothing"
