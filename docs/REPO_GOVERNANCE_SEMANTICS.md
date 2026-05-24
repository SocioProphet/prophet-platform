# Repo Governance Semantic Replay

## Purpose

This layer lifts the local repo-governance observation packet into deterministic RDF/Turtle and a replay manifest.

It remains local-only and pre-infrastructure.

## Inputs

`contracts/repo-governance/examples/sociosphere-active-spine.observations.v0.json`

## Outputs

Generated locally under:

```text
build/repo-governance-mvp/repo-governance-observations.ttl
build/repo-governance-mvp/repo-governance-replay-manifest.json
```

## Execution

```bash
python3 tools/lift_repo_governance_rdf.py
python3 tools/validate_repo_governance_semantics.py
```

## What is represented

The lift emits RDF-style resources for:

- replay;
- observations;
- repositories;
- source artifacts;
- source blob SHAs;
- parser IDs;
- extraction methods;
- confidence;
- evidence digests.

## Safety boundary

This semantic replay does not:

- mutate repositories;
- authorize actions;
- provision infrastructure;
- deploy workloads;
- require GCP;
- require Kubernetes;
- require Argo CD.

## Next semantic tranche

The next tranche should add an optional `rdflib` implementation while preserving this no-dependency Turtle fallback for bootstrap CI.
