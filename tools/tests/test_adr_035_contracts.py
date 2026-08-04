"""ADR-035 fault-attribution contract validation tests.

Validates all five contract schemas against their fixture examples.
Every fixture must conform; an unknown kind is a hard failure.
Schema conformance is the CI gate for these contracts — a fixture that
silently does not exercise the schema is a hole.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "tools"))

try:
    import jsonschema
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

KIND_TO_SCHEMA = {
    "FaultEnvelope": "FaultEnvelope.v0.1.json",
    "EngineManifest": "EngineManifest.v0.1.json",
    "BoundaryTransition": "BoundaryTransition.v0.1.json",
    "RolloutReceipt": "RolloutReceipt.v0.1.json",
    "DiagnosticRedactionPolicy": "DiagnosticRedactionPolicy.v0.1.json",
}

_SCHEMA_CACHE: dict[str, dict] = {}


def _load_schema(name: str) -> dict:
    if name not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[name] = json.loads((CONTRACTS / name).read_text())
    return _SCHEMA_CACHE[name]


def _validate(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    kind = data.get("kind")
    schema_name = KIND_TO_SCHEMA.get(kind)
    if not schema_name:
        return [f"unknown kind '{kind}'"]
    schema = _load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    return [str(e.message) for e in validator.iter_errors(data)]


# ── Parametrize over example fixtures ────────────────────────────────────────

_EXAMPLE_FIXTURES = sorted(EXAMPLES.glob("adr-035-*.json"))

# Guard: we must have at least 5 fixtures (one per contract type).
# If the glob is empty the parametrize decorator skips the tests silently,
# which is a false-green gate — catch it here.
assert len(_EXAMPLE_FIXTURES) >= 5, (
    f"Expected at least 5 adr-035-*.json fixtures in {EXAMPLES.relative_to(ROOT)}, "
    f"found {len(_EXAMPLE_FIXTURES)}. "
    "An empty fixture set silently disables this gate."
)


@pytest.mark.parametrize("fixture_path", _EXAMPLE_FIXTURES, ids=lambda p: p.name)
def test_example_fixture_valid(fixture_path: Path) -> None:
    errors = _validate(fixture_path)
    assert errors == [], f"{fixture_path.name} failed schema validation:\n" + "\n".join(errors)


# ── Synthetic fixture (motivating case from the ADR) ─────────────────────────

def test_synthetic_script_editor_fault_envelope() -> None:
    path = FIXTURES / "fault-envelope-script-editor-synthetic.json"
    assert path.exists(), f"Synthetic fixture missing: {path}"
    errors = _validate(path)
    assert errors == [], "Synthetic fixture failed:\n" + "\n".join(errors)

    data = json.loads(path.read_text())
    # Verify the motivating invariant: simulated guard fault in WebKit namespace
    assert data["fault"]["namespace"] == "WebKit"
    assert data["fault"]["simulated"] is True
    assert data["fault"]["intentional"] is False


# ── Kind coverage check ───────────────────────────────────────────────────────

def test_all_five_kinds_covered() -> None:
    """Every ADR-035 contract kind must appear in at least one fixture."""
    covered: set[str] = set()
    for path in _EXAMPLE_FIXTURES:
        data = json.loads(path.read_text())
        covered.add(data.get("kind", ""))
    # Also count synthetic fixtures
    synth = FIXTURES / "fault-envelope-script-editor-synthetic.json"
    if synth.exists():
        covered.add(json.loads(synth.read_text()).get("kind", ""))

    missing = set(KIND_TO_SCHEMA.keys()) - covered
    assert not missing, f"No fixture covers these contract kinds: {missing}"


# ── Schema structural invariants ─────────────────────────────────────────────

@pytest.mark.parametrize("kind,schema_file", sorted(KIND_TO_SCHEMA.items()))
def test_schema_has_required_fields(kind: str, schema_file: str) -> None:
    schema = _load_schema(schema_file)
    required = schema.get("required", [])
    assert "schemaVersion" in required, f"{kind}: 'schemaVersion' must be required"
    assert "kind" in required, f"{kind}: 'kind' must be required"
    assert schema.get("additionalProperties") is False, (
        f"{kind}: additionalProperties must be false (closed schema)"
    )


@pytest.mark.parametrize("kind,schema_file", sorted(KIND_TO_SCHEMA.items()))
def test_schema_kind_is_const(kind: str, schema_file: str) -> None:
    schema = _load_schema(schema_file)
    kind_prop = schema.get("properties", {}).get("kind", {})
    assert kind_prop.get("const") == kind, (
        f"{schema_file}: kind property must be const: '{kind}', "
        f"got {kind_prop!r}"
    )


# ── Negative tests ────────────────────────────────────────────────────────────

def test_fault_envelope_rejects_missing_fault() -> None:
    data = {
        "schemaVersion": "v0.1",
        "kind": "FaultEnvelope",
        "eventId": "fe-bad",
        "timestamp": "2026-08-04T00:00:00Z",
        "eventType": "renderer_crash",
        "severity": "warning",
        "process": {"name": "test"},
        "privacy": {"tier": "local_private", "stableIdentifiersRedacted": False},
    }
    schema = _load_schema("FaultEnvelope.v0.1.json")
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert any("fault" in str(e.message).lower() or "required" in str(e.message).lower() for e in errors), (
        "Expected a 'fault' required-field error, got none"
    )


def test_engine_manifest_rejects_unknown_engine_type() -> None:
    data = {
        "schemaVersion": "v0.1",
        "kind": "EngineManifest",
        "engineId": "bad-engine",
        "engineType": "flying_car",
        "ownerComponent": "SomeApp",
        "observability": {
            "emitEngineInit": True,
            "emitBoundaryTransition": True,
            "emitFaultEnvelope": True,
        },
    }
    schema = _load_schema("EngineManifest.v0.1.json")
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert errors, "Expected validation errors for unknown engineType"


def test_boundary_transition_rejects_unknown_initiator() -> None:
    data = {
        "schemaVersion": "v0.1",
        "kind": "BoundaryTransition",
        "transitionId": "bt-bad",
        "timestamp": "2026-08-04T00:00:00Z",
        "sourceComponent": "A",
        "targetComponent": "B",
        "boundaryType": "shell_execution",
        "initiator": "magic",
        "userVisible": False,
    }
    schema = _load_schema("BoundaryTransition.v0.1.json")
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert errors, "Expected validation errors for unknown initiator"


def test_diagnostic_policy_rejects_wrong_tier_value() -> None:
    data = {
        "schemaVersion": "v0.1",
        "kind": "DiagnosticRedactionPolicy",
        "tiers": {
            "localPrivate": {"tokensOrSecrets": "redact"},
            "shareableDefault": {"stableDeviceIds": "publish"},
            "publicIssue": {"stableDeviceIds": "omit"},
        },
    }
    schema = _load_schema("DiagnosticRedactionPolicy.v0.1.json")
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert errors, "Expected validation errors for invalid tier value 'publish'"
