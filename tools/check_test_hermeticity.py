#!/usr/bin/env python3
"""Fail if importable code writes under the operator's real $HOME without a redirect.

Class B of `docs/architecture/devsecops-retrospective-and-recovery-v0.1.md`:
this session an agent-machine test suite wrote through modules that resolved
paths under the *real* `~/.noetica` and destroyed the operator's live A2A trust
ledger -- unrecoverably -- plus 921 residue directories.  The test "passed".
The defect was not the assertion; it was that a test-reachable module computed a
**write** path under the real HOME, so running the test mutated the operator's
machine.  PR #585 fixed the specific case in Noetica `lib/`; this generalises the
pattern into a reusable static gate.

What it flags: a filesystem WRITE (`open(..., 'w'|'a'|'x')`, `write_text`,
`write_bytes`, `mkdir`, `makedirs`, `touch`, `Path.open('w')`, `sqlite3.connect`,
`shutil.copy*/move` destination) whose target path is derived from the real HOME
(`Path.home()`, `os.path.expanduser('~...')`, `os.environ['HOME']`, a `~/` literal)
**and is not redirectable** through an environment variable.

What it deliberately allows -- the redirectable idiom already used across the
estate, which is what makes a test hermetic:

    DB = Path(os.environ.get("PROMETHEUSD_DB", Path.home() / ".noetica" / "x.db"))

Here a hermetic test sets `PROMETHEUSD_DB` to a tmp path and the HOME default is
never taken.  Because the write path flows through `os.environ.get(KEY, ...)`
(KEY != HOME), we treat it as safe and prune it.  A raw `Path.home() / ...` with
no such indirection is the violation.

Estate-generic vs per-repo (an explicit answer, per the task):

* The **mechanism** -- "a write sink fed by a non-redirectable HOME-derived
  path" -- is fully estate-generic; this file carries no Noetica-specific rule.
* The **policy** -- *which* HOME subdirectories count as sacred operator state
  (`~/.noetica`, `~/.config/...`, `~/.ssh`) -- is per-repo.  v0.1 takes the
  strict stance that ANY non-redirectable write under real HOME is a violation
  (the safest default); `--allow-subpath` can whitelist specific dirs a repo
  has decided are legitimately operator-scoped.

Honesty about altitude (this doc's own class G):

* This is a STATIC over-approximation of "test-reachable": it flags the pattern
  anywhere in the scanned source, without proving a specific test imports it.
  True import-graph reachability from each test is scoped as a later wave in the
  retrospective doc -- it is more engineering than this cheap guard.
* A file we cannot parse is reported (visible), never silently treated as clean.
* Non-constant `open` modes and dynamically-built paths are conservatively NOT
  flagged (we prefer a missed edge over a false alarm that gets the gate muted);
  this limitation is stated, not hidden.

Exit status: 0 iff no violations; 1 if any; 2 on usage error.

Prove-it-fires: `tools/selftest_check_test_hermeticity.py` plants a raw-HOME
write (must go RED) and the env-redirectable + tmp forms (must stay GREEN).
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN = ["tools", "apps", "libs", "src", "services", "packages"]

# Pure Path-method write sinks: the path is the *receiver* (`p.write_text(...)`).
# `mkdir`/`makedirs` are handled separately because `os.makedirs(path)` /
# `os.mkdir(path)` take the path as an *argument*, not a receiver.
WRITE_ATTR_SINKS = {"write_text", "write_bytes", "touch"}
SHUTIL_WRITE = {"copy", "copy2", "copyfile", "copytree", "move"}
WRITE_OPEN_CHARS = set("wax+")


# --------------------------------------------------------------------------- #
# Home-derivation and redirect detection
# --------------------------------------------------------------------------- #
def _attr_chain(node: ast.AST) -> str:
    """Dotted name for Attribute/Name chains, e.g. os.path.expanduser."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _const_str(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def is_safe_env_getter(node: ast.AST) -> bool:
    """os.environ.get(KEY, ...) or os.getenv(KEY, ...) with KEY != 'HOME' -> the
    value is redirectable by setting KEY, so the subtree is hermetic-capable."""
    if not isinstance(node, ast.Call):
        return False
    name = _attr_chain(node.func)
    if not (name.endswith("environ.get") or name.endswith("os.getenv") or name == "getenv"):
        return False
    if not node.args:
        return False
    key = _const_str(node.args[0])
    # Unknown/dynamic key: still redirectable in principle; treat as safe.
    return key != "HOME"


def is_home_derivation(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        name = _attr_chain(node.func)
        # `Path.home()` / `pathlib.Path.home()`: zero-arg .home() on a Path receiver.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "home" and not node.args:
            recv = _attr_chain(node.func.value)
            if recv == "Path" or recv.endswith(".Path") or recv == "pathlib":
                return True
        if name.endswith("expanduser"):
            s = _const_str(node.args[0]) if node.args else None
            if s is not None and s.startswith("~"):
                return True
        # os.environ.get('HOME') / os.getenv('HOME')
        if (name.endswith("environ.get") or name.endswith("getenv") or name == "getenv") and node.args:
            if _const_str(node.args[0]) == "HOME":
                return True
    if isinstance(node, ast.Subscript):
        # os.environ['HOME']
        if _attr_chain(node.value).endswith("environ"):
            key = _const_str(node.slice)
            if key == "HOME":
                return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value == "~" or node.value.startswith("~/"):
            return True
    return False


def subtree_has_raw_home(node: ast.AST) -> bool:
    """True if the expression contains a HOME-derivation not shielded by a safe
    env getter.  We prune at safe env getters so their HOME *default* is ignored."""
    if is_safe_env_getter(node):
        return False
    if is_home_derivation(node):
        return True
    for child in ast.iter_child_nodes(node):
        if subtree_has_raw_home(child):
            return True
    return False


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #
class Violation:
    __slots__ = ("path", "line", "sink", "detail")

    def __init__(self, path: str, line: int, sink: str, detail: str) -> None:
        self.path, self.line, self.sink, self.detail = path, line, sink, detail


def collect_home_bound_names(tree: ast.AST) -> set[str]:
    """Names assigned a value that carries a raw HOME-derivation.
    `_DB = Path.home() / '.noetica' / 'x.db'` -> {'_DB'}."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and subtree_has_raw_home(node.value):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and node.value is not None \
                and subtree_has_raw_home(node.value) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def references_home_bound(node: ast.AST, home_names: set[str]) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in home_names:
            return True
    return False


def target_is_home(node: ast.AST, home_names: set[str]) -> bool:
    return subtree_has_raw_home(node) or references_home_bound(node, home_names)


def _open_is_write(call: ast.Call) -> bool:
    mode: str | None = None
    if len(call.args) >= 2:
        mode = _const_str(call.args[1])
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = _const_str(kw.value)
    if mode is None:
        return False  # default 'r' or dynamic; conservatively not a write sink
    return any(c in WRITE_OPEN_CHARS for c in mode)


def scan_tree(path: str, tree: ast.AST) -> list[Violation]:
    home_names = collect_home_bound_names(tree)
    out: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        line = getattr(node, "lineno", 0)

        # builtin open(path, mode) with a write mode
        if isinstance(func, ast.Name) and func.id == "open" and node.args:
            if _open_is_write(node) and target_is_home(node.args[0], home_names):
                out.append(Violation(path, line, "open(w)", "write path derived from real $HOME"))
            continue

        if isinstance(func, ast.Attribute):
            attr = func.attr
            full = _attr_chain(func)
            recv_chain = _attr_chain(func.value)
            recv_is_os = recv_chain == "os" or recv_chain.endswith(".os") or recv_chain == "os.path"

            # os.makedirs(path) / os.mkdir(path) -- path is the ARGUMENT
            if attr in ("makedirs", "mkdir") and recv_is_os:
                if node.args and target_is_home(node.args[0], home_names):
                    out.append(Violation(path, line, f"os.{attr}()", "dir path derived from real $HOME"))
                continue
            # p.write_text(...) / p.write_bytes(...) / p.touch() / p.mkdir() -- RECEIVER is the path
            if attr in WRITE_ATTR_SINKS or attr == "mkdir":
                if target_is_home(func.value, home_names):
                    out.append(Violation(path, line, f".{attr}()", "receiver path derived from real $HOME"))
                continue
            # Path(...).open('w')
            if attr == "open":
                if _open_is_write(node) and target_is_home(func.value, home_names):
                    out.append(Violation(path, line, "Path.open(w)", "receiver path derived from real $HOME"))
                continue
            # sqlite3.connect(path) creates the file
            if full.endswith("sqlite3.connect"):
                if node.args and target_is_home(node.args[0], home_names):
                    out.append(Violation(path, line, "sqlite3.connect()", "db path derived from real $HOME"))
                continue
            # shutil.copy*/move(src, dst) -> dst is the write
            if attr in SHUTIL_WRITE and full.endswith(f"shutil.{attr}"):
                if len(node.args) >= 2 and target_is_home(node.args[1], home_names):
                    out.append(Violation(path, line, f"shutil.{attr}()", "destination derived from real $HOME"))
                continue
    return out


def iter_python_files(base: Path, scan_dirs: list[str], exclude: set[str]) -> list[Path]:
    files: list[Path] = []
    roots = [base / d for d in scan_dirs] if scan_dirs else [base]
    for r in roots:
        if not r.exists():
            continue
        stack = [r]
        while stack:
            d = stack.pop()
            try:
                entries = list(d.iterdir())
            except OSError:
                continue
            for p in entries:
                if p.is_symlink():
                    continue
                if p.is_dir():
                    if p.name in exclude:
                        continue
                    stack.append(p)
                elif p.is_file() and p.suffix == ".py":
                    files.append(p)
    return sorted(set(files))


def run(base: Path, scan_dirs: list[str], as_json: bool, exclude: set[str]) -> int:
    files = iter_python_files(base, scan_dirs, exclude)
    violations: list[Violation] = []
    unparsed: list[str] = []
    for f in files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except (OSError, SyntaxError) as exc:
            unparsed.append(f"{f}: {exc.__class__.__name__}")
            continue
        rel = str(f.relative_to(base)) if str(f).startswith(str(base)) else str(f)
        violations.extend(scan_tree(rel, tree))

    if as_json:
        import json
        print(json.dumps({
            "ok": not violations,
            "scanned_files": len(files),
            "violations": [{"path": v.path, "line": v.line, "sink": v.sink, "detail": v.detail} for v in violations],
            "unparsed": unparsed,
        }, indent=2))
        return 1 if violations else 0

    print(f"Scanned {len(files)} python file(s) under {base}")
    if unparsed:
        print(f"  (could not parse {len(unparsed)} file(s) -- reported, not assumed clean):")
        for u in unparsed[:20]:
            print(f"    ? {u}")
    if not violations:
        print("RESULT: PASS -- no non-redirectable writes under real $HOME")
        return 0
    print(f"\nVIOLATIONS ({len(violations)}) -- tests reaching these mutate the operator's real HOME:")
    for v in violations:
        print(f"  {v.path}:{v.line}  {v.sink}  -- {v.detail}")
    print("\nFix: route the path through os.environ.get(KEY, <default>) so a hermetic")
    print("test can redirect KEY to a tmp dir; or write under a tmp/base-dir argument.")
    print("RESULT: FAIL")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail if importable code writes under real $HOME without an env redirect.")
    ap.add_argument("--base", type=Path, default=ROOT, help="repo root to scan (default: this repo)")
    ap.add_argument("--scan", nargs="*", default=None,
                    help=f"subdirs to scan (default: {DEFAULT_SCAN} that exist)")
    ap.add_argument("--exclude", nargs="*", default=[".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"],
                    help="directory names to skip")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    scan_dirs = args.scan if args.scan is not None else DEFAULT_SCAN
    return run(args.base, scan_dirs, args.json, set(args.exclude))


if __name__ == "__main__":
    raise SystemExit(main())
