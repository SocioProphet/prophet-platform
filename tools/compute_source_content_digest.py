#!/usr/bin/env python3
"""Compute a deterministic *source content-digest* for a build component, and decide
whether a rebuild is needed — COST GUARD 1 of the wave-based build-once-promote-many
deploy strategy (docs/DEPLOY-WAVE-STRATEGY.md).

Why this exists
---------------
`images.yml` and the per-component image workflows rebuild on every push whose paths
touch a component, even when the *content* is byte-identical to what was already built
(a whitespace-only merge, a revert-to-same, a re-run). A rebuild that produces the same
layers is wasted runner minutes. This tool gives the workflows a cheap preflight:

    content-digest(source paths)  ==  content-digest recorded in the image-lock ?
        yes -> SKIP the build, REUSE the already-pinned immutable sha256 digest
        no  -> build, push, and record the new content-digest alongside the new digest

The content-digest is a sha256 over the SORTED list of ``<posix-path>\\0<sha256(bytes)>``
for every file under the declared source paths. It is:

  * deterministic  — sorted, path-relative, byte-exact, no timestamps/inode/mode noise;
  * content-only   — a file moved without content change moves the line but the set-hash
                     still changes (path is part of the tuple, intentionally: a rename is
                     a real source change that can change a COPY in a Dockerfile);
  * git-free       — hashes file bytes directly, so it runs identically in CI and locally
                     and in a test tmpdir with no repository.

Fail-closed
-----------
An unreadable path, a missing declared path, or a non-regular file makes the digest
computation ERROR (non-zero exit) rather than silently hashing a partial tree — a
partial hash could equal a prior full hash by omission and wave a stale build through.
``--allow-missing`` is available for the *comparison* CLI only (a not-yet-created
component legitimately has no lock), never for digest emission.

Usage
-----
  # Emit the content-digest for a set of paths (newline/space separated globs or dirs):
  compute_source_content_digest.py digest \\
      --path services/search-orchestrator \\
      --path .github/workflows/search-orchestrator-image.yml

  # Decide skip-vs-build against a recorded image-lock (exit 0 = SKIP, 10 = BUILD):
  compute_source_content_digest.py decide \\
      --path services/search-orchestrator \\
      --lock releases/images/search-orchestrator.image-lock.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

# Directories that never belong to a component's *source* content — hashing them would
# make the digest depend on local build detritus and defeat the whole skip decision.
_EXCLUDE_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules",
                 ".venv", ".venv-tools", "dist", "build", ".terraform"}

# Field name written into the image-lock so the next run can compare against it.
CONTENT_DIGEST_FIELD = "source_content_digest"


def _iter_files(paths: Iterable[Path]) -> list[Path]:
    """Expand the declared paths into a flat, deterministic list of regular files."""
    out: list[Path] = []
    for p in paths:
        if not p.exists():
            raise SystemExit(f"::error::source path does not exist: {p} "
                             f"(refusing to hash a partial tree — fail closed)")
        if p.is_file():
            out.append(p)
            continue
        for child in p.rglob("*"):
            if child.is_dir():
                continue
            if any(part in _EXCLUDE_DIRS for part in child.parts):
                continue
            if not child.is_file():
                # sockets / fifos / broken symlinks — a build input we cannot hash.
                raise SystemExit(f"::error::non-regular file under source path: {child}")
            out.append(child)
    return out


def compute_digest(paths: Iterable[Path], root: Path | None = None) -> str:
    """Return ``sha256:<64hex>`` over the sorted (relpath, filehash) tuples."""
    root = (root or Path.cwd()).resolve()
    files = _iter_files([Path(p) for p in paths])
    lines: list[str] = []
    for f in files:
        rel = f.resolve()
        try:
            rel_str = rel.relative_to(root).as_posix()
        except ValueError:
            rel_str = rel.as_posix()
        file_hash = hashlib.sha256(f.read_bytes()).hexdigest()
        lines.append(f"{rel_str}\0{file_hash}")
    lines.sort()
    agg = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return f"sha256:{agg}"


def _load_lock_content_digest(lock_path: Path, allow_missing: bool) -> str | None:
    if not lock_path.exists():
        if allow_missing:
            return None
        raise SystemExit(f"::error::image-lock not found: {lock_path}")
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"::error::image-lock is not a JSON object: {lock_path}")
    return data.get(CONTENT_DIGEST_FIELD)


def _emit_github_output(**kv: str) -> None:
    """Write key=value pairs to $GITHUB_OUTPUT when running in Actions (no-op locally)."""
    import os
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            fh.write(f"{k}={v}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("digest", help="print the source content-digest")
    d.add_argument("--path", action="append", required=True, dest="paths")
    d.add_argument("--root", type=Path, default=None)

    c = sub.add_parser("decide", help="SKIP (exit 0) if content matches lock, else BUILD (exit 10)")
    c.add_argument("--path", action="append", required=True, dest="paths")
    c.add_argument("--lock", type=Path, required=True)
    c.add_argument("--root", type=Path, default=None)
    c.add_argument("--allow-missing", action="store_true",
                   help="a missing lock means BUILD (first build of a new component), not error")

    args = parser.parse_args(argv)

    if args.cmd == "digest":
        print(compute_digest(args.paths, args.root))
        return 0

    # decide
    current = compute_digest(args.paths, args.root)
    recorded = _load_lock_content_digest(args.lock, args.allow_missing)
    if recorded is not None and recorded == current:
        print(f"SKIP: source content-digest unchanged ({current}) — reuse pinned digest")
        _emit_github_output(build_needed="false", content_digest=current)
        return 0
    reason = "no recorded content-digest" if recorded is None else "content-digest changed"
    print(f"BUILD: {reason} (current={current}, recorded={recorded})")
    _emit_github_output(build_needed="true", content_digest=current)
    return 10


if __name__ == "__main__":
    raise SystemExit(main())
