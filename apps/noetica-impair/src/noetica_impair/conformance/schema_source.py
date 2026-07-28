"""Where the interpretability schemas come from, and whether they are trustworthy.

Noetica is the integration surface for interpretability evidence, so the schemas are
vendored into ``Noetica/vendor/superconscious/schemas/interpretability/`` with a
sha256-per-file ``manifest.json``. This module resolves them, in order:

  1. ``NOETICA_IMPAIR_SCHEMA_DIR``      -- explicit override (CI, containers)
  2. ``$NOETICA_REPO/vendor/...``        -- the vendored copy in Noetica  <- normal path
  3. ``$SUPERCONSCIOUS_REPO/schemas/...``-- a live upstream checkout
  4. ``None``                            -- nothing found; callers skip rather than fake it

Order matters: the VENDORED copy wins over a live checkout. A dev with a
half-rebased superconscious working tree should not silently change what Noetica
considers valid evidence. Upstream is used to *detect drift*, not to define truth.

Which is the point of ``verify_manifest``. A missing schema is a loud failure -- you
notice immediately. A STALE schema is the dangerous one: it validates happily and
certifies evidence against a contract that has since moved. So the vendored copy
carries hashes, and the conformance suite recomputes them.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_NAMES = (
    "provider-binding",
    "artifact-source-lock",
    "intervention-spec",
    "feature-registry-entry",
)

#: The wider vendored families. The interpretability four define what an INTERVENTION
#: looks like; these define what may be ASSERTED about one and what may be TOUCHED --
#: the auditable/attested layer this rig conforms to rather than reinvents.
FAMILY_SCHEMAS = {
    "lawful-learning": (
        "claim-ledger-entry.v1", "circuit-registry.v1", "forbidden-circuits.v1",
        "alignment-check.v1", "decision-emission.v1", "evidence-status.v1",
        "lawful-learning-invariants.v1",
    ),
    "composition": ("interpretability-harness-tier2-binding.v1",),
}

VENDOR_SUBPATH = Path("vendor") / "superconscious" / "schemas" / "interpretability"
UPSTREAM_SUBPATH = Path("schemas") / "interpretability"


def _candidate_dirs() -> list[tuple[str, Path]]:
    home = Path.home()
    out: list[tuple[str, Path]] = []

    override = os.environ.get("NOETICA_IMPAIR_SCHEMA_DIR")
    if override:
        out.append(("env-override", Path(override)))

    noetica = Path(os.environ.get("NOETICA_REPO", home / "dev" / "Noetica"))
    out.append(("noetica-vendored", noetica / VENDOR_SUBPATH))

    sc = Path(os.environ.get("SUPERCONSCIOUS_REPO", home / "dev" / "superconscious"))
    out.append(("superconscious-upstream", sc / UPSTREAM_SUBPATH))
    return out


@dataclass
class SchemaSource:
    origin: str
    path: Path
    manifest: dict | None = None

    @property
    def is_vendored(self) -> bool:
        return self.manifest is not None

    def schema_file(self, name: str) -> Path:
        return self.path / f"{name}.v0.json"

    def load(self, name: str) -> dict:
        return json.loads(self.schema_file(name).read_text())

    def describe(self) -> dict:
        d = {"origin": self.origin, "path": str(self.path), "vendored": self.is_vendored}
        if self.manifest:
            d["upstream_commit"] = self.manifest.get("upstream_commit")
        return d


def resolve() -> SchemaSource | None:
    """First candidate that actually holds every schema. None if nowhere does."""
    for origin, path in _candidate_dirs():
        if not path.is_dir():
            continue
        if not all((path / f"{n}.v0.json").is_file() for n in SCHEMA_NAMES):
            continue
        manifest = None
        mpath = path / "manifest.json"
        if mpath.is_file():
            try:
                manifest = json.loads(mpath.read_text())
            except json.JSONDecodeError:
                manifest = None
        return SchemaSource(origin=origin, path=path, manifest=manifest)
    return None


@dataclass
class IntegrityReport:
    ok: bool
    checked: int = 0
    mismatched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unmanifested: list[str] = field(default_factory=list)
    detail: str = ""

    def __bool__(self) -> bool:
        return self.ok


def verify_manifest(src: SchemaSource) -> IntegrityReport:
    """Recompute every sha256 against the vendored manifest."""
    if src.manifest is None:
        return IntegrityReport(ok=True, detail=f"{src.origin} carries no manifest; nothing to verify")

    files = src.manifest.get("files", {})
    rep = IntegrityReport(ok=True)
    for name in SCHEMA_NAMES:
        fname = f"{name}.v0.json"
        p = src.path / fname
        if not p.is_file():
            rep.missing.append(fname)
            continue
        entry = files.get(fname)
        if entry is None:
            rep.unmanifested.append(fname)
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        rep.checked += 1
        if actual != entry.get("sha256"):
            rep.mismatched.append(f"{fname} (manifest {entry.get('sha256', '')[:12]} != actual {actual[:12]})")

    rep.ok = not (rep.mismatched or rep.missing or rep.unmanifested)
    rep.detail = (
        f"{rep.checked} schema(s) match the vendored manifest "
        f"(upstream {str(src.manifest.get('upstream_commit'))[:12]})"
        if rep.ok else
        "vendored schemas do not match their manifest: "
        + "; ".join(rep.mismatched + [f"missing {m}" for m in rep.missing]
                    + [f"unmanifested {u}" for u in rep.unmanifested])
    )
    return rep


def family_schema(family: str, name: str) -> dict | None:
    """Load a schema from a wider vendored family, if the vendored tree has it.

    Returns None rather than raising: a checkout that predates the lawful-learning
    vendoring should skip those conformance tests, not fail them.
    """
    src = resolve()
    if src is None:
        return None
    # families sit beside the interpretability dir
    path = src.path.parent / family / f"{name}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def upstream_dir() -> Path | None:
    """A live superconscious checkout, if present -- used ONLY for drift detection."""
    sc = Path(os.environ.get("SUPERCONSCIOUS_REPO", Path.home() / "dev" / "superconscious"))
    p = sc / UPSTREAM_SUBPATH
    return p if p.is_dir() else None


def drift_against_upstream(src: SchemaSource) -> IntegrityReport:
    """Compare the vendored copy byte-for-byte with a live upstream checkout.

    This is the check that catches the dangerous case: a vendored schema that is
    internally consistent (its manifest matches its own bytes) but has fallen behind
    the contract it claims to represent.
    """
    up = upstream_dir()
    if up is None or up == src.path:
        return IntegrityReport(ok=True, detail="no separate upstream checkout; drift not checkable")

    rep = IntegrityReport(ok=True)
    for name in SCHEMA_NAMES:
        fname = f"{name}.v0.json"
        a, b = src.path / fname, up / fname
        if not b.is_file():
            rep.missing.append(f"upstream {fname}")
            continue
        rep.checked += 1
        if hashlib.sha256(a.read_bytes()).hexdigest() != hashlib.sha256(b.read_bytes()).hexdigest():
            rep.mismatched.append(fname)

    rep.ok = not (rep.mismatched or rep.missing)
    rep.detail = (
        f"vendored copy is byte-identical to upstream ({rep.checked} schemas)"
        if rep.ok else
        "VENDORED SCHEMAS HAVE DRIFTED from upstream superconscious: "
        + ", ".join(rep.mismatched + rep.missing)
        + " -- re-vendor and regenerate manifest.json before trusting any conformance result"
    )
    return rep
