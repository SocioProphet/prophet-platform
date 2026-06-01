# DevSecOps Workroom External Fixture Sync v0.1

Status: fixture synchronization process  
Plane: Prophet Platform CI / cross-plane contract validation  
Related: `fixtures/external/README.md`, `fixtures/external/mirror-manifest.json`, `tools/validate_external_fixture_mirrors.py`

## Purpose

This process governs how Prophet Platform mirrors AgentPlane and Sociosphere fixture records for DevSecOps Workroom cross-plane validation.

The goal is to prevent drift and overclaiming while still allowing Prophet Platform CI to validate cross-plane contracts without live runtime access.

## Rule of authority

External fixture mirrors are not authoritative.

Authoritative source remains in the owning plane:

- AgentPlane owns runtime sandbox run fixtures and schemas.
- Sociosphere owns environment state and runtime evidence ingestion fixtures.
- Prophet Platform owns Workroom projections and product/API reports.

A Prophet mirror is a pinned compatibility artifact. It is not proof that upstream currently matches unless a sync review says so.

## Sync triggers

Run this sync process when any of the following changes:

1. AgentPlane runtime sandbox run schema or fixtures.
2. Sociosphere runtime evidence ingestion fixtures or validator.
3. Prophet Workroom cross-plane handoff validator.
4. Workroom parity ledger or claim boundary.
5. Shared receipt identity semantics.
6. Runtime parity state names or receipt reference names.

## Sync steps

1. Identify the upstream fixture and its owning plane.
2. Confirm the upstream validator for that fixture is green in its owning repo.
3. Copy the fixture into `fixtures/external/<plane>/` using a filename that preserves its state and purpose.
4. Update `fixtures/external/mirror-manifest.json` with:
   - mirror path;
   - source plane;
   - source repo;
   - source path;
   - purpose;
   - required non-claim posture.
5. Ensure the mirrored fixture contains explicit non-claims:
   - no infrastructure execution or allocation;
   - no Signadot feature parity certification;
   - no production mutation authority.
6. Run Prophet Platform validators:

```text
python tools/validate_external_fixture_mirrors.py
python tools/validate_cross_plane_runtime_handoff.py
python tools/validate_devsecops_workroom.py
```

7. Update the related GitHub issue with:
   - source fixture path;
   - mirror path;
   - reason for sync;
   - claim boundary preserved.

## Drift states

A mirror can be in one of four states:

- `current` — reviewed against upstream and compatible with the current cross-plane contract;
- `pinned` — intentionally kept at an older state for compatibility testing;
- `future` — fixture shape is staged before the upstream repo has adopted it;
- `stale` — known drift exists and must not be used for parity claims.

The current v0.1 manifest uses `future/` source paths for shared receipt fixtures where the cross-plane path is staged in Prophet before equivalent upstream fixtures are committed.

Future mirrors must never be described as upstream truth.

## Failure handling

If `validate_external_fixture_mirrors.py` fails:

- do not update parity claims;
- inspect missing mirror, source metadata, or non-claim text;
- repair manifest or fixture text first.

If `validate_cross_plane_runtime_handoff.py` fails:

- treat it as a cross-plane compatibility failure;
- do not claim runtime receipt parity;
- repair the fixture chain or update the handoff contract.

## Claim boundary

Allowed claims after a passing mirror validation:

- Prophet Platform has a governed fixture mirror for cross-plane contract validation.
- Prophet Platform CI can test fixture-level handoff semantics.

Forbidden claims:

- upstream runtime is live;
- AgentPlane executed a sandbox;
- Sociosphere observed live runtime state;
- full Signadot-style feature parity is certified;
- production remediation is authorized.

## Non-claims

This sync process does not execute infrastructure.

This sync process does not fetch live upstream content automatically.

This sync process does not certify full runtime parity.

This sync process does not make Prophet Platform authoritative over AgentPlane or Sociosphere records.
