# TrustOps ART-Smoke Runner v0.1

## Purpose

`apps/trustops-art-runner` is the first Prophet Platform runtime slice that emits a `trustops-receipt.v1` receipt for the TrustOps Fabric path.

This first tranche is synthetic and receipt-first. It intentionally does not import ART into platform core. It proves the platform can accept a manifest, evaluate a deterministic synthetic robustness metric, and emit a provider-neutral TrustOps receipt that downstream systems can consume.

## Boundary

The runner emits evidence only.

It does not:

- mutate runtime state;
- call Guardrail Fabric;
- mutate Agent Registry authority;
- write Model Governance Ledger records;
- promote, rollback, revoke, or waive anything;
- import ART into platform core.

Downstream surfaces remain separate:

```text
prophet-platform TrustOps runner -> trustops-receipt.v1 evidence
model-governance-ledger -> evidence ledger record
guardrail-fabric -> runtime-control decision
agent-registry -> authority mutation decision
agentplane -> governed attempt admission consumer
```

## CLI

```bash
PYTHONPATH=apps/trustops-art-runner/src \
python3 -m trustops_art_runner.cli run \
  --profile art-smoke \
  --manifest apps/trustops-art-runner/examples/functional-service.art-smoke.manifest.json \
  --output build/trustops-art-runner/trustops-receipt.art-smoke.json
```

## Validation

```bash
python3 tools/validate_trustops_art_receipt.py build/trustops-art-runner/trustops-receipt.art-smoke.json
```

Or run the full smoke:

```bash
make trustops-art-runner-smoke
```

## Acceptance posture for #398

This tranche satisfies the first functional path:

- synthetic manifest in;
- valid `trustops-receipt.v1` out;
- metrics-only redacted evidence refs;
- runner provenance;
- policy decision;
- downstream action hints only;
- no platform core ART import.

A later tranche can replace the synthetic metric generator with an actual ART-backed runner behind the same receipt boundary.
