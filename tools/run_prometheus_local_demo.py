#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMETHEUS_LINEAR_FIXTURE = "tests/fixtures/prometheus/pysr-mvp-linear.csv"
SINDY_LINEAR_FIXTURE = "tests/fixtures/prometheus/sindy-fast-path-linear.csv"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_POLICY = ROOT / "catalog" / "prometheus-sr-gate-policy-equation-discovery.v0.1.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_command(args: list[str]) -> None:
    subprocess.run(args, check=True)


def artifact_record(kind: str, path: Path) -> dict[str, Any]:
    return {"kind": kind, "path": str(path), "sha256": sha256_file(path)}


def build_manifest(output_dir: Path, issued_at: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "manifestVersion": "0.3.0",
        "kind": "PrometheusLocalDemoManifest",
        "issuedAt": issued_at,
        "nonAuthorityDeclaration": "PROMETHEUS local demo artifacts are evidence only. They are not laws, ontology assertions, policies, controllers, or deployment authorizations.",
        "outputDir": str(output_dir),
        "artifacts": artifacts,
        "runs": [
            {
                "applicationMode": "equation_discovery",
                "methodFamily": "pysr",
                "candidateArtifact": str(output_dir / "pysr" / "equation-candidate.json"),
                "runArtifact": str(output_dir / "pysr" / "sr-run-artifact.json"),
                "gateEvaluationArtifact": str(output_dir / "pysr" / "gate-evaluation.json"),
                "jsonldArtifact": str(output_dir / "pysr" / "sr.jsonld"),
                "controlAuthority": False,
            },
            {
                "applicationMode": "scientific_law_discovery",
                "methodFamily": "ai_descartes",
                "candidateArtifact": str(output_dir / "ai-descartes" / "equation-candidate.json"),
                "runArtifact": str(output_dir / "ai-descartes" / "sr-run-artifact.json"),
                "gateEvaluationArtifact": str(output_dir / "ai-descartes" / "gate-evaluation.json"),
                "jsonldArtifact": str(output_dir / "ai-descartes" / "sr.jsonld"),
                "controlAuthority": False,
            },
            {
                "applicationMode": "platform_dynamics",
                "methodFamily": "sindy",
                "candidateArtifact": str(output_dir / "sindy" / "platform-dynamics-candidate.json"),
                "runArtifact": str(output_dir / "sindy" / "sr-run-artifact.json"),
                "controlAuthority": False,
            },
        ],
    }


def emit_pysr_lane(output_dir: Path, issued_at: str, gate_policy: str) -> list[dict[str, Any]]:
    pysr_dir = output_dir / "pysr"
    pysr_dir.mkdir(parents=True, exist_ok=True)
    candidate = pysr_dir / "equation-candidate.json"
    run = pysr_dir / "sr-run-artifact.json"
    gate = pysr_dir / "gate-evaluation.json"
    jsonld = pysr_dir / "sr.jsonld"

    run_command([
        sys.executable, "tools/prometheus_pysr_mvp.py",
        "--engine", "mvp_linear_fallback",
        "--data", PROMETHEUS_LINEAR_FIXTURE,
        "--target", "y",
        "--dataset-uri", "urn:dataset:prometheus:pysr-mvp-linear",
        "--target-unit", "meter",
        "--feature-unit", "x=meter",
        "--generated-at", issued_at,
        "--output", str(candidate),
    ])
    run_command([
        sys.executable, "tools/prometheus_emit_sr_run_artifact.py",
        "--candidate", str(candidate),
        "--run-id", "urn:prometheus:sr-run:pysr-local-demo:001",
        "--chronos-carrier-id", "urn:chronos:carrier:prometheus:local-demo:pysr",
        "--random-seed", "42",
        "--issued-at", issued_at,
        "--output", str(run),
    ])
    run_command([
        sys.executable, "tools/emit_prometheus_gate_evaluation.py",
        "--candidate", str(candidate),
        "--run-artifact", str(run),
        "--dataset", PROMETHEUS_LINEAR_FIXTURE,
        "--evaluation-id", "urn:prometheus:gate-evaluation:pysr-local-demo:001",
        "--gate-policy", gate_policy,
        "--issued-at", issued_at,
        "--output", str(gate),
    ])
    run_command([
        sys.executable, "tools/emit_prometheus_jsonld_review.py",
        "--candidate", str(candidate),
        "--run-artifact", str(run),
        "--gate-evaluation", str(gate),
        "--review-id", "urn:prometheus:jsonld:pysr-local-demo:001",
        "--review-surface", "automated_shacl_gate",
        "--issued-at", issued_at,
        "--output", str(jsonld),
    ])
    # Structural SHACL validation on the JSON-LD proposal
    run_command([
        sys.executable, "tools/validate_prometheus_jsonld_shacl.py",
        str(jsonld),
    ])
    return [
        artifact_record("EquationCandidate", candidate),
        artifact_record("SRRunArtifact", run),
        artifact_record("AutomatedGateEvaluation", gate),
        artifact_record("SRAssertionProposalJSONLD", jsonld),
    ]


def emit_ai_descartes_lane(output_dir: Path, issued_at: str) -> list[dict[str, Any]]:
    """AI-Descartes lane: scientific_law_discovery / ai_descartes methodFamily.

    Gate policy enforcement is not applied here because ai_descartes uses a
    different applicationMode than the equation_discovery policy. A dedicated
    ai_descartes gate policy is a follow-on tranche.
    """
    ai_dir = output_dir / "ai-descartes"
    ai_dir.mkdir(parents=True, exist_ok=True)
    candidate = ai_dir / "equation-candidate.json"
    run = ai_dir / "sr-run-artifact.json"
    gate = ai_dir / "gate-evaluation.json"
    jsonld = ai_dir / "sr.jsonld"

    run_command([
        sys.executable, "tools/prometheus_ai_descartes_mvp.py",
        "--engine", "fixture_ai_descartes",
        "--data", PROMETHEUS_LINEAR_FIXTURE,
        "--target", "y",
        "--dataset-uri", "urn:dataset:prometheus:ai-descartes-fixture-linear",
        "--target-unit", "meter",
        "--feature-unit", "x=meter",
        "--generated-at", issued_at,
        "--output", str(candidate),
    ])
    run_command([
        sys.executable, "tools/prometheus_emit_sr_run_artifact.py",
        "--candidate", str(candidate),
        "--run-id", "urn:prometheus:sr-run:ai-descartes-local-demo:001",
        "--chronos-carrier-id", "urn:chronos:carrier:prometheus:local-demo:ai-descartes",
        "--issued-at", issued_at,
        "--output", str(run),
    ])
    run_command([
        sys.executable, "tools/emit_prometheus_gate_evaluation.py",
        "--candidate", str(candidate),
        "--run-artifact", str(run),
        "--dataset", PROMETHEUS_LINEAR_FIXTURE,
        "--evaluation-id", "urn:prometheus:gate-evaluation:ai-descartes-local-demo:001",
        "--issued-at", issued_at,
        "--output", str(gate),
    ])
    run_command([
        sys.executable, "tools/emit_prometheus_jsonld_review.py",
        "--candidate", str(candidate),
        "--run-artifact", str(run),
        "--gate-evaluation", str(gate),
        "--review-id", "urn:prometheus:jsonld:ai-descartes-local-demo:001",
        "--review-surface", "automated_shacl_gate",
        "--issued-at", issued_at,
        "--output", str(jsonld),
    ])
    # Structural SHACL validation on the JSON-LD proposal
    run_command([
        sys.executable, "tools/validate_prometheus_jsonld_shacl.py",
        str(jsonld),
    ])
    return [
        artifact_record("EquationCandidate", candidate),
        artifact_record("SRRunArtifact", run),
        artifact_record("AutomatedGateEvaluation", gate),
        artifact_record("SRAssertionProposalJSONLD", jsonld),
    ]


def emit_sindy_lane(output_dir: Path, issued_at: str) -> list[dict[str, Any]]:
    sindy_dir = output_dir / "sindy"
    sindy_dir.mkdir(parents=True, exist_ok=True)
    candidate = sindy_dir / "platform-dynamics-candidate.json"
    run = sindy_dir / "sr-run-artifact.json"

    run_command([
        sys.executable, "tools/prometheus_sindy_fast_path.py",
        "--data", SINDY_LINEAR_FIXTURE,
        "--time-column", "t",
        "--value-column", "q",
        "--dataset-uri", "urn:dataset:prometheus:sindy-fast-path-linear",
        "--generated-at", issued_at,
        "--output", str(candidate),
    ])
    run_command([
        sys.executable, "tools/prometheus_emit_sr_run_artifact.py",
        "--candidate", str(candidate),
        "--run-id", "urn:prometheus:sr-run:sindy-local-demo:001",
        "--chronos-carrier-id", "urn:chronos:carrier:prometheus:local-demo:sindy",
        "--issued-at", issued_at,
        "--output", str(run),
    ])
    return [
        artifact_record("PlatformDynamicsCandidate", candidate),
        artifact_record("SRRunArtifact", run),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run consolidated PROMETHEUS local demo")
    parser.add_argument("--output-dir", default="build/prometheus/local-demo")
    parser.add_argument("--issued-at", default="2026-05-27T21:00:00Z")
    parser.add_argument("--gate-policy", default=str(DEFAULT_GATE_POLICY),
                        help="Path to machine-readable gate policy JSON (default: catalog/prometheus-sr-gate-policy-equation-discovery.v0.1.json)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    artifacts: list[dict[str, Any]] = []
    artifacts.extend(emit_pysr_lane(output_dir, args.issued_at, args.gate_policy))
    artifacts.extend(emit_ai_descartes_lane(output_dir, args.issued_at))
    artifacts.extend(emit_sindy_lane(output_dir, args.issued_at))

    gate_policy_path = Path(args.gate_policy)
    artifacts.append(artifact_record("GatePolicyThresholds", gate_policy_path))

    manifest = build_manifest(output_dir, args.issued_at, artifacts)
    manifest["gatePolicyRef"] = str(gate_policy_path)
    manifest["validationSteps"] = [
        {"step": "structural_shacl_pysr", "artifact": str(output_dir / "pysr" / "sr.jsonld"), "tool": "validate_prometheus_jsonld_shacl.py"},
        {"step": "structural_shacl_ai_descartes", "artifact": str(output_dir / "ai-descartes" / "sr.jsonld"), "tool": "validate_prometheus_jsonld_shacl.py"},
        {"step": "gate_policy_enforcement", "artifact": str(output_dir / "pysr" / "gate-evaluation.json"), "tool": "emit_prometheus_gate_evaluation.py", "policyRef": str(gate_policy_path)},
    ]
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Ontogenesis compat validation: validates static platform compatibility manifest
    # (contracts/ontology/prometheus-sr-assertion-compat.manifest.json), not the demo output manifest.
    run_command([
        sys.executable, "tools/validate_prometheus_ontogenesis_compat.py",
    ])

    print(json.dumps({
        "ok": True,
        "manifest": str(manifest_path),
        "artifactCount": len(artifacts),
        "gatePolicyRef": str(gate_policy_path),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
