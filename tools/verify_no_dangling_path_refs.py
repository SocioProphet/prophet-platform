#!/usr/bin/env python3
"""Blast-radius on refactor (INV-DEP-12): a PR that MOVES/RENAMES/DELETES a repo path
must not leave any surviving tracked file still referencing that path by its old name.

A refactor that relocates a file is invisible to the file it moved — but every tool,
workflow, manifest, or doc that hard-coded the OLD path is now pointing at nothing. The
render/parse still succeeds (the string is just a string); the break only surfaces when
something dereferences the path at run time. That is the same "looks fine, fails later"
class the deploy self-containment gates (INV-DEP-9/10) close for cluster refs — here for
*repo-path* refs.

This actually happened. `infra/k8s/search-orchestrator/base/configmap.yaml` was factored out
to `.../base-support/configmap.yaml` so the prod blue-green overlay could render it. The move
was correct, but `tools/validate_search_orchestrator_academy_deploy.py` had the old
`.../base/configmap.yaml` path hard-coded in its required-files list. Nothing in the diff of
the moved file could reveal it; the validator only went red in CI, AFTER push. This gate would
have caught it in the diff, before push (and `make preflight`, L5, runs it locally).

Design / seam:
  * `scan(removed_paths, tree_files)` is the pure, git-free core. `removed_paths` is the list
    of old paths a PR deleted or renamed away; `tree_files` is the CURRENT tree as a mapping
    (or iterable of pairs) of {repo-relative path: text}. It returns human-readable violation
    strings, each carrying `file:line` and the missing path — unit-testable without a repo.
  * The git plumbing (`compute_removed_paths`, `read_tracked_files`, `main`) is a thin wrapper
    that computes the removed set from `git diff` against the merge-base and feeds the tracked
    tree to `scan`.

Matching rule (avoid false positives): a surviving reference counts only when the text contains
the FULL removed path OR a path suffix of >= 2 segments (e.g. `base/configmap.yaml`). A bare,
common basename (`kustomization.yaml`, `configmap.yaml`) is NEVER matched on its own — two
unrelated files can share a basename, and flagging that would be noise. References are matched
on path boundaries so `base/configmap.yaml` does not hit inside `xbase/configmap.yaml` or
`base/configmap.yaml.bak`.

Fail-closed: if git is unavailable, or the merge-base / diff cannot be computed, the gate exits
non-zero with a clear message. A gate that cannot compute blast-radius must not silently pass.

Auto-remediation (L6): when a derived gate KNOWS the mechanical fix, offer the patch, not just the
refusal. A RENAME reports the git-detected rename target (`git diff --diff-filter=R -M`), so each
surviving reference to the old path carries a concrete "→ <new path>" suggestion; `--fix` rewrites
the UNAMBIGUOUS full-path cases in place (literal old → new, on the same path boundaries) and prints
a summary. DELETIONS have no rename target, so they are reported but NEVER auto-rewritten — there is
no safe path to point at. `--fix` is a developer convenience; CI never runs it (CI stays report-
only and fail-closed). The default (no `--fix`) report behaviour is unchanged: report-only, exits
non-zero on any surviving reference, modifies nothing.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]

# A file bigger than this, or one carrying a NUL byte, is treated as binary/opaque and skipped
# for reference scanning. Path references live in text (YAML, Python, Markdown, shell).
_MAX_TEXT_BYTES = 2_000_000


def _needles(removed_path: str) -> list[str]:
    """The literal strings whose presence counts as a surviving reference to `removed_path`:
    the full path plus every path suffix of >= 2 segments. A single trailing segment (a bare
    basename) is deliberately excluded — it is not distinctive enough to flag."""
    parts = [p for p in removed_path.split("/") if p]
    if not parts:
        return []
    needles: list[str] = []
    # i == 0 is the full path; suffixes down to (but not including) the bare last segment.
    for i in range(len(parts) - 1):
        needles.append("/".join(parts[i:]))
    if len(parts) == 1:
        # A top-level path (e.g. `go.work`) has no >=2-segment suffix; the full path IS the
        # only distinctive form, so match it exactly.
        needles.append(parts[0])
    return needles


def _compile(needle: str) -> re.Pattern[str]:
    # Bound the match on path characters so a needle does not match inside a longer path
    # segment or a different extension: `base/configmap.yaml` must not hit `xbase/...` (left)
    # or `.../configmap.yaml.bak` (right).
    return re.compile(r"(?<![\w./-])" + re.escape(needle) + r"(?![\w./-])")


def scan(removed_paths: Iterable[str], tree_files, renames: Mapping[str, str] | None = None) -> list[str]:
    """Return violation messages for every removed path still referenced in the current tree.

    `tree_files`: a mapping {path: text} or an iterable of (path, text) pairs. A `text` of
    None is skipped (binary/unreadable). Each violation carries `file:line` and the missing
    path, deduped per (removed_path, file, line).

    `renames`: an optional {old_path: new_path} map for paths that were RENAMED (not deleted). When
    a surviving reference points at a renamed old path, the violation carries a concrete suggestion
    — "→ <new path>" — because the mechanical fix is known (that is L6, auto-remediation: `--fix`
    rewrites the unambiguous full-path cases). A DELETED path has no rename target, so it gets NO
    suggestion (there is nothing safe to point at). When `renames` is empty/None the output is
    byte-identical to the report-only default — the suggestion is purely additive for renames."""
    removed = [p for p in dict.fromkeys(removed_paths) if p]  # de-dupe, keep order, drop empties
    if not removed:
        return []
    renames = renames or {}
    removed_set = set(removed)
    patterns = {p: [_compile(n) for n in _needles(p)] for p in removed}

    if isinstance(tree_files, Mapping):
        items = tree_files.items()
    else:
        items = tree_files

    seen: set[tuple[str, str, int]] = set()
    violations: list[str] = []
    for path, text in items:
        if text is None:
            continue
        # A file the PR itself removed is not in the current tree; if a caller passes one
        # anyway, never let it flag itself.
        if path in removed_set:
            continue
        lines = text.splitlines()
        for removed_path in removed:
            pats = patterns[removed_path]
            for lineno, line in enumerate(lines, start=1):
                if any(pat.search(line) for pat in pats):
                    key = (removed_path, path, lineno)
                    if key in seen:
                        continue
                    seen.add(key)
                    new_path = renames.get(removed_path)
                    if new_path:
                        suggestion = (
                            f" It was RENAMED to '{new_path}' — update the reference to that path "
                            f"(auto-fixable: rerun with --fix)."
                        )
                    else:
                        suggestion = ""
                    violations.append(
                        f"{path}:{lineno}: references '{removed_path}', but that path was "
                        f"DELETED or RENAMED away in this PR and no longer exists — update or "
                        f"remove the reference (blast-radius of the refactor).{suggestion}"
                    )
    return violations


def plan_fixes(renames: Mapping[str, str], tree_files) -> tuple[dict[str, str], list[str]]:
    """Compute the in-place rewrites for RENAME cases only, without touching disk (pure — the
    testable core of `--fix`).

    For each `old -> new` rename, every surviving reference to the FULL old path is rewritten to
    the FULL new path, matched on the SAME path boundaries the detector uses (so `base/pvc.yaml`
    is not rewritten inside `xbase/pvc.yaml` or `pvc.yaml.bak`). This is deliberately bounded to
    the UNAMBIGUOUS full-path form: a bare-suffix reference (e.g. `base/pvc.yaml` on its own) has
    no single safe new target, so it is left for a human (it is still reported by `scan`).

    DELETIONS are never passed here (a deleted path has no rename target), so nothing a delete
    touched is ever auto-rewritten.

    Returns ({path: new_text} for files that changed, [human-readable summary lines])."""
    rmap = {o: n for o, n in renames.items() if o and n}
    if not rmap:
        return {}, []
    # Full-path, boundary-bounded pattern per old path — NOT the >=2-segment suffixes (those are
    # ambiguous to rewrite). Longer old paths first so a rewrite is stable if one is a suffix of
    # another.
    pats = {o: _compile(o) for o in sorted(rmap, key=len, reverse=True)}

    items = tree_files.items() if isinstance(tree_files, Mapping) else tree_files
    changed: dict[str, str] = {}
    summary: list[str] = []
    for path, text in items:
        if text is None or path in rmap:
            continue
        new_text = text
        per_file: list[tuple[str, str, int]] = []
        for old, pat in pats.items():
            new = rmap[old]
            new_text, count = pat.subn(lambda _m, _n=new: _n, new_text)
            if count:
                per_file.append((old, new, count))
        if per_file:
            changed[path] = new_text
            for old, new, count in per_file:
                summary.append(f"{path}: rewrote {count} full-path reference(s) '{old}' -> '{new}'")
    return changed, summary


# --------------------------------------------------------------------------------------------
# git plumbing — a thin wrapper around scan().
# --------------------------------------------------------------------------------------------
class GitError(RuntimeError):
    pass


def _git(args: list[str], root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise GitError("git executable not found — cannot compute blast-radius") from e
    if proc.returncode != 0:
        raise GitError(f"`git {' '.join(args)}` failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def merge_base(root: Path, base_ref: str) -> str:
    """The merge-base of HEAD and `base_ref`. Robust when `base_ref` is already the base."""
    out = _git(["merge-base", "HEAD", base_ref], root).strip()
    if not out:
        raise GitError(f"could not determine merge-base of HEAD and {base_ref}")
    return out


def compute_removed_paths(root: Path, base: str, head: str = "HEAD") -> list[str]:
    """Old paths DELETED (D) or RENAMED-away (R) between `base` and `head`."""
    out = _git(["diff", "--diff-filter=DR", "--name-status", "-z", base, head], root)
    return _parse_name_status_z(out)


def compute_rename_map(root: Path, base: str, head: str = "HEAD") -> dict[str, str]:
    """{old_path: new_path} for paths RENAMED (R) between `base` and `head`. `-M` asks git to
    detect renames; a pure delete has no entry here, so it can never receive an auto-fix target."""
    out = _git(["diff", "--diff-filter=R", "-M", "--name-status", "-z", base, head], root)
    return _parse_rename_map_z(out)


def _parse_rename_map_z(out: str) -> dict[str, str]:
    """Parse `git diff --diff-filter=R --name-status -z`: each R record is
    `Rnnn\\0oldpath\\0newpath`. Returns {old: new}."""
    fields = out.split("\0")
    renames: dict[str, str] = {}
    i = 0
    while i < len(fields):
        status = fields[i]
        if not status:
            i += 1
            continue
        if status[0] == "R" and i + 2 < len(fields):
            old, new = fields[i + 1], fields[i + 2]
            if old and new:
                renames[old] = new
            i += 3
        else:
            i += 2
    return renames


def _parse_name_status_z(out: str) -> list[str]:
    """Parse `git diff --name-status -z` output. NUL-separated fields: a D record is
    `status\\0path`; an R record is `Rnnn\\0oldpath\\0newpath`. We collect the OLD path."""
    fields = out.split("\0")
    removed: list[str] = []
    i = 0
    while i < len(fields):
        status = fields[i]
        if not status:
            i += 1
            continue
        code = status[0]
        if code == "R":
            if i + 2 < len(fields):
                removed.append(fields[i + 1])  # old path
            i += 3
        elif code == "D":
            if i + 1 < len(fields):
                removed.append(fields[i + 1])
            i += 2
        else:
            # Any other status shouldn't appear under --diff-filter=DR; skip its single path.
            i += 2
    return [p for p in removed if p]


def read_tracked_files(root: Path):
    """Yield (path, text|None) for every tracked file. Binary or oversized files yield None."""
    out = _git(["ls-files", "-z"], root)
    for rel in out.split("\0"):
        if not rel:
            continue
        fp = root / rel
        try:
            data = fp.read_bytes()
        except (OSError, ValueError):
            yield rel, None
            continue
        if b"\0" in data[:8192] or len(data) > _MAX_TEXT_BYTES:
            yield rel, None
            continue
        yield rel, data.decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--base-ref",
        default="origin/main",
        help="ref to diff against for removed/renamed paths (default: origin/main)",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help=(
            "auto-remediation (L6): for RENAME cases only, rewrite surviving full-path references "
            "to the old path in-place (old -> new) and print a summary. DELETIONS are reported but "
            "NEVER rewritten (no safe target). A developer convenience — CI never runs --fix; it "
            "stays report-only and fail-closed."
        ),
    )
    args = ap.parse_args(argv)

    try:
        base = merge_base(ROOT, args.base_ref)
        removed = compute_removed_paths(ROOT, base)
        renames = compute_rename_map(ROOT, base)
    except GitError as e:
        # Fail-closed: a gate that cannot compute blast-radius must not pass.
        print(f"no-dangling-path-refs check FAILED (INV-DEP-12): {e}", file=sys.stderr)
        print(
            "  This gate needs full git history to diff HEAD against the merge-base with "
            f"{args.base_ref}. In CI, check out with fetch-depth: 0 (or `git fetch --unshallow`).",
            file=sys.stderr,
        )
        return 2

    if not removed:
        print("OK: no paths deleted or renamed in this PR — nothing to check for dangling refs.")
        return 0

    if args.fix:
        # L6: rewrite the unambiguous rename cases in place, then re-check what remains. Deletions
        # (and any bare-suffix rename refs) are left for a human and still fail the gate.
        tree = dict(read_tracked_files(ROOT))
        changed, summary = plan_fixes(renames, tree)
        for rel, new_text in changed.items():
            (ROOT / rel).write_text(new_text, encoding="utf-8")
            tree[rel] = new_text
        if summary:
            print(f"--fix: auto-remediated {len(changed)} file(s) for {len(renames)} rename(s):")
            for line in summary:
                print(f"  - {line}")
        else:
            print("--fix: no full-path rename references to rewrite.")
        remaining = scan(removed, tree, renames)
        if remaining:
            print("no-dangling-path-refs check FAILED (INV-DEP-12) — remaining after --fix:", file=sys.stderr)
            print(
                "  the following are DELETIONS or ambiguous (bare-suffix) rename refs that --fix "
                "cannot safely rewrite; resolve them by hand:",
                file=sys.stderr,
            )
            for v in remaining:
                print(f"  - {v}", file=sys.stderr)
            return 1
        print("OK: all dangling references were rename cases and have been rewritten in place.")
        return 0

    violations = scan(removed, read_tracked_files(ROOT), renames)
    if violations:
        print("no-dangling-path-refs check FAILED (INV-DEP-12):", file=sys.stderr)
        print(
            f"  {len(removed)} path(s) were removed/renamed; the following tracked files still "
            f"reference an old path that no longer exists:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"OK: {len(removed)} path(s) removed/renamed, and no surviving tracked file references "
        f"any of them by the old path."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
