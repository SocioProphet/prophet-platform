# agentic-os-api

The coordination service for the **agentic operating system** — agent pods
pursuing objectives across the estate under a governed capture cadence.

Serves the canonical agentic-OS objects (`Opportunity` / `AgentPod` /
`ReadinessScore` / `CaptureCadence`) that the cockpit console renders and the
pods coordinate against. Object shapes conform to the **sourceos-spec**
agentic-OS contract and compose over **prophet-workspace** (ProfessionalWorkroom
/ OrgGovControlRoom) and **prophet-mesh** (agent-choir + estate graph).

Read-only seed today; a live registry adapter will resolve the same URNs from the
workspace + estate graph.

## Endpoints
- `GET /health`
- `GET /opportunities` · `GET /opportunities/{slug}` (with readiness + cadence)
- `GET /pods`
- `GET /cadence`

## Run
```
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```
