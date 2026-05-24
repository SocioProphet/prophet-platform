# Repo Governance Demo Walkthrough

## Purpose

This walkthrough demonstrates the local pre-infrastructure governance MVP.

The demo intentionally avoids:
- cloud infrastructure;
- Kubernetes;
- Argo CD;
- deployment automation;
- repository mutation.

## Inputs

Checked-in Sociosphere observation packet:

`contracts/repo-governance/examples/sociosphere-active-spine.observations.v0.json`

## Execution

Run the validator:

```bash
python3 tools/validate_repo_governance_mvp.py
```

Run the governance pipeline:

```bash
python3 tools/run_repo_governance_mvp.py
```

Render the governance readout:

```bash
python3 tools/render_repo_governance_readout.py
```

## Generated artifacts

```text
build/repo-governance-mvp/repo-governance-findings.json
build/repo-governance-mvp/repo-governance-policy-requests.json
build/repo-governance-mvp/repo-governance-readout.md
```

## Demonstrated behavior

The demo proves:

1. Sociosphere can emit typed governance observations.
2. Prophet Platform can ingest observations.
3. Findings can be deterministically generated.
4. Policy-review requests can be deterministically generated.
5. Findings remain advisory only.

## Current safety boundary

This MVP does not:
- mutate repositories;
- execute actions;
- authorize deployment;
- provision infrastructure;
- reconcile clusters.

All future runtime mutation must pass through an explicit policy-decision layer.
