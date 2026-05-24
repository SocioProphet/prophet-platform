from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
BUILD = ROOT / "build" / "repo-governance-mvp"
OBSERVATIONS = ROOT / "contracts" / "repo-governance" / "examples" / "sociosphere-active-spine.observations.v0.json"
FINDINGS = BUILD / "repo-governance-findings.json"
REQUESTS = BUILD / "repo-governance-policy-requests.json"
READOUT = BUILD / "repo-governance-readout.md"


def _load_tool(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contracts() -> dict[str, Any]:
    validator = _load_tool("validate_repo_governance_mvp", TOOLS / "validate_repo_governance_mvp.py")
    status = int(validator.main())
    return {
        "ok": status == 0,
        "status": status,
        "mode": "local-pre-infrastructure",
        "mutation_authorized": False,
    }


def replay() -> dict[str, Any]:
    runner = _load_tool("run_repo_governance_mvp", TOOLS / "run_repo_governance_mvp.py")
    renderer = _load_tool("render_repo_governance_readout", TOOLS / "render_repo_governance_readout.py")
    run_status = int(runner.main())
    render_status = int(renderer.main())
    return {
        "ok": run_status == 0 and render_status == 0,
        "run_status": run_status,
        "render_status": render_status,
        "artifacts": {
            "findings": str(FINDINGS.relative_to(ROOT)),
            "policy_requests": str(REQUESTS.relative_to(ROOT)),
            "readout": str(READOUT.relative_to(ROOT)),
        },
        "mutation_authorized": False,
    }


def readout() -> dict[str, Any]:
    if not READOUT.exists():
        replay()
    return {
        "ok": READOUT.exists(),
        "readout_markdown": READOUT.read_text(encoding="utf-8") if READOUT.exists() else "",
        "mutation_authorized": False,
    }


def lineage() -> dict[str, Any]:
    if not FINDINGS.exists() or not REQUESTS.exists():
        replay()
    observations = _json(OBSERVATIONS).get("observations", [])
    findings = _json(FINDINGS) if FINDINGS.exists() else []
    requests = _json(REQUESTS) if REQUESTS.exists() else []
    nodes = []
    edges = []

    for obs in observations:
        nodes.append({
            "id": obs["observation_id"],
            "type": "observation",
            "label": obs["surface"],
            "repository": obs["subject_repository"],
        })

    for finding in findings:
        nodes.append({
            "id": finding["finding_id"],
            "type": "finding",
            "label": finding["kind"],
            "repository": finding["subject_repository"],
        })
        for obs_id in finding.get("antecedent_observations", []):
            edges.append({"from": obs_id, "to": finding["finding_id"], "label": "supports"})

    for request in requests:
        nodes.append({
            "id": request["request_id"],
            "type": "policy_request",
            "label": request["requested_decision"],
            "repository": request["subject_repository"],
        })
        edges.append({"from": request["finding_id"], "to": request["request_id"], "label": "requires_policy_review"})

    return {
        "ok": True,
        "nodes": nodes,
        "edges": edges,
        "mutation_authorized": False,
    }


try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover - keeps local import usable without FastAPI installed
    FastAPI = None  # type: ignore[assignment]


if FastAPI is not None:
    app = FastAPI(title="Prophet Platform Repo Governance API", version="0.1")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True, "mode": "local-pre-infrastructure", "mutation_authorized": False}

    @app.get("/validate")
    def validate_endpoint() -> dict[str, Any]:
        return validate_contracts()

    @app.post("/replay")
    def replay_endpoint() -> dict[str, Any]:
        return replay()

    @app.get("/readout")
    def readout_endpoint() -> dict[str, Any]:
        return readout()

    @app.get("/lineage")
    def lineage_endpoint() -> dict[str, Any]:
        return lineage()


def main() -> int:
    result = replay()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
