# Repo Governance Visualization UI

## Purpose

This visualization layer provides a local exploratory interface for the governance replay MVP.

The UI intentionally remains:
- local-only;
- advisory-only;
- pre-infrastructure;
- deployment-free.

## Current capabilities

The UI renders:
- governance replay status;
- observation nodes;
- finding nodes;
- policy-request nodes;
- lineage edges;
- markdown governance readout.

## Current architecture

```text
Sociosphere observations
  → replay API
    → findings
      → policy requests
        → lineage graph
          → visualization UI
```

## Local serving model

The UI is static HTML and can be served directly from the local FastAPI-compatible replay service.

Current file:

`apps/repo-governance-api/static/index.html`

## Safety boundary

The UI does not:
- mutate repositories;
- execute workflows;
- authorize deployments;
- provision infrastructure;
- trigger runtime actions.

All displayed governance artifacts remain advisory only.
