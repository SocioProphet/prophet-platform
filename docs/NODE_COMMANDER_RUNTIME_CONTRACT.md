# Node Commander runtime contract (v0)

## Purpose

This note captures the first concrete runtime contract for the `apps/node-commander/` lane.

It is intentionally narrow and matches the current bootstrap reality:

- local-first operator/control-node runtime
- Podman / OCI packaging
- user-scoped service execution on the control node
- explicit config, state, and log paths

## Runtime identity

- service name: `node-commander`
- canonical app path: `apps/node-commander/`
- canonical HTTP entrypoint: `app.main`
- current mode: `bootstrap`

## Expected packaging

The runtime should support both:

1. local Python service execution for development
2. OCI image packaging for operator-node deployment and promotion tests

The current preferred container runtime assumption is Podman/OCI.

## Runtime directories

The first contract shape assumes three host-visible paths:

- config: `/etc/node-commander`
- state: `/var/lib/node-commander`
- logs: `/tmp/node-commander.log` and `/tmp/node-commander.err.log` during bootstrap, with a later move to a repo-governed or platform-governed destination

## Configuration surface

The runtime should accept, at minimum:

- `mode` (`bootstrap`, later `service`)
- `control_node_profile_ref`
- `promotion_gate_ref`
- `evidence_dir`
- `image_ref`

## Immediate non-goals

This v0 contract does not yet require:

- remote executor dispatch
- full image-promotion policy enforcement
- direct Git repo mutation
- full CloudShell semantics
- attested fog scheduling

Those remain downstream follow-on slices.
