#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/repo-intelligence/prophet-understanding.fixture.json"
VALIDATOR = ROOT / "tools/validate_prophet_understand.py"
OUT_DIR = ROOT / "build/prophet-understand"
INDEX_OUT = OUT_DIR / "lampstand-index.json"
SEARCH_OUT = OUT_DIR / "sherlock-search-contract-query.json"
POLICY_OUT = OUT_DIR / "policy-decision.json"
SCORECARD_OUT = OUT_DIR / "delivery-scorecard.json"
SUMMARY_OUT = OUT_DIR / "vertical-slice-summary.json"


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_artifact() -> dict[str, Any]:
    if not FIXTURE.exists():
        fail(f"missing fixture: {FIXTURE.relative_to(ROOT)}")
    try:
        value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid fixture JSON: {exc}")
    if not isinstance(value, dict):
        fail("fixture must contain a JSON object")
    return value


def run_contract_validator() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        fail("Prophet Understand contract validator failed")


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def base_record(artifact: dict[str, Any], family: str, record_id: str, title: str, text: str, raw: dict[str, Any]) -> dict[str, Any]:
    repo = artifact.get("repo", {})
    policy = artifact.get("policy_status", {})
    return {
        "repo_full_name": repo.get("full_name", "unknown") if isinstance(repo, dict) else "unknown",
        "repo_commit": repo.get("commit", "unknown") if isinstance(repo, dict) else "unknown",
        "schema_version": artifact.get("schema_version", "unknown"),
        "record_family": family,
        "record_id": record_id,
        "title": title,
        "text": text,
        "policy_state": policy.get("state", "unknown") if isinstance(policy, dict) else "unknown",
        "raw": raw,
    }


def build_index(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    nodes = {node.get("id"): node for node in as_list(artifact.get("nodes")) if isinstance(node, dict)}
    edges = {edge.get("id"): edge for edge in as_list(artifact.get("edges")) if isinstance(edge, dict)}

    for node_id, node in sorted(nodes.items()):
        record = base_record(
            artifact,
            "repo_graph_node",
            str(node_id),
            f"{node.get('kind', 'node')}: {node.get('label', node_id)}",
            " ".join(str(part) for part in [node.get("label"), node.get("kind"), node.get("path"), node.get("metadata", {})] if part),
            node,
        )
        record.update({"node_id": node_id, "path": node.get("path"), "source_anchor": node.get("source_anchor"), "confidence": node.get("confidence"), "provenance_receipt_ids": node.get("provenance_receipt_ids", [])})
        records.append(record)

    for edge_id, edge in sorted(edges.items()):
        source = edge.get("source")
        target = edge.get("target")
        source_label = nodes.get(source, {}).get("label", source)
        target_label = nodes.get(target, {}).get("label", target)
        record = base_record(artifact, "repo_graph_edge", str(edge_id), f"{edge.get('kind', 'edge')}: {source} -> {target}", f"{edge.get('kind')} relationship from {source_label} to {target_label}", edge)
        record.update({"edge_id": edge_id, "source_node_id": source, "target_node_id": target, "confidence": edge.get("confidence"), "provenance_receipt_ids": edge.get("provenance_receipt_ids", [])})
        records.append(record)

    for summary in [item for item in as_list(artifact.get("summaries")) if isinstance(item, dict)]:
        node_id = summary.get("node_id")
        record = base_record(artifact, "repo_graph_summary", summary.get("id", "summary:unknown"), f"summary: {node_id}", summary.get("text", ""), summary)
        record.update({"node_id": node_id, "confidence": summary.get("confidence"), "provenance_receipt_ids": summary.get("provenance_receipt_ids", [])})
        records.append(record)

    for result in [item for item in as_list(artifact.get("validation_results")) if isinstance(item, dict)]:
        record = base_record(artifact, "repo_graph_validation", result.get("id", "validation:unknown"), f"validation: {result.get('check_id')}", result.get("message", ""), result)
        record.update({"validation_status": result.get("status"), "severity": result.get("severity"), "target_id": result.get("target_id")})
        records.append(record)

    policy = artifact.get("policy_status", {}) if isinstance(artifact.get("policy_status"), dict) else {}
    for check in [item for item in as_list(policy.get("checks")) if isinstance(item, dict)]:
        record = base_record(artifact, "repo_graph_policy", check.get("id", "policy:unknown"), f"policy: {check.get('state')}", check.get("message", ""), check)
        record.update({"policy_state": check.get("state"), "provenance_receipt_ids": check.get("evidence_receipt_ids", [])})
        records.append(record)

    return sorted(records, key=lambda item: (item["record_family"], item["record_id"]))


def tokens(text: str) -> list[str]:
    import re

    return [part for part in re.split(r"[^A-Za-z0-9_.:/-]+", text.lower()) if part]


def search(records: list[dict[str, Any]], query: str, limit: int = 10) -> dict[str, Any]:
    query_tokens = tokens(query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for record in records:
        haystack = " ".join(str(record.get(key, "")) for key in ["title", "text", "record_id", "node_id", "edge_id", "path", "record_family", "policy_state", "validation_status"]).lower()
        haystack_tokens = set(tokens(haystack))
        overlap = sum(1 for token in query_tokens if token in haystack_tokens)
        partial = sum(1 for token in query_tokens if token in haystack)
        confidence = record.get("confidence")
        confidence_boost = float(confidence) if isinstance(confidence, (int, float)) else 0.0
        score = overlap * 2.0 + partial * 0.5 + confidence_boost
        if query.lower() in haystack:
            score += 4.0
        if score > 0:
            ranked.append((score, record))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].get("record_id", "")))
    return {
        "query": query,
        "mode": "lexical-graph-evidence-v0",
        "result_count": min(limit, len(ranked)),
        "results": [
            {
                "score": round(score, 4),
                "record_family": record.get("record_family"),
                "record_id": record.get("record_id"),
                "title": record.get("title"),
                "path": record.get("path"),
                "node_id": record.get("node_id"),
                "edge_id": record.get("edge_id"),
                "source_anchor": record.get("source_anchor"),
                "policy_state": record.get("policy_state"),
                "validation_status": record.get("validation_status"),
                "provenance_receipt_ids": record.get("provenance_receipt_ids", []),
            }
            for score, record in ranked[:limit]
        ],
        "notice": "No semantic/vector certainty is claimed without embedding evidence.",
    }


def evaluate_policy(artifact: dict[str, Any]) -> dict[str, Any]:
    nodes = [item for item in as_list(artifact.get("nodes")) if isinstance(item, dict)]
    edges = [item for item in as_list(artifact.get("edges")) if isinstance(item, dict)]
    receipts = [item for item in as_list(artifact.get("provenance_receipts")) if isinstance(item, dict)]
    node_ids = {node.get("id") for node in nodes}
    receipt_ids = {receipt.get("id") for receipt in receipts}
    factual_nodes = [node for node in nodes if node.get("kind") not in {"repo", "directory"}]
    anchored = [node for node in factual_nodes if isinstance(node.get("source_anchor"), dict)]
    endpoint_errors = [edge.get("id") for edge in edges if edge.get("source") not in node_ids or edge.get("target") not in node_ids]
    missing_provenance = []
    for family in ["nodes", "edges", "summaries", "tours", "diff_impact_sets"]:
        for item in as_list(artifact.get(family)):
            if isinstance(item, dict):
                refs = set(as_list(item.get("provenance_receipt_ids")))
                if not refs or not refs <= receipt_ids:
                    missing_provenance.append(item.get("id", f"{family}:unknown"))
    checks = []
    checks.append({"id": "graph.schema.version", "state": "allow" if artifact.get("schema_version") == "prophet-understanding.v0" else "deny", "message": "Schema version checked."})
    checks.append({"id": "graph.edge.valid_endpoints", "state": "deny" if endpoint_errors else "allow", "message": "Edge endpoint integrity checked.", "affected_ids": endpoint_errors})
    checks.append({"id": "graph.source_anchor.coverage", "state": "allow" if len(anchored) == len(factual_nodes) else "require_review", "message": "Source-anchor coverage checked."})
    checks.append({"id": "graph.provenance.coverage", "state": "allow" if not missing_provenance else "require_review", "message": "Provenance coverage checked.", "affected_ids": missing_provenance[:50]})
    state_order = {"allow": 0, "warn": 1, "unknown": 1, "require_review": 2, "deny": 3}
    policy_state = max((check["state"] for check in checks), key=lambda state: state_order[state])
    return {"policy_state": policy_state, "checks": checks, "metrics": {"node_count": len(nodes), "edge_count": len(edges), "source_anchor_coverage_ratio": round(len(anchored) / len(factual_nodes), 4) if factual_nodes else 1.0, "provenance_receipt_count": len(receipts)}}


def scorecard(artifact: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    nodes = [item for item in as_list(artifact.get("nodes")) if isinstance(item, dict)]
    edges = [item for item in as_list(artifact.get("edges")) if isinstance(item, dict)]
    facts = []
    for family in ["nodes", "edges", "summaries", "tours", "diff_impact_sets"]:
        facts.extend([item for item in as_list(artifact.get(family)) if isinstance(item, dict)])
    facts_with_receipts = [item for item in facts if as_list(item.get("provenance_receipt_ids"))]
    factual_nodes = [node for node in nodes if node.get("kind") not in {"repo", "directory"}]
    anchored_nodes = [node for node in factual_nodes if isinstance(node.get("source_anchor"), dict)]
    diff_radius = 0
    for diff in as_list(artifact.get("diff_impact_sets")):
        if isinstance(diff, dict):
            diff_radius += len(as_list(diff.get("affected_nodes"))) + len(as_list(diff.get("affected_edges"))) + 2 * len(as_list(diff.get("affected_tests"))) + len(as_list(diff.get("affected_docs"))) + 3 * len(as_list(diff.get("affected_policies")))
    return {
        "repo_graph_present": 1,
        "repo_graph_schema_valid": 1 if artifact.get("schema_version") == "prophet-understanding.v0" else 0,
        "repo_graph_node_count": len(nodes),
        "repo_graph_edge_count": len(edges),
        "repo_graph_anchor_coverage_ratio": round(len(anchored_nodes) / len(factual_nodes), 4) if factual_nodes else 1.0,
        "repo_graph_provenance_coverage_ratio": round(len(facts_with_receipts) / len(facts), 4) if facts else 1.0,
        "repo_graph_policy_warning_count": sum(1 for check in as_list(artifact.get("policy_status", {}).get("checks")) if isinstance(check, dict) and check.get("state") in {"warn", "require_review"}),
        "repo_pr_impact_radius": diff_radius,
        "scorecard_state": "red" if policy.get("policy_state") == "deny" else "yellow" if policy.get("policy_state") in {"warn", "require_review"} else "green",
    }


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    run_contract_validator()
    artifact = load_artifact()
    index = build_index(artifact)
    search_result = search(index, "what depends on this contract?")
    policy = evaluate_policy(artifact)
    score = scorecard(artifact, policy)
    summary = {
        "artifact": str(FIXTURE.relative_to(ROOT)),
        "index_records": len(index),
        "search_result_count": search_result["result_count"],
        "policy_state": policy["policy_state"],
        "scorecard_state": score["scorecard_state"],
        "outputs": [str(path.relative_to(ROOT)) for path in [INDEX_OUT, SEARCH_OUT, POLICY_OUT, SCORECARD_OUT]],
    }
    write(INDEX_OUT, index)
    write(SEARCH_OUT, search_result)
    write(POLICY_OUT, policy)
    write(SCORECARD_OUT, score)
    write(SUMMARY_OUT, summary)
    print("OK: Prophet Understand vertical slice passed")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
