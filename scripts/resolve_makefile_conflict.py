#!/usr/bin/env python3
"""Resolve Makefile merge conflicts when rebasing prophet-platform branches.

Each branch adds one new validate target. Conflicts arise on .PHONY and validate:
lines. Resolution: keep HEAD's accumulated line, add the branch's new target,
and keep both target-definition blocks.
"""
import re
import sys
from pathlib import Path

MAKEFILE = Path(__file__).parent.parent / "Makefile"


def resolve(text: str) -> str:
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("<<<<<<<"):
            out.append(line)
            i += 1
            continue

        # Collect conflict block
        ours, theirs = [], []
        i += 1
        in_theirs = False
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            if lines[i].startswith("======="):
                in_theirs = True
            elif in_theirs:
                theirs.append(lines[i])
            else:
                ours.append(lines[i])
            i += 1
        i += 1  # skip >>>>>>>

        # Determine if this is a header block (.PHONY + validate:) or a target block
        ours_text = "\n".join(ours)
        theirs_text = "\n".join(theirs)

        if ours_text.startswith(".PHONY:") or theirs_text.startswith(".PHONY:"):
            # Header block: merge .PHONY and validate: lines
            merged = _merge_header_block(ours, theirs)
            out.extend(merged)
        else:
            # Target definition block: keep both
            out.extend(ours)
            out.append("")
            out.extend(theirs)

    return "\n".join(out)


def _merge_header_block(ours: list[str], theirs: list[str]) -> list[str]:
    """Merge .PHONY and validate: lines by unioning their target lists."""
    result = []
    # Pair up lines (skip blank lines)
    ours_lines = [l for l in ours if l.strip()]
    theirs_lines = [l for l in theirs if l.strip()]

    # Build a map: prefix -> merged targets
    merged_map: dict[str, list[str]] = {}
    order: list[str] = []

    for group in [ours_lines, theirs_lines]:
        for line in group:
            if ":" in line:
                prefix, rest = line.split(":", 1)
                targets = rest.split()
                key = prefix
                if key not in merged_map:
                    merged_map[key] = []
                    order.append(key)
                for t in targets:
                    if t not in merged_map[key]:
                        merged_map[key].append(t)

    for key in order:
        result.append(f"{key}: {' '.join(merged_map[key])}")
    result.append("")
    return result


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else MAKEFILE
    original = path.read_text()
    if "<<<<<<<" not in original:
        print("No conflicts found.")
        sys.exit(0)
    resolved = resolve(original)
    path.write_text(resolved)
    print(f"Resolved conflicts in {path}")
