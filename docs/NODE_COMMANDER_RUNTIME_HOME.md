# Node Commander runtime home (v0)

## Purpose

This note records why `prophet-platform` is the eventual runtime and deployment home for the real `Node Commander` service.

## Why this belongs here

`prophet-platform` is explicitly the runtime and deployment hub for the SocioProphet platform, and its `apps/` directory is the home for deployable services.

That makes this repository the correct downstream home for the production-facing `Node Commander` runtime once the implementation moves beyond the current bootstrap envelope.

## Current status

The current operator-side work has already proven a first local runtime envelope:

- nix-darwin-managed control node on macOS
- Podman / OCI build, push, and local run path
- launch-agent-managed local runtime invocation
- local-first posture for node control and pre-promotion validation

But the current image is still a bootstrap placeholder, not the real service.

## Decision

When the real runtime is ready, it should land in this repository as an `apps/node-commander/` service rather than staying only in host-local bootstrap code.

Expected runtime responsibilities include:

- local or delegated node command execution
- OCI-backed service packaging
- explicit config/state/evidence directories
- integration with downstream execution/evidence surfaces
- support for build validation and image-promotion workflows

## Repo split

- `SourceOS-Linux/sourceos-spec`
  - canonical ADRs and typed contracts
- `SociOS-Linux/source-os`
  - workstation/bootstrap application of the control-node profile
- `SocioProphet/agentplane`
  - execution/evidence/replay consumption seam
- `SocioProphet/prophet-platform`
  - real runtime/service implementation home for `Node Commander`

## Immediate implication

This note does **not** move the bootstrap placeholder into `prophet-platform` yet. It only freezes the eventual runtime landing zone so implementation work does not drift into the wrong repository.
