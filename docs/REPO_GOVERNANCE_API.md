# Repo Governance Local API

## Purpose

This API provides a local replay surface for the pre-infrastructure governance MVP.

The API intentionally avoids:
- cloud infrastructure;
- Kubernetes;
- Argo CD;
- deployment orchestration;
- repository mutation.

## Endpoints

### Health

`GET /healthz`

Returns:
- local mode;
- advisory-only status;
- mutation authorization state.

### Validate

`GET /validate`

Runs:
- governance contract validation;
- local replay validator.

### Replay

`POST /replay`

Runs:
- governance replay pipeline;
- findings generation;
- policy-request generation;
- markdown readout rendering.

### Readout

`GET /readout`

Returns:
- rendered markdown governance report.

### Lineage

`GET /lineage`

Returns:
- observation nodes;
- finding nodes;
- policy-request nodes;
- lineage edges.

## Safety boundary

All outputs remain advisory only.

This API does not:
- mutate repositories;
- execute workflows;
- authorize deployment;
- reconcile clusters;
- provision infrastructure.

## Local execution

Example local execution:

```bash
python3 apps/repo-governance-api/main.py
```

Optional FastAPI execution:

```bash
uvicorn apps.repo-governance-api.main:app --reload
```
