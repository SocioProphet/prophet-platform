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
        "manifestVersion": "0.2.0",
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
                "applicationMode": "platform_dynamics",
                "methodFamily": "sindy",
                "candidateArtifact": str(output_dir / "sindy" / "platform-dynamics-candidate.json"),
                "runArtifact": str(output_dir / "sindy" / "sr-run-artifact.json"),
                "controlAuthority": False,
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run consolidated PROMETHEUS local demo")
    parser.add_argument("--output-dir", default="build/prometheus/local-demo")
    parser.add_argument("--issued-at", default="2026-05-27T21:00:00Z")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    pysr_dir = output_dir / "pysr"
    sindy_dir = output_dir / "sindy"
    pysr_dir.mkdir(parents=True, exist_ok=True)
    sindy_dir.mkdir(parents=True, exist_ok=True)

    pysr_candidate = pysr_dir / "equation-candidate.json"
    pysr_run = pysr_dir / "sr-run-artifact.json"
    pysr_gate = pysr_dir / "gate-evaluation.json"
    pysr_jsonld = pysr_dir / "sr.jsonld"
    sindy_candidate = sindy_dir / "platform-dynamics-candidate.json"
    sindy_run = sindy_dir / "sr-run-artifact.json"

    run_command([
        sys.executable, "tools/prometheus_pysr_mvp.py",
        "--engine", "mvp_linear_fallback",
        "--data", "tests/fixtures/prometheus/pysr-mvp-linear.csv",
        "--target", "y",
        "--dataset-uri", "urn:dataset:prometheus:pysr-mvp-linear",
        "--target-unit", "meter",
        "--feature-unit", "x=meter",
        "--generated-at", args.issued_at,
        "--output", str(pysr_candidate),
    ])

    run_command([
        sys.executable, "tools/prometheus_emit_sr_run_artifact.py",
        "--candidate", str(pysr_candidate),
        "--run-id", "urn:prometheus:sr-run:pysr-local-demo:001",
        "--chronos-carrier-id", "urn:chronos:carrier:prometheus:local-demo:pysr",
        "--random-seed", "42",
        "--issued-at", args.issued_at,
        "--output", str(pysr_run),
    ])

    run_command([
        sys.executable, "tools/emit_prometheus_gate_evaluation.py",
        "--candidate", str(pysr_candidate),
        "--run-artifact", str(pysr_run),
        "--dataset", "tests/fixtures/prometheus/pysr-mvp-linear.csv",
        "--evaluation-id", "urn:prometheus:gate-evaluation:pysr-local-demo:001",
        "--issued-at", args.issued_at,
        "--output", str(pysr_gate),
    ])

    run_command([
        sys.executable, "tools/emit_prometheus_jsonld_review.py",
        "--candidate", str(pysr_candidate),
        "--run-artifact", str(pysr_run),
        "--gate-evaluation", str(pysr_gate),
        "--review-id", "urn:prometheus:jsonld:pysr-local-demo:001",
        "--review-surface", "automated_shacl_gate",
        "--issued-at", args.issued_at,
        "--output", str(pysr_jsonld),
    ])

    run_command([
        sys.executable, "tools/prometheus_sindy_fast_path.py",
        "--data", "tests/fixtures/prometheus/sindy-fast-path-linear.csv",
        "--time-column", "t",
        "--value-column", "q",
        "--dataset-uri", "urn:dataset:prometheus:sindy-fast-path-linear",
        "--generated-at", args.issued_at,
        "--output", str(sindy_candidate),
    ])

    run_command([
        sys.executable, "tools/prometheus_emit_sr_run_artifact.py",
        "--candidate", str(sindy_candidate),
        "--run-id", "urn:prometheus:sr-run:sindy-local-demo:001",
        "--chronos-carrier-id", "urn:chronos:carrier:prometheus:local-demo:sindy",
        "--issued-at", args.issued_at,
        "--output", str(sindy_run),
    ])

    artifacts = [
        artifact_record("EquationCandidate", pysr_candidate),
        artifact_record("SRRunArtifact", pysr_run),
        artifact_record("AutomatedGateEvaluation", pysr_gate),
        artifact_record("SRAssertionProposalJSONLD", pysr_jsonld),
        artifact_record("PlatformDynamicsCandidate", sindy_candidate),
        artifact_record("SRRunArtifact", sindy_run),
    ]
    manifest = build_manifest(output_dir, args.issued_at, artifacts)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "manifest": str(manifest_path), "artifactCount": len(artifacts)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
