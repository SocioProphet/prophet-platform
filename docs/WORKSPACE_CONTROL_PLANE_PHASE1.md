# Workspace Control Plane — Phase 1 (frozen schemas)

Implements **Phase 1** of the Workspace Control Plane control spec: *freeze the
object model, event schema, and manifest schemas before runtime code exists, so
drift cannot creep in.* Borrows structure from W3C PROV (entity/activity/agent),
OpenLineage (run/job), and TUF/Sigstore (signed manifests with expiry,
delegation, revocation).

These schemas are the contract every later phase builds against.

## Frozen objects (`contracts/workspace-control-plane/schemas`)

| Schema | Spec | Purpose |
|---|---|---|
| `event.v0` | D2, D12 | Canonical append-only, object-centric event: `case_id` + `object_refs` + `activity` + `actor` + `inputs`/`outputs`/`state_delta`, PROV framing. |
| `asset.v0` | D6 | Content-addressed, versioned asset bound to a root (distinct from claims). |
| `claim.v0` | D6 | Traceable proposition: provenance + `derived_from` lineage, confidence, `epistemic_level`, validity window, `contradiction_status`. |
| `attention-mark.v0` | D5 | Resurfacing marker: `mode` ∈ pin/watch/revisit/incubate/hold/forget, triggers, decay, suppression. |
| `workflow-run.v0` | D11, D12 | Durable run: status incl. `awaiting_approval`, `event_history_ref`, `outbox`. |
| `capability-manifest.v0` | D7, D8, D9 | **Signed** capability manifest (separate plane from data topics); expiry/delegation/revocation. |
| `topic-manifest.v0` | D8, D9 | **Signed** data-topic manifest naming the overlay transport (hypercore/hyperswarm/autobase). |
| `catalog-entry.v0` | D9 | **Signed** TUF-role trust-catalog entry (root/targets/snapshot/timestamp) with delegation threshold + multi-sig. |
| `discovery-policy.v0` | D7 | Deterministic resolution order (local → MCP → catalog → remote) + trust requirements. |

## Invariants the schemas enforce (with teeth — see tests)

- Claims must carry `epistemic_level` (governing enum) and `contradiction_status`.
- Capability, data-topic, and trust are **separate kinds** (D8) — a callable tool
  is not a data topic is not a permission grant.
- Signed manifests **require** a signature; catalog entries require ≥1 signature
  and a valid TUF role.
- `discovery-policy.resolution_order` is a constrained enum — the planner cannot
  declare "crawl the internet."
- Events are object-centric: `case_id` + `object_refs` + `activity` + `actor` are
  mandatory.

## Validation

`tools/validate_control_plane_contracts.py` checks every schema is valid JSON
Schema and that its committed example conforms, and asserts all nine frozen
objects are present. `tools/tests/test_control_plane_contracts.py` adds
negative tests proving each key invariant has teeth. Path-filtered CI:
`.github/workflows/control-plane-contracts.yml`.

## Where the already-built lanes fit

The Web Intelligence lane, the Crystal Atlas value-driver seam, and the
governed-metric events already emit warranted, provenance-bearing claims — they
are early producers against this object model. Later phases (connectors, rails,
trust broker, overlay transport, Temporal outbox, memory tiers) attach to these
frozen contracts.
