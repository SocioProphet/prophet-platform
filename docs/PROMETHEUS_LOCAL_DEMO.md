# PROMETHEUS Local Demo Runner

Status: v0.1 consolidated platform demo.

This runner makes the PROMETHEUS MVP legible and repeatable. It emits both current platform paths:

- PySR-style equation discovery through the deterministic fallback engine.
- SINDy-style platform dynamics discovery through the fast-path time-series emitter.

Each path produces a candidate artifact and an AgentPlane-compatible `SRRunArtifact`. The runner also writes a manifest with artifact paths and SHA-256 hashes.

## Boundary

The local demo emits evidence only. It does not create laws, ontology assertions, policies, controllers, or deployment authorizations.

`controlAuthority` is false for both runs.

## Usage

Run:

`python3 tools/run_prometheus_local_demo.py --output-dir build/prometheus/local-demo --issued-at 2026-05-27T21:00:00Z`

Then validate:

`python3 tools/validate_prometheus_local_demo.py build/prometheus/local-demo/manifest.json`

## Outputs

The runner writes:

- `pysr/equation-candidate.json`
- `pysr/sr-run-artifact.json`
- `sindy/platform-dynamics-candidate.json`
- `sindy/sr-run-artifact.json`
- `manifest.json`

The manifest records artifact hashes so downstream review can verify local-demo integrity.
