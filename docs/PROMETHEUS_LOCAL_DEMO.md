# PROMETHEUS Local Demo Runner

Status: v0.2 consolidated platform demo.

This runner makes the PROMETHEUS MVP legible and repeatable. It emits the current platform evidence chain:

- PySR-style equation discovery through the deterministic fallback engine.
- AgentPlane-compatible SRRunArtifact emission for the PySR-style candidate.
- Automated gate evaluation for the PySR-style candidate.
- JSON-LD semantic handoff artifact for the PySR-style candidate.
- SINDy-style platform dynamics discovery through the fast-path time-series emitter.
- AgentPlane-compatible SRRunArtifact emission for the SINDy-style candidate.

## Boundary

The local demo emits evidence only. It does not create laws, ontology assertions, policies, controllers, or deployment authorizations.

`controlAuthority` is false for both runs.

The JSON-LD artifact is a handoff artifact only. It does not mutate Ontogenesis and does not require WebProtege.

## Usage

Run:

`python3 tools/run_prometheus_local_demo.py --output-dir build/prometheus/local-demo --issued-at 2026-05-27T21:00:00Z`

Then validate:

`python3 tools/validate_prometheus_local_demo.py build/prometheus/local-demo/manifest.json`

## Outputs

The runner writes:

- `pysr/equation-candidate.json`
- `pysr/sr-run-artifact.json`
- `pysr/gate-evaluation.json`
- `pysr/sr.jsonld`
- `sindy/platform-dynamics-candidate.json`
- `sindy/sr-run-artifact.json`
- `manifest.json`

The manifest records artifact hashes so downstream review can verify local-demo integrity.
