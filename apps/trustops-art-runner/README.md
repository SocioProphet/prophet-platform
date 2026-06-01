# TrustOps ART Runner

`trustops-art-runner` is the first TrustOps Fabric runtime slice for Prophet Platform.

It is intentionally a thin runner boundary. ART is treated as an isolated provider backend, not a core platform dependency. The first slice emits a deterministic synthetic `trustops-receipt.v1` robustness receipt so the platform can wire manifest input, receipt output, policy action, ledger ingestion, and guardrail consumption before adding heavyweight adversarial dependencies.

## Goals

- Consume a functional service manifest.
- Run the `art-smoke` TrustOps profile.
- Emit a normalized `trustops-receipt.v1` robustness receipt.
- Preserve data-boundary guarantees: raw data is not exported by default.
- Keep provider details behind the runner interface.

## Example

```bash
PYTHONPATH=apps/trustops-art-runner/src \
  python3 -m trustops_art_runner.cli run \
  --profile art-smoke \
  --manifest apps/trustops-art-runner/examples/functional-service.demo.json \
  --output build/trustops-art-runner/receipt.json
```

## Next implementation step

Replace the synthetic metric backend with isolated ART-backed attack probes while preserving the same receipt contract and CLI/API surface.
