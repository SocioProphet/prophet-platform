# Repo Governance Replay Ledger

## Purpose

This layer introduces deterministic replay-ledger emission and signature-envelope preparation for the local governance replay MVP.

It remains:
- local-only;
- advisory-only;
- pre-infrastructure.

## Generated artifacts

```text
build/repo-governance-mvp/repo-governance-replay-ledger.jsonl
build/repo-governance-mvp/repo-governance-replay-signature-envelope.json
```

## Execution

```bash
python3 tools/emit_repo_governance_replay_ledger.py
python3 tools/validate_repo_governance_ledger.py
```

## What is recorded

The replay ledger records:

- replay ID;
- observation digest;
- findings artifact digest;
- policy-request artifact digest;
- RDF artifact digest;
- replay-manifest digest;
- deterministic record digest.

## Signature envelope

The current MVP emits a deterministic unsigned signature envelope placeholder.

This intentionally prepares for future:
- ed25519 signing;
- replay attestation;
- distributed replay verification.

## Safety boundary

This replay ledger does not:
- authorize runtime mutation;
- authorize deployment;
- provision infrastructure;
- require Kubernetes;
- require GCP;
- execute workflows.
