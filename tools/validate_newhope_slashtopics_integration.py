#!/usr/bin/env python3
"""Self-contained CI gate for the New Hope + Slash Topics integration.

The platform mirrors a schema subset of SocioProphet/slash-topics under
``contracts/imported/slash-topics/`` (see SOURCE_MANIFEST.yaml, pinned) rather
than vendoring the whole repo, so this validator runs against the mirrored
files already present in the tree. It makes no network calls and writes nothing.

Checks:
- No .DS_Store / __MACOSX junk under the landed integration paths.
- IMPORT_MANIFEST declares new-hope AND slash-topics, each with a pin
  (the platform's provenance invariant — replaces the cross-repo LICENSE check).
- Slash Topics pack schema, MembraneDecision schema, and Model Selection policy
  hold their expected invariants.
- All 4 landed example fixtures parse as JSON; the 2 that bind to a MIRRORED
  slash-topics schema (slash_topics_pack_min, membrane_decision_allow) are also
  schema-validated against it. The other 2 (newhope_message_posted,
  embedding_receipt_lsi) bind to New Hope schemas, imported by pinned manifest
  only — not mirrored into this tree — so this gate parse-checks them and stops
  there; it does not claim to schema-validate all 4.

Exit non-zero on any violation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SLASH = ROOT / "contracts" / "imported" / "slash-topics"
SPECS = SLASH / "specs"
EXAMPLES = ROOT / "examples" / "newhope-slash-topics"
IMPORT_MANIFEST = ROOT / "contracts" / "imported" / "IMPORT_MANIFEST.yaml"
LANDED_PATHS = [SLASH, EXAMPLES, ROOT / "docs" / "INTEGRATION_NewHope_SlashTopics_SemanticBI.md"]


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Required file missing: {path.relative_to(ROOT)}")
    except Exception as e:  # noqa: BLE001
        fail(f"Could not parse JSON: {path} ({e})")


def assert_no_junk() -> None:
    junk = []
    for base in LANDED_PATHS:
        if base.is_dir():
            for p in base.rglob("*"):
                if p.name == ".DS_Store" or "__MACOSX" in p.parts:
                    junk.append(str(p.relative_to(ROOT)))
    if junk:
        fail("Junk artifacts present (must be deleted):\n" + "\n".join(junk[:50]))
    ok("No .DS_Store/__MACOSX junk under landed paths")


def confine(base: Path, rel: str, *, allow_absolute: bool = False) -> Path:
    """Resolve `rel` under `base` and REFUSE if the result escapes `base`.

    Pure and side-effect-free (raises ValueError, never exits) so it can be tested in
    isolation from the full ROOT tree. Two escape shapes are closed:
      - `rel` is absolute: pathlib's `/` operator DISCARDS `base` entirely when the
        right-hand side is absolute (`Path("/a") / "/etc/passwd" == Path("/etc/passwd")`),
        so an absolute `rel` would otherwise resolve wherever it points, silently.
      - `rel` contains `..` segments that walk back out of `base` after `.resolve()`.
    """
    if not allow_absolute and Path(rel).is_absolute():
        raise ValueError(f"expected a path relative to {base}, got an absolute path: {rel}")
    resolved = (base / rel).resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"{rel!r} resolves outside {base}: {resolved}")
    return resolved


def assert_import_provenance() -> None:
    try:
        manifest = yaml.safe_load(IMPORT_MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Required file missing: {IMPORT_MANIFEST.relative_to(ROOT)}")
    except yaml.YAMLError as e:
        fail(f"Could not parse {IMPORT_MANIFEST.relative_to(ROOT)}: {e}")
    except (OSError, UnicodeDecodeError) as e:
        # FileNotFoundError/YAMLError above are the expected shapes; a PermissionError,
        # a directory-where-a-file-is-expected, or a bad-encoding manifest must still
        # produce this tool's own [FAIL], never an uncaught traceback bypassing it.
        fail(f"Could not read {IMPORT_MANIFEST.relative_to(ROOT)}: {e}")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("imports"), list):
        fail("IMPORT_MANIFEST malformed: expected a mapping with an 'imports' list")
    by_repo = {i.get("repo"): i for i in manifest["imports"] if isinstance(i, dict)}
    for repo in ("SocioProphet/new-hope", "SocioProphet/slash-topics"):
        entry = by_repo.get(repo)
        if not entry:
            fail(f"IMPORT_MANIFEST does not declare {repo}")
        if not entry.get("pin"):
            fail(f"IMPORT_MANIFEST entry for {repo} has no pin (provenance required)")
    ok("IMPORT_MANIFEST declares new-hope + slash-topics, both pinned")

    # Enforce slash-topics required_objects: each must resolve under its local_path,
    # and local_path itself must resolve under ROOT. Both values come from a file this
    # PR itself lands (IMPORT_MANIFEST.yaml), so a malicious or malformed entry — an
    # absolute local_path (which pathlib's `/` operator lets silently DISCARD ROOT
    # entirely), or a `../`-laden required_object — must not let the check "pass" by
    # probing or reading a path outside the mirror directory. Confine both, fail-closed.
    st = by_repo["SocioProphet/slash-topics"]
    raw_local_path = st.get("local_path", "contracts/imported/slash-topics/")
    try:
        local_path = confine(ROOT, raw_local_path)
    except ValueError as e:
        fail(f"slash-topics local_path is unsafe: {e}")
    for obj in st.get("required_objects", []):
        try:
            resolved = confine(local_path, obj)
        except ValueError as e:
            fail(f"slash-topics required_object is unsafe: {e}")
        if not resolved.is_file():
            fail(f"slash-topics required_object not mirrored: {resolved.relative_to(ROOT)}")
    ok("slash-topics required_objects all resolve under local_path (confined to ROOT)")


def assert_schema_invariants() -> None:
    schema = load_json(SPECS / "SlashTopics_Schema_v0.1.json")
    md = load_json(SPECS / "Membrane_Decision_v0.1.json")
    model = load_json(SPECS / "Model_Selection_Policy_v0.1.json")

    required = set(schema.get("required", []))
    for k in ["schema", "pack", "version", "snapshot", "topics"]:
        if k not in required:
            fail(f"SlashTopics schema missing required field: {k}")
    ok("SlashTopics pack schema required fields look sane")

    md_required = set(md.get("required", []))
    if not {"decision", "audit"}.issubset(md_required):
        fail("MembraneDecision v0.1 schema must require decision + audit")
    decision_enum = set(md.get("properties", {}).get("decision", {}).get("enum", []))
    expected = {"ALLOW", "DENY", "QUARANTINE", "REDACT", "REQUIRE_SIGNATURE"}
    if decision_enum != expected:
        fail(f"MembraneDecision enum mismatch. Expected {sorted(expected)}, got {sorted(decision_enum)}")
    ok("MembraneDecision enum + required fields look sane")

    encoder_allowed = model.get("encoder_policy", {}).get("allowed")
    if encoder_allowed is not False:
        fail("Model_Selection_Policy_v0.1 must default encoder_policy.allowed=false")
    ok("Model selection policy defaults to classical methods (encoder disabled)")


def _schema_validate(instance: dict, schema: dict, label: str) -> None:
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as e:
        # The SCHEMA itself is malformed (not the instance under test) — a mirrored
        # spec that fails to compile is exactly the kind of drift this gate exists to
        # catch, so it must produce [FAIL], not an uncaught constructor exception.
        fail(f"{label}'s schema is invalid Draft 2020-12: {e.message}")
        return
    try:
        validator.validate(instance)
    except ValidationError as e:
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        fail(f"{label} failed schema validation at {loc}: {e.message}")


def validate_examples() -> None:
    # All four landed fixtures must at least parse as JSON.
    all_fixtures = [
        "slash_topics_pack_min.example.json",
        "membrane_decision_allow.example.json",
        "newhope_message_posted.example.json",
        "embedding_receipt_lsi.example.json",
    ]
    for name in all_fixtures:
        load_json(EXAMPLES / name)

    # The two fixtures with a mirrored slash-topics schema are validated against it.
    # newhope_message_posted / embedding_receipt_lsi bind to New Hope schemas, which
    # the platform imports by pinned manifest only (not mirrored), so they are
    # parse-checked above rather than schema-validated here.
    schema = load_json(SPECS / "SlashTopics_Schema_v0.1.json")
    md_schema = load_json(SPECS / "Membrane_Decision_v0.1.json")
    _schema_validate(load_json(EXAMPLES / "slash_topics_pack_min.example.json"), schema, "slash_topics_pack_min")
    _schema_validate(load_json(EXAMPLES / "membrane_decision_allow.example.json"), md_schema, "membrane_decision_allow")
    ok("All 4 fixtures parse; the 2 with mirrored schemas validate against them")


def main() -> int:
    assert_no_junk()
    assert_import_provenance()
    assert_schema_invariants()
    validate_examples()
    ok("New Hope + Slash Topics integration: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
