# Organization Governance Control Plane Contracts

This directory contains the platform-owned contract spine for **Organization Governance Control Plane v0**.

The product loop is:

```text
Objective → Workroom → Actor → Role → Policy → Asset → Action → Evidence → Review → Outcome → Score → Learning
```

## Why this exists

The competitive benchmark is not an agent runtime. It is a buyer-visible control plane for governed human-agent institutional work.

SocioProphet already has the deeper machinery across AgentPlane, Policy Fabric, Ontogenesis, Agent Registry, Model Governance Ledger, Sociosphere, Delivery Excellence, Sherlock, Prophet Workspace, and SourceOS. These contracts compress that machinery into one product-readable loop.

## Files

- `orggov-control-plane.v0.1.schema.json` — platform contract for the integrated control-loop record.
- `orggov-control-plane.v0.1.example.json` — dogfood fixture tied to `SocioProphet/prophet-platform#406`.

## Validation

```bash
python3 tools/validate_orggov_contracts.py
```

## Ownership split

- `prophet-platform` owns runtime contracts and smoke-test fixtures.
- `ontogenesis` owns ontology terms and SHACL gates.
- `prophet-workspace` owns the control-room user experience.
- `agent-registry` owns actor, role, authority, grants, sessions, and revocation.
- `policy-fabric` owns role/action/asset policy decisions and replay packs.
- `agentplane` owns execution evidence and replay.
- `model-governance-ledger` owns model, adapter, dataset, eval, rollback, and revocation receipts.
- `sociosphere` owns estate topology, ownership, and propagation rules.
- `delivery-excellence` owns KPI/OKR/adoption scorecards.
- `sherlock-search` owns evidence search and control-graph indexing.
- `sourceos-syncd` owns local-first state integrity evidence.
