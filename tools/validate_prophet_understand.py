#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/repo-intelligence/prophet-understanding.schema.json"
FIXTURE = ROOT / "examples/repo-intelligence/prophet-understanding.fixture.json"
DOC = ROOT / "docs/PROPHET_UNDERSTAND_REPO_INTELLIGENCE.md"
SCHEMA_ID = "https://standards.socioprophet.org/schemas/repo-intelligence/prophet-understanding.schema.json"
VERSION = "prophet-understanding.v0"
NODE_KINDS = {"repo", "directory", "file", "module", "package", "service", "endpoint", "schema", "contract", "document", "workflow", "test", "config", "runtime", "policy", "domain", "concept", "validator"}
EDGE_KINDS = {"contains", "imports", "depends_on", "defines", "documents", "tests", "configures", "calls", "owns", "generates", "validates", "governed_by", "impacted_by", "related_to"}
POLICY_STATES = {"allow", "warn", "require_review", "deny", "unknown"}
DOC_MARKERS = ["Core artifact", "Required top-level fields", "Node taxonomy", "Edge taxonomy", "Source anchors", "Provenance receipts", "Guided tours", "Diff impact sets", "Policy states", "Cross-repo responsibilities", "v0 acceptance criteria", "Non-goals"]


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def require(obj: dict[str, Any], keys: set[str], where: str) -> None:
    missing = sorted(keys - set(obj))
    if missing:
        fail(f"{where} missing keys: {', '.join(missing)}")


def as_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{where} must be a list")
    return value


def check_hash(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        fail(f"{where} must start with sha256:")


def check_confidence(value: Any, where: str) -> None:
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        fail(f"{where} confidence must be numeric 0..1")


def check_relpath(value: str, where: str) -> None:
    if not value or value.startswith("/") or ".." in Path(value).parts or re.match(r"^[A-Za-z]:", value):
        fail(f"{where} must be a repo-relative path")


def check_stable_id(value: str, where: str) -> None:
    if not value or value.startswith("/") or re.search(r"20\d{2}-\d{2}-\d{2}|T\d{2}:\d{2}:\d{2}|\\", value):
        fail(f"{where} has unstable id: {value!r}")


def ids(items: list[dict[str, Any]], where: str) -> set[str]:
    seen: set[str] = set()
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            fail(f"{where} item missing string id")
        check_stable_id(item_id, f"{where}.{item_id}")
        if item_id in seen:
            fail(f"duplicate {where} id: {item_id}")
        seen.add(item_id)
    return seen


def validate_schema(schema: dict[str, Any]) -> None:
    if schema.get("$id") != SCHEMA_ID:
        fail("schema $id drifted")
    if schema.get("properties", {}).get("schema_version", {}).get("const") != VERSION:
        fail("schema_version const drifted")
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        fail("schema missing $defs")
    for name in ["RepoMetadata", "Generator", "AgentIdentity", "SourceAnchor", "RepoNode", "RepoEdge", "Summary", "GuidedTour", "DiffImpactSet", "ProvenanceReceipt", "ValidationResult", "PolicyStatus", "PolicyCheck"]:
        if name not in defs:
            fail(f"schema missing definition: {name}")
    if not NODE_KINDS <= set(defs["RepoNode"]["properties"]["kind"]["enum"]):
        fail("RepoNode.kind enum missing required values")
    if not EDGE_KINDS <= set(defs["RepoEdge"]["properties"]["kind"]["enum"]):
        fail("RepoEdge.kind enum missing required values")
    if set(defs["PolicyStatus"]["properties"]["state"]["enum"]) != POLICY_STATES:
        fail("PolicyStatus.state enum drifted")


def validate_jsonschema(schema: dict[str, Any], fixture: dict[str, Any]) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        return
    try:
        jsonschema.Draft202012Validator(schema).validate(fixture)
    except Exception as exc:
        fail(f"fixture does not validate against JSON Schema: {exc}")


def validate_artifact(artifact: dict[str, Any]) -> None:
    require(artifact, {"schema_version", "repo", "generator", "agent_identity", "nodes", "edges", "summaries", "tours", "diff_impact_sets", "provenance_receipts", "validation_results", "policy_status"}, "artifact")
    if artifact["schema_version"] != VERSION:
        fail("artifact schema_version drifted")
    repo = artifact["repo"]
    require(repo, {"full_name", "default_branch", "commit", "generated_at", "artifact_hash"}, "artifact.repo")
    if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo["full_name"]):
        fail("artifact.repo.full_name must be owner/name")
    if not re.match(r"^[0-9a-fA-F]{7,40}$|^unknown$", repo["commit"]):
        fail("artifact.repo.commit must be SHA-like or unknown")
    check_hash(repo["artifact_hash"], "artifact.repo.artifact_hash")

    receipts = [x for x in as_list(artifact["provenance_receipts"], "provenance_receipts") if isinstance(x, dict)]
    receipt_ids = ids(receipts, "provenance_receipts")
    for receipt in receipts:
        require(receipt, {"id", "claim_type", "generator", "parser_version", "input_source_hash", "generated_at", "confidence", "validation_state", "warnings"}, f"receipt {receipt.get('id')}")
        check_hash(receipt["input_source_hash"], f"receipt {receipt['id']}.input_source_hash")
        check_confidence(receipt["confidence"], f"receipt {receipt['id']}")

    nodes = [x for x in as_list(artifact["nodes"], "nodes") if isinstance(x, dict)]
    node_ids = ids(nodes, "nodes")
    seen_kinds: set[str] = set()
    for node in nodes:
        require(node, {"id", "kind", "label", "confidence", "provenance_receipt_ids", "metadata"}, f"node {node.get('id')}")
        if node["kind"] not in NODE_KINDS:
            fail(f"node {node['id']} has invalid kind")
        seen_kinds.add(node["kind"])
        if "path" in node:
            check_relpath(node["path"], f"node {node['id']}.path")
        if node["kind"] not in {"repo", "directory"}:
            anchor = node.get("source_anchor")
            if not isinstance(anchor, dict):
                fail(f"node {node['id']} missing source_anchor")
            require(anchor, {"path", "start_line", "end_line", "content_hash"}, f"node {node['id']}.source_anchor")
            check_relpath(anchor["path"], f"node {node['id']}.source_anchor.path")
            check_hash(anchor["content_hash"], f"node {node['id']}.source_anchor.content_hash")
        check_confidence(node["confidence"], f"node {node['id']}")
        if set(as_list(node["provenance_receipt_ids"], f"node {node['id']}.provenance_receipt_ids")) - receipt_ids:
            fail(f"node {node['id']} references unknown receipt")
    for kind in {"repo", "document", "schema", "contract", "validator", "policy", "test"}:
        if kind not in seen_kinds:
            fail(f"fixture missing seed node kind: {kind}")

    edges = [x for x in as_list(artifact["edges"], "edges") if isinstance(x, dict)]
    edge_ids = ids(edges, "edges")
    for edge in edges:
        require(edge, {"id", "kind", "source", "target", "confidence", "provenance_receipt_ids", "metadata"}, f"edge {edge.get('id')}")
        if edge["kind"] not in EDGE_KINDS or edge["source"] not in node_ids or edge["target"] not in node_ids:
            fail(f"edge {edge['id']} is invalid")
        check_confidence(edge["confidence"], f"edge {edge['id']}")
        if set(as_list(edge["provenance_receipt_ids"], f"edge {edge['id']}.provenance_receipt_ids")) - receipt_ids:
            fail(f"edge {edge['id']} references unknown receipt")

    for summary in [x for x in as_list(artifact["summaries"], "summaries") if isinstance(x, dict)]:
        require(summary, {"id", "node_id", "text", "confidence", "provenance_receipt_ids"}, f"summary {summary.get('id')}")
        if summary["node_id"] not in node_ids:
            fail(f"summary {summary['id']} references unknown node")

    for tour in [x for x in as_list(artifact["tours"], "tours") if isinstance(x, dict)]:
        require(tour, {"id", "kind", "title", "steps", "provenance_receipt_ids"}, f"tour {tour.get('id')}")
        last = 0
        for step in as_list(tour["steps"], f"tour {tour['id']}.steps"):
            require(step, {"order", "node_id", "summary"}, f"tour {tour['id']}.step")
            if step["order"] <= last or step["node_id"] not in node_ids:
                fail(f"tour {tour['id']} has invalid step")
            last = step["order"]
            for edge_id in step.get("edge_ids", []):
                if edge_id not in edge_ids:
                    fail(f"tour {tour['id']} references unknown edge")

    valid_targets = node_ids | edge_ids | {"artifact:prophet-understanding.v0"}
    for result in [x for x in as_list(artifact["validation_results"], "validation_results") if isinstance(x, dict)]:
        require(result, {"id", "check_id", "target_id", "status", "severity", "message"}, f"validation {result.get('id')}")
        if result["target_id"] not in valid_targets:
            fail(f"validation {result['id']} references unknown target")

    policy = artifact["policy_status"]
    require(policy, {"state", "checks"}, "policy_status")
    if policy["state"] not in POLICY_STATES:
        fail("policy_status.state invalid")
    for check in as_list(policy["checks"], "policy_status.checks"):
        require(check, {"id", "state", "message", "evidence_receipt_ids"}, f"policy check {check.get('id')}")
        if check["state"] not in POLICY_STATES or set(check["evidence_receipt_ids"]) - receipt_ids:
            fail(f"policy check {check['id']} is invalid")


def validate_doc() -> None:
    text = DOC.read_text(encoding="utf-8", errors="replace")
    for marker in DOC_MARKERS:
        if marker not in text:
            fail(f"doc missing marker: {marker}")


def main() -> None:
    schema = load(SCHEMA)
    fixture = load(FIXTURE)
    validate_schema(schema)
    validate_jsonschema(schema, fixture)
    validate_artifact(fixture)
    validate_doc()
    print("OK: Prophet Understand repo intelligence validation passed")


if __name__ == "__main__":
    main()
