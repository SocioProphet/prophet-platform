#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "agent-action-trace"
EXAMPLES_DIR = CONTRACT_DIR / "examples"
EXPECTED_API_VERSION = "prophet-platform.socioprophet.org/v0.1"
EXPECTED_KINDS = {
    "agent-action-record.v0.1.schema.json": "AgentActionRecord",
    "agent-trace-record.v0.1.schema.json": "AgentTraceRecord",
    "agent-action-trace-conformance-report.v0.1.schema.json": "AgentActionTraceConformanceReport",
}
EXAMPLE_BY_KIND = {
    "AgentActionRecord": "agent-action-record.example.v0.1.json",
    "AgentTraceRecord": "agent-trace-record.example.v0.1.json",
    "AgentActionTraceConformanceReport": "agent-action-trace-conformance-report.example.v0.1.json",
}


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
    if not isinstance(data, dict):
        fail(f"{path.relative_to(ROOT)}: expected top-level object")
    return data


def require_keys(obj: dict, keys: list[str], where: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        fail(f"{where}: missing required keys: {', '.join(missing)}")


def validate_schema(path: Path, expected_kind: str) -> None:
    data = load_json(path)
    if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail(f"{path.relative_to(ROOT)}: expected JSON Schema draft 2020-12")
    if data.get("title") != expected_kind:
        fail(f"{path.relative_to(ROOT)}: expected title {expected_kind}")
    props = data.get("properties")
    if not isinstance(props, dict):
        fail(f"{path.relative_to(ROOT)}: properties must be object")
    if props.get("apiVersion", {}).get("const") != EXPECTED_API_VERSION:
        fail(f"{path.relative_to(ROOT)}: apiVersion const mismatch")
    if props.get("kind", {}).get("const") != expected_kind:
        fail(f"{path.relative_to(ROOT)}: kind const mismatch")


def validate_example(path: Path, expected_kind: str) -> None:
    data = load_json(path)
    require_keys(data, ["apiVersion", "kind", "metadata", "spec"], str(path.relative_to(ROOT)))
    if data["apiVersion"] != EXPECTED_API_VERSION:
        fail(f"{path.relative_to(ROOT)}: apiVersion mismatch")
    if data["kind"] != expected_kind:
        fail(f"{path.relative_to(ROOT)}: kind mismatch")
    metadata = data["metadata"]
    if not isinstance(metadata, dict):
        fail(f"{path.relative_to(ROOT)}: metadata must be object")
    for ref_key in ("profileRef", "standardsRef"):
        if ref_key in metadata and "socioprophet-agent-standards" not in metadata[ref_key]:
            fail(f"{path.relative_to(ROOT)}: metadata.{ref_key} must reference socioprophet-agent-standards")
    if "ontologyRef" in metadata and "SocioProphet/ontogenesis" not in metadata["ontologyRef"]:
        fail(f"{path.relative_to(ROOT)}: metadata.ontologyRef must reference SocioProphet/ontogenesis")

    spec = data["spec"]
    if not isinstance(spec, dict):
        fail(f"{path.relative_to(ROOT)}: spec must be object")
    if expected_kind == "AgentTraceRecord":
        if spec.get("traceIsAuthority") is not False:
            fail(f"{path.relative_to(ROOT)}: traceIsAuthority must be false")
        require_keys(spec, ["traceId", "pattern", "traceKind", "medium", "timestamp"], f"{path.relative_to(ROOT)}:spec")
    elif expected_kind == "AgentActionRecord":
        require_keys(spec, ["agentSubjectRef", "actionId", "actionType", "policyRef", "receiptRef"], f"{path.relative_to(ROOT)}:spec")
    elif expected_kind == "AgentActionTraceConformanceReport":
        require_keys(spec, ["implementationRef", "ontologyRef", "bootstrapValidatorRef", "overallStatus", "checks"], f"{path.relative_to(ROOT)}:spec")
        if "SocioProphet/ontogenesis" not in spec["ontologyRef"]:
            fail(f"{path.relative_to(ROOT)}: spec.ontologyRef must reference SocioProphet/ontogenesis")
        if "socioprophet-standards-storage" not in spec["bootstrapValidatorRef"]:
            fail(f"{path.relative_to(ROOT)}: spec.bootstrapValidatorRef must reference socioprophet-standards-storage")


def main() -> int:
    for schema_name, kind in EXPECTED_KINDS.items():
        schema_path = CONTRACT_DIR / schema_name
        if not schema_path.exists():
            fail(f"missing schema: {schema_path.relative_to(ROOT)}")
        validate_schema(schema_path, kind)
        example_path = EXAMPLES_DIR / EXAMPLE_BY_KIND[kind]
        if not example_path.exists():
            fail(f"missing example: {example_path.relative_to(ROOT)}")
        validate_example(example_path, kind)
    print("OK: validated agent action/trace generated contracts and examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
