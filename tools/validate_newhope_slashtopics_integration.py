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
- The landed integration example fixtures validate against the mirrored schemas.

Exit non-zero on any violation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

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


def assert_import_provenance() -> None:
    manifest = yaml.safe_load(IMPORT_MANIFEST.read_text(encoding="utf-8"))
    by_repo = {i.get("repo"): i for i in manifest.get("imports", [])}
    for repo in ("SocioProphet/new-hope", "SocioProphet/slash-topics"):
        entry = by_repo.get(repo)
        if not entry:
            fail(f"IMPORT_MANIFEST does not declare {repo}")
        if not entry.get("pin"):
            fail(f"IMPORT_MANIFEST entry for {repo} has no pin (provenance required)")
    ok("IMPORT_MANIFEST declares new-hope + slash-topics, both pinned")


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


def validate_examples() -> None:
    schema = load_json(SPECS / "SlashTopics_Schema_v0.1.json")
    md_schema = load_json(SPECS / "Membrane_Decision_v0.1.json")

    pack_example = load_json(EXAMPLES / "slash_topics_pack_min.example.json")
    md_example = load_json(EXAMPLES / "membrane_decision_allow.example.json")

    Draft202012Validator(schema).validate(pack_example)
    Draft202012Validator(md_schema).validate(md_example)
    ok("Landed example fixtures validate against the mirrored Slash Topics schemas")


def main() -> int:
    assert_no_junk()
    assert_import_provenance()
    assert_schema_invariants()
    validate_examples()
    ok("New Hope + Slash Topics integration: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
