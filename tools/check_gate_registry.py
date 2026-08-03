#!/usr/bin/env python3
"""Meta-gate: every deploy/resilience gate must PROVE it can fire (never-fired == suspect).

The estate's oldest failure mode is a control that passes because it cannot fail — enforcement
theater. This meta-gate reads `tools/gate_registry.yaml` and fails closed unless every registered
gate demonstrates teeth:

  * pytest gate  -> its tool file and teeth-test exist, and the teeth-test contains at least
    `min_negative_tests` NEGATIVE-case test functions (a test whose name marks a failure it
    expects the gate to catch: fail/missing/dangling/broken/malformed/mismatch/bogus/not_/
    unresolved/fabricated/invalid/absent). A gate with no negative case has never been shown to
    deny anything.
  * workflow gate -> its workflow file and negative fixture exist, and the workflow carries the
    toothless-guard marker (it applies the broken fixture and fails unless the detector fires).

The ratchet: EVERY `tools/verify_*.py` must be either registered under `gates` or explicitly
booked under `known_unproven` (acknowledged debt). A verify tool in neither fails this gate — a
new gate cannot land without proving it can fire or being visibly recorded as debt.

Teeth both ways in tools/tests/test_check_gate_registry.py: the shipped registry passes; a gate
whose teeth-test has no negative case fails; an unregistered verify tool fails.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "tools" / "gate_registry.yaml"

# A test function name signals a negative (failure-expecting) case if it contains one of these.
_NEGATIVE_MARKERS = (
    "fail", "missing", "dangling", "broken", "malformed", "mismatch", "bogus",
    "not_", "unresolved", "fabricated", "invalid", "absent", "reject", "deny", "unmet",
)
_DEF_RE = re.compile(r"^\s*def (test_\w+)", re.MULTILINE)


def negative_test_count(text: str) -> int:
    return sum(
        1 for name in _DEF_RE.findall(text)
        if any(m in name.lower() for m in _NEGATIVE_MARKERS)
    )


def _read(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError) as e:
        return None, f"{type(e).__name__}: {e}"


def check(registry_obj: dict, root: Path) -> list[str]:
    """Return violation strings. Empty == every gate proves it can fire. Fail-closed."""
    problems: list[str] = []
    if not isinstance(registry_obj, dict):
        return ["gate_registry.yaml did not parse to a mapping"]

    gates = registry_obj.get("gates") or []
    known_unproven = registry_obj.get("known_unproven") or []
    registered_tools: set[str] = set()

    for g in gates:
        gid = g.get("id", "<no-id>")
        kind = g.get("kind")
        if kind == "pytest":
            tool = g.get("tool", "")
            teeth = g.get("teeth_test", "")
            minneg = int(g.get("min_negative_tests", 1))
            registered_tools.add(tool)
            if not (root / tool).is_file():
                problems.append(f"{gid}: tool {tool!r} does not exist")
            tt = root / teeth
            if not tt.is_file():
                problems.append(f"{gid}: teeth-test {teeth!r} does not exist — gate has no proof it can fire")
                continue
            text, err = _read(tt)
            if err:
                problems.append(f"{gid}: teeth-test unreadable ({err})")
                continue
            n = negative_test_count(text)
            if n < minneg:
                problems.append(
                    f"{gid}: teeth-test {teeth!r} has {n} negative-case test(s), needs >= {minneg} "
                    f"— an all-green gate proves nothing (never-fired == suspect)"
                )
        elif kind == "workflow":
            wf = g.get("workflow", "")
            fixture = g.get("negative_fixture", "")
            marker = g.get("toothless_guard_marker", "toothless")
            if not (root / wf).is_file():
                problems.append(f"{gid}: workflow {wf!r} does not exist")
            elif marker not in (_read(root / wf)[0] or ""):
                problems.append(f"{gid}: workflow {wf!r} missing toothless-guard marker {marker!r}")
            if fixture and not (root / fixture).is_dir():
                problems.append(f"{gid}: negative fixture {fixture!r} does not exist")
        else:
            problems.append(f"{gid}: unknown gate kind {kind!r}")

    # Ratchet: every verify_*.py must be registered or explicitly booked as debt.
    debt_tools = {d.get("tool", "") for d in known_unproven}
    for vf in sorted((root / "tools").glob("verify_*.py")):
        rel = f"tools/{vf.name}"
        if rel not in registered_tools and rel not in debt_tools:
            problems.append(
                f"{rel}: a verify_*.py gate that is neither registered in gate_registry.yaml with a "
                f"teeth-test nor booked under known_unproven — register it (with proof it can fire) "
                f"or acknowledge it as debt"
            )

    # Debt tools must actually exist (a stale debt entry hides a removed gate).
    for d in known_unproven:
        t = d.get("tool", "")
        if not (root / t).is_file():
            problems.append(f"known_unproven references {t!r} which does not exist — remove the stale debt entry")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default=str(REGISTRY))
    args = ap.parse_args(argv)
    text, err = _read(Path(args.registry))
    if err:
        print(f"gate-registry check FAILED: cannot read {args.registry}: {err}", file=sys.stderr)
        return 1
    try:
        obj = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"gate-registry check FAILED: {args.registry} is not valid YAML: {e}", file=sys.stderr)
        return 1
    problems = check(obj, ROOT)
    if problems:
        print("gate-registry check FAILED — a gate cannot prove it fires (never-fired == suspect):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    gates = obj.get("gates") or []
    debt = obj.get("known_unproven") or []
    print(f"OK: {len(gates)} gate(s) each prove they can fire (registered teeth).")
    if debt:
        print(f"  acknowledged debt (teeth owed): {', '.join(d.get('tool','?') for d in debt)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
