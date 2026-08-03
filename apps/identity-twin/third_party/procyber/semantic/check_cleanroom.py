"""Clean-room guard — fail the build if a framework artifact carries third-party
*expression*, or uses a third-party mark to name something of ours.

What changed and why
--------------------
This guard used to fail on any mention of a third-party metalanguage or its author.
That tested the wrong invariant. A copying claim needs access AND substantial
similarity of protected expression; a name-grep addresses neither. It would pass a
file that transcribed five hundred dictionary entries without ever using the name,
and fail a single truthful sentence of comparison. Worse, suppressing the comparison
forfeits the best evidence of independent creation — a documented provenance register
showing what was known and deliberately not taken is stronger than silence.

Naming a third party in truthful comparison is nominative reference and is lawful.
So the guard now tests the two things that actually carry risk:

  1. EXPRESSION — copied lexicon: dictionary-entry markers (zero tolerance; their
     presence means dictionary structure was transcribed) and coordinate tokens of a
     third-party language above a citation threshold (a handful is a citation, bulk
     is a lexicon).
  2. NAMING — a third-party mark used to name one of OUR artifacts: a filename, a
     schema title/$id, a class or function. That is a trademark concern and survives
     regardless of the copyright analysis.

Prose that names, compares, or criticises a third-party system is explicitly allowed.
The protected expression is the dictionary, the definitions, and the grammar prose —
not the fact that it exists.

Self-exclusion: this file and its test necessarily contain the very patterns they
scan for, so they are never scanned. A scanner that flags itself is broken.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]

#: Markers of a transcribed dictionary. Any occurrence means lexicon structure was
#: copied rather than described, so the tolerance is zero.
DICTIONARY_MARKERS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p) for p in (r"@rootparadigm\b", r"@inflection\b", r"@auxiliary\b",
                            r"@junction\b", r"@node\b")
)

#: Coordinate tokens of a third-party language (punctuation-delimited primitive
#: sequences). A few are a citation supporting a factual claim; many are a lexicon.
COORDINATE_TOKEN = re.compile(r'"[EUASBTOMFI]:[A-Za-z:.\-\'+,]*[.\-\',]"')

#: Above this count in one file, coordinate tokens stop reading as citation.
COORDINATE_CITATION_LIMIT = 8

#: Third-party marks. NOT forbidden in prose — only when used to name our own things.
MARKS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (r"\bieml\b", r"\bintlekt\b", r"\bl[eé]vy\b")
)

#: Positions where a mark would be naming one of OUR artifacts rather than referring
#: to theirs: a schema identity field, or a Python definition.
NAMING_POSITIONS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r'"\$?(?:id|title)"\s*:\s*"[^"]*(?:ieml|intlekt|l[eé]vy)[^"]*"',
        r"^\s*(?:class|def)\s+\w*(?:ieml|intlekt|levy)\w*",
    )
)

#: The framework's own artifacts — the surface the clean-room covers. This file and its
#: test are deliberately absent (self-exclusion).
FRAMEWORK_FILES: Tuple[str, ...] = (
    "procyber/semantic/semantic_algebra.py",
    "procyber/semantic/agent_coordinate_vector.py",
    "procyber/semantic/boundary_transition_actants.py",
    "procyber/semantic/abstraction_level_gate.py",
    "procyber/semantic/intent_address.py",
    "procyber/semantic/spectral_grounding.py",
    "procyber/semantic/market_paradigm.py",
    "procyber/semantic/internal_model.py",
    "procyber/semantic/vsa.py",
    "procyber/semantic/vrf.py",
    "procyber/semantic/interferometry.py",
    "procyber/semantic/twin.py",
    "docs/SEMANTIC_COORDINATE_ALGEBRA.md",
    "docs/SEMANTIC_LAYER_ADJUNCTION.md",
    "docs/SEMANTIC_CONTROL_ARCHITECTURE.md",
    "docs/SEMANTIC_MARKET_PARADIGM.md",
    "docs/SEMANTIC_PRIOR_ART_COMPARISON.md",
    "docs/SEMANTIC_IP_POSITION.md",
    "contracts/AgentCoordinateVector.v0.1.json",
    "contracts/BoundaryTransition.v0.2.json",
    "contracts/examples/agent-coordinate-vector-michael-agent.example.json",
    "contracts/examples/boundary-transition-v0.2-ai-invocation.example.json",
)

_SELF = Path(__file__).name  # never scan self, whatever the caller passes


def scan_paths(paths: Sequence[str]) -> List[Tuple[str, int, str]]:
    """Return (file, line, finding) for every violation. Empty == clean.

    Three findings are possible: a transcribed dictionary marker, coordinate tokens
    past the citation limit, and a third-party mark used to name one of our own
    artifacts. Prose that merely names or compares is not a finding.
    """
    hits: List[Tuple[str, int, str]] = []
    for p in paths:
        path = Path(p)
        if not path.exists() or path.name == _SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        for lineno, line in enumerate(lines, 1):
            for pattern in DICTIONARY_MARKERS:
                match = pattern.search(line)
                if match:
                    hits.append(
                        (str(path), lineno, f"transcribed dictionary marker {match.group(0)!r}")
                    )
            for pattern in NAMING_POSITIONS:
                match = pattern.search(line)
                if match:
                    hits.append(
                        (str(path), lineno, f"third-party mark naming our artifact: {match.group(0)!r}")
                    )

        # Volume test, whole-file: citation is fine, transcription is not.
        tokens = COORDINATE_TOKEN.findall(text)
        if len(tokens) > COORDINATE_CITATION_LIMIT:
            hits.append(
                (
                    str(path),
                    0,
                    f"{len(tokens)} third-party coordinate tokens "
                    f"(limit {COORDINATE_CITATION_LIMIT}) — reads as lexicon, not citation",
                )
            )

        # A mark in the FILENAME names our artifact, whatever the contents say.
        # Separators are normalised first: `_` and `-` are word characters to `\b`,
        # so `ieml_bridge.py` would otherwise slip past the boundary anchors.
        normalised_name = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", " ", path.name)
        for pattern in MARKS:
            match = pattern.search(normalised_name)
            if match:
                hits.append((str(path), 0, f"third-party mark in filename: {match.group(0)!r}"))

    return hits


def framework_files() -> List[str]:
    return [str(REPO / rel) for rel in FRAMEWORK_FILES]


def main(argv: Sequence[str]) -> int:
    targets = list(argv) or framework_files()
    hits = scan_paths(targets)
    if hits:
        print("CLEAN-ROOM VIOLATION — third-party expression or naming in a framework artifact:")
        for f, ln, finding in hits:
            where = f"{f}:{ln}" if ln else f
            print(f"  {where}: {finding}")
        return 1
    print(
        f"clean-room OK: {len(targets)} file(s) scanned — no copied expression, "
        "no third-party naming of our artifacts"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI glue
    raise SystemExit(main(sys.argv[1:]))
