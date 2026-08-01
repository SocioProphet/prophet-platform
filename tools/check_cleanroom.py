"""Clean-room guard — fail the build if a framework artifact names a third-party
metalanguage or its author.

The clean-room posture ("take the algebra, leave the lexicon; keep the comparison in
the internal register, never in this repo") was, until now, a prose promise. A control
that is only asserted is not a control. This mechanizes it: run it in CI over the
framework's own files and it exits non-zero on any leak.

Self-exclusion: this file and its test necessarily contain the forbidden tokens (the
patterns they scan for, and the fixtures that prove they bite), so they are never
scanned. A scanner that flags itself is broken — see the estate rule that a
self-validating checker must exclude itself.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]

#: Third-party marks/systems that must not appear in shipped framework artifacts. The
#: algebra is an unprotectable system traced to public-domain sources; naming a specific
#: third-party metalanguage in the repo establishes access with no offsetting benefit.
FORBIDDEN: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (r"\bieml\b", r"\bintlekt\b", r"\bl[eé]vy\b")
)

#: The framework's own artifacts — the surface the clean-room covers. This file and its
#: test are deliberately absent (self-exclusion).
FRAMEWORK_FILES: Tuple[str, ...] = (
    "tools/semantic_algebra.py",
    "tools/agent_coordinate_vector.py",
    "tools/boundary_transition_actants.py",
    "tools/abstraction_level_gate.py",
    "tools/intent_address.py",
    "tools/spectral_grounding.py",
    "docs/SEMANTIC_COORDINATE_ALGEBRA.md",
    "docs/SEMANTIC_LAYER_ADJUNCTION.md",
    "contracts/AgentCoordinateVector.v0.1.json",
    "contracts/BoundaryTransition.v0.2.json",
    "contracts/examples/agent-coordinate-vector-michael-agent.example.json",
    "contracts/examples/boundary-transition-v0.2-ai-invocation.example.json",
)

_SELF = Path(__file__).name  # never scan self, whatever the caller passes


def scan_paths(paths: Sequence[str]) -> List[Tuple[str, int, str]]:
    """Return (file, line, token) for every forbidden hit. Empty == clean."""
    hits: List[Tuple[str, int, str]] = []
    for p in paths:
        path = Path(p)
        if not path.exists() or path.name == _SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in FORBIDDEN:
                match = pattern.search(line)
                if match:
                    hits.append((str(path), lineno, match.group(0)))
    return hits


def framework_files() -> List[str]:
    return [str(REPO / rel) for rel in FRAMEWORK_FILES]


def main(argv: Sequence[str]) -> int:
    targets = list(argv) or framework_files()
    hits = scan_paths(targets)
    if hits:
        print("CLEAN-ROOM VIOLATION — third-party mark in a framework artifact:")
        for f, ln, tok in hits:
            print(f"  {f}:{ln}: {tok!r}")
        return 1
    print(f"clean-room OK: {len(targets)} file(s) scanned, no third-party marks")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI glue
    raise SystemExit(main(sys.argv[1:]))
