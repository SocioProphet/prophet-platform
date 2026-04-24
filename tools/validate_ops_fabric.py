#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_JSON = [
    "schemas/ops/evidence-ref.schema.v0.1.json",
    "schemas/ops/intelligence-ref.schema.v0.1.json",
    "schemas/ops/telemetry-event.schema.v0.1.json",
    "schemas/ops/action-proposal.schema.v0.1.json",
    "schemas/ops/handoff-candidate.schema.v0.1.json",
    "examples/ops/action-proposal-sample.v0.1.json",
]

REQUIRED_DOCS = [
    "docs/PROPHET_REAL_TIME_OPS_FABRIC.md",
    "docs/OPS_FABRIC_GLOBAL_DEVSECOPS_ALIGNMENT.md",
    "docs/OPS_FABRIC_SHERLOCK_SEARCH_ALIGNMENT.md",
]

REQUIRED_DOC_TERMS = {
    "docs/PROPHET_REAL_TIME_OPS_FABRIC.md": [
        "global-devsecops-intelligence",
        "sherlock",
        "report-only",
    ],
    "docs/OPS_FABRIC_GLOBAL_DEVSECOPS_ALIGNMENT.md": [
        "global-devsecops-intelligence",
        "AI4IT",
        "operational graph",
    ],
    "docs/OPS_FABRIC_SHERLOCK_SEARCH_ALIGNMENT.md": [
        "Sherlock Search",
        "chat-ops",
        "OPS_FABRIC",
    ],
}


def fail(message: str) -> None:
    raise SystemExit(f"ops fabric validation failed: {message}")


def read_json(path: str) -> dict:
    full = ROOT / path
    if not full.exists():
        fail(f"missing required JSON file: {path}")
    try:
        data = json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"expected JSON object in {path}")
    return data


def require_terms(path: str, text: str) -> None:
    normalized = text.lower()
    for term in REQUIRED_DOC_TERMS.get(path, []):
        if term.lower() not in normalized:
            fail(f"{path} missing required term: {term}")


def main() -> None:
    for path in REQUIRED_JSON:
        read_json(path)

    for path in REQUIRED_DOCS:
        full = ROOT / path
        if not full.exists():
            fail(f"missing required doc: {path}")
        text = full.read_text(encoding="utf-8")
        if not text.strip():
            fail(f"empty required doc: {path}")
        require_terms(path, text)

    proposal = read_json("examples/ops/action-proposal-sample.v0.1.json")
    if proposal.get("policy_status") != "NOT_EVALUATED":
        fail("sample proposal must remain policy_status=NOT_EVALUATED")
    if proposal.get("autonomy_tier") != "REPORT_ONLY":
        fail("sample proposal must remain autonomy_tier=REPORT_ONLY")
    if not proposal.get("intelligence_refs"):
        fail("sample proposal must include global-devsecops intelligence_refs")

    print("ops fabric validation passed")


if __name__ == "__main__":
    main()
