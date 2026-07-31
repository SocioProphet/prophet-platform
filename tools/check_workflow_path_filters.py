#!/usr/bin/env python3
"""Prove that a path-filtered workflow still runs when its real inputs change.

A `paths:` filter on a validation workflow is a promise: "nothing outside these
globs can affect this check."  A wrong promise is worse than no filter, because
the validator stops running pre-merge and nobody notices — the check is still
green, it is simply never asked.  That is the "declared but unenforced" failure
mode this repo already hunts elsewhere.

So we do not take the promise on trust.  For every workflow that declares
`pull_request.paths`, we read the scripts it actually runs, statically extract
the repository paths those scripts open, and assert each one is matched by the
declared globs.  Add an input directory to a validator without widening its
filter and this check fails.

Deliberately conservative: we only *add* required coverage.  Unparseable
constructs are reported, never silently ignored.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# `ROOT / "contracts" / "svf"` and friends.
PY_JOIN = re.compile(r'ROOT\s*/\s*((?:["\'][^"\']+["\']\s*/\s*)*["\'][^"\']+["\'])')
# `$ROOT/tools/validate-x.sh`
SH_JOIN = re.compile(r'\$(?:\{)?ROOT(?:\})?/([A-Za-z0-9_./*-]+)')
# bare repo-relative paths in a workflow `run:` line or a python literal
BARE = re.compile(r'(?<![\w/.-])((?:tools|tests|specs|contracts|fixtures|apps|infra|libs|releases|src|docs)/[A-Za-z0-9_./*-]+)')


def declared_paths(text: str) -> list[str]:
    """Globs under `pull_request: paths:` — parsed positionally, no yaml dep."""
    m = re.search(r'^on:.*?(?=^\w)', text, re.M | re.S)
    if not m:
        return []
    on = m.group(0)
    pr = re.search(r'^  pull_request:\s*$(.*?)(?=^  \w|\Z)', on, re.M | re.S)
    if not pr:
        return []
    blk = re.search(r'^    paths:\s*$(.*?)(?=^    \w|\Z)', pr.group(1), re.M | re.S)
    if not blk:
        return []
    return [x.strip().strip("'\"") for x in re.findall(r"^\s*-\s*(.+)$", blk.group(1), re.M)]


def has_main_push(text: str) -> bool:
    """An unfiltered push-on-main trigger is the safety net that makes a wrong
    filter degrade to merge-time detection instead of never running at all."""
    m = re.search(r'^on:.*?(?=^\w)', text, re.M | re.S)
    if not m:
        return False
    push = re.search(r'^  push:\s*$(.*?)(?=^  \w|\Z)', m.group(0), re.M | re.S)
    # `paths:` OR `paths-ignore:` under push means the trigger is filtered, not the
    # unfiltered safety net: `paths-ignore` still skips the run for the ignored set,
    # so it cannot be relied on to catch a wrong filter at merge time. `"paths:" in`
    # missed `paths-ignore:` (no `paths:` substring in it), wrongly accepting it.
    if not push or re.search(r'^\s+paths(?:-ignore)?:', push.group(1), re.M):
        return False
    # Match `main` as a whole branch token, not a substring: `maintenance`,
    # `main-release`, `main/foo` and globs like `main.*` are different refs, NOT the
    # unfiltered main-branch safety net. The boundary excludes every ref-name
    # character (`[\w./*+-]`), so only an exact `main` token counts — `(?![\w-])`
    # alone let `/`, `.` and `*` through.
    return re.search(r'(?<![\w./*+-])main(?![\w./*+-])', push.group(1)) is not None


def make_target_scripts(target: str) -> set[str]:
    """`run: make foo` hides the real script in the Makefile recipe.  A checker
    that cannot see through this silently vouches for a filter it never
    examined — so resolve the target rather than skip it."""
    mk = ROOT / "Makefile"
    if not mk.exists():
        return set()
    body = re.search(rf'^{re.escape(target)}:.*?$(.*?)(?=^\S|\Z)',
                     mk.read_text(encoding="utf-8", errors="replace"), re.M | re.S)
    return set(BARE.findall(body.group(1))) if body else set()


def _run_bodies(text: str) -> list[str]:
    """Every `run:` body, INCLUDING multi-line `run: |` / `run: >` block scalars.

    The naive `run:\\s*(.*)` captures only the first physical line, so a script
    invoked on line 2+ of a block scalar is invisible -- and a vouched workflow
    whose real script lives in a `run: |` block would be checked against nothing
    and pass. Block bodies are gathered by indentation: the run-together lines
    more-indented than the `run:` key belong to it.
    """
    bodies: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r'^(\s*)(?:-\s+)?run:\s*(\|[-+]?|>[-+]?)?\s*(.*)$', lines[i])
        if not m:
            i += 1
            continue
        indent, block, inline = m.group(1), m.group(2), m.group(3)
        if not block:
            bodies.append(inline)
            i += 1
            continue
        base = len(indent)
        collected = [inline] if inline else []
        i += 1
        while i < len(lines):
            ln = lines[i]
            if ln.strip() and (len(ln) - len(ln.lstrip())) <= base:
                break
            collected.append(ln)
            i += 1
        bodies.append("\n".join(collected))
    return bodies


def scripts_invoked(text: str) -> set[str]:
    out: set[str] = set()
    for body in _run_bodies(text):
        out.update(BARE.findall(body))
        for target in re.findall(r'\bmake\s+([A-Za-z0-9_.-]+)', body):
            out.update(make_target_scripts(target))
    resolved: set[str] = set()
    for item in out:
        if Path(item).suffix in {".py", ".sh"}:
            resolved.add(item)
            continue
        # `pytest tests/some_dir/` names a directory, not a script — analyse the
        # test modules inside it, or the workflow looks unanalysable and gets
        # wrongly vouched.
        d = ROOT / item.rstrip("/")
        if d.is_dir():
            resolved.update(str(f.relative_to(ROOT)) for f in d.rglob("*.py"))
    return resolved


def inputs_of(script: Path, seen: set[Path] | None = None) -> set[str]:
    """Repo paths a script reads, following shell scripts that call siblings."""
    seen = seen if seen is not None else set()
    if script in seen or not script.exists():
        return set()
    seen.add(script)
    src = script.read_text(encoding="utf-8", errors="replace")
    found: set[str] = set()
    for joined in PY_JOIN.findall(src):
        parts = re.findall(r'["\']([^"\']+)["\']', joined)
        if parts:
            found.add("/".join(parts))
    found.update(SH_JOIN.findall(src))
    found.update(BARE.findall(src))
    for nested in {f for f in found if f.endswith(".sh")}:
        found |= inputs_of(ROOT / nested, seen)
    out = set()
    for f in found:
        if f.startswith(".github") or "/" not in f:
            continue          # bare dir mentions in prose/help text
        if f.split("/")[0] == "build":
            continue          # generated artifact, produced by the job, not an input
        if not (ROOT / f).exists():
            continue          # only vouch for inputs that actually exist today
        out.add(f)
    return out


def covered(path: str, globs: list[str]) -> bool:
    for g in globs:
        g = g.rstrip("/")
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g + "/*"):
            return True
        # `a/**` must cover `a/b/c` — fnmatch's * does not cross separators
        if g.endswith("/**") and (path == g[:-3] or path.startswith(g[:-2])):
            return True
    return False


# Workflows whose filter this repo has actually verified against its inputs.
# Enforced hard.  Everything else is reported as advisory debt — see
# `docs/CI_PATH_FILTER_DEBT.md`.  The list is meant to grow; nothing is meant
# to leave it.
VOUCHED = {
    "brokerage-validation.yml",
    "semantic-projection-contracts.yml",
    "svf-validation.yml",
    "scope-d-hardening-fixtures.yml",
    "workspace-operation-runtime.yml",
    "cloudshell-fog-structural-conformance-v2.yml",
    "cloudshell-fog-structural-conformance-v3.yml",
}


def main() -> int:
    failures: list[str] = []
    advisory: list[str] = []
    checked = 0
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="replace")
        globs = declared_paths(text)
        if not globs:
            continue
        if wf.name == "ci-path-filter-audit.yml":
            # The auditor's own tool and tests mention repo paths as DATA
            # (fixtures, examples in docstrings), not as inputs it reads.
            # Scanning it would report those literals as uncovered forever.
            continue
        checked += 1
        sink = failures if wf.name in VOUCHED else advisory
        if not has_main_push(text):
            sink.append(
                f"{wf.name}: filtered on pull_request but has no unfiltered "
                f"push-on-main trigger — a wrong filter would mean it NEVER runs")
        found_scripts = scripts_invoked(text)
        if wf.name in VOUCHED and not found_scripts:
            failures.append(
                f"{wf.name}: vouched, but no analysable script was found in its "
                f"run: steps — the filter cannot be proven, so it is not vouched")
        for script in found_scripts:
            if not covered(script, globs):
                sink.append(f"{wf.name}: runs {script}, which its paths: filter does not match")
            for dep in inputs_of(ROOT / script):
                if not covered(dep, globs):
                    sink.append(f"{wf.name}: {script} reads {dep}, not matched by paths: filter")

    for f in sorted(set(failures)):
        print(f"FAIL {f}")
    for a in sorted(set(advisory)):
        print(f"debt {a}")
    print(f"\nchecked {checked} path-filtered workflow(s): "
          f"{len(VOUCHED)} vouched, {len(set(failures))} failure(s), "
          f"{len(set(advisory))} pre-existing gap(s) not yet vouched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
