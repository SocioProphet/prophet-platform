# PROMETHEUS Consolidated Runner Status

Status: implemented as the current Prophet Platform local-demo runner.

The consolidated PROMETHEUS runner is `tools/run_prometheus_local_demo.py`.

It performs the current governed local execution chain:

1. emits a PySR-style `EquationCandidate` through the deterministic fallback engine;
2. emits an AgentPlane-compatible `SRRunArtifact` for the PySR-style candidate;
3. emits an automated gate-evaluation artifact;
4. emits a JSON-LD `SRAssertionProposal` handoff artifact for semantic review;
5. emits a SINDy-style `PlatformDynamicsCandidate` through the platform-dynamics fast path;
6. emits an AgentPlane-compatible `SRRunArtifact` for the SINDy-style candidate;
7. emits a manifest with SHA-256 hashes for all six generated artifacts.

## Authority boundary

This runner is an evidence-producing platform utility only.

It does not:

- create scientific law assertions;
- mutate Ontogenesis;
- grant policy authority;
- grant controller authority;
- authorize deployment;
- write to memory mesh;
- promote candidates to admitted knowledge.

`controlAuthority` remains `false` for both the PySR-style and SINDy-style runs.

## Commands

Run the full local evidence chain:

```bash
python3 tools/run_prometheus_local_demo.py \
  --output-dir build/prometheus/local-demo \
  --issued-at 2026-05-27T21:00:00Z
```

Validate the emitted manifest and artifacts:

```bash
python3 tools/validate_prometheus_local_demo.py build/prometheus/local-demo/manifest.json
```

## Dedicated CI

The dedicated workflow is `.github/workflows/prometheus-local-demo.yml`.

The workflow runs the consolidated local demo, validates the manifest, and uploads the resulting artifact bundle.

This keeps PROMETHEUS validation narrow and avoids expanding the broad platform `make validate` blast radius.

## Next governance tranche

The next missing control-plane layer is not another discovery engine. It is the AgentPlane automated gate-policy contract for machine-readable promotion eligibility.
