#!/usr/bin/env python3
"""Report git work that exists on NO remote -- i.e. single copies a dead disk erases.

Class D of `docs/architecture/devsecops-retrospective-and-recovery-v0.1.md`:
when a laptop disk hit zero this session it took with it 47+43+33 unpushed
commits and a stash holding the *sole* copy of a sovereign-Gitea manifest.  None
of it was recoverable because none of it existed anywhere but that disk.  The
cure is not heroics after the fact; it is *visibility before* -- a cheap sweep
that makes single-copy work impossible to forget.

This is a LOCAL OPERATOR tool, not a CI gate.  It shells out to `git` and, for
each repository under the given roots, reports four kinds of single-copy work:

  1. repositories with **no remote at all** (every commit is single-copy);
  2. **unpushed commits** -- reachable from a local branch/tag but from no
     remote-tracking ref;
  3. **stashes** -- which never leave the local disk;
  4. **uncommitted changes** in any (linked) worktree.

Honesty about the instrument (this doc's own class G):

* "On no remote" is judged against **remote-tracking refs** (`refs/remotes/*`),
  which can be STALE.  A branch you pushed from another machine may still look
  unpushed here until you fetch.  Pass `--fetch` to refresh first (slower, hits
  the network); without it, results are a safe over-approximation -- it may over-
  report, it will not under-report work that is genuinely only local.
* We never conclude "all clear" from a git command that errored; a repo we
  cannot interrogate is listed as `unknown`, not as safe.

Exit status: 0 iff no single-copy work was found in any scanned repo; 1 if any
was found; 2 on usage error.  As an operator pre-flight ("is it safe to let this
disk sleep?"), non-zero means "push something first".
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOTS = [Path.home() / "dev"]


def git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        cp = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 255, f"<git invocation failed: {exc}>"
    return cp.returncode, (cp.stdout or "").strip()


def find_repos(roots: list[Path], max_depth: int) -> list[Path]:
    """A git repo is a directory whose `.git` exists (dir for a normal clone,
    file for a linked worktree).  We stop descending into a repo once found."""
    seen: set[Path] = set()
    out: list[Path] = []

    def walk(d: Path, depth: int) -> None:
        try:
            resolved = d.resolve()
        except OSError:
            return
        if resolved in seen:
            return
        if (d / ".git").exists():
            seen.add(resolved)
            out.append(d)
            return  # do not descend into a repo's own subtree
        if depth >= max_depth:
            return
        try:
            children = sorted(p for p in d.iterdir() if p.is_dir() and not p.is_symlink())
        except OSError:
            return
        for c in children:
            if c.name in (".git", "node_modules", ".venv", "venv", "__pycache__"):
                continue
            walk(c, depth + 1)

    for r in roots:
        if r.is_dir():
            walk(r, 0)
    return out


class RepoReport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.no_remote = False
        self.unknown: list[str] = []
        self.unpushed: list[str] = []     # short commit lines
        self.total_local_commits = 0      # only meaningful when no_remote
        self.stashes: list[str] = []
        self.dirty: list[str] = []        # "<worktree>: N files"

    @property
    def has_single_copy(self) -> bool:
        return bool(self.no_remote or self.unpushed or self.stashes or self.dirty
                    or (self.no_remote and self.total_local_commits))

    @property
    def any_finding(self) -> bool:
        return self.has_single_copy or bool(self.unknown)


def inspect(repo: Path, do_fetch: bool) -> RepoReport:
    rep = RepoReport(repo)

    rc, remotes = git(repo, "remote")
    if rc != 0:
        rep.unknown.append("could not list remotes")
        return rep
    has_remote = bool(remotes.strip())

    if do_fetch and has_remote:
        git(repo, "fetch", "--all", "--quiet")

    # Stashes -- always single-copy.
    rc, stash = git(repo, "stash", "list")
    if rc == 0 and stash:
        rep.stashes = stash.splitlines()

    # Uncommitted changes, this worktree.
    rc, porc = git(repo, "status", "--porcelain")
    if rc == 0 and porc:
        rep.dirty.append(f"{repo.name}: {len(porc.splitlines())} file(s)")

    # Linked worktrees share this repo's object store but each has its own index
    # and HEAD.  A dirty linked worktree (often parked in /tmp, outside the
    # scanned roots) is single-copy work that would otherwise be invisible.
    rc, wl = git(repo, "worktree", "list", "--porcelain")
    if rc == 0 and wl:
        for line in wl.splitlines():
            if not line.startswith("worktree "):
                continue
            wt = Path(line[len("worktree "):])
            try:
                if wt.resolve() == repo.resolve():
                    continue  # primary worktree already covered above
            except OSError:
                continue
            wrc, wporc = git(wt, "status", "--porcelain")
            if wrc == 0 and wporc:
                rep.dirty.append(f"{wt} (linked worktree): {len(wporc.splitlines())} file(s)")

    if not has_remote:
        rep.no_remote = True
        rc, cnt = git(repo, "rev-list", "--all", "--count")
        if rc == 0 and cnt.isdigit():
            rep.total_local_commits = int(cnt)
        return rep

    # Commits on local branches/tags that no remote-tracking ref contains.
    rc, out = git(repo, "rev-list", "--branches", "--tags", "--not", "--remotes",
                  "--pretty=oneline", "--max-count=200")
    if rc != 0:
        rep.unknown.append("rev-list for unpushed commits failed")
    elif out:
        # --pretty=oneline prints "<sha> <subject>" lines; keep them as-is.
        rep.unpushed = [ln for ln in out.splitlines() if ln.strip()]

    return rep


def render(reports: list[RepoReport], scanned: int) -> None:
    flagged = [r for r in reports if r.any_finding]
    print(f"Scanned {scanned} repo(s); {len(flagged)} with single-copy work or unknown state.\n")
    tot_unpushed = tot_stash = tot_dirty = tot_noremote = 0
    for r in flagged:
        print(f"### {r.path}")
        if r.no_remote:
            tot_noremote += 1
            print(f"  NO REMOTE configured -- all {r.total_local_commits} commit(s) are single-copy")
        if r.unpushed:
            tot_unpushed += len(r.unpushed)
            print(f"  {len(r.unpushed)} unpushed commit(s) (on no remote):")
            for ln in r.unpushed[:8]:
                print(f"    - {ln[:100]}")
            if len(r.unpushed) > 8:
                print(f"    ... and {len(r.unpushed) - 8} more")
        if r.stashes:
            tot_stash += len(r.stashes)
            print(f"  {len(r.stashes)} stash(es) (never leave this disk):")
            for ln in r.stashes[:5]:
                print(f"    - {ln[:100]}")
        if r.dirty:
            for d in r.dirty:
                tot_dirty += 1
                print(f"  uncommitted: {d}")
        for u in r.unknown:
            print(f"  UNKNOWN (not proven safe): {u}")
        print()
    print("TOTALS:")
    print(f"  repos with no remote : {tot_noremote}")
    print(f"  unpushed commits     : {tot_unpushed}")
    print(f"  stashes              : {tot_stash}")
    print(f"  dirty worktrees      : {tot_dirty}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Report git commits/stashes/worktrees that exist on no remote (single-copy work).")
    ap.add_argument("--roots", type=Path, nargs="*", default=DEFAULT_ROOTS,
                    help="directories to scan for repositories (default: ~/dev)")
    ap.add_argument("--max-depth", type=int, default=2,
                    help="how deep under each root to look for repos (default: 2)")
    ap.add_argument("--fetch", action="store_true",
                    help="git fetch --all before judging (accurate but slow; default off)")
    args = ap.parse_args(argv)

    repos = find_repos([Path(r).expanduser() for r in args.roots], args.max_depth)
    reports = [inspect(r, args.fetch) for r in repos]
    render(reports, len(repos))
    return 1 if any(r.any_finding for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
