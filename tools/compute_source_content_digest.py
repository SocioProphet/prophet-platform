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

    content-digest(source paths)  ==  content-digest recorded in the image-lock
        AND  the recorded pinned digest STILL EXISTS in the registry (INV-DEP-6) ?
        yes -> SKIP the build, REUSE the already-pinned immutable sha256 digest
        no  -> build, push, and record the new content-digest alongside the new digest

The second half of that AND is not optional cosmetics — it closes the exact hole the
wave-deploy incident surfaced. A lock can record a ``source_content_digest`` next to a
``digest`` that was NEVER pushed (a pre-computed placeholder, or a lock committed before its
Wave-0 build ran / after a registry GC). A content match against such a lock would SKIP the
build and "reuse" a digest that ImagePullBackOffs. So with ``--verify-image-exists`` a SKIP
requires BOTH the source-content match AND the recorded image resolving to a real manifest;
a missing image forces BUILD regardless of source match.

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


def _load_lock(lock_path: Path, allow_missing: bool) -> dict | None:
    if not lock_path.exists():
        if allow_missing:
            return None
        raise SystemExit(f"::error::image-lock not found: {lock_path}")
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"::error::image-lock is not a JSON object: {lock_path}")
    return data


def _load_lock_content_digest(lock_path: Path, allow_missing: bool) -> str | None:
    lock = _load_lock(lock_path, allow_missing)
    return None if lock is None else lock.get(CONTENT_DIGEST_FIELD)


def _default_image_checker(image: str, digest: str) -> str:
    """Return the registry existence status ('exists' | 'absent' | 'unreachable') of a pinned
    digest, delegating to tools/verify_pinned_digest_exists.py (INV-DEP-6). Imported lazily so
    the pure content-digest path never needs the network layer."""
    import importlib.util

    mod_path = Path(__file__).with_name("verify_pinned_digest_exists.py")
    spec = importlib.util.spec_from_file_location("verify_pinned_digest_exists", mod_path)
    assert spec is not None and spec.loader is not None
    verify = importlib.util.module_from_spec(spec)
    # Register before exec so the module's @dataclass resolves its own __module__ under
    # `from __future__ import annotations`.
    sys.modules.setdefault(spec.name, verify)
    spec.loader.exec_module(verify)
    return verify.check_manifest(image, digest).status


def decide_build(current: str, lock: dict | None, *, verify_image: bool,
                 image_checker=_default_image_checker) -> "tuple[int, str]":
    """Pure skip-vs-build decision. Returns (exit_code, message).

    exit 0  => SKIP (source content matches AND, when verify_image, the pinned image EXISTS).
    exit 10 => BUILD (content changed / no lock / recorded image missing or unverifiable).

    A SKIP is granted ONLY when both conditions hold. If the recorded source matches but the
    pinned digest has no registry manifest (or cannot be proven to), we force BUILD — a skip
    that reuses a non-existent digest is exactly the deploy-time ImagePullBackOff (INV-DEP-6).
    """
    recorded = None if lock is None else lock.get(CONTENT_DIGEST_FIELD)
    if recorded is None or recorded != current:
        reason = "no recorded content-digest" if recorded is None else "content-digest changed"
        return 10, f"BUILD: {reason} (current={current}, recorded={recorded})"

    # Source content matches. Without the image-exists check that alone would SKIP.
    if not verify_image:
        return 0, f"SKIP: source content-digest unchanged ({current}) — reuse pinned digest"

    image = str((lock or {}).get("image", ""))
    digest = str((lock or {}).get("digest", ""))
    if not image or not digest:
        return 10, ("BUILD: source matched but the lock records no image/digest to verify "
                    f"(image={image!r}, digest={digest!r}) — refusing to reuse an unverifiable pin")
    status = image_checker(image, digest)
    if status == "exists":
        return 0, (f"SKIP: source content-digest unchanged ({current}) AND pinned image exists "
                   f"in the registry — reuse {image}@{digest}")
    if status == "absent":
        return 10, ("BUILD: source content matches but the recorded pinned digest does NOT exist "
                    f"in the registry ({image}@{digest}) — a placeholder/never-pushed digest; "
                    "forcing a real build (INV-DEP-6)")
    # unreachable / anything non-definitive: we could not PROVE the image exists -> BUILD.
    return 10, ("BUILD: source content matches but the registry could not confirm the pinned "
                f"digest exists ({image}@{digest}; status={status}) — fail-closed, forcing build")


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
    c.add_argument("--verify-image-exists", action="store_true",
                   help="on a source-content match, ALSO require the recorded pinned digest to "
                        "resolve to a registry manifest (INV-DEP-6); a missing/unverifiable image "
                        "forces BUILD, never SKIP")

    args = parser.parse_args(argv)

    if args.cmd == "digest":
        print(compute_digest(args.paths, args.root))
        return 0

    # decide
    current = compute_digest(args.paths, args.root)
    lock = _load_lock(args.lock, args.allow_missing)
    rc, message = decide_build(current, lock, verify_image=args.verify_image_exists)
    print(message)
    _emit_github_output(build_needed="true" if rc == 10 else "false", content_digest=current)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
