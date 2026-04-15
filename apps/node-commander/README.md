# node-commander

Bootstrap runtime starter for the local-first SourceOS / SociOS control-node lane.

## Purpose

`node-commander` is the small operator-side runtime that gives the control node a concrete, deployable command surface before the larger image-generation and validation flow is fully wired.

This starter is intentionally narrow. It proves the runtime home and service shape inside `prophet-platform` without pretending the full implementation is finished.

## Current scope

This starter owns:

- `/healthz` — liveness only
- `/readyz` — local runtime readiness only
- `/v1/node-commander/status` — minimal local status envelope
- `/v1/node-commander/heartbeat` — explicit bootstrap heartbeat surface

## Non-goals in this starter

This starter does not yet:

- issue real node control commands
- run build/promotion gates itself
- own the canonical contract definitions
- replace `agentplane` execution/evidence ownership

## Upstream / downstream split

- canonical contracts: `SourceOS-Linux/sourceos-spec`
- workstation/bootstrap lane: `SociOS-Linux/source-os`
- execution/evidence seam: `SocioProphet/agentplane`
- runtime implementation: this repo
