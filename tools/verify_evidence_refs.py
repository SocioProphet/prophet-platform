#!/usr/bin/env python3
"""Evidence-reference verification (INV-DEP-13): every reference a release/evidence artifact
makes to another repo artifact must RESOLVE to a real, well-formed file — not a string that
merely LOOKS right.

The estate's oldest ghost is a claim that passes schema validation but resolves to nothing: a
fabricated `evidence://` URI that "validated" (agent-registry #56), a placeholder digest that
rendered green. Schema-shape is necessary but never sufficient — the same "looks fine, fails on
use" class the deploy gates close for cluster refs (INV-DEP-9/10) and repo-path refs (INV-DEP-12),
here lifted to EVIDENCE artifacts in the release surface. A manifest may say
`"lock": "releases/images/search-orchestrator.image-lock.json"` or claim
`"bundle_digest": "sha256:…"`; this gate makes each such claim PROVE itself against the repo.

Scope (default): the release-surface artifacts under `releases/` —
  * releases/manifests/*.json
  * releases/evidence/*.json
  * releases/images/*image-lock*.json
The top-level `releases/*.release.json` consumer descriptors are deliberately NOT in the default
set: they are draft, consumer-side, and reference OTHER repos / PRs / not-yet-present runtime
targets by design (e.g. sourceos.osbuild-v1.release.json). Pass explicit paths to check them.

What counts as a reference, and how each is resolved (deny-closed):

  * REPO-PATH ref — a whitespace-free string with >= 2 `/`-segments whose FIRST segment is a real
    top-level entry of THIS repo (releases/, tools/, infra/, bundles/, conformance/, docs/,
    services/, apps/, contracts/, .github/, …). That is precisely "a path rooted at the repo".
    The target MUST exist; a `.json`/`.yaml`/`.yml` target MUST also parse. A missing or malformed
    target FAILS with the manifest, field (JSON path), and unresolved target. Prose that merely
    contains a slash ("builds/publishes GHCR image"), a registry ref
    (`us-central1-docker.pkg.dev/…`, excluded by whitespace/`@sha256:`), and an org/repo
    (`SocioProphet/prophet-platform`, first segment not a top-level entry) are NOT repo-path refs
    and are left alone.

  * URI ref — an `evidence://…` or `file://…` string. The scheme is stripped and the remainder
    resolved as a repo-relative path (existence + parse). An `evidence://` URI that resolves to
    nothing is the exact agent-registry #56 ghost — it FAILS here rather than validating green.

  * DIGEST-EVIDENCE ref — a `<name>_digest` field whose sibling `<name>` field is a repo-path ref
    to an existing file (e.g. `bundle_digest` ↔ `bundle`, `rulepack_digest` ↔ `rulepack`). The
    claim is verified by content: sha256(the referenced file) MUST equal the claimed digest. A
    placeholder-that-looks-real, a truncated digest, or a digest that no longer matches the file it
    names FAILS. (Image digests — `digest`, `source_content_digest`, `pinned_ref` — are NOT
    file-content digests: they name registry blobs, have no sibling repo file, and are covered by
    INV-DEP-6/7, so this gate does not touch them.)

  * PLACEHOLDER — a string carrying REPLACE / PLACEHOLDER (case-insensitive) is an explicit
    unfilled slot in an `*.example.*` / `*.template.*` artifact, not a live claim; it is skipped.
    The ghost is a placeholder shaped like a REAL ref (a 64-hex digest, an `evidence://` URI), not
    an obvious `REPLACE_WITH_…` slot — so those still fail, while templates stay green.

Deny-closed on ambiguity: a string that HAS a resolvable ref shape (repo-path rooted at a real
top-level entry, or an evidence/file URI) is resolved, and FAILS if it points at a repo artifact
that does not exist. A string with no ref shape (prose, an id, an external repo/registry ref) is
not treated as a claim. The classification is filesystem-independent via the `Resolver` seam, so
the exact "is this a repo path / does it exist / does it parse / what is its sha256" boundary is
mockable in tests.

Teeth both ways: tools/tests/test_verify_evidence_refs.py drives scan(manifest_obj, resolver) with
a fake resolver — a ref that resolves passes; a ref to a missing file fails; a digest-evidence
claim that mismatches fails; an evidence:// URI that resolves to nothing fails; a placeholder is
skipped — and asserts the SHIPPED releases/ artifacts pass end-to-end against the real filesystem.

Runs pure-filesystem: no kubectl, no cluster, no network. Wired into `make evidence-refs-check`
(the validate-target-diagnostics matrix) and `tools/run_preflight.py` (fast + hermetic).
"""
from __future__ import annotations

import argparse
import glob as globmod
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Protocol

import yaml

ROOT = Path(__file__).resolve().parents[1]

# The release-surface artifacts checked by default. See the module docstring for why the top-level
# releases/*.release.json descriptors are excluded (draft, consumer-side, cross-repo by design).
DEFAULT_ARTIFACT_GLOBS = [
    "releases/manifests/*.json",
    "releases/evidence/*.json",
    "releases/images/*image-lock*.json",
]

# A string carrying either marker (case-insensitive) is an explicit unfilled slot in a template /
# example artifact, not a live reference — never a fabricated-but-real-looking claim.
PLACEHOLDER_MARKERS = ("REPLACE", "PLACEHOLDER")

# Schemes whose target is a repo-relative artifact. `evidence://` is the estate's canonical
# evidence-URI form (the agent-registry #56 ghost); `file://` is the generic local form.
REF_SCHEMES = ("evidence://", "file://")

_STRUCTURED_SUFFIXES = (".json", ".yaml", ".yml")
_HEX = set("0123456789abcdef")


def _is_placeholder(s: str) -> bool:
    up = s.upper()
    return any(m in up for m in PLACEHOLDER_MARKERS)


def _well_formed_sha256(s: str) -> bool:
    """A real content digest is `sha256:` + exactly 64 lowercase hex chars."""
    if not s.startswith("sha256:"):
        return False
    hexpart = s[len("sha256:"):]
    return len(hexpart) == 64 and all(c in _HEX for c in hexpart)


# --------------------------------------------------------------------------------------------
# The Resolver seam — the ONLY filesystem boundary. scan() is pure logic over it, so tests drive
# scan(manifest_obj, resolver) with an in-memory fake and never touch disk.
# --------------------------------------------------------------------------------------------
class Resolver(Protocol):
    def is_top_level(self, segment: str) -> bool:
        """Is `segment` a real top-level entry of the repo (so a path starting with it is
        rooted at the repo)?"""

    def exists(self, relpath: str) -> bool:
        """Does the repo-relative path resolve to a real file or directory?"""

    def parse_error(self, relpath: str) -> str | None:
        """None if the target parses (or is not a structured .json/.yaml file); otherwise a
        short reason it is malformed. Only consulted when exists(relpath) is True."""

    def sha256(self, relpath: str) -> str | None:
        """`sha256:<hex>` of the file's bytes, or None if it cannot be read. Only consulted for
        digest-evidence verification of an existing file."""


def _is_repo_path(s: str, resolver: Resolver) -> bool:
    """True iff `s` is a reference rooted at this repo: no whitespace, >= 2 `/`-segments, and a
    first segment that is a real top-level entry. Excludes scheme URIs (handled separately),
    registry pins (`@sha256:`), prose (whitespace), and org/repo or registry hosts (first segment
    not a top-level entry)."""
    if not s or any(ch.isspace() for ch in s):
        return False
    if "://" in s or "@sha256:" in s:
        return False
    parts = s.split("/")
    if len(parts) < 2 or not all(parts):
        return False
    return resolver.is_top_level(parts[0])


def _uri_target(s: str) -> str | None:
    """The repo-relative path a recognised evidence/file URI points at, or None if `s` is not
    such a URI. Strips the scheme and any leading slashes (file:///a/b -> a/b)."""
    for scheme in REF_SCHEMES:
        if s.startswith(scheme):
            return s[len(scheme):].lstrip("/")
    return None


def _check_target(target: str, s: str, jp: str, where: str, resolver: Resolver, out: list[str], kind: str) -> None:
    """Existence + parse for a resolved reference target."""
    if not resolver.exists(target):
        out.append(
            f"{where}: {jp} = {s!r} is {kind} to '{target}', but no such artifact exists in the "
            f"repo — the reference resolves to nothing (a claim that looks right but points at "
            f"nothing; update or remove it)."
        )
        return
    perr = resolver.parse_error(target)
    if perr is not None:
        out.append(
            f"{where}: {jp} = {s!r} references '{target}', which exists but {perr} — a malformed "
            f"artifact cannot back the claim."
        )


def _check_string_ref(s: str, jp: str, where: str, resolver: Resolver, out: list[str]) -> None:
    if _is_placeholder(s):
        return  # explicit unfilled slot in a template/example — not a live claim
    uri_target = _uri_target(s)
    if uri_target is not None:
        _check_target(uri_target, s, jp, where, resolver, out, kind="an evidence/file URI")
        return
    if _is_repo_path(s, resolver):
        _check_target(s, s, jp, where, resolver, out, kind="a repo-path reference")


def _check_digest_evidence(base_path: str, digest_value: str, jp: str, where: str, resolver: Resolver, out: list[str]) -> None:
    """A `<name>_digest` claim whose sibling `<name>` names an existing repo file must equal
    sha256(that file)."""
    if _is_placeholder(digest_value):
        return
    if not _is_repo_path(base_path, resolver) or not resolver.exists(base_path):
        # The sibling path is not a resolvable repo file (or is missing — the string-ref pass on
        # the sibling already reports a missing file); nothing to verify by content here.
        return
    if not _well_formed_sha256(digest_value):
        out.append(
            f"{where}: {jp} = {digest_value!r} claims a digest for '{base_path}' that is not a "
            f"well-formed sha256:<64 hex> — a digest that cannot even be parsed cannot be proven "
            f"against the file it names."
        )
        return
    actual = resolver.sha256(base_path)
    if actual is None:
        out.append(
            f"{where}: {jp} claims a digest for '{base_path}', but that file cannot be read to "
            f"verify it."
        )
        return
    if actual != digest_value:
        out.append(
            f"{where}: {jp} claims {digest_value!r} for '{base_path}', but its actual content "
            f"digest is {actual!r} — the digest-evidence no longer matches the artifact it names "
            f"(stale or fabricated)."
        )


def _walk(obj: Any, jp: str, where: str, resolver: Resolver, out: list[str]) -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            # Digest-evidence pairing: `<name>_digest` verified against its sibling `<name>` file.
            if isinstance(key, str) and key.endswith("_digest"):
                base_key = key[: -len("_digest")]
                base_val = obj.get(base_key)
                if isinstance(val, str) and isinstance(base_val, str):
                    _check_digest_evidence(base_val, val, f"{jp}.{key}", where, resolver, out)
        for key, val in obj.items():
            _walk(val, f"{jp}.{key}", where, resolver, out)
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            _walk(val, f"{jp}[{i}]", where, resolver, out)
    elif isinstance(obj, str):
        _check_string_ref(obj, jp or "<root>", where, resolver, out)


def scan(manifest_obj: Any, resolver: Resolver, where: str = "<manifest>") -> list[str]:
    """Return human-readable violation strings for every unresolved reference in one already-parsed
    manifest object. Pure over the `Resolver` seam — the test entrypoint."""
    out: list[str] = []
    _walk(manifest_obj, "", where, resolver, out)
    return out


# --------------------------------------------------------------------------------------------
# Filesystem Resolver + CLI plumbing — a thin wrapper around scan().
# --------------------------------------------------------------------------------------------
class FsResolver:
    """The real filesystem boundary for scan(). Confines every lookup to the repo root."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._top = {p.name for p in self.root.iterdir()}

    def is_top_level(self, segment: str) -> bool:
        return segment in self._top

    def _safe_path(self, relpath: str) -> Path | None:
        p = (self.root / relpath).resolve()
        if p == self.root or self.root in p.parents:
            return p
        return None  # a '..' escape out of the repo is never a resolvable repo artifact

    def exists(self, relpath: str) -> bool:
        p = self._safe_path(relpath)
        return p is not None and p.exists()

    def parse_error(self, relpath: str) -> str | None:
        low = relpath.lower()
        p = self._safe_path(relpath)
        if p is None or not p.is_file():
            return None  # directories and non-files carry no parse obligation
        if low.endswith(".json"):
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                return f"is not valid JSON ({type(e).__name__})"
            return None
        if low.endswith((".yaml", ".yml")):
            try:
                # safe_load_all: k8s manifests are legitimately multi-document (`---`); the
                # generator is lazy, so force it with list() to surface any parse error.
                list(yaml.safe_load_all(p.read_text(encoding="utf-8")))
            except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
                return f"is not valid YAML ({type(e).__name__})"
            return None
        return None

    def sha256(self, relpath: str) -> str | None:
        p = self._safe_path(relpath)
        if p is None:
            return None
        try:
            return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            return None


def resolve_artifacts(root: Path, patterns: list[str]) -> list[Path]:
    seen: dict[str, Path] = {}
    for pat in patterns:
        for m in sorted(globmod.glob(str(root / pat))):
            seen.setdefault(m, Path(m))
    return list(seen.values())


def check_artifacts(root: Path, patterns: list[str]) -> tuple[int, list[str]]:
    """Load + scan every artifact. Returns (n_checked, violations). A file that will not parse is
    itself a fail-closed violation — an evidence artifact we cannot read cannot be certified."""
    resolver = FsResolver(root)
    artifacts = resolve_artifacts(root, patterns)
    violations: list[str] = []
    for path in artifacts:
        rel = str(path.relative_to(root)) if path.is_absolute() and root in path.parents else str(path)
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            violations.append(f"{rel}: cannot parse the artifact itself ({type(e).__name__}); a release artifact that will not load cannot be certified.")
            continue
        violations.extend(scan(obj, resolver, where=rel))
    return len(artifacts), violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "artifacts",
        nargs="*",
        help="explicit artifact files to check (default: the release-surface globs)",
    )
    args = ap.parse_args(argv)

    if args.artifacts:
        # Explicit files: scan each directly (still via the same seam + resolver).
        resolver = FsResolver(ROOT)
        violations: list[str] = []
        n = 0
        for a in args.artifacts:
            p = Path(a)
            rel = a
            n += 1
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                violations.append(f"{rel}: cannot parse the artifact itself ({type(e).__name__}).")
                continue
            violations.extend(scan(obj, resolver, where=rel))
    else:
        n, violations = check_artifacts(ROOT, DEFAULT_ARTIFACT_GLOBS)

    if violations:
        print("Evidence-reference check FAILED (INV-DEP-13):", file=sys.stderr)
        print(
            f"  {len(violations)} unresolved reference(s) across {n} release artifact(s) — a claim "
            f"that looks right but resolves to nothing:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"OK: {n} release artifact(s) — every repo-path ref resolves to a real, well-formed file, "
        f"every evidence/file URI resolves, and every digest-evidence claim matches its artifact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
