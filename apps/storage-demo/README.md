# Storage Demo (Prophet Platform)

This app demonstrates the minimal end-to-end pipeline:

1. Observation (Dolt contract)
2. Promotion → Claim (TypeDB contract)
3. Projection (Neo4j-style graph)

## Flow

Input (Observation):

{
  "observation_id": "obs:demo:1:v1",
  "normalized_payload": {
    "subject": "user123",
    "action": "has_role",
    "object": "admin"
  }
}

Promotion produces:

- Entity(user123)
- Entity(admin)
- Claim(user123 HAS_ROLE admin)

Projection produces:

Nodes:
- user123
- admin

Edge:
- HAS_ROLE

## Purpose

This demo proves:

- deterministic promotion
- separation of operational vs semantic vs projection layers
- replayability

## Next

Implement:
- ingest.py
- promote.py
- project.py
